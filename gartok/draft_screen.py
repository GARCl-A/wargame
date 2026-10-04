"""Draft screen: build your squad by picking 1 of 3 candidates, three times,
then naming the guild and picking its banner, then choosing which of the
three leads it.

Players have 3 Commission Tokens across the entire squad draft to tailor candidates
into essential archetypes (Leaders, Pack Mules, Heavy Hitters, etc.) via a dedicated
modal, eliminating the slot-machine reroll loop while maintaining tabletop emergent variety.

`on_done(picks, leader, name, banner_color, banner_icon)` -- the "identity"
phase (name + banner, purely cosmetic -- see `Guild.name`/`banner_color`/
`banner_icon` in `guild.py`) recolours every unit token live via
`theme.set_player_color` as the player picks, so the leader-pick cards that
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
from .theme import BANNER_COLORS, set_player_color
from .ui.primitives import (
    TOKEN_INK,
    caps,
    draw_button,
    draw_tooltip,
    ellipsize,
    format_tooltip,
    modal_card,
    panel,
    smooth_circle,
    text,
    token_badge,
    tracked,
)
from .ui.sheet_card import draw_row, draw_sheet, sheet_height, unit_to_ch
from .ui.tokens import ARCHETYPE_COLORS, T, mix
from .unit import Unit

TEAM_SIZE = 3
DRAFT_ROUNDS = 3
DRAFT_CHOICES = 3
COMMISSION_TOKENS = 3
_MAX_GUILD_NAME = 24


class DraftScreen(Screen):
    native = True

    def __init__(self, fonts, on_done):
        super().__init__()
        self.F = fonts
        self.on_done = on_done
        self.picks = []
        self.phase = "pick"        # "pick" (rounds 1-3) | "identity"
        self.tokens = COMMISSION_TOKENS
        self.commissioned_labels = []
        self.commission_modal_open = False
        self.selected_modal_labels = []

        self.commission_btn_rect = None
        self.modal_rect = None
        self.modal_item_rects = []
        self.modal_confirm_rect = None
        self.modal_cancel_rect = None
        self.card_rects = []

        # legacy button rects preserved as None for safety
        self.edit_btn_rect = None
        self.reroll_btn_rect = None

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
        self._new_candidates()

    # ------------------------------------------------------------------ #
    def _new_candidates(self):
        self.candidates = [Unit("player") for _ in range(DRAFT_CHOICES)]
        self.commissioned_labels = []

    def _pick(self, unit):
        self.picks.append(unit)
        self.commissioned_labels = []
        if len(self.picks) < DRAFT_ROUNDS:
            self._new_candidates()
        else:
            self.phase = "identity"

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
                self.commission_modal_open = False
                self.selected_modal_labels = []
            return

        super().handle_event(event)

    # ------------------------------------------------------------------ #
    def _click(self, px):
        if self.phase == "identity":
            self._click_identity(px)
            return

        if self.commission_modal_open:
            self._click_commission_modal(px)
            return

        if self.commission_btn_rect and self.commission_btn_rect.collidepoint(px):
            if self.tokens > 0:
                self.commission_modal_open = True
                self.selected_modal_labels = []
            return

        for rect, unit in self.card_rects:
            if rect.collidepoint(px):
                self._pick(unit)
                return

    def _click_commission_modal(self, px):
        if self.modal_confirm_rect and self.modal_confirm_rect.collidepoint(px):
            cost = len(self.selected_modal_labels)
            if 1 <= cost <= self.tokens:
                self.tokens -= cost
                self.commissioned_labels = list(self.selected_modal_labels)
                self.candidates = [
                    generate_candidate(self.commissioned_labels)
                    for _ in range(DRAFT_CHOICES)
                ]
                self.commission_modal_open = False
                self.selected_modal_labels = []
            return

        if self.modal_cancel_rect and self.modal_cancel_rect.collidepoint(px):
            self.commission_modal_open = False
            self.selected_modal_labels = []
            return

        for rect, key, can_toggle in self.modal_item_rects:
            if rect.collidepoint(px):
                if key in self.selected_modal_labels:
                    self.selected_modal_labels.remove(key)
                elif can_toggle:
                    self.selected_modal_labels.append(key)
                return

        if self.modal_rect and not self.modal_rect.collidepoint(px):
            self.commission_modal_open = False
            self.selected_modal_labels = []
            return

    # ------------------------------------------------------------------ #
    # soft tutorial (screen.py) -- one id per phase                      #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return {"pick": "draft.pick", "identity": "draft.identity"}.get(self.phase)

    def tutorial_badge_rect(self, size):
        W, H = size
        pad = T.S * 4
        return pygame.Rect(W - pad - 28, pad, 28, 28)

    def tutorial_anchor(self, size):
        W, H = size
        pad = T.S * 4
        return (W - pad - 340, pad + 36, 340, "down")

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

        round_no = len(self.picks) + 1

        text(screen, F["titleb"], "SQUAD DRAFT", (T.S * 4, T.S * 4 - 2), T.TX)
        tokens_dots = "● " * self.tokens + "○ " * (COMMISSION_TOKENS - self.tokens)
        sub = (f"Round {round_no} of {DRAFT_ROUNDS}  ·  pick 1 of {DRAFT_CHOICES}  "
               f"·  squad {len(self.picks)}/{TEAM_SIZE}  ·  commission tokens: {tokens_dots.strip()}")
        text(screen, F["body"], sub, (T.S * 4, T.S * 4 + 30), T.TX_MUTED)

        self._draw_top_buttons(screen, mouse)

        rail_h = 92
        header_h = 16 + T.S * 2
        sh = sheet_height("normal")
        footer_h = T.S * 3 + 26 + T.S * 3
        card_h = T.S * 3 + header_h + sh + footer_h

        group_h = card_h + T.S * 4 + rail_h
        slack = max(0, (screen.get_height() - 18) - (T.S * 4 + 58) - group_h)
        top = T.S * 4 + 58 + slack // 2
        rail_y = top + card_h + T.S * 4
        gap = T.S * 3
        card_w = (screen.get_width() - 2 * (T.S * 4) - (DRAFT_CHOICES - 1) * gap) // DRAFT_CHOICES

        self.card_rects = []
        for i, unit in enumerate(self.candidates):
            rect = pygame.Rect(T.S * 4 + i * (card_w + gap), top, card_w, card_h)
            self.card_rects.append((rect, unit))
            hover = rect.collidepoint(mouse) and not self.commission_modal_open
            self._draw_card(screen, rect, unit, hover, mouse)

        self._draw_squad_rail(screen, T.S * 4, rail_y, screen.get_width() - 2 * (T.S * 4), rail_h)
        text(screen, F["body_sm"], "[Esc] quit", (T.S * 4, screen.get_height() - 18), T.TX_FAINT)

        if self.commission_modal_open:
            self._draw_commission_modal(screen, mouse)

        if getattr(self, "tooltip", None):
            draw_tooltip(screen, F, self.tooltip, mouse)

    # ------------------------------------------------------------------ #
    def _draw_top_buttons(self, screen, mouse):
        F = self.F
        W = screen.get_width()
        pad = T.S * 4
        has_tut = self.tutorial_key() is not None
        offset = (28 + T.S) if has_tut else 0

        btn_w = 190
        r_comm = pygame.Rect(W - pad - offset - btn_w, pad, btn_w, 28)
        self.commission_btn_rect = r_comm

        if self.tokens > 0:
            lbl = f"COMMISSION ({self.tokens} TOKENS)" if self.tokens > 1 else "COMMISSION (1 TOKEN)"
            draw_button(screen, F, r_comm, lbl, primary=(self.tokens == COMMISSION_TOKENS),
                        enabled=not self.commission_modal_open, mpos=mouse)
        else:
            draw_button(screen, F, r_comm, "NO TOKENS LEFT", enabled=False, mpos=mouse)

    # ------------------------------------------------------------------ #
    def _draw_commission_modal(self, screen, mouse):
        F = self.F
        cw, ch = 230, 52
        gap = 8
        cols = 3
        rows = 4
        pw = cols * cw + (cols - 1) * gap + 48
        ph = rows * ch + (rows - 1) * gap + 144

        panel_r = modal_card(screen, (pw, ph), veil=True)
        self.modal_rect = panel_r

        text(screen, F["titleb"], "COMMISSION RECRUITS", (panel_r.x + 24, panel_r.y + 16), T.TX)
        token_str = f"{self.tokens} token" if self.tokens == 1 else f"{self.tokens} tokens"
        sub = f"Guarantee archetypes for this round's 3 candidates. You have {token_str} remaining."
        text(screen, F["body_sm"], sub, (panel_r.x + 24, panel_r.y + 44), T.TX_MUTED)

        self.modal_item_rects = []
        for i, (key, arc) in enumerate(ARCHETYPES.items()):
            col_i = i % cols
            row_i = i // cols
            rx = panel_r.x + 24 + col_i * (cw + gap)
            ry = panel_r.y + 72 + row_i * (ch + gap)
            r = pygame.Rect(rx, ry, cw, ch)

            selected = key in self.selected_modal_labels
            compatible = is_compatible(self.selected_modal_labels, key)
            tokens_left = len(self.selected_modal_labels) < self.tokens
            can_toggle = selected or (tokens_left and compatible)

            hover = r.collidepoint(mouse) and can_toggle
            if selected:
                pygame.draw.rect(screen, T.STEEL_HI, r)
                pygame.draw.rect(screen, T.BRASS, r, 2)
            elif can_toggle:
                pygame.draw.rect(screen, T.STEEL_HI if hover else T.STEEL, r)
                pygame.draw.rect(screen, T.BRASS if hover else T.STEEL_LINE, r, 1)
            else:
                pygame.draw.rect(screen, T.TABLE, r)
                pygame.draw.rect(screen, T.STEEL_LINE, r, 1)

            mark = "[✓] " if selected else "[ ] "
            arc_col = ARCHETYPE_COLORS.get(arc.style, T.TX_MUTED)
            lbl_col = T.BRASS if selected else (arc_col if can_toggle else T.TX_FAINT)
            caps(screen, F["microb"], mark + arc.label, (r.x + 10, r.y + 8), lbl_col)

            if not compatible and not selected:
                desc = "Incompatible with selection"
                dcol = T.TX_FAINT
            elif not tokens_left and not selected:
                desc = "Token limit reached"
                dcol = T.TX_FAINT
            else:
                desc = ellipsize(arc.desc, F["body_sm"], cw - 20)
                dcol = T.TX_MUTED if can_toggle else T.TX_FAINT

            text(screen, F["body_sm"], desc, (r.x + 10, r.y + 26), dcol)

            if r.collidepoint(mouse):
                title = arc.label + (" [SELECTED]" if selected else "")
                self.tooltip = format_tooltip(title, arc.desc, F)

            self.modal_item_rects.append((r, key, can_toggle))

        fy = panel_r.bottom - 48
        cost = len(self.selected_modal_labels)
        cost_txt = f"Cost: {cost} of {self.tokens} tokens"
        text(screen, F["body"], cost_txt, (panel_r.x + 24, fy + 8),
             T.BRASS if cost > 0 else T.TX_MUTED)

        cancel_r = pygame.Rect(panel_r.right - 24 - 100 - 8 - 140, fy, 100, 32)
        self.modal_cancel_rect = cancel_r
        draw_button(screen, F, cancel_r, "CANCEL", ghost=True, mpos=mouse)

        confirm_r = pygame.Rect(panel_r.right - 24 - 140, fy, 140, 32)
        self.modal_confirm_rect = confirm_r
        conf_lbl = f"CONFIRM ({cost})" if cost > 0 else "CONFIRM"
        draw_button(screen, F, confirm_r, conf_lbl, primary=True,
                    enabled=(1 <= cost <= self.tokens), mpos=mouse)

    # ------------------------------------------------------------------ #
    def _draw_card(self, screen, rect, unit, hover, mouse):
        F = self.F
        pad = T.S * 3

        header_h = 16 + T.S * 2
        sh = sheet_height("normal")
        footer_h = T.S * 3 + 26 + T.S * 3

        actual_h = pad + header_h + sh + footer_h
        bg_rect = pygame.Rect(rect.x, rect.y, rect.w, max(rect.h, actual_h))
        panel(screen, bg_rect, hover=hover, width=2 if hover else 1)

        ty = bg_rect.y + pad
        tx = bg_rect.x + pad

        # Prioritize commissioned archetypes to appear first on the card
        tags = unit_archetypes(unit)
        tags.sort(key=lambda t: 0 if t[0] in self.commissioned_labels else 1)

        for label, style, desc in tags[:3]:
            tcol = ARCHETYPE_COLORS.get(style, T.TX_MUTED)
            is_comm = label in self.commissioned_labels
            display_label = f"★ {label}" if is_comm else label
            w = F["microb"].size(display_label)[0] + 12
            pill = pygame.Rect(tx, ty, w, 16)
            pill_fill = mix(T.STEEL_HI, T.BRASS, 0.25) if is_comm else T.STEEL_HI
            pill_border = T.BRASS if is_comm else tcol
            pygame.draw.rect(screen, pill_fill, pill, border_radius=4)
            pygame.draw.rect(screen, pill_border, pill, 2 if is_comm else 1, border_radius=4)
            text(screen, F["microb"], display_label, pill.center, T.BRASS if is_comm else tcol, center=True)
            if pill.collidepoint(mouse):
                title = label + (" (COMMISSIONED)" if is_comm else "")
                self.tooltip = format_tooltip(title, desc, F)
            tx += w + T.S

        ty += 16 + T.S * 2

        sheet_rect = pygame.Rect(bg_rect.x + pad, ty, bg_rect.w - 2 * pad, sh)
        ch = unit_to_ch(Combatant(unit))
        used_h, tip = draw_sheet(screen, F, sheet_rect, ch, density="normal", mouse=mouse)
        if tip:
            self.tooltip = tip

        ty += used_h + T.S * 3

        fr = pygame.Rect(bg_rect.x + pad, ty, bg_rect.w - 2 * pad, 26)
        panel(screen, fr, hover=hover)
        text(screen, F["microb"] if hover else F["body_sm"], "PICK" if hover else "click to pick",
             fr.center, T.BRASS if hover else T.TX_MUTED, center=True)

    # ------------------------------------------------------------------ #
    def _draw_squad_rail(self, screen, x, y, w, h):
        F = self.F
        tracked(screen, F["microb"], "YOUR SQUAD", (x, y), T.TX_FAINT)
        y += 16
        slot_w = (w - 2 * (T.S * 2)) // 3
        for i in range(TEAM_SIZE):
            r = pygame.Rect(x + i * (slot_w + T.S * 2), y, slot_w, h - 16)
            if i < len(self.picks):
                u = self.picks[i]
                panel(screen, r)
                pygame.draw.rect(screen, T.GREEN, r, 1)
                dot = (r.x + T.S * 3 + 9, r.centery)
                token_badge(screen, F, dot, u, r=12)
                text(screen, F["bodyb"], u.name, (dot[0] + 20, r.y + T.S * 2), T.TX)
                text(screen, F["body_sm"], f"{u.race['name']}  ·  {u.occupation['name']}",
                     (dot[0] + 20, r.y + T.S * 2 + 18), T.TX_MUTED)
                attr_x = dot[0] + 20
                for k, name in (("STR", "strength"), ("DEX", "dexterity"),
                                ("CON", "constitution"), ("INT", "intelligence"),
                                ("WIS", "wisdom"), ("CHA", "charisma")):
                    txt = f"{k} {getattr(u, name)}"
                    tw = F["body_sm"].size(txt)[0]
                    ar = pygame.Rect(attr_x, r.y + T.S * 2 + 36, tw, 16)
                    text(screen, F["body_sm"], txt, (attr_x, r.y + T.S * 2 + 36), T.TX_MUTED)
                    if ar.collidepoint(self.mouse) and k in data.ATTRIBUTE_HELP:
                        t, d = data.ATTRIBUTE_HELP[k]
                        self.tooltip = format_tooltip(t, d, F)
                    attr_x += tw + 8
            else:
                pygame.draw.rect(screen, T.STEEL_LINE, r, 1)
                text(screen, F["body_sm"], f"slot {i + 1}", r.center, T.TX_FAINT, center=True)

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
            for k, name in (("STR", "strength"), ("DEX", "dexterity"),
                            ("CON", "constitution"), ("INT", "intelligence"),
                            ("WIS", "wisdom"), ("CHA", "charisma")):
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
