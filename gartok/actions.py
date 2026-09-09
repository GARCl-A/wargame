"""Combat actions.

Model: 2 action points per turn. Each action is a class that knows its cost, what
kind of target it needs, whether it can be done now and how it resolves. The UI
builds the buttons from `PANEL_ACTIONS`; the AI scores from the same objects.

Adding an action (a new world thing that becomes a mechanic) = one class here and
one entry in the lists at the end of the file. Nothing else needs to know it exists.
"""

import random

from . import data
from .board import COLS, ROWS, cells, chebyshev, grid_distance, neighbors
from .conditions import Defending, Demoralized
from .data import DEMORALIZE_RANGE, d20, resolve_bonus
from .ground import GroundObject


def _sign(v):
    return (v > 0) - (v < 0)


# --------------------------------------------------------------------------- #
# Base                                                                         #
# --------------------------------------------------------------------------- #

class Action:
    id = ""
    name = ""
    cost = 1
    target = "none"        # "none" | "enemy" | "cell"
    aimed = False          # True: needs the target picked by clicking the screen

    def available(self, battle, actor):
        """Does the action show enabled for this unit now (no target chosen yet)?"""
        return actor.ap >= self.cost

    def can(self, battle, actor, target=None):
        """Can it be executed against this specific target?"""
        return self.available(battle, actor)

    def execute(self, battle, actor, target=None):
        raise NotImplementedError

    def label(self, battle, actor):
        return self.name

    # highlights for the UI while the action is being aimed
    def highlight_cells(self, battle, actor):
        return []

    def highlight_targets(self, battle, actor):
        return [u for u in battle.units
                if u.alive and u.team != actor.team and self.can(battle, actor, u)]


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _pack_flank(battle, attacker, target):
    """Loose flank (Pack Tactics): any ally, other than the attacker, adjacent to
    the target. Feeds the racial 'Pack Tactics' bonus."""
    return any(u.alive and u.team == attacker.team and u is not attacker
               and battle.units_distance(u, target) == 1
               for u in battle.units)


def _facing(battle, unit, target_cells):
    """Rough unit-direction (sx, sy) from `unit`'s nearest cell to the target's centre."""
    cx = sum(x for x, _ in target_cells) / len(target_cells)
    cy = sum(y for _, y in target_cells) / len(target_cells)
    ux, uy = min(battle.cells_of(unit), key=lambda c: (c[0] - cx) ** 2 + (c[1] - cy) ** 2)
    return (_sign(ux - cx), _sign(uy - cy))


def _flanked(battle, attacker, target):
    """Strict flank: the attacker and an ally are both adjacent to the target and
    on opposite sides (a line between them crosses the target). +2 [circumstance]."""
    if battle.units_distance(attacker, target) > 1:
        return False
    tcells = battle.cells_of(target)
    da = _facing(battle, attacker, tcells)
    if da == (0, 0):
        return False
    for u in battle.units:
        if (u.alive and u.team == attacker.team and u is not attacker
                and battle.units_distance(u, target) <= 1
                and _facing(battle, u, tcells) == (-da[0], -da[1])):
            return True
    return False


def _hostile_target(actor, target):
    return target is not None and target.alive and target.team != actor.team


def _attackable_target(actor, target):
    """Attack and Throw may also target a downed enemy body, to finish it off."""
    return target is not None and not target.dead and target.team != actor.team


def _shared_language(a, b):
    return bool(set(a.languages) & set(b.languages))


def _drop_cell(battle, target):
    """A free cell adjacent to the target where the thrown weapon lands."""
    tcells = set(cells(target.pos, target.footprint))
    around = {v for c in tcells for v in neighbors(c)} - tcells
    free = [p for p in around
            if battle.unit_at(p) is None and battle.ground_at(p) is None
            and p not in battle.board.walls]
    return random.choice(free) if free else target.pos


def _pickable(unit, obj):
    """Anyone can pick up / swap a torch; a weapon only if the unit is unarmed."""
    if obj.is_torch:
        return not unit.has_torch
    return unit.unarmed


