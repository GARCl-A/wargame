"""Play recorder: an opt-in log of how a person plays, for the economy sim.

With the `record_play` setting on, the game appends one JSON object per line to
`play.jsonl` in the guild's world folder, beside the saves and never inside one.
`scripts/play_analysis.py` turns those logs into the sim's day-by-day table and
the decision thresholds the `human` policy plays by.

Every hook calls `emit` or one of the order/day helpers, which do nothing while
no recorder is attached, so the engine and the sims pay nothing for it. This
module imports nothing from the game: it reads the guild it is handed.

Events (all carry `t`, the clock in seconds):
  session  a world was entered (new or loaded); the clock may jump back on a load
  day      end-of-day state: every character's money, levels and HP, rations
  order    a group was given an order (kind, from, dest, hours)
  buy/sell a market transaction (node, item, qty, price per unit)
  fight    a battle ended (kind, won, squad, deaths, xp)
  death    a character was lost: who (race, occupation, levels), the cause (combat / starvation)
           and, for a fight, how: the last log lines before they fell, the foes, the round
  talent   a talent was picked
  asset    the bank chest, the house or an upgrade was bought
  animal   an animal was bought or sold at the stables
  recruit  a pitch (pitcher, candidate, bail, ok)
  mission  a mission accepted or turned in (id, reward)
  craft    a crafting shift (recipe, hours worked, units made)

Each fight also writes its own decision log next to this file, in `combat_logs/` (`combat_log.py`).
"""

import json
import os

FILE = "play.jsonl"

COMBAT_DIR = "combat_logs"

_guild = None
_path = None
_seen_orders = {}
_last_day = None
_before = None


def attached():
    return _guild is not None


def attach(world_dir, guild):
    """Start logging `guild` into `world_dir`. Returns False if the file cannot be opened."""
    global _guild, _path, _last_day, _before
    try:
        os.makedirs(world_dir, exist_ok=True)
    except OSError:
        return False
    _guild, _path = guild, os.path.join(world_dir, FILE)
    _seen_orders.clear()
    _last_day, _before = guild.clock.day, None
    emit("session", node=_node_of(guild), members=len(guild.roster))
    return True


def combat_log_path(label):
    """Where the combat log of a campaign fight goes (`<world>/combat_logs/<label>.jsonl`, `-2`,
    `-3` ... when taken), or None while the recorder is detached."""
    if _path is None:
        return None
    folder = os.path.join(os.path.dirname(_path), COMBAT_DIR)
    path, n = os.path.join(folder, f"{label}.jsonl"), 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(folder, f"{label}-{n}.jsonl")
    return path


def detach():
    global _guild, _path, _last_day, _before
    _guild = _path = _last_day = _before = None
    _seen_orders.clear()


def _pulse(guild):
    """Money in hand, days of food and head count, stamped on every row: the thresholds a person
    shops and fights by are read off these."""
    mouths = max(1, len(guild.roster))
    return {"members": len(guild.roster), "money": sum(u.money for u in guild.roster),
            "food_days": round(sum(g.rations for g in guild.groups) / mouths, 2)}


def death(unit, cause, **fields):
    """A character is lost. `cause` is "combat" or "starvation"; `fields` say how."""
    emit("death", name=unit.name, race=unit.race["name"], occupation=unit.occupation["name"],
         combat=unit.combat_level, work=unit.work_level, hp_max=unit.hp_max, cause=cause, **fields)


def before_fight(squad):
    """The squad as it walks in, kept for the `fight` row that closes the battle."""
    global _before
    if _guild is None or not squad:
        return
    _before = {"hp_frac": round(sum(max(0, u.hp) / u.hp_max for u in squad) / len(squad), 2),
               "level_before": round(sum(u.combat_level for u in squad) / len(squad), 2),
               **{k + "_before": v for k, v in _pulse(_guild).items()}}


def emit(event, /, **fields):
    global _before
    if _guild is None:
        return
    if event == "fight" and _before is not None:
        fields = {**_before, **fields}
        _before = None
    row = {"e": event, "t": _guild.clock.seconds, **_pulse(_guild), **fields}
    try:
        with open(_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
    except OSError:
        pass


def _node_of(guild):
    return guild.groups[0].node if guild.groups else None


def _state(guild):
    return {
        "roster": [{"name": u.name, "money": u.money, "hp": u.hp, "hp_max": u.hp_max,
                     "combat": u.combat_level, "work": u.work_level}
                    for u in guild.roster],
        "rations": sum(g.rations for g in guild.groups),
        "groups": [{"gid": g.gid, "node": g.node, "size": len(g.members)} for g in guild.groups],
    }


def day_tick(guild):
    """Called after the clock moved: one `day` row for the last day boundary crossed."""
    global _last_day
    if guild is not _guild or guild.clock.day == _last_day:
        return
    _last_day = guild.clock.day
    emit("day", day=guild.clock.day, **_state(guild))


def orders_issued(guild):
    """Log the orders a person gave since the last tick. Orders the engine makes itself
    (the next leg of a route, a pause's follow-up) are marked by `orders_settled`."""
    if guild is not _guild:
        return
    for g in guild.groups:
        order = g.order
        if order is None or order.kind == "idle" or _seen_orders.get(g.gid) is order:
            continue
        _seen_orders[g.gid] = order
        emit("order", gid=g.gid, kind=order.kind, node=g.node, dest=order.final_dest,
             hours=round(order.eta, 2), size=len(g.members))


def orders_settled(guild):
    if guild is not _guild:
        return
    _seen_orders.clear()
    _seen_orders.update({g.gid: g.order for g in guild.groups if g.order is not None})
