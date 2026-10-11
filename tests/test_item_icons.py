import pygame
import pytest

from gartok.ui.item_icons import KINDS, draw_item_icon
from gartok.ui.tokens import T


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_every_icon_kind_paints_something_inside_its_rect(kind):
    surf = pygame.Surface((96, 96))
    surf.fill((0, 0, 0))
    draw_item_icon(surf, pygame.Rect(16, 16, 64, 64), kind, (200, 200, 210), T.BRASS)
    assert surf.get_at((20, 20)) != (0, 0, 0)               # the plate
    assert any(surf.get_at((x, 48)) not in ((0, 0, 0, 255), T.STEEL) for x in range(24, 72))   # the silhouette
    assert surf.get_at((4, 4)) == (0, 0, 0)                 # nothing outside the rect


def test_every_catalogue_item_has_an_icon_of_its_own():
    from gartok import item_icon, items
    bare = [n for n in items.all_items() if item_icon._base(n) not in item_icon.ICONS]
    assert not bare, f"add these to item_icon.ICONS: {bare}"


def test_every_item_draws_and_rarity_sets_the_rim():
    from gartok import item_icon, items
    surf = pygame.Surface((64, 64))
    for name, defn in items.all_items().items():
        kind, _tone, rim, _scale, _shape = item_icon.icon_spec(name)
        assert kind in KINDS, name
        assert (rim is None) == (defn.rarity == items.ItemRarity.COMMON), name
        item_icon.draw_icon(surf, pygame.Rect(0, 0, 64, 64), name)


def test_sizes_scrolls_and_dictionaries_share_one_icon_and_an_unknown_item_still_draws():
    from gartok import item_icon
    assert item_icon.icon_spec("Large Axe")[::3] == item_icon.icon_spec("Axe")[::3]
    assert item_icon.icon_spec("Scroll of Sleep")[:2] == item_icon.icon_spec("Scroll")[:2]
    assert item_icon.icon_spec("Dictionary of Elvish")[:2] == item_icon.icon_spec("Dictionary")[:2]
    assert item_icon.icon_spec("Meat (3 days old)")[0] == "steak"
    assert item_icon.icon_spec("Nothing Of The Kind")[0] == "coin"


def test_a_pack_row_and_a_slot_show_the_items_icon():
    from gartok.ui import loadout_panel
    from gartok.ui.tokens import fonts
    pygame.init()
    F = fonts()
    surf = pygame.Surface((400, 120))
    surf.fill((0, 0, 0))
    row = pygame.Rect(8, 8, 360, 48)
    loadout_panel.pack_row(surf, F, row, ("Axe", "WEAPON", 3.0, 1, False), selected=False, mouse=(0, 0))
    icon_cx, icon_cy = row.x + 8 + 22 + loadout_panel.ICON // 2, row.centery
    plate = surf.get_at((row.x + 8 + 22 + 2, icon_cy - loadout_panel.ICON // 2 + 2))
    assert plate[:3] == tuple(loadout_panel.T.STEEL)
    assert any(surf.get_at((icon_cx + dx, icon_cy + dy))[:3] not in (tuple(loadout_panel.T.STEEL), (0, 0, 0))
               for dx in range(-8, 8) for dy in range(-8, 8))


def test_icon_strip_stacks_equal_items_and_sums_up_what_does_not_fit():
    from gartok.ui import loadout_panel
    from gartok.ui.tokens import fonts
    pygame.init()
    F = fonts()
    surf = pygame.Surface((300, 60))
    surf.fill((0, 0, 0))
    loadout_panel.icon_strip(surf, F, pygame.Rect(0, 0, 300, 40), ["Rope", "Torch", "Torch"])
    assert surf.get_at((12, 20))[:3] != (0, 0, 0)
    narrow = pygame.Surface((60, 60))
    narrow.fill((0, 0, 0))
    loadout_panel.icon_strip(narrow, F, pygame.Rect(0, 0, 60, 40), ["Rope", "Torch", "Axe", "Salt"])
    assert any(narrow.get_at((x, y))[:3] != (0, 0, 0) for x in range(28, 60) for y in range(10, 30))


def test_the_vault_the_forge_the_quest_card_and_the_sheet_draw_with_icons():
    from gartok import items
    from gartok.bank_view_screen import BankViewScreen
    from gartok.combatant import Combatant
    from gartok.crafting_screen import CraftingScreen
    from gartok.guild import Guild
    from gartok.holdings import Stash
    from gartok.sheet_panel import draw_sheet
    from gartok.ui import quest_panel
    from gartok.ui.tokens import fonts
    from gartok.unit import Unit
    from tests.helpers import packed
    pygame.init()
    F = fonts()
    u = Unit("player")
    u._base_inventory = packed(["Rope", "Torch", "Torch"])
    u.recipes = list(items.CRAFTING_RECIPES)[:2]
    g = Guild([u])
    g.bank = Stash(50, packed(["Rope", "Axe"]))
    surf = pygame.Surface((1400, 900))
    vault = BankViewScreen(None, g, lambda: None)
    vault.mouse = (0, 0)
    vault.draw(surf)
    forge = CraftingScreen(None, g, g.groups[0], lambda: None)
    forge.mouse = (0, 0)
    forge.draw(surf)
    draw_sheet(surf, pygame.Rect(0, 0, 520, 900), Combatant(u), F)
    quest_panel.quest_list(surf, F, pygame.Rect(0, 0, 600, 100),
                           [{"name": "Hides", "accepted_by": "A", "days_left": 2, "progress": (1, 3, "1sqm Hide"), "tags": ()}])