def _cells_in_radius(origin, radius):
    """Cells within `radius` of `origin` by the diagonal-aware metric (an octagon,
    not a square -- matches how the range checks actually measure)."""
    ox, oy = origin
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            if (dx or dy) and grid_distance((0, 0), (dx, dy)) <= radius:
                yield (ox + dx, oy + dy)


def _resolve_hit(battle, attacker, target, nat, bonus, detail, prefix, thrown=False):
    """Resolve a d20 roll already made: log and apply damage. Returns 'hit'|'miss'|'crit'."""
    total = nat + bonus
    ac = target.ac
    crit = nat == 20
    desc = f"{prefix}: d20({nat}) {detail} = {total} vs AC {ac}"
    if nat == 1:
        battle.log(desc + "  -> critical miss.")
        return "miss"
    if crit or total >= ac:
        if target.dying:                     # a hit on a dying body finishes it
            battle.log(desc + "  -> coup de grace: DEAD.")
            target.status = "dead"
            return "crit" if crit else "hit"
        battle.log(desc + ("  -> CRITICAL HIT!" if crit else "  -> hit."))
        was_up = target.alive
        target.take_damage(attacker.damage_roll(crit=crit, thrown=thrown), battle.log)
        if was_up and target.team != attacker.team:
            if not target.alive:
                attacker.credit_kill(target)  # downed a standing enemy -> combat XP later
            elif target.hp <= 0 and target.ferocity_downer is None:
                target.ferocity_downer = attacker   # Ferocity: still up at 0 HP, credit the fall
        return "crit" if crit else "hit"
    battle.log(desc + "  -> misses.")
    return "miss"


# --------------------------------------------------------------------------- #
# Move                                                                         #
# --------------------------------------------------------------------------- #

class Move(Action):
    id, name, target = "move", "Move", "cell"

    def available(self, battle, actor):
        return bool(battle.reachable(actor))

    def can(self, battle, actor, target=None):
        return target in battle.reachable(actor)

    def execute(self, battle, actor, target=None):
        battle.move_unit(actor, target)

    def highlight_cells(self, battle, actor):
        return list(battle.reachable(actor))

    def highlight_targets(self, battle, actor):
        return []


# --------------------------------------------------------------------------- #
# Attack                                                                       #
# --------------------------------------------------------------------------- #

class Attack(Action):
    id, name, target = "attack", "Attack", "enemy"

    def can(self, battle, actor, target=None):
        if actor.ap < self.cost or not _attackable_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.attack_range:
            return False
        if not battle.los_between(actor, target):
            return False
        # a ranged attack needs to see the target; melee does not
        if actor.attack_range > 1 and not battle.can_see_unit(actor, target):
            return False
        return True

    def highlight_targets(self, battle, actor):
        return [u for u in battle.units
                if not u.dead and u.team != actor.team and self.can(battle, actor, u)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        if actor.ranged:
            actor.ammo -= 1
            battle.log(f"{actor.name} shoots ({actor.ammo} arrow(s) left).")
        mods = actor.attack_mods(target, _pack_flank(battle, actor, target))
        if _flanked(battle, actor, target):
            mods.append((2, "circumstance", "Flank"))

        ab = actor.ability
        if ab.feint and actor.spend_once("feint"):
            mods += ab.feint(actor, target)
            battle.log(f"{actor.name} uses {ab.name} to distract.")

        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} -> {target.name}"
        result = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix)

        if result == "miss" and nat != 1 and ab.on_attack_miss \
                and actor.spend_once("on_attack_miss"):
            ab.on_attack_miss(battle, actor, target, bonus, target.ac, battle.log)


# --------------------------------------------------------------------------- #
# Defend                                                                       #
# --------------------------------------------------------------------------- #

