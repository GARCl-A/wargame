"""AI racial talent behaviors: Corpse Eater (Gnoll) and Centaur Mount."""

from unittest.mock import patch

from tests.helpers import Battle, Combatant, Unit, data
from gartok import actions, ai


def _gnoll():
    u = Unit("enemy", race=data.race_by_name("Gnoll"))
    u.set_track_level("racial", 5)
    assert u.choose_talent("racial", "corpse_eater")
    return u


def _centaur():
    u = Unit("enemy", race=data.race_by_name("Centaur"))
    u.set_track_level("racial", 5)
    assert u.choose_talent("racial", "centaur_mount")
    return u


def _rider_unit(team="enemy"):
    import random
    random.seed(1)
    u = Unit(team)
    u.size = "Medium"
    return u


# --------------------------------------------------------------------------- #
# Corpse Eater                                                                #
# --------------------------------------------------------------------------- #

def test_gnoll_ai_eats_adjacent_dead_enemy():
    gnoll = _gnoll()
    player = Unit("player")
    player.hp = 5

    batt = Battle([player], [gnoll])
    g_c, p_c = batt.enemy_units[0], batt.player_units[0]
    g_c.pos, p_c.pos = (5, 5), (5, 6)

    p_c.status = "dead"
    gnoll.unfed_days = 3

    with patch("gartok.actions.d20", return_value=15):
        ai.take_turn(batt, g_c)

    assert any("devours" in line for line in batt.log_lines)
    assert gnoll.unfed_days == 0


def test_gnoll_ai_does_not_eat_without_talent():
    import random
    random.seed(0)
    gnoll = Unit("enemy", race=data.race_by_name("Gnoll"))
    player = Unit("player")

    batt = Battle([player], [gnoll])
    g_c, p_c = batt.enemy_units[0], batt.player_units[0]
    g_c.pos, p_c.pos = (5, 5), (5, 6)
    p_c.status = "dead"

    with patch("gartok.actions.d20", return_value=15):
        ai.take_turn(batt, g_c)

    assert not any("devours" in line for line in batt.log_lines)


def test_gnoll_ai_does_not_eat_a_corpse_that_is_not_adjacent():
    gnoll = _gnoll()
    player = Unit("player")

    batt = Battle([player], [gnoll])
    g_c, p_c = batt.enemy_units[0], batt.player_units[0]
    g_c.pos, p_c.pos = (1, 1), (8, 8)
    p_c.status = "dead"

    with patch("gartok.actions.d20", return_value=15):
        ai.take_turn(batt, g_c)

    assert not any("devours" in line for line in batt.log_lines)


# --------------------------------------------------------------------------- #
# Centaur Mount                                                               #
# --------------------------------------------------------------------------- #

def test_ai_rider_mounts_adjacent_centaur_ally():
    centaur = _centaur()
    rider_unit = _rider_unit(team="enemy")

    batt = Battle([Unit("player")], [centaur, rider_unit])
    c_c = batt.enemy_units[0]
    r_c = batt.enemy_units[1]

    c_c.pos = (5, 5)
    r_c.pos = (5, 6)
    batt.player_units[0].pos = (1, 1)

    with patch("gartok.actions.d20", return_value=10):
        ai.take_turn(batt, r_c)

    assert r_c.mounted_on is c_c
    assert c_c.rider is r_c


def test_ai_does_not_mount_without_centaur_talent():
    import random
    random.seed(0)
    mount_unit = Unit("enemy")
    rider_unit = _rider_unit(team="enemy")

    batt = Battle([Unit("player")], [mount_unit, rider_unit])
    m_c = batt.enemy_units[0]
    r_c = batt.enemy_units[1]
    m_c.pos, r_c.pos = (5, 5), (5, 6)
    batt.player_units[0].pos = (1, 1)

    with patch("gartok.actions.d20", return_value=10):
        ai.take_turn(batt, r_c)

    assert r_c.mounted_on is None
