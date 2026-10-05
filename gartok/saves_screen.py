"""Saves of one guild: every snapshot of a world, newest first, with date and time.

`current` is the live state; "auto" saves are taken right before each fight (the
last `persist.AUTOSAVES_KEPT` stay) and "manual" ones are named by the player.
LOAD makes the chosen snapshot the world's live state -- the rest stay on the
list, so going back never loses the way forward.
"""

import time

import pygame

from . import persist
from .screen import Screen
from .ui.primitives import draw_button, panel, set_pointer, text
from .ui.tokens import T

MARGIN = T.S * 2
SP3 = T.S * 3 // 2
ROW_H = 78

KIND_LABEL = {"current": ("CURRENT", T.GREEN), "auto": ("AUTO", T.TX_MUTED), "manual": ("MANUAL", T.BRASS)}


def full_stamp(ts):
    return time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(ts)) if ts else ""


class SavesScreen(Screen):
    native = True

    def __init__(self, fonts, world, on_load, on_back):
        super().__init__()
        self.F = fonts
        self.world = world
        self.on_load = on_load
        self.on_back = on_back
        self.confirm_delete = None            # save id awaiting delete confirmation
        self.buttons = []                    # [(key, save_id, rect)]
        self.scroll = 0
        self._max_scroll = 0
        self._refresh()

    def _refresh(self):
        self.saves = persist.list_saves(self.world)
        self.title = next((s["name"] for s in self.saves if s["name"]), "Unnamed guild")

    def handle_escape(self):
        self.on_back()
        return True

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, min(self._max_scroll, self.scroll - event.y * 40))
            return
        super().handle_event(event)

    def _click(self, px):
        for key, save_id, rect in self.buttons:
            if not rect.collidepoint(px):
                continue
            if key == "back":
                self.on_back()
            elif key == "load":
                self.on_load(self.world, save_id)
            elif key == "delete":
                self.confirm_delete = save_id
            elif key == "delete_yes":
                persist.delete_save(self.world, save_id)
                self.confirm_delete = None
                self._refresh()
            elif key == "delete_no":
                self.confirm_delete = None
            return
        self.confirm_delete = None

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self.F
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        mouse = self.mouse
        self.buttons = []

        text(screen, F["big"], self.title.upper(), (MARGIN, MARGIN), T.TX)
        text(screen, F["body"], "pick a moment to go back to  ·  loading keeps every other save",
             (MARGIN, MARGIN + 32), T.TX_MUTED)

        row_w = min(720, W - 2 * MARGIN)
        x = (W - row_w) // 2
        top = MARGIN + 64
        view = pygame.Rect(0, top, W, max(0, H - top - 56))
        content_h = len(self.saves) * (ROW_H + SP3)
        self._max_scroll = max(0, content_h - view.h)
        self.scroll = min(self.scroll, self._max_scroll)

        clip = screen.get_clip()
        screen.set_clip(view)
        y = top - self.scroll
        for s in self.saves:
            self._draw_row(screen, pygame.Rect(x, y, row_w, ROW_H), s, mouse, view)
            y += ROW_H + SP3
        screen.set_clip(clip)

        back = pygame.Rect(MARGIN, H - 48, 140, 34)
        draw_button(screen, F, back, "BACK", mpos=mouse)
        self.buttons.append(("back", None, back))
        set_pointer(any(rect.collidepoint(mouse) for _, _, rect in self.buttons))

    def _draw_row(self, screen, rect, s, mouse, view):
        F = self.F
        panel(screen, rect)
        kind, color = KIND_LABEL.get(s["kind"], KIND_LABEL["current"])
        text(screen, F["microb"], kind, (rect.x + SP3, rect.y + SP3), color)
        text(screen, F["bodyb"], full_stamp(s["saved_at"]), (rect.x + SP3 + 80, rect.y + SP3 - 3), T.TX)
        label = s["label"] or ("live state, saved on every stop" if s["kind"] == "current" else "")
        text(screen, F["body"], label, (rect.x + SP3, rect.y + 32), T.TX_MUTED)
        day = f"day {s['day']}  ·  " if s["day"] is not None else ""
        text(screen, F["body"], f"{day}{s['battles_won']} wins", (rect.x + SP3, rect.y + 54), T.TX_FAINT)

        if rect.bottom <= view.top or rect.top >= view.bottom:
            return
        sid = s["id"]
        if self.confirm_delete == sid:
            text(screen, F["body"], "delete this save?", (rect.right - 330, rect.y + 12), T.BLOOD)
            self._btn(screen, "delete_yes", sid, pygame.Rect(rect.right - 210, rect.bottom - 36, 92, 28), "delete", mouse)
            self._btn(screen, "delete_no", sid, pygame.Rect(rect.right - 108, rect.bottom - 36, 92, 28), "cancel", mouse)
            return
        self._btn(screen, "load", sid, pygame.Rect(rect.right - 190, rect.bottom - 36, 100, 28), "load", mouse)
        if s["kind"] != "current":
            self._btn(screen, "delete", sid, pygame.Rect(rect.right - 80, rect.bottom - 36, 64, 28), "delete", mouse)

    def _btn(self, screen, key, sid, rect, label, mouse):
        draw_button(screen, self.F, rect, label, primary=(key == "load"), danger=(key == "delete_yes"), mpos=mouse)
        self.buttons.append((key, sid, rect))
