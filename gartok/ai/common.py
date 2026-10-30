"""Small helpers the other `ai` modules share."""

from .. import actions, data
from ..board import grid_distance


def _avg_die(nf):
    n, faces = nf
    return n * (faces + 1) / 2


def _hand_die(unit):
    """Average damage die of the unit's hand attack (a real swing, an improvised
    club, or bare fists)."""
    if unit.unarmed or unit.improvised:
        return _avg_die(unit.unarmed_damage)
    return _avg_die(unit.weapon["damage"])


def _other_side(team):
    return "enemy" if team == "player" else "player"


def _runs_flag(battle, target):
    """`target` carries a flag, or stands a walk from the flag of the other side (it can scoop it
    up this turn): what the foes see of a runner, not the runner tag of its own side."""
    if not battle.is_ctf:
        return False
    if target in battle.flag_carrier.values():
        return True
    theirs = _other_side(target.team)
    flag = (battle.flags or {}).get(theirs)
    return flag is not None and battle.flag_carrier.get(theirs) is None and min(
        grid_distance(c, flag) for c in battle.cells_of(target)) <= target.speed


def _axes(unit):
    """(order, morality) of the unit's tendency, each in {-1, 0, 1}."""
    return data.alignment_axes(unit.alignment)


def _wants_alive(battle, unit, target):
    """The player's side pulls its blows on a foe it means to capture (`Battle.wanted_alive`);
    the enemy side never captures."""
    return unit.team == "player" and target in battle.wanted_alive


def _spell_can(battle, unit, spell_id, target):
    return (spell_id in getattr(unit, "spells_known", [])
            and actions.CastSpellAction(spell_id).can(battle, unit, target))


def _mindless(unit):
    """The dead do not break and run: an undead body, or one raised from the dead."""
    return getattr(unit, "raised", False) or unit.race.get("kind") == "undead"
