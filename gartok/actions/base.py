"""The Action base class and the shared combat helpers (flanking, hit resolution)."""

import random

from .. import combat_log, poisons
from ..board import cells


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

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        if "execute" in cls.__dict__:
            cls.execute = combat_log.recorded(lambda self: self.id)(cls.__dict__["execute"])

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
    """Anyone can pick up a torch if the off hand is free; relics and chests can
    always be retrieved; a weapon only if the unit is unarmed and can wield it."""
    if obj.is_torch:
        return not unit.has_torch and not unit.has_lantern
    if getattr(obj, "is_relic", False) or getattr(obj, "is_chest", False):
        return True
    return unit.unarmed and unit.char.can_wield(obj.weapon_name)


def _envenom(battle, attacker, target):
    """A venomous attacker's hit that hurt a standing target: Constitution save or
    one more stack of the venom (it lasts past the fight -- see unit_poison.py)."""
    pid = attacker.ability.venom
    if not pid or not target.alive:
        return
    poison = poisons.get(pid)
    dc = poisons.save_dc(poison, attacker.char)
    ok, nat, total = target.char.poison_save(dc)
    roll = f"CON d20({nat}) {target.char.mod_constitution:+} = {total} vs DC {dc}"
    if ok:
        battle.log(f"  {target.name} shakes off the {poison.name} ({roll}).")
        return
    level = target.char.add_poison(pid, dc)
    battle.log(f"  {target.name} is poisoned: {poison.name} {level} "
               f"(-{level * poison.per_stack} {poison.attribute.capitalize()}) ({roll}).")
    target.check_collapse(battle.log)


def _resolve_hit(battle, attacker, target, nat, bonus, detail, prefix, thrown=False,
                 weapon=None):
    total = nat + bonus
    ac = target.ac_vs(attacker)
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
            battle.log(desc + "  -> a blow on the fallen.")
            battle.tick_dying(target)       # the hit counts as one more turn on the clock
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
        if not thrown and target.team != attacker.team:
            _envenom(battle, attacker, target)
        return "crit" if crit else "hit"
    battle.log(desc + "  -> misses.")
    battle.fx(target.pos, fx_text, "faint")
    return "miss"
