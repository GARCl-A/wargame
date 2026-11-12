"""The AI leaves a sleeping foe alone while another foe stands awake: any damage wakes it."""

from gartok import ai
from gartok.ai.attack import _demoralize_victim
from gartok.conditions import Sleeping
from tests.helpers import _melee_battle, _recruit, actions, fixed_d20
from tests.test_ai_actions import _duel
from tests.test_magic_track import _breath_battle
from tests.test_racial_track import _sweep_board


def _asleep(unit):
    unit.add_condition(Sleeping())
    return unit


def _pit_duel():
    """The duel board with a deep pit behind the player's unit: a shove the AI takes."""
    batt, e, p = _duel("Club")
    batt.board.elevation = {(7, 5): -4}
    return batt, e, p


def test_the_ai_does_not_shove_a_sleeper_while_another_foe_is_awake(monkeypatch):
    monkeypatch.setattr(ai.reckon, "_shove_odds", lambda unit, foe: 0.9)
    batt, e, p = _pit_duel()
    assert ai._try_shove(batt, e) is not None
    batt, e, p = _pit_duel()
    _asleep(p)
    _recruit(batt, team="player").pos = (9, 9)
    assert ai._try_shove(batt, e) is None


def test_the_ai_does_not_demoralize_a_sleeper_while_another_foe_is_awake():
    batt, a, d = _melee_battle()
    a.pos, d.pos, a.ap = (4, 5), (8, 5), 1
    a.languages = d.languages = ["Ankarin"]
    _recruit(batt, team=d.team).pos = (12, 9)
    assert _demoralize_victim(batt, a, d) is d
    _asleep(d)
    assert _demoralize_victim(batt, a, d) is not d


def test_a_sleeper_does_not_count_toward_a_breath():
    batt, dragon = _breath_battle([(6, 5), (7, 4), (7, 6), (5, 12)])
    assert ai._best_cone(batt, dragon)[1] == 3
    _asleep(batt.player_units[0])
    assert ai._best_cone(batt, dragon) == (None, 0)


def test_of_two_cones_the_ai_breathes_the_one_that_wakes_nobody():
    batt, dragon = _breath_battle([(6, 5), (7, 4), (7, 6), (4, 5), (3, 4), (3, 6), (5, 12)])
    east = set(batt.player_units[:3])
    _asleep(batt.player_units[6])
    batt.player_units[6].pos = (7, 5)
    cell, foes = ai._best_cone(batt, dragon)
    assert foes == 3 and not east & set(actions.DRAGON_BREATH.caught(batt, dragon, cell))


def test_the_ai_does_not_sweep_its_tail_into_a_sleeper():
    batt, l = _sweep_board()
    first, second = batt.enemy_units
    assert ai._pick_attack(batt, l, first) is actions.TAIL_SWEEP
    _asleep(second)
    assert ai._pick_attack(batt, l, first) is not actions.TAIL_SWEEP


def test_the_ai_strikes_a_sleeper_when_it_is_the_only_foe_left():
    batt, e, p = _duel("Club")
    _asleep(p)
    batt.turn_idx = batt.order.index(e)
    with fixed_d20(20):
        ai.take_turn(batt, e)
    assert p.hp < 30 and not p.has_condition("sleeping")
