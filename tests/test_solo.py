"""Solo tasks: a member crafts apart from the group, on a `solo` order the clock settles."""

import pygame
import pytest

import gartok.unit_loadout as _unit_mod
from gartok import campaign, persist, solo
from gartok.clock import Clock
from gartok.crafting_screen import CraftingScreen
from gartok.group import Group
from gartok.guild import Guild
from gartok.ui.tokens import fonts
from tests.helpers import Unit

RECIPE = "Bear Trap"


def _crafter(material=True):
    u = Unit("player")
    u.recipes.append(RECIPE)
    if material:
        u.give_to_pack("Iron Bar")
    return u


def _setup(*units):
    g = Group(list(units), node="city")
    return Guild(None, groups=[g], clock=Clock(12 * 3600)), g


def _sure_rolls(monkeypatch):
    monkeypatch.setattr(_unit_mod, "roll", lambda n, d: 9999)


def test_a_lone_crafter_works_on_their_own_order(monkeypatch):
    _sure_rolls(monkeypatch)
    u = _crafter()
    guild, g = _setup(u)
    ok, _ = solo.craft(guild, g, u, RECIPE, 4)
    assert ok and g.order.kind == "solo" and g.order.task == "craft" and g.order.recipe == RECIPE
    assert g.locked and not u.has_item(RECIPE)
    res = campaign.advance(guild)
    assert u.has_item(RECIPE) and g.order is None
    assert any("finished crafting" in e for e in res.events)
    assert guild.clock.hour_of_day == (12 + 4) % 24


def test_working_alone_splits_the_crafter_off_and_the_rest_stay_free(monkeypatch):
    _sure_rolls(monkeypatch)
    u, mate = _crafter(), Unit("player")
    guild, g = _setup(u, mate)
    ok, _ = solo.craft(guild, g, u, RECIPE, 4)
    ward = next(x for x in guild.groups if u in x.members)
    assert ok and ward is not g and ward.members == [u] and g.members == [mate]
    assert ward.locked and not g.locked
    with pytest.raises(ValueError):
        guild.merge_groups(g, ward)
    campaign.advance(guild)
    assert u.has_item(RECIPE) and not ward.locked
    guild.merge_groups(g, ward)
    assert set(g.members) == {u, mate}


def test_working_alone_with_no_free_slot_is_refused_and_changes_nothing():
    u, mate = _crafter(), Unit("player")
    guild, g = _setup(u, mate)
    guild.groups += [Group([Unit("player")], node="city") for _ in range(guild.group_slots)]
    ok, lines = solo.craft(guild, g, u, RECIPE, 4)
    assert not ok and "slot" in lines[0] and g.order is None and g.members == [u, mate]


def test_the_whole_group_can_wait_and_feeds_the_craft_from_every_pack(monkeypatch):
    _sure_rolls(monkeypatch)
    u, mate = _crafter(material=False), Unit("player")
    mate.give_to_pack("Iron Bar")
    guild, g = _setup(u, mate)
    assert not solo.craft(guild, g, u, RECIPE, 4)[0]
    ok, lines = solo.craft(guild, g, u, RECIPE, 4, alone=False)
    assert ok and "waits" in lines[0] and g.members == [u, mate] and g.locked
    campaign.advance(guild)
    assert u.has_item(RECIPE) and not mate.has_item("Iron Bar") and g.order is None


def test_a_craft_without_materials_or_with_an_order_in_flight_is_refused():
    from gartok import orders
    u = _crafter(material=False)
    guild, g = _setup(u)
    ok, lines = solo.craft(guild, g, u, RECIPE, 4)
    assert not ok and "missing materials" in lines[0] and g.order is None
    u.give_to_pack("Iron Bar")
    g.order = orders.rest(8)
    assert not solo.craft(guild, g, u, RECIPE, 4)[0]


def test_hours_the_crafter_does_not_use_still_pass(monkeypatch):
    _sure_rolls(monkeypatch)
    u = _crafter()
    guild, g = _setup(u)
    solo.craft(guild, g, u, RECIPE, 8)
    campaign.advance(guild)
    assert u.work_hours > 0 and guild.clock.hour_of_day == (12 + 8) % 24


def test_a_craft_order_survives_a_save():
    u = _crafter()
    guild, g = _setup(u)
    solo.craft(guild, g, u, RECIPE, 4)
    back = persist.order_from_dict(persist.order_to_dict(g.order))
    assert (back.task, back.who, back.recipe, back.hours) == ("craft", u.uid, RECIPE, 4)


def test_the_forge_sends_a_crafter_off_alone():
    u = _crafter()
    guild, g = _setup(u)
    done = []
    scr = CraftingScreen(fonts(), guild, g, lambda: done.append(1))
    surf = pygame.Surface((1280, 900))
    scr.draw(surf)
    keys = dict(scr.buttons)
    assert f"alone:8:{RECIPE}" in keys
    scr.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=keys[f"alone:8:{RECIPE}"].center))
    assert done and g.order.task == "craft" and g.order.hours == 8


def test_the_forge_does_not_offer_alone_without_a_free_slot():
    u, mate = _crafter(), Unit("player")
    guild, g = _setup(u, mate)
    guild.groups += [Group([Unit("player")], node="city") for _ in range(guild.group_slots)]
    scr = CraftingScreen(fonts(), guild, g, lambda: None)
    scr.draw(pygame.Surface((1280, 900)))
    keys = dict(scr.buttons)
    assert f"work:8:{RECIPE}" in keys and f"alone:8:{RECIPE}" not in keys


def test_a_waiting_group_heals_everyone_but_the_worker(monkeypatch):
    _sure_rolls(monkeypatch)
    u, mate = _crafter(), Unit("player")
    u.hp -= 3
    mate.hp -= 3
    guild, g = _setup(u, mate)
    solo.craft(guild, g, u, RECIPE, 16, alone=False)
    guild.pass_time(16)
    assert u.consecutive_rest_hours == 0 and u.hp == u.hp_max - 3
    assert mate.hp > mate.hp_max - 3
