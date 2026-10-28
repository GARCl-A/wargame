"""Jerky, salt and the two places a group can cook: the house (needs an oven
from the Bankers) and the Wilds claim (needs a campfire). Together they let a
garrison outlast the 10-day sustain without hauling fresh meat."""

import os
import random

import pygame

from gartok import data, items, orders, persist
from gartok.group import Group
from gartok.guild import Guild
from gartok.ui.tokens import fonts as ui_fonts
from gartok.vault import HouseVault
from tests.helpers import Unit, economy, packed, world

NODE = world.WILDS_TERRITORY_NODE


# --------------------------------------------------------------------------- #
# items and the recipe                                                        #
# --------------------------------------------------------------------------- #

def test_salt_is_sold_at_the_farm_and_jerky_at_the_tavern():
    assert "Salt" in economy.targets_of("farm") and "Jerky" in economy.targets_of("tavern")
    assert economy.PRICES["Salt"] > 0


def test_everyone_knows_the_jerky_recipe_without_learning_it():
    u = Unit("player")
    assert "Jerky" not in u.recipes
    assert "Jerky" in u.known_recipes
    assert "Roast Meat" in u.known_recipes
    assert "Fruit Compote" in u.known_recipes


def test_cooking_roast_meat():
    u = Unit("player")
    u._base_inventory = packed(["Meat"])
    guild = Guild([u])
    events, _ = guild.crafting_shift(u, "Roast Meat", 4)
    assert u.count_of("Roast Meat") == 1
    assert u.count_of("Meat") == 0
    assert any("finished crafting" in e for e in events)


def test_cooking_fruit_compote_preserves_fruit_lifespan():
    u = Unit("player")
    u._base_inventory = packed(["Fruit", "Sugar", "Vial"])
    guild = Guild([u])
    events, _ = guild.crafting_shift(u, "Fruit Compote", 8)
    assert u.count_of("Fruit Compote") == 1
    assert u.count_of("Fruit") == 0 and u.count_of("Sugar") == 0 and u.count_of("Vial") == 0
    assert items.get("Fruit Compote").lifespan == 25
    assert items.get("Fruit").lifespan == 1


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

def _house(coins, owned=True, oven=False):
    p = Unit("player")
    p.money = coins
    guild = Guild([p])
    guild.house.owned = owned
    guild.house.oven = oven
    return guild, HouseVault(guild, [p])


def test_the_oven_is_bought_at_the_house_and_charged():
    guild, scr = _house(economy.OVEN_PRICE + 5)
    assert [s[0] for s in scr._services()] == ["oven"]
    scr._run_service("oven")
    assert guild.house.oven
    assert scr.purse == 5
    assert scr._services() == []


def test_the_oven_is_refused_when_the_party_cannot_pay():
    guild, scr = _house(economy.OVEN_PRICE - 1)
    assert not scr._services()[0][3]
    scr._run_service("oven")
    assert not guild.house.oven


def test_losing_the_house_loses_the_oven():
    guild, _ = _house(0, oven=True)
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
    assert u.work_hours == spent * 2                   # a level 1 recipe for a level 0 cook: x2


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


# --------------------------------------------------------------------------- #
# the claim oven                                                              #
# --------------------------------------------------------------------------- #

def _bricked(n=economy.CLAIM_OVEN_BRICKS):
    guild, g, p = _claim(fuel=0)
    p._base_inventory = packed([economy.CLAIM_OVEN_BRICK] * n)
    return guild, g, p


def test_the_oven_takes_bricks_and_hours_and_unlocks_cooking():
    guild, g, p = _bricked(economy.CLAIM_OVEN_BRICKS + 1)
    t0 = guild.clock.seconds
    built, events, _ = guild.claim_build_oven(g.members)
    assert built and guild.claim_oven and guild.wilds_claim_can_cook
    assert p.count_of(economy.CLAIM_OVEN_BRICK) == 1
    assert guild.clock.seconds - t0 == economy.CLAIM_OVEN_HOURS * 3600


def test_the_oven_pools_bricks_across_the_group():
    guild, g, p = _bricked(economy.CLAIM_OVEN_BRICKS - 2)
    q = Unit("second")
    q._base_inventory = packed([economy.CLAIM_OVEN_BRICK] * 2)
    g.members.append(q)
    built, _, _ = guild.claim_build_oven(g.members)
    assert built and p.count_of(economy.CLAIM_OVEN_BRICK) + q.count_of(economy.CLAIM_OVEN_BRICK) == 0


def test_too_few_bricks_build_nothing_and_cost_no_time():
    guild, g, p = _bricked(economy.CLAIM_OVEN_BRICKS - 1)
    t0 = guild.clock.seconds
    built, events, _ = guild.claim_build_oven(g.members)
    assert not built and not guild.claim_oven and guild.clock.seconds == t0
    assert p.count_of(economy.CLAIM_OVEN_BRICK) == economy.CLAIM_OVEN_BRICKS - 1


def test_a_second_oven_is_refused():
    guild, g, p = _bricked(economy.CLAIM_OVEN_BRICKS * 2)
    guild.claim_build_oven(g.members)
    built, _, _ = guild.claim_build_oven(g.members)
    assert not built and p.count_of(economy.CLAIM_OVEN_BRICK) == economy.CLAIM_OVEN_BRICKS


