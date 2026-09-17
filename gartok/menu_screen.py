"""Menu screen: the save-slot picker shown at launch.

Empty slot -> click to start a new campaign (draft). Filled slot -> a summary
(squad, victories, date) with Continue and Delete. Deleting asks once.
"""

import time

import pygame

from . import persist
from .screen import Screen
from .theme import set_pointer
from .ui.primitives import draw_button, panel, text
from .ui.tokens import T

MARGIN = T.S * 2
SP3 = T.S * 3 // 2
SP4 = T.S * 2


class MenuScreen(Screen):
    native = True                            # draw at the real window size

    def __init__(self, fonts, on_new, on_continue, on_delete, on_editor=None):
        super().__init__()
        self.F = fonts
        self.on_new = on_new
        self.on_continue = on_continue
        self.on_delete = on_delete
        self.on_editor = on_editor
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
            elif key == "editor" and self.on_editor:
                self.on_editor()
            return
        self.confirm_delete = None

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self.F
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        mouse = self.mouse
        self.buttons = []

        text(screen, F["big"], "GARTOK TACTICAL", (MARGIN, MARGIN), T.TX)
        text(screen, F["body"], "pick a slot to play", (MARGIN, MARGIN + 32), T.TX_MUTED)

        card_w = min(560, W - 2 * MARGIN)
        card_h = 116
        gap = SP4
        total = persist.NUM_SLOTS * card_h + (persist.NUM_SLOTS - 1) * gap
        x = (W - card_w) // 2
        y = max(MARGIN + 72, (H - total) // 2)

        for s in self.slots:
            rect = pygame.Rect(x, y, card_w, card_h)
            self._draw_slot(screen, rect, s, mouse)
            y += card_h + gap

        if self.on_editor:
            er = pygame.Rect(x, y + SP3, card_w, 34)
            hov = er.collidepoint(mouse)

            panel(screen, er, hover=hov)

            text(screen, F["microb"], "EDITOR", (er.centerx, er.centery - 8), T.BRASS if hov else T.TX_MUTED, center=True)
            text(screen, F["body"], "character & scenario creator", (er.centerx, er.centery + 4), T.TX_FAINT, center=True)
            self.buttons.append(("editor", None, er))

        text(screen, F["body"], "[Esc] quit", (MARGIN, H - 18), T.TX_FAINT)

        set_pointer(any(rect.collidepoint(mouse) for _, _, rect in self.buttons))

    def _draw_slot(self, screen, rect, s, mouse):
        F = self.F
        i = s["index"]
        hov_card = s["empty"] and rect.collidepoint(mouse)

        panel(screen, rect, hover=hov_card, width=2 if hov_card else 1)

        text(screen, F["microb"], f"SLOT {i + 1}", (rect.x + SP3, rect.y + SP3), T.TX_FAINT)

        if s["empty"]:
            hov = hov_card
            text(screen, F["body"], "empty", (rect.x + SP3, rect.y + 34), T.TX_MUTED)
            text(screen, F["body"], "click to start a new game", (rect.x + SP3, rect.y + 56), T.BRASS if hov else T.TX_FAINT)
            self.buttons.append(("new", i, rect))
            return

        squad = "  ·  ".join(name.split()[0] for name in s["squad"]) or "(no squad)"
        when = time.strftime("%d/%m %H:%M", time.localtime(s["saved_at"])) if s["saved_at"] else ""
        text(screen, F["bodyb"], squad, (rect.x + SP3, rect.y + 30), T.TX)
        text(screen, F["body"], f"{s['battles_won']} wins    {when}", (rect.x + SP3, rect.y + 52), T.TX_MUTED)

        if self.confirm_delete == i:
            text(screen, F["body"], "delete this game?", (rect.x + SP3, rect.bottom - 34), T.BLOOD)
            self._btn(screen, "delete_yes", i,
                      pygame.Rect(rect.right - 210, rect.bottom - 40, 92, 28),
                      "delete", T.BLOOD, mouse)
            self._btn(screen, "delete_no", i,
                      pygame.Rect(rect.right - 108, rect.bottom - 40, 92, 28),
                      "cancel", T.TX_MUTED, mouse)
            return

        self._btn(screen, "continue", i,
                  pygame.Rect(rect.right - 210, rect.bottom - 40, 120, 28),
                  "continue", T.BRASS, mouse)
        self._btn(screen, "delete", i,
                  pygame.Rect(rect.right - 80, rect.bottom - 40, 64, 28),
                  "delete", T.TX_MUTED, mouse)

    def _btn(self, screen, key, slot, rect, label, color, mouse):
        draw_button(screen, self.F, rect, label, primary=(color is T.BRASS), danger=(color is T.BLOOD), mpos=mouse)
        self.buttons.append((key, slot, rect))
