"""The house garage: bought by the bay, holds a wagon and an animal per tier, keeps
them safe, feeds the animals from the house stash and gives them back to the group."""

import os

import pygame

from gartok import economy, persist
from gartok.animals import HARNESS, STARVE_DAYS, Animal
from gartok.city_property_screen import CityPropertyScreen
from gartok.garage_screen import GarageScreen
from gartok.group import Group
from gartok.guild import Guild
from gartok.ui.tokens import fonts as ui_fonts
from gartok.wagon import Wagon
from tests.helpers import Unit


def _setup(coins=0, bays=1, wagons=1, animals=1, wise=0):
    u = Unit("player")
    u.gold = coins
    u.mod_wisdom = wise
    g = Group([u], node="city", wagons=[Wagon() for _ in range(wagons)],
              herd=[Animal("Donkey") for _ in range(animals)])
    guild = Guild(None, groups=[g])
    guild.house.owned = True
    guild.house.garage.tier = bays
    return guild, g, u


def _screen(guild, g):
    return GarageScreen(ui_fonts(), guild, g, lambda: None)


def _keys(scr):
    pygame.init()
    scr.mouse = (0, 0)
    scr.draw(pygame.Surface((1280, 800)))
    return {k for k, _ in scr.buttons}


def test_a_bay_costs_the_flat_price_and_adds_room_for_one_of_each():
    guild, g, u = _setup(coins=economy.GARAGE_PRICE + 4, bays=0)
    scr = _screen(guild, g)
    assert "bay" in _keys(scr)
    scr._click("bay")
    garage = guild.house.garage
    assert garage.tier == 1 and garage.wagon_room == 1 and garage.animal_room == 1
    assert u.gold == 4


def test_a_bay_is_refused_when_the_party_cannot_pay():
    guild, g, u = _setup(coins=economy.GARAGE_PRICE - 1, bays=0)
    scr = _screen(guild, g)
    assert "bay" not in _keys(scr)
    scr._click("bay")
    assert guild.house.garage.tier == 0 and u.gold == economy.GARAGE_PRICE - 1


def test_parking_moves_the_wagon_and_the_animal_out_of_the_group_and_keeps_the_cargo():
    guild, g, _ = _setup()
    wagon, animal = g.wagons[0], g.herd[0]
    wagon.stash.put("Potato")
    assert guild.park_wagon(g, wagon) and guild.park_animal(g, animal)
    assert g.wagons == [] and g.herd == [] and wagon._group is None
    assert guild.house.garage.wagons == [wagon] and guild.house.garage.herd == [animal]
    assert [n for n, _ in wagon.stash.items] == ["Potato"]


def test_parking_unhitches_the_animal_from_its_wagon():
    guild, g, _ = _setup()
    g.herd[0].give_to_tack(HARNESS)
    g.hitch_idle()
    assert g.herd[0].hitch == g.wagons[0].uid
    guild.park_wagon(g, g.wagons[0])
    assert g.herd[0].hitch is None


def test_a_full_garage_takes_no_more():
    guild, g, _ = _setup(wagons=2, animals=2)
    assert guild.park_wagon(g, g.wagons[0]) and guild.park_animal(g, g.herd[0])
    assert not guild.park_wagon(g, g.wagons[0]) and not guild.park_animal(g, g.herd[0])
    assert len(g.wagons) == 1 and len(g.herd) == 1


def test_no_garage_means_nothing_can_be_parked():
    guild, g, _ = _setup(bays=0)
    assert not guild.park_wagon(g, g.wagons[0]) and not guild.park_animal(g, g.herd[0])


def test_taking_out_gives_the_group_the_wagon_and_hitches_the_harnessed_animal():
    guild, g, _ = _setup(wagons=1, animals=0)
    donkey = Animal("Donkey", tack=HARNESS)
    guild.house.garage.herd.append(donkey)
    wagon = g.wagons[0]
    guild.park_wagon(g, wagon)
    assert guild.take_wagon(g, wagon) and guild.take_animal(g, donkey)
    assert g.wagons == [wagon] and wagon._group is g and g.herd == [donkey]
    assert donkey.hitch == wagon.uid
    assert guild.house.garage.wagons == [] and guild.house.garage.herd == []


def test_a_garaged_animal_does_not_count_against_the_herd_but_coming_out_does():
    guild, g, _ = _setup(wagons=0, animals=0, bays=1)
    herd = [Animal("Donkey") for _ in range(g.herd_capacity)]
    g.herd.extend(herd)
    guild.house.garage.herd.append(Animal("Ox"))
    assert g.herd_load == g.herd_capacity
    assert not guild.take_animal(g, guild.house.garage.herd[0])
    assert len(guild.house.garage.herd) == 1


