"""Delay: the active unit drops to the end of the initiative order."""

import random

from gartok import ai
from tests.helpers import Battle, Unit, actions


def _trio():
    random.seed(3)
    batt = Battle([Unit("player"), Unit("player")], [Unit("enemy")])
    a, b, e = batt.units
    batt.order = [a, b, e]
    batt.turn_idx = 0
    a.pos, b.pos, e.pos = (2, 5), (2, 7), (12, 5)
    return batt, a, b, e


def test_delay_moves_unit_to_end_and_passes_turn():
    batt, a, b, e = _trio()
    assert actions.DELAY.available(batt, a)
    actions.DELAY.execute(batt, a)
    assert batt.order == [b, e, a]
    assert batt.active is b


def test_delayed_unit_resumes_with_full_ap_without_a_second_start_turn():
    batt, a, b, e = _trio()
    calls = []
    orig = a.start_turn
    a.start_turn = lambda log: (calls.append(1), orig(log))
    actions.DELAY.execute(batt, a)
    batt.end_turn()
    batt.end_turn()
    assert batt.active is a and a.ap == 2 and not a.delayed
    assert calls == []


def test_delay_unavailable_once_a_point_is_spent_or_unit_moved():
    batt, a, b, e = _trio()
    a.ap = 1
    assert not actions.DELAY.available(batt, a)
    a.ap, a.moved = 2, 1
    assert not actions.DELAY.available(batt, a)


def test_delay_unavailable_for_last_unit_and_for_inactive():
    batt, a, b, e = _trio()
    assert not actions.DELAY.available(batt, b)
    batt.turn_idx = 2
    assert not actions.DELAY.available(batt, e)


def test_delay_unavailable_when_everyone_after_is_down():
    batt, a, b, e = _trio()
    b.status = e.status = "dead"
    assert not actions.DELAY.available(batt, a)


def test_delayed_unit_cannot_delay_again_on_its_resumed_turn():
    batt, a, b, e = _trio()
    actions.DELAY.execute(batt, a)
    batt.end_turn()
    batt.end_turn()
    assert not actions.DELAY.available(batt, a)


def test_delay_is_once_per_round():
    batt, a, b, e = _trio()
    actions.DELAY.execute(batt, a)
    actions.DELAY.execute(batt, b)
    actions.DELAY.execute(batt, e)                       # the order is back to a, b, e
    assert batt.order == [a, b, e] and batt.active is a and batt.round_no == 1
    ok, why = actions.DELAY.applicable(batt, a)
    assert not ok and why == "already delayed this round"
    batt.end_turn()
    assert not actions.DELAY.available(batt, b)          # b delayed this round too


def test_delay_is_back_in_the_next_round():
    batt, a, b, e = _trio()
    actions.DELAY.execute(batt, a)
    for _ in range(3):
        batt.end_turn()
    assert batt.round_no == 2 and batt.active is b
    assert actions.DELAY.available(batt, b)
    actions.DELAY.execute(batt, b)
    assert batt.order == [e, a, b] and batt.active is e


def test_ai_does_not_delay_twice_in_a_round():
    batt, a, b, e = _trio()
    a.pos, b.pos, e.pos = (1, 1), (11, 5), (12, 5)
    a.delay_round = batt.round_no
    ai.take_turn(batt, a)
    assert batt.order == [a, b, e]


def test_delay_keeps_the_new_order_next_round():
    batt, a, b, e = _trio()
    actions.DELAY.execute(batt, a)
    for _ in range(3):
        batt.end_turn()
    assert batt.round_no == 2 and batt.active is b


def test_ai_waits_for_an_engaged_ally_then_acts_after_it():
    batt, a, b, e = _trio()
    a.pos, b.pos, e.pos = (1, 1), (11, 5), (12, 5)
    ai.take_turn(batt, a)
    assert batt.order == [b, e, a] and a.ap == 2


def test_ai_does_not_delay_when_it_can_reach_a_foe():
    batt, a, b, e = _trio()
    a.pos, b.pos, e.pos = (10, 5), (11, 5), (12, 5)
    ai.take_turn(batt, a)
    assert batt.order == [a, b, e]


def test_ai_does_not_delay_without_an_engaged_ally():
    batt, a, b, e = _trio()
    a.pos, b.pos, e.pos = (1, 1), (1, 3), (14, 10)
    ai.take_turn(batt, a)
    assert batt.order == [a, b, e]


def test_unit_downed_while_waiting_starts_its_next_turn_fresh():
    batt, a, b, e = _trio()
    actions.DELAY.execute(batt, a)
    a.status = "dying"
    batt.end_turn()
    batt.end_turn()
    assert not a.delayed
