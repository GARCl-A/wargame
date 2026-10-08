"""The Claim's garage: open once the garrison opens, no limit, safe only while someone
garrisons it, one silent roll a day when nobody does, and its food feeds the garrison."""

import os

import pygame

from gartok import economy, orders, persist, world
from gartok.animals import Animal
from gartok.garage_screen import GarageScreen
from gartok.group import Group
from gartok.guild import Guild
from gartok.ui.tokens import fonts as ui_fonts
from gartok.wagon import Wagon
from gartok.wilds_claim_screen import WildsClaimScreen
from tests.helpers import Unit


def _setup(stage="SUSTAINING", garrisoned=True, wagons=1, species=("Ox",)):
    u = Unit("player")
    u._base_inventory = []
    g = Group([u], node=world.WILDS_TERRITORY_NODE, wagons=[Wagon() for _ in range(wagons)],
              herd=[Animal(s) for s in species])
    if garrisoned:
        g.order = orders.garrison("lumber")
    guild = Guild(None, groups=[g])
    guild.wilds_claim_stage = stage
    if stage == "SUSTAINING":
        guild.wilds_claim_sustain_days_left = economy.WILDS_CLAIM_SUSTAIN_DAYS
    return guild, g, u


def _park_all(guild, g):
    for wagon in list(g.wagons):
        assert guild.park_wagon(g, wagon, guild.claim_garage)
    for animal in list(g.herd):
        assert guild.park_animal(g, animal, guild.claim_garage)


def _roll(monkeypatch, value):
    monkeypatch.setattr("random.random", lambda: value)


def _keys(scr):
    pygame.init()
    scr.mouse = (0, 0)
    scr.draw(pygame.Surface((1280, 800)))
    return {k for k, _ in scr.buttons}


def test_the_garage_opens_with_the_garrison_and_closes_when_the_claim_is_seized():
    for stage, open_ in (("NONE", False), ("SWEPT", False), ("SUSTAINING", True), ("ESTABLISHED", True)):
        guild, _, _ = _setup(stage)
        assert guild.claim_garage_open is open_
    guild, _, _ = _setup("ESTABLISHED")
    guild.wilds_claim_owner = "seized"
    assert not guild.claim_garage_open


def test_there_is_no_limit_on_wagons_or_animals():
    guild, g, _ = _setup(wagons=3, species=("Donkey", "Donkey", "Ox"))
    _park_all(guild, g)
    assert len(guild.claim_garage.wagons) == 3 and len(guild.claim_garage.herd) == 3
    assert g.wagons == [] and g.herd == []


def test_taking_out_hands_the_wagon_back_to_the_group():
    guild, g, _ = _setup()
    wagon = g.wagons[0]
    guild.park_wagon(g, wagon, guild.claim_garage)
    assert guild.take_wagon(g, wagon, guild.claim_garage) and g.wagons == [wagon]
    assert guild.house.garage.wagons == []


def test_a_garrisoned_claim_never_loses_what_is_parked(monkeypatch):
    guild, g, _ = _setup()
    _park_all(guild, g)
    _roll(monkeypatch, 0.0)
    for _ in range(5):
        guild._claim_garage_tick()
    assert len(guild.claim_garage.wagons) == 1 and len(guild.claim_garage.herd) == 1


def test_an_empty_claim_rolls_the_flightiest_animals_chance_each_day(monkeypatch):
    guild, g, _ = _setup(species=("Donkey", "Ox"))
    _park_all(guild, g)
    g.order = None
    _roll(monkeypatch, 0.15)
    guild._claim_garage_tick()
    assert len(guild.claim_garage.wagons) == 1
    _roll(monkeypatch, 0.14)
    guild._claim_garage_tick()
    assert guild.claim_garage.empty


def test_left_alone_long_enough_it_always_goes():
    guild, g, _ = _setup(species=("Horse",))
    _park_all(guild, g)
    g.order = None
    days = 0
    while not guild.claim_garage.empty and days < 2000:
        guild._claim_garage_tick()
        days += 1
    assert guild.claim_garage.empty


def test_a_wagon_with_no_animal_has_nothing_to_bolt(monkeypatch):
    guild, g, _ = _setup(species=())
    _park_all(guild, g)
    g.order = None
    _roll(monkeypatch, 0.0)
    guild._claim_garage_tick()
    assert len(guild.claim_garage.wagons) == 1


def test_the_daily_sweep_rolls_it(monkeypatch):
    guild, g, _ = _setup()
    _park_all(guild, g)
    g.order = None
    _roll(monkeypatch, 0.0)
    guild.pass_time(24)
    assert guild.claim_garage.empty


