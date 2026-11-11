"""Surgical Strike: Brutal 1 on every attack against a foe the side has read in full (Exploit Weakness first)."""

import random

from gartok import actions, intel
from gartok.ai.reckon import _strike_worth
from scripts import race_study_builds as rb
from tests.helpers import Battle, fixed_d20, standard_unit

PATH = ("tactical_mind", "analytical_eye", "exploit_weakness", "surgical_strike")


def _duel(*talents, read=True):
    a, d = standard_unit("player"), standard_unit("enemy")
    for i, t in enumerate(talents, 1):
        a.set_track_level("combat", i)
        assert a.choose_talent("combat", t), t
    a._derive_combat()
    b = Battle([a], [d])
    ca, cd = b.units
    b.board.walls.clear()
    ca.pos, cd.pos = (5, 5), (6, 5)
    ca.ap = 3
    cd.hp = cd.hp_max = 500
    if read:
        b.intel.margin[ca.team][cd] = intel.HARD
    return b, ca, cd


def _brutal_dice(unit):
    seen = {}
    real = unit.damage_roll

    def spy(**k):
        seen.update(k)
        return real(**k)

    unit.damage_roll = spy
    return seen


def test_it_needs_exploit_weakness():
    u = standard_unit("player")
    u.set_track_level("combat", 4)
    assert u.choose_talent("combat", "tactical_mind") and u.choose_talent("combat", "analytical_eye")
    assert not u.choose_talent("combat", "surgical_strike")


def test_an_attack_on_a_foe_read_in_full_is_brutal():
    b, a, d = _duel(*PATH)
    seen = _brutal_dice(a)
    with fixed_d20(15):
        actions._strike(b, a, d)
    assert seen["brutal"] == 1
    assert any("Surgical Strike" in line for line in b.log_lines)


def test_an_attack_on_a_foe_not_read_in_full_is_not():
    b, a, d = _duel(*PATH, read=False)
    seen = _brutal_dice(a)
    with fixed_d20(15):
        actions._strike(b, a, d)
    assert not seen["brutal"]


def test_the_ai_prices_the_extra_dice():
    b, a, d = _duel(*PATH)
    with_it = _strike_worth(b, a, d)
    a.char.talents["combat"].remove("surgical_strike")
    assert with_it > _strike_worth(b, a, d)


def test_the_analyst_holds_the_whole_line():
    unit, notes = rb.make_unit("player", "Human", "analyst", 5, random.Random(1))
    assert set(rb.BUILDS["analyst"].combat) == set(unit.talents["combat"])
    assert not [n for n in notes if n.startswith("talent")], notes
