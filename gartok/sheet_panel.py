"""The full character sheet, drawn as a modal over whichever screen opens it.

The rendering lives in `gartok.ui.sheet_card` (density="full"); this module is
the `SheetModalMixin` a screen mixes in to open it (`open_sheet`, `sheet_open`,
`close_sheet_on_click`, `sheet_badge`, `draw_sheet_modal`).
"""

import pygame

from .combatant import Combatant
from .ui import primitives
from .ui.sheet_card import draw_sheet as _draw_sheet_card
from .ui.sheet_card import sheet_height, unit_to_ch
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

PANEL_W = 620
PANEL_H = sheet_height("full") + 96


# ---------------------------------------------------------------- mixin
class SheetModalMixin:
    """Lets a screen pop the full character sheet over itself. The sheet needs a
    `Combatant` view (to-hit, ammo, hand state), so a roster member is wrapped in
    a throwaway one -- fresh, so it reads "full HP, standing".

    A screen mixes this in, calls `open_sheet(unit)` from its own card hit, guards
    its click handler with `if self.close_sheet_on_click(): return` and ends its
    `draw` with `self.draw_sheet_modal(surface, fonts)`.
    """

    _sheet_unit = None

    def open_sheet(self, unit):
        self._sheet_unit = unit

    @property
    def sheet_open(self):
        return self._sheet_unit is not None

    def close_sheet_on_click(self):
        """True (and closes the sheet) if a modal was up -- the click is spent on
        dismissing it and the screen should do nothing else with it."""
        if self._sheet_unit is None:
            return False
        self._sheet_unit = None
        return True

    def sheet_badge(self, screen, topright, fonts=None):
        """Draw a small 'i' disc at `topright` (the card's inspect affordance) and
        return its rect for the screen to hit-test. `fonts` is accepted for the
        callers' existing call shape but unused -- this always draws in the
        war-table palette regardless of the host screen's own font system."""
        F = ui_fonts()
        r = pygame.Rect(0, 0, 20, 20)
        r.topright = topright
        hot = r.collidepoint(self.mouse)
        pygame.draw.circle(screen, T.STEEL_HI, r.center, 9)
        pygame.draw.circle(screen, T.BRASS if hot else T.STEEL_LINE, r.center, 9, 1)
        primitives.text(screen, F["bodyb"], "i", r.center, T.BRASS if hot else T.TX_MUTED,
                        center=True)
        return r

    def draw_sheet_modal(self, screen, fonts=None):
        if self._sheet_unit is None:
            return
        F = ui_fonts()
        ch = unit_to_ch(Combatant(self._sheet_unit))
        rect = primitives.modal_card(screen, (PANEL_W, PANEL_H), veil=True)
        pad = T.S * 2
        inner = pygame.Rect(rect.x + pad, rect.y + pad, rect.w - 2 * pad, 0)
        _, tooltip = _draw_sheet_card(screen, F, inner, ch, density="full", mouse=self.mouse)
        primitives.text(screen, F["micro"], "click anywhere to close",
                        (rect.centerx, rect.bottom - 18), T.TX_FAINT, center=True)
        if tooltip:
            primitives.draw_tooltip(screen, F, tooltip, self.mouse)


def draw_sheet(screen, rect, u, fonts=None, mouse=None):
    """Legacy entry point -- draws the same modal content at an arbitrary
    rect instead of through `SheetModalMixin`. Kept for direct callers
    (tests included); `fonts` is unused, drawing is always war-table style."""
    F = ui_fonts()
    ch = unit_to_ch(u if isinstance(u, Combatant) else Combatant(u))
    _, tooltip = _draw_sheet_card(screen, F, pygame.Rect(rect.x, rect.y, rect.w, 0),
                                  ch, density="full", mouse=mouse)
    if tooltip and mouse:
        primitives.draw_tooltip(screen, F, tooltip, mouse)