def test_a_seized_claim_takes_what_was_parked_there():
    guild, g, _ = _setup("ESTABLISHED")
    _park_all(guild, g)
    guild.wilds_claim_seize()
    assert guild.wilds_claim_owner == "seized" and guild.claim_garage.empty


def test_an_unguarded_seizure_takes_it_too(monkeypatch):
    from gartok import campaign
    guild, g, _ = _setup("ESTABLISHED", garrisoned=False)
    guild.wilds_claim_owner = "guild"
    _park_all(guild, g)
    _roll(monkeypatch, 0.0)
    campaign._wilds_claim_seizure_check(guild)
    assert guild.claim_garage.empty


def test_a_lost_seizure_fight_takes_it_and_a_won_one_keeps_it():
    from gartok import campaign

    class Outcome:
        def __init__(self, won):
            self.won = won

    guild, g, _ = _setup("ESTABLISHED")
    _park_all(guild, g)
    campaign.resolve_wilds_seizure(guild, g, orders.Order("wilds_seizure", job="lumber"), Outcome(True))
    assert not guild.claim_garage.empty
    campaign.resolve_wilds_seizure(guild, g, orders.Order("wilds_seizure", job="lumber"), Outcome(False))
    assert guild.claim_garage.empty


def test_a_parked_wagons_food_feeds_the_garrison():
    guild, g, u = _setup(species=())
    wagon = g.wagons[0]
    wagon.stash.put("Potato", 2)
    guild.park_wagon(g, wagon, guild.claim_garage)
    guild.pass_time(24)
    assert u.unfed_days == 0
    assert wagon.rations == 1


def test_a_group_that_is_not_the_garrison_cannot_eat_from_the_garage():
    guild, g, u = _setup(species=(), garrisoned=False)
    wagon = g.wagons[0]
    wagon.stash.put("Potato", 2)
    guild.park_wagon(g, wagon, guild.claim_garage)
    guild.pass_time(24)
    assert u.unfed_days > 0 and wagon.rations == 2


def test_garaged_animals_eat_from_the_garrisons_pack_and_starve_without_it():
    guild, g, u = _setup(wagons=0, species=("Donkey",))
    u.give_to_pack("Potato")
    donkey = g.herd[0]
    guild.park_animal(g, donkey, guild.claim_garage)
    assert guild._claim_garage_feed() == [] and donkey.unfed_days == 0
    assert u.rations == 0
    guild._claim_garage_feed()
    assert donkey.unfed_days == 1


def test_parked_food_rots_like_any_other():
    guild, g, _ = _setup(species=(), garrisoned=False)
    wagon = g.wagons[0]
    wagon.stash.put("Meat")
    guild.park_wagon(g, wagon, guild.claim_garage)
    guild.pass_time(24 * 3)
    assert [n for n, _ in wagon.stash.items] == ["Rotten Food"]


def test_the_garage_screen_draws_and_parks_at_the_claim():
    guild, g, _ = _setup()
    scr = GarageScreen(ui_fonts(), guild, g, lambda: None, claim=True)
    keys = _keys(scr)
    assert {"park_wagon:0", "park_animal:0"} <= keys and "bay" not in keys
    scr._click("park_wagon:0")
    scr._click("park_animal:0")
    assert {"take_wagon:0", "take_animal:0"} <= _keys(scr)
    g.order = None
    _keys(scr)
    scr._click("take_wagon:0")
    scr._click("take_animal:0")
    assert len(g.wagons) == 1 and len(g.herd) == 1


def test_the_claim_screen_offers_the_garage_only_once_it_is_open():
    calls = []
    for stage, offered in (("SWEPT", False), ("SUSTAINING", True)):
        guild, g, _ = _setup(stage)
        scr = WildsClaimScreen(ui_fonts(), guild, g, lambda: None, lambda g: None, lambda g: None,
                               on_garage=lambda: calls.append(1))
        assert ("garage" in _keys(scr)) is offered
    for key, rect in scr.buttons:
        if key == "garage":
            scr._click(rect.center)
    assert calls == [1]


def test_the_claim_garage_survives_a_save_round_trip():
    slot = "testworld_claim_garage"
    if os.path.exists(persist.save_path(slot)):
        return
    guild, g, _ = _setup()
    g.wagons[0].stash.put("Potato")
    _park_all(guild, g)
    try:
        persist.save_game(slot, guild)
        garage = persist.load_game(slot).claim_garage
        assert garage.unlimited and [w.kind for w in garage.wagons] == ["Cart"]
        assert [n for n, _ in garage.wagons[0].stash.items] == ["Potato"]
        assert [a.species for a in garage.herd] == ["Ox"]
    finally:
        persist.delete_world(slot)


