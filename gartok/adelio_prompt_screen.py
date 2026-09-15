"""Prompt screen shown after defeating Adelio in the pit title bout."""

import pygame

from .screen import Screen
from .theme import ACCENT, INK_DIM, LINE_SOFT, RADIUS, SP4, SURFACE_2, panel, text
from .widgets import ButtonsMixin


class AdelioPromptScreen(ButtonsMixin, Screen):
    native = True

    def __init__(self, fonts, on_recruit, on_leave):
        super().__init__()
        self.fonts = fonts
        self.on_recruit = on_recruit
        self.on_leave = on_leave
        self.buttons = []
        self._hot = False

    def _click(self, px):
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "recruit":
                    self.on_recruit()
                elif key == "leave":
                    self.on_leave()
                return

    def draw(self, screen):
        f = self.fonts
        W, H = screen.get_size()
        screen.fill((18, 19, 24))
        self._reset_buttons()

        cw, ch = 540, 240
        card = pygame.Rect((W - cw) // 2, (H - ch) // 2, cw, ch)
        panel(screen, card, fill=SURFACE_2, border=LINE_SOFT, radius=RADIUS)

        text(screen, "THE FALLEN CHAMPION", f.title, ACCENT, (card.x + SP4, card.y + SP4))
        lines = [
            "Adelio Small-Knife lies defeated on the sands of the Pit.",
            "His championship title is lost, but his blade is still sharp.",
            "Do you want to convince him to join your guild?",
        ]
        y = card.y + 64
        for ln in lines:
            text(screen, ln, f.body, INK_DIM, (card.x + SP4, y))
            y += 24

        bw, bh = 200, 38
        by = card.bottom - SP4 - bh

        rec_r = pygame.Rect(card.x + SP4, by, bw, bh)
        self.add_button(screen, rec_r, "recruit", "TALK TO ADELIO", primary=True)

        leave_r = pygame.Rect(card.right - SP4 - bw, by, bw, bh)
        self.add_button(screen, leave_r, "leave", "LEAVE HIM")
