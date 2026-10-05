"""Pause menu: the only way back to the main menu once a campaign is running.

Esc opens it over whatever scene is showing (`resume_to`, drawn frozen behind a
dark veil); Esc again -- or RESUME -- drops back into the game. SAVE AS...
snapshots the campaign under a name the player types (it shows up on the guild's
saves list); it is greyed out where there is no campaign yet to save (the draft,
the editors). Leaving to the main menu or quitting is a deliberate two-step from
here, not a stray click on a footer button. `native` mirrors the scene underneath
so `app` draws it the same way.
"""

import pygame

from .screen import Screen
from .ui.primitives import caps, draw_button, modal_card, panel, set_pointer, text
from .ui.tokens import T

MAX_SAVE_NAME = 40


class PauseScreen(Screen):
    def __init__(self, fonts, resume_to, on_resume, on_menu, on_quit,
                 tutorial=None, on_tutorial_toggle=None, on_tutorial_reset=None,
                 on_save_as=None, can_save=True):
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
        self.on_save_as = on_save_as      # callable(name) or None: no SAVE AS row
        self.can_save = can_save          # False: the row shows greyed out and does nothing
        self.naming = False
        self.name_buf = ""
        self.saved_note = None
        self._buttons = []

    def handle_escape(self):
        if self.naming:
            self.naming = False
            return True
        return False

    def handle_event(self, event):
        if self.naming and event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                name = self.name_buf.strip() or "Manual save"
                self.on_save_as(name)
                self.saved_note = f"saved: {name}"
                self.naming, self.name_buf = False, ""
            elif event.key == pygame.K_BACKSPACE:
                self.name_buf = self.name_buf[:-1]
            elif event.unicode and event.unicode.isprintable() and len(self.name_buf) < MAX_SAVE_NAME:
                self.name_buf += event.unicode
            return
        super().handle_event(event)

    def _click(self, px):
        for key, rect in self._buttons:
            if rect.collidepoint(px):
                if key == "save_as":
                    self.naming, self.saved_note = True, None
                    return
                {"resume": self.on_resume,
                 "menu": self.on_menu,
                 "quit": self.on_quit,
                 "tutorial_toggle": self.on_tutorial_toggle,
                 "tutorial_reset": self.on_tutorial_reset}[key]()
                return

    def draw(self, screen):
        if self.resume_to:
            try:
                self.resume_to.mouse = (-1, -1)
                self.resume_to.draw(screen)
            except Exception:  # noqa: BLE001 -- resume_to is whatever scene was live; never let its redraw crash the pause overlay
                screen.fill(T.TABLE)
        else:
            screen.fill(T.TABLE)

        tutorial_rows = (2 if self.tutorial is not None else 0) + (1 if self.on_save_as else 0)
        card = modal_card(screen, (320, 250 + tutorial_rows * 48), veil=True)

        f = self.fonts
        caps(screen, f["big"], "PAUSED", (card.centerx, card.y + 26), T.TX, center=True)
        text(screen, f["body_sm"], "the campaign is saved on every stop",
             (card.centerx, card.y + 58), T.TX_FAINT, center=True)

        rows = [("resume", "RESUME", True, False)]
        if self.on_save_as:
            rows.append(("save_as", "SAVE AS...", False, False))
        rows += [("menu", "SAVE & MAIN MENU", False, False),
                 ("quit", "QUIT GAME", False, True)]
        
        if self.tutorial is not None:
            on = self.tutorial.enabled
            rows.append(("tutorial_toggle", f"TUTORIALS: {'ON' if on else 'OFF'}", False, False))
            rows.append(("tutorial_reset", "RESET TUTORIALS", False, False))

        if self.naming:
            box = pygame.Rect(card.x + T.S * 3, card.y + 78, card.w - 2 * T.S * 3, 40)
            panel(screen, box, hover=True, width=2)
            text(screen, f["body"], self.name_buf + "|", (box.x + T.S, box.centery - 9), T.TX)
            text(screen, f["body_sm"], "name this save  ·  Enter to save  ·  Esc to cancel",
                 (card.centerx, box.bottom + 18), T.TX_FAINT, center=True)
            self._buttons.clear()
            return
        if self.saved_note:
            text(screen, f["body_sm"], self.saved_note, (card.centerx, card.y + 74), T.GREEN, center=True)

        self._buttons.clear()
        by = card.y + 84
        for key, label, primary, danger in rows:
            r = pygame.Rect(card.x + T.S * 3, by, card.w - 2 * T.S * 3, 40)
            enabled = self.can_save or key != "save_as"
            draw_button(screen, f, r, label, primary=primary, danger=danger,
                        enabled=enabled, mpos=self.mouse)
            if enabled:
                self._buttons.append((key, r))
            by += 40 + T.S

        set_pointer(any(rect.collidepoint(self.mouse) for _, rect in self._buttons))
