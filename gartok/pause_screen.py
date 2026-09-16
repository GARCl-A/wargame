"""Pause menu: the only way back to the main menu once a campaign is running.

Esc opens it over whatever scene is showing (`resume_to`, drawn frozen behind a
dark veil); Esc again -- or RESUME -- drops back into the game. Leaving to the
main menu or quitting is a deliberate two-step from here, not a stray click on a
footer button. `native` mirrors the scene underneath so `app` draws it the same
way.
"""

import pygame

from .screen import Screen
from .ui.primitives import caps, draw_button, text
from .ui.tokens import T


class PauseScreen(Screen):
    def __init__(self, fonts, resume_to, on_resume, on_menu, on_quit,
                 tutorial=None, on_tutorial_toggle=None, on_tutorial_reset=None):
        super().__init__()
        self.fonts = fonts
        self.resume_to = resume_to
        self.native = getattr(resume_to, "native", False)
        self.on_resume = on_resume
        self.on_menu = on_menu
        self.on_quit = on_quit
        self.tutorial = tutorial  # tutorial.TutorialState -- read for the ON/OFF label
        self.on_tutorial_toggle = on_tutorial_toggle
        self.on_tutorial_reset = on_tutorial_reset
        self._buttons = []

    def _click(self, px):
        for key, rect in self._buttons:
            if rect.collidepoint(px):
                {"resume": self.on_resume,
                 "menu": self.on_menu,
                 "quit": self.on_quit,
                 "tutorial_toggle": self.on_tutorial_toggle,
                 "tutorial_reset": self.on_tutorial_reset}[key]()
                return

    def draw(self, screen):
        W, H = screen.get_size()

        if self.resume_to:
            try:
                self.resume_to.mouse = (-1, -1)
                self.resume_to.draw(screen)
            except Exception:
                screen.fill(T.TABLE)
        else:
            screen.fill(T.TABLE)

        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((6, 7, 12, 210))
        screen.blit(veil, (0, 0))

        tutorial_rows = 2 if self.tutorial is not None else 0
        card = pygame.Rect(0, 0, 320, 250 + tutorial_rows * 48)
        card.center = (W // 2, H // 2)

        pygame.draw.rect(screen, T.STEEL, card)
        pygame.draw.rect(screen, T.STEEL_LINE, card, 1)

        f = self.fonts
        caps(screen, f.title, "PAUSED", (card.centerx, card.y + 26), T.TX, center=True)
        text(screen, f.body_sm, "the campaign is saved on every stop", 
             (card.centerx, card.y + 58), T.TX_FAINT, center=True)

        rows = [
            ("resume", "RESUME", True, False), 
            ("menu", "SAVE & MAIN MENU", False, False),
            ("quit", "QUIT GAME", False, True)
        ]
        
        if self.tutorial is not None:
            on = self.tutorial.enabled
            rows.append(("tutorial_toggle", f"TUTORIALS: {'ON' if on else 'OFF'}", False, False))
            rows.append(("tutorial_reset", "RESET TUTORIALS", False, False))

        self._buttons.clear()
        by = card.y + 84
        for key, label, primary, danger in rows:
            r = pygame.Rect(card.x + T.S * 3, by, card.w - 2 * T.S * 3, 40)
            draw_button(screen, {}, r, label, primary=primary, danger=danger, 
                        mpos=self.mouse, fnt=f.label)
            self._buttons.append((key, r))
            by += 40 + T.S
