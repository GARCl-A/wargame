"""One fight driven from the web client: the turn flow `BattleScreen` runs, and the board as one
side knows it, as plain data.

Everything that leaves here is what the side may know: foes out of sight are left out, their
health is in `intel` steps, cells never seen carry no terrain, and the light is the per-cell level
`lighting.cell_levels` gives. The client is never trusted with the rest.
"""

import os

from .. import actions, aftermath, ai, artwork, data, intel, lighting, vision
from ..battle_screen import BattleScreen
from ..board import cells
from ..combatant import AP_PER_TURN
from ..foe_card import foe_card
from ..fog import FogMemory
from ..scenario import own_half
from ..ui import floors

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
LOG_LINES = 60


def asset_url(path):
    return "/assets/" + os.path.relpath(path, ASSETS).replace(os.sep, "/") if path else None


def _cell(c):
    return [c[0], c[1]]


class _StepTap:
    """Sits in front of the battle's sink (the combat log, when one is attached) and cuts what
    happens into steps: one per decision, so the client can play an AI turn move by move."""

    def __init__(self, session, inner):
        self.session = session
        self.inner = inner
        self.busy = False

    def __getattr__(self, name):
        inner = self.__dict__.get("inner")
        if inner is None or name.startswith("__"):
            raise AttributeError(name)
        return getattr(inner, name)

    def record(self, battle, name, actor, target, kw, run):
        def decide():
            return self.inner.record(battle, name, actor, target, kw, run) if self.inner else run()
        if self.session.steps is None:
            return decide()
        self.busy = True
        try:
            before = {id(u): (u.pos, len(u.path)) for u in battle.units}
            result = decide()
            self.session.cut_step(before)
            return result
        finally:
            self.busy = False


