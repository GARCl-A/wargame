"""Initiation into a magic school (rite.py): who the school takes, what each rite costs, the
boarding and its daily progress, the blood test, the board, the save and the INITIATION tab."""

import os
import random
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from gartok import data, items, magic, orders, persist, rite, world
from gartok.group import Group
from gartok.guild import Guild
from gartok.hub_screen import TabbedHubScreen
from gartok.initiation_screen import InitiationScreen
from gartok.ui.tokens import fonts as ui_fonts
from gartok.unit import Unit


def _guild(node="faith_cathedral", members=2, rep=2):
    random.seed(5)
    units = [Unit("player") for _ in range(members)]
    for u in units:
        u.money = 100
        u.magic_sources = []
        u.magic_blood = False
    g = Group(units, node=node)
    guild = Guild(None, groups=[g])
    for faction in rite.FACTION.values():
        guild.reputation[faction] = rep
    return guild, g, units


def _days(guild, n, roll=10):
    saved = data.roll
    data.roll = lambda k, faces: roll
    try:
        for _ in range(n):
            guild.pass_time(24)
    finally:
        data.roll = saved


def _ward(guild, unit):
    return next(g for g in guild.groups if unit in g.members)


# --- magic blood ------------------------------------------------------------------------ #

def test_magic_blood_is_rolled_at_creation_kept_per_uid_and_a_kobold_always_has_it():
    kobold = SimpleNamespace(uid="x", race={"name": "Kobold"})
    assert magic.roll_magic_blood(kobold)
    folk = [SimpleNamespace(uid=f"u{i}", race={"name": "Human"}) for i in range(4000)]
    share = sum(magic.roll_magic_blood(u) for u in folk) / len(folk)
    assert 0.03 < share < 0.07
    assert [magic.roll_magic_blood(u) for u in folk[:50]] == [magic.roll_magic_blood(u) for u in folk[:50]]
    u = Unit("player")
    assert u.magic_blood == magic.roll_magic_blood(u)


def test_rolling_magic_blood_leaves_the_shared_dice_alone():
    random.seed(9)
    expected = random.random()
    random.seed(9)
    magic.roll_magic_blood(SimpleNamespace(uid="abc", race={"name": "Elf"}))
    assert random.random() == expected


def test_the_rite_fields_survive_a_save_and_an_empty_magic_blood_is_rolled_on_load():
    u = Unit("player")
    u.blood_tested, u.blood_test_days, u.rite_school, u.rite_progress = True, 7, "blood", {"blood": 30}
    d = persist.unit_to_dict(u)
    back = Unit.from_save(d)
    assert (back.magic_blood, back.blood_tested, back.blood_test_days, back.rite_school, back.rite_progress) == (
        u.magic_blood, True, 7, "blood", {"blood": 30})
    d.pop("magic_blood")
    assert Unit.from_save(d).magic_blood == magic.roll_magic_blood(u)


# --- who the school takes ---------------------------------------------------------------- #

def test_the_school_wants_two_reputation_never_spent():
    guild, g, (a, _b) = _guild(node="nature_grove", rep=1)
    assert "2 reputation" in rite.blocker(guild, g, a, "nature")
    guild.reputation["nature_coven"] = 2
    assert rite.blocker(guild, g, a, "nature") is None
    rite.begin(guild, g, a, "nature")
    assert guild.reputation["nature_coven"] == 2


def test_an_initiate_is_not_taken_twice():
    guild, g, (a, _b) = _guild(node="nature_grove")
    a.magic_sources = ["nature"]
    assert "already initiated" in rite.blocker(guild, g, a, "nature")


def test_faith_consumes_a_holy_symbol_once_from_any_pack_in_the_group():
    guild, g, (a, b) = _guild()
    assert "Holy Symbol" in rite.blocker(guild, g, a, "faith")
    b.give_to_pack("Holy Symbol")
    ok, _ = rite.begin(guild, g, a, "faith")
    assert ok and not b.has_item("Holy Symbol") and rite.paid(a, "faith")
    ward = _ward(guild, a)
    ward.order = None                                      # leaves mid-way
    assert rite.blocker(guild, ward, a, "faith") is None   # resuming asks for no second symbol


# --- boarding --------------------------------------------------------------------------- #

def test_the_initiate_splits_off_into_a_group_of_their_own_on_the_rite():
    guild, g, (a, b) = _guild(node="nature_grove")
    ok, _ = rite.begin(guild, g, a, "nature")
    ward = _ward(guild, a)
    assert ok and ward is not g and ward.members == [a] and g.members == [b]
    assert ward.order.kind == "garrison" and ward.order.job == rite.JOB and a.rite_school == "nature"
    assert g.order is None


def test_with_no_free_slot_the_whole_group_waits():
    guild, g, (a, _b) = _guild(node="nature_grove")
    while guild.free_slots:
        guild.groups.append(Group([Unit("player")], node="city"))
    ok, lines = rite.begin(guild, g, a, "nature")
    assert ok and _ward(guild, a) is g and g.order.job == rite.JOB and "waits" in lines[-1]


