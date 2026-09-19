"""Draft screen: build your squad by picking 1 of 3 candidates, three times,
then naming the guild and picking its banner, then choosing which of the
three leads it.

The pencil/EDIT toggle swaps a candidate's race or occupation before you lock
it in. Presentation only -- the character model lives in `unit` / `data`.

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
from .combatant import Combatant
from .screen import Screen
from .theme import (
    ACCENT,
    ACCENT_INK,
    BANNER_COLORS,
    INFO,
    INK,
    INK_DIM,
    INK_FAINT,
    LINE,
    LINE_SOFT,
    MARGIN,
    OK,
    RADIUS,
    SP1,
    SP2,
    SP3,
    SP4,
    SURFACE_1,
    SURFACE_2,
    SURFACE_3,
    TOKEN_INK,
    WARN,
    draw_tooltip,
    ellipsize,
    format_tooltip,
    panel,
    set_player_color,
    smooth_circle,
    text,
    token_badge,
    tracked,
)
from .ui.sheet_card import draw_sheet, sheet_height, unit_to_ch
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts
from .unit import Unit
from .widgets import draw_button

TEAM_SIZE = 3
DRAFT_ROUNDS = 3
DRAFT_CHOICES = 3
_MAX_GUILD_NAME = 24


def _archetypes(u):
    """Two or three quick read tags to help the pick."""
    tags = []
    if u.size == "Large":
        tags.append(("LARGE", INFO, "Takes up more space on the grid; has higher base health."))
    if u.dr or u.ac >= 12 or u.hp_max >= 9:
        tags.append(("TOUGH", OK, "High survivability from HP, Damage Reduction, or Armor Class."))
    if u.ranged:
        tags.append(("RANGED", INFO, "Carries a ranged weapon to attack from distance."))
    if u.speed >= 7:
        tags.append(("FAST", OK, "Swift and agile, with high movement and evasion."))
    if u.mod_strength >= 2:
        tags.append(("BRUTE", WARN, "Heavy hitter with high melee damage and carry capacity."))
    if u.mod_charisma >= 1:
        tags.append(("TAUNTER", WARN, "Charismatic. Effective at demoralizing enemies and recruiting."))
    if u.ability.darkvision:
        tags.append(("SEES IN DARK", INFO, "Can see in darkness without needing a light source."))
    return tags[:3] or [("BALANCED", INK_FAINT, "Balanced stats with no single specialization.")]


class DraftScreen(Screen):
    native = True

    def __init__(self, fonts, on_done):
        super().__init__()
        self.fonts = fonts
        self.on_done = on_done
        self.picks = []
        self.phase = "pick"        # "pick" (rounds 1-3) | "identity" | "leader"
        self.edit_mode = False
        self.picker = None
        self.edit_btn_rect = None
        self.card_rects = []
        self.edit_rects = []
        self.picker_rects = []
        # identity: guild name (click-to-type, see char_editor_screen.py's
        # pattern) + banner colour/icon, picked from a curated set (not a
        # free painter -- see the module docstring)
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
        set_player_color(self.banner_color)     # reset tokens to the default for a fresh draft
        self._new_candidates()

    # ------------------------------------------------------------------ #
    def _new_candidates(self):
        self.candidates = [Unit("player") for _ in range(DRAFT_CHOICES)]

    def _pick(self, unit):
        self.picks.append(unit)
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
        super().handle_event(event)

    # ------------------------------------------------------------------ #
    def _click(self, px):
        if self.phase == "identity":
            self._click_identity(px)
            return

        if self.picker is not None:
            for rect, name in self.picker_rects:
                if rect.collidepoint(px):
                    unit, field = self.picker
                    (unit.set_race if field == "race" else unit.set_occupation)(name)
                    self.picker = None
                    return
            self.picker = None
            return

        if self.edit_btn_rect and self.edit_btn_rect.collidepoint(px):
            self.edit_mode = not self.edit_mode
            return

        if getattr(self, "reroll_btn_rect", None) and self.reroll_btn_rect.collidepoint(px):
            self._new_candidates()
            return

        if self.edit_mode:
            for rect, unit, field in self.edit_rects:
                if rect.collidepoint(px):
                    self.picker = (unit, field)
                    return
            return

        for rect, unit in self.card_rects:
            if rect.collidepoint(px):
                self._pick(unit)
                return

    # ------------------------------------------------------------------ #
    # soft tutorial (screen.py) -- one id per phase                      #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return {"pick": "draft.pick", "identity": "draft.identity"}.get(self.phase)

    def _click_identity(self, px):
        if self.editing_name:                 # a click anywhere commits the field being typed
            self.guild_name, self.editing_name = self.name_buf, False
        if self.name_rect and self.name_rect.collidepoint(px):
            self.name_buf, self.editing_name = self.guild_name, True
            return
        for rect, color in self.color_rects:
            if rect.collidepoint(px):
                self.banner_color = color
                set_player_color(color)       # live preview on every token already on screen
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
        f = self.fonts
        screen.fill((18, 19, 24))
        mouse = self.mouse
        self.tooltip = None

        if self.phase == "identity":
            self._draw_identity(screen)
            if getattr(self, "tooltip", None):
                self._draw_tooltip(screen)
            return

        round_no = len(self.picks) + 1

        text(screen, "SQUAD DRAFT", f.title, INK, (MARGIN, MARGIN - 2))
        if self.edit_mode:
            sub, col = ("EDIT MODE  ·  click 'swap' to change race / occupation  ·  "
                        "EDITING goes back to picking", ACCENT)
        else:
            sub, col = (f"Round {round_no} of {DRAFT_ROUNDS}  ·  pick 1 of {DRAFT_CHOICES}  "
                        f"·  squad {len(self.picks)}/{TEAM_SIZE}", INK_DIM)
        text(screen, sub, f.body, col, (MARGIN, MARGIN + 30))
        self._draw_top_buttons(screen, mouse)

        rail_h = 92
        
        # calculate actual_h for the cards so they perfectly stack with the rail
        header_h = 16 + SP2
        if self.edit_mode:
            header_h += 2 * (28 + SP1) + SP1
        sh = sheet_height("normal")
        footer_h = (SP3 + 26 + SP3) if not self.edit_mode else SP3
        card_h = SP3 + header_h + sh + footer_h
        
        group_h = card_h + SP4 + rail_h
        slack = max(0, (screen.get_height() - 18) - (MARGIN + 58) - group_h)
        top = MARGIN + 58 + slack // 2
        rail_y = top + card_h + SP4
        gap = SP3
        card_w = (screen.get_width() - 2 * MARGIN - (DRAFT_CHOICES - 1) * gap) // DRAFT_CHOICES

        self.card_rects = []
        self.edit_rects = []
        for i, unit in enumerate(self.candidates):
            rect = pygame.Rect(MARGIN + i * (card_w + gap), top, card_w, card_h)
            self.card_rects.append((rect, unit))
            hover = rect.collidepoint(mouse) and not self.edit_mode
            self._draw_card(screen, rect, unit, hover, mouse)

        self._draw_squad_rail(screen, MARGIN, rail_y, screen.get_width() - 2 * MARGIN, rail_h)
        text(screen, "[Esc] quit", f.body_sm, INK_FAINT, (MARGIN, screen.get_height() - 18))

        if self.picker is not None:
            self._draw_picker(screen, mouse)

        if getattr(self, "tooltip", None):
            self._draw_tooltip(screen)

    def _draw_tooltip(self, screen):
        draw_tooltip(screen, self.fonts.body_sm, self.tooltip, self.mouse)

    # ------------------------------------------------------------------ #
    def _draw_identity(self, screen):
        """Name + banner (colour, then emblem), then FOUND THE GUILD. A form,
        not a card gallery -- its own layout, no `card_rects`/`_draw_card`."""
        f = self.fonts
        W, _ = screen.get_size()
        mouse = self.mouse

        cw = min(560, W - 2 * MARGIN)
        cx = (W - cw) // 2

        text(screen, "FOUND THE GUILD", f.title, ACCENT, (cx, MARGIN - 2))
        text(screen, "Name your guild, pick a banner, and choose your leader.", f.body, INK_DIM,
             (cx, MARGIN + 30))

        y = MARGIN + 74

        # --- preview + name field ----------------------------------- #
        pv = (cx + 24, y + 28)
        smooth_circle(screen, self.banner_color, pv, 24)
        art = artwork.banner_icon(self.banner_icon, 32, TOKEN_INK)
        if art is not None:
            screen.blit(art, art.get_rect(center=pv))

        nx = cx + 64
        nw = cw - 64
        tracked(screen, "GUILD NAME", f.label, INK_FAINT, (nx, y))
        self.name_rect = pygame.Rect(nx, y + 16, nw, 40)
        hov = self.name_rect.collidepoint(mouse)
        panel(screen, self.name_rect, fill=SURFACE_3 if (hov or self.editing_name) else SURFACE_2,
              border=ACCENT if (hov or self.editing_name) else LINE, width=1, radius=RADIUS)
        shown = self.name_buf + "|" if self.editing_name else self.guild_name or "click to name your guild"
        col = INK if (self.editing_name or self.guild_name) else INK_FAINT
        text(screen, shown, f.body, col, (self.name_rect.x + SP3, self.name_rect.centery - 8))
        y += 56 + SP3

        # --- banner colour: a curated palette, not a free picker --------- #
        tracked(screen, "BANNER COLOUR", f.label, INK_FAINT, (cx, y))
        y += 18
        self.color_rects = []
        sw = 40
        for i, (_, color) in enumerate(BANNER_COLORS):
            r = pygame.Rect(cx + i * (sw + SP2), y, sw, sw)
            sel = color == self.banner_color
            hov = r.collidepoint(mouse)
            smooth_circle(screen, color, r.center, sw // 2)
            smooth_circle(screen, ACCENT if sel else (LINE if hov else LINE_SOFT),
                          r.center, sw // 2, 3 if sel else 1)
            self.color_rects.append((r, color))
        y += sw + SP3

        # --- banner emblem: a curated gallery, not a paint tool ---------- #
        tracked(screen, "EMBLEM", f.label, INK_FAINT, (cx, y))
        y += 18
        self.icon_rects = []
        isz = 44
        per_row = max(1, (cw + SP2) // (isz + SP2))
        for i, (_, slug, _label) in enumerate(artwork.BANNER_ICONS):
            col_i, row_i = i % per_row, i // per_row
            r = pygame.Rect(cx + col_i * (isz + SP2), y + row_i * (isz + SP2), isz, isz)
            sel = slug == self.banner_icon
            hov = r.collidepoint(mouse)
            panel(screen, r, fill=SURFACE_3 if (sel or hov) else SURFACE_1,
                  border=ACCENT if sel else (LINE if hov else LINE_SOFT),
                  width=2 if sel else 1, radius=8)
            smooth_circle(screen, self.banner_color, r.center, 14)
            art = artwork.banner_icon(slug, isz - 16, TOKEN_INK)
            if art is not None:
                screen.blit(art, art.get_rect(center=r.center))
            self.icon_rects.append((r, slug))
        rows = (len(artwork.BANNER_ICONS) + per_row - 1) // per_row
        y += rows * (isz + SP2) + SP3

        # --- guild leader ------------------------------------------ #
        tracked(screen, "WHO LEADS THE GUILD?", f.label, INK_FAINT, (cx, y))
        y += 18
        self.leader_rects = []
        
        from .combatant import Combatant
        from .ui.sheet_card import draw_row, unit_to_ch
        
        F = ui_fonts()
        def _trailing(surf, r, ch):
            u = ch["unit"]
            attr_x = r.right - 380
            for k, name in (("STR", "strength"), ("DEX", "dexterity"),
                            ("CON", "constitution"), ("INT", "intelligence"),
                            ("WIS", "wisdom"), ("CHA", "charisma")):
                txt = f"{k} {getattr(u, name)}"
                tw = f.body_sm.size(txt)[0]
                ar = pygame.Rect(attr_x, r.centery - 8, tw, 16)
                text(surf, txt, f.body_sm, INK_DIM, (attr_x, r.centery - 8))
                if ar.collidepoint(mouse) and k in data.ATTRIBUTE_HELP:
                    t, d = data.ATTRIBUTE_HELP[k]
                    self.tooltip = format_tooltip(t, d, f)
                attr_x += tw + 20

        for i, unit in enumerate(self.picks):
            r = pygame.Rect(cx, y + i * (74 + SP2), cw, 74)
            sel = unit == self.leader_pick
            c = Combatant(unit)
            draw_row(screen, F, r, unit_to_ch(c), selected=sel, draw_trailing=_trailing)
            self.leader_rects.append((r, unit))
            
        rows_h = len(self.picks) * (74 + SP2) + SP4
        y += rows_h

        # --- confirm --------------------------------- #

        self.continue_rect = pygame.Rect(cx, y, cw, 44)
        hov = self.continue_rect.collidepoint(mouse)
        can_cont = self.leader_pick is not None
        panel(screen, self.continue_rect, fill=ACCENT if hov and can_cont else SURFACE_3,
              border=ACCENT if can_cont else LINE, width=1, radius=RADIUS)
        text(screen, "FOUND THE GUILD", f.body_bd, (ACCENT_INK if hov else ACCENT) if can_cont else INK_DIM,
             self.continue_rect.center, center=True)

        text(screen, "[Esc] quit", f.body_sm, INK_FAINT, (MARGIN, screen.get_height() - 18))

    # ------------------------------------------------------------------ #
    def _draw_card(self, screen, rect, unit, hover, mouse, leader_pick=False):
        f = self.fonts
        pad = SP3
        
        # Calculate dynamic height
        header_h = 16 + SP2
        if self.edit_mode:
            header_h += 2 * (28 + SP1) + SP1
            
        sh = sheet_height("normal")
        footer_h = (SP3 + 26 + SP3) if not self.edit_mode else SP3
        
        actual_h = pad + header_h + sh + footer_h
        bg_rect = pygame.Rect(rect.x, rect.y, rect.w, max(rect.h, actual_h))
        
        # The background panel uses war-table palette to match sheet_card
        pygame.draw.rect(screen, T.TABLE, bg_rect, border_radius=RADIUS)
        pygame.draw.rect(screen, ACCENT if hover else T.STEEL_LINE, bg_rect, 2, border_radius=RADIUS)
        
        # --- floating archetypes ---
        ty = bg_rect.y + pad
        tx = bg_rect.x + pad
        for label, tcol, desc in _archetypes(unit):
            w = f.label.size(label)[0] + 12
            pill = pygame.Rect(tx, ty, w, 16)
            pygame.draw.rect(screen, SURFACE_1, pill, border_radius=4)
            pygame.draw.rect(screen, tcol, pill, 1, border_radius=4)
            text(screen, label, f.label, tcol, (pill.centerx, pill.centery - 1), center=True)
            if pill.collidepoint(mouse):
                self.tooltip = desc
            tx += w + SP1
            
        ty += 16 + SP2

        # --- floating edit mode buttons ---
        if self.edit_mode:
            for field, lbl, val in (("race", "RACE", unit.race["name"]),
                                    ("occupation", "OCCUP", unit.occupation["name"])):
                br = pygame.Rect(bg_rect.x + pad, ty, bg_rect.w - 2 * pad, 28)
                ty += 28 + SP1
                hov = br.collidepoint(mouse)
                panel(screen, br, fill=SURFACE_3 if hov else SURFACE_1,
                      border=ACCENT if hov else LINE, width=1, radius=4)
                text(screen, f"{lbl}  {val}", f.body_sm, INK, (br.x + SP2, br.y + 7))
                text(screen, "swap", f.label, ACCENT if hov else INK_DIM,
                     (br.right - SP2, br.y + 8), right=True)
                self.edit_rects.append((br, unit, field))
            ty += SP1

        # --- the shared sheet component ---
        sheet_rect = pygame.Rect(bg_rect.x + pad, ty, bg_rect.w - 2 * pad, sh)
        ch = unit_to_ch(Combatant(unit))
        used_h, tip = draw_sheet(screen, ui_fonts(), sheet_rect, ch, density="normal", mouse=mouse)
        if tip:
            self.tooltip = tip
            
        ty += used_h + SP3

        # --- footer --------------------------------------- #
        if not self.edit_mode:
            fr = pygame.Rect(bg_rect.x + pad, ty, bg_rect.w - 2 * pad, 26)
            panel(screen, fr, fill=ACCENT if hover else SURFACE_3,
                  border=ACCENT if hover else LINE, width=1, radius=4)
            text(screen, "PICK" if hover else "click to pick",
                 f.label if hover else f.body_sm,
                 ACCENT_INK if hover else INK_DIM, fr.center, center=True)

    # ------------------------------------------------------------------ #
    def _draw_squad_rail(self, screen, x, y, w, h):
        f = self.fonts
        tracked(screen, "YOUR SQUAD", f.label, INK_FAINT, (x, y))
        y += 16
        slot_w = (w - 2 * SP2) // 3
        for i in range(TEAM_SIZE):
            r = pygame.Rect(x + i * (slot_w + SP2), y, slot_w, h - 16)
            if i < len(self.picks):
                u = self.picks[i]
                panel(screen, r, fill=SURFACE_2, border=OK, width=1)
                dot = (r.x + SP3 + 9, r.centery)
                token_badge(screen, dot, u, f, r=12)
                text(screen, u.name, f.body_bd, INK, (dot[0] + 20, r.y + SP2))
                text(screen, f"{u.race['name']}  ·  {u.occupation['name']}",
                     f.body_sm, INK_DIM, (dot[0] + 20, r.y + SP2 + 18))
                attr_x = dot[0] + 20
                for k, name in (("STR", "strength"), ("DEX", "dexterity"),
                                ("CON", "constitution"), ("INT", "intelligence"),
                                ("WIS", "wisdom"), ("CHA", "charisma")):
                    txt = f"{k} {getattr(u, name)}"
                    tw = f.body_sm.size(txt)[0]
                    ar = pygame.Rect(attr_x, r.y + SP2 + 36, tw, 16)
                    text(screen, txt, f.body_sm, INK_DIM, (attr_x, r.y + SP2 + 36))
                    if ar.collidepoint(self.mouse) and k in data.ATTRIBUTE_HELP:
                        t, d = data.ATTRIBUTE_HELP[k]
                        self.tooltip = format_tooltip(t, d, f)
                    attr_x += tw + 8
            else:
                pygame.draw.rect(screen, LINE_SOFT, r, 1, border_radius=RADIUS)
                text(screen, f"slot {i + 1}", f.body_sm, INK_FAINT, r.center, center=True)

    def _draw_top_buttons(self, screen, mouse):
        # Place buttons to the left of the global tutorial button (26px + SP2 gap)
        r_edit = pygame.Rect(screen.get_width() - MARGIN - 26 - SP2 - 96, MARGIN, 96, 30)
        self.edit_btn_rect = r_edit
        draw_button(screen, r_edit, "EDITING" if self.edit_mode else "EDIT", self.fonts,
                   mouse, primary=self.edit_mode, font=self.fonts.label)

        r_reroll = pygame.Rect(r_edit.left - SP2 - 96, MARGIN, 96, 30)
        self.reroll_btn_rect = r_reroll
        draw_button(screen, r_reroll, "REROLL", self.fonts, mouse, font=self.fonts.label)

    # ------------------------------------------------------------------ #
    def _draw_picker(self, screen, mouse):
        f = self.fonts
        unit, field = self.picker
        if field == "race":
            options, current, title = data.RACE_NAMES, unit.race["name"], "Pick a race"
        else:
            options, current, title = (data.OCCUPATION_NAMES, unit.occupation["name"],
                                       "Pick an occupation")

        veil = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 190))
        screen.blit(veil, (0, 0))

        cols = 3
        rows = (len(options) + cols - 1) // cols
        cw, ch, pad = 220, 27, SP4
        pw = cols * cw + 2 * pad
        ph = 52 + rows * ch + SP4
        panel_r = pygame.Rect((screen.get_width() - pw) // 2, (screen.get_height() - ph) // 2, pw, ph)
        panel(screen, panel_r, fill=SURFACE_2, border=ACCENT, width=2, radius=8)
        text(screen, title, f.title, INK, (panel_r.x + pad, panel_r.y + 12))

        self.picker_rects = []
        for i, name in enumerate(options):
            c, rw = i % cols, i // cols
            it = pygame.Rect(panel_r.x + pad + c * cw, panel_r.y + 46 + rw * ch,
                             cw - SP1, ch - SP1)
            sel = name == current
            hov = it.collidepoint(mouse)
            panel(screen, it, fill=SURFACE_3 if (hov or sel) else SURFACE_1,
                  border=ACCENT if sel else (LINE if hov else LINE_SOFT), width=1, radius=4)
            text(screen, name, f.body_sm, ACCENT if sel else INK, (it.x + SP2, it.y + 4))
            self.picker_rects.append((it, name))
        text(screen, "click outside to cancel", f.body_sm, INK_FAINT,
             (panel_r.x + pad, panel_r.bottom - 20))
