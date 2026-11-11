"""A foe already running is let go while another stands to fight; when every foe left runs, the AI chases them."""

from gartok import actions
from gartok.ai.attack import _demoralize_victim, _pick_attack
from gartok.ai.target import _target
from gartok.conditions import Routed
from tests.helpers import Battle, standard_unit


def _field(foes=2):
    a = standard_unit("player")
    a.languages = ["Ankarin"]
    b = Battle([a], [standard_unit("enemy") for _ in range(foes)])
    b.board.walls.clear()
    b.ambient_light = True
    me, *rest = b.units
    me.pos, me.ap = (5, 5), 3
    for i, f in enumerate(rest):
        f.pos = (6 + i * 2, 5)
    return b, me, rest


def test_the_nearest_foe_is_skipped_when_it_runs_and_another_stands():
    b, me, (near, far) = _field()
    near.add_condition(Routed())
    assert _target(b, me) is far


def test_without_a_runner_the_nearest_is_still_the_target():
    b, me, (near, _far) = _field()
    assert _target(b, me) is near


def test_when_every_foe_runs_the_nearest_runner_is_chased():
    b, me, (near, far) = _field()
    near.add_condition(Routed())
    far.add_condition(Routed())
    assert _target(b, me) is near


def test_a_runner_is_struck_not_grabbed_even_when_it_is_the_last():
    b, me, (foe,) = _field(foes=1)
    foe.add_condition(Routed())
    assert _pick_attack(b, me, _target(b, me)) is actions.ATTACK


def test_demoralize_leaves_a_runner_alone():
    b, me, (near, far) = _field()
    near.add_condition(Routed())
    victim = _demoralize_victim(b, me, far)
    assert victim is not near
