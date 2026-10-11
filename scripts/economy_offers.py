"""Economy sim v2: what is on offer to a guild right now, each priced in copper and days.

Plan: docs/plans/economy_sim_v2.md. The hand-written policies reach for the same few levers (the
Axe, the Champion's stake, the Library's Dictionary mission, the starting kit to sell); this lists
them from the game's own tables, so a planner can pick among them and a recording can be checked
against what was available. Nothing here plays a day: it reads `arena`, `missions`, `economy`,
`items` and `craft_level` and states what each offer costs up front, what it pays, and how long it
takes. A gain that depends on a fight is the purse as printed (no win rate): the sim's library
gives that.

    python scripts/economy_offers.py                  # a fresh three-member guild
    python scripts/economy_offers.py --size 4 --money 400
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import economy_activities as act

from gartok import craft_level, economy, items, missions
from gartok.guild import Guild

HOURS_PER_DAY = 24
WORK_SHIFT_HOURS = 16
KINDS = ("tool", "kit", "bout", "mission")

# where a mission's goal item comes from when the market does not sell it, and the hours one trip
# there takes beyond the walk (a hunt shift, a dungeon delve)
SOURCES = {
    "1sqm Hide": ("hunt", WORK_SHIFT_HOURS),
    "Red Mushroom": ("forage", WORK_SHIFT_HOURS),
}


@dataclass(frozen=True)
class Offer:
    kind: str           # "tool" | "kit" | "bout" | "mission"
    name: str
    cost: int           # copper up front: a stake, materials, a tool's price
    gain: int           # copper it pays: a purse, a reward, a sale (a tool: the extra wage of one shift)
    hours: float        # time it takes, walking and working; 0 when it is instant
    covered: bool       # the guild holds `cost` right now
    note: str = ""

    @property
    def net(self):
        return self.gain - self.cost

    @property
    def per_day(self):
        """Net copper a day it ties the guild up; `None` for an instant offer."""
        return self.net / (self.hours / HOURS_PER_DAY) if self.hours else None


def tool_offers(members, money):
    """Each work node's own tool, for the members who do not own it yet: the extra wage of one
    16 h shift is the gain, so `cost / gain` is the shifts it takes to pay back."""
    out = []
    for node_id, tool in economy.WORK_TOOLS.items():
        lacking = [u for u in members if economy.work_level(u, node_id) < economy.LUMBER_LEVEL_OWN_AXE]
        if not lacking:
            continue
        gain = economy.work_pay(node_id, WORK_SHIFT_HOURS, 1) - economy.work_pay(node_id, WORK_SHIFT_HOURS, 0)
        cost = items.get(tool).price * len(lacking)
        out.append(Offer("tool", f"{tool} for {len(lacking)}", cost, gain * len(lacking), 0, money >= cost,
                         f"{economy.work_pay(node_id, WORK_SHIFT_HOURS, 1)} a shift instead of "
                         f"{economy.work_pay(node_id, WORK_SHIFT_HOURS, 0)}, pays back in "
                         f"{-(-cost // max(gain * len(lacking), 1))} shift(s)"))
    return out


def kit_offers(members):
    """The starting kit that is not food or coin, at the market's buying price."""
    out = []
    for u in members:
        for name, qty in u._base_inventory:
            if items.is_coin(name) or items.is_food(name):
                continue
            out.append(Offer("kit", f"sell {qty}x {name} ({u.name})", 0, economy.sell_price(name) * qty, 0, True))
    return out


def bout_offers(size, money):
    """Every staked bout: the stake for the fighters it takes, and the whole purse."""
    out = []
    walk = 2 * act.trip_hours(size, 0, "arena")
    for make in act.BOUTS.values():
        bout = make()
        fighters = min(size, bout.squad_max) if bout.squad_max else size
        stake = bout.entry * fighters
        out.append(Offer("bout", bout.name, stake, bout.purse, walk, money >= stake,
                         f"{fighters} fighters, win chance not priced"))
    return out


def _material_cost(name):
    """(copper, source) for one goal item: bought at the market, or fetched."""
    if name in SOURCES:
        return 0, SOURCES[name][0]
    item = items.get(name)
    if item is not None and economy.freely_buyable(name):
        return item.price, "market"
    return 0, "found"


def mission_offers(guild, size, money):
    """The one-off jobs the guild could take today, with what their goal costs to fetch or make."""
    out = []
    here = {t.id: t for node_id in {t.node for t in missions.TEMPLATES.values()}
            for t in missions.offers_at(guild, node_id)}
    for t in here.values():
        if not t.reward:
            continue
        cost, source = _material_cost(t.goal_item)
        cost *= t.goal_qty
        hours = 0.0
        note = f"{t.goal_qty}x {t.goal_item} ({source})"
        if t.goal_item == "Any Dictionary":
            cost = sum(items.get(n).price for n in economy.LIBRARY_SUPPLIES)
            hours = craft_level.batch_hours(items.CRAFTING_RECIPES["Dictionary of Ankarin"])
            hours += act.WORK_DAY_HOURS
            note = "Paper and Ink at the Library, a Hide from a hunt, one craft"
        if source in ("hunt", "forage"):
            hours += SOURCES[t.goal_item][1]
        if source != "market" or hours:
            hours += 2 * act.trip_hours(size, 0, "wilds" if source in ("hunt", "forage") else t.node)
        if source in ("hunt", "forage") and t.goal_qty > 1:
            note += ", hours price one trip"
        if t.deadline_days:
            note += f", {t.deadline_days} days to deliver"
        out.append(Offer("mission", t.name, cost, t.reward, hours, money >= cost, note))
    return out


def all_offers(guild, money):
    members = [m for g in guild.groups for m in g.members]
    size = len(members)
    offers = (tool_offers(members, money) + kit_offers(members) + bout_offers(size, money)
              + mission_offers(guild, size, money))
    return sorted(offers, key=lambda o: (KINDS.index(o.kind), -(o.per_day if o.per_day is not None else o.net)))


def report(offers):
    lines = [f"{'kind':8} {'offer':34} {'cost':>6} {'pays':>6} {'net':>6} {'days':>5} {'net/day':>8}  note"]
    for o in offers:
        days = f"{o.hours / HOURS_PER_DAY:.1f}" if o.hours else "-"
        per_day = f"{o.per_day:.0f}" if o.per_day is not None else "-"
        mark = "" if o.covered else " (cannot afford)"
        lines.append(f"{o.kind:8} {o.name[:34]:34} {o.cost:>6} {o.gain:>6} {o.net:>6} {days:>5} {per_day:>8}  {o.note}{mark}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--size", type=int, default=3)
    ap.add_argument("--money", type=int, default=None, help="copper in hand (default: what the fresh guild holds)")
    args = ap.parse_args()
    guild = Guild(act.make_squad(args.size, 0), node="city")
    members = [m for g in guild.groups for m in g.members]
    money = sum(m.money for m in members) if args.money is None else args.money
    print(f"{len(members)} members, ${money} in hand\n")
    print(report(all_offers(guild, money)))


if __name__ == "__main__":
    main()
