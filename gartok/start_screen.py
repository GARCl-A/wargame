"""Start screen: classic main menu replacing direct boot into saves list.

Offers:
- CONTINUE: directly loads the most recently played campaign save.
- NEW GAME: enters vocation and character draft to found a new guild.
- LOAD GAME: opens the guild browser and saves screen.
- EDITOR: opens character, map and combat lab editors.
- SETTINGS: player preferences and system options.
- WIKI: in-game compendium of rules, items, talents, recipes and beasts.
- QUIT: exits to desktop.

The right side shows the last guild played (its banner, its people), or an invitation to
found one when there is none.
"""

import time

import pygame

from . import data, persist, vocations
from .guild import DEFAULT_BANNER_COLOR, DEFAULT_BANNER_ICON
from .screen import Screen
from .ui.primitives import set_pointer, text
from .ui.title_panel import (
    ROW_H,
    draw_campaign,
    draw_invite,
    draw_menu,
    draw_title,
    menu_height,
    title_height,
)
from .ui.tokens import T

INVITE_RACES = ("Human", "Orc", "Elf", "Dwarf", "Goblin", "Grippli", "Centaur", "Kenku")
MAX_FACES = 12
QUOTE = "In Gartok the risk pays. Most of those who take it do not live to spend it."


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
        self.campaign_rect = None
        self._refresh()

    def _refresh(self):
        self.worlds = persist.list_worlds()
        self.latest_world = self.worlds[0] if self.worlds else None

    def handle_escape(self):
        self.on_quit()
        return True

    def _click(self, px):
        if self.campaign_rect and self.campaign_rect.collidepoint(px) and self.latest_world:
            self.on_continue()
            return
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

    def _menu(self):
        has_save = self.latest_world is not None
        n = len(self.worlds)
        return [
            {"key": "continue", "label": "Continue", "primary": True, "enabled": has_save,
             "hint": (self.latest_world["name"] or "Unnamed Guild") if has_save else None},
            {"key": "new", "label": "New guild", "primary": not has_save, "enabled": True},
            {"key": "load", "label": "Load game", "enabled": True,
             "hint": f"{n} guild{'s' if n != 1 else ''}" if n else None},
            None,
            {"key": "wiki", "label": "Wiki & compendium", "enabled": True},
            {"key": "settings", "label": "Settings", "enabled": True},
            {"key": "editor", "label": "Editor", "enabled": True, "hint": "characters, maps, combat lab"},
            None,
            {"key": "quit", "label": "Quit", "enabled": True},
        ]

    def _campaign(self):
        w = self.latest_world
        voc = vocations.get(w.get("vocation"))
        color = w.get("banner_color")
        return {
            "name": w["name"] or "Unnamed Guild",
            "vocation": voc.name if voc else None,
            "day": w.get("day") or 1,
            "members": len(w.get("squad", [])),
            "wins": w.get("battles_won", 0),
            "saved": stamp(w.get("saved_at", 0)),
            "color": tuple(color) if color else DEFAULT_BANNER_COLOR,
            "icon": w.get("banner_icon") or DEFAULT_BANNER_ICON,
            "faces": w.get("faces", [])[:MAX_FACES],
        }

    def draw(self, screen):
        F = self.F
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        mouse = self.mouse

        margin = round(max(T.S * 4, min(T.S * 16, W * 0.07)))
        col_w = round(max(T.S * 36, min(T.S * 56, W * 0.26)))
        gap = round(max(T.S * 4, min(T.S * 14, W * 0.05)))
        rw = min(T.S * 90, W - 2 * margin - col_w - gap)
        show_right = rw >= T.S * 40
        total_w = col_w + gap + rw if show_right else col_w
        x0 = (W - total_w) // 2

        items = self._menu()
        rows = sum(1 for i in items if i)
        title_h = title_height(F, col_w, QUOTE) + (F["hub_bodyb"].get_height() + T.S if self.notice else 0)
        room = H - T.S * 14 - title_h - T.S * 5 - menu_height(items, 0)
        row_h = max(T.S * 4, min(ROW_H, room // rows - 2))
        content_h = title_h + T.S * 5 + menu_height(items, row_h)
        top = max(T.S * 4, (H - T.S * 6 - content_h) // 2)
        left = pygame.Rect(x0, top, col_w, content_h)

        y = draw_title(screen, F, left, "Gartok", "Tactical", "A squad wargame · a sandbox guild", QUOTE)
        if self.notice:
            y += T.S
            text(screen, F["hub_bodyb"], self.notice, (left.x, y), T.BLOOD)
            y += F["hub_bodyb"].get_height()
        menu = pygame.Rect(left.x, y + T.S * 5, col_w, left.bottom - y - T.S * 5)
        self.buttons = draw_menu(screen, F, menu, items, mouse, row_h)

        self.campaign_rect = None
        if show_right:
            rx = left.right + gap
            pygame.draw.line(screen, T.STEEL_LINE, (left.right + gap // 2, top),
                             (left.right + gap // 2, self.buttons[-1][1].bottom))
            room = pygame.Rect(rx, top + T.S * 3, rw, H - top - T.S * 12)
            if self.latest_world is not None:
                self.campaign_rect = draw_campaign(screen, F, room, self._campaign(), mouse)
            else:
                faces = [{"name": r, "race": r, "portrait": 0} for r in INVITE_RACES if r in data.RACE_NAMES]
                draw_invite(screen, F, room, faces)

        text(screen, F["hub_sub"], "GARTOK Tactical  ·  English edition", (x0, H - T.S * 4), T.TX_FAINT)
        text(screen, F["hub_sub"], "Esc · quit", (x0 + total_w, H - T.S * 4), T.TX_FAINT, right=True)

        hot = any(rect.collidepoint(mouse) and en for _, rect, en in self.buttons)
        set_pointer(hot or bool(self.campaign_rect and self.campaign_rect.collidepoint(mouse)))
