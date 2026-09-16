"""Combat actions.

Model: 2 action points per turn. Each action is a class that knows its cost, what
kind of target it needs, whether it can be done now and how it resolves. The UI
builds the buttons from `PANEL_ACTIONS`; the AI scores from the same objects.

Adding an action (a new world thing that becomes a mechanic) = one class here and
one entry in the lists at the end of the file. Nothing else needs to know it exists.
"""

import random

from . import data, magic
from .board import cells, cells_in_radius, chebyshev, grid_distance, line_cells
from .conditions import Defending, Demoralized, Sleeping
from .data import DEMORALIZE_RANGE, d20, resolve_bonus
from .ground import GroundObject

PUSH_DC_BASE = 10          # Shove: Strength vs 10 + the target's Constitution modifier
JUMP_DIVISOR = 5          # Jump: (d20 + Strength) / this = squares cleared, capped at speed
SWIM_DIVISOR = 5          # Swim: (d20 + Strength) / this = squares crossed, capped at half speed


def _sign(v):
    return (v > 0) - (v < 0)


def _cell_free(battle, actor, pos, footprint=None):
    """Is the `footprint` (the actor's by default) able to stand at `pos` -- in
    bounds, no wall, no other body, no creature?"""
    fp = footprint or actor.footprint
    shape = cells(pos, fp)
    if not all(battle.board.in_bounds(c) for c in shape):
        return False
    blocked = (battle.board.walls | battle.occupied(exclude=actor)
               | battle.creature_cells())
    return not blocked.intersection(shape)


# --------------------------------------------------------------------------- #
# Base                                                                         #
# --------------------------------------------------------------------------- #

class Action:
    id = ""
    name = ""
    cost = 1
    desc = ""
    target = "none"        # "none" | "enemy" | "cell"
    aimed = False          # True: needs the target picked by clicking the screen

    @classmethod
    def applicable(cls, battle, actor):
        """Should this action be shown on the action bar for this unit at all?
        Returns (True, "") if it should, or (False, reason) if blocked."""
        return True, ""

    def available(self, battle, actor):
        """Does the action show enabled for this unit now (no target chosen yet)?"""
        applies, _ = self.applicable(battle, actor)
        return applies and actor.ap >= self.cost

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
    """Loose flank (Pack Tactics): how many allies, other than the attacker,
    are adjacent to the target -- 0 is falsy (no flank) same as the old bool;
    a wolf's version of the ability reads the actual count to scale with the
    size of the pack, not just whether it's flanked at all."""
    return sum(1 for u in battle.units
               if u.alive and u.team == attacker.team and u is not attacker
               and battle.units_distance(u, target) == 1)


def _facing(battle, unit, target_cells):
    """Which side of the target's footprint `unit` is on: each axis is -1/0/1,
    0 meaning `unit` is aligned within the footprint's span on that axis (e.g.
    directly north of a Large target, not off to a diagonal corner) -- a
    fractional centre would never land on 0 for an even (Large+) footprint and
    bias every facing to a diagonal, so this uses the footprint's box instead."""
    xs = [x for x, _ in target_cells]
    ys = [y for _, y in target_cells]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)

    def dist(c):
        x, y = c
        return (x - min(max(x, min_x), max_x)) ** 2 + (y - min(max(y, min_y), max_y)) ** 2

    ux, uy = min(battle.cells_of(unit), key=dist)
    sx = -1 if ux < min_x else (1 if ux > max_x else 0)
    sy = -1 if uy < min_y else (1 if uy > max_y else 0)
    return (sx, sy)


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


def _phalanxed(battle, target):
    """Hobgoblin Phalanx: +1 AC if adjacent to at least one ally."""
    if not target.char.has_talent("phalanx"):
        return False
    for u in battle.units:
        if (u.alive and u.team == target.team and u is not target
                and battle.units_distance(u, target) <= 1):
            return True
    return False


def _hostile_target(actor, target):
    return target is not None and target.alive and target.team != actor.team


def _shovable_target(actor, target):
    """Push works on anyone standing, foe or friend -- just not yourself."""
    return target is not None and target.alive and target is not actor


def _attackable_target(actor, target):
    """Attack and Throw may also target a downed enemy body, to finish it off."""
    return target is not None and not target.dead and target.team != actor.team


def _shared_language(a, b):
    return bool(set(a.languages) & set(b.languages))


def _drop_cell(battle, target):
    """A free cell adjacent to the target where the thrown weapon lands."""
    tcells = set(cells(target.pos, target.footprint))
    around = {v for c in tcells for v in battle.board.neighbors(c)} - tcells
    free = [p for p in around
            if battle.unit_at(p) is None and battle.ground_at(p) is None
            and p not in battle.board.walls]
    return random.choice(free) if free else target.pos


def _pickable(unit, obj):
    """Anyone can pick up a torch if the off hand is free; a weapon only if
    the unit is unarmed."""
    if obj.is_torch:
        return not unit.has_torch and not unit.has_lantern
    return unit.unarmed


