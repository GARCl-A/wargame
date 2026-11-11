"""Pits and the Z axis: falling, climbing, pushing, jumping."""

import random

from tests.helpers import Battle, Unit, abilities, actions, data, duelists, fixed_d20


def _set_stats(combatant, **scores):
    """Force raw attribute scores on the wrapped character and re-derive."""
    for k, v in scores.items():
        setattr(combatant.char, k, v)
    combatant.char._derive_combat()


def _pit_battle(depth=2, rope=False):
    random.seed(3)
    side_a, side_d = duelists()
    batt = Battle([side_a], [side_d])
    batt.ambient_light = True
    a, d = batt.units
    a._ability = d._ability = abilities.get("none")
    a.pos, d.pos = (5, 5), (6, 5)
    a.weapon_hand, a.torch_hand = True, False
    batt.board.walls = {w for w in batt.board.walls if w[1] != 5}   # clear the row
    batt.board.elevation = {(6, 5): -depth, (7, 5): -depth} if depth else {}
    batt.board.ropes = {(6, 5)} if rope else set()
    a.ap = d.ap = 2
    return batt, a, d


def test_fall_damage_skips_the_first_level():
    batt, a, _ = _pit_battle()
    batt.apply_fall(a, 1, batt.log)
    assert a.hp == a.hp_max                                              # 1 level: free
    hp = a.hp
    batt.apply_fall(a, 3, batt.log)                                       # 3 levels: 2d6
    assert hp - 12 <= a.hp < hp                                          # 2..12 damage


def test_drop_in_takes_the_fall():
    batt, a, d = _pit_battle(depth=3)
    d.pos = (9, 9)
    assert actions.DROP.can(batt, a, (6, 5))
    hp = a.hp
    actions.DROP.execute(batt, a, (6, 5))
    assert a.pos == (6, 5) and a.hp < hp and a.ap == 1


def test_climb_out_needs_a_strength_check():
    batt, a, d = _pit_battle(depth=2)
    a.pos, d.pos = (6, 5), (9, 9)          # a is in the pit
    _set_stats(a, strength=4)              # STR mod -3
    assert actions.CLIMB.can(batt, a, (5, 5))
    with fixed_d20(10):                          # 10 - 3 = 7, short of DC 15
        actions.CLIMB.execute(batt, a, (5, 5))
    assert a.pos == (6, 5) and a.ap == 1    # slipped, still down there
    a.ap = 2
    with fixed_d20(19):                          # 19 - 3 = 16, clears DC 15
        actions.CLIMB.execute(batt, a, (5, 5))
    assert a.pos == (5, 5)


def _channel_battle(footprint):
    """A 2-wide channel (rows 4-5) flooded from x=8 to x=12, floor at both ends."""
    batt, a, d = _pit_battle(depth=0)
    batt.board.walls = set()
    flooded = {(x, y) for x in range(8, 13) for y in (4, 5)}
    batt.board.elevation = {c: -3 for c in flooded}
    batt.board.water = set(flooded)
    batt.board.deep_water = set(flooded)
    a.footprint = footprint
    d.pos = (18, 15)
    a.ap = 2
    return batt, a


def test_a_large_body_climbs_out_with_all_four_squares_on_dry_ground():
    batt, a = _channel_battle(2)
    a.pos = (11, 4)                                    # afloat: columns 11 and 12 are water
    spots = actions.CLIMB.highlight_cells(batt, a)
    assert (13, 4) in spots and (13, 5) in spots        # two squares on: columns 13 and 14, no water under it
    assert (12, 4) not in spots and (12, 5) not in spots   # never half in the water
    with fixed_d20(20):
        actions.CLIMB.execute(batt, a, (13, 4))
    assert a.pos == (13, 4)
    assert not any(batt.board.is_deep_water(c) for c in batt.cells_of(a))


def test_a_medium_body_still_climbs_to_the_square_beside_it():
    batt, a = _channel_battle(1)
    a.pos = (12, 4)
    assert (13, 4) in actions.CLIMB.highlight_cells(batt, a)
    assert (14, 4) not in actions.CLIMB.highlight_cells(batt, a)


def test_the_ai_odds_of_a_climb_and_a_jump_follow_the_strength_check():
    from gartok import actions as acts
    from gartok.ai.movement import _odds
    batt, a = _channel_battle(2)
    a.pos = (11, 4)
    _set_stats(a, strength=10)                          # STR mod 0
    assert _odds(batt, a, acts.CLIMB, (13, 4)) == 0.30        # d20 >= DC 15, or a natural 20
    assert _odds(batt, a, acts.JUMP, (13, 4)) == 0.55         # 2 squares: d20 >= 10
    assert _odds(batt, a, acts.SWIM, (10, 4)) == 1.0
    a._ability = abilities.get("climber")
    assert _odds(batt, a, acts.CLIMB, (13, 4)) == 1.0


def test_the_ai_takes_the_surer_way_out_when_two_moves_close_the_same_distance():
    from unittest.mock import patch

    from gartok import ai
    batt, a = _channel_battle(2)
    a.pos = (11, 4)
    _set_stats(a, strength=10)
    foe = batt.enemy_units[0]
    foe.pos = (15, 4)
    with patch.object(actions.JUMP, "execute") as jump, patch.object(actions.CLIMB, "execute") as climb:
        assert ai._step_over_terrain(batt, a, foe)
    assert jump.called and not climb.called


def test_rope_lowers_the_climb_dc():
    batt, a, d = _pit_battle(depth=2, rope=True)
    assert batt.board.surface_dc((6, 5)) == 10
    assert batt.board.surface_dc((7, 5)) == 15


