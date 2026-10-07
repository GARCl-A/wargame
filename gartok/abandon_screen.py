"""Travelling with a broken wagon means leaving it behind: this asks first.

The card names the wagon and what it still carries. MANAGE CARGO opens the loot
screen on that cargo, to move it into the packs before the wagon goes; LEAVE IT
drops the wagon, cargo and all; STAY cancels the trip.
"""

import pygame

from .screen import Screen
from .ui.primitives import caps, draw_button, modal_card, set_pointer, text, wrap
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


class AbandonScreen(Screen):
    native = True

    def __init__(self, fonts, wagon, on_manage, on_leave, on_stay):
        super().__init__()
        self.fonts = fonts
        self._F = fonts if (isinstance(fonts, dict) and "body" in fonts) else ui_fonts()
        self.wagon = wagon
        self.on_manage = on_manage
        self.on_leave = on_leave
        self.on_stay = on_stay
        self.buttons = []

    def handle_escape(self):
        self.on_stay()
        return True

    def _click(self, pos):
        for key, rect in self.buttons:
            if rect.collidepoint(pos):
                {"manage": self.on_manage, "leave": self.on_leave, "stay": self.on_stay}[key]()
                return

    def _lines(self):
        w = self.wagon
        lines = [f"The {w.kind.lower()} is broken: it cannot move. Setting out means leaving it behind."]
        stacks = sum(q for _, q in w.stash.items)
        if stacks:
            lines.append(f"It still holds {stacks} item(s), {w.stash.load:g} kg, and they go with it "
                         "unless you unload them into the packs first.")
        return lines

    def draw(self, screen):
        F = self._F
        screen.fill(T.TABLE)
        self.buttons.clear()
        card = modal_card(screen, (min(620, screen.get_width() - 48), 300))
        caps(screen, F["big"], "ABANDON THE WAGON?", (card.x + T.S * 3, card.y + T.S * 3), T.TX)

        y = card.y + 64
        for line in self._lines():
            for ln in wrap(F["body"], line, card.w - T.S * 6):
                text(screen, F["body"], ln, (card.x + T.S * 3, y), T.TX_MUTED)
                y += 24
            y += 8

        bh = 38
        by = card.bottom - T.S * 3 - bh
        gap = T.S * 2
        keys = [("leave", "LEAVE IT BEHIND", True)]
        if self.wagon.stash.items:
            keys.insert(0, ("manage", "MANAGE CARGO", False))
        keys.append(("stay", "STAY", False))
        bw = (card.w - T.S * 6 - gap * (len(keys) - 1)) // len(keys)
        for i, (key, label, danger) in enumerate(keys):
            r = pygame.Rect(card.x + T.S * 3 + i * (bw + gap), by, bw, bh)
            draw_button(screen, F, r, label, primary=danger, danger=danger, mpos=self.mouse)
            self.buttons.append((key, r))
        set_pointer(any(r.collidepoint(self.mouse) for _, r in self.buttons))