def _resolve_hit(battle, attacker, target, nat, bonus, detail, prefix, thrown=False,
                 weapon=None):
    total = nat + bonus
    ac = target.ac
    phalanx = _phalanxed(battle, target)
    if phalanx:
        ac += 1
    crit = nat == 20
    desc = f"{prefix}: d20({nat}) {detail} = {total} vs AC {ac}" + (" [Phalanx]" if phalanx else "")
    fx_text = f"{total} vs AC {ac}"
    if nat == 1:
        battle.log(desc + "  -> critical miss.")
        battle.fx(target.pos, "Crit Miss!", "faint")
        return "miss"
    if crit or total >= ac:
        battle.fx(target.pos, fx_text, "ok" if not crit else "crit")
        if target.dying:
            battle.log(desc + "  -> coup de grace: DEAD.")
            target.status = "dead"
            return "crit" if crit else "hit"
        battle.log(desc + ("  -> CRITICAL HIT!" if crit else "  -> hit."))
        was_up = target.alive
        target.take_damage(
            attacker.damage_roll(crit=crit, thrown=thrown, weapon=weapon), battle.log)
        if was_up and target.team != attacker.team:
            if not target.alive:
                attacker.credit_kill(target)
            elif target.hp <= 0 and target.ferocity_downer is None:
                target.ferocity_downer = attacker
        return "crit" if crit else "hit"
    battle.log(desc + "  -> misses.")
    battle.fx(target.pos, fx_text, "faint")
    return "miss"


# --------------------------------------------------------------------------- #
# Move                                                                         #
# --------------------------------------------------------------------------- #

class Move(Action):
    id, name, cost, target = "move", "Move", 1, "cell"
    desc = "Move up to your speed."

    def available(self, battle, actor):
        if getattr(actor, "mounted_on", None) is not None:
            return False
        return bool(battle.reachable(actor))

    def can(self, battle, actor, target=None):
        if getattr(actor, "mounted_on", None) is not None:
            return False
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

def _strike(battle, actor, target, *, weapon=None, prefix=None):
    """The shared attack resolution once the AP is paid: assemble the mods (flank,
    feint), roll, resolve the hit, fire the on-miss ability. `weapon` overrides the
    held one (the Tongue). Returns 'hit'|'miss'|'crit'."""
    mods = actor.attack_mods(target, _pack_flank(battle, actor, target), weapon=weapon)
    if _flanked(battle, actor, target):
        mods.append((2, "circumstance", "Flank"))

    ab = actor.ability
    if ab.feint and actor.spend_once("feint"):
        mods += ab.feint(actor, target)
        battle.log(f"{actor.name} uses {ab.name} to distract.")

    bonus, applied = resolve_bonus(mods)
    detail = " ".join(f"{v:+}({r})" for v, r in applied)
    nat = d20()
    result = _resolve_hit(battle, actor, target, nat, bonus, detail,
                          prefix or f"{actor.name} -> {target.name}", weapon=weapon)

    if result == "miss" and nat != 1 and ab.on_attack_miss \
            and actor.spend_once("on_attack_miss"):
        ab.on_attack_miss(battle, actor, target, bonus, target.ac, battle.log)
    elif result == "miss" and actor.can_use_luck(getattr(battle, "clock_day", 1)):
        actor.use_luck(getattr(battle, "clock_day", 1))
        nat2 = d20()
        total2 = nat2 + bonus
        hits = nat2 == 20 or total2 >= target.ac
        battle.log(f"  Halfling Luck! {actor.name} rerolls attack: d20({nat2}) = {total2} -> "
                   + ("hit." if hits else "misses again."))
        if hits:
            target.take_damage(actor.damage_roll(crit=nat2 == 20, weapon=weapon), battle.log)
            result = "hit"
    return result


