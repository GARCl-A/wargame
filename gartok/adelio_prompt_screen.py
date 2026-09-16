"""Prompt screen shown after defeating Adelio in the pit title bout."""

import pygame

from .screen import Screen
from .ui.tokens import T
from .ui.primitives import draw_button, text, caps


class AdelioPromptScreen(Screen):
    native = True

    def __init__(self, fonts, on_recruit, on_leave):
        super().__init__()
        self.fonts = fonts
        self.on_recruit = on_recruit
        self.on_leave = on_leave
        self.buttons = []

    def _click(self, px):
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "recruit":
                    self.on_recruit()
                elif key == "leave":
                    self.on_leave()
                return

    def draw(self, screen):
        F = self.fonts
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self.buttons.clear()

        cw, ch = 540, 240
        card = pygame.Rect((W - cw) // 2, (H - ch) // 2, cw, ch)
        pygame.draw.rect(screen, T.STEEL, card)
        pygame.draw.rect(screen, T.STEEL_LINE, card, 1)

        caps(screen, F.title, "THE FALLEN CHAMPION", (card.x + T.S * 3, card.y + T.S * 3), T.TX)
        
        lines = [
            "Adelio Small-Knife lies defeated on the sands of the Pit.",
            "His championship title is lost, but his blade is still sharp.",
            "Do you want to convince him to join your guild?",
        ]
        
        y = card.y + 64
        for ln in lines:
            text(screen, F.body, ln, (card.x + T.S * 3, y), T.TX_MUTED)
            y += 24

        bw, bh = 200, 38
        by = card.bottom - T.S * 3 - bh

        rec_r = pygame.Rect(card.x + T.S * 3, by, bw, bh)
        draw_button(screen, {}, rec_r, "TALK TO ADELIO", primary=True, mpos=self.mouse, fnt=F.label)
        self.buttons.append(("recruit", rec_r))

        leave_r = pygame.Rect(card.right - T.S * 3 - bw, by, bw, bh)
        draw_button(screen, {}, leave_r, "LEAVE HIM", mpos=self.mouse, fnt=F.label)
        self.buttons.append(("leave", leave_r))
