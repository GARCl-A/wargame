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
from .theme import (ACCENT, ACCENT_INK, BANNER_COLORS, DANGER, DEMO_HL, INFO,
                    INK, INK_DIM, INK_FAINT, LINE, LINE_SOFT, MARGIN, OK,
                    RADIUS, SP1, SP2, SP3, SP4, SURFACE_1, SURFACE_2,
                    SURFACE_3, TOKEN_INK, WARN,
                    Stack, chip, ellipsize, panel, section, set_player_color,
                    token_badge, text, tracked, wrap_lines)
from .unit import Unit

TEAM_SIZE = 3
DRAFT_ROUNDS = 3
DRAFT_CHOICES = 3
_MAX_GUILD_NAME = 24


def _archetypes(u):
    """Two or three quick read tags to help the pick."""
    tags = []
    if u.size == "Large":
        tags.append(("LARGE", INFO))
    if u.dr or u.ac >= 12 or u.hp_max >= 9:
        tags.append(("TOUGH", OK))
    if u.ranged:
        tags.append(("RANGED", INFO))
    if u.speed >= 7:
        tags.append(("FAST", OK))
    if u.mod_strength >= 2:
        tags.append(("BRUTE", WARN))
    if u.mod_charisma >= 1:
        tags.append(("TAUNTER", WARN))
    if u.ability.darkvision:
        tags.append(("SEES IN DARK", INFO))
    return tags[:3] or [("BALANCED", INK_FAINT)]


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

        if self.phase == "leader":
            for rect, unit in self.card_rects:
                if rect.collidepoint(px):
                    self.on_done(self.picks, unit, self.guild_name,
                                self.banner_color, self.banner_icon)
                    return
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
        if self.continue_rect and self.continue_rect.collidepoint(px):
            self.phase = "leader"

    # ------------------------------------------------------------------ #
    # drawing                                                            #
    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        screen.fill((18, 19, 24))
        mouse = self.mouse

        if self.phase == "identity":
            self._draw_identity(screen)
            return

        round_no = len(self.picks) + 1
        leader_phase = self.phase == "leader"

        if leader_phase:
            text(screen, "WHO LEADS THE GUILD?", f.title, ACCENT, (MARGIN, MARGIN - 2))
            sub, col = ("This is who you answer to -- their Charisma speaks for the "
                        "group when it haggles, and leads any group they're in. "
                        "Click one to found the guild.", ACCENT)
            text(screen, sub, f.body, col, (MARGIN, MARGIN + 30))
        else:
            text(screen, "SQUAD DRAFT", f.title, INK, (MARGIN, MARGIN - 2))
            if self.edit_mode:
                sub, col = ("EDIT MODE  ·  click 'swap' to change race / occupation  ·  "
                            "EDITING goes back to picking", ACCENT)
            else:
                sub, col = (f"Round {round_no} of {DRAFT_ROUNDS}  ·  pick 1 of {DRAFT_CHOICES}  "
                            f"·  squad {len(self.picks)}/{TEAM_SIZE}", INK_DIM)
            text(screen, sub, f.body, col, (MARGIN, MARGIN + 30))
            self._draw_edit_button(screen, mouse)

        rail_h = 92
        card_h = 548
        group_h = card_h + SP4 + rail_h
        slack = max(0, (screen.get_height() - 18) - (MARGIN + 58) - group_h)
        top = MARGIN + 58 + slack // 2
        rail_y = top + card_h + SP4
        gap = SP3
        card_w = (screen.get_width() - 2 * MARGIN - (DRAFT_CHOICES - 1) * gap) // DRAFT_CHOICES

        self.card_rects = []
        self.edit_rects = []
        cards = self.picks if leader_phase else self.candidates
        for i, unit in enumerate(cards):
            rect = pygame.Rect(MARGIN + i * (card_w + gap), top, card_w, card_h)
            self.card_rects.append((rect, unit))
            hover = rect.collidepoint(mouse) and not self.edit_mode
            self._draw_card(screen, rect, unit, hover, mouse, leader_pick=leader_phase)

        if not leader_phase:
            self._draw_squad_rail(screen, MARGIN, rail_y, screen.get_width() - 2 * MARGIN, rail_h)
        text(screen, "[Esc] quit", f.body_sm, INK_FAINT, (MARGIN, screen.get_height() - 18))

        if self.picker is not None:
            self._draw_picker(screen, mouse)

    # ------------------------------------------------------------------ #
    def _draw_identity(self, screen):
        """Name + banner (colour, then emblem), then FOUND THE GUILD. A form,
        not a card gallery -- its own layout, no `card_rects`/`_draw_card`."""
        f = self.fonts
        W, _ = screen.get_size()
        mouse = self.mouse

        text(screen, "NAME YOUR GUILD", f.title, ACCENT, (MARGIN, MARGIN - 2))
        text(screen, "Purely cosmetic -- pick a name and a banner. Every unit's "
             "token shows the colour from here on.", f.body, INK_DIM,
             (MARGIN, MARGIN + 30))

        cx = MARGIN
        cw = min(560, W - 2 * MARGIN)
        y = MARGIN + 74

        # --- name field (click-to-type, same pattern as char_editor_screen) #
        tracked(screen, "GUILD NAME", f.label, INK_FAINT, (cx, y))
        y += 16
        self.name_rect = pygame.Rect(cx, y, cw, 40)
        hov = self.name_rect.collidepoint(mouse)
        panel(screen, self.name_rect, fill=SURFACE_3 if (hov or self.editing_name) else SURFACE_2,
              border=ACCENT if (hov or self.editing_name) else LINE, width=1, radius=RADIUS)
        shown = self.name_buf + "|" if self.editing_name else self.guild_name or "click to name your guild"
        col = INK if (self.editing_name or self.guild_name) else INK_FAINT
        text(screen, shown, f.body, col, (self.name_rect.x + SP3, self.name_rect.centery - 8))
        y += 40 + SP4

        # --- banner colour: a curated palette, not a free picker --------- #
        tracked(screen, "BANNER COLOUR", f.label, INK_FAINT, (cx, y))
        y += 18
        self.color_rects = []
        sw = 40
        for i, (_, color) in enumerate(BANNER_COLORS):
            r = pygame.Rect(cx + i * (sw + SP2), y, sw, sw)
            sel = color == self.banner_color
            hov = r.collidepoint(mouse)
            pygame.draw.circle(screen, color, r.center, sw // 2)
            pygame.draw.circle(screen, ACCENT if sel else (LINE if hov else LINE_SOFT),
                               r.center, sw // 2, 3 if sel else 1)
            self.color_rects.append((r, color))
        y += sw + SP4

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
            art = artwork.banner_icon(slug, isz - 16, TOKEN_INK)
            if art is not None:
                screen.blit(art, art.get_rect(center=r.center))
            self.icon_rects.append((r, slug))
        rows = (len(artwork.BANNER_ICONS) + per_row - 1) // per_row
        y += rows * (isz + SP2) + SP4

        # --- live preview + confirm --------------------------------- #
        pv = (cx + 30, y + 30)
        pygame.draw.circle(screen, self.banner_color, pv, 30)
        art = artwork.banner_icon(self.banner_icon, 40, TOKEN_INK)
        if art is not None:
            screen.blit(art, art.get_rect(center=pv))
        text(screen, self.guild_name or "The Guild", f.title, INK, (pv[0] + 46, y + 14))
        y += 76

        self.continue_rect = pygame.Rect(cx, y, cw, 44)
        hov = self.continue_rect.collidepoint(mouse)
        panel(screen, self.continue_rect, fill=ACCENT if hov else SURFACE_3,
              border=ACCENT, width=1, radius=RADIUS)
        text(screen, "FOUND THE GUILD", f.body_bd, ACCENT_INK if hov else ACCENT,
             self.continue_rect.center, center=True)

        text(screen, "[Esc] quit", f.body_sm, INK_FAINT, (MARGIN, screen.get_height() - 18))

    # ------------------------------------------------------------------ #
    def _draw_card(self, screen, rect, unit, hover, mouse, leader_pick=False):
        f = self.fonts
        pad = SP3
        preview = Combatant(unit)             # in-fight view of the candidate (ammo, kit, ...)
        s = Stack(rect.x + pad, rect.y, rect.w - 2 * pad)

        panel(screen, rect, fill=SURFACE_2,
              border=ACCENT if hover else LINE_SOFT, width=2, radius=RADIUS)

        # --- header ------------------------------------------------- #
        head = pygame.Rect(rect.x, rect.y, rect.w, 50)
        pygame.draw.rect(screen, SURFACE_3, head,
                         border_top_left_radius=RADIUS, border_top_right_radius=RADIUS)
        tok = (rect.x + pad + 13, rect.y + 25)
        token_badge(screen, tok, unit, f, r=15)
        name_x = tok[0] + 26
        name_w = rect.right - pad - name_x
        text(screen, ellipsize(unit.name, f.card_name, name_w), f.card_name, INK,
             (name_x, rect.y + 7))
        text(screen, ellipsize(f"{unit.race['name']}  ·  {unit.occupation['name']}",
                                f.body_sm, name_w),
             f.body_sm, INK_DIM, (name_x, rect.y + 27))
        s.y = head.bottom + SP3

        # --- tags + context --------------------------------------- #
        tag_row = s.row(17)
        tx = tag_row.x
        for label, tcol in _archetypes(unit):
            w = f.label.size(label)[0] + 12
            pill = pygame.Rect(tx, tag_row.y, w, 16)
            pygame.draw.rect(screen, SURFACE_1, pill, border_radius=4)
            pygame.draw.rect(screen, tcol, pill, 1, border_radius=4)
            text(screen, label, f.label, tcol, (pill.centerx, pill.centery - 1), center=True)
            tx += w + SP1
        s.gap(SP3)
        ctx = s.row(16)
        text(screen, f"{unit.alignment}   ·   {unit.size}   ·   {unit.age} yrs",
             f.body_sm, INK_DIM, (ctx.x, ctx.y))
        s.gap(SP3)

        # --- edit rows ------------------------------------------- #
        if self.edit_mode:
            for field, lbl, val in (("race", "RACE", unit.race["name"]),
                                    ("occupation", "OCCUPATION", unit.occupation["name"])):
                br = s.row(28)
                s.gap(SP1)
                hov = br.collidepoint(mouse)
                panel(screen, br, fill=SURFACE_3 if hov else SURFACE_1,
                      border=ACCENT if hov else LINE, width=1, radius=4)
                text(screen, f"{lbl}  {val}", f.body_sm, INK, (br.x + SP2, br.y + 7))
                text(screen, "swap", f.label, ACCENT if hov else INK_DIM,
                     (br.right - SP2, br.y + 8), right=True)
                self.edit_rects.append((br, unit, field))
            s.gap(SP2)

        # --- stat chips ----------------------------------------- #
        row = s.row(46)
        cg = SP1
        cw = (row.w - 3 * cg) // 4
        for i, (k, v, ac) in enumerate((("HP", unit.hp_max, OK), ("AC", unit.ac, INFO),
                                        ("MD", unit.mental_defense, DEMO_HL),
                                        ("SPD", unit.speed, INFO))):
            chip(screen, pygame.Rect(row.x + i * (cw + cg), row.y, cw, 46),
                 k, v, f, accent=ac)
        s.gap(SP3)

        # --- attributes (one compact row) --------------------- #
        s.y = section(screen, "ATTRIBUTES", s.x, s.y, s.w, f)
        arow = s.row(46)
        aw = arow.w // 6
        for i, (k, name) in enumerate((("STR", "strength"), ("DEX", "dexterity"),
                                       ("CON", "constitution"), ("INT", "intelligence"),
                                       ("WIS", "wisdom"), ("CHA", "charisma"))):
            val = getattr(unit, name)
            m = getattr(unit, f"mod_{name}")
            acx = arow.x + i * aw + aw // 2
            cell = pygame.Rect(arow.x + i * aw + 1, arow.y, aw - 2, 46)
            pygame.draw.rect(screen, SURFACE_1, cell, border_radius=4)
            text(screen, k, f.label, INK_FAINT, (acx, arow.y + 6), center=True)
            text(screen, f"{val}", f.num, INK, (acx, arow.y + 22), center=True)
            mc = OK if m > 0 else DANGER if m < 0 else INK_FAINT
            text(screen, f"{m:+}", f.body_sm, mc, (acx, arow.y + 38), center=True)
        s.gap(SP3)

        # --- weapon ------------------------------------------- #
        s.y = section(screen, "WEAPON", s.x, s.y, s.w, f)
        n, faces = unit.weapon["damage"]
        reach = f"range {unit.weapon['range']}" if unit.ranged else "melee"
        hands = "2 hands" if unit.weapon["hands"] == 2 else "1 hand"
        ammo = f"  ·  {preview.ammo} arrows" if preview.needs_ammo else ""
        wrow = s.row(34)
        text(screen, unit.weapon_name, f.body_bd, INK, (wrow.x, wrow.y))
        text(screen, f"{n}d{faces}  ·  {reach}  ·  {hands}{ammo}", f.body_sm, INK_DIM,
             (wrow.x, wrow.y + 17))
        if unit.has_tongue and unit.equipped_tongue:
            tn, tf = data.WEAPONS[unit.equipped_tongue]["damage"]
            trow = s.row(20)
            text(screen, f"tongue: {unit.equipped_tongue}  ·  {tn}d{tf}  ·  "
                 f"reach {unit.tongue_reach}", f.body_sm, INK_FAINT, (trow.x, trow.y))
        s.gap(SP2)

        # --- languages -------------------------------------- #
        s.y = section(screen, "LANGUAGES", s.x, s.y, s.w, f)
        text(screen, ", ".join(unit.languages), f.body_sm, INK, (s.x, s.y))
        if unit.ability.demoralize_ignores_language:
            note = "mimics voices: Demoralize needs no shared language"
        elif unit.ability.extra_languages:
            note = "2nd language: more targets to Demoralize"
        else:
            note = "Demoralize needs a shared language"
        text(screen, note, f.body_sm, INK_DIM, (s.x, s.y + 15))
        s.gap(32)

        # --- ability --------------------------------------- #
        eff = wrap_lines([unit.ability.effect], f.body_sm, s.w - SP3) \
            if not self.edit_mode else []
        s.y = section(screen, "ABILITY", s.x, s.y + SP1, s.w, f)
        hb = s.row(22 + len(eff) * 15 + SP2)
        panel(screen, hb, fill=SURFACE_1, border=INFO, width=1, radius=4)
        text(screen, unit.ability.name, f.body_bd, INFO, (hb.x + SP2, hb.y + 5))
        for j, ln in enumerate(eff):
            text(screen, ln, f.body_sm, INK_DIM, (hb.x + SP2, hb.y + 22 + j * 15))
        s.gap(SP3)

        # --- inventory one-liner --------------------------- #
        inv = ", ".join(unit._base_inventory) if unit._base_inventory else "(empty)"
        text(screen, f"carries {inv}  ·  {unit.gold} copper  ·  load {unit.load:g}/{unit.carry_normal:g}",
             f.body_sm, INK_FAINT, (s.x, s.y))

        # --- footer --------------------------------------- #
        if leader_pick:
            fr = pygame.Rect(rect.x + pad, rect.bottom - 36, rect.w - 2 * pad, 26)
            panel(screen, fr, fill=ACCENT if hover else SURFACE_3,
                  border=ACCENT if hover else LINE, width=1, radius=4)
            text(screen, "MAKE LEADER" if hover else "click to lead the guild",
                 f.label if hover else f.body_sm,
                 ACCENT_INK if hover else INK_DIM, fr.center, center=True)
        elif not self.edit_mode:
            fr = pygame.Rect(rect.x + pad, rect.bottom - 36, rect.w - 2 * pad, 26)
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
                n, faces = u.weapon["damage"]
                text(screen, f"HP {u.hp_max}  AC {u.ac}  Speed {u.speed}  {u.weapon_name} {n}d{faces}",
                     f.body_sm, INK_DIM, (dot[0] + 20, r.y + SP2 + 18))
            else:
                pygame.draw.rect(screen, LINE_SOFT, r, 1, border_radius=RADIUS)
                text(screen, f"slot {i + 1}", f.body_sm, INK_FAINT, r.center, center=True)

    def _draw_edit_button(self, screen, mouse):
        r = pygame.Rect(screen.get_width() - MARGIN - 96, MARGIN, 96, 30)
        self.edit_btn_rect = r
        on = self.edit_mode
        hov = r.collidepoint(mouse)
        panel(screen, r, fill=ACCENT if on else (SURFACE_3 if hov else SURFACE_2),
              border=ACCENT if (on or hov) else LINE, width=1, radius=4)
        text(screen, "EDITING" if on else "EDIT", self.fonts.label,
             ACCENT_INK if on else INK, r.center, center=True)

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