class Attack(Action):
    id, name, cost, target, aimed = "attack", "Attack", 1, "enemy", True
    desc = "Melee or Ranged attack based on your equipped weapon."

    def can(self, battle, actor, target=None):
        if actor.ap < self.cost or not _attackable_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.attack_range:
            return False
        # melee only crosses a one-level lip; a deeper drop is out of reach
        if not actor.ranged \
                and abs(battle.elevation(actor) - battle.elevation(target)) > 1:
            return False
        if not battle.los_between(actor, target):
            return False
        if not battle.can_see_unit(actor, target):
            return False
        return True

    def highlight_cells(self, battle, actor):
        rng = actor.attack_range
        return [p for c in cells(actor.pos, actor.footprint)
                for p in cells_in_radius(c, rng)]

    def highlight_targets(self, battle, actor):
        return [u for u in battle.units
                if not u.dead and u.team != actor.team and self.can(battle, actor, u)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        if actor.ranged:
            if actor.weapon.get("reload"):
                actor.crossbow_loaded = False               # spent -- needs a Reload before the next shot
            battle.log(f"{actor.name} shoots ({actor.ammo} bolt(s) in the quiver).")
        _strike(battle, actor, target)


class AttackTongue(Action):
    """The Grippli's Tongue: a second weapon, an extra limb. A 1-handed weapon in
    the Tongue slot, swung at +1 square of reach. A separate action so a Grippli
    can choose it or the hand weapon each turn (a reach poke vs. a 2-handed blow)."""

    id, name, cost, target, aimed = "attack_tongue", "Lash", 1, "enemy", True
    desc = "Lash an enemy with your tongue."

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.has_tongue_weapon:
            return False, "Not a Grippli with Tongue."
        return True, ""

    def available(self, battle, actor):
        return actor.ap >= self.cost and actor.has_tongue_weapon

    def can(self, battle, actor, target=None):
        if actor.ap < self.cost or not actor.has_tongue_weapon:
            return False
        if not _attackable_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.tongue_reach:
            return False
        if abs(battle.elevation(actor) - battle.elevation(target)) > 1:
            return False
        return battle.los_between(actor, target) and battle.can_see_unit(actor, target)

    def label(self, battle, actor):
        if not self.available(battle, actor):
            return "Lash with the tongue (1 pt)"
        return f"Lash {actor.tongue_weapon_name} (1 pt, reach {actor.tongue_reach})"

    def highlight_cells(self, battle, actor):
        return [p for c in cells(actor.pos, actor.footprint)
                for p in cells_in_radius(c, actor.tongue_reach)]

    def highlight_targets(self, battle, actor):
        return [u for u in battle.units
                if not u.dead and u.team != actor.team and self.can(battle, actor, u)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        _strike(battle, actor, target, weapon=actor.tongue_weapon,
                prefix=f"{actor.name} -> {target.name} (tongue)")


# --------------------------------------------------------------------------- #
# Reload                                                                       #
# --------------------------------------------------------------------------- #

class Reload(Action):
    """Chamber a bolt in the crossbow: takes one from the quiver, 1 action point.
    A crossbow fires only while loaded and each shot empties it, so a crossbowman
    gets one bolt away per turn (Reload + Attack = the whole turn)."""

    id, name, cost, target = "reload", "Reload", 1, "none"
    desc = "Reload your crossbow."

    @classmethod
    def applicable(cls, battle, actor):
        if not hasattr(actor, "weapon") or not actor.weapon:
            return False, "Not holding a weapon."
        if not actor.weapon.get("reload"):
            return False, "Weapon does not need reloading."
        return True, ""

    def available(self, battle, actor):
        return actor.ap >= self.cost and actor.can_reload

    def can(self, battle, actor, target=None):
        return self.available(battle, actor)

    def label(self, battle, actor):
        return f"Reload the weapon (1 pt, {actor.ammo} bolts left)"

    def execute(self, battle, actor, target=None):
        if not self.available(battle, actor):
            return
        actor.ap -= 1
        actor.walking = False
        actor.ammo -= 1
        actor.crossbow_loaded = True
        battle.log(f"{actor.name} reloads the weapon ({actor.ammo} bolt(s) left).")


# --------------------------------------------------------------------------- #
# Defend                                                                       #
# --------------------------------------------------------------------------- #

class Defend(Action):
    id, name, cost, target = "defend", "Defend", 1, "none"
    desc = "+2 AC until your next turn."

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
    id, name, cost, target, aimed = "throw", "Throw", 1, "enemy", True
    desc = "Throw your equipped weapon at a target in range."

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
                for p in cells_in_radius(c, actor.throw_range)]

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
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix, thrown=True)
        if res == "miss" and actor.can_use_luck(getattr(battle, "clock_day", 1)):
            actor.use_luck(getattr(battle, "clock_day", 1))
            nat2 = d20()
            total2 = nat2 + bonus
            hits = nat2 == 20 or total2 >= target.ac
            battle.log(f"  Halfling Luck! {actor.name} rerolls throw: d20({nat2}) = {total2} -> "
                       + ("hit." if hits else "misses again."))
            if hits:
                target.take_damage(actor.damage_roll(crit=nat2 == 20, thrown=True), battle.log)

        actor.disarm()
        landing = _drop_cell(battle, target)
        battle.ground.append(GroundObject.weapon(landing, weapon_name))
        battle.log(f"  {weapon_name} lands at {landing}; {actor.name} is disarmed.")


# --------------------------------------------------------------------------- #
# Pick up object                                                               #
# --------------------------------------------------------------------------- #

