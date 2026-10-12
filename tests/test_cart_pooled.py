"""What the group's wagons and animals hold counts like a member's pack: coins at the shops,
a Dictionary at the tavern, Lumber at the Wilds claim."""

import pygame

from gartok import items, magic, orders, world
from gartok.animals import Animal
from gartok.group import Group
from gartok.guild import Guild
from gartok.market_screen import MarketScreen
from gartok.taverna_screen import TavernaScreen
from gartok.ui.tokens import fonts as ui_fonts
from gartok.wagon import Wagon
from gartok.wilds_claim_screen import WildsClaimScreen
from tests.helpers import Unit, packed


def _party(carried=()):
    u = Unit("player")
    u._base_inventory = packed([])
    cart = Wagon("Cart")
    if carried:
        cart.give_to_pack(*carried)
    group = Group([u], node="city", wagons=[cart])
    return Guild(None, groups=[group]), group, u, cart


def test_a_cart_holds_coins_like_a_pack():
    cart = Wagon("Cart")
    cart.money = 250
    assert cart.money == 250 and cart.count_of(items.COIN_ITEM) == 250
    cart.money = 90
    assert cart.money == 90


def test_the_common_purse_counts_the_carts_coins_and_pays_across_all_of_them():
    guild, _, u, cart = _party((items.COIN_ITEM, 100))
    u.money = 40
    shop = MarketScreen(None, guild, [u], world.node("city"), lambda: None)
    assert shop.purse == 140
    shop.purse -= 120
    assert shop.purse == 20 and u.money + cart.money == 20


def test_change_and_proceeds_go_to_the_shoppers_never_into_the_cart():
    guild, _, u, cart = _party((items.COIN_ITEM, 100))
    u.money = 0
    shop = MarketScreen(None, guild, [u], world.node("city"), lambda: None)
    shop.purse += 30
    assert u.money == 30 and cart.money == 100


def test_a_pack_animal_also_counts_toward_the_purse():
    guild, group, u, _ = _party()
    donkey = Animal("Donkey")
    group.herd.append(donkey)
    donkey.money = 12
    u.money = 8
    shop = MarketScreen(None, guild, [u], world.node("city"), lambda: None)
    assert shop.purse == 20


def test_a_dictionary_in_the_cart_is_a_study_option_and_moves_to_the_student():
    guild, group, u, cart = _party(("Dictionary of Elvish", 1))
    u.languages = ["Ankarin"]
    screen = TavernaScreen(ui_fonts(), guild, list(group.members), "city", lambda: None, group=group)
    options = screen._available_study_options(u)
    assert [o["id"] for o in options] == ["Elvish"]

    magic.begin_study(u, "Elvish", screen._study_holders())
    assert u.count_of("Dictionary of Elvish") == 1 and cart.count_of("Dictionary of Elvish") == 0


def test_studying_goes_on_with_the_dictionary_left_in_the_cart():
    guild, group, u, _ = _party(("Dictionary of Elvish", 1))
    u.languages = ["Ankarin"]
    u.study_target = "Elvish"
    u.money = 1000
    group.node = "tavern"
    group.order = orders.garrison("study")
    guild.pass_time(24)
    assert u.study_progress > 0


def test_lumber_in_the_cart_counts_and_goes_into_the_claim_fences():
    guild, group, u, cart = _party(("Lumber", 3))
    u.give_to_pack("Lumber", 2)
    group.node = world.WILDS_TERRITORY_NODE
    guild.wilds_claim_stage = "CLEARED"
    pygame.init()
    scr = WildsClaimScreen(ui_fonts(), guild, group, lambda: None, lambda g: None, lambda g: None)
    assert scr._party_lumber() == 5
    scr._deposit_lumber()
    assert guild.wilds_claim_fence_lumber == 5
    assert cart.count_of("Lumber") == 0 and u.count_of("Lumber") == 0