class Defend(Action):
    id, name = "defend", "Defend"

    def available(self, battle, actor):
        return actor.ap >= self.cost and not actor.defending

    def label(self, battle, actor):
        return "Defend (1 pt, +1 AC)"

    def execute(self, battle, actor, target=None):
        if actor.ap < self.cost:
            return
        actor.ap -= 1
        actor.walking = False
        if actor.defending:
            battle.log(f"{actor.name} is already defending (circumstance bonus doesn't stack).")
        else:
            actor.add_condition(Defending())
            battle.log(f"{actor.name} defends: +1 AC [circumstance] until next turn.")


# --------------------------------------------------------------------------- #
# Throw                                                                        #
# --------------------------------------------------------------------------- #

class Throw(Action):
    id, name, target, aimed = "throw", "Throw", "enemy", True

    def available(self, battle, actor):
        return actor.ap >= self.cost and actor.can_throw

    def can(self, battle, actor, target=None):
        if not actor.can_throw or actor.ap < self.cost:
            return False
        if not _attackable_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.throw_range:
            return False
        return battle.los_between(actor, target) and battle.can_see_unit(actor, target)

    def label(self, battle, actor):
        if not self.available(battle, actor):
            return "Throw weapon (1 pt)"
        return f"Throw {actor.weapon_name} (1 pt)"

    def highlight_cells(self, battle, actor):
        return [p for c in cells(actor.pos, actor.footprint)
                for p in _cells_in_radius(c, actor.throw_range)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        weapon_name = actor.weapon_name

        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), thrown=True)
        if _flanked(battle, actor, target):
            mods.append((2, "circumstance", "Flank"))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} throws {weapon_name} at {target.name}"
        _resolve_hit(battle, actor, target, nat, bonus, detail, prefix, thrown=True)

        actor.disarm()
        landing = _drop_cell(battle, target)
        battle.ground.append(GroundObject.weapon(landing, weapon_name))
        battle.log(f"  {weapon_name} lands at {landing}; {actor.name} is disarmed.")


# --------------------------------------------------------------------------- #
# Pick up object                                                               #
# --------------------------------------------------------------------------- #

class PickUp(Action):
    id, name = "pickup", "Pick up"

    def available(self, battle, actor):
        return (actor.ap >= self.cost
                and any(_pickable(actor, o) for o in battle.ground_in_reach(actor)))

    def label(self, battle, actor):
        return "Pick up / swap object (1 pt)"

    def _queue(self, battle, actor):
        # unarmed prioritizes a weapon; otherwise the nearest
        prefer = GroundObject.WEAPON if actor.unarmed else GroundObject.TORCH
        return sorted(
            (o for o in battle.ground_in_reach(actor) if _pickable(actor, o)),
            key=lambda o: (o.kind != prefer, chebyshev(o.pos, actor.pos)))

    def _drop_on_ground(self, battle, actor, kind, weapon_name=None):
        dest = actor.pos
        if battle.ground_at(dest) is not None:
            for p in neighbors(actor.pos):
                if (p not in battle.board.walls and battle.unit_at(p) is None
                        and battle.ground_at(p) is None):
                    dest = p
                    break
        battle.ground.append(GroundObject(kind, dest, weapon_name))
        battle.log(f"  {actor.name} drops {'the torch' if kind == GroundObject.TORCH else weapon_name} at {dest}.")

    def execute(self, battle, actor, target=None):
        if actor.ap < self.cost:
            return
        queue = self._queue(battle, actor)
        if not queue:
            return
        obj = queue[0]
        battle.ground.remove(obj)
        actor.ap -= 1
        actor.walking = False

        # equip; whatever does not fit in two hands falls to the ground
        if obj.is_torch:
            dropped = actor.equip_torch()
            battle.log(f"{actor.name} picks up a torch (lights {data.TORCH_RADIUS} squares).")
        else:
            dropped = actor.equip_weapon(obj.weapon_name)
            battle.log(f"{actor.name} picks up {obj.weapon_name} from the ground.")

        for kind, weapon_name in dropped:
            self._drop_on_ground(battle, actor, kind, weapon_name)


# --------------------------------------------------------------------------- #
# Demoralize                                                                   #
# --------------------------------------------------------------------------- #

