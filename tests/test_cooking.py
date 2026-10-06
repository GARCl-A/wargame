"""Jerky, salt and the two places a group can cook: the house (needs an oven
from the Bankers) and the Wilds claim (needs a campfire). Together they let a
garrison outlast the 10-day sustain without hauling fresh meat."""

import os
import random

import pygame

from gartok import data, items, orders, persist
from gartok.city_property_screen import CityPropertyScreen
from gartok.group import Group
from gartok.guild import Guild
from gartok.ui.tokens import fonts as ui_fonts
from gartok.wilds_claim_screen import WildsClaimScreen
from tests.helpers import Unit, economy, packed, world

NODE = world.WILDS_TERRITORY_NODE


# --------------------------------------------------------------------------- #
# items and the recipe                                                        #
# --------------------------------------------------------------------------- #

def test_salt_is_sold_at_the_market_and_jerky_is_not():
    assert "Salt" in economy.MARKET_STOCK and "Jerky" not in economy.MARKET_STOCK
    assert economy.PRICES["Salt"] > 0


def test_everyone_knows_the_jerky_recipe_without_learning_it():
    u = Unit("player")
    assert "Jerky" not in u.recipes
    assert "Jerky" in u.known_recipes


def test_cooking_one_batch_turns_two_meat_and_salt_into_two_jerky():
    u = Unit("player")
    u._base_inventory = packed(["Meat", "Meat", "Salt"])
    guild = Guild([u])
    events, _ = guild.crafting_shift(u, "Jerky", 8)
    assert u.count_of("Jerky") == 2
    assert u.count_of("Meat") == 0 and u.count_of("Salt") == 0
    assert any("finished crafting" in e for e in events)


def test_cooking_needs_the_salt():
    u = Unit("player")
    u._base_inventory = packed(["Meat", "Meat"])
    events, _ = Guild([u]).crafting_shift(u, "Jerky", 1)
    assert u.count_of("Jerky") == 0 and u.count_of("Meat") == 2
    assert any("missing materials" in e for e in events)


def test_jerky_outlasts_the_garrison_but_meat_does_not():
    assert items.get("Jerky").lifespan >= economy.WILDS_CLAIM_SUSTAIN_DAYS * 2
    assert items.get("Meat").lifespan < economy.WILDS_CLAIM_SUSTAIN_DAYS


