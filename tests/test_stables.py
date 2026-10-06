"""The Stables: buying and selling a wagon, animals and tack with the party's coin."""

import pygame

from gartok import animals, economy, items, orders, wagon, world
from gartok.group import HERD_BASE, Group
from gartok.guild import Guild
from gartok.stables_screen import StablesScreen
from gartok.ui.tokens import fonts as ui_fonts
from tests.helpers import Unit


def _stables(coins, w=None, pets=(), wis=0):
    a, b = Unit("player"), Unit("player")
    a.gold, b.gold = coins, 0
    a.mod_wisdom = b.mod_wisdom = wis
    g = Group([a, b], node="farm", wagon=w, animals=list(pets))
    guild = Guild(None, groups=[g])
    return StablesScreen(ui_fonts(), guild, g, lambda: None), g, a


def _keys(scr):
    pygame.init()
    scr.mouse = (0, 0)
    scr.draw(pygame.Surface((1280, 800)))
    return {k for k, _ in scr.buttons}


def test_the_stables_are_on_the_farm_outside_the_city_and_the_map_can_send_a_group_there():
    assert world.node("farm").stable and not world.node("city").stable
    path, hours = world.route("city", "farm")
    assert path == ["city", "farm"] and hours > 0
    assert world.node("farm").jurisdiction is None
    assert "stable" in orders.INTERACTIVE_KINDS


def test_buying_the_wagon_takes_the_coin_and_gives_the_group_a_wagon():
    scr, g, a = _stables(wagon.WAGON_PRICE + 7)
    assert "buy_wagon" in _keys(scr)
    scr._click("buy_wagon")
    assert g.wagon is not None and a.gold == 7 and g.wagon._group is g


def test_the_wagon_is_refused_when_the_party_cannot_pay():
    scr, g, _ = _stables(wagon.WAGON_PRICE - 1)
    assert "buy_wagon" not in _keys(scr)
    scr._click("buy_wagon")
    assert g.wagon is None


def test_an_animal_is_bought_with_no_tack_and_no_wagon_needed():
    scr, g, a = _stables(1000)
    scr._click("buy:Donkey")
    assert [x.species for x in g.animals] == ["Donkey"] and g.animals[0].tack is None
    assert a.gold == 1000 - animals.SPECIES["Donkey"]["price"]


def test_the_group_cannot_keep_a_herd_beyond_its_leaders_control():
    scr, g, a = _stables(10_000, pets=[animals.Animal("Donkey") for _ in range(HERD_BASE)])
    assert not any(k.startswith("buy:") for k in _keys(scr))
    scr._click("buy:Ox")
    assert len(g.animals) == HERD_BASE and a.gold == 10_000


def test_a_wise_leader_can_buy_more_animals():
    scr, g, _ = _stables(10_000, pets=[animals.Animal("Donkey") for _ in range(HERD_BASE)], wis=2)
    assert "buy:Ox" in _keys(scr)
    scr._click("buy:Ox")
    assert len(g.animals) == HERD_BASE + 1


def test_tack_is_bought_onto_the_animal_and_decides_its_role():
    scr, g, a = _stables(1000, pets=[animals.Animal("Donkey")])
    scr._click(f"fit:0:{animals.HARNESS}")
    assert g.animals[0].role == "draft" and a.gold == 1000 - items.get(animals.HARNESS).price
    assert not any(k.startswith("fit:") for k in _keys(scr))


def test_an_animal_wears_only_one_set_of_tack():
    scr, g, a = _stables(1000, pets=[animals.Animal("Donkey", tack=animals.PACK_SADDLE)])
    scr._click(f"fit:0:{animals.HARNESS}")
    assert g.animals[0].tack == animals.PACK_SADDLE and a.gold == 1000


def test_tack_that_cannot_be_afforded_is_not_offered():
    scr, g, _ = _stables(items.get(animals.HARNESS).price - 1, pets=[animals.Animal("Donkey")])
    keys = _keys(scr)
    assert f"fit:0:{animals.HARNESS}" not in keys


def test_taking_tack_off_returns_it_to_the_leaders_pack():
    scr, g, _ = _stables(0, pets=[animals.Animal("Donkey", tack=animals.HARNESS)])
    scr._click("unfit:0")
    assert g.animals[0].tack is None and g.leader.count_of(animals.HARNESS) == 1


def test_a_loaded_animal_has_to_be_unloaded_before_it_is_sold_or_unfitted():
    pet = animals.Animal("Donkey", tack=animals.PACK_SADDLE)
    pet.stash.put("Rope")
    scr, g, _ = _stables(0, pets=[pet])
    scr._click("sell:0")
    scr._click("unfit:0")
    assert g.animals == [pet] and pet.tack == animals.PACK_SADDLE
    assert "unload" in scr.notice


def test_selling_an_animal_pays_the_resale_and_keeps_the_tack():
    scr, g, _ = _stables(0, pets=[animals.Animal("Ox", tack=animals.HARNESS)])
    before = g.leader.gold
    scr._click("sell:0")
    assert g.animals == []
    assert g.leader.gold - before == int(animals.SPECIES["Ox"]["price"] * economy.SELL_FACTOR)
    assert g.leader.count_of(animals.HARNESS) == 1


def test_the_wagon_can_only_be_sold_empty():
    w = wagon.Wagon()
    w.stash.items.append(items.create_instance("Rope"))
    scr, g, _ = _stables(0, w)
    scr._click("sell_wagon")
    assert g.wagon is not None

    g.wagon.stash.items.clear()
    assert "sell_wagon" in _keys(scr)
    scr._click("sell_wagon")
    assert g.wagon is None


def test_the_screen_draws_in_every_state():
    pets = [animals.Animal("Donkey", tack=animals.HARNESS), animals.Animal("Ox"),
            animals.Animal("Donkey", tack=animals.PACK_SADDLE)]
    for w, p in ((None, ()), (wagon.Wagon(), ()), (wagon.Wagon(), pets), (None, pets)):
        scr, _, _ = _stables(500, w, p)
        _keys(scr)