class PickUp(Action):
    id, name, cost, target = "pick_up", "Pick up", 1, "none"
    desc = "Pick up a dropped item or torch in your cell."

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
            for p in battle.board.neighbors(actor.pos):
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
    id, name, cost, target, aimed = "demoralize", "Demoralize", 1, "enemy", True
    desc = "Cha vs MD. Target is demoralized (cannot move, lower defenses)."

    def _can_provoke(self, battle, actor, target):
        return (actor.ability.demoralize_ignores_language
                or _shared_language(actor, target)
                or (battle.arena and getattr(actor, "arena_title", False)))

    def can(self, battle, actor, target=None):
        if actor.ap < self.cost or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > DEMORALIZE_RANGE:
            return False
        if not (battle.can_see_unit(actor, target) and battle.can_see_unit(target, actor)):
            return False
        return self._can_provoke(battle, actor, target)

    def label(self, battle, actor):
        return "Demoralize (1 pt, CHA vs Mental Defense)"

    def highlight_cells(self, battle, actor):
        return [p for c in cells(actor.pos, actor.footprint)
                for p in cells_in_radius(c, DEMORALIZE_RANGE)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False

        base_mod = actor.mod_charisma
        using_str = False
        has_talent = getattr(actor.char, "has_talent", lambda x: False)
        if has_talent("intimidating_presence") and actor.mod_strength > actor.mod_charisma:
            base_mod = actor.mod_strength
            using_str = True

        mods = [(base_mod, None, "STR" if using_str else "CHA")]
        titled = battle.arena and getattr(actor, "arena_title", False)
        if titled and _shared_language(actor, target):
            mods.append((1, "circumstance", "Champion of the Pit"))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)

        if actor.ability.demoralize_ignores_language and not _shared_language(actor, target):
            battle.log(f"{actor.name} mimics {target.name}'s voice to provoke them.")

        nat = d20()
        total = nat + bonus
        md = target.mental_defense
        if battle.arena and getattr(target, "arena_title", False):
            md += 1                                # the champion is hard to rattle in their own pit
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
    id, name, cost, target, aimed = "stabilize", "Stabilize", 1, "ally", True
    desc = "50% chance to stabilize an adjacent dying ally."

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
            battle.fx(target.pos, f"{total} vs {data.AUTOMATON_REPAIR_DC}", "ok" if ok else "faint")
            if ok:
                battle.repair(target)
            return ok
        nat = d20()
        ok = nat >= data.DEATH_SAVE_MIN
        battle.log(f"{actor.name} tries to stabilize {target.name}: d20({nat}) -> "
                   + ("success." if ok else "fails."))
        battle.fx(target.pos, f"d20({nat}) " + ("Success" if ok else "Fail"), "ok" if ok else "faint")
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
    id, name, cost, target, aimed = "first_aid", "First Aid", 1, "ally", True
    desc = "Use a medkit: 100% chance to stabilize, or cure sickness."

    def _downed_allies(self, battle, actor):
        # a med kit is for the dying and the sick; a broken automaton needs the plain Stabilize
        return [u for u in battle.units
                if (u.dying or getattr(u.char, "sick", False)) and u.team == actor.team and u is not actor
                and battle.units_distance(actor, u) <= 1]

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
        target_sick = getattr(target.char, "sick", False)
        target_dying = target.dying

        battle.log(f"{actor.name} uses the kit on {target.name}: "
                   f"d20({nat}) {actor.mod_wisdom:+}(WIS) = {total} vs {data.FIRST_AID_DC} -> "
                   + ("success." if ok else "fails.")
                   + f"  ({actor.first_aid_charges} charge(s))")
        if ok:
            if target_dying:
                battle.stabilize(target)
            if target_sick:
                target.char.sick = False
                battle.log(f"  {target.name} is cured of their sickness!")
                target.char._derive_combat()
                target.hp_max = target.char.hp_max
                target.hp = min(target.hp, target.hp_max)


# --------------------------------------------------------------------------- #
# Flee the battle                                                              #
# --------------------------------------------------------------------------- #

