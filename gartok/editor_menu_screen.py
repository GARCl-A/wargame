"""Editor hub: pick what to build.

Reached from the main menu's EDITOR button. Two doors: the character creator
(`char_editor_screen`) and the scenario creator (`map_editor_screen`).
`on_character` / `on_scenario` open them; `on_back` returns to the main menu.
"""

import pygame

from .screen import Screen
from .theme import (ACCENT, INK, INK_DIM, INK_FAINT, LINE_SOFT, MARGIN, RADIUS,
                    SP3, SP4, SURFACE_2, SURFACE_3, panel, set_pointer, text)
from .widgets import ButtonsMixin


class EditorMenuScreen(ButtonsMixin, Screen):
    native = True

    def __init__(self, fonts, on_character, on_back, on_scenario=None):
        super().__init__()
        self.fonts = fonts
        self.on_character = on_character
        self.on_scenario = on_scenario
        self.on_back = on_back
        self.cards = []                       # [(key, rect, enabled)] -- the two feature tiles
        self.buttons = []                     # [(key, rect)] -- the footer BACK button

    def _click(self, px):
        for key, rect, enabled in self.cards:
            if not rect.collidepoint(px) or not enabled:
                continue
            if key == "character":
                self.on_character()
            elif key == "scenario":
                self.on_scenario()
            return
        key = self.buttons_hit(px)
        if key == "back":
            self.on_back()

    def draw(self, screen):
        f = self.fonts
        W, H = screen.get_size()
        screen.fill((18, 19, 24))
        self.cards = []
        self._reset_buttons()

        text(screen, "EDITOR", f.title, INK, (MARGIN, MARGIN))
        text(screen, "build content outside a campaign", f.body, INK_DIM,
             (MARGIN, MARGIN + 32))

        card_w = min(560, W - 2 * MARGIN)
        card_h = 104
        x = (W - card_w) // 2
        y = max(MARGIN + 96, H // 2 - card_h - SP3)

        self._card(screen, pygame.Rect(x, y, card_w, card_h), "character",
                   "CHARACTER CREATOR",
                   "roll and hand-edit a full GARTOK character; save it to the "
                   "NPC library", True)
        y += card_h + SP3
        self._card(screen, pygame.Rect(x, y, card_w, card_h), "scenario",
                   "SCENARIO CREATOR",
                   "paint a battle map -- walls, torches and deployment zones; "
                   "save it to the map library",
                   self.on_scenario is not None)

        back = pygame.Rect(MARGIN, H - MARGIN - 30, 120, 30)
        self.add_button(screen, back, "back", "BACK", font=f.label)

        set_pointer(self._hot or any(r.collidepoint(self.mouse) and e for _, r, e in self.cards))

    def _card(self, screen, rect, key, title, blurb, enabled):
        f = self.fonts
        hov = enabled and rect.collidepoint(self.mouse)
        panel(screen, rect, fill=SURFACE_3 if hov else SURFACE_2,
              border=ACCENT if hov else LINE_SOFT, width=2 if hov else 1, radius=RADIUS)
        tcol = INK if enabled else INK_FAINT
        text(screen, title, f.heading, ACCENT if hov else tcol, (rect.x + SP4, rect.y + SP3))
        text(screen, blurb, f.body_sm, INK_DIM if enabled else INK_FAINT,
             (rect.x + SP4, rect.y + SP3 + 26))
        if not enabled:
            text(screen, "LOCKED", f.label, INK_FAINT,
                 (rect.right - SP4, rect.y + SP3), right=True)
        self.cards.append((key, rect, enabled))
