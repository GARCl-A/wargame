"""Combat log: one JSONL file per fight, enough to rebuild the fight from the file alone.

A `CombatLog` is attached to a `Battle` as `battle.sink`. Every action a unit performs
(`Action.execute`, ending a turn, planting a flag or a trap) goes through `CombatLog.record`,
whether a person clicked it or `ai.py` chose it, so both sides' decisions land in the same
rows. `scripts/combat_analysis.py` reads them back.

Rows (all carry `e`):
  start  the whole fight as it begins: `meta`, `controllers` ({team: "human" | "ai"}), the board,
         every unit (`units`: static data, with the character as `persist.unit_to_dict`), the
         first `state` and the turn order.
  act    one decision: `n`, `round`, `actor` (index into `units`), `team`, `by` (who decided),
         `action` (an Action id, "end_turn", "plant_flag", "plant_trap", "skip_traps"), `target`
         ({"unit": i} | {"cell": [x, y]}), `kw`, `ap`, `options` (what was legal), `ai`
         (what `ai.py` would have done in the same state, human rows only), `state` after it,
         the `log` lines it produced, and `winner` once the fight is decided. `new_units` adds
         the static data of anyone who joined mid-fight (reinforcements).
  end    the result: `winner`, `rounds`, `survivors`, `seconds`.

A `state` is {"units": [[x, y, z, hp, ap, status, [conditions], mounted_on, delayed, ammo], ...]
(one entry per unit, in `units` order; `UNIT_FIELDS`), "order": [unit index, ...],
"turn": position of the active unit in `order`, "round": n}, plus "world" (ground objects, flags,
creatures) whenever it changed since the last row. `load` and `frames` turn the file back into
a list of rows and a list of states with each unit as a dict.
"""

import copy
import json
import os
import random
import time

FORMAT = 1
UNIT_FIELDS = ("x", "y", "z", "hp", "ap", "status", "conditions", "mounted_on", "delayed", "ammo")


def _cell(c):
    return [int(c[0]), int(c[1])]