class BattleSession:
    def __init__(self, battle, meta=None, team="player"):
        self.battle = battle
        self.meta = meta or {}
        self.team = team
        self.fog = FogMemory()
        self._log_seen = battle.log_total
        self.steps = None
        self._inspect_id = None
        self._shown = set()
        self._last_visible = set()
        self._sight_key = self._sight_val = None
        battle.sink = _StepTap(self, battle.sink)

    def plays(self, unit):
        return unit.team == self.team and not unit.ai_ally

    def my_turn(self):
        b = self.battle
        return b.winner is None and not b.awaiting_flag and not b.awaiting_trap and self.plays(b.active)

    def uid(self, unit):
        return f"u{self.battle.units.index(unit)}"

    def unit(self, uid):
        try:
            return self.battle.units[int(str(uid).lstrip("u"))]
        except (ValueError, IndexError):
            return None

    def advance(self, inspect=None):
        """What the client does not decide: a placement, or one AI unit's whole turn. Returns its
        steps (see `cut_step`); does nothing on the player's turn or once the fight is over."""
        return self._stepped(self._advance, inspect)

    def act(self, action_id, target=None, cell=None, inspect=None):
        """The player's `action_id` ("move" walks to `cell`) on `target` (a unit id) or `cell`,
        as steps. Raises ValueError when it cannot be done now."""
        return self._stepped(lambda: self._act(action_id, target, cell), inspect)

    def snapshot(self, inspect=None):
        """The board as it stands, as the one step of a fight just opened."""
        return self._stepped(lambda: None, inspect)

    def _stepped(self, run, inspect):
        self._inspect_id = inspect
        self.steps = []
        try:
            run()
        finally:
            steps, self.steps = self.steps, None
        if not steps or self._events_pending():
            steps.append({"moves": [], **self._events(), "state": self.state(inspect)})
        return steps

    def _events_pending(self):
        b = self.battle
        return b.log_total != self._log_seen or b.fx_events or b.acts or b.cues

    def cut_step(self, before):
        """Close one step: the units that moved (each with the cells it went through, cut to
        what the side can see), what the step showed, and the board after it."""
        b = self.battle
        seen_before, shown_before = self._last_visible, self._shown
        state = self.state(self._inspect_id)
        visible = self._last_visible
        moves = []
        for u in b.units:
            pos, n = before.get(id(u), (None, 0))
            if pos is None or u.pos == pos:
                continue
            walked = u.path[n - 1:] if n and len(u.path) > n and u.path[n - 1] == pos else [pos, u.pos]
            if u.team != self.team:
                walked = [c for c in walked if any(cc in visible or cc in seen_before
                                                   for cc in cells(c, u.footprint))]
            if len(walked) >= 2 and (u.team == self.team or self.uid(u) in self._shown | shown_before):
                moves.append({"id": self.uid(u), "path": [_cell(c) for c in walked]})
        self.steps.append({"moves": moves, **self._events(visible), "state": state})

    def _advance(self):
        b = self.battle
        if b.winner is not None or self.my_turn():
            return
        if b.awaiting_flag:
            team = b.active.team
            tiles = [(x, y) for x in own_half(team, b.board.cols) for y in range(b.board.rows)
                     if b.can_plant_flag((x, y))]
            b.plant_flag(tiles[0] if tiles else (0, b.board.rows // 2))
        elif b.awaiting_trap:
            cell = ai.trap_cell(b, b.awaiting_trap)
            b.skip_traps() if cell is None else b.plant_trap(b.awaiting_trap, cell)
        else:
            ai.take_turn(b, b.active)

    def _act(self, action_id, target, cell):
        b = self.battle
        if not self.my_turn():
            raise ValueError("not your turn")
        actor = b.active
        cell = tuple(cell) if cell is not None else None
        if action_id == "move":
            dest = self._anchor(actor, cell)
            if dest is None:
                raise ValueError("out of reach")
            actions.MOVE.execute(b, actor, dest)
        elif action_id == "defend_end":
            if actions.DEFEND.can(b, actor):
                actions.DEFEND.execute(b, actor)
            b.end_turn()
        else:
            action = self._action(action_id)
            if action is None:
                raise ValueError(f"no action {action_id}")
            if action is actions.END:
                b.end_turn()
            elif action.target == "cell":
                if cell is None or not action.can(b, actor, cell):
                    raise ValueError(f"{action.name} cannot reach that cell")
                action.execute(b, actor, cell)
            elif action.aimed:
                unit = self.unit(target) if target is not None else None
                if unit is None or not action.can(b, actor, unit):
                    raise ValueError(f"{action.name} cannot take that target")
                action.execute(b, actor, unit)
            else:
                if not action.can(b, actor):
                    raise ValueError(f"{action.name} cannot be done now")
                action.execute(b, actor)
        self._after_action()

    def _after_action(self):
        b = self.battle
        if b.is_ctf:
            b.check_objective()
        if b.winner is None and self.plays(b.active):
            act = b.active
            if act.ap < 1 and not b.reachable(act):
                b.end_turn()

    def _anchor(self, unit, cell):
        if cell is None:
            return None
        reach = self.battle.reachable(unit)
        if cell in reach:
            return cell
        cand = [a for a in reach if cell in cells(a, unit.footprint)]
        return min(cand, key=lambda a: reach[a]) if cand else None

    def _action(self, action_id):
        b = self.battle
        if action_id.startswith("spell:"):
            spell = action_id.split(":", 1)[1]
            return actions.CastSpellAction(spell) if spell in b.active.char.spells_known else None
        return next((a for a in actions.PANEL_ACTIONS if a.id == action_id), None)

    def route(self, cell):
        """The path the active unit would walk to `cell`, and its cost."""
        b = self.battle
        if not self.my_turn():
            return {"path": [], "cost": None}
        actor = b.active
        dest = self._anchor(actor, tuple(cell))
        if dest is None or dest == actor.pos:
            return {"path": [], "cost": None}
        return {"path": [_cell(c) for c in b.path_to(actor, dest)], "cost": b.reachable(actor).get(dest)}

    def aim(self, action_id):
        """The cells and targets `action_id` offers the active unit now."""
        b = self.battle
        action = self._action(action_id)
        if action is None or not self.my_turn():
            return {"cells": [], "targets": []}
        actor, obs = b.active, self._observers()
        shown = [c for c in action.highlight_cells(b, actor)
                 if 0 <= c[0] < b.board.cols and 0 <= c[1] < b.board.rows]
        targets = [self.uid(u) for u in action.highlight_targets(b, actor)
                   if u.team == actor.team or vision.enemy_visible(b, obs, u)]
        return {"cells": [_cell(c) for c in shown], "targets": targets,
                "kind": BattleScreen._aim_kind(action)}

    def _observers(self):
        return vision.observers(self.battle, False, self.team)

    def _visible(self):
        return self._sight(self._observers())[0]

    def _sight(self, obs):
        """`(visible cells, light levels)` for `obs`, worked out again only when what they hang
        on has changed: the observers, the lights, the walls. A foe's step mostly changes none."""
        b = self.battle
        key = (tuple((id(o), o.pos, o.footprint, o.alive) for o in obs), tuple(vision.light_sources(b)),
               frozenset(b.board.walls), b.winner is None)
        if key != self._sight_key:
            visible = vision.visible_cells(b, obs)
            self._sight_key, self._sight_val = key, (visible, lighting.cell_levels(b, visible, obs))
        return self._sight_val

    def state(self, inspect=None):
        """The board as the side knows it, `inspect` (a unit id) opened in the side panel."""
        b = self.battle
        obs = self._observers()
        visible, levels = self._sight(obs)
        self.fog.remember(self.team, visible, self._props())
        seen = self.fog.seen(self.team)
        known = visible | seen
        my_turn = self.my_turn()
        board = b.board
        units = [self._token(u, obs, my_turn) for u in b.units if self._shows(u, obs, my_turn)]
        self._last_visible, self._shown = visible, {t["id"] for t in units}
        return {
            "meta": self.meta,
            "round": b.round_no,
            "my_turn": my_turn,
            "winner": b.winner,
            "result": aftermath.result_word(b, self.team) if b.winner is not None else None,
            "board": {
                "cols": board.cols, "rows": board.rows,
                "floor": b.scenario.floor,
                "wall_kind": floors.style(b.scenario.floor)["wall"],
                "walls": [_cell(c) for c in sorted(board.walls & known)],
                "water": [_cell(c) for c in sorted(set(getattr(board, "water", ())) & known)],
                "elevation": [[x, y, z] for (x, y), z in sorted(board.elevation.items()) if (x, y) in known],
                "fire": [_cell(c) for c in sorted(set(b.fire) & visible)],
            },
            "visible": [_cell(c) for c in sorted(visible)],
            "seen": [_cell(c) for c in sorted(seen - visible)],
            "light": [[x, y, round(v, 3)] for (x, y), v in sorted(levels.items())],
            "props": ([p | {"pos": _cell(p["pos"])} for p in self._props() if p["pos"] in visible]
                      + [p | {"pos": _cell(p["pos"]), "remembered": True}
                         for p in self.fog.remembered_props(self.team, visible)]),
            "units": units,
            "initiative": self._initiative(obs),
            "active": self._sheet(b.active) if b.active and (self.plays(b.active) or
                                                             self._shows(b.active, obs, my_turn)) else None,
            "actions": self._actions(my_turn),
            "reach": ([[x, y, c] for (x, y), c in sorted(b.reachable(b.active).items())] if my_turn else []),
            "trail": [_cell(c) for c in b.active.path] if my_turn and len(b.active.path) >= 2 else [],
            "inspect": self._inspect(inspect, obs, my_turn),
            "log": list(b.log_lines[-LOG_LINES:]),
            "flags": {"mopping_up": b.mopping_up, "binding": b.binding_captives, "ctf": b.is_ctf,
                      "can_withdraw": b.can_withdraw, "can_flee": my_turn and actions.FLEE.available(b, b.active)},
        }

    def _props(self):
        b = self.battle
        props = []
        for o in b.ground:
            kind = ("torch" if o.is_torch else
                    "chest" if getattr(o, "is_chest", False) else
                    "relic" if getattr(o, "is_relic", False) else
                    "trap" if getattr(o, "is_trap", False) else
                    "disk" if getattr(o, "is_disk", False) else "item")
            props.append({"kind": kind, "pos": o.pos})
        props += [{"kind": "corpse", "pos": u.pos, "size": u.footprint} for u in b.units if u.dead]
        return props

    def _shows(self, u, obs, my_turn):
        b = self.battle
        if u.dead or u.fled:
            return False
        if u.team == self.team:
            return True
        return vision.enemy_visible(b, obs, u) or (my_turn and u.alive and actions.ATTACK.can(b, b.active, u))

    def _side(self, u):
        return "ally" if u.team == self.team else "foe"

    def _health(self, u):
        if u.team != self.team:
            return {"hp_frac": intel.health_steps(u) / intel.STEPS, "steps": intel.STEPS}
        return {"hp_frac": max(0, u.hp) / u.hp_max, "hp": u.hp, "hp_max": u.hp_max}

    def _token(self, u, obs, my_turn):
        b = self.battle
        return {
            "id": self.uid(u), "name": u.name, "side": self._side(u), "team": u.team,
            "race": u.race["name"],
            "portrait": asset_url(artwork.portrait_path(u.race["name"], getattr(u, "portrait_id", None))),
            "pos": _cell(u.pos), "fp": u.footprint,
            **self._health(u),
            "active": u is b.active and b.winner is None,
            "torch": u.has_torch, "defending": u.defending, "demoralized": u.demoralized,
            "downed": u.downed, "dying": f"{u.death_clock}/{data.DYING_TURNS}" if u.dying else None,
            "ai_ally": u.ai_ally,
            "attackable": bool(my_turn and u.team != self.team and u.alive
                               and (actions.ATTACK.can(b, b.active, u) or actions.ATTACK_TONGUE.can(b, b.active, u))),
        }

    def _initiative(self, obs):
        b = self.battle
        out = []
        for u in b.order:
            if u.dead or u.fled:
                continue
            known = u.team == self.team or vision.enemy_visible(b, obs, u)
            out.append({"id": self.uid(u) if known else None, "side": self._side(u),
                        "portrait": asset_url(artwork.portrait_path(u.race["name"], getattr(u, "portrait_id", None)))
                        if known else None,
                        "name": u.name if known else None,
                        "hp_frac": self._health(u)["hp_frac"] if known else None,
                        "active": u is b.active})
        return out

    def _sheet(self, u):
        w = u.weapon if u.weapon_hand else None
        occupation = u.char.occupation
        return {
            "id": self.uid(u), "name": u.name, "side": self._side(u),
            "portrait": asset_url(artwork.portrait_path(u.race["name"], getattr(u, "portrait_id", None))),
            "race": u.race["name"], "occupation": occupation["name"] if isinstance(occupation, dict) else occupation,
            "alignment": u.char.alignment,
            **self._health(u),
            "ac": u.ac if u.team == self.team else None,
            "md": u.mental_defense if u.team == self.team else None,
            "speed": u.speed, "ap": u.ap, "ap_max": AP_PER_TURN,
            "weapon": None if w is None else {
                "name": w.name, "damage": f"{w.damage[0]}d{w.damage[1]}" if w.damage else None,
                "thrown": w.thrown or None, "range": w.range or None,
                "action": next((a.name for a in actions.WEAPON_ACTIONS if w.has_trait(a.id)), None),
            },
            "conditions": [c.id for c in u.conditions],
        }

    def _actions(self, my_turn):
        b = self.battle
        if not my_turn:
            return {"combat": [], "utility": []}
        actor = b.active
        out = {}
        for tab in ("combat", "utility"):
            out[tab] = [{"id": e["action"].id, "name": e["action"].name,
                         "label": e["action"].label(b, actor), "cost": e["action"].cost,
                         "enabled": e["enabled"], "aimed": e["action"].aimed, "target": e["action"].target,
                         "hotkey": e["hotkey"], "toggle": bool(getattr(e["action"], "toggle", False))}
                        for e in actions.panel(b, actor, tab, my_turn)]
        spells = [actions.CastSpellAction(sp) for sp in actor.char.spells_known]
        out["combat"] = [{"id": f"spell:{a.spell_id}", "name": a.name, "label": a.name, "cost": a.cost,
                          "enabled": a.available(b, actor), "aimed": True, "target": a.target,
                          "hotkey": None, "toggle": False} for a in spells] + out["combat"]
        return out

    def _inspect(self, uid, obs, my_turn):
        u = self.unit(uid) if uid else None
        if u is None or not self._shows(u, obs, my_turn):
            return None
        if u.team == self.team:
            return {"kind": "ally", **self._sheet(u)}
        card = foe_card(intel.known_fields(self.battle, self.team, u))
        return {"kind": "foe", "id": uid,
                "portrait": asset_url(artwork.portrait_path(u.race["name"], getattr(u, "portrait_id", None))),
                **card}

    def _events(self, visible=None):
        """What the last step did that the side could see, drained off the battle: the
        floating numbers, the named actions and their missiles, crits and misses, new log lines."""
        b = self.battle
        if visible is None:
            visible = self._visible()
        fresh = b.log_total - self._log_seen
        self._log_seen = b.log_total
        events = {
            "log": list(b.log_lines[-fresh:]) if fresh > 0 else [],
            "fx": [{"pos": _cell(pos), "text": text, "kind": kind}
                   for pos, text, kind in b.fx_events if tuple(pos) in visible],
            "acts": [{"actor": self.uid(actor), "name": name, "aim": _cell(getattr(aim, "pos", aim)) if aim else None}
                     for actor, name, aim in b.acts if actor.pos in visible or actor.team == self.team],
            "cues": [{"kind": kind, "pos": _cell(pos)} for kind, pos in b.cues if tuple(pos) in visible],
        }
        b.fx_events.clear()
        b.acts.clear()
        b.cues.clear()
        return events
