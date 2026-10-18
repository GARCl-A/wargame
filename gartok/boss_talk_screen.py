"""The line each arena boss says before the guild's first bout against them (`arena.boss_talk`).

One card per speaker, in order; the last one's button starts the fight. No choices: it is flavour."""

import pygame

from .screen import Screen
from .ui.boss_line import draw_boss_line
from .ui.primitives import set_pointer
from .ui.tokens import T


class BossTalkScreen(Screen):
    native = True

    def __init__(self, fonts, cards, on_done):
        super().__init__()
        self.fonts = fonts
        self.cards = list(cards)
        self.on_done = on_done
        self.index = 0
        self.button = None

    @property
    def last(self):
        return self.index >= len(self.cards) - 1

    def advance(self):
        if self.index >= len(self.cards):
            return
        self.index += 1
        if self.index >= len(self.cards):
            self.on_done()

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.advance()
            return
        super().handle_event(event)

    def _click(self, pos):
        if self.button is not None and self.button.collidepoint(pos):
            self.advance()

    def draw(self, screen):
        screen.fill(T.TABLE)
        if self.index >= len(self.cards):
            return
        n = len(self.cards)
        d = {**self.cards[self.index], "button": "FIGHT" if self.last else "NEXT",
             "step": f"{self.index + 1} / {n}" if n > 1 else ""}
        self.button = draw_boss_line(screen, self.fonts, d, self.mouse)
        set_pointer(self.button.collidepoint(self.mouse))