class CombatLog:
    def __init__(self, path, meta=None, controllers=None):
        self.path = path
        self.meta = dict(meta or {})
        self.controllers = dict(controllers or {"player": "ai", "enemy": "ai"})
        self.busy = False
        self.n = 0
        self._fh = None
        self._known = 0
        self._world = None
        self._log_seen = 0
        self._t0 = time.time()
        self.closed = False

    # -- file ------------------------------------------------------------- #
    def _write(self, row):
        if self._fh is None:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            self._fh = open(self.path, "w", encoding="utf-8")  # noqa: SIM115 -- stays open across the fight's rows
        self._fh.write(json.dumps(row, separators=(",", ":")) + "\n")
        self._fh.flush()

    def close(self):
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        self.closed = True

    # -- rows ------------------------------------------------------------- #
    def start(self, battle):
        board = battle.board
        self._known = len(battle.units)
        self._log_seen = battle.log_total
        self._write({
            "e": "start", "format": FORMAT, "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "meta": self.meta, "controllers": self.controllers,
            "scenario": type(battle.scenario).__name__,
            "lethal": battle.lethal, "arena": battle.arena, "daylight": battle.daylight,
            "ambient_light": battle.ambient_light,
            "board": {"cols": board.cols, "rows": board.rows,
                      "walls": sorted(_cell(c) for c in board.walls),
                      "elevation": sorted([*_cell(c), z] for c, z in board.elevation.items()),
                      "ropes": sorted(_cell(c) for c in board.ropes),
                      "water": sorted(_cell(c) for c in board.water)},
            "units": [unit_static(i, u) for i, u in enumerate(battle.units)],
            "state": self._state(battle, first=True),
        })

    def record(self, battle, name, actor, target, kw, run):
        """Run `run()` -- one decision -- and write the row for it."""
        self.busy = True
        try:
            idx = battle.units.index(actor)
            by = self.controllers.get(actor.team, "ai")
            before = {"round": battle.round_no, "ap": actor.ap, "options": legal_options(battle, actor)}
            guess = ai_choice(battle, actor) if by == "human" else None
            result = run()
            self.n += 1
            row = {"e": "act", "n": self.n, "round": before["round"], "actor": idx,
                   "team": actor.team, "by": by, "action": name, "target": _target(battle, target),
                   "kw": kw, "ap": before["ap"], "options": before["options"], "ai": guess}
            new = battle.units[self._known:]
            if new:
                row["new_units"] = [unit_static(self._known + i, u) for i, u in enumerate(new)]
                self._known = len(battle.units)
            row["state"] = self._state(battle)
            row["log"] = self._new_log(battle)
            if battle.winner:
                row["winner"] = battle.winner
            self._write(row)
            return result
        finally:
            self.busy = False

    def end(self, battle):
        if self.closed:
            return
        self._write({"e": "end", "winner": battle.winner, "rounds": battle.round_no,
                     "survivors": [i for i, u in enumerate(battle.units) if u.alive],
                     "seconds": round(time.time() - self._t0, 1)})
        self.close()

    # -- state ------------------------------------------------------------ #
    def _new_log(self, battle):
        fresh = battle.log_total - self._log_seen
        self._log_seen = battle.log_total
        return list(battle.log_lines[-fresh:]) if fresh > 0 else []

    def _state(self, battle, first=False):
        units = battle.units
        state = {
            "units": [[*_cell(u.pos), u.z or 0, u.hp, u.ap, u.status,
                       sorted(c.id for c in u.conditions),
                       units.index(u.mounted_on) if u.mounted_on in units else None,
                       bool(u.delayed), u.ammo] for u in units],
            "order": [units.index(u) for u in battle.order],
            "turn": battle.turn_idx, "round": battle.round_no,
        }
        world = self._world_state(battle)
        if first or world != self._world:
            state["world"] = self._world = world
        return state

    @staticmethod
    def _world_state(battle):
        units = battle.units
        flags = None
        if battle.is_ctf:
            flags = {team: ({"carrier": units.index(battle.flag_carrier[team])}
                            if battle.flag_carrier[team] is not None
                            else (_cell(battle.flags[team]) if battle.flags[team] else None))
                     for team in ("player", "enemy")}
        return {"ground": [[g.kind, *_cell(g.pos), g.weapon_name or g.trap_type or g.item_name]
                           for g in battle.ground],
                "creatures": [_cell(c.pos) for c in battle.creatures],
                "flags": flags}


# --------------------------------------------------------------------------- #
# what a row says                                                              #
# --------------------------------------------------------------------------- #
def _target(battle, target):
    if target is None:
        return None
    if isinstance(target, tuple):
        return {"cell": _cell(target)}
    if target in battle.units:
        return {"unit": battle.units.index(target)}
    return {"other": type(target).__name__}


def unit_static(idx, c):
    """What never changes about a unit in the fight, enough to rebuild its character."""
    from . import persist
    try:
        char = persist.unit_to_dict(c.char)
    except Exception:  # noqa: BLE001 -- a log must never stop the fight
        char = {"name": c.name, "race": c.race["name"]}
    return {"i": idx, "name": c.name, "team": c.team, "char": char, "hp_max": c.hp_max,
            "ac": c.ac, "speed": c.speed, "footprint": c.footprint,
            "weapon": c.weapon_name, "spells": list(c.spells_known)}


def legal_options(battle, actor):
    """What `actor` could do right now: the cells it can walk to, and for each other action the
    targets it could aim at (unit indices or cells), or True for one that needs none."""
    from . import actions
    units = battle.units
    out = {}
    try:
        reach = sorted(_cell(c) for c in battle.reachable(actor))
        if reach:
            out["move"] = reach
        panel = list(actions.PANEL_ACTIONS) + [actions.CastSpellAction(s) for s in actor.spells_known]
        for act in panel:
            if act is actions.END or not act.available(battle, actor):
                continue
            if act.target == "cell":
                cells_ = [_cell(c) for c in act.highlight_cells(battle, actor)]
                if cells_:
                    out[act.id] = cells_
            elif act.aimed:
                targets = [units.index(u) for u in act.highlight_targets(battle, actor)]
                if targets:
                    out[act.id] = targets
            else:
                out[act.id] = True
    except Exception as exc:  # noqa: BLE001 -- a log must never stop the fight
        out["error"] = type(exc).__name__
    return out


