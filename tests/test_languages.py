"""Learning a language: same process as learning a level-0 spell (see
RULES.md "Learning a language"), minus the `magic_source` gate. Covers the
Linguist's starting `Dictionary of <Language>`, `magic.progress_study`'s
language branch, and the item's weight/pricing fallback.
"""

import random

from gartok import magic, orders
from gartok.group import Group
from gartok.guild import Guild
from tests.helpers import Unit, data

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


def test_studying_a_language_with_shared_party_dictionary():
    import random
    random.seed(1)
    student = Unit("player")
    student.magic_source = None
    student.languages = ["Ankarin"]
    student.study_target = "Elvish"
    student.gold = 1000

    companion = Unit("player")
    companion.give_to_pack("Dictionary of Elvish")

    g = Group([student, companion], node="tavern")
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("study")

    guild.pass_time(24)

    assert student.study_progress > 0
    assert student.gold == 1000 - 15


def test_idle_member_pays_no_rent_and_order_ends_when_nobody_studies():
    u = Unit("player")
    u.study_target = None
    u.gold = 1000
    g = Group([u], node="tavern")
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("study")

    guild.pass_time(24)

    assert u.gold == 1000
    assert g.order is None


def test_beginning_a_study_pulls_one_dictionary_into_the_students_pack():
    student, companion = Unit("player"), Unit("player")
    companion.give_to_pack("Dictionary of Elvish", 2)

    donor = magic.begin_study(student, "Elvish", [student, companion])

    assert donor is companion
    assert student.study_target == "Elvish" and student.study_progress == 0
    assert student.count_of("Dictionary of Elvish") == 1
    assert companion.count_of("Dictionary of Elvish") == 1            # peeled off the stack
    assert student.locked_of("Dictionary of Elvish") == 1


def test_a_scroll_the_student_already_holds_stays_put():
    student, companion = Unit("player"), Unit("player")
    spell = magic.SPELLS["sleep"]
    student.give_to_pack(f"Scroll of {spell.name}")
    companion.give_to_pack(f"Scroll of {spell.name}")

    assert magic.begin_study(student, spell.id, [student, companion]) is None
    assert student.count_of(f"Scroll of {spell.name}") == 1
    assert companion.count_of(f"Scroll of {spell.name}") == 1


def test_distribute_load_leaves_the_study_item_with_the_student():
    from gartok.unit import distribute_load
    student, companion = Unit("player"), Unit("player")
    companion.give_to_pack("Dictionary of Elvish")
    magic.begin_study(student, "Elvish", [student, companion])
    distribute_load([student, companion])
    assert student.count_of("Dictionary of Elvish") == 1


def test_ending_a_study_releases_the_lock_on_the_study_item():
    from gartok.unit import distribute_load
    student, companion = Unit("player"), Unit("player")
    companion.give_to_pack("Dictionary of Elvish")
    magic.begin_study(student, "Elvish", [student, companion])
    magic.end_study(student)
    assert student.study_target is None and student.study_progress == 0
    assert student.locked_of("Dictionary of Elvish") == 0
    distribute_load([student, companion])                       # free to move again
    assert student.count_of("Dictionary of Elvish") + companion.count_of("Dictionary of Elvish") == 1


def test_mastering_a_language_releases_the_lock_too():
    random.seed(4)
    student, companion = Unit("player"), Unit("player")
    student.magic_source = None
    student.languages = ["Ankarin"]
    student.gold = 1000
    companion.give_to_pack("Dictionary of Elvish")
    magic.begin_study(student, "Elvish", [student, companion])
    student.study_progress = magic.points_to_learn(0)
    magic.progress_study(student)
    assert "Elvish" in student.languages
    assert student.locked_of("Dictionary of Elvish") == 0
