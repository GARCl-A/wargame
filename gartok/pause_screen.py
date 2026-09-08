"""Pause menu: the only way back to the main menu once a campaign is running.

Esc opens it over whatever scene is showing (`resume_to`, drawn frozen behind a
dark veil); Esc again -- or RESUME -- drops back into the game. Leaving to the
main menu or quitting is a deliberate two-step from here, not a stray click on a
footer button. `native` mirrors the scene underneath so `app` draws it the same
way.
"""

import pygame

from .screen import Screen
from .theme import (ACCENT, DANGER, INK, INK_DIM, LINE_SOFT, RADIUS, SP2, SP3,
                    SURFACE_1, SURFACE_2, SURFACE_3, panel, set_pointer, text)


class PauseScreen(Screen):
    def __init__(self, fonts, resume_to, on_resume, on_menu, on_quit):
        super().__init__()
        self.fonts = fonts
        self.resume_to = resume_to
        self.native = getattr(resume_to, "native", False)
        self.on_resume = on_resume
        self.on_menu = on_menu
        self.on_quit = on_quit
        self.buttons = []

    def _click(self, px):
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                {"resume": self.on_resume, "menu": self.on_menu,
                 "quit": self.on_quit}[key]()
                return

    def draw(self, screen):
        f = self.fonts
        W, H = screen.get_size()
        try:
            self.resume_to.mouse = (-1, -1)      # keep its hover art quiet
            self.resume_to.draw(screen)
        except Exception:
            screen.fill(SURFACE_1)
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((6, 7, 12, 210))
        screen.blit(veil, (0, 0))

        card = pygame.Rect(0, 0, 320, 250)
        card.center = (W // 2, H // 2)
        panel(screen, card, fill=SURFACE_2, border=LINE_SOFT, width=2, radius=RADIUS)
        text(screen, "PAUSED", f.title, INK, (card.centerx, card.y + 26), center=True)
        text(screen, "the campaign is saved on every stop", f.body_sm, INK_DIM,
             (card.centerx, card.y + 58), center=True)

        self.buttons = []
        rows = [("resume", "RESUME", ACCENT), ("menu", "SAVE & MAIN MENU", INK),
                ("quit", "QUIT GAME", DANGER)]
        by = card.y + 84
        for key, label, col in rows:
            r = pygame.Rect(card.x + SP3, by, card.w - 2 * SP3, 40)
            hov = r.collidepoint(self.mouse)
            panel(screen, r, fill=SURFACE_3 if hov else SURFACE_1,
                  border=col if hov else LINE_SOFT, width=1, radius=RADIUS)
            text(screen, label, f.body_bd, col, r.center, center=True)
            self.buttons.append((key, r))
            by += 40 + SP2

        set_pointer(any(r.collidepoint(self.mouse) for _, r in self.buttons))