def test_lizardfolk_climbs_stone_with_no_check():
    batt, a, d = _pit_battle(depth=2)
    a.pos, d.pos = (6, 5), (9, 9)
    a._ability = abilities.get("climber")
    _set_stats(a, strength=3)               # a roll would never pass
    with fixed_d20(1):
        actions.CLIMB.execute(batt, a, (5, 5))
    assert a.pos == (5, 5)                  # auto-climb (DC 15 <= 25)


def test_melee_cannot_reach_two_levels_down():
    batt, a, d = _pit_battle(depth=2)
    d.pos = (6, 5)                          # one square away but two levels down
    assert actions.ATTACK.can(batt, a, d) is False
    batt.board.elevation = {(6, 5): -1}     # a one-level lip: melee reaches
    assert actions.ATTACK.can(batt, a, d) is True


def test_tongue_lash_reaches_two_squares_and_counts_the_height():
    batt, a, d = _pit_battle(depth=0)
    a.char.talents["racial"] = ["tongue"]
    a.tongue_weapon_name = "Dagger"
    a.tongue_weapon = data.WEAPONS["Dagger"]
    a.pos, d.pos = (5, 5), (7, 5)           # two squares apart, flat ground
    assert actions.ATTACK.can(batt, a, d) is False        # the hand weapon is reach 1
    assert a.tongue_reach == 2 and actions.ATTACK_TONGUE.can(batt, a, d) is True
    batt.board.elevation = {(6, 5): -1, (7, 5): -1}       # a level down: 2 squares + the height still fits
    assert actions.ATTACK_TONGUE.can(batt, a, d) is True
    batt.board.elevation = {(6, 5): -2, (7, 5): -2}       # two levels down: the reach is 3D, 2 + 1 > 2
    assert actions.ATTACK_TONGUE.can(batt, a, d) is False


def test_push_shoves_the_target_back_a_square():
    batt, a, d = _pit_battle(depth=0)
    a.pos, d.pos = (5, 5), (6, 5)
    _set_stats(a, strength=14)              # +2
    _set_stats(d, constitution=10)          # DC 10
    with fixed_d20(3):                           # 3 + 2 = 5, target holds
        actions.PUSH.execute(batt, a, d)
    assert d.pos == (6, 5)
    a.ap = 2
    with fixed_d20(12):                          # 12 + 2 = 14 >= 10, shoved
        actions.PUSH.execute(batt, a, d)
    assert d.pos == (7, 5) and a.ap == 1


def test_push_can_shove_an_ally():
    random.seed(3)
    batt = Battle([Unit("player"), Unit("player")], [Unit("enemy")])
    a, b, e = batt.units
    a._ability = b._ability = e._ability = abilities.get("none")
    a.pos, b.pos, e.pos = (5, 5), (6, 5), (9, 9)
    batt.board.walls = {w for w in batt.board.walls if w[1] != 5}
    a.ap = b.ap = 2
    _set_stats(a, strength=14)              # +2
    _set_stats(b, constitution=10)          # DC 10
    assert actions.PUSH.can(batt, a, b) is True
    with fixed_d20(12):                          # 12 + 2 = 14 >= 10, shoved
        actions.PUSH.execute(batt, a, b)
    assert b.pos == (7, 5) and a.ap == 1


def test_push_cannot_target_self():
    batt, a, d = _pit_battle(depth=0)
    assert actions.PUSH.can(batt, a, a) is False


def test_push_against_a_wall_does_not_move_the_target():
    batt, a, d = _pit_battle(depth=0)
    a.pos, d.pos = (5, 5), (6, 5)
    batt.board.walls = {(7, 5)}
    with fixed_d20(20):                          # roll succeeds, but the wall stops the shove
        actions.PUSH.execute(batt, a, d)
    assert d.pos == (6, 5) and a.ap == 1


def test_push_into_a_pit_makes_the_target_fall():
    batt, a, d = _pit_battle(depth=3)
    a.pos, d.pos = (5, 5), (6, 5)
    batt.board.elevation = {(7, 5): -3}
    hp = d.hp
    with fixed_d20(20):
        actions.PUSH.execute(batt, a, d)
    assert d.pos == (7, 5) and d.hp < hp    # shoved in, took the fall


def test_push_into_a_pit_credits_kill_if_target_dies():
    batt, a, d = _pit_battle(depth=4)
    a.pos, d.pos = (5, 5), (6, 5)
    batt.board.elevation = {(7, 5): -4}
    d.hp = 1                                # fall damage (3d6) will easily down d
    with fixed_d20(20):
        actions.PUSH.execute(batt, a, d)
    assert not d.alive
    assert a.kills == 1
    assert d.downed_by == a



def test_flight_lets_a_unit_move_in_three_dimensions():
    batt, a, d = _pit_battle(depth=2)
    a.pos, d.pos = (5, 5), (9, 9)
    a._ability = abilities.get("flight")
    assert a.can_move_vertically
    assert (6, 5) in batt.reachable(a)             # can fly straight into the pit


def test_jump_clears_squares_by_the_roll():
    batt, a, d = _pit_battle(depth=2)
    a.pos, d.pos = (3, 5), (9, 9)
    _set_stats(a, strength=10)                     # +0: jump distance == roll // 5
    assert actions.JUMP.can(batt, a, (7, 5))
    with fixed_d20(15):                                 # 15 // 5 = 3 squares -> lands at (6, 5)
        actions.JUMP.execute(batt, a, (7, 5))
    assert a.pos == (6, 5) and a.ap == 1
