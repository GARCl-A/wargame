"""What a character of racial level X has earned by the time they get there: the copper a body
of that level could have put into kit; `outfit.KIT_BUDGET` is read off it.

The guild sim (`economy_guild.py`) does not answer it: its policies earn and stay put, none of
them climbs past racial level 1 in 200 days. So this follows one *career* over layer 1's
activity rows (`economy_activities.build_tables`, real fights at each level) and three rows of
its own that layer 1 has not got:

  - the supply run (Ledger Hold -> Frontier Outpost and back): `SUPPLY_RUN_PAY`, work XP up to
    `SUPPLY_RUN_LEVEL`, an ambush roll per leg against real fights with
    `encounters.roll_supply_ambush`; a lost fight loses the cargo and the pay. The talk before
    the fight is not played: every ambush is fought.
  - crafting, one row per recipe level: the open or talent recipe with the best margin an hour
    (inputs the shops sell at their buy price, scarce ones at their sell price, the product at
    its sell price, a neutral haggle); 16 h a day at an average roll, the profit held to the
    buying shop's daily `MARKET_CASH_REGEN` split by the group. The talent pick a talent recipe
    costs is not counted.
  - magic by study: the Faith rite (the school anyone may take; Blood needs magic blood) then
    every Faith spell, scroll bought and the tavern's study room rented, at an average roll; its
    XP and copper are spread evenly over the whole program. The 2 reputation the rite asks for
    and magic XP from kills are not counted.

The group grows with the level: `group_size` is what a leader of the character's racial level
holds (`Group.capacity`: `BASE_CAPACITY` + CHA mod + racial level // 2, the CHA mod `--cha`).
The hunt and the supply run are fought by the whole group and split its loot; the arena's bouts
field `ARENA_SQUAD` a side whatever the group, and the craft till is shared by the group.

The career:

  - every day the character takes the in-band activity (`economy_activities.ROLES` plus
    `EXTRA_ROLES`, one-offs left out) that moves the racial track fastest: track levels gained
    per day, each track's XP over the gap to its next level; ties go to the better net copper.
    When nothing in band teaches, every activity is open.
  - an activity whose net is a loss is skipped while the purse cannot pay it (a day of the best
    safe pay refills it), and one that kills more than `--risk` of the group a day is never
    taken (the Wilds lose ~45% a run at 80%).
  - combat XP is read off the rows at the character's combat level, work marks at their work
    level, copper, deaths and the band at their racial level (racial = combat + work + magic,
    halved).
  - everything is the expectation, not a draw: copper is net of the cheapest meal, survival is
    the chance of living through every run on the way.

Level 0 is the starting kit: the occupation's weapon and item plus the starting coins, at the
market's buy price, averaged over random characters. Every figure is per character.

    python scripts/wealth_by_level.py                     # a player who wins 80% of fights
    python scripts/wealth_by_level.py --skill 0.95 --risk 1   # the run KIT_BUDGET was read off
    python scripts/wealth_by_level.py --skill 0.95 --cha 1 --extras
"""

from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
from dataclasses import dataclass

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import economy_activities as act

from gartok import (
    arena,
    craft_level,
    economy,
    encounters,
    group,
    items,
    loot,
    magic,
    orders,
    progression,
    rite,
)
from gartok.guild import Guild
from gartok.items import ItemType
from gartok.scenario import ErmosScenario
from gartok.unit import Unit

DAY_LIMIT = 730
SUPPLY = "Supply run"
STUDY = "Study Faith magic"
MAGIC_SCHOOL = "faith"
NO_TOP = 99
ARENA_SQUAD = arena.STAGE2_ENEMIES
ARENA_BOUTS = ("arena", "brawl", "ctf")
# the model's own bands: the supply ambush is 4-10 soldiers of level 3-8
EXTRA_ROLES = {SUPPLY: ("income", 4, NO_TOP), STUDY: ("leveling", 0, NO_TOP)}


@dataclass
class Activity(act.Row):
    magic_xp: float = 0.0              # magic XP per member per run
    magic_cap: float = 0.0             # the most magic XP the activity can ever give


