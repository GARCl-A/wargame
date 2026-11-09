"""Fly up / Fly down: a flier hovers above the floor, paying for it out of its walk."""

import pytest

from gartok import ai
from gartok.actions.movement import MAX_ALTITUDE
from gartok.conditions import Entangled, PixieFlight, Prone
from tests.helpers import Battle, actions, data, fitted, standard_unit


def _sprite(team="player", kit=("Quarterstaff", None)):
    u = standard_unit(team)
    u.set_race("Sprite")
    u.set_kit(fitted(u, kit[0]), kit[1])
    u._derive_combat()
    return u


def _arena(sprite, foe, gap=1, extra=()):
    batt = Battle([sprite, *extra], [foe])
    batt.board.walls.clear()
    batt.ambient_light = True
    s, f = batt.player_units[0], batt.enemy_units[0]
    s.pos, f.pos = (5, 5), (5 + gap, 5)
    s.ap = f.ap = 3
    batt.clear_pf_cache()
    return batt, s, f


def test_only_a_flier_can_fly_up():
    batt, h, _f = _arena(standard_unit("player"), standard_unit("enemy"), gap=4)
    assert not h.flies
    assert not actions.FLY_UP.available(batt, h)


def test_fly_up_opens_a_walk_and_costs_double_the_squares():
    batt, s, _f = _arena(_sprite(), standard_unit("enemy"), gap=4)
    s.speed = 6
    actions.FLY_UP.execute(batt, s)
    assert s.altitude == 1 and s.ap == 2 and s.walking
    assert batt.walk_left(s) == 4
    actions.FLY_UP.execute(batt, s)
    assert s.altitude == 2 and s.ap == 2                       # the second level rides the same walk


def test_a_sprites_walk_of_three_buys_one_level_a_point():
    batt, s, _f = _arena(_sprite(), standard_unit("enemy"), gap=4)
    assert s.speed == 3
    actions.FLY_UP.execute(batt, s)
    assert s.altitude == 1 and s.ap == 2
    actions.FLY_UP.execute(batt, s)                            # one square is left: not enough, a new walk
    assert s.altitude == 2 and s.ap == 1


def test_a_walk_that_fits_two_levels_charges_one_point():
    batt, s, _f = _arena(_sprite(), standard_unit("enemy"), gap=4)
    s.speed = 4
    actions.FLY_UP.execute(batt, s)
    actions.FLY_UP.execute(batt, s)
    assert s.altitude == 2 and s.ap == 2 and not s.walking
    actions.FLY_UP.execute(batt, s)                            # another point buys another walk
    assert s.altitude == 3 and s.ap == 1


def test_no_points_no_rising():
    batt, s, _f = _arena(_sprite(), standard_unit("enemy"), gap=4)
    s.ap = 0
    assert not actions.FLY_UP.available(batt, s)


def test_the_ceiling():
    batt, s, _f = _arena(_sprite(), standard_unit("enemy"), gap=4)
    s.speed = 20
    for _ in range(MAX_ALTITUDE + 2):
        actions.FLY_UP.execute(batt, s)
    assert s.altitude == MAX_ALTITUDE


def test_fly_down_costs_one_square_a_level_and_needs_height():
    batt, s, _f = _arena(_sprite(), standard_unit("enemy"), gap=4)
    assert not actions.FLY_DOWN.available(batt, s)
    s.altitude = 2
    actions.FLY_DOWN.execute(batt, s)
    assert s.altitude == 1 and batt.walk_left(s) == s.speed - 1
    actions.FLY_DOWN.execute(batt, s)
    assert s.altitude == 0


@pytest.mark.parametrize("cond", [Prone, Entangled])
def test_a_pinned_flier_cannot_rise(cond):
    batt, s, _f = _arena(_sprite(), standard_unit("enemy"), gap=4)
    s.add_condition(cond())
    assert not actions.FLY_UP.available(batt, s)


