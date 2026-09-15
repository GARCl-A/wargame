"""Prompt screen shown when the group is ambushed on the road."""

import pygame

from .screen import Screen
from .theme import (DANGER, ACCENT_INK, INK, RADIUS,
                    SP4, SURFACE_2, SURFACE_3, panel, text)


class AmbushScreen(Screen):
    native = True

    def __init__(self, fonts, group, order, on_fight):
        super().__init__()
        self.fonts = fonts
        self.group = group
        self.order = order
        self.on_fight = on_fight
        self.buttons = []

    def _click(self, px):
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "fight":
                    self.on_fight(self.group, self.order)
                return

    def draw(self, screen):
        f = self.fonts
        W, H = screen.get_size()
        screen.fill((24, 18, 18))  # Dark reddish background for danger
        self.buttons = []

        cw, ch = 540, 240
        card = pygame.Rect((W - cw) // 2, (H - ch) // 2, cw, ch)
        panel(screen, card, fill=SURFACE_2, border=DANGER, radius=RADIUS)

        text(screen, "AMBUSH!", f.title, DANGER, (card.x + SP4, card.y + SP4))
        lines = [
            f"Your group was ambushed on the road!",
            "Enemies block the path ahead.",
            "There is no escaping this fight."
        ]
        y = card.y + 72
        for ln in lines:
            text(screen, ln, f.body, INK, (card.x + SP4, y))
            y += 24

        bw, bh = 200, 38
        by = card.bottom - SP4 - bh

        # Only one option: fight
        fight_r = pygame.Rect(card.x + (cw - bw) // 2, by, bw, bh)
        hov = fight_r.collidepoint(self.mouse)
        panel(screen, fight_r, fill=DANGER if hov else SURFACE_3, border=DANGER, radius=RADIUS)
        text(screen, "FIGHT", f.body_bd, ACCENT_INK if hov else DANGER, fight_r.center, center=True)
        self.buttons.append(("fight", fight_r))