def kit_value(unit):
    """Copper the market would charge for what `unit` carries: slots and pack, coins at face."""
    total = 0
    for name in (unit.equipped_weapon, unit.equipped_offhand, unit.equipped_armor,
                 unit.equipped_artifact, unit.equipped_tongue):
        if name:
            total += economy.buy_price(name)
    for inst in unit.inventory:
        if items.is_coin(inst.name):
            total += items.COIN_VALUE[inst.name] * inst.qty
        else:
            total += economy.buy_price(inst.name) * inst.qty
    return total


def starting_wealth(samples=500):
    """(mean kit, mean coins) of a fresh character."""
    units = [Unit("player") for _ in range(samples)]
    coins = [u.money for u in units]
    return statistics.mean(kit_value(u) for u in units) - statistics.mean(coins), statistics.mean(coins)


def supply_row(size, level, trials, skill):
    """A run to the Frontier Outpost and back with the wagon, each leg ambushed at
    `SUPPLY_RUN_AMBUSH_CHANCE`, the caravan on the road day and night: won at `skill` (never
    below the AI's own rate, which a big group beats), loot, XP and casualties drawn from the fights the AI played, split by outcome
    (casualties in a win scaled by `relief`, as layer 1's hunt does)."""
    fights = []
    for _ in range(trials):
        squad = act.make_squad(size, level)
        b = act.play(squad, encounters.roll_supply_ambush(), ErmosScenario(), lethal=True)
        fallen = [c for c in b.player_units if not c.alive]
        won = b.winner == "player"
        fights.append((won, act.loot_value(loot.field_loot(b, fallen)) if won else 0,
                       len(fallen) / size, statistics.mean(c.combat_xp_earned for c in b.player_units)))
    ai_rate = sum(f[0] for f in fights) / trials
    skill = max(skill, ai_rate)
    won = [f for f in fights if f[0]] or [(True, 0, 0.0, 0.0)]
    lost = [f for f in fights if not f[0]] or [(False, 0, 1.0, 0.0)]
    relief = min(1.0, (1 - skill) / (1 - ai_rate)) if ai_rate < 1 else 1.0
    mean = statistics.mean
    ambush = economy.SUPPLY_RUN_AMBUSH_CHANCE
    through = 1 - ambush * (1 - skill)                 # a leg the caravan gets past
    fought = ambush + through * ambush                 # the second leg only after the first
    finished = through ** 2
    guild = Guild(act.make_squad(size, level), node=orders.SUPPLY_START)
    hours = orders.supply_hours(guild, guild.groups[0])
    marks = act.work_marks(economy.SUPPLY_RUN_HOURS, economy.SUPPLY_RUN_LEVEL, level)
    return Activity(SUPPLY, hours,
                    income=finished * economy.SUPPLY_RUN_PAY + fought * skill * mean(f[1] for f in won) / size,
                    combat_xp=fought * (skill * mean(f[3] for f in won) + (1 - skill) * mean(f[3] for f in lost)),
                    work_marks=finished * marks, win_rate=skill,
                    death_rate=fought * (skill * mean(f[2] for f in won) * relief
                                         + (1 - skill) * mean(f[2] for f in lost)),
                    runs_per_day=24 / (hours + orders.APPROACH_HOURS),
                    note=f"the AI wins {ai_rate * 100:.0f}% of these ambushes; {fought:.2f} fights a run")


def craft_rows(size, level):
    """One row per recipe level: the best-paying recipe at it that a character of any race may
    learn. The profit is held to what the buying shop earns back in a day, shared by the group:
    inputs bought there refill its till, so the margin is all it pays out net."""
    till = economy.MARKET_CASH_REGEN / size
    best = {}
    for name, r in items.CRAFTING_RECIPES.items():
        parts = craft_level.breakdown(r)
        if parts["entry"] == "race":
            continue
        cost = sum(economy.sell_price(m) if m in parts["scarce"] else economy.buy_price(m)
                   for m in r.materials)
        per_hour = (r.yield_qty * economy.sell_price(r.target) - cost) / parts["hours"]
        if parts["level"] not in best or per_hour > best[parts["level"]][1]:
            best[parts["level"]] = (name, per_hour)
    return [Activity(f"Craft L{lvl}: {name}", act.WORK_DAY_HOURS,
                     income=min(till, per_hour * act.WORK_DAY_HOURS),
                     work_marks=act.work_marks(act.WORK_DAY_HOURS, lvl, level),
                     note=f"${per_hour * act.WORK_DAY_HOURS:.0f} a day before the till's ${till:.1f}")
            for lvl, (name, per_hour) in sorted(best.items())]


