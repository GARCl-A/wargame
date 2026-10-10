"""Sideways scroll over a row of equal columns (member bags, stores).

A screen keeps one `ColumnScroll`, calls `fit` each frame to learn which
columns are on screen and how wide, feeds it the wheel, and draws `hint`
under the row so the hidden ones are not a surprise.
"""

import pygame

from .primitives import text
from .tokens import T


class ColumnScroll:
    def __init__(self):
        self.pos = 0
        self.max = 0

    def fit(self, n, width, gap, col_min, col_max):
        """-> (slice of the n columns to draw, their width)."""
        cap = max(1, (width + gap) // (col_min + gap))
        shown = min(cap, n)
        self.max = max(0, n - cap)
        self.pos = max(0, min(self.pos, self.max))
        col_w = min(col_max, max(col_min, (width - (shown - 1) * gap) // shown)) if shown else col_min
        return slice(self.pos, self.pos + shown), col_w

    def wheel(self, event, over=True):
        """True when the event scrolled the row: a sideways wheel, or the
        plain wheel with Shift held, or (with `over`) a plain wheel."""
        if self.max <= 0:
            return False
        hx, hy = getattr(event, "x", 0), getattr(event, "y", 0)
        if hx:
            step = hx
        elif hy and (over or pygame.key.get_mods() & pygame.KMOD_SHIFT):
            step = -hy
        else:
            return False
        self.pos = max(0, min(self.max, self.pos + step))
        return True

    def hint(self, surf, F, area):
        if self.max <= 0:
            return
        if self.max - self.pos > 0:
            text(surf, F["body_sm"], f"{self.max - self.pos} more →  (scroll)",
                 (area.right - 8, area.bottom + 8), T.TX_FAINT, right=True)
        if self.pos > 0:
            text(surf, F["body_sm"], f"← {self.pos} more  (scroll)",
                 (area.x + 8, area.bottom + 8), T.TX_FAINT)