class _Probe:
    """Stands in for the sink on a copy of the battle: remembers the first thing the AI does."""
    busy = False

    def __init__(self):
        self.first = None

    def record(self, battle, name, actor, target, kw, run):
        if self.first is None:
            self.first = {"action": name, "target": _target(battle, target), "kw": kw}
        return run()


def ai_choice(battle, actor):
    """What `ai.py` would do first from this exact state, played out on a copy so nothing real
    changes and the dice the fight goes on to roll are the ones it would have rolled anyway."""
    from . import ai
    state = random.getstate()
    sink, battle.sink = battle.sink, None
    try:
        twin = copy.deepcopy(battle)
    except Exception:  # noqa: BLE001 -- a copy that cannot be made just means no guess
        return None
    finally:
        battle.sink = sink
    probe = twin.sink = _Probe()
    try:
        ai.take_turn(twin, twin.units[battle.units.index(actor)])
    except Exception:  # noqa: BLE001 -- the AI failing on a copy is no reason to lose the row
        return None
    finally:
        random.setstate(state)
    return probe.first


def recorded(name_of):
    """Decorator for `Action.execute`-shaped methods: `name_of(self)` is the action's name in
    the log. A battle with no sink (almost every one) pays one attribute read."""
    def wrap(fn):
        def run(self, battle, actor, target=None, **kw):
            sink = getattr(battle, "sink", None)
            if sink is None or sink.busy:
                return fn(self, battle, actor, target, **kw)
            return sink.record(battle, name_of(self), actor, target, kw,
                               lambda: fn(self, battle, actor, target, **kw))
        run.__name__, run.__doc__ = fn.__name__, fn.__doc__
        run.recorded = True
        return run
    return wrap


# --------------------------------------------------------------------------- #
# reading a log back                                                           #
# --------------------------------------------------------------------------- #
def load(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


REPLAYABLE = ("Scenario", "ArenaScenario", "ErmosScenario", "CustomScenario")


def rebuild(rows):
    """A `Battle` standing at the opening of the fight in `rows`: the same characters (rebuilt from
    their saved dicts), the same board and cells. The turn order and the dice are fresh, so
    each rebuild is one more way the same fight could have gone. Raises `ValueError` for a fight
    with an objective of its own (flags, the Ruins), which the rebuild does not carry."""
    from .battle import Battle
    from .scenario import ReplayScenario
    from .unit import Unit
    start = rows[0]
    if start["scenario"] not in REPLAYABLE:
        raise ValueError(f"cannot rebuild a {start['scenario']} fight")
    sides = {"player": [], "enemy": []}
    for static in start["units"]:
        unit = Unit.from_save(static["char"])
        unit.team = static["team"]
        sides[static["team"]].append(unit)
    return Battle(sides["player"], sides["enemy"], scenario=ReplayScenario(start),
                  daylight=start["daylight"], lethal=start["lethal"], arena=start["arena"])


def frames(rows):
    """The fight as a list of states, the opening one first: each is
    {"n", "round", "active": unit index, "units": [dict per unit], "world", "row"}.
    A unit dict has `UNIT_FIELDS` plus `name`, `team` and `hp_max` from the static data."""
    start = rows[0]
    statics = list(start["units"])
    out, world = [], None
    for row in [start] + [r for r in rows[1:] if r["e"] == "act"]:
        statics += row.get("new_units", [])
        state = row["state"]
        world = state.get("world", world)
        units = []
        for static, vals in zip(statics, state["units"]):
            u = dict(zip(UNIT_FIELDS, vals))
            u.update(name=static["name"], team=static["team"], hp_max=static["hp_max"])
            units.append(u)
        out.append({"n": row.get("n", 0), "round": state["round"],
                    "active": state["order"][state["turn"]] if state["order"] else None,
                    "units": units, "world": world, "row": row})
    return out
