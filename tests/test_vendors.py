"""The shopkeepers' faces: a vendor per node function, its portrait file, and the screens that show it."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from gartok import artwork, world
from gartok.ui.tokens import fonts as ui_fonts
from gartok.ui.vendor_panel import draw_vendor, draw_vendor_name

_VENDORS = [(n.id, fn, v) for n in world.NODES for fn, v in n.vendors.items()]


def test_every_vendor_serves_a_function_its_node_offers_and_has_a_portrait():
    assert {"shop", "tanner", "forge", "library", "bank", "trust", "property", "prison", "ledger", "arena"}.issubset({fn for _, fn, _ in _VENDORS})
    pygame.init()
    for node_id, fn, v in _VENDORS:
        assert fn in world.node(node_id).functions or (fn == "arena" and world.node(node_id).arena)
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
