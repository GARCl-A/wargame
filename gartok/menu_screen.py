"""Menu screen: the save-slot picker shown at launch.

Empty slot -> click to start a new campaign (draft). Filled slot -> a summary
(squad, victories, date) with Continue and Delete. Deleting asks once.
"""

import time

import pygame

from . import persist
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, DANGER, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, RADIUS, SP3, SP4, SURFACE_1,
                    SURFACE_2, SURFACE_3, WIN_H, WIN_W, panel, text)


class MenuScreen(Screen):
    def __init__(self, fonts, on_new, on_continue, on_delete):
        super().__init__()
        self.fonts = fonts
        self.on_new = on_new
        self.on_continue = on_continue
        self.on_delete = on_delete
        self.confirm_delete = None            # slot index awaiting delete confirmation
        self.buttons = []                    # [(key, slot, rect)]
        self._refresh()

    def _refresh(self):
        self.slots = persist.slot_summaries()

    # ------------------------------------------------------------------ #
    def _click(self, px):
        for key, slot, rect in self.buttons:
            if not rect.collidepoint(px):
                continue
            if key == "new":
                self.on_new(slot)
            elif key == "continue":
                self.on_continue(slot)
            elif key == "delete":
                self.confirm_delete = slot
            elif key == "delete_yes":
                self.on_delete(slot)
                self.confirm_delete = None
                self._refresh()
            elif key == "delete_no":
                self.confirm_delete = None
            return
        self.confirm_delete = None

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        screen.fill((18, 19, 24))
        mouse = self.mouse
        self.buttons = []

        text(screen, "GARTOK TACTICAL", f.title, INK, (MARGIN, MARGIN))
        text(screen, "pick a slot to play", f.body, INK_DIM,
             (MARGIN, MARGIN + 32))

        card_w = min(560, WIN_W - 2 * MARGIN)
        card_h = 116
        gap = SP4
        total = persist.NUM_SLOTS * card_h + (persist.NUM_SLOTS - 1) * gap
        x = (WIN_W - card_w) // 2
        y = (WIN_H - total) // 2

        for s in self.slots:
            rect = pygame.Rect(x, y, card_w, card_h)
            self._draw_slot(screen, rect, s, mouse)
            y += card_h + gap

        text(screen, "[Esc] quit", f.body_sm, INK_FAINT, (MARGIN, WIN_H - 18))

    def _draw_slot(self, screen, rect, s, mouse):
        f = self.fonts
        i = s["index"]
        hov_card = s["empty"] and rect.collidepoint(mouse)
        panel(screen, rect, fill=SURFACE_3 if hov_card else SURFACE_2,
              border=ACCENT if hov_card else LINE_SOFT,
              width=2 if hov_card else 1, radius=RADIUS)
        text(screen, f"SLOT {i + 1}", f.label, INK_FAINT, (rect.x + SP3, rect.y + SP3))

        if s["empty"]:
            hov = hov_card
            text(screen, "empty", f.body, INK_DIM, (rect.x + SP3, rect.y + 34))
            text(screen, "click to start a new game", f.body_sm,
                 ACCENT if hov else INK_FAINT, (rect.x + SP3, rect.y + 56))
            self.buttons.append(("new", i, rect))
            return

        squad = "  ·  ".join(name.split()[0] for name in s["squad"]) or "(no squad)"
        when = time.strftime("%d/%m %H:%M", time.localtime(s["saved_at"])) if s["saved_at"] else ""
        text(screen, squad, f.body_bd, INK, (rect.x + SP3, rect.y + 30))
        text(screen, f"{s['battles_won']} wins    {when}", f.body_sm, INK_DIM,
             (rect.x + SP3, rect.y + 52))

        if self.confirm_delete == i:
            text(screen, "delete this game?", f.body_sm, DANGER,
                 (rect.x + SP3, rect.bottom - 34))
            self._btn(screen, "delete_yes", i,
                      pygame.Rect(rect.right - 210, rect.bottom - 40, 92, 28),
                      "delete", DANGER, mouse)
            self._btn(screen, "delete_no", i,
                      pygame.Rect(rect.right - 108, rect.bottom - 40, 92, 28),
                      "cancel", INK_DIM, mouse)
            return

        self._btn(screen, "continue", i,
                  pygame.Rect(rect.right - 210, rect.bottom - 40, 120, 28),
                  "continue", ACCENT, mouse)
        self._btn(screen, "delete", i,
                  pygame.Rect(rect.right - 80, rect.bottom - 40, 64, 28),
                  "delete", INK_DIM, mouse)

    def _btn(self, screen, key, slot, rect, label, color, mouse):
        hov = rect.collidepoint(mouse)
        on_accent = color is ACCENT
        panel(screen, rect, fill=color if (hov and on_accent) else SURFACE_3 if hov else SURFACE_1,
              border=color, width=1, radius=4)
        ink = ACCENT_INK if (hov and on_accent) else color
        text(screen, label, self.fonts.label, ink, rect.center, center=True)
        self.buttons.append((key, slot, rect))