def test_the_oven_outlives_the_garrison_that_puts_the_campfire_out():
    guild, g, _ = _bricked()
    guild.claim_build_oven(g.members)
    guild.wilds_claim_campfire = True
    guild._campfire_tick()
    assert not guild.wilds_claim_campfire and guild.wilds_claim_can_cook


def test_a_seized_claim_cannot_cook_but_keeps_the_oven():
    guild, g, _ = _bricked()
    guild.claim_build_oven(g.members)
    guild.wilds_claim_seize()
    assert guild.claim_oven and not guild.wilds_claim_can_cook
    guild.wilds_claim_owner = "guild"
    assert guild.wilds_claim_can_cook


def test_the_claim_oven_costs_the_same_as_the_house_oven_in_bricks():
    assert economy.CLAIM_OVEN_BRICKS * economy.PRICES[economy.CLAIM_OVEN_BRICK] == economy.OVEN_PRICE


def test_the_bricks_are_sold_at_the_mine():
    assert economy.CLAIM_OVEN_BRICK in economy.MINE_SUPPLIES and economy.PRICES[economy.CLAIM_OVEN_BRICK] > 0
    assert economy.CLAIM_OVEN_BRICK not in economy.MARKET_STOCK


def test_the_claim_oven_survives_a_save_round_trip():
    slot = "testworld_claim_oven"
    if os.path.exists(persist.save_path(slot)):
        return
    guild = Guild([Unit("player")])
    guild.claim_oven = True
    try:
        persist.save_game(slot, guild)
        assert persist.load_game(slot).claim_oven
    finally:
        persist.delete_world(slot)


# --------------------------------------------------------------------------- #
# field campfire cooking at any node                                         #
# --------------------------------------------------------------------------- #

def test_field_campfire_lighting_consumes_lumber_and_coal_requires_flint_and_steel():
    u = Unit("player")
    u._base_inventory = packed(["Flint and Steel", "Lumber", "1kg Coal", "Meat", "Meat", "Salt"])
    g = Group([u], node="wilds")
    assert g.can_light_campfire()
    assert not g.has_campfire(1000)

    assert g.light_campfire(1000)
    assert g.has_campfire(1000)
    assert g.campfire_hours_left(1000) == 4.0
    assert u.count_of("Flint and Steel") == 1
    assert u.count_of("Lumber") == 0
    assert u.count_of("1kg Coal") == 0


def test_field_campfire_cannot_light_without_tools_or_fuel():
    # Missing flint & steel
    u = Unit("player")
    u._base_inventory = packed(["Lumber", "1kg Coal"])
    g = Group([u], node="wilds")
    assert not g.can_light_campfire()
    assert not g.light_campfire(1000)

    # Missing lumber
    u._base_inventory = packed(["Flint and Steel", "1kg Coal"])
    assert not g.can_light_campfire()

    # Missing coal
    u._base_inventory = packed(["Flint and Steel", "Lumber"])
    assert not g.can_light_campfire()


def test_field_campfire_expires_after_4_hours():
    u = Unit("player")
    u._base_inventory = packed(["Flint and Steel", "Lumber", "1kg Coal"])
    g = Group([u], node="wilds")
    g.light_campfire(0)
    assert g.has_campfire(3600 * 3)
    assert g.campfire_hours_left(3600 * 3) == 1.0
    assert not g.has_campfire(3600 * 4)
    assert g.campfire_hours_left(3600 * 4) == 0.0


def test_field_campfire_left_behind_when_moving():
    u = Unit("player")
    u._base_inventory = packed(["Flint and Steel", "Lumber", "1kg Coal"])
    g = Group([u], node="wilds")
    g.light_campfire(100)
    assert g.has_campfire(100)
    g.node = "road"
    assert not g.has_campfire(100)


def test_field_campfire_survives_save_round_trip():
    slot = "testworld_field_campfire"
    if os.path.exists(persist.save_path(slot)):
        return
    u = Unit("player")
    g = Group([u], node="wilds")
    g.campfire_node = "wilds"
    g.campfire_expires = 50000
    guild = Guild([u], groups=[g])
    guild.clock.seconds = 10000
    try:
        persist.save_game(slot, guild)
        loaded = persist.load_game(slot)
        lg = loaded.groups[0]
        assert lg.has_campfire(10000)
        assert lg.campfire_node == "wilds"
        assert lg.campfire_expires == 50000
    finally:
        persist.delete_world(slot)


def test_field_campfire_in_group_screen_actions():
    from gartok.group_screen import GroupScreen
    pygame.init()
    u = Unit("player")
    u._base_inventory = packed(["Flint and Steel", "Lumber", "1kg Coal"])
    g = Group([u], node="wilds")
    guild = Guild([u], groups=[g])

    cook_opened = []
    scr = GroupScreen(ui_fonts(), guild, g, on_back=lambda: None, on_cook=lambda: cook_opened.append(True))
    scr.mouse = (0, 0)
    scr.draw(pygame.Surface((1280, 800)))
    
    # Click campfire action in toolbar
    scr._handle_button("campfire_cook")
    assert g.has_campfire(guild.clock.seconds)
    assert cook_opened == [True]
