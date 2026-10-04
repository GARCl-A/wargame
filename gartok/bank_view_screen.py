"""The City vault, read-only: what the guild's strongbox holds and how full it
is. Moving gear in or out needs a band standing at the bank (`bank_screen.py`)."""

import pygame

from . import items
from .screen import Screen
from .theme import set_pointer
from .ui.primitives import (
    caps,
    contained,
    draw_button,
    ellipsize,
    footer_bar,
    hline,
    panel,
    scrollbar,
    text,
)
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

ROW_H = T.S * 5
CARD_MAX_W = T.S * 90


class BankViewScreen(Screen):
    native = True

    def __init__(self, fonts, guild, on_done):
        super().__init__()
        self.fonts = fonts
        self._F = ui_fonts()
        self.guild = guild
        self.on_done = on_done
        self.buttons = []
        self._hot = False
        self._scroll = 0
        self._max_scroll = 0

    def add_button(self, surf, rect, key, label, *, enabled=True, primary=False,
                   danger=False, font=None, sub=None):
        draw_button(surf, self._F, rect, label, sub=sub, primary=primary, danger=danger,
                    enabled=enabled, mpos=self.mouse, fnt=font)
        if enabled:
            self.buttons.append((key, rect))
            self._hot = self._hot or rect.collidepoint(self.mouse)

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            self._scroll = max(0, min(self._max_scroll, self._scroll - event.y * ROW_H))
            return
        super().handle_event(event)

    def _click(self, pos):
        for key, rect in self.buttons:
            if key == "done" and rect.collidepoint(pos):
                self.on_done()

    def handle_escape(self):
        self.on_done()
        return True

    def draw(self, screen):
        F = self._F
        W, H = screen.get_size()
        m = T.S * 3
        screen.fill(T.TABLE)
        self.buttons, self._hot = [], False

        text(screen, F["titleb"], "CITY VAULT", (m, m - 2), T.TX)
        caps(screen, F["micro"], "View only -- take a band to the bank in the City to move gear",
             (m, m + 30), T.TX_FAINT)

        avail = H - (m + T.S * 7) - T.S * 9
        rows_h = max(1, len(self.guild.bank_items)) * ROW_H
        card = pygame.Rect(0, m + T.S * 7, min(CARD_MAX_W, W - 2 * m), min(avail, T.S * 11 + rows_h))
        card.centerx = W // 2
        panel(screen, card)

        stash = list(self.guild.bank_items)
        load, cap = self.guild.bank_load, self.guild.bank_capacity
        x, w = card.x + T.S * 2, card.w - T.S * 4
        y = card.y + T.S * 2
        caps(screen, F["microb"], f"Stored {load:g} / {cap:g} kg", (x, y), T.TX)
        bar = pygame.Rect(x, y + T.S * 2, w, T.S)
        pygame.draw.rect(screen, T.TABLE, bar)
        pygame.draw.rect(screen, T.STEEL_LINE, bar, 1)
        frac = min(1.0, load / cap) if cap else 0
        if frac:
            pygame.draw.rect(screen, T.BLOOD if load > cap else T.BRASS,
                             (bar.x + 1, bar.y + 1, int((bar.w - 2) * frac), bar.h - 2))
        top = bar.bottom + T.S * 2
        hline(screen, x, x + w, top - T.S)

        view = pygame.Rect(x, top, w, card.bottom - top - T.S)
        total_h = max(1, len(stash)) * ROW_H
        self._max_scroll = max(0, total_h - view.h)
        self._scroll = min(self._scroll, self._max_scroll)
        with contained(screen, view):
            if not stash:
                text(screen, F["body"], "The strongbox is empty.", (view.x, view.y), T.TX_FAINT)
            for i, (name, qty) in enumerate(stash):
                ry = view.y + i * ROW_H - self._scroll
                tag = items.item_tag(name)
                text(screen, F["bodyb"], ellipsize(name, F["bodyb"], w - T.S * 30), (x, ry + 4), T.TX)
                if tag:
                    caps(screen, F["micro"], tag, (x, ry + 22), T.TX_FAINT)
                text(screen, F["body"], f"x{qty}", (x + w - T.S * 12, ry + 8), T.TX_MUTED, right=True)
                text(screen, F["body"], f"{items.item_weight(name) * qty:g} kg", (x + w, ry + 8),
                     T.TX_MUTED, right=True)
                hline(screen, x, x + w, ry + ROW_H - 2)
        if self._max_scroll:
            scrollbar(screen, pygame.Rect(view.x, view.y, view.w + T.S * 2, view.h), self._scroll, self._max_scroll, total_h)

        footer_bar(self, screen, F, primary=("done", "BACK TO GUILD"), hint=None)
        set_pointer(self._hot)