def test_two_levels_up_is_out_of_melee_reach():
    batt, s, f = _arena(_sprite(), standard_unit("enemy"))
    assert actions.ATTACK.can(batt, f, s)
    s.altitude = 1
    assert actions.ATTACK.can(batt, f, s)                      # a one-level lip is still reachable
    s.altitude = 2
    assert not actions.ATTACK.can(batt, f, s)
    assert not actions.ATTACK.can(batt, s, f)                  # and it cannot reach down either


def test_a_shot_still_finds_the_flier_overhead():
    archer = standard_unit("enemy")
    archer.set_kit("Shortbow", data.AMMO_ITEM)
    batt, s, f = _arena(_sprite(), archer, gap=3)
    s.altitude = 3
    assert actions.ATTACK.can(batt, f, s)


def test_the_panel_shows_the_wings_to_a_flier_only():
    batt, s, f = _arena(_sprite(), standard_unit("enemy"), gap=4)

    def shown(unit):
        return {e["action"].id for e in actions.panel(batt, unit, "utility", True)}

    assert "fly_up" in shown(s) and "fly_down" not in shown(s)
    assert "fly_up" not in shown(f)


def test_the_dust_wearing_off_drops_a_borrowed_flier():
    friend = standard_unit("player")
    batt, _s, _f = _arena(_sprite(), standard_unit("enemy"), gap=6, extra=(friend,))
    ally = batt.player_units[1]
    ally.add_condition(PixieFlight())
    ally.altitude = 3
    batt.land_fliers()
    assert ally.altitude == 3                                  # still flying: stays up
    ally.conditions.clear()
    hp = ally.hp
    batt.land_fliers()
    assert ally.altitude == 0 and ally.hp < hp                 # 3 levels: 2d6 after the free one


def test_a_downed_flier_floats_down_unhurt():
    batt, s, _f = _arena(_sprite(), standard_unit("enemy"), gap=4)
    s.altitude = 3
    s.take_damage(s.hp + 5, batt.log)
    hp = s.hp
    batt.land_fliers()
    assert s.altitude == 0 and s.hp == hp


def test_a_shooter_with_wings_rises_when_a_fighter_closes_in():
    batt, s, _f = _arena(_sprite(kit=("Shortbow", data.AMMO_ITEM)), standard_unit("enemy"), gap=4)
    ai.take_turn(batt, s)
    assert s.altitude == 2                                     # a quarterstaff's reach is 1: two levels clear it


def test_a_shooter_stays_down_when_nobody_is_closing_in():
    batt, s, _f = _arena(_sprite(kit=("Shortbow", data.AMMO_ITEM)), standard_unit("enemy"), gap=15)
    ai.take_turn(batt, s)
    assert s.altitude == 0


def test_a_fighter_with_wings_comes_down_to_swing():
    batt, s, f = _arena(_sprite(), standard_unit("enemy"), gap=1)
    s.altitude = 3
    ai.take_turn(batt, s)
    assert s.altitude < 2 or batt.height(s) - batt.height(f) <= 1


def test_a_glaive_reaches_one_level_higher_than_a_sword():
    batt, s, f = _arena(_sprite(), standard_unit("enemy"), gap=1)
    f.char.set_kit("Glaive", None)
    f.reset_battle_state()
    f.pos, f.ap = (6, 5), 3
    assert f.attack_range == 2
    s.altitude = 2
    assert actions.ATTACK.can(batt, f, s)
    s.altitude = 3
    assert not actions.ATTACK.can(batt, f, s)


def test_distance_has_three_axes():
    batt, s, f = _arena(_sprite(), standard_unit("enemy"), gap=4)
    assert batt.units_distance(s, f) == 4
    s.altitude = 2
    assert batt.units_distance(s, f) == 4 + 1                  # the height counts half, like the short leg of a diagonal
    s.altitude = 4
    assert batt.units_distance(s, f) == 4 + 2
    f.pos = (5, 5 + 2)                                        # four up and two aside: the long axis whole, one more for the half
    s.pos = (5, 5)
    assert batt.units_distance(s, f) == 5


