"""The Action base class and the shared combat helpers (flanking, hit resolution)."""

import random

from .. import combat_log, intel, poisons
from ..board import cells
from ..data import roll


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


def _breaks_invisibility(execute):
    """An invisible actor that hurts someone on another side is seen from then on."""
    def run(self, battle, actor, target=None, **kw):
        if not actor.has_condition("invisible"):
            return execute(self, battle, actor, target, **kw)
        before = {u: u.hp for u in battle.units if u.team != actor.team}
        result = execute(self, battle, actor, target, **kw)
        if any(u.hp < hp for u, hp in before.items()):
            actor.drop_invisibility(battle.log)
        return result
    run.__name__, run.__doc__ = execute.__name__, execute.__doc__
    return run


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
            cls.execute = combat_log.recorded(lambda self: self.id)(_breaks_invisibility(cls.__dict__["execute"]))

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


def _held_line(battle, target):
    """Hobgoblin Hold the Line: the AC an ally Defending beside `target` lends it."""
    return max((u.char.talent_bonus("hold_the_line") for u in battle.units
                if u.alive and u.team == target.team and u is not target and u.defending
                and battle.units_distance(u, target) <= 1), default=0)


def _hostile_target(actor, target):
    return (target is not None and target.alive and target.team != actor.team
            and not target.hidden_from(actor.team))


def _shovable_target(actor, target):
    """Push works on anyone standing, foe or friend -- just not yourself."""
    return target is not None and target.alive and target is not actor


def _attackable_target(actor, target):
    """Attack and Throw may also target a downed enemy body, to finish it off -- not a captive."""
    return (target is not None and not target.dead and target.team != actor.team
            and not getattr(target, "captured", False) and not target.hidden_from(actor.team))


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
    pid = attacker.char.venom
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


NONLETHAL_PENALTY = 1      # to hit, while a character pulls its blows (the Non-lethal toggle)


OBSCURED_PENALTY = 4


def nonlethal_penalty(attacker):
    return NONLETHAL_PENALTY if getattr(attacker, "nonlethal_blows", False) else 0


def obscured_penalty(battle, attacker, target):
    if not (hasattr(battle, "board") and hasattr(target, "pos")):
        return 0
    from .. import vision
    if vision.is_obscured(battle, attacker, target):
        relief = getattr(attacker.char, "talent_bonus", lambda x: 0)("obscured_penalty_relief") if hasattr(attacker, "char") else 0
        return max(0, OBSCURED_PENALTY - relief)
    return 0


def _flank_penalty(battle, attacker, target):
    """Strict flank: the attacker and an ally are both adjacent to the target and
    on opposite sides. Defender suffers -2 AC (reduced to -1 AC if target has
    flank_defense / Peripheral Vision)."""
    if not _flanked(battle, attacker, target):
        return 0
    relief = getattr(target.char, "talent_bonus", lambda x: 0)("flank_defense") if hasattr(target, "char") else 0
    return max(0, 2 - relief)


def _check_gruesome_takedown(battle, attacker, downed_target):
    if not hasattr(attacker, "char") or not attacker.char.has_talent("gruesome_takedown"):
        return
    from ..data import DEMORALIZE_RANGE
    from .combat import execute_demoralize
    foes = [u for u in battle.units if u.alive and u.team != attacker.team and u is not downed_target
            and not u.hidden_from(attacker.team) and battle.units_distance(attacker, u) <= DEMORALIZE_RANGE]
    if not foes:
        return
    foes.sort(key=lambda u: battle.units_distance(attacker, u))
    victim = foes[0]
    battle.log(f"  Gruesome Takedown! {attacker.name} roars at {victim.name}:")
    execute_demoralize(battle, attacker, victim, free=True, ignore_language=True)


def _stone_endurance(battle, target, dmg):
    """Goliath Stone's Endurance: the first blow of the fight that hurts is cut by 1d4 + CON."""
    die = int(target.char.talent_bonus("stone_endurance"))
    if not die or dmg <= target.dr or not target.spend_once("stone_endurance"):
        return dmg
    cut = max(0, roll(1, die) + target.mod_constitution)
    battle.log(f"  {target.name} takes the blow like stone: -{cut} damage [Stone's Endurance].")
    return max(0, dmg - cut)


def _thornskin(battle, attacker, target):
    """Treefolk Thornskin: a melee blow that lands pricks the one who struck it."""
    thorns = int(target.char.talent_bonus("thornskin"))
    if thorns and attacker.alive and attacker.team != target.team:
        battle.log(f"  {attacker.name} is pricked by {target.name}'s thorns.")
        attacker.take_damage(thorns, battle.log)


GORE_RUN_UP = 4     # squares walked this turn before the Ox's blow throws the target


