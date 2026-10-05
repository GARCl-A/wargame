"""Menu screen: the guilds shown at launch.

One card per world (a guild's campaign), newest first: CONTINUE loads its live
state, SAVES opens the list of every snapshot it has (`saves_screen`), DELETE
removes the whole world after one confirmation. The first card starts a new
guild. `notice` is a one-line message from the app (e.g. after a wipe).
"""

import time

import pygame

from . import persist
from .screen import Screen
from .ui.primitives import draw_button, panel, set_pointer, text
from .ui.tokens import T

MARGIN = T.S * 2
SP3 = T.S * 3 // 2
SP4 = T.S * 2
CARD_H = 116
NEW_H = 64


def stamp(ts):
    """`dd/mm/yyyy HH:MM` for a save's timestamp, '' when unknown."""
    return time.strftime("%d/%m/%Y %H:%M", time.localtime(ts)) if ts else ""


class MenuScreen(Screen):
    native = True                            # draw at the real window size

    def __init__(self, fonts, on_new, on_continue, on_saves, on_delete, on_editor=None, notice=None):
        super().__init__()
        self.F = fonts
        self.on_new = on_new
        self.on_continue = on_continue
        self.on_saves = on_saves
        self.on_delete = on_delete
        self.on_editor = on_editor
        self.notice = notice
        self.confirm_delete = None            # world id awaiting delete confirmation
        self.buttons = []                    # [(key, world, rect)]
        self.scroll = 0
        self._max_scroll = 0
        self._refresh()

    def _refresh(self):
        self.worlds = persist.list_worlds()

    # ------------------------------------------------------------------ #
    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, min(self._max_scroll, self.scroll - event.y * 40))
            return
        super().handle_event(event)

    def _click(self, px):
        for key, world, rect in self.buttons:
            if not rect.collidepoint(px):
                continue
            if key == "new":
                self.on_new()
            elif key == "continue":
                self.on_continue(world)
            elif key == "saves":
                self.on_saves(world)
            elif key == "delete":
                self.confirm_delete = world
            elif key == "delete_yes":
                self.on_delete(world)
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
        text(screen, F["body"], "pick a guild to play", (MARGIN, MARGIN + 32), T.TX_MUTED)
        if self.notice:
            text(screen, F["body"], self.notice, (MARGIN, MARGIN + 54), T.BLOOD)

        card_w = min(560, W - 2 * MARGIN)
        x = (W - card_w) // 2
        top = MARGIN + 84
        footer_h = 34 + SP3 + 24 if self.on_editor else 24
        view = pygame.Rect(0, top, W, max(0, H - top - footer_h))

        content_h = NEW_H + SP4 + len(self.worlds) * (CARD_H + SP4)
        self._max_scroll = max(0, content_h - view.h)
        self.scroll = min(self.scroll, self._max_scroll)

        clip = screen.get_clip()
        screen.set_clip(view)
        y = top - self.scroll
        self._draw_new(screen, pygame.Rect(x, y, card_w, NEW_H), mouse, view)
        y += NEW_H + SP4
        for w in self.worlds:
            self._draw_world(screen, pygame.Rect(x, y, card_w, CARD_H), w, mouse, view)
            y += CARD_H + SP4
        screen.set_clip(clip)

        if self.on_editor:
            er = pygame.Rect(x, H - footer_h + SP3 // 2, card_w, 34)
            hov = er.collidepoint(mouse)
            panel(screen, er, hover=hov)
            text(screen, F["microb"], "EDITOR", (er.centerx, er.centery - 8), T.BRASS if hov else T.TX_MUTED, center=True)
            text(screen, F["body"], "character & scenario creator", (er.centerx, er.centery + 4), T.TX_FAINT, center=True)
            self.buttons.append(("editor", None, er))

        text(screen, F["body"], "[Esc] quit", (MARGIN, H - 18), T.TX_FAINT)
        set_pointer(any(rect.collidepoint(mouse) for _, _, rect in self.buttons))

    @staticmethod
    def _visible(rect, view):
        return rect.bottom > view.top and rect.top < view.bottom

    def _draw_new(self, screen, rect, mouse, view):
        F = self.F
        hov = rect.collidepoint(mouse) and view.collidepoint(mouse)
        panel(screen, rect, hover=hov, width=2 if hov else 1)
        text(screen, F["bodyb"], "NEW GUILD", (rect.x + SP3, rect.y + 14), T.BRASS if hov else T.TX)
        text(screen, F["body"], "draft a squad and start a new world", (rect.x + SP3, rect.y + 36), T.TX_FAINT)
        if self._visible(rect, view):
            self.buttons.append(("new", None, rect))

    def _draw_world(self, screen, rect, w, mouse, view):
        F = self.F
        world = w["world"]
        panel(screen, rect)
        title = w["name"] or "Unnamed guild"
        text(screen, F["bodyb"], title, (rect.x + SP3, rect.y + SP3), T.TX)
        squad = "  ·  ".join(name.split()[0] for name in w["squad"]) or "(no squad)"
        text(screen, F["body"], squad, (rect.x + SP3, rect.y + 34), T.TX_MUTED)
        n = w["saves"]
        text(screen, F["body"],
             f"{w['battles_won']} wins  ·  {n} save{'s' if n != 1 else ''}  ·  last played {stamp(w['saved_at'])}",
             (rect.x + SP3, rect.y + 54), T.TX_FAINT)

        if not self._visible(rect, view):
            return
        if self.confirm_delete == world:
            text(screen, F["body"], "delete this guild and all its saves?", (rect.x + SP3, rect.bottom - 34), T.BLOOD)
            self._btn(screen, "delete_yes", world, pygame.Rect(rect.right - 210, rect.bottom - 40, 92, 28),
                      "delete", T.BLOOD, mouse)
            self._btn(screen, "delete_no", world, pygame.Rect(rect.right - 108, rect.bottom - 40, 92, 28),
                      "cancel", T.TX_MUTED, mouse)
            return
        self._btn(screen, "continue", world, pygame.Rect(rect.right - 330, rect.bottom - 40, 100, 28),
                  "continue", T.BRASS, mouse)
        self._btn(screen, "saves", world, pygame.Rect(rect.right - 224, rect.bottom - 40, 80, 28),
                  "saves", T.TX_MUTED, mouse)
        self._btn(screen, "delete", world, pygame.Rect(rect.right - 80, rect.bottom - 40, 64, 28),
                  "delete", T.TX_MUTED, mouse)

    def _btn(self, screen, key, world, rect, label, color, mouse):
        draw_button(screen, self.F, rect, label, primary=(color is T.BRASS), danger=(color is T.BLOOD), mpos=mouse)
        self.buttons.append((key, world, rect))
