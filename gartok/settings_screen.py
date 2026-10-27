"""Settings screen: adjust player preferences outside of combat.

Displays configurable options from `settings.SPEC`. Clicking an option cycles its value.
Given the app's `tutorial` state, it also toggles and resets the tutorial cards.
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

    def __init__(self, fonts, on_back, tutorial=None, on_tutorial_toggle=None, on_tutorial_reset=None):
        super().__init__()
        self.F = fonts
        self.on_back = on_back
        self.tutorial = tutorial
        self.on_tutorial_toggle = on_tutorial_toggle
        self.on_tutorial_reset = on_tutorial_reset
        self.buttons = []
        self._reset_note = None

    def handle_escape(self):
        self.on_back()
        return True

    def _click(self, px):
        for key, rect in self.buttons:
            if not rect.collidepoint(px):
                continue
            if key == "back":
                self.on_back()
            elif key == "tutorial_toggle":
                if self.on_tutorial_toggle:
                    self.on_tutorial_toggle()
            elif key == "tutorial_reset":
                if self.on_tutorial_reset:
                    self.on_tutorial_reset()
                    self._reset_note = "tutorials reset"
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
            name, choices, _ = settings.SPEC[k]
            val = settings.get(k)

            text(screen, F["bodyb"], name, (r.x + T.S * 2, r.y + 12), T.BRASS if hov else T.TX)
            text(screen, F["body"], str(val), (r.right - T.S * 2, r.y + 12), T.BRASS if hov else T.TX_MUTED, right=True)

            self.buttons.append((f"set_{k}", r))
            y += BTN_H + GAP

        if self.tutorial is not None:
            r_tut = pygame.Rect(cx, y, card_w, BTN_H)
            hov = r_tut.collidepoint(mouse)
            panel(screen, r_tut, hover=hov)
            text(screen, F["bodyb"], "TUTORIALS", (r_tut.x + T.S * 2, r_tut.y + 12), T.BRASS if hov else T.TX)
            val = "ON" if self.tutorial.enabled else "OFF"
            text(screen, F["body"], val, (r_tut.right - T.S * 2, r_tut.y + 12), T.BRASS if hov else T.TX_MUTED, right=True)
            self.buttons.append(("tutorial_toggle", r_tut))
            y += BTN_H + GAP

            r_reset = pygame.Rect(cx, y, card_w, BTN_H)
            draw_button(screen, F, r_reset, self._reset_note or "RESET TUTORIALS", mpos=mouse)
            self.buttons.append(("tutorial_reset", r_reset))
            y += BTN_H + GAP

        # Back button
        r_back = pygame.Rect(cx, y + T.S * 2, card_w, 36)
        draw_button(screen, F, r_back, "BACK", mpos=mouse)
        self.buttons.append(("back", r_back))

        text(screen, F["body"], "[Esc] back", (MARGIN, H - 24), T.TX_FAINT)
        set_pointer(any(rect.collidepoint(mouse) for _, rect in self.buttons))
