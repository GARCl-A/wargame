"""Test trap mechanics in battle: trigger on movement, trigger on push, shield AC."""

import random

from tests.helpers import _melee_battle, fixed_d20
from gartok.battle import Battle
from gartok.unit import Unit
from gartok.ground import GroundObject
from gartok.actions import Push


def test_bear_trap_trigger_on_movement():
    """Walking into an enemy bear trap deals damage and stops movement."""
    batt, actor, defender = _melee_battle()

    # place trap one step to the right of actor
    trap_pos = (actor.pos[0] + 1, actor.pos[1] - 1)
    # make sure defender is elsewhere
    defender.pos = (0, 0)
    batt.ground.append(GroundObject.trap(trap_pos, "bear trap", "enemy"))

    hp_before = actor.hp
    actor.ap = 2
    batt.move_unit(actor, trap_pos)

    assert actor.hp < hp_before, "bear trap should deal damage"
    assert actor.moved >= actor.speed, "bear trap should stop movement"
    assert not any(g.pos == trap_pos and g.is_trap for g in batt.ground), \
        "triggered trap should be removed from the board"


def test_alarm_trap_trigger_on_movement():
    """Walking into an alarm trap penalises movement but does no damage."""
    batt, actor, defender = _melee_battle()
    trap_pos = (actor.pos[0] + 1, actor.pos[1] - 1)
    defender.pos = (0, 0)
    batt.ground.append(GroundObject.trap(trap_pos, "alarm trap", "enemy"))

    hp_before = actor.hp
    actor.ap = 2
    batt.move_unit(actor, trap_pos)

    assert actor.hp == hp_before, "alarm trap should not deal damage"
    assert not any(g.pos == trap_pos and g.is_trap for g in batt.ground), \
        "triggered alarm trap should be removed"


def test_bear_trap_trigger_on_push():
    """Pushing a unit onto a bear trap triggers it."""
    batt, actor, defender = _melee_battle()
    # actor at (5,5), defender at (6,5); push direction is +x
    push_dest = (7, 5)
    batt.ground.append(GroundObject.trap(push_dest, "bear trap", "player"))
    hp_before = defender.hp

    with fixed_d20(20):  # guarantee push success
        actor.ap = 2
        Push().execute(batt, actor, defender)

    assert defender.pos == push_dest, "defender should have been pushed"
    assert defender.hp < hp_before, "bear trap should have dealt damage on push"
    assert not any(g.pos == push_dest and g.is_trap for g in batt.ground)


def test_friendly_trap_does_not_trigger():
    """A unit walking onto its own team's trap should not trigger it."""
    batt, actor, defender = _melee_battle()
    trap_pos = (actor.pos[0] + 1, actor.pos[1] - 1)
    defender.pos = (0, 0)
    batt.ground.append(GroundObject.trap(trap_pos, "bear trap", "player"))

    hp_before = actor.hp
    actor.ap = 2
    batt.move_unit(actor, trap_pos)

    assert actor.hp == hp_before, "friendly trap should not trigger"
    assert any(g.pos == trap_pos and g.is_trap for g in batt.ground), \
        "friendly trap should stay on the board"


def test_dwarf_shield_ac():
    u = Unit("player")
    u.equipped_offhand = None
    u._derive_combat()
    base_ac = u.ac

    u.equipped_offhand = "Dwarf Shield"
    u._derive_combat()

    # Dwarf Shield gives +2 AC
    assert u.ac == base_ac + 2
