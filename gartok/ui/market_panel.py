"""The brass chip that follows the cursor while something is dragged on the market."""

import pygame

from .primitives import text
from .tokens import T, mix


def drag_ghost(surf, F, label, mpos):
    """The brass chip that follows the cursor while something is dragged."""
    gx, gy = mpos
    r = pygame.Rect(gx + 12, gy + 6, F["body"].size(label)[0] + 2 * T.S, 20)
    pygame.draw.rect(surf, mix(T.BRASS, T.STEEL, .85), r)
    pygame.draw.rect(surf, T.BRASS, r, 1)
    text(surf, F["body"], label, r.center, T.TX, center=True)