def test_garaged_animals_eat_from_the_house_stash_each_day():
    guild, g, u = _setup(wagons=0, animals=0)
    u._base_inventory = []
    donkey = Animal("Donkey")
    guild.house.garage.herd.append(donkey)
    guild.house.stash.put("Potato", 2)
    assert guild.house.garage.feed(guild.house.stash) == []
    assert guild.house.stash.items[0][1] == 1 and donkey.unfed_days == 0


def test_garaged_animals_also_eat_from_a_parked_wagons_cargo():
    guild, g, _ = _setup(animals=0)
    wagon = g.wagons[0]
    wagon.stash.put("Potato")
    guild.park_wagon(g, wagon)
    donkey = Animal("Donkey")
    guild.house.garage.herd.append(donkey)
    guild.house.garage.feed(guild.house.stash)
    assert wagon.rations == 0 and donkey.unfed_days == 0


def test_garaged_animals_starve_when_the_house_has_no_food():
    guild, _g, _ = _setup(wagons=0, animals=0)
    guild.house.garage.herd.append(Animal("Donkey"))
    for _ in range(STARVE_DAYS - 1):
        assert any("went hungry" in e for e in guild.house.garage.feed(guild.house.stash))
    assert any("starved" in e for e in guild.house.garage.feed(guild.house.stash))
    assert guild.house.garage.herd == []


def test_the_daily_sweep_feeds_the_garage():
    guild, _g, u = _setup(wagons=0, animals=0)
    u._base_inventory = []
    guild.house.garage.herd.append(Animal("Donkey"))
    guild.house.stash.put("Potato", 3)
    guild.pass_time(24)
    assert guild.house.garage.herd[0].unfed_days == 0
    assert guild.house.stash.items[0][1] == 2


def test_losing_the_house_loses_the_garage():
    guild, g, _ = _setup()
    guild.park_wagon(g, g.wagons[0])
    guild.house.repossess()
    assert not guild.house.garage.open and guild.house.garage.wagons == []
    guild.house.garage.tier = 1
    guild.house.garage.herd.append(Animal("Ox"))
    guild.house.abandon()
    assert guild.house.garage.herd == [] and guild.house.garage.tier == 0


def test_the_house_screen_offers_the_garage_once_it_is_wired():
    guild, g, _ = _setup(bays=0)
    calls = []
    scr = CityPropertyScreen(ui_fonts(), guild, list(g.members), lambda: None,
                             on_garage=lambda: calls.append(1))
    assert "garage" in [s[0] for s in scr._services()]
    scr._run_service("garage")
    assert calls == [1]


def test_the_screen_draws_with_and_without_a_garage():
    for bays in (0, 2):
        guild, g, _ = _setup(bays=bays, wagons=2, animals=2)
        guild.park_wagon(g, g.wagons[0]) if bays else None
        _keys(_screen(guild, g))


def test_the_screen_buttons_park_and_take_out():
    guild, g, _ = _setup()
    scr = _screen(guild, g)
    keys = _keys(scr)
    assert {"park_wagon:0", "park_animal:0"} <= keys
    scr._click("park_wagon:0")
    scr._click("park_animal:0")
    keys = _keys(scr)
    assert {"take_wagon:0", "take_animal:0"} <= keys and "park_wagon:0" not in keys
    scr._click("take_wagon:0")
    scr._click("take_animal:0")
    assert len(g.wagons) == 1 and len(g.herd) == 1


def test_the_garage_survives_a_save_round_trip():
    slot = "testworld_garage"
    if os.path.exists(persist.save_path(slot)):
        return
    guild, g, _ = _setup(bays=2)
    g.wagons[0].stash.put("Potato")
    guild.park_wagon(g, g.wagons[0])
    guild.park_animal(g, g.herd[0])
    try:
        persist.save_game(slot, guild)
        garage = persist.load_game(slot).house.garage
        assert garage.tier == 2 and [w.kind for w in garage.wagons] == ["Cart"]
        assert [n for n, _ in garage.wagons[0].stash.items] == ["Potato"]
        assert [a.species for a in garage.herd] == ["Donkey"]
    finally:
        persist.delete_world(slot)


def test_an_old_save_without_a_garage_loads_empty():
    assert not persist.garage_from_dict(None).open


def test_a_groups_ration_count_includes_what_its_wagon_carries():
    _guild, g, u = _setup(animals=0)
    u._base_inventory = []
    g.wagons[0].stash.put("Potato", 3)
    assert g.rations == 3
