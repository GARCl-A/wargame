"""Draft screen: a pool of nine candidates, pick three, then name the guild,
pick its banner and choose which of the three leads it.

The player has 3 Commission Tokens across the whole draft to call the archetypes
the pool lacks (Leaders, Strong, Tough, etc.): the commission picks the
archetypes, then the candidate it replaces. A replaced card that was picked
leaves the squad.

`on_done(picks, leader, name, banner_color, banner_icon)` -- the "identity"
phase (name + banner, purely cosmetic -- see `Guild.name`/`banner_color`/
`banner_icon` in `guild.py`) recolours every unit token live via
`ui.banner.set_player_color` as the player picks, so the leader-pick cards that
follow already show it. The leader step itself ("who am I") is `Guild.leader`
-- see that module for what the choice does downstream (haggling, and the
run's one free way to change your mind).
"""

import pygame

from . import artwork, data
from .archetypes import (
    ARCHETYPES,
    generate_candidate,
    is_compatible,
    unit_archetypes,
)
from .combatant import Combatant
from .screen import Screen
from .ui.banner import BANNER_COLORS, set_player_color
from .ui.draft_panel import (
    draw_commission_modal,
    draw_pool_card,
    draw_squad_rail,
    pool_card_height,
)
from .ui.primitives import (
    TOKEN_INK,
    contained,
    draw_button,
    draw_tooltip,
    format_tooltip,
    panel,
    scrollbar,
    smooth_circle,
    text,
    tracked,
)
from .ui.sheet_card import draw_row, unit_to_ch
from .ui.tokens import T
from .unit import Unit

TEAM_SIZE = 3
POOL_SIZE = 9
POOL_COLUMNS = 3
COMMISSION_TOKENS = 3
_MAX_GUILD_NAME = 24
_ATTRS = (("STR", "strength"), ("DEX", "dexterity"), ("CON", "constitution"),
          ("INT", "intelligence"), ("WIS", "wisdom"), ("CHA", "charisma"))