def _gore_charge(battle, attacker, target):
    """Ox Gore Charge: after a run-up, the blow throws the target straight back, no roll."""
    squares = int(attacker.char.talent_bonus("gore_charge"))
    if (not squares or len(attacker.path) - 1 < GORE_RUN_UP or not target.alive
            or target.team == attacker.team or battle.units_distance(attacker, target) > 1):
        return
    from .combat import Push
    if Push.direction(attacker, target) == (0, 0):
        return
    path, _ = Push.landing(battle, attacker, target, squares=squares)
    if path:
        battle.log(f"  {attacker.name} gores {target.name} and throws them to {path[-1]}!")
        Push.throw(battle, attacker, target, path)


def _resolve_hit(battle, attacker, target, nat, bonus, detail, prefix, thrown=False,
                 weapon=None, armor_pierce=False, bonus_damage=0, crit_mult=None):
    pulled = nonlethal_penalty(attacker)
    if pulled:
        bonus -= pulled
        detail += f" -{pulled}(non-lethal)"
    obscured = obscured_penalty(battle, attacker, target)
    if obscured:
        bonus -= obscured
        detail += f" -{obscured}(obscured)"
    total = nat + bonus
    melee = not thrown and (weapon is not None or not attacker.ranged)
    ac = target.ac_vs(attacker, armor_pierce=armor_pierce, ranged=not melee)
    flank_pen = _flank_penalty(battle, attacker, target)
    if flank_pen:
        ac -= flank_pen
    phalanx = _phalanxed(battle, target)
    if phalanx:
        ac += 1
    ac += _held_line(battle, target)
    w = weapon if weapon is not None else attacker.weapon
    if hasattr(w, "crit_range"):
        crit_range = w.crit_range
    elif isinstance(w, dict):
        crit_range = w.get("crit_range", 20)
    else:
        crit_range = 20
    if hasattr(attacker, "char") and intel.has_full_intel(battle, attacker.team, target):
        crit_relief = getattr(attacker.char, "talent_bonus", lambda x: 0)("full_intel_crit_range")
        crit_range = max(2, crit_range - crit_relief)
    crit = nat >= crit_range
    shown = intel.shown(battle, target, "ac", ac)
    flank_tag = f" [Flank -{flank_pen}]" if flank_pen else ""
    phalanx_tag = " [Phalanx]" if phalanx and shown != "?" else ""
    desc = f"{prefix}: d20({nat}) {detail} = {total} vs AC {shown}{flank_tag}{phalanx_tag}"
    fx_text = f"{total} vs AC {shown}"
    if nat == 1:
        battle.log(desc + "  -> critical miss.")
        battle.fx(target.pos, "Crit Miss!", "faint")
        battle.cue("miss", target.pos)
        return "miss"
    if crit or total >= ac:
        battle.fx(target.pos, fx_text, "ok" if not crit else "crit")
        if crit:
            battle.cue("crit", target.pos)
        if target.dying:
            if pulled:
                battle.log(desc + "  -> the blow is pulled; the fallen is spared.")
                return "crit" if crit else "hit"
            battle.log(desc + "  -> a blow on the fallen.")
            battle.tick_dying(target)       # the hit counts as one more turn on the clock
            return "crit" if crit else "hit"
        battle.log(desc + ("  -> CRITICAL HIT!" if crit else "  -> hit."))
        was_up = target.alive
        cull = 0
        if getattr(target, "demoralized", False) and hasattr(attacker, "char"):
            cull = getattr(attacker.char, "talent_bonus", lambda x: 0)("demoralized_target_damage")
        flank_finesse = 0
        if _flanked(battle, attacker, target) and getattr(attacker, "is_dex_melee", False) and not thrown and hasattr(attacker, "char"):
            flank_finesse = getattr(attacker.char, "talent_bonus", lambda x: 0)("flank_finesse_damage")
        frenzy = attacker.char.talent_bonus("blood_frenzy") if melee and target.hp < target.hp_max / 2 else 0
        dmg = attacker.damage_roll(crit=crit, thrown=thrown, weapon=weapon, crit_mult=crit_mult,
                                   bonus_damage=bonus_damage + cull + flank_finesse + frenzy)
        dmg = _stone_endurance(battle, target, dmg)
        target.take_damage(dmg, battle.log, knockout=bool(pulled))
        if dmg > 0:
            target.hurt_by.add(attacker)
        if melee:
            _thornskin(battle, attacker, target)
            _gore_charge(battle, attacker, target)
        if was_up and target.team != attacker.team:
            if not target.alive:
                attacker.credit_kill(target)
            elif target.hp <= 0 and target.ferocity_downer is None:
                target.ferocity_downer = attacker
            if not target.alive or target.hp <= 0:
                _check_gruesome_takedown(battle, attacker, target)
        if not thrown and target.team != attacker.team:
            _envenom(battle, attacker, target)
        return "crit" if crit else "hit"
    battle.log(desc + "  -> misses.")
    battle.fx(target.pos, fx_text, "faint")
    battle.cue("miss", target.pos)
    return "miss"