def test_a_garrison_fed_on_jerky_holds_the_full_sustain():
    random.seed(1)
    p = Unit("player")
    p._base_inventory = packed(["Jerky"] * (economy.WILDS_CLAIM_SUSTAIN_DAYS + 2))
    g = Group([p], node=NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_start_sustaining()
    g.order = orders.garrison("lumber")
    for _ in range(economy.WILDS_CLAIM_SUSTAIN_DAYS):
        guild.pass_time(24)
    assert guild.wilds_claim_stage == "ESTABLISHED"
    assert p.count_of("Rotten Food") == 0


# --------------------------------------------------------------------------- #
# the house oven                                                              #
# --------------------------------------------------------------------------- #

def _house_screen(coins, owned=True, oven=False, on_cook=lambda: None):
    p = Unit("player")
    p.gold = coins
    guild = Guild([p])
    guild.house.owned = owned
    guild.house.oven = oven
    return guild, CityPropertyScreen(ui_fonts(), guild, [p], lambda: None, on_cook=on_cook)


def test_the_oven_is_bought_from_the_house_screen_and_charged():
    guild, scr = _house_screen(economy.OVEN_PRICE + 5)
    assert [s[0] for s in scr._services()] == ["oven"]
    scr._run_service("oven")
    assert guild.house.oven
    assert scr.purse == 5
    assert [s[0] for s in scr._services()] == ["cook"]


def test_the_oven_is_refused_when_the_party_cannot_pay():
    guild, scr = _house_screen(economy.OVEN_PRICE - 1)
    assert not scr._services()[0][3]
    scr._run_service("oven")
    assert not guild.house.oven


def test_the_cook_button_opens_the_kitchen():
    calls = []
    _, scr = _house_screen(0, oven=True, on_cook=lambda: calls.append(1))
    scr._run_service("cook")
    assert calls == [1]


def test_losing_the_house_loses_the_oven():
    guild, _ = _house_screen(0, oven=True)
    guild.house.repossess()
    assert not guild.house.oven
    guild.house.oven = True
    guild.house.abandon()
    assert not guild.house.oven


# --------------------------------------------------------------------------- #
# the claim campfire                                                          #
# --------------------------------------------------------------------------- #

def _claim(fuel=1):
    p = Unit("player")
    p._base_inventory = packed([economy.CAMPFIRE_FUEL] * fuel)
    g = Group([p], node=NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_stage = "SWEPT"
    return guild, g, p


def _rolling(value):
    orig = data.roll
    data.roll = lambda n, sides: value
    return orig


def test_the_campfire_burns_one_fuel_and_an_hour_and_unlocks_cooking():
    guild, g, p = _claim()
    t0 = guild.clock.seconds
    orig = _rolling(20)
    try:
        lit, events, _ = guild.wilds_claim_light_campfire(g.members)
    finally:
        data.roll = orig
    assert lit and guild.wilds_claim_can_cook
    assert p.count_of(economy.CAMPFIRE_FUEL) == 0
    assert guild.clock.seconds - t0 == economy.CAMPFIRE_HOURS * 3600


def test_a_failed_check_still_burns_the_fuel():
    guild, g, p = _claim()
    orig = _rolling(1)
    try:
        lit, events, _ = guild.wilds_claim_light_campfire(g.members)
    finally:
        data.roll = orig
    if p.mod_wisdom + 1 >= economy.CAMPFIRE_DC:
        return                                  # a very wise character cannot fail on a 1
    assert not lit and not guild.wilds_claim_can_cook
    assert p.count_of(economy.CAMPFIRE_FUEL) == 0


def test_no_fuel_means_no_fire_and_no_time_passes():
    guild, g, _ = _claim(fuel=0)
    t0 = guild.clock.seconds
    lit, events, _ = guild.wilds_claim_light_campfire(g.members)
    assert not lit and guild.clock.seconds == t0
    assert any(economy.CAMPFIRE_FUEL in e for e in events)


def test_a_seized_claim_cannot_cook():
    guild, _, _ = _claim()
    guild.wilds_claim_campfire = True
    guild.wilds_claim_owner = "seized"
    assert not guild.wilds_claim_can_cook


def _claim_screen(guild, group, on_cook=lambda: None):
    return WildsClaimScreen(ui_fonts(), guild, group, lambda: None, lambda g: None,
                            lambda g: None, on_cook=on_cook)


def _button_keys(scr):
    pygame.init()
    scr.mouse = (0, 0)
    scr.draw(pygame.Surface((1280, 800)))
    return {k for k, _ in scr.buttons}


def test_the_claim_screen_offers_a_campfire_then_the_kitchen():
    guild, g, _ = _claim()
    scr = _claim_screen(guild, g)
    keys = _button_keys(scr)
    assert "campfire" in keys and "cook" not in keys

    guild.wilds_claim_campfire = True
    keys = _button_keys(scr)
    assert "cook" in keys and "campfire" not in keys


def test_the_campfire_button_is_off_without_fuel():
    guild, g, _ = _claim(fuel=0)
    assert "campfire" not in _button_keys(_claim_screen(guild, g))


def test_no_hearth_before_the_land_is_swept():
    guild, g, _ = _claim()
    guild.wilds_claim_stage = "FENCED"
    assert not {"campfire", "cook"} & _button_keys(_claim_screen(guild, g))


# --------------------------------------------------------------------------- #
# saves                                                                       #
# --------------------------------------------------------------------------- #

def test_oven_and_campfire_survive_a_save_round_trip():
    slot = "testworld_cooking"
    if os.path.exists(persist.save_path(slot)):
        return
    guild = Guild([Unit("player")])
    guild.house.owned = True
    guild.house.oven = True
    guild.wilds_claim_campfire = True
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot)
        assert back.house.oven and back.wilds_claim_campfire
    finally:
        persist.delete_world(slot)


# --------------------------------------------------------------------------- #
# batch cooking and the campfire going out                                    #
# --------------------------------------------------------------------------- #

def _batch_cook(monkeypatch, batches, hours, roll=10):
    monkeypatch.setattr("gartok.unit_loadout.roll", lambda n, sides: roll)
    u = Unit("player")
    u._base_inventory = packed(["Meat", "Meat", "Salt"] * batches)
    guild = Guild([u])
    t0 = guild.clock.seconds
    events, _ = guild.crafting_shift(u, "Jerky", hours)
    hourly = max(1, roll + u.mod_intelligence + u.talent_bonus("craft_bonus") + u.craft_bonuses.get("cooking", 0))
    return guild, u, events, hourly, (guild.clock.seconds - t0) / 3600


def test_one_shift_cooks_several_batches_and_the_last_keeps_its_progress(monkeypatch):
    goal = Unit.crafting_goal("Jerky")
    _, u, _, hourly, _ = _batch_cook(monkeypatch, 5, 8)
    assert hourly * 8 >= goal and hourly * 8 < goal * 5, "pick a roll that finishes some but not all"
    made = (hourly * 8) // goal
    assert u.count_of("Jerky") == 2 * made
    assert u.crafting_target == "Jerky" and u.crafting_progress == hourly * 8 - made * goal


def test_a_batch_shift_stops_when_the_materials_run_out(monkeypatch):
    goal = Unit.crafting_goal("Jerky")
    _, u, events, hourly, spent = _batch_cook(monkeypatch, 2, 40)
    assert u.count_of("Jerky") == 4 and u.crafting_target is None and u.crafting_progress == 0
    assert spent < 40 and spent == -(-2 * goal // hourly)
    assert any("out of materials" in e and "x4" in e for e in events)


def test_a_batch_shift_banks_work_xp_only_for_the_hours_worked(monkeypatch):
    _, u, _, _, spent = _batch_cook(monkeypatch, 1, 40)
    assert u.work_hours == spent


def test_the_campfire_burns_while_garrisoned_and_dies_the_day_nobody_is_there():
    guild, g, _ = _claim()
    guild.wilds_claim_campfire = True
    g.order = orders.garrison("lumber")
    guild._campfire_tick()
    assert guild.wilds_claim_campfire
    g.order = None
    guild._campfire_tick()
    assert not guild.wilds_claim_campfire and not guild.wilds_claim_can_cook


def test_the_daily_sweep_puts_the_fire_out_without_a_garrison():
    guild, _, _ = _claim()
    guild.wilds_claim_campfire = True
    guild.pass_time(24)
    assert not guild.wilds_claim_campfire