def test_a_day_of_boarding_rolls_1d20_plus_int_and_initiation_ends_the_stay():
    guild, g, (a, _b) = _guild(node="nature_grove")
    a.intelligence = 10
    a._derive_combat()
    rite.begin(guild, g, a, "nature")
    ward = _ward(guild, a)
    _days(guild, 1, roll=10)
    assert a.rite_progress["nature"] == 10
    _days(guild, 26, roll=10)
    assert "nature" in a.magic_sources and a.rite_school is None and ward.order is None
    assert not a.spells_known                               # the rite teaches no spell


def test_leaving_mid_way_keeps_the_points():
    guild, g, (a, _b) = _guild(node="nature_grove")
    rite.begin(guild, g, a, "nature")
    _days(guild, 2, roll=15)
    kept = a.rite_progress["nature"]
    ward = _ward(guild, a)
    ward.order = orders.idle()
    a.rite_school = None
    _days(guild, 2)
    assert a.rite_progress["nature"] == kept and kept > 0
    assert rite.begin(guild, ward, a, "nature")[0] and a.rite_progress["nature"] == kept


def test_a_rite_left_behind_does_not_close_another_school():
    guild, g, (a, _b) = _guild(node="nature_grove")
    rite.begin(guild, g, a, "nature")
    ward = _ward(guild, a)
    ward.order = None
    ward.node = "blood_sanctuary"
    a.magic_blood = True
    assert rite.blocker(guild, ward, a, "blood") is None
    rite.begin(guild, ward, a, "blood")
    assert a.rite_school == "blood" and a.rite_progress["nature"] == 0


# --- the blood test ---------------------------------------------------------------------- #

def test_no_magic_blood_fails_the_test_after_seven_days_for_good():
    guild, g, (a, _b) = _guild(node="blood_sanctuary")
    a.magic_blood = False
    rite.begin(guild, g, a, "blood")
    ward = _ward(guild, a)
    _days(guild, 6)
    assert not a.blood_tested and a.rite_school == "blood"
    _days(guild, 1)
    assert a.blood_tested and a.rite_school is None and ward.order is None
    assert "no magic" in rite.blocker(guild, ward, a, "blood")


def test_magic_blood_passes_the_test_then_ninety_points():
    guild, g, (a, _b) = _guild(node="blood_sanctuary")
    a.magic_blood = True
    a.intelligence = 10
    a._derive_combat()
    rite.begin(guild, g, a, "blood")
    _days(guild, 7)
    assert a.blood_tested and a.rite_school == "blood" and a.rite_progress["blood"] == 0
    _days(guild, 8, roll=10)
    assert a.rite_progress["blood"] == 80 and "blood" not in a.magic_sources
    _days(guild, 1, roll=10)
    assert "blood" in a.magic_sources


# --- the board --------------------------------------------------------------------------- #

def test_board_feeds_a_boarder_with_an_empty_pack_for_three_and_charges_nothing_otherwise():
    guild, g, (a, _b) = _guild(node="nature_grove")
    a._base_inventory = [i for i in a._base_inventory if not items.is_food(i.name.split(" (")[0])]
    rite.begin(guild, g, a, "nature")
    a.share_food = False
    a.money = 10
    _days(guild, 1)
    assert a.money == 10 - rite.BOARD_PER_DAY and a.unfed_days == 0
    a.give_to_pack("Potato", 3)
    _days(guild, 1)
    assert a.money == 10 - rite.BOARD_PER_DAY and a.rations == 2


# --- the keepers and the tab ------------------------------------------------------------- #

def test_each_sanctuary_has_its_keeper_and_its_school():
    keepers = {n: world.vendor(n, "shrine") for n in rite.SANCTUARY}
    assert {n: k.race for n, k in keepers.items()} == {
        "blood_sanctuary": "Lizardfolk", "nature_grove": "Centaur", "faith_cathedral": "Kenku"}
    assert all(world.node(n).garrison_job == rite.JOB for n in rite.SANCTUARY)


def test_the_sanctuary_hub_has_an_initiation_tab_that_starts_the_rite():
    pygame.init()
    guild, g, (a, b) = _guild()
    b.give_to_pack("Holy Symbol")
    done = []
    hub = TabbedHubScreen.for_node(ui_fonts(), guild, g, world.node("faith_cathedral"), on_done=lambda: done.append(1))
    hub.tab = "initiation"
    screen = hub.active_screen()
    assert isinstance(screen, InitiationScreen)
    surf = pygame.Surface((1000, 640))
    hub.mouse = (0, 0)
    hub.draw(surf)
    row = dict(screen.row_rects)[a.uid]
    screen._click(row.center)
    assert screen._action() == "BEGIN THE RITE"
    hub.draw(surf)
    screen._click(screen.begin_rect.center)
    assert a.rite_school == "faith" and not done and "Holy Symbol" in screen.notice
    assert screen.tutorial_key() == "initiation"