def test_a_bow_loses_range_to_height():
    archer = standard_unit("enemy")
    archer.set_kit("Shortbow", data.AMMO_ITEM)
    batt, s, f = _arena(_sprite(), archer, gap=3)
    s.altitude = 1
    reach = f.attack_range
    s.pos = (f.pos[0] - reach, f.pos[1])
    assert actions.ATTACK.can(batt, f, s)
    s.altitude = 4                                            # the same flat range, but four levels up
    assert batt.units_distance(s, f) > reach and not actions.ATTACK.can(batt, f, s)


def test_a_shooter_rises_past_the_glaive_that_is_closing_in():
    foe = standard_unit("enemy")
    foe.set_kit("Glaive", None)
    batt, s, _f = _arena(_sprite(kit=("Shortbow", data.AMMO_ITEM)), foe, gap=4)
    s.speed = 6
    ai.take_turn(batt, s)
    assert s.altitude == 3


def test_a_large_body_reaches_a_level_higher():
    centaur = standard_unit("enemy")
    centaur.set_race("Centaur")
    centaur.set_kit("Quarterstaff", None)
    centaur._derive_combat()
    batt, s, f = _arena(_sprite(), centaur)
    assert f.footprint == 2 and f.attack_range == 1
    s.altitude = 2
    assert actions.ATTACK.can(batt, f, s)                      # the same sword in a smaller hand falls short
    s.altitude = 3
    assert not actions.ATTACK.can(batt, f, s)


@pytest.mark.parametrize("cond", [Prone, Entangled])
def test_what_pins_a_flier_pulls_it_to_the_ground(cond):
    batt, s, _f = _arena(_sprite(), standard_unit("enemy"), gap=4)
    s.altitude = 3
    s.add_condition(cond())
    assert s.altitude == 0
    hp = s.hp
    batt.land_fliers()
    assert s.hp == hp                                          # dragged down, not dropped


def test_roots_and_a_grip_pull_a_flier_down_and_keep_it_there():
    from gartok.conditions import Grappled, Rooted
    batt, s, f = _arena(_sprite(), standard_unit("enemy"), gap=4)
    s.altitude = 2
    s.add_condition(Rooted())
    assert s.altitude == 0 and not actions.FLY_UP.available(batt, s)
    s.conditions.clear()
    s.altitude = 2
    g = Grappled()
    g.grappler = f
    s.add_condition(g)
    assert s.altitude == 0 and not actions.FLY_UP.available(batt, s)


def test_with_two_points_a_shooter_spends_the_turn_getting_out_of_reach():
    batt, s, _f = _arena(_sprite(kit=("Shortbow", data.AMMO_ITEM)), standard_unit("enemy"), gap=4)
    s.ap = 2
    ai.take_turn(batt, s)
    assert s.altitude == 2


def test_a_large_target_is_taller_to_reach_too():
    centaur = standard_unit("player")
    centaur.set_race("Centaur")
    centaur.set_kit("Quarterstaff", None)
    centaur._derive_combat()
    batt, c, f = _arena(centaur, standard_unit("enemy"))
    f.altitude = 2
    assert f.footprint == 1 and actions.ATTACK.can(batt, f, c)    # the centaur fills levels 0-1: one below
    f.altitude = 3
    assert not actions.ATTACK.can(batt, f, c)


def test_the_log_says_when_a_flier_is_dragged_down():
    from gartok.conditions import Rooted
    batt, s, f = _arena(_sprite(), standard_unit("enemy"), gap=2)
    s.altitude = 1
    s.add_condition(Rooted())
    actions.DEFEND.execute(batt, f)                              # any action closes with the check
    assert any("dragged down" in str(line) for line in batt.log_lines)


def test_a_sword_reaches_up_a_diagonal_one_level():
    batt, s, f = _arena(_sprite(), standard_unit("enemy"))
    s.pos, f.pos = (5, 5), (6, 6)
    s.altitude = 1
    assert batt.units_distance(f, s) == 1 and actions.ATTACK.can(batt, f, s)
    s.altitude = 2
    assert not actions.ATTACK.can(batt, f, s)