def study_row():
    """The Faith rite, then every Faith spell from the scroll, the study room rented for each day
    of study; XP and cost averaged over the whole program."""
    days = rite.POINTS[MAGIC_SCHOOL] / craft_level.AVG_ROLL
    cost = economy.buy_price(rite.HOLY_SYMBOL)
    xp = 0
    for spell in magic.SPELLS.values():
        if MAGIC_SCHOOL not in spell.sources:
            continue
        study = magic.points_to_learn(spell.level) / craft_level.AVG_ROLL
        days += study
        cost += economy.buy_price(f"Scroll of {spell.name}") + study * economy.TAVERN_STUDY_COST_PER_DAY
        xp += magic.study_xp(spell)
    return Activity(STUDY, 24, income=-cost / days, magic_xp=xp / days, magic_cap=xp,
                    note=f"{days:.0f} days, ${cost:.0f} and {xp} magic XP in all")


def group_size(level, cha):
    """How many a leader of racial `level` and Charisma mod `cha` holds in one group."""
    return group.BASE_CAPACITY + cha + level // 2


def measure(max_level, cha, trials, skill):
    """{level: {activity: Row}} at the player's `skill`, the one-offs and the tavern left out."""
    act.ROLES.update(EXTRA_ROLES)
    out = {}
    for level in range(max_level + 1):
        size = group_size(level, cha)
        print(f"  measuring level {level}, a group of {size}...", file=sys.stderr, flush=True)
        bouts = act.arena_rows(ARENA_SQUAD, level, trials, [skill], keys=ARENA_BOUTS)
        hunt = act.hunt_row(size, level, trials)
        rows = [act.lumber_row(act.make_squad(size, level)), *(b[skill] for b in bouts.values()),
                act.hunt_row(size, level, trials, skill=skill, samples=hunt.samples)]
        crafts = craft_rows(size, level)
        for r in crafts:
            act.ROLES[r.name] = ("income", 0, NO_TOP)
        rows += [supply_row(size, level, trials, skill), *crafts, study_row()]
        out[level] = {r.name: r for r in rows}
    return out


def _gap(curve, xp):
    """XP still missing to the next level of `curve` from `xp`."""
    level = curve.level(xp)
    return curve[level] - xp


