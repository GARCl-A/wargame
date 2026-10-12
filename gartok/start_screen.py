"""Start screen: classic main menu replacing direct boot into saves list.

Offers:
- CONTINUE: directly loads the most recently played campaign save.
- NEW GAME: enters vocation and character draft to found a new guild.
- LOAD GAME: opens the guild browser and saves screen.
- EDITOR: opens character, map and combat lab editors.
- SETTINGS: player preferences and system options.
- WIKI: in-game compendium of rules, items, talents, recipes and beasts.
- QUIT: exits to desktop.
"""

import time
import pygame

from . import persist
from .screen import Screen
from .ui.primitives import draw_button, panel, set_pointer, text
from .ui.tokens import T

MARGIN = T.S * 4
BTN_W = 380
BTN_H = 42
GAP = T.S * 2


def stamp(ts):
    return time.strftime("%d/%m/%Y %H:%M", time.localtime(ts)) if ts else ""


class StartScreen(Screen):
    native = True

    def __init__(self, fonts, on_continue, on_new, on_load, on_editor,
                 on_settings, on_wiki, on_quit, notice=None):
        super().__init__()
        self.F = fonts
        self.on_continue = on_continue
        self.on_new = on_new
        self.on_load = on_load
        self.on_editor = on_editor
        self.on_settings = on_settings
        self.on_wiki = on_wiki
        self.on_quit = on_quit
        self.notice = notice
        self.buttons = []
        self._refresh()

    def _refresh(self):
        self.worlds = persist.list_worlds()
        self.latest_world = self.worlds[0] if self.worlds else None

    def handle_escape(self):
        self.on_quit()
        return True

    def _click(self, px):
        for key, rect, enabled in self.buttons:
            if not rect.collidepoint(px) or not enabled:
                continue
            if key == "continue" and self.latest_world:
                self.on_continue()
            elif key == "new":
                self.on_new()
            elif key == "load":
                self.on_load()
            elif key == "editor":
                self.on_editor()
            elif key == "settings":
                self.on_settings()
            elif key == "wiki":
                self.on_wiki()
            elif key == "quit":
                self.on_quit()
            return

    def draw(self, screen):
        F = self.F
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        mouse = self.mouse
        self.buttons = []

        # Title header
        title_y = MARGIN + 12
        text(screen, F["big"], "GARTOK TACTICAL", (W // 2, title_y), T.TX, center=True)
        text(screen, F["body"], "A squad wargame & sandbox guild manager", (W // 2, title_y + 36), T.TX_MUTED, center=True)

        if self.notice:
            text(screen, F["bodyb"], self.notice, (W // 2, title_y + 60), T.BLOOD, center=True)

        cx = (W - BTN_W) // 2
        y = title_y + 88

        # Latest campaign banner
        has_save = self.latest_world is not None
        if has_save:
            w = self.latest_world
            info_r = pygame.Rect(cx, y, BTN_W, 58)
            panel(screen, info_r)
            title = w["name"] or "Unnamed Guild"
            meta = f"Day {w.get('day', 1)}  ·  {len(w.get('squad', []))} members  ·  {w.get('battles_won', 0)} wins"
            last = f"Last saved: {stamp(w.get('saved_at', 0))}"
            text(screen, F["bodyb"], title, (info_r.centerx, info_r.y + 8), T.BRASS, center=True)
            text(screen, F["micro"], meta, (info_r.centerx, info_r.y + 26), T.TX, center=True)
            text(screen, F["micro"], last, (info_r.centerx, info_r.y + 42), T.TX_FAINT, center=True)
            y += 58 + GAP
        else:
            empty_r = pygame.Rect(cx, y, BTN_W, 40)
            panel(screen, empty_r)
            text(screen, F["body"], "No campaigns found  ·  Start a new guild",
                 (empty_r.centerx, empty_r.centery - 6), T.TX_FAINT, center=True)
            y += 40 + GAP

        # Buttons list
        menu_items = [
            ("continue", "CONTINUE", has_save, has_save),
            ("new", "NEW GAME", False, True),
            ("load", "LOAD GAME", False, True),
            ("editor", "EDITOR", False, True),
            ("settings", "SETTINGS", False, True),
            ("wiki", "WIKI & COMPENDIUM", False, True),
            ("quit", "QUIT", False, True),
        ]

        for key, label, is_primary, is_enabled in menu_items:
            r = pygame.Rect(cx, y, BTN_W, BTN_H)
            draw_button(screen, F, r, label, primary=is_primary, enabled=is_enabled, mpos=mouse)
            self.buttons.append((key, r, is_enabled))
            y += BTN_H + T.S

        # Minimal footer
        text(screen, F["micro"], "GARTOK Tactics  ·  English edition", (MARGIN, H - 20), T.TX_FAINT)
        text(screen, F["micro"], "[Esc] quit", (W - MARGIN, H - 20), T.TX_FAINT, right=True)

        set_pointer(any(rect.collidepoint(mouse) and en for _, rect, en in self.buttons))
