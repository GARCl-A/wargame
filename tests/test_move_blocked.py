"""A Move that is off always says why: the battle state carries the line the hint shows."""

import pytest

from gartok import actions, i18n
from gartok.conditions import Entangled, Grappled, Prone
from tests.helpers import _melee_battle


def _why(batt, a):
    return actions.MOVE.blocked_reason(batt, a)


def test_a_unit_that_can_walk_has_no_reason():
    batt, a, _ = _melee_battle()
    a.ap = 2
    assert actions.MOVE.available(batt, a) and _why(batt, a) == ""


@pytest.mark.parametrize("cond, key", [(Entangled, "entangled"), (Grappled, "grappled"), (Prone, "prone")])
def test_a_condition_that_pins_names_itself(cond, key):
    batt, a, _ = _melee_battle()
    a.ap = 2
    a.add_condition(cond())
    assert not actions.MOVE.available(batt, a)
    assert _why(batt, a) == i18n.t(f"action.move_blocked.{key}")


def test_no_action_point_and_a_spent_walk_say_so():
    batt, a, _ = _melee_battle()
    a.ap = 0
    assert _why(batt, a) == i18n.t("action.move_blocked.no_ap")
    a.ap, a.walking, a.moved = 1, True, a.speed
    assert _why(batt, a) == i18n.t("action.move_blocked.spent")


def test_a_walled_in_unit_is_boxed_in():
    batt, a, _ = _melee_battle()
    a.ap = 2
    batt.board.walls = set(batt.board.neighbors(a.pos)) - {a.pos}
    batt.units[1].pos = (15, 15)
    assert not actions.MOVE.available(batt, a)
    assert _why(batt, a) == i18n.t("action.move_blocked.boxed_in")


def test_a_disabled_move_always_carries_a_reason():
    batt, a, _ = _melee_battle()
    for cond in (None, Entangled, Grappled, Prone):
        for ap in (0, 1, 2):
            a.conditions = [] if cond is None else [cond()]
            a.ap = ap
            if not actions.MOVE.available(batt, a):
                assert _why(batt, a), (cond, ap)