class Career:
    def __init__(self, rows, start_coins, risk):
        self.rows = rows
        self.risk = risk
        self.top = max(rows)
        self.cxp = 0.0
        self.wxp = 0.0
        self.mxp = 0.0
        self.money = start_coins
        self.earned = 0.0
        self.alive = 1.0
        self.day = 0
        self.days_on = {}
        self.ledger = {}                      # activity -> [days, copper it paid before the meal]

    @property
    def combat(self):
        return progression.combat_level(self.cxp)

    @property
    def work(self):
        return progression.work_level(self.wxp)

    @property
    def magic(self):
        return progression.magic_level(self.mxp)

    @property
    def racial(self):
        return progression.racial_level(self.combat + self.work + self.magic)

    def _at(self, level):
        return self.rows[min(level, self.top)]

    def options(self, in_band):
        """[(name, combat XP/day, work marks/day, magic XP/day, net $/day, deaths/day)] the
        character may take."""
        here = self._at(self.racial)
        meal = act.cheapest_meal()
        out = []
        for name, r in here.items():
            if in_band and not r.in_band(self.racial):
                continue
            mxp = getattr(r, "magic_xp", 0.0) * r.runs_per_day
            if mxp and self.mxp >= r.magic_cap:
                continue
            c_row, w_row = self._at(self.combat)[name], self._at(self.work)[name]
            out.append((name, c_row.combat_xp * c_row.runs_per_day,
                        w_row.work_marks * r.runs_per_day, mxp,
                        r.per_day - meal, min(1.0, r.death_rate * r.runs_per_day)))
        return out

    def pick(self):
        return self._best(in_band=True) or self._best(in_band=False) or self._earn()

    def _earn(self):
        """A day of the safest pay when nothing that teaches is affordable: it refills the purse."""
        paid = [o for o in self.options(in_band=False) if o[4] > 0 and o[5] <= self.risk]
        return max(paid, key=lambda o: o[4]) if paid else None

    def _best(self, in_band):
        c_gap = _gap(progression.COMBAT_XP_THRESHOLDS, self.cxp)
        w_gap = _gap(progression.WORK_XP_THRESHOLDS, self.wxp)
        m_gap = _gap(progression.MAGIC_XP_THRESHOLDS, self.mxp)
        best = None
        for opt in self.options(in_band):
            _, cxp, wxp, mxp, net, deaths = opt
            if (net < 0 and self.money + net < 0) or deaths > self.risk:
                continue
            key = (cxp / c_gap + wxp / w_gap + mxp / m_gap, net)
            if key[0] > 0 and (best is None or key > best[0]):
                best = (key, opt)
        return best[1] if best else None

    def day_of(self, opt):
        name, cxp, wxp, mxp, net, deaths = opt
        self.cxp += cxp
        self.wxp += wxp
        self.mxp += mxp
        self.money += net
        self.earned += net
        self.alive *= 1 - deaths
        self.day += 1
        self.days_on[name] = self.days_on.get(name, 0) + 1
        line = self.ledger.setdefault(name, [0, 0.0])
        line[0] += 1
        line[1] += net + act.cheapest_meal()


def climb(rows, start_coins, max_level, risk):
    """-> ([(racial level, day, copper earned, survival, (combat, work, magic), {activity: days},
    {activity: copper paid} on the way to that level)], stalled at, the career)."""
    career = Career(rows, start_coins, risk)
    marks = [(0, 0, 0.0, 1.0, (0, 0, 0), {}, {})]
    stalled = None
    paid_before = {}
    while career.racial < max_level and career.day < DAY_LIMIT:
        opt = career.pick()
        if opt is None:
            stalled = career.racial
            break
        before = career.racial
        career.day_of(opt)
        if career.racial > before:
            paid = {n: g - paid_before.get(n, 0.0) for n, (_, g) in career.ledger.items()}
            paid_before = {n: g for n, (_, g) in career.ledger.items()}
            marks.append((career.racial, career.day, career.earned, career.alive,
                          (career.combat, career.work, career.magic), career.days_on, paid))
            career.days_on = {}
    if career.day >= DAY_LIMIT:
        stalled = career.racial
    return marks, stalled, career


def dearest(budget, kind):
    """The dearest market item of `kind` that `budget` buys, or '-'."""
    best = None
    for name in economy.MARKET_STOCK:
        it = items.get(name)
        if it is None or it.type != kind:
            continue
        price = economy.buy_price(name)
        if price <= budget and (best is None or price > best[1]):
            best = (name, price)
    return f"{best[0]} ({best[1]})" if best else "-"


def extras_report(rows):
    """What the model's own rows pay and teach at each level."""
    lines = [f"{'level':>5}  {'activity':<34}{'net/day':>8}{'cXP/d':>7}{'wXP/d':>7}{'mXP/d':>7}{'dead/d':>8}"]
    meal = act.cheapest_meal()
    for level, here in rows.items():
        for name, r in here.items():
            if not isinstance(r, Activity):
                continue
            lines.append(f"{level:>5}  {name:<34}{r.per_day - meal:>8.1f}{r.combat_xp * r.runs_per_day:>7.2f}"
                         f"{r.work_marks * r.runs_per_day:>7.2f}{r.magic_xp * r.runs_per_day:>7.2f}"
                         f"{r.death_rate * r.runs_per_day * 100:>7.1f}%")
    notes = {r.name: r.note for here in rows.values() for r in here.values()
             if isinstance(r, Activity) and r.note}
    lines += [f"  {name}: {note}" for name, note in notes.items()]
    return "\n".join(lines)


