"""Test trap mechanics in battle: trigger on movement, trigger on push, shield AC."""


from gartok.actions import Push
from gartok.ground import GroundObject
from gartok.unit import Unit
from tests.helpers import _melee_battle, fixed_d20


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


def test_traps_are_neutral_and_spring_on_whoever_steps_on_them():
    """Whoever planted it, a trap hurts the first unit to step on it."""
    batt, actor, defender = _melee_battle()
    trap_pos = (actor.pos[0] + 1, actor.pos[1] - 1)
    defender.pos = (0, 0)
    batt.ground.append(GroundObject.trap(trap_pos, "bear trap", "player"))

    hp_before = actor.hp
    actor.ap = 2
    batt.move_unit(actor, trap_pos)

    assert actor.hp < hp_before, "a trap springs whatever team planted it"
    assert not any(g.pos == trap_pos and g.is_trap for g in batt.ground)


def test_dwarf_shield_ac():
    u = Unit("player")
    u.strength = 14
    u.equipped_offhand = None
    u._derive_combat()
    base_ac = u.ac

    u.equipped_offhand = "Dwarf Shield"
    u._derive_combat()

    # Dwarf Shield gives +2 AC
    assert u.ac == base_ac + 2


def test_battle_screen_draws_traps():
    import pygame
    pygame.font.init()
    from gartok.battle_screen import BattleScreen
    from gartok.ui.tokens import fonts as ui_fonts
    batt, actor, defender = _melee_battle()
    batt.ground.append(GroundObject.trap((1, 1), "bear trap", "enemy"))
    batt.ground.append(GroundObject.trap((2, 2), "alarm trap", "player"))
    batt.ground.append(GroundObject.trap((3, 3), "unknown trap", "enemy"))
    bs = BattleScreen(ui_fonts(), batt, lambda w: None)
    bs._visible = {(1, 1), (2, 2), (3, 3)}
    surf = pygame.Surface((1024, 768))
    bs._draw_ground(surf)

