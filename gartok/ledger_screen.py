"""Ledger Hold's desk: the pygame window over `ledger.LedgerDesk`."""

import pygame

from .ledger import LedgerDesk
from .screen import Screen
from .ui import hub_body as hb
from .ui.hub_frame import MARGIN, hub_button
from .ui.primitives import set_pointer, text, wrap
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


class LedgerScreen(Screen, LedgerDesk):
    native = True
    framed = True

    def tutorial_key(self):
        return "ledger"

    def __init__(self, fonts, guild, group, on_done):
        super().__init__()
        LedgerDesk.__init__(self, guild, group, on_done)   # Screen ends the cooperative chain
        self.fonts = fonts
        self._F = ui_fonts()
        self.buttons = []              # [(key, rect)]
        self._hot = False

    def _reset_buttons(self):
        self.buttons = []
        self._hot = False

    def add_button(self, surf, rect, key, label, *, enabled=True, primary=False):
        hub_button(surf, self._F, rect, label, primary=primary, enabled=enabled, mpos=self.mouse)
        if enabled:
            self.buttons.append((key, rect))
            self._hot = self._hot or rect.collidepoint(self.mouse)

    def _click(self, px):
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                self._act(key)
                return

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self._F
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self._reset_buttons()

        panels = self.panels()
        bottom = H - T.S * 4 - (T.S * 3 if self.notice else 0)
        body = pygame.Rect(MARGIN, 0, W - 2 * MARGIN, bottom)
        gap = T.S * 3
        w = min(T.S * 72, (body.w - gap * (len(panels) - 1)) // len(panels))
        for i, p in enumerate(panels):
            self._draw_panel(screen, pygame.Rect(body.x + i * (w + gap), body.y, w, body.h), p)

        if self.notice:
            text(screen, F["hub_body"], self.notice, (MARGIN, H - T.S * 3), T.BRASS)
        set_pointer(self._hot)

    def _draw_panel(self, screen, rect, p):
        F = self._F
        inner = hb.draw_panel(screen, F, rect, p["title"], p["aside"])
        y = inner.y
        for line in p["lines"]:
            for ln in wrap(F["hub_body"], line, inner.w):
                text(screen, F["hub_body"], ln, (inner.x, y), T.TX_MUTED)
                y += F["hub_body"].get_linesize()
            y += T.S
        if p["rows"]:
            y = hb.draw_facts(screen, F, (inner.x, inner.y), inner.w, p["rows"])
        if p["button"]:
            key, label, enabled = p["button"]
            b = pygame.Rect(inner.x, y + T.S, inner.w, T.S * 6 + 4)
            self.add_button(screen, b, key, label, enabled=enabled, primary=True)
            y = b.bottom
        if p["warn"]:
            text(screen, F["hub_body"], p["warn"], (inner.x, y + T.S * 2), T.BLOOD)
