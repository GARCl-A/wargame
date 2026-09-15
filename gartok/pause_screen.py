"""Pause menu: the only way back to the main menu once a campaign is running.

Esc opens it over whatever scene is showing (`resume_to`, drawn frozen behind a
dark veil); Esc again -- or RESUME -- drops back into the game. Leaving to the
main menu or quitting is a deliberate two-step from here, not a stray click on a
footer button. `native` mirrors the scene underneath so `app` draws it the same
way.
"""

import pygame

from .screen import Screen
from .theme import INK, INK_DIM, SP2, SP3, text
from .widgets import ModalScreen


class PauseScreen(ModalScreen, Screen):
    def __init__(self, fonts, resume_to, on_resume, on_menu, on_quit,
                tutorial=None, on_tutorial_toggle=None, on_tutorial_reset=None):
        super().__init__()
        self.fonts = fonts
        self.resume_to = resume_to
        self.native = getattr(resume_to, "native", False)
        self.on_resume = on_resume
        self.on_menu = on_menu
        self.on_quit = on_quit
        self.tutorial = tutorial                      # tutorial.TutorialState -- read for the ON/OFF label
        self.on_tutorial_toggle = on_tutorial_toggle
        self.on_tutorial_reset = on_tutorial_reset
        self.buttons = []

    def on_button(self, key):
        {"resume": self.on_resume, "menu": self.on_menu,
         "quit": self.on_quit,
         "tutorial_toggle": self.on_tutorial_toggle,
         "tutorial_reset": self.on_tutorial_reset}[key]()

    def card_rect(self, size):
        W, H = size
        tutorial_rows = 2 if self.tutorial is not None else 0
        card = pygame.Rect(0, 0, 320, 250 + tutorial_rows * (40 + SP2))
        card.center = (W // 2, H // 2)
        return card

    def draw_body(self, screen, card):
        f = self.fonts
        text(screen, "PAUSED", f.title, INK, (card.centerx, card.y + 26), center=True)
        text(screen, "the campaign is saved on every stop", f.body_sm, INK_DIM,
             (card.centerx, card.y + 58), center=True)

        rows = [("resume", "RESUME", True, False), ("menu", "SAVE & MAIN MENU", False, False),
                ("quit", "QUIT GAME", False, True)]
        if self.tutorial is not None:
            on = self.tutorial.enabled
            rows.append(("tutorial_toggle", f"TUTORIALS: {'ON' if on else 'OFF'}", False, False))
            rows.append(("tutorial_reset", "RESET TUTORIALS", False, False))
        by = card.y + 84
        for key, label, primary, danger in rows:
            r = pygame.Rect(card.x + SP3, by, card.w - 2 * SP3, 40)
            self.add_button(screen, r, key, label, primary=primary, danger=danger)
            by += 40 + SP2
