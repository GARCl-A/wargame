"""Helping and using the unit's own kit: allies, mounts, potions, the horn."""

from .. import actions, intel
from ..board import cells, cells_distance
from .common import _axes, _spell_can


def _try_healing_touch(battle, unit):
    """Healing Touch on the most hurt of the unit and the allies in reach, at half health or less."""
    if "healing_touch" not in getattr(unit, "spells_known", []):
        return False
    touch = actions.CastSpellAction("healing_touch")
    hurt = [u for u in touch.highlight_targets(battle, unit) if u.alive and u.hp <= u.hp_max * 0.5]
    if not hurt or not touch.available(battle, unit):
        return False
    touch.execute(battle, unit, min(hurt, key=lambda u: u.hp / u.hp_max))
    return True


def _try_lift_rider(battle, unit):
    """A Centaur with Lift Rider takes a dying ally beside it onto its back, out from under the
    blows that would finish it, and carries it on."""
    lift = actions.LIFT_RIDER
    if not lift.available(battle, unit):
        return False
    fallen = [u for u in lift.highlight_targets(battle, unit) if u.dying]
    if not fallen:
        return False
    lift.execute(battle, unit, max(fallen, key=lambda u: u.death_clock))
    return True


def _try_pixie_dust(battle, unit):
    """A Sprite gives wings to an ally beside it whose way to the foes is cut by water or a pit."""
    dust = actions.PIXIE_DUST
    if not dust.available(battle, unit):
        return False
    for ally in dust.highlight_targets(battle, unit):
        if ally.has_condition("entangled") or ally.has_condition("grappled"):
            continue
        foes = [f for f in battle.units if f.alive and f.team != ally.team and battle.can_see_unit(ally, f)]
        if not foes or any(battle.units_distance(ally, f) <= ally.attack_range for f in foes):
            continue
        walk = battle.reachable(ally, budget=WHOLE_BOARD)
        if not any(cells_distance(cells(p, ally.footprint), battle.cells_of(f)) <= ally.attack_range
                   for f in foes for p in walk):
            dust.execute(battle, unit, ally)
            return True
    return False


WHOLE_BOARD = 10 ** 6       # a movement budget no walk runs out of


def _try_mount(battle, unit):
    """Mount an adjacent allied Centaur (centaur_mount talent) if one is available
    and the unit is not already riding. Returns True if acted."""
    if not actions.MOUNT.available(battle, unit):
        return False
    if any(actions.ATTACK.can(battle, unit, f) for f in battle.units if f.team != unit.team and f.alive):
        return False                      # a foe in reach: fight on foot rather than climb up
    targets = actions.MOUNT.highlight_targets(battle, unit)
    if not targets:
        return False
    actions.MOUNT.execute(battle, unit, targets[0])
    return True


def _try_signal_horn(battle, unit):
    """Blow the Signal Horn while the fight is still a walk away: it takes the whole turn,
    so only when nobody is in reach to hit and at least two allies hear it."""
    horn = actions.SIGNAL_HORN
    if not horn.available(battle, unit):
        return False
    foes = intel.visible_foes(battle, unit)
    if not foes or any(battle.units_distance(unit, f) <= unit.speed + 1 for f in foes):
        return False
    if len(horn.allies_in_range(battle, unit)) < 2:
        return False
    horn.execute(battle, unit)
    return True


def _try_drink_potion(battle, unit):
    if unit.hp <= unit.hp_max * 0.5:
        if actions.DRINK_POTION.can(battle, unit, unit):
            actions.DRINK_POTION.execute(battle, unit, unit)
            return True
    return False


def _try_share_magic(battle, unit):
    """Sprite Nature Initiate: share a known spell with an ally who lacks it."""
    if not actions.SHARE_MAGIC.available(battle, unit):
        return False
    allies = [u for u in battle.units if u.alive and u.team == unit.team and u != unit]
    needy = [u for u in allies if any(s not in getattr(u, "spells_known", []) for s in unit.spells_known)]
    if not needy:
        return False
    enemies = [u for u in battle.units if u.alive and u.team != unit.team]
    in_melee = any(battle.units_distance(unit, e) <= 1 for e in enemies)
    if in_melee and unit.ap < 2:
        return False
    actions.SHARE_MAGIC.execute(battle, unit)
    return True


def _ally_to_help(battle, unit):
    """A downed ally this unit wants to stabilize -- only if it is of good
    bent (it will spend the action to save a friend before fighting)."""
    if _axes(unit)[1] <= 0:
        return None
    # Prefer an adjacent one if possible
    adj = next((a for a in battle.units
                if actions.FIRST_AID.can(battle, unit, a) or actions.STABILIZE.can(battle, unit, a)
                or any(_spell_can(battle, unit, sid, a) for sid in ("healing_touch", "spare_the_dying"))), None)
    if adj:
        return adj
    # Else nearest ally still savable -- a stable one is already saved, and
    # walking to it would leave a good unit idling beside it instead of fighting
    bodies = sorted((u for u in battle.units if u.team == unit.team and (u.dying or u.broken)),
                    key=lambda u: battle.units_distance(unit, u))
    return bodies[0] if bodies else None
