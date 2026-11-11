"""Merciless: Brutal 1 on every attack against a demoralized target. A race whose ability already crosses the language gap
(the Kenku's Mimic Sounds) is not offered Wordless Menace, and the study's builds give it Merciless in its place."""

import random

from gartok import actions
from gartok.ai.reckon import _strike_worth
from gartok.conditions import Demoralized
from scripts import race_study_builds as rb
from tests.helpers import Battle, fitted, fixed_d20, standard_unit

PATH = ("imposing", "menacing", "cull_the_broken", "merciless")


def _duel(*talents, demoralized=True):
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
    if demoralized:
        cd.add_condition(Demoralized())
    return b, ca, cd


def _brutal_dice(unit, **kw):
    seen = {}
    real = unit.damage_roll

    def spy(**k):
        seen.update(k)
        return real(**k)

    unit.damage_roll = spy
    return seen


def test_merciless_needs_cull_the_broken():
    u = standard_unit("player")
    u.set_track_level("combat", 2)
    assert u.choose_talent("combat", "imposing") and u.choose_talent("combat", "menacing")
    assert not u.choose_talent("combat", "merciless")


def test_an_attack_on_a_demoralized_target_is_brutal():
    b, a, d = _duel(*PATH)
    seen = _brutal_dice(a)
    with fixed_d20(15):
        actions._strike(b, a, d)
    assert seen["brutal"] == 1
    assert any("Brutal" in line for line in b.log_lines)


def test_an_attack_on_a_steady_target_is_not():
    b, a, d = _duel(*PATH, demoralized=False)
    seen = _brutal_dice(a)
    with fixed_d20(15):
        actions._strike(b, a, d)
    assert not seen["brutal"]


def test_it_stacks_with_the_weapons_own_brutal():
    b, a, d = _duel(*PATH)
    a.equip_weapon(fitted(a, "Hammer"))
    a.ap = 2
    seen = _brutal_dice(a)
    with fixed_d20(15):
        actions.MAIMING_STRIKE.execute(b, a, d)
    assert seen["brutal"] == 2


def test_the_ai_prices_the_extra_dice():
    b, a, d = _duel(*PATH)
    with_it = _strike_worth(b, a, d)
    a.char.talents["combat"].remove("merciless")
    assert with_it > _strike_worth(b, a, d)


def test_a_kenku_is_not_offered_wordless_menace():
    kenku = standard_unit("player")
    kenku.set_race("Kenku")
    kenku.set_track_level("combat", 3)
    assert kenku.choose_talent("combat", "imposing") and kenku.choose_talent("combat", "menacing")
    assert not kenku.choose_talent("combat", "wordless_menace")
    assert kenku.choose_talent("combat", "cull_the_broken")


def test_a_human_still_takes_it():
    human = standard_unit("player")
    human.set_track_level("combat", 3)
    assert human.choose_talent("combat", "imposing") and human.choose_talent("combat", "menacing")
    assert human.choose_talent("combat", "wordless_menace")


def test_the_kenku_intimidator_takes_merciless_in_its_place():
    unit, notes = rb.make_unit("player", "Kenku", "intimidator", 5, random.Random(1))
    held = set(unit.talents["combat"])
    assert "wordless_menace" not in held and {"merciless", "cull_the_broken", "dread_voice"} <= held
    assert not [n for n in notes if n.startswith("talent")], notes


def test_the_kenku_commander_takes_dread_voice_in_its_place():
    unit, notes = rb.make_unit("player", "Kenku", "commander", 5, random.Random(1))
    held = set(unit.talents["combat"])
    assert "wordless_menace" not in held and {"gruesome_takedown", "inspiring_shout", "dread_voice"} <= held
    assert not [n for n in notes if n.startswith("talent")], notes


def test_the_intimidating_archer_is_a_longbow_with_the_whole_line():
    unit, notes = rb.make_unit("player", "Kenku", "intimidator_archer", 5, random.Random(1))
    assert set(rb.BUILDS["intimidator_archer"].combat) <= set(unit.talents["combat"])
    assert "Longbow" in unit.equipped_weapon and not [n for n in notes if n.startswith("talent")], notes
