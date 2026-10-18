"""Sideways scroll over a row of equal columns (member bags, stores).

A screen keeps one `ColumnScroll`, calls `fit` each frame to learn which
columns are on screen and how wide, feeds it the wheel, and draws `hint`
under the row so the hidden ones are not a surprise.
"""

import pygame

from .primitives import draw_button
from .tokens import T


class ColumnScroll:
    def __init__(self):
        self.pos = 0
        self.max = 0
        self.shown = 0
        self.total = 0
        self.prev_rect = None
        self.next_rect = None

    def fit(self, n, width, gap, col_min, col_max):
        """-> (slice of the n columns to draw, their width)."""
        cap = max(1, (width + gap) // (col_min + gap))
        shown = min(cap, n)
        self.total = n
        self.shown = shown
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

    def click(self, pos):
        if self.max <= 0:
            return False
        if self.prev_rect is not None and self.prev_rect.collidepoint(pos):
            self.pos = max(0, self.pos - 1)
            return True
        if self.next_rect is not None and self.next_rect.collidepoint(pos):
            self.pos = min(self.max, self.pos + 1)
            return True
        return False

    def hovering(self, pos):
        return bool((self.prev_rect and self.prev_rect.collidepoint(pos))
                    or (self.next_rect and self.next_rect.collidepoint(pos)))

    def hint(self, surf, F, area, mpos=(-1, -1)):
        self.prev_rect = None
        self.next_rect = None
        if self.max <= 0:
            return
        track = pygame.Rect(area.x, area.bottom + 2, area.w, 4)
        pygame.draw.rect(surf, T.STEEL_LINE, track)
        if self.total > 0:
            thumb_w = max(24, round(area.w * (self.shown / self.total)))
            thumb_x = area.x + round((area.w - thumb_w) * (self.pos / self.max))
            pygame.draw.rect(surf, T.BRASS, pygame.Rect(thumb_x, track.y, thumb_w, 4))
        btn_w, btn_h = 128, 22
        by = area.bottom + 8
        if self.pos > 0:
            self.prev_rect = pygame.Rect(area.x, by, btn_w, btn_h)
            draw_button(surf, F, self.prev_rect, f"<  {self.pos} MORE", mpos=mpos)
        if self.max - self.pos > 0:
            self.next_rect = pygame.Rect(area.right - btn_w, by, btn_w, btn_h)
            draw_button(surf, F, self.next_rect, f"{self.max - self.pos} MORE  >", mpos=mpos)
