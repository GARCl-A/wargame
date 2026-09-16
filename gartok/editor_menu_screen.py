"""Editor hub: pick what to build.

Reached from the main menu's EDITOR button. Two doors: the character creator
(`char_editor_screen`) and the scenario creator (`map_editor_screen`).
`on_character` / `on_scenario` open them; `on_back` returns to the main menu.
"""

import pygame

from .screen import Screen
from .ui.primitives import caps, draw_button, text, contained
from .ui.tokens import T


class EditorMenuScreen(Screen):
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
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "back":
                    self.on_back()
                return

    def draw(self, screen):
        f = self.fonts
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self.cards = []
        self.buttons = []

        mpos = self.mouse

        caps(screen, f.title, "EDITOR", (T.S * 4, T.S * 4), T.TX)
        text(screen, f.body, "build content outside a campaign", 
             (T.S * 4, T.S * 4 + 32), T.TX_MUTED)

        card_w = min(560, W - 2 * T.S * 4)
        card_h = 104
        x = (W - card_w) // 2
        y = max(T.S * 4 + 96, H // 2 - card_h - T.S * 3)

        self._card(screen, pygame.Rect(x, y, card_w, card_h), "character",
                   "CHARACTER CREATOR",
                   "roll and hand-edit a full GARTOK character; save it to the "
                   "NPC library", True, mpos)
        y += card_h + T.S * 3
        self._card(screen, pygame.Rect(x, y, card_w, card_h), "scenario",
                   "SCENARIO CREATOR",
                   "paint a battle map -- walls, torches and deployment zones; "
                   "save it to the map library",
                   self.on_scenario is not None, mpos)

        back = pygame.Rect(T.S * 4, H - T.S * 4 - 30, 120, 30)
        draw_button(screen, {}, back, "BACK", ghost=True, mpos=mpos, fnt=f.label)
        self.buttons.append(("back", back))

    def _card(self, screen, rect, key, title, blurb, enabled, mpos):
        f = self.fonts
        hov = enabled and rect.collidepoint(mpos)
        
        bg = T.STEEL_HI if hov else T.STEEL
        bc = T.BRASS if hov else T.STEEL_LINE
        
        with contained(screen, rect):
            pygame.draw.rect(screen, bg, rect)
            pygame.draw.rect(screen, bc, rect, 1)
            
            tcol = T.TX if enabled else T.TX_FAINT
            caps(screen, f.heading, title, (rect.x + T.S * 3, rect.y + T.S * 2), T.BRASS if hov else tcol)
            
            text(screen, f.body_sm, blurb,
                 (rect.x + T.S * 3, rect.y + T.S * 2 + 26), T.TX_MUTED if enabled else T.TX_FAINT)
            
            if not enabled:
                caps(screen, f.label, "LOCKED",
                     (rect.right - T.S * 3, rect.y + T.S * 2), T.TX_FAINT, right=True)
                 
        self.cards.append((key, rect, enabled))