class Demoralize(Action):
    id, name, target, aimed = "demoralize", "Demoralize", "enemy", True

    def _can_provoke(self, actor, target):
        return actor.ability.demoralize_ignores_language or _shared_language(actor, target)

    def can(self, battle, actor, target=None):
        if actor.ap < self.cost or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > DEMORALIZE_RANGE:
            return False
        if not (battle.can_see_unit(actor, target) and battle.can_see_unit(target, actor)):
            return False
        return self._can_provoke(actor, target)

    def label(self, battle, actor):
        return "Demoralize (1 pt, CHA vs Mental Defense)"

    def highlight_cells(self, battle, actor):
        return [p for c in cells(actor.pos, actor.footprint)
                for p in _cells_in_radius(c, DEMORALIZE_RANGE)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False

        bonus, applied = resolve_bonus([(actor.mod_charisma, None, "CHA")])
        detail = " ".join(f"{v:+}({r})" for v, r in applied)

        if actor.ability.demoralize_ignores_language and not _shared_language(actor, target):
            battle.log(f"{actor.name} mimics {target.name}'s voice to provoke them.")

        nat = d20()
        total = nat + bonus
        md = target.mental_defense
        crit = nat == 20
        desc = (f"{actor.name} tries to demoralize {target.name}: "
                f"d20({nat}) {detail} = {total} vs MD {md}")
        if nat == 1:
            battle.log(desc + "  -> critical miss.")
        elif crit or total >= md:
            target.add_condition(Demoralized())
            battle.log(desc + ("  -> CRITICAL HIT!" if crit else "  -> lands.")
                       + f" {target.name} is demoralized (-1 status until the end of their turn).")
        else:
            battle.log(desc + "  -> no effect.")


# --------------------------------------------------------------------------- #
# Stabilize a downed ally                                                      #
# --------------------------------------------------------------------------- #

class Stabilize(Action):
    id, name, target, aimed = "stabilize", "Stabilize", "ally", True

    def _downed_allies(self, battle, actor):
        """Adjacent allied bodies this action can work on: dying units, or broken
        automatons (repaired with an INT check instead of a death save)."""
        return [u for u in battle.units
                if (u.dying or u.broken) and u.team == actor.team and u is not actor
                and battle.units_distance(actor, u) <= 1]

    def available(self, battle, actor):
        return actor.ap >= self.cost and bool(self._downed_allies(battle, actor))

    def can(self, battle, actor, target=None):
        return (actor.ap >= self.cost and target is not None
                and target in self._downed_allies(battle, actor))

    def label(self, battle, actor):
        return (f"Stabilize a downed ally (1 pt: 50%, or repair automaton "
                f"INT vs {data.AUTOMATON_REPAIR_DC})")

    def highlight_targets(self, battle, actor):
        return self._downed_allies(battle, actor)

    def _attempt(self, battle, actor, target):
        """Stabilize a dying ally (death save) or repair a broken automaton
        (d20 + INT vs DC). Returns True on success."""
        if target.broken:
            nat = d20()
            total = nat + actor.mod_intelligence
            ok = total >= data.AUTOMATON_REPAIR_DC
            battle.log(f"{actor.name} tries to repair {target.name}: "
                       f"d20({nat}) {actor.mod_intelligence:+}(INT) = {total} vs "
                       f"{data.AUTOMATON_REPAIR_DC} -> "
                       + ("repaired." if ok else "fails."))
            if ok:
                battle.repair(target)
            return ok
        nat = d20()
        ok = nat >= data.DEATH_SAVE_MIN
        battle.log(f"{actor.name} tries to stabilize {target.name}: d20({nat}) -> "
                   + ("success." if ok else "fails."))
        if ok:
            battle.stabilize(target)
        return ok

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        self._attempt(battle, actor, target)


class FirstAid(Stabilize):
    id, name = "first_aid", "First Aid"

    def _downed_allies(self, battle, actor):
        # a med kit is for the dying; a broken automaton needs the plain Stabilize
        return [u for u in super()._downed_allies(battle, actor) if u.dying]

    def available(self, battle, actor):
        return actor.first_aid_charges > 0 and super().available(battle, actor)

    def can(self, battle, actor, target=None):
        return actor.first_aid_charges > 0 and super().can(battle, actor, target)

    def label(self, battle, actor):
        return (f"First Aid (1 pt, WIS vs {data.FIRST_AID_DC}, "
                f"{actor.first_aid_charges} charges)")

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        actor.first_aid_charges -= 1
        nat = d20()
        total = nat + actor.mod_wisdom
        ok = total >= data.FIRST_AID_DC
        battle.log(f"{actor.name} uses the kit on {target.name}: "
                   f"d20({nat}) {actor.mod_wisdom:+}(WIS) = {total} vs {data.FIRST_AID_DC} -> "
                   + ("success." if ok else "fails.")
                   + f"  ({actor.first_aid_charges} charge(s))")
        if ok:
            battle.stabilize(target)


# --------------------------------------------------------------------------- #
# Flee the battle                                                              #
# --------------------------------------------------------------------------- #

class Flee(Action):
    """Run off the map. Only from a border cell, and only if the pursuers cannot
    keep up: you are faster than the quickest of them, or already far enough
    ahead that the chase fizzles. Deterministic -- the button lights up exactly
    when the escape would work. Ends your turn; downed allies are left behind."""

    id, name = "flee", "Flee"

    @staticmethod
    def _at_edge(battle, actor):
        return any(x == 0 or x == COLS - 1 or y == 0 or y == ROWS - 1
                   for x, y in battle.cells_of(actor))

    @staticmethod
    def _pursuers(battle, actor):
        return [u for u in battle.units if u.alive and u.team != actor.team]

    def _escapes(self, battle, actor):
        pursuers = self._pursuers(battle, actor)
        if not pursuers:
            return True
        fastest = max(p.speed for p in pursuers)
        nearest = min(battle.units_distance(actor, p) for p in pursuers)
        return actor.speed > fastest or nearest > fastest

    def available(self, battle, actor):
        return (actor.ap >= self.cost and self._at_edge(battle, actor)
                and self._escapes(battle, actor))

    def label(self, battle, actor):
        if not self._at_edge(battle, actor):
            return "Flee (reach the map edge)"
        if not self._escapes(battle, actor):
            return "Flee (pursuers too fast / too close)"
        return "Flee the fight (1 pt, ends the turn)"

    def execute(self, battle, actor, target=None):
        if not self.available(battle, actor):
            return
        actor.ap = 0
        actor.walking = False
        actor.status = "fled"
        battle.log(f"{actor.name} flees the fight off the map edge.")
        # drag out any downed ally you are standing next to -- the rest are left
        for ally in battle.units:
            if (ally is not actor and ally.team == actor.team and ally.downed
                    and battle.units_distance(actor, ally) <= 1):
                ally.status = "fled"
                battle.log(f"  {actor.name} drags {ally.name} out of the fight.")
        battle._check_winner()


# --------------------------------------------------------------------------- #
# End turn                                                                     #
# --------------------------------------------------------------------------- #

class EndTurn(Action):
    id, name, cost = "end", "End turn", 0

    def available(self, battle, actor):
        return battle.winner is None

    def execute(self, battle, actor, target=None):
        battle.end_turn()


# --------------------------------------------------------------------------- #
# Registry                                                                     #
# --------------------------------------------------------------------------- #

MOVE = Move()
ATTACK = Attack()
DEFEND = Defend()
THROW = Throw()
PICK_UP = PickUp()
DEMORALIZE = Demoralize()
STABILIZE = Stabilize()
FIRST_AID = FirstAid()
FLEE = Flee()
END = EndTurn()

# Panel buttons, in order. Move and Attack are the default board click.
PANEL_ACTIONS = [THROW, DEMORALIZE, STABILIZE, FIRST_AID, PICK_UP, DEFEND, FLEE, END]
