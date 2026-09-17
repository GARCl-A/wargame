"""Learning a language: same process as learning a level-0 spell (see
RULES.md "Learning a language"), minus the `magic_source` gate. Covers the
Linguist's starting `Dictionary of <Language>`, `magic.progress_study`'s
language branch, and the item's weight/pricing fallback.
"""

import random

from tests.helpers import data, Unit
from gartok import magic, orders
from gartok.group import Group
from gartok.guild import Guild


# --------------------------------------------------------------------------- #
# the Linguist's starting item                                                #
# --------------------------------------------------------------------------- #

def test_linguist_starts_with_a_dictionary_of_a_foreign_language():
    random.seed(3)
    u = Unit("player")
    u.set_occupation("Linguist")            # deterministic re-roll of the occupation's item

    item = u._base_inventory[0][0]
    assert item.startswith("Dictionary of ")
    lang = magic.language_for_dictionary(item)
    assert lang is not None
    assert lang.name not in u.languages     # a language the character doesn't already speak


def test_dictionary_of_x_weighs_the_same_as_a_plain_dictionary():
    assert data.item_weight("Dictionary of Elvish") == data.item_weight("Dictionary")


def test_language_for_dictionary_rejects_non_dictionary_items():
    assert magic.language_for_dictionary("Scroll of Sleep") is None
    assert magic.language_for_dictionary("Dictionary of Nonsense") is None
    assert magic.language_for_dictionary(None) is None


# --------------------------------------------------------------------------- #
# the taverna's "study" garrison job -- language branch                       #
# --------------------------------------------------------------------------- #

def _student(language="Elvish"):
    u = Unit("player")
    u.magic_source = None
    u.languages = ["Ankarin"]
    u.study_target = language
    u.give_to_pack(f"Dictionary of {language}")
    return u


def test_studying_a_language_needs_no_magic_source():
    random.seed(1)
    u = _student()
    u.gold = 1000
    g = Group([u], node="tavern")
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("study")

    saved = data.roll
    data.roll = lambda n, faces: 10
    try:
        guild.pass_time(24)
    finally:
        data.roll = saved

    assert u.study_progress == 10 + u.mod_intelligence
    assert u.gold == 1000 - 15                    # economy.TAVERN_STUDY_COST_PER_DAY
    assert "Elvish" not in u.languages             # not enough points yet


def test_studying_masters_the_language_once_enough_points_are_banked():
    random.seed(1)
    u = _student()
    u.gold = 1000
    u.study_progress = magic.points_to_learn(0) - 1
    g = Group([u], node="tavern")
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("study")

    saved = data.roll
    data.roll = lambda n, faces: 20                # guarantee enough points regardless of INT mod
    try:
        guild.pass_time(24)
    finally:
        data.roll = saved

    assert "Elvish" in u.languages
    assert u.study_target is None
    assert u.study_progress == 0


def test_studying_a_language_without_the_dictionary_makes_no_progress():
    random.seed(1)
    u = _student()
    u._base_inventory.clear()          # dictionary lost/sold
    u.gold = 1000
    g = Group([u], node="tavern")
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("study")

    guild.pass_time(24)

    assert u.study_progress == 0
    assert u.gold == 1000 - 15         # the room is still rented either way


def test_progress_study_ignores_a_target_that_is_neither_spell_nor_language():
    u = Unit("player")
    u.study_target = "not-a-real-spell-or-language"
    u.gold = 1000

    event = magic.progress_study(u)

    assert event is None
    assert u.study_progress == 0
    assert u.gold == 1000 - 15         # the room is still rented either way
