"""Settings screen: adjust player preferences outside of combat.

Displays configurable options from `settings.SPEC`. Clicking an option cycles its value.
"""

import pygame

from . import settings
from .screen import Screen
from .ui.primitives import draw_button, panel, set_pointer, text
from .ui.tokens import T

MARGIN = T.S * 4
BTN_W = 440
BTN_H = 44
GAP = T.S * 2


class SettingsScreen(Screen):
    native = True

    def __init__(self, fonts, on_back):
        super().__init__()
        self.F = fonts
        self.on_back = on_back
        self.buttons = []

    def handle_escape(self):
        self.on_back()
        return True

    def _click(self, px):
        for key, rect in self.buttons:
            if not rect.collidepoint(px):
                continue
            if key == "back":
                self.on_back()
            elif key.startswith("set_"):
                opt = key[4:]
                settings.cycle(opt)
            return

    def draw(self, screen):
        F = self.F
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        mouse = self.mouse
        self.buttons = []

        text(screen, F["big"], "SETTINGS", (MARGIN, MARGIN), T.TX)
        text(screen, F["body"], "player preferences and system configuration",
             (MARGIN, MARGIN + 32), T.TX_MUTED)

        card_w = min(520, W - 2 * MARGIN)
        cx = (W - card_w) // 2
        y = MARGIN + 84

        for k in settings.SPEC:
            r = pygame.Rect(cx, y, card_w, BTN_H)
            hov = r.collidepoint(mouse)
            panel(screen, r, hover=hov)
            lbl = settings.label(k)
            name, choices, _ = settings.SPEC[k]
            val = settings.get(k)

            text(screen, F["bodyb"], name, (r.x + T.S * 2, r.y + 12), T.BRASS if hov else T.TX)
            text(screen, F["body"], str(val), (r.right - T.S * 2, r.y + 12), T.BRASS if hov else T.TX_MUTED, right=True)

            self.buttons.append((f"set_{k}", r))
            y += BTN_H + GAP

        # Back button
        r_back = pygame.Rect(cx, y + T.S * 2, card_w, 36)
        draw_button(screen, F, r_back, "BACK", mpos=mouse)
        self.buttons.append(("back", r_back))

        text(screen, F["body"], "[Esc] back", (MARGIN, H - 24), T.TX_FAINT)
        set_pointer(any(rect.collidepoint(mouse) for _, rect in self.buttons))
