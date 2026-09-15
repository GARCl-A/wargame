"""Generic alert popup used for starvation, death, and hunger notifications."""

import pygame

from .screen import Screen
from .theme import ACCENT, DANGER, INK, SP2, SP3, text
from .widgets import ModalScreen


class AlertScreen(ModalScreen, Screen):
    def __init__(self, fonts, resume_to, title, messages, on_done, is_danger=False):
        super().__init__()
        self.fonts = fonts
        self.resume_to = resume_to
        self.native = getattr(resume_to, "native", False)
        self.title = title
        self.messages = messages
        self.on_done = on_done
        self.is_danger = is_danger
        self.buttons = []

    def on_button(self, key):
        if key == "ok":
            self.on_done()

    def card_rect(self, size):
        W, H = size
        f = self.fonts
        title_surf = f.title.render(self.title, True, INK)
        msg_surfs = [f.body.render(m, True, INK) for m in self.messages]
        box_w = max([title_surf.get_width()] + [s.get_width() for s in msg_surfs]) + SP3 * 2
        box_w = max(box_w, 400)
        box_h = SP3 * 2 + title_surf.get_height() + SP2 + sum(s.get_height() + 4 for s in msg_surfs) + SP3 + 40
        r = pygame.Rect(0, 0, box_w, box_h)
        r.center = (W // 2, H // 2)
        return r

    def draw_body(self, screen, card):
        f = self.fonts
        title_col = DANGER if self.is_danger else ACCENT
        y = card.y + SP3
        text(screen, self.title, f.title, title_col, (card.x + SP3, y))
        y += f.title.get_height() + SP2
        for m in self.messages:
            text(screen, m, f.body, INK, (card.x + SP3, y))
            y += f.body.get_height() + 4
        y += SP3

        bw, bh = max(120, f.label.size("OK")[0] + 32), 40
        btn_rect = pygame.Rect(card.right - SP3 - bw, card.bottom - SP3 - bh, bw, bh)
        self.add_button(screen, btn_rect, "ok", "OK")
