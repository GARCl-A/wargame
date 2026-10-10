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
