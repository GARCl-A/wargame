"""The body's size moves Armor Class and touch AC: smaller is harder to hit."""

import pytest

from gartok import data
from gartok.combatant import Combatant
from tests.helpers import standard_unit

AC_BY_SIZE = {"Tiny": 2, "Small": 1, "Medium": 0, "Large": -1, "Huge": -2}


def test_table_matches_the_ladder():
    assert {s: data.SIZES[s]["ac"] for s in data.SIZE_ORDER} == AC_BY_SIZE


@pytest.mark.parametrize("race,size", [("Sprite", "Tiny"), ("Halfling", "Small"), ("Human", "Medium"), ("Centaur", "Large")])
def test_size_adds_to_ac_and_its_breakdown(race, size):
    u = standard_unit()
    u.set_race(race)
    assert u.size == size
    assert u.ac == 10 + u.mod_dexterity + AC_BY_SIZE[size] + u.ac_natural
    assert ((f"{size} size", AC_BY_SIZE[size]) in u.ac_breakdown()) == bool(AC_BY_SIZE[size])
    assert sum(v for _, v in u.ac_breakdown()) == u.ac


def test_size_counts_against_touch_attacks_too():
    small, medium = standard_unit(), standard_unit()
    small.set_race("Halfling")
    medium.set_race("Human")
    gap = Combatant(small, small.team).touch_ac - Combatant(medium, medium.team).touch_ac
    assert gap == 1 + small.mod_dexterity - medium.mod_dexterity
