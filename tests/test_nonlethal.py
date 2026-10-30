"""The Non-lethal toggle (actions.NonLethal): pulled blows knock a foe out instead of killing."""

from unittest.mock import patch

from gartok import ai
from gartok.actions.base import _resolve_hit
from tests.helpers import Battle, Unit, _melee_battle, actions


def _sturdy_battle():
    batt, a, d = _melee_battle()
    a.ap = 2
    d.hp = 1
    return batt, a, d


def test_the_toggle_is_free_and_flips_back():
    batt, a, _ = _sturdy_battle()
    assert actions.NONLETHAL.cost == 0
    actions.NONLETHAL.execute(batt, a)
    assert a.nonlethal_blows and a.ap == 2
    assert actions.NONLETHAL.label(batt, a) == "Non-lethal: ON"
    actions.NONLETHAL.execute(batt, a)
    assert not a.nonlethal_blows


def test_a_non_lethal_fight_has_no_toggle():
    batt = Battle([Unit("player")], [Unit("enemy")], lethal=False)
    assert not actions.NONLETHAL.applicable(batt, batt.player_units[0])[0]


def test_a_pulled_blow_is_one_worse_to_hit():
    batt, a, d = _sturdy_battle()
    d.hp = 50
    ac = d.ac_vs(a)
    assert _resolve_hit(batt, a, d, 10, ac - 10, "", "x") == "hit"
    a.nonlethal_blows = True
    assert _resolve_hit(batt, a, d, 10, ac - 10, "", "x") == "miss"


def test_a_foe_dropped_by_a_pulled_blow_is_knocked_out_not_dying():
    batt, a, d = _sturdy_battle()
    a.nonlethal_blows = True
    _resolve_hit(batt, a, d, 20, 0, "", "x")
    assert d.status == "stable"


def test_a_lethal_blow_still_leaves_the_foe_dying():
    batt, a, d = _sturdy_battle()
    _resolve_hit(batt, a, d, 20, 0, "", "x")
    assert d.status == "dying"


def test_a_pulled_blow_on_a_dying_body_spares_it():
    batt, a, d = _sturdy_battle()
    _resolve_hit(batt, a, d, 20, 0, "", "x")
    a.nonlethal_blows = True
    clock = d.death_clock
    _resolve_hit(batt, a, d, 20, 0, "", "x")
    assert d.status == "dying" and d.death_clock == clock


def test_a_pulled_magic_missile_knocks_out_too():
    batt, a, d = _sturdy_battle()
    a.spells_known = ["magic_missile"]
    a.nonlethal_blows = True
    missile = actions.CastSpellAction("magic_missile")
    with patch("gartok.actions.spells.d20", return_value=20):
        missile.execute(batt, a, d)
    assert d.status == "stable"


def test_the_player_side_ai_pulls_its_blows_on_a_foe_it_wants_alive():
    batt, a, d = _sturdy_battle()
    batt.wanted_alive.add(d)
    assert ai._wants_alive(batt, a, d)
    assert not ai._wants_alive(batt, d, a)
    d.hp = 0
    d.status = "dying"
    assert ai._finish_off(batt, a) is None


def test_the_ai_switches_the_toggle_when_its_target_is_wanted():
    batt, a, d = _sturdy_battle()
    d.hp = 40
    batt.wanted_alive.add(d)
    with patch("gartok.ai.turn._target", return_value=d), patch.object(batt, "end_turn"):
        ai.take_turn(batt, a)
    assert a.nonlethal_blows
