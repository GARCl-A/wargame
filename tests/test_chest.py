"""The locked chest (chest.py): a pack item with its own DC, picked outside
battle. Same d20 + mod idiom as every other check in the game (`fixed_d20`
pins it, same as a death save or the guard test)."""

import random

from tests.helpers import fixed_d20, Unit
from gartok import chest, data


def test_a_clean_pick_consumes_the_chest_and_hands_over_gems():
    u = Unit("player")
    u.mod_dexterity = 0
    u._base_inventory = [data.CHEST_ITEM]
    with fixed_d20(data.CHEST_DC):              # exactly clears the lock
        opened, gems = chest.try_open(u)

    assert opened and gems >= 2
    assert data.CHEST_ITEM not in u._base_inventory
    assert u._base_inventory.count(data.GEM_ITEM) == gems


def test_a_miss_costs_nothing_the_chest_stays_put():
    u = Unit("player")
    u.mod_dexterity = 0
    u._base_inventory = [data.CHEST_ITEM]
    with fixed_d20(data.CHEST_DC - 1):           # one short
        opened, gems = chest.try_open(u)

    assert not opened and gems == 0
    assert u._base_inventory == [data.CHEST_ITEM]   # untouched -- try again any time


def test_no_chest_in_the_pack_is_a_clean_no_op():
    u = Unit("player")
    u._base_inventory = []
    with fixed_d20(20):
        assert chest.try_open(u) == (False, 0)


def test_gems_are_sellable_at_an_explicit_price_not_the_weight_fallback():
    from gartok import economy
    assert economy.PRICES[data.GEM_ITEM] == 60
    assert economy.buy_price(data.GEM_ITEM) > round(data.item_weight(data.GEM_ITEM) * 2)


def test_gear_screen_right_click_offers_to_open_a_chest_and_resolves_it():
    """The chest-opening action lives in the gear screen's existing right-click
    send-to menu (a design decision the plan doc left open) -- OPEN THE CHEST
    only appears when the single thing picked is a chest, and clicking it
    rolls `chest.try_open` in place rather than moving the item anywhere."""
    import os
    import pygame
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((1, 1))
    from gartok.gear_screen import GearScreen
    from gartok.theme import Fonts

    random.seed(1)
    u = Unit("player")
    u.mod_dexterity = 0
    u._base_inventory = [data.CHEST_ITEM]
    guild = _guild_of(u)
    gs = GearScreen(Fonts(), guild, lambda: None)
    surface = pygame.Surface((1600, 900))
    gs.draw(surface)                              # populates self.sources

    rect, unit, loc = next(s for s in gs.sources if s[1] is u and s[2] == 0)
    gs._open_menu(rect.center)
    assert any(kind == "open" for kind, _arg in gs.menu["rows"])
    gs.draw(surface)                              # populates menu["hits"]

    open_hit = next(r for r, kind, _arg in gs.menu["hits"] if kind == "open")
    with fixed_d20(data.CHEST_DC):
        gs._menu_click(open_hit.center)

    assert data.CHEST_ITEM not in u._base_inventory
    assert data.GEM_ITEM in u._base_inventory
    assert gs.notice and "picks the lock" in gs.notice


def _guild_of(*units):
    from gartok.guild import Guild
    return Guild(list(units))
