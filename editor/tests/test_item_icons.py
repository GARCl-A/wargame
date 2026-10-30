import pygame
import pytest
from editor.ui.item_icons import KINDS, draw_icon, draw_item_icon
from editor.ui.tokens import T

@pytest.mark.parametrize("kind", sorted(KINDS))
def test_every_icon_kind_paints_something_inside_its_rect(kind):
    surf = pygame.Surface((96, 96))
    surf.fill((0, 0, 0))
    draw_item_icon(surf, pygame.Rect(16, 16, 64, 64), kind, (200, 200, 210), T.BRASS)
    assert surf.get_at((20, 20)) != (0, 0, 0)               # the plate
    assert any(surf.get_at((x, 48)) not in ((0, 0, 0, 255), T.STEEL) for x in range(24, 72))   # the silhouette
    assert surf.get_at((4, 4)) == (0, 0, 0)                 # nothing outside the rect


def test_every_item_draws_and_rarity_sets_the_rim():
    from gartok import item_icon, items
    surf = pygame.Surface((64, 64))
    for name, defn in items.all_items().items():
        kind, _tone, rim, _scale, _shape = item_icon.icon_spec(name)
        assert kind in KINDS, name
        assert (rim is None) == (defn.rarity == items.ItemRarity.COMMON), name
        draw_icon(surf, pygame.Rect(0, 0, 64, 64), name)


def test_a_pack_row_and_a_slot_show_the_items_icon():
    from editor.ui import loadout_panel
    from editor.ui.tokens import fonts
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
    from editor.ui import loadout_panel
    from editor.ui.tokens import fonts
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


def test_icon_list_draws_each_item_and_cuts_off_at_the_edge():
    import pygame

    from editor.ui.loadout_panel import icon_list
    from editor.ui.tokens import T, fonts
    pygame.init()
    surf = pygame.Surface((400, 40))
    F = fonts()
    names = ["1sqm Hide", "Paper", "Ink"]
    wide = icon_list(surf, F, (0, 10), names, T.TX_MUTED, 400)
    assert wide > icon_list(surf, F, (0, 10), names[:1], T.TX_MUTED, 400)
    assert icon_list(surf, F, (0, 10), names, T.TX_MUTED, 60) <= 100


def test_every_vocation_has_an_icon_that_draws():
    import pygame

    from gartok import item_icon, vocations
    from editor.ui.item_icons import KINDS, draw_item_icon
    pygame.init()
    assert set(item_icon.VOCATION_ICONS) == set(vocations.VOCATIONS)
    for vid in vocations.VOCATIONS:
        kind, tone, shape = item_icon.vocation_icon(vid)
        assert kind in KINDS
        draw_item_icon(pygame.Surface((48, 48)), pygame.Rect(0, 0, 48, 48), kind, tone, **shape)


def test_item_instance_draws_icon_without_error():
    from gartok import item_icon, items
    inst = items.create_instance("Dagger", qty=2)
    kind, _tone, rim, _scale, _shape = item_icon.icon_spec(inst)
    assert kind in KINDS
    surf = pygame.Surface((32, 32))
    draw_icon(surf, pygame.Rect(0, 0, 32, 32), inst)