class Flee(Action):
    """Run off the map. Only from a border cell, and only if the pursuers cannot
    keep up: you are faster than the quickest of them, or already far enough
    ahead that the chase fizzles. Deterministic -- the button lights up exactly
    when the escape would work. Ends your turn; downed allies are left behind."""

    id, name, cost, target = "flee", "Flee", 1, "none"
    desc = "Flee the battle from the map edge."

    @staticmethod
    def _at_edge(battle, actor):
        b = battle.board
        return any(x == 0 or x == b.cols - 1 or y == 0 or y == b.rows - 1
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
# The Z axis: Push, Climb, Drop in, Jump                                       #
# --------------------------------------------------------------------------- #

class Push(Action):
    """Shove an adjacent unit -- foe or friend -- one square straight back.
    Strength vs 10 + their Constitution modifier. If the square behind them is
    a pit, they go in (and take the fall). A wall / body behind them stops the
    shove dead."""

    id, name, cost, target, aimed = "push", "Push", 1, "unit", True
    desc = "Push an adjacent unit."

    def _targets(self, battle, actor):
        return [u for u in battle.units
                if u.alive and u is not actor and self.can(battle, actor, u)]

    def available(self, battle, actor):
        return actor.ap >= self.cost and bool(self._targets(battle, actor))

    def can(self, battle, actor, target=None):
        if actor.ap < self.cost or not _shovable_target(actor, target):
            return False
        if battle.units_distance(actor, target) > 1:
            return False
        if abs(battle.elevation(actor) - battle.elevation(target)) > 1:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Push (1 pt, STR vs 10 + target CON)"

    def highlight_targets(self, battle, actor):
        return self._targets(battle, actor)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        dc = PUSH_DC_BASE + target.mod_constitution
        nat = d20()
        total = nat + actor.mod_strength
        desc = (f"{actor.name} shoves {target.name}: d20({nat}) "
                f"{actor.mod_strength:+}(STR) = {total} vs {dc}")
        if nat != 20 and (nat == 1 or total < dc):
            battle.log(desc + "  -> holds their ground.")
            return

        ax, ay = actor.pos
        tx, ty = target.pos
        dx, dy = _sign(tx - ax), _sign(ty - ay)
        if dx == 0 and dy == 0:
            battle.log(desc + "  -> no room to shove.")
            return
        dest = (tx + dx, ty + dy)
        if battle.board.diagonal_corner_blocked(target.pos, dest) \
                or not _cell_free(battle, actor, dest, target.footprint):
            battle.log(desc + f"  -> {target.name} is shoved against something and can't move.")
            return
        z_from = battle.elevation(target)
        z_to = battle.board.elevation_at(dest)
        target.pos = dest
        target.walking = False
        battle.log(desc + f"  -> {target.name} is shoved to {dest}.")
        
        trap = battle.ground_at(dest)
        if trap and trap.is_trap and trap.trap_owner_team != target.team:
            battle.trigger_trap(target, trap)
            
        if z_to < z_from:
            battle.apply_fall(target, z_from - z_to, battle.log)


class _VerticalStep(Action):
    """Shared base for the single-square elevation moves (Climb / Drop in): the
    candidate cells are the adjacent ones at a different floor height."""

    target, aimed = "cell", True

    def _spots(self, battle, actor):
        z = battle.elevation(actor)
        return [nb for nb in battle.board.neighbors(actor.pos)
                if self._wants(battle.board.elevation_at(nb), z)
                and _cell_free(battle, actor, nb)
                and not battle.board.diagonal_corner_blocked(actor.pos, nb)]

    def _wants(self, z_nb, z_here):
        raise NotImplementedError

    def available(self, battle, actor):
        return actor.ap >= self.cost and bool(self._spots(battle, actor))

    def can(self, battle, actor, target=None):
        return (actor.ap >= self.cost and isinstance(target, tuple)
                and target in self._spots(battle, actor))

    def highlight_cells(self, battle, actor):
        return self._spots(battle, actor)

    def highlight_targets(self, battle, actor):
        return []


class Climb(_VerticalStep):
    """Haul yourself one square up or down a pit wall. Strength vs the surface DC
    (bare stone 15, a rope 10); the Lizardfolk's Climber clears it with no roll.
    A slip just costs the action."""

    id, name, cost = "climb", "Climb", 1
    desc = "Climb an obstacle."

    def _wants(self, z_nb, z_here):
        return z_nb != z_here

    def label(self, battle, actor):
        return "Climb (1 pt, STR vs surface DC)"

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        z_from = battle.elevation(actor)
        z_to = battle.board.elevation_at(target)
        low_cell = target if z_to < z_from else actor.pos
        dc = battle.board.surface_dc(low_cell)
        way = "down" if z_to < z_from else "up"
        if actor.auto_climb(dc):
            actor.pos = target
            battle.log(f"{actor.name} climbs {way} (Climber -- no check).")
            return
        nat = d20()
        total = nat + actor.mod_strength
        desc = (f"{actor.name} climbs {way}: d20({nat}) {actor.mod_strength:+}(STR) "
                f"= {total} vs DC {dc}")
        if nat == 20 or total >= dc:
            actor.pos = target
            battle.log(f"{desc}  -> {'up and over' if way == 'up' else 'down'}.")
        else:
            battle.log(desc + "  -> slips, stays put.")


class DropIn(_VerticalStep):
    """Throw yourself into the pit -- a deliberate drop into a lower adjacent
    square, no check, but you take the fall (every level past the first is 1d6)."""

    id, name, cost = "drop", "Drop in", 1
    desc = "Drop into a lower adjacent square."

    def _wants(self, z_nb, z_here):
        return z_nb < z_here

    def label(self, battle, actor):
        return "Drop into the pit (1 pt, take the fall)"

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        z_from = battle.elevation(actor)
        z_to = battle.board.elevation_at(target)
        actor.pos = target
        battle.log(f"{actor.name} drops into the pit at {target}.")
        battle.apply_fall(actor, z_from - z_to, battle.log)


class Jump(Action):
    """A running jump: d20 + Strength, clear (result / 5) squares (never more than
    your speed) straight toward the aimed cell, sailing over any pit in between.
    A wall or a body ends the jump short; land lower than you left and you fall."""

    id, name, cost, target, aimed = "jump", "Jump", 1, "cell", True
    desc = "Jump across gaps or obstacles."

    def _max_reach(self, battle, actor):
        return max(0, min((20 + actor.mod_strength) // JUMP_DIVISOR, actor.speed))

    def available(self, battle, actor):
        return actor.ap >= self.cost and self._max_reach(battle, actor) >= 1

    def can(self, battle, actor, target=None):
        if actor.ap < self.cost or not isinstance(target, tuple):
            return False
        if not battle.board.in_bounds(target) or target == actor.pos:
            return False
        return grid_distance(actor.pos, target) <= self._max_reach(battle, actor)

    def label(self, battle, actor):
        return "Jump (1 pt, STR: clears result/5 squares)"

    def highlight_cells(self, battle, actor):
        r = self._max_reach(battle, actor)
        return [p for p in cells_in_radius(actor.pos, r) if battle.board.in_bounds(p)]

    def highlight_targets(self, battle, actor):
        return []

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        nat = d20()
        total = nat + actor.mod_strength
        dist = max(0, min(total // JUMP_DIVISOR, actor.speed))
        landing = actor.pos
        for step, cell in enumerate(line_cells(actor.pos, target)[1:], start=1):
            if step > dist or cell in battle.board.walls \
                    or not _cell_free(battle, actor, cell):
                break
            landing = cell
        z_from = battle.elevation(actor)
        z_to = battle.board.elevation_at(landing)
        actor.pos = landing
        battle.log(f"{actor.name} jumps: d20({nat}) {actor.mod_strength:+}(STR) = "
                   f"{total} -> {total // JUMP_DIVISOR} squares, lands at {landing}.")
        if z_to < z_from:
            battle.apply_fall(actor, z_from - z_to, battle.log)


class Swim(Action):
    """Strike out through deep water: d20 + Strength, cross (result / 5) squares
    toward the aimed cell, never more than half your speed. You swim only through
    water -- a wall, a body or the water's edge ends the swim there (haul yourself
    out of the pit with a Climb). No check to stay afloat; a poor roll just means
    a short swim."""

    id, name, cost, target, aimed = "swim", "Swim", 1, "cell", True
    desc = "Swim through deep water."

    def _at_water(self, battle, actor):
        """The actor is in deep water, or on a cell touching it (can push off)."""
        for c in battle.cells_of(actor):
            if battle.board.is_deep_water(c):
                return True
            if any(battle.board.is_deep_water(nb) for nb in battle.board.neighbors(c)):
                return True
        return False

    def _max_reach(self, battle, actor):
        by_str = (20 + actor.mod_strength) // SWIM_DIVISOR
        return max(1, min(by_str, max(1, actor.speed // 2)))

    def available(self, battle, actor):
        return (actor.ap >= self.cost and not actor.flies
                and self._at_water(battle, actor))

    def can(self, battle, actor, target=None):
        if actor.ap < self.cost or actor.flies or not isinstance(target, tuple):
            return False
        if not battle.board.in_bounds(target) or target == actor.pos:
            return False
        if not self._at_water(battle, actor):
            return False
        return grid_distance(actor.pos, target) <= self._max_reach(battle, actor)

    def label(self, battle, actor):
        return "Swim (1 pt, STR: crosses result/5 squares, half speed)"

    def highlight_cells(self, battle, actor):
        r = self._max_reach(battle, actor)
        return [p for p in cells_in_radius(actor.pos, r)
                if battle.board.in_bounds(p)
                and (battle.board.is_deep_water(p) or grid_distance(actor.pos, p) == 1)]

    def highlight_targets(self, battle, actor):
        return []

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        nat = d20()
        total = nat + actor.mod_strength
        dist = max(1, min(total // SWIM_DIVISOR, max(1, actor.speed // 2)))
        landing = actor.pos
        for step, cell in enumerate(line_cells(actor.pos, target)[1:], start=1):
            if step > dist or cell in battle.board.walls \
                    or not _cell_free(battle, actor, cell):
                break
            if not battle.board.is_deep_water(cell):
                break                        # left the water -- climb out from here
            landing = cell
        z_from = battle.elevation(actor)
        z_to = battle.board.elevation_at(landing)
        actor.pos = landing
        battle.log(f"{actor.name} swims: d20({nat}) {actor.mod_strength:+}(STR) = "
                   f"{total} -> {total // SWIM_DIVISOR} squares, to {landing}.")
        if z_to < z_from:
            battle.apply_fall(actor, z_from - z_to, battle.log)


# --------------------------------------------------------------------------- #
# Racial Actions                                                               #
# --------------------------------------------------------------------------- #

class EatCorpse(Action):
    id, name, cost, target, aimed = "eat_corpse", "Eat Corpse", 1, "enemy", True
    desc = "Devour a corpse to reset hunger and terrify foes."

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.char.has_talent("corpse_eater"):
            return False, "Missing 'corpse_eater' talent."
        return True, ""

    def available(self, battle, actor):
        if not super().available(battle, actor) or getattr(actor, "mounted_on", None) is not None:
            return False
        if not actor.char.has_talent("corpse_eater"):
            return False
        for u in battle.units:
            if u.team != actor.team and u.dead and getattr(u, "eaten", False) is False and battle.units_distance(u, actor) <= 1:
                return True
        return False

    def can(self, battle, actor, target=None):
        return (super().can(battle, actor, target) and target is not None 
                and target.team != actor.team and target.dead 
                and battle.units_distance(target, actor) <= 1
                and getattr(target, "eaten", False) is False)

    def highlight_targets(self, battle, actor):
        return [u for u in battle.units if self.can(battle, actor, u)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        target.eaten = True
        actor.char.unfed_days = 0
        battle.log(f"{actor.name} devours {target.name}'s corpse (hunger reset to 0).")
        
        nat = d20()
        bonus = max(actor.mod_strength, actor.mod_charisma)
        total = nat + bonus
        battle.log(f"  Terrifying feast: d20({nat}) {bonus:+} = {total} (AoE Demoralize)")
        
        for u in battle.units:
            if u.team != actor.team and u.alive and battle.can_see_unit(u, actor):
                md = u.mental_defense
                if total >= md:
                    u.add_condition(Demoralized())
                    battle.log(f"    {u.name} (MD {md}) is terrified -> DEMORALIZED.")
                else:
                    battle.log(f"    {u.name} (MD {md}) resists the horror.")


class Mount(Action):
    id, name, cost, target, aimed = "mount", "Mount", 1, "ally", True
    desc = "Mount an allied centaur."

    @classmethod
    def applicable(cls, battle, actor):
        if getattr(actor, "mounted_on", None) is not None:
            return False, "Already mounted."
        if actor.size not in ("Small", "Medium"):
            return False, "Too large to ride a mount."
        has_mount = any(u.alive and u.team == actor.team and u is not actor and u.char.has_talent("centaur_mount") for u in battle.units)
        if not has_mount:
            return False, "No mount in squad."
        return True, ""

    def available(self, battle, actor):
        if not super().available(battle, actor):
            return False
        if getattr(actor, "mounted_on", None) is not None or actor.size not in ("Small", "Medium"):
            return False
        for u in battle.units:
            if u.alive and u.team == actor.team and u is not actor and u.char.has_talent("centaur_mount") and not getattr(u, "rider", None) and battle.units_distance(actor, u) <= 1:
                return True
        return False

    def can(self, battle, actor, target=None):
        return (super().can(battle, actor, target) and target is not None
                and target.alive and target.team == actor.team and target is not actor
                and target.char.has_talent("centaur_mount") and not getattr(target, "rider", None)
                and battle.units_distance(actor, target) <= 1)

    def highlight_targets(self, battle, actor):
        return [u for u in battle.units if self.can(battle, actor, u)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        actor.mounted_on = target
        target.rider = actor
        actor.pos = target.pos
        battle.log(f"{actor.name} mounts {target.name}.")


class Dismount(Action):
    id, name, cost, target, aimed = "dismount", "Dismount", 1, "cell", True
    desc = "Dismount from your current mount."

    @classmethod
    def applicable(cls, battle, actor):
        if getattr(actor, "mounted_on", None) is None:
            return False, "Not currently mounted."
        return True, ""

    def available(self, battle, actor):
        return super().available(battle, actor) and getattr(actor, "mounted_on", None) is not None

    def can(self, battle, actor, target=None):
        if not super().can(battle, actor, target):
            return False
        if getattr(actor, "mounted_on", None) is None or target is None:
            return False
        return target in battle.board.neighbors(actor.mounted_on.pos) and _cell_free(battle, actor, target)

    def highlight_cells(self, battle, actor):
        if not getattr(actor, "mounted_on", None):
            return []
        return [c for c in battle.board.neighbors(actor.mounted_on.pos) if _cell_free(battle, actor, c)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        mount = actor.mounted_on
        actor.mounted_on = None
        mount.rider = None
        actor.pos = target
        battle.log(f"{actor.name} dismounts to {target}.")

class WakeUp(Action):
    id, name, cost, target, aimed = "wake_up", "Wake Up", 1, "ally", True
    desc = "Wake up an adjacent sleeping ally."

    @classmethod
    def applicable(cls, battle, actor):
        has_sleeping = any(u.alive and u.team == actor.team and u.has_condition("sleeping") for u in battle.units)
        if not has_sleeping:
            return False, "No sleeping allies."
        return True, ""

    def _sleeping_allies(self, battle, actor):
        return [u for u in battle.units
                if u.alive and u.team == actor.team and u is not actor
                and u.has_condition("sleeping")
                and battle.units_distance(actor, u) <= 1]

    def available(self, battle, actor):
        return actor.ap >= self.cost and bool(self._sleeping_allies(battle, actor))

    def can(self, battle, actor, target=None):
        return (actor.ap >= self.cost and target is not None
                and target in self._sleeping_allies(battle, actor))

    def label(self, battle, actor):
        return "Wake Up (1 pt, wake a sleeping ally)"

    def highlight_targets(self, battle, actor):
        return self._sleeping_allies(battle, actor)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        
        sleeping_cond = next((c for c in target.conditions if c.id == "sleeping"), None)
        if sleeping_cond:
            target.conditions.remove(sleeping_cond)
        
        battle.log(f"{actor.name} shakes {target.name} awake!")


# --------------------------------------------------------------------------- #
# End turn                                                                     #
# --------------------------------------------------------------------------- #

class EndTurn(Action):
    id, name, cost, target = "end", "End Turn", 0, "none"
    desc = "End your turn."

    def available(self, battle, actor):
        return battle.winner is None

    def execute(self, battle, actor, target=None):
        battle.end_turn()


# --------------------------------------------------------------------------- #
# Registry                                                                     #
# --------------------------------------------------------------------------- #

MOVE = Move()
ATTACK = Attack()
ATTACK_TONGUE = AttackTongue()
RELOAD = Reload()
DEFEND = Defend()
THROW = Throw()
PICK_UP = PickUp()
DEMORALIZE = Demoralize()
STABILIZE = Stabilize()
FIRST_AID = FirstAid()
PUSH = Push()
CLIMB = Climb()
DROP = DropIn()
JUMP = Jump()
SWIM = Swim()
FLEE = Flee()
EAT_CORPSE = EatCorpse()
MOUNT = Mount()
DISMOUNT = Dismount()
WAKE_UP = WakeUp()
END = EndTurn()

class SpellAction(Action):
    """Shared plumbing for a spell cast as a combat action: one subclass per
    spell (same "one class = one mechanic" rule as the rest of this file),
    looked up once against `magic.SPELLS` by `spell_id`. Built through the
    `CastSpellAction(spell_id)` factory below, so `ai.py` / `battle_screen.py`
    don't need to know the id -> class mapping."""
    spell_id = ""
    cost = 1

    def __init__(self):
        self.spell = magic.SPELLS[self.spell_id]
        self.id = f"cast_{self.spell_id}"
        self.name = self.spell.name

    def available(self, battle, actor):
        return actor.ap >= self.cost and self.spell_id in actor.spells_known


class MagicMissileAction(SpellAction):
    spell_id = "magic_missile"
    target, aimed = "enemy", True

    def can(self, battle, actor, target=None):
        if not super().can(battle, actor, target):
            return False
        if not _hostile_target(actor, target):
            return False
        return battle.units_distance(actor, target) <= 6

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        battle.log(f"{actor.name} casts {self.spell.name} on {target.name}!")
        atk = d20()
        if atk == 1:
            battle.log(" Critical miss!")
            return
        hit_score = atk + actor.mod_intelligence
        if atk == 20 or hit_score >= target.ac:
            dmg = data.roll(1, 4)
            battle.log(f" Hit ({hit_score} vs AC {target.ac}) for {dmg} magic damage.")
            was_up = target.alive
            target.take_damage(dmg, battle.log)
            if was_up and not target.alive and target.team != actor.team:
                actor.credit_kill(target)
        else:
            battle.log(f" Miss ({hit_score} vs AC {target.ac}).")


class SleepAction(SpellAction):
    spell_id = "sleep"
    target, aimed = "enemy", True

    def can(self, battle, actor, target=None):
        if not super().can(battle, actor, target):
            return False
        if not _hostile_target(actor, target):
            return False
        return battle.units_distance(actor, target) <= 6

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        battle.log(f"{actor.name} casts {self.spell.name} on {target.name}!")
        if getattr(target.char.ability, "sleep_immunity", False):
            battle.log(f"  {target.name} is immune to sleep effects!")
            return

        atk = d20()
        hit_score = atk + actor.mod_intelligence
        md = target.mental_defense
        desc = f" d20({atk}) {actor.mod_intelligence:+}(INT) = {hit_score} vs MD {md}"

        if atk == 1:
            battle.log(desc + " -> Critical miss!")
        elif atk == 20 or hit_score >= md:
            target.add_condition(Sleeping())
            battle.log(desc + (" -> CRITICAL HIT!" if atk == 20 else " -> lands.") + f" {target.name} falls asleep!")
        else:
            battle.log(desc + " -> resisted.")


class _PlacedSpellAction(SpellAction):
    """Shared `can()` for the two spells that drop something on a cell
    (Light Globe, Floating Disk) instead of targeting an enemy."""
    target, aimed = "cell", True

    def can(self, battle, actor, target=None):
        if not super().can(battle, actor, target):
            return False
        if not target or not battle.board.in_bounds(target):
            return False
        dist = grid_distance(battle.cells_of(actor)[0], target)
        return dist <= 6 and _cell_free(battle, actor, target, footprint=1)


class LightGlobeAction(_PlacedSpellAction):
    spell_id = "light_globe"

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        battle.log(f"{actor.name} casts {self.spell.name}.")
        battle.ground.append(GroundObject.torch(target))


class FloatingDiskAction(_PlacedSpellAction):
    spell_id = "floating_disk"

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        battle.log(f"{actor.name} casts {self.spell.name}.")
        battle.ground.append(GroundObject("floating_disk", target))


_SPELL_ACTIONS = {
    "magic_missile": MagicMissileAction,
    "sleep": SleepAction,
    "light_globe": LightGlobeAction,
    "floating_disk": FloatingDiskAction,
}


def CastSpellAction(spell_id):
    """Build the Action for `spell_id` (see `_SPELL_ACTIONS`)."""
    return _SPELL_ACTIONS[spell_id]()

class ShareMagicAction(Action):
    id = "share_magic"
    name = "Share Magic"
    cost = 1
    target = "none"
    
    @classmethod
    def applicable(cls, battle, actor):
        if not actor.char.has_talent("sprite_nature_initiate"):
            return False, "Not a Sprite Initiate."
        if not actor.spells_known:
            return False, "No spells known."
        return True, ""

    def available(self, battle, actor):
        return (actor.ap >= self.cost
                and actor.char.has_talent("sprite_nature_initiate")
                and len(actor.spells_known) > 0)

    def execute(self, battle, actor, target=None):
        if not self.available(battle, actor): return
        actor.ap -= self.cost

        allies = [u for u in battle.units if u.alive and u.team == actor.team and u != actor]
        if not allies:
            battle.log(f"{actor.name} tries to share magic, but no allies are nearby!")
            return

        ally = random.choice(allies)
        spell_id = random.choice(actor.spells_known)
        spell_name = magic.SPELLS[spell_id].name if spell_id in magic.SPELLS else spell_id

        if spell_id not in ally.spells_known:
            ally.spells_known.append(spell_id)
            battle.log(f"{actor.name} shares magic! {ally.name} temporarily learns {spell_name}.")
        else:
            battle.log(f"{actor.name} tries to share magic, but {ally.name} already knows {spell_name}.")

SHARE_MAGIC = ShareMagicAction()

# Panel buttons, in order. Move and Attack are the default board click.
# Note: CAST_SPELL is handled dynamically by the UI, so it's not directly in PANEL_ACTIONS.
PANEL_ACTIONS = [ATTACK, ATTACK_TONGUE, RELOAD, THROW, DEMORALIZE, PUSH, CLIMB, DROP, JUMP,
                 SWIM, STABILIZE, FIRST_AID, PICK_UP, SHARE_MAGIC, DEFEND, EAT_CORPSE, MOUNT, DISMOUNT, WAKE_UP, FLEE, END]