def report(marks, stalled, kit, coins, skill, cha):
    lines = [(f"== wealth by racial level, per character: a player who wins {skill * 100:.0f}% of "
              f"fights, a group of {group.BASE_CAPACITY} + racial level // 2 + CHA mod {cha:+d}"),
             (f"   level 0 = starting kit ${kit:.0f} + coins ${coins:.0f}; wealth = that + "
              "copper earned net of the meal"), ""]
    lines.append(f"{'racial':>6}{'group':>6}{'day':>6}{'C/W/M':>8}{'alive%':>8}{'earned':>8}{'wealth':>8}"
                 f"  {'weapon in half':<22}{'armour in half':<22}days by activity")
    for level, day, earned, alive, tracks, days_on, _ in marks:
        wealth = kit + coins + earned
        spent = ", ".join(f"{n.replace('Arena: ', '')} {d}" for n, d in
                          sorted(days_on.items(), key=lambda kv: -kv[1]))
        lines.append(f"{level:>6}{group_size(level, cha):>6}{day:>6}{'/'.join(map(str, tracks)):>8}"
                     f"{alive * 100:>8.0f}"
                     f"{earned:>8.0f}{wealth:>8.0f}  {dearest(wealth / 2, ItemType.WEAPON):<22}"
                     f"{dearest(wealth / 2, ItemType.ARMOR):<22}{spent}")
    if stalled is not None:
        lines.append(f"\n   the climb stalls at racial level {stalled}: no activity teaches anything "
                     "there (or none the purse can pay)")
    return "\n".join(lines)


def ledger_report(marks, career):
    """Where the copper came from and went on the way to each level, then over the whole career."""
    meal = act.cheapest_meal()
    lines = ["== the purse level by level: what each activity paid (+) or cost (-) before the meal",
             f"{'racial':>6}{'days':>6}{'paid in':>9}{'paid out':>9}{'meals':>8}{'net':>8}  by activity"]
    prev_day = 0
    for level, day, _, _, _, days_on, paid in marks[1:]:
        days = day - prev_day
        prev_day = day
        gains = sum(v for v in paid.values() if v > 0)
        costs = sum(v for v in paid.values() if v < 0)
        parts = ", ".join(f"{n.replace('Arena: ', '')} {v:+.0f} ({days_on.get(n, 0)} d)"
                          for n, v in sorted(paid.items(), key=lambda kv: -abs(kv[1])) if days_on.get(n))
        lines.append(f"{level:>6}{days:>6}{gains:>9.0f}{costs:>9.0f}{-days * meal:>8.0f}"
                     f"{gains + costs - days * meal:>8.0f}  {parts}")
    lines += ["", f"{'whole career':<36}{'days':>6}{'paid':>9}{'a day':>8}"]
    for name, (days, paid) in sorted(career.ledger.items(), key=lambda kv: -kv[1][1]):
        lines.append(f"  {name:<34}{days:>6}{paid:>9.0f}{paid / days:>8.1f}")
    lines.append(f"  {'meals':<34}{career.day:>6}{-career.day * meal:>9.0f}{-meal:>8.1f}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skill", type=float, default=0.8, help="the player's win chance in a fight")
    ap.add_argument("--max-level", type=int, default=8)
    ap.add_argument("--risk", type=float, default=0.05,
                    help="the most deaths a day the character accepts (1 takes anything)")
    ap.add_argument("--cha", type=int, default=0, help="the group leader's Charisma modifier")
    ap.add_argument("--trials", type=int, default=60)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--extras", action="store_true",
                    help="also print what the supply run, crafting and study pay and teach per level")
    args = ap.parse_args()
    random.seed(args.seed)
    kit, coins = starting_wealth()
    rows = measure(args.max_level, args.cha, args.trials, args.skill)
    marks, stalled, career = climb(rows, coins, args.max_level, args.risk)
    print(report(marks, stalled, kit, coins, args.skill, args.cha))
    print("\n" + ledger_report(marks, career))
    if args.extras:
        print("\n" + extras_report(rows))


if __name__ == "__main__":
    main()
