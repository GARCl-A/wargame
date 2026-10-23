"""Vocation screen: the first choice of a new guild.

The guild picks one of six trades (`vocations.py`). It is permanent, the perk is
the whole guild's, and the draft pool that follows always holds one of each of
the trade's races. `on_done(vocation_id)` hands the pick to the draft.
"""

import pygame

from . import vocations
from .item_icon import vocation_icon
from .screen import Screen
from .ui.hub_frame import button_width, hub_button
from .ui.primitives import ellipsize, small_caps, text
from .ui.tokens import T
from .ui.vocation_panel import draw_steps, draw_vocation_cards

STEPS = ("Vocation", "Draft", "Banner")


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
        return [{"id": v.id, "name": v.name, "motto": v.motto, "races": list(v.races), "perk": v.perk,
                 "dormant": not v.active, "icon": vocation_icon(v.id)}
                for v in vocations.VOCATIONS.values()]

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
        pad = round(max(T.S * 3, min(T.S * 6, W * 0.025)))
        screen.fill(T.TABLE)

        r = small_caps(screen, F["hub_title"], F["hub_title_sc"], "Choose a Vocation", (pad, pad), T.TX)
        text(screen, F["hub_body"], "The trade your guild is founded on. It cannot be changed later; "
             "its perk belongs to every member, and the draft brings one of each of its races.",
             (pad, r.bottom + T.S), T.TX_MUTED)
        draw_steps(screen, F, (W - pad, pad + T.S), STEPS, 0)
        head_bottom = r.bottom + T.S * 2 + F["hub_body"].get_height()

        foot_h = T.S * 6
        foot_y = H - pad - foot_h
        pygame.draw.line(screen, T.STEEL_LINE, (pad, foot_y - T.S * 2), (W - pad, foot_y - T.S * 2))
        view = pygame.Rect(pad, head_bottom + T.S * 3, W - 2 * pad, foot_y - T.S * 5 - head_bottom)
        self.card_rects = draw_vocation_cards(screen, F, view, self._cards(), self.selected, self.mouse)

        label = "Continue to the draft"
        bw = button_width(F, label)
        self.continue_rect = pygame.Rect(W - pad - bw, foot_y, bw, foot_h)
        hub_button(screen, F, self.continue_rect, label, primary=True, enabled=self.selected is not None,
                   mpos=self.mouse)

        room = self.continue_rect.x - pad - T.S * 4
        v = vocations.get(self.selected)
        line = (f"{v.name}: the draft pool holds one of each of {', '.join(v.races)}." if v
                else "Pick the trade your guild is founded on.")
        y = foot_y + (foot_h - F["hub_bodyb"].get_height() - F["hub_sub"].get_height() - 2) // 2
        text(screen, F["hub_bodyb"], ellipsize(line, F["hub_bodyb"], room), (pad, y), T.TX if v else T.TX_MUTED)
        text(screen, F["hub_sub"], "Esc · quit", (pad, y + F["hub_bodyb"].get_height() + 2), T.TX_FAINT)