class DraftScreen(Screen):
    native = True

    def __init__(self, fonts, on_done, tutorial=None):
        super().__init__()
        self.F = fonts
        self.on_done = on_done
        self.tutorial = tutorial
        self.picks = []
        self.phase = "pick"        # "pick" | "identity"
        self.tokens = COMMISSION_TOKENS
        self.pool = [Unit("player") for _ in range(POOL_SIZE)]
        self.commissioned = {}     # id(unit) -> the archetypes that were called for it
        self.pending_labels = []   # a confirmed commission waiting for the card it replaces
        self.scroll = 0
        self.max_scroll = 0
        self.pool_view = None
        self.commission_modal_open = False
        self.selected_modal_labels = []

        self.commission_btn_rect = None
        self.modal_rect = None
        self.modal_item_rects = []
        self.modal_confirm_rect = None
        self.modal_cancel_rect = None
        self.card_rects = []

        # identity phase state
        self.guild_name = ""
        self.editing_name = False
        self.name_buf = ""
        self.name_rect = None
        self.banner_color = BANNER_COLORS[0][1]
        self.banner_icon = artwork.BANNER_ICONS[0][1]
        self.color_rects = []
        self.icon_rects = []
        self.leader_pick = None
        self.leader_rects = []
        self.continue_rect = None

        set_player_color(self.banner_color)

    # ------------------------------------------------------------------ #
    def _toggle_pick(self, unit):
        if unit in self.picks:
            self.picks.remove(unit)
        elif len(self.picks) < TEAM_SIZE:
            self.picks.append(unit)

    def _replace(self, unit):
        """Spend the pending commission on `unit`'s slot in the pool."""
        labels = self.pending_labels
        fresh = generate_candidate(labels)
        self.pool[self.pool.index(unit)] = fresh
        if unit in self.picks:
            self.picks.remove(unit)
        self.commissioned.pop(id(unit), None)
        self.commissioned[id(fresh)] = list(labels)
        self.tokens -= len(labels)
        self.pending_labels = []

    def handle_event(self, event):
        if self.editing_name and event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.guild_name, self.editing_name = self.name_buf, False
            elif event.key == pygame.K_BACKSPACE:
                self.name_buf = self.name_buf[:-1]
            elif event.unicode and len(self.name_buf) < _MAX_GUILD_NAME \
                    and event.unicode.isprintable():
                self.name_buf += event.unicode
            return

        if self.commission_modal_open and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._close_modal()
            return

        if event.type == pygame.MOUSEWHEEL and self.phase == "pick" and not self.commission_modal_open:
            self.scroll = max(0, min(self.max_scroll, self.scroll - event.y * T.S * 5))
            return

        super().handle_event(event)

    def handle_escape(self):
        if self.commission_modal_open:
            self._close_modal()
            return True
        if self.pending_labels:
            self.pending_labels = []
            return True
        return False

    def _close_modal(self):
        self.commission_modal_open = False
        self.selected_modal_labels = []

    # ------------------------------------------------------------------ #
    def _click(self, px):
        if self.phase == "identity":
            self._click_identity(px)
            return

        if self.commission_modal_open:
            self._click_commission_modal(px)
            return

        if self.commission_btn_rect and self.commission_btn_rect.collidepoint(px):
            if self.pending_labels:
                self.pending_labels = []
            elif self.tokens > 0:
                self.commission_modal_open = True
                self.selected_modal_labels = []
            return

        if self.continue_rect and self.continue_rect.collidepoint(px) and len(self.picks) == TEAM_SIZE:
            self.phase = "identity"
            return

        if self.pool_view is not None and not self.pool_view.collidepoint(px):
            return
        for rect, unit in self.card_rects:
            if rect.collidepoint(px):
                if self.pending_labels:
                    self._replace(unit)
                else:
                    self._toggle_pick(unit)
                return

    def _click_commission_modal(self, px):
        if self.modal_confirm_rect and self.modal_confirm_rect.collidepoint(px):
            if 1 <= len(self.selected_modal_labels) <= self.tokens:
                self.pending_labels = list(self.selected_modal_labels)
                self._close_modal()
            return

        if self.modal_cancel_rect and self.modal_cancel_rect.collidepoint(px):
            self._close_modal()
            return

        for rect, key, can_toggle in self.modal_item_rects:
            if rect.collidepoint(px):
                if key in self.selected_modal_labels:
                    self.selected_modal_labels.remove(key)
                elif can_toggle:
                    self.selected_modal_labels.append(key)
                return

        if self.modal_rect and not self.modal_rect.collidepoint(px):
            self._close_modal()

    # ------------------------------------------------------------------ #
    # tutorial (screen.py) -- one id per phase                           #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        if (self.phase == "pick" and not self.picks
                and self.tutorial is not None and "draft.intro" not in self.tutorial.seen):
            return "draft.intro"
        return {"pick": "draft.pick", "identity": "draft.identity"}.get(self.phase)

    def tutorial_badge_rect(self, size):
        W, _H = size
        pad = T.S * 4
        return pygame.Rect(W - pad - 28, pad, 28, 28)

    def _click_identity(self, px):
        if self.editing_name:
            self.guild_name, self.editing_name = self.name_buf, False
        if self.name_rect and self.name_rect.collidepoint(px):
            self.name_buf, self.editing_name = self.guild_name, True
            return
        for rect, color in self.color_rects:
            if rect.collidepoint(px):
                self.banner_color = color
                set_player_color(color)
                return
        for rect, slug in self.icon_rects:
            if rect.collidepoint(px):
                self.banner_icon = slug
                return
        for rect, unit in self.leader_rects:
            if rect.collidepoint(px):
                self.leader_pick = unit
                return
        if self.continue_rect and self.continue_rect.collidepoint(px) and self.leader_pick is not None:
            self.on_done(self.picks, self.leader_pick, self.guild_name or "The Guild",
                         self.banner_color, self.banner_icon)

    # ------------------------------------------------------------------ #
    # drawing                                                            #
    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self.F
        screen.fill(T.TABLE)
        mouse = self.mouse
        self.tooltip = None

        if self.phase == "identity":
            self._draw_identity(screen)
            if getattr(self, "tooltip", None):
                draw_tooltip(screen, F, self.tooltip, mouse)
            return

        W, H = screen.get_size()
        pad = T.S * 4
        modal = self.commission_modal_open

        text(screen, F["titleb"], "SQUAD DRAFT", (pad, pad - 2), T.TX)
        tokens_dots = "● " * self.tokens + "○ " * (COMMISSION_TOKENS - self.tokens)
        sub = (f"Pick {TEAM_SIZE} of {POOL_SIZE}  ·  squad {len(self.picks)}/{TEAM_SIZE}  "
               f"·  commission tokens: {tokens_dots.strip()}")
        text(screen, F["body"], sub, (pad, pad + 30), T.TX_MUTED)
        self._draw_top_buttons(screen, mouse)

        rail_h = 92
        rail_y = H - 28 - rail_h
        view = pygame.Rect(pad, pad + 58, W - 2 * pad, rail_y - T.S * 2 - (pad + 58))
        self.pool_view = view

        gap = T.S * 2
        card_w = (view.w - T.S - (POOL_COLUMNS - 1) * gap) // POOL_COLUMNS
        card_h = pool_card_height()
        rows = (POOL_SIZE + POOL_COLUMNS - 1) // POOL_COLUMNS
        content_h = rows * card_h + (rows - 1) * gap
        self.max_scroll = max(0, content_h - view.h)
        self.scroll = min(self.scroll, self.max_scroll)

        self.card_rects = []
        tip = None
        off = (-1, -1)
        hover = off if modal else mouse
        pool_hover = hover if view.collidepoint(mouse) else off
        with contained(screen, view):
            for i, unit in enumerate(self.pool):
                rect = pygame.Rect(view.x + (i % POOL_COLUMNS) * (card_w + gap),
                                   view.y + (i // POOL_COLUMNS) * (card_h + gap) - self.scroll,
                                   card_w, card_h)
                if rect.bottom < view.y or rect.y > view.bottom:
                    continue
                self.card_rects.append((rect, unit))
                labels = self.commissioned.get(id(unit), [])
                tags = unit_archetypes(unit)
                tags.sort(key=lambda t: 0 if t[0] in labels else 1)
                card = {"ch": unit_to_ch(Combatant(unit)),
                        "tags": [(lb, st, ds, lb in labels) for lb, st, ds in tags],
                        "selected": unit in self.picks,
                        "order": self.picks.index(unit) + 1 if unit in self.picks else None,
                        "targeting": bool(self.pending_labels)}
                tip = draw_pool_card(screen, F, rect, card, pool_hover) or tip
        if self.max_scroll:
            scrollbar(screen, view, self.scroll, self.max_scroll, content_h)

        slots = [self._rail_slot(self.picks[i]) if i < len(self.picks) else None
                 for i in range(TEAM_SIZE)]
        btn_w = T.S * 25
        rail = pygame.Rect(pad, rail_y, W - 2 * pad - btn_w - T.S * 2, rail_h)
        tip = draw_squad_rail(screen, F, rail, slots, hover) or tip
        self.tooltip = tip
        self.continue_rect = pygame.Rect(W - pad - btn_w, rail_y + rail_h - T.S * 6, btn_w, T.S * 5)
        draw_button(screen, F, self.continue_rect, "CONTINUE", primary=True,
                    enabled=len(self.picks) == TEAM_SIZE, mpos=mouse)

        text(screen, F["body_sm"], "[Esc] quit", (pad, H - 18), T.TX_FAINT)

        if modal:
            self._draw_commission_modal(screen, mouse)

        if getattr(self, "tooltip", None):
            draw_tooltip(screen, F, self.tooltip, mouse)

    # ------------------------------------------------------------------ #
    def _rail_slot(self, unit):
        return {"ch": unit_to_ch(Combatant(unit)),
                "attrs": [(k, getattr(unit, name)) for k, name in _ATTRS]}

    def _draw_top_buttons(self, screen, mouse):
        F = self.F
        W = screen.get_width()
        pad = T.S * 4
        offset = (28 + T.S) if self.tutorial_key() is not None else 0

        btn_w = 190
        r_comm = pygame.Rect(W - pad - offset - btn_w, pad, btn_w, 28)
        self.commission_btn_rect = r_comm

        if self.pending_labels:
            text(screen, F["body"], "Click the candidate to replace  ·  " + ", ".join(self.pending_labels),
                 (r_comm.x - T.S * 2, pad + 6), T.BRASS, right=True)
            draw_button(screen, F, r_comm, "CANCEL", ghost=True, mpos=mouse)
        elif self.tokens > 0:
            lbl = f"COMMISSION ({self.tokens} TOKENS)" if self.tokens > 1 else "COMMISSION (1 TOKEN)"
            draw_button(screen, F, r_comm, lbl, primary=(self.tokens == COMMISSION_TOKENS),
                        enabled=not self.commission_modal_open, mpos=mouse)
        else:
            draw_button(screen, F, r_comm, "NO TOKENS LEFT", enabled=False, mpos=mouse)

    def _draw_commission_modal(self, screen, mouse):
        items = []
        for key, arc in ARCHETYPES.items():
            on = key in self.selected_modal_labels
            compatible = is_compatible(self.selected_modal_labels, key)
            room = len(self.selected_modal_labels) < self.tokens
            note = ""
            if not on and not compatible:
                note = "Incompatible with selection"
            elif not on and not room:
                note = "Token limit reached"
            items.append({"key": key, "label": arc.label, "desc": arc.desc, "style": arc.style,
                          "can_toggle": on or (room and compatible), "note": note})
        out = draw_commission_modal(screen, self.F, items, self.selected_modal_labels,
                                    self.tokens, mouse)
        self.modal_rect = out["modal"]
        self.modal_item_rects = out["items"]
        self.modal_cancel_rect = out["cancel"]
        self.modal_confirm_rect = out["confirm"]
        if out["tooltip"]:
            self.tooltip = out["tooltip"]

    # ------------------------------------------------------------------ #
    def _draw_identity(self, screen):
        F = self.F
        W, H = screen.get_size()
        mouse = self.mouse

        cw = min(560, W - 2 * (T.S * 4))
        cx = (W - cw) // 2

        text(screen, F["titleb"], "FOUND THE GUILD", (cx, T.S * 4 - 2), T.TX)
        text(screen, F["body"], "Name your guild, pick a banner, and choose your leader.",
             (cx, T.S * 4 + 30), T.TX_MUTED)

        y = T.S * 4 + 74

        pv = (cx + 24, y + 28)
        smooth_circle(screen, self.banner_color, pv, 24)
        art = artwork.banner_icon(self.banner_icon, 32, TOKEN_INK)
        if art is not None:
            screen.blit(art, art.get_rect(center=pv))

        nx = cx + 64
        nw = cw - 64
        tracked(screen, F["microb"], "GUILD NAME", (nx, y), T.TX_FAINT)
        self.name_rect = pygame.Rect(nx, y + 16, nw, 40)
        hov = self.name_rect.collidepoint(mouse)
        panel(screen, self.name_rect, hover=(hov or self.editing_name), width=2 if (hov or self.editing_name) else 1)
        shown = self.name_buf + "|" if self.editing_name else self.guild_name or "click to name your guild"
        col = T.TX if (self.editing_name or self.guild_name) else T.TX_FAINT
        text(screen, F["body"], shown, (self.name_rect.x + T.S * 2, self.name_rect.centery - F["body"].get_height() // 2), col)
        y += 56 + T.S * 3

        tracked(screen, F["microb"], "BANNER COLOUR", (cx, y), T.TX_FAINT)
        y += 18
        self.color_rects = []
        sw = 40
        for i, (_, color) in enumerate(BANNER_COLORS):
            r = pygame.Rect(cx + i * (sw + T.S * 2), y, sw, sw)
            sel = color == self.banner_color
            hov = r.collidepoint(mouse)
            smooth_circle(screen, color, r.center, sw // 2)
            smooth_circle(screen, T.BRASS if sel else (T.STEEL_LINE if hov else T.STEEL),
                          r.center, sw // 2, 3 if sel else 1)
            self.color_rects.append((r, color))
        y += sw + T.S * 3

        tracked(screen, F["microb"], "EMBLEM", (cx, y), T.TX_FAINT)
        y += 18
        self.icon_rects = []
        isz = 44
        per_row = max(1, (cw + T.S * 2) // (isz + T.S * 2))
        for i, (_, slug, _label) in enumerate(artwork.BANNER_ICONS):
            col_i, row_i = i % per_row, i // per_row
            r = pygame.Rect(cx + col_i * (isz + T.S * 2), y + row_i * (isz + T.S * 2), isz, isz)
            sel = slug == self.banner_icon
            hov = r.collidepoint(mouse)
            panel(screen, r, hover=(sel or hov), width=2 if sel else 1)
            smooth_circle(screen, self.banner_color, r.center, 14)
            art = artwork.banner_icon(slug, isz - 16, TOKEN_INK)
            if art is not None:
                screen.blit(art, art.get_rect(center=r.center))
            self.icon_rects.append((r, slug))
        rows = (len(artwork.BANNER_ICONS) + per_row - 1) // per_row
        y += rows * (isz + T.S * 2) + T.S * 3

        tracked(screen, F["microb"], "WHO LEADS THE GUILD?", (cx, y), T.TX_FAINT)
        y += 18
        self.leader_rects = []

        def _trailing(surf, r, ch):
            u = ch["unit"]
            attr_x = r.right - 380
            for k, name in _ATTRS:
                txt = f"{k} {getattr(u, name)}"
                tw = F["body_sm"].size(txt)[0]
                ar = pygame.Rect(attr_x, r.centery - F["body_sm"].get_height() // 2, tw, F["body_sm"].get_height())
                text(surf, F["body_sm"], txt, (attr_x, r.centery - F["body_sm"].get_height() // 2), T.TX_MUTED)
                if ar.collidepoint(mouse) and k in data.ATTRIBUTE_HELP:
                    t, d = data.ATTRIBUTE_HELP[k]
                    self.tooltip = format_tooltip(t, d, F)
                attr_x += tw + 20

        for i, unit in enumerate(self.picks):
            r = pygame.Rect(cx, y + i * (74 + T.S * 2), cw, 74)
            sel = unit == self.leader_pick
            c = Combatant(unit)
            draw_row(screen, F, r, unit_to_ch(c), selected=sel, draw_trailing=_trailing)
            self.leader_rects.append((r, unit))

        rows_h = len(self.picks) * (74 + T.S * 2) + T.S * 4
        y += rows_h

        self.continue_rect = pygame.Rect(cx + cw - 200, y, 200, 44)
        can_cont = self.leader_pick is not None
        draw_button(screen, F, self.continue_rect, "FOUND THE GUILD", primary=True, enabled=can_cont, mpos=mouse)

        text(screen, F["body_sm"], "[Esc] quit", (T.S * 4, H - 18), T.TX_FAINT)
