"""Vocation screen: the first choice of a new guild.

The guild picks one of six trades (`vocations.py`). It is permanent, the perk is
the whole guild's, and the draft pool that follows always holds one of each of
the trade's races. `on_done(vocation_id)` hands the pick to the draft.
"""

import pygame

from . import vocations
from .screen import Screen
from .ui.primitives import draw_button, text
from .ui.tokens import T
from .ui.vocation_panel import draw_vocation_cards


class VocationScreen(Screen):
    native = True

    def __init__(self, fonts, on_done, tutorial=None):
        super().__init__()
        self.F = fonts
        self.on_done = on_done
        self.tutorial = tutorial
        self.selected = None
        self.card_rects = []
        self.continue_rect = None

    def _cards(self):
        return [{"id": v.id, "name": v.name, "races": list(v.races), "perk": v.perk,
                 "dormant": not v.active} for v in vocations.VOCATIONS.values()]

    def _click(self, px):
        for rect, vid in self.card_rects:
            if rect.collidepoint(px):
                self.selected = vid
                return
        if self.continue_rect and self.continue_rect.collidepoint(px) and self.selected:
            self.on_done(self.selected)

    def tutorial_key(self):
        if self.tutorial is not None and "draft.intro" not in self.tutorial.seen:
            return "draft.intro"
        return "draft.vocation"

    def draw(self, screen):
        F = self.F
        W, H = screen.get_size()
        pad = T.S * 4
        screen.fill(T.TABLE)
        text(screen, F["titleb"], "CHOOSE A VOCATION", (pad, pad - 2), T.TX)
        text(screen, F["body"], "The trade your guild is founded on. It cannot be changed later; "
             "its perk belongs to every member.", (pad, pad + 30), T.TX_MUTED)

        view = pygame.Rect(pad, pad + 70, W - 2 * pad, H - 2 * pad - 70 - T.S * 7)
        self.card_rects = draw_vocation_cards(screen, F, view, self._cards(), self.selected, self.mouse)

        btn_w = T.S * 25
        self.continue_rect = pygame.Rect(W - pad - btn_w, H - pad - T.S * 5, btn_w, T.S * 5)
        draw_button(screen, F, self.continue_rect, "CONTINUE", primary=True,
                    enabled=self.selected is not None, mpos=self.mouse)
        text(screen, F["body_sm"], "[Esc] quit", (pad, H - 18), T.TX_FAINT)
