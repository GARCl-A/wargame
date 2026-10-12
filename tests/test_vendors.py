"""The shopkeepers' faces: a vendor per node function, its portrait file, and the screens that show it."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from gartok import artwork, world
from gartok.crafting_screen import CraftingScreen
from gartok.guild import Guild
from gartok.library_mission_screen import LibraryMissionScreen
from gartok.library_screen import LibraryScreen
from gartok.market_screen import MarketScreen
from gartok.tanner_screen import TannerScreen
from gartok.ui.tokens import fonts as ui_fonts
from gartok.ui.vendor_panel import draw_vendor, draw_vendor_name
from gartok.unit import Unit

_VENDORS = [(n.id, fn, v) for n in world.NODES for fn, v in n.vendors.items()]


def test_every_vendor_serves_a_function_its_node_offers_and_has_a_portrait():
    assert {"shop", "tanner", "forge", "library", "bank", "trust", "property", "prison", "ledger"}.issubset({fn for _, fn, _ in _VENDORS})
    pygame.init()
    for node_id, fn, v in _VENDORS:
        assert fn in world.node(node_id).functions
        assert artwork.portrait(None, v.portrait, 32) is not None, v.portrait
        assert v.name and v.card["caption"] == f"{v.race} {v.role}"


def test_every_shop_has_a_keeper():
    shops = {n.id for n in world.NODES if "shop" in n.functions}
    assert all(world.node(s).vendors for s in shops)


def test_vendor_names_are_distinct():
    names = [name for _, name in {(node_id, v.name) for node_id, _, v in _VENDORS}]
    assert len(set(names)) == len(names)


def test_vendor_lookup_is_none_for_a_node_without_a_face():
    assert world.vendor("apothecary", "apothecary") is None
    assert world.vendor("ancient_ruins", "ancient_ruins") is None
    assert world.vendor("city", "bank").name == "Elysia"
    assert world.vendor("prison", "prison").name == "Captain Caelen"
    assert world.vendor("ledger_hold", "ledger").name == "Commander Varkas"


def test_no_card_draws_nothing():
    pygame.init()
    surf = pygame.Surface((200, 100))
    assert draw_vendor(surf, ui_fonts(), (0, 0), None) == 0
    assert draw_vendor_name(surf, ui_fonts(), (5, 5), None) == 5


def test_screens_draw_with_the_keeper_and_without():
    pygame.init()
    F = ui_fonts()
    guild = Guild([Unit("player") for _ in range(2)], node="city")
    group = guild.groups[0]
    shoppers = list(group.members)
    from gartok.bank_screen import BankScreen
    from gartok.ledger_screen import LedgerScreen
    from gartok.prison_screen import PrisonScreen

    screens = [
        MarketScreen(F, guild, shoppers, world.node("market"), lambda: None),
        MarketScreen(F, guild, shoppers, world.node("mine"), lambda: None),
        LibraryScreen(F, guild, shoppers, world.node("library"), lambda: None),
        CraftingScreen(F, guild, group, lambda: None, vendor=world.vendor("smith", "forge")),
        CraftingScreen(F, guild, group, lambda: None),
        TannerScreen(F, guild, group, lambda: None),
        LibraryMissionScreen(F, guild, group, lambda: None),
        BankScreen(F, guild, shoppers, lambda: None),
        PrisonScreen(F, guild, shoppers, world.node("prison"), lambda: None),
        LedgerScreen(F, guild, group, lambda: None),
    ]
    for scr in screens:
        scr.mouse = (0, 0)
        scr.draw(pygame.Surface((1280, 720)))
    assert screens[0].vendor_function == "shop" and screens[2].vendor_function == "library"
    assert screens[5].vendor_card["name"] == world.vendor("tanner", "tanner").name
    assert screens[7].vendor.name == "Elysia"
    assert screens[8].vendor.name == "Captain Caelen"
