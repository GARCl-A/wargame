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
from .theme import BANNER_COLORS, set_player_color
from .ui.primitives import (
    caps,
    contained,
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
    TOKEN_INK,
)
from .ui.sheet_card import draw_sheet, draw_row, sheet_height, unit_to_ch
from .ui.tokens import T
from .unit import Unit

TEAM_SIZE = 3
DRAFT_ROUNDS = 3
DRAFT_CHOICES = 3
_MAX_GUILD_NAME = 24


def _archetypes(u):
    """Two or three quick read tags to help the pick."""
    tags = []
    
    # Calculate expected damage for DAMAGE DEALER tag
    wep_name = u.equipped_weapon
    if not wep_name:
        count, sides = u.unarmed_damage
        expected_dmg = count * ((sides + 1) / 2) + u.mod_strength
    else:
        wep = data.WEAPONS.get(wep_name)
        if not wep:
            count, sides = u.unarmed_damage
            expected_dmg = count * ((sides + 1) / 2) + u.mod_strength
        else:
            count, sides = wep.get("damage", (1, 2))
            stat_mod = u.mod_dexterity if wep.get("finesse") else u.mod_strength
            expected_dmg = count * ((sides + 1) / 2) + stat_mod

    if u.size == "Large":
        tags.append(("LARGE", T.TX_MUTED, "Takes up more space on the grid; has higher base health."))
    if u.hp_max >= 8:
        tags.append(("TOUGH", T.GREEN, "High survivability from a massive health pool."))
    if u.carry_normal >= 35:
        tags.append(("PACK MULE", T.GREEN, "Can carry the heaviest armor and equipment without slowing down."))
    if u.ranged:
        tags.append(("RANGED", T.TX_MUTED, "Carries a ranged weapon to attack from distance."))
    if u.speed >= 7:
        tags.append(("FAST", T.GREEN, "Swift and agile, with high movement and evasion."))
    if expected_dmg >= 6:
        tags.append(("DAMAGE DEALER", T.BRASS, "Heavy hitter with very high expected damage output."))
    if u.mod_dexterity >= 2:
        tags.append(("NIMBLE", T.GREEN, "Highly dexterous. Superior accuracy with finesse weapons and high innate defense."))
    if u.mod_intelligence >= 2:
        tags.append(("GENIUS", T.GREEN, "Brilliant mind. Learns and crafts at high speeds, repairs automatons, and excels at magic."))
    if u.mod_wisdom >= 2:
        tags.append(("WISE", T.GREEN, "Level-headed. High combat initiative, strong mental defense, and a natural field medic."))
    if u.mod_charisma >= 2:
        tags.append(("LEADER", T.BRASS, "Highly charismatic. Excellent at recruiting, haggling, and leading."))
    if getattr(u, 'magic_source', None) or getattr(u, 'spells_known', []):
        tags.append(("MAGIC", T.TX_MUTED, "Initiated in magic. Can cast spells and read magical scrolls."))
    if u.ability.darkvision:
        tags.append(("SEES IN DARK", T.TX_MUTED, "Can see in darkness without needing a light source."))
        
    return tags[:3]


class DraftScreen(Screen):
    native = True

    def __init__(self, fonts, on_done):
        super().__init__()
        self.F = fonts
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
        if self.edit_mode:
            sub, col = ("EDIT MODE  ·  click 'swap' to change race / occupation  ·  "
                        "EDITING goes back to picking", T.BRASS)
        else:
            sub, col = (f"Round {round_no} of {DRAFT_ROUNDS}  ·  pick 1 of {DRAFT_CHOICES}  "
                        f"·  squad {len(self.picks)}/{TEAM_SIZE}", T.TX_MUTED)
        text(screen, F["body"], sub, (T.S * 4, T.S * 4 + 30), col)
        self._draw_top_buttons(screen, mouse)

        rail_h = 92
        
        # calculate actual_h for the cards so they perfectly stack with the rail
        header_h = 16 + T.S * 2
        if self.edit_mode:
            header_h += 2 * (28 + T.S) + T.S
        sh = sheet_height("normal")
        footer_h = (T.S * 3 + 26 + T.S * 3) if not self.edit_mode else T.S * 3
        card_h = T.S * 3 + header_h + sh + footer_h
        
        group_h = card_h + T.S * 4 + rail_h
        slack = max(0, (screen.get_height() - 18) - (T.S * 4 + 58) - group_h)
        top = T.S * 4 + 58 + slack // 2
        rail_y = top + card_h + T.S * 4
        gap = T.S * 3
        card_w = (screen.get_width() - 2 * (T.S * 4) - (DRAFT_CHOICES - 1) * gap) // DRAFT_CHOICES

        self.card_rects = []
        self.edit_rects = []
        for i, unit in enumerate(self.candidates):
            rect = pygame.Rect(T.S * 4 + i * (card_w + gap), top, card_w, card_h)
            self.card_rects.append((rect, unit))
            hover = rect.collidepoint(mouse) and not self.edit_mode
            self._draw_card(screen, rect, unit, hover, mouse)

        self._draw_squad_rail(screen, T.S * 4, rail_y, screen.get_width() - 2 * (T.S * 4), rail_h)
        text(screen, F["body_sm"], "[Esc] quit", (T.S * 4, screen.get_height() - 18), T.TX_FAINT)

        if self.picker is not None:
            self._draw_picker(screen, mouse)

        if getattr(self, "tooltip", None):
            draw_tooltip(screen, F, self.tooltip, mouse)

    # ------------------------------------------------------------------ #
    def _draw_identity(self, screen):
        """Name + banner (colour, then emblem), then FOUND THE GUILD. A form,
        not a card gallery -- its own layout, no `card_rects`/`_draw_card`."""
        F = self.F
        W, H = screen.get_size()
        mouse = self.mouse

        cw = min(560, W - 2 * (T.S * 4))
        cx = (W - cw) // 2

        text(screen, F["titleb"], "FOUND THE GUILD", (cx, T.S * 4 - 2), T.TX)
        text(screen, F["body"], "Name your guild, pick a banner, and choose your leader.",
             (cx, T.S * 4 + 30), T.TX_MUTED)

        y = T.S * 4 + 74

        # --- preview + name field ----------------------------------- #
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

        # --- banner colour: a curated palette, not a free picker --------- #
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

        # --- banner emblem: a curated gallery, not a paint tool ---------- #
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

        # --- guild leader ------------------------------------------ #
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
                ar = pygame.Rect(attr_x, r.centery - F["body_sm"].get_height()//2, tw, F["body_sm"].get_height())
                text(surf, F["body_sm"], txt, (attr_x, r.centery - F["body_sm"].get_height()//2), T.TX_MUTED)
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

        # --- confirm --------------------------------- #
        self.continue_rect = pygame.Rect(cx + cw - 200, y, 200, 44)
        can_cont = self.leader_pick is not None
        draw_button(screen, F, self.continue_rect, "FOUND THE GUILD", primary=True, enabled=can_cont, mpos=mouse)

        text(screen, F["body_sm"], "[Esc] quit", (T.S * 4, H - 18), T.TX_FAINT)

    # ------------------------------------------------------------------ #
    def _draw_card(self, screen, rect, unit, hover, mouse, leader_pick=False):
        F = self.F
        pad = T.S * 3
        
        # Calculate dynamic height
        header_h = 16 + T.S * 2
        if self.edit_mode:
            header_h += 2 * (28 + T.S) + T.S
            
        sh = sheet_height("normal")
        footer_h = (T.S * 3 + 26 + T.S * 3) if not self.edit_mode else T.S * 3
        
        actual_h = pad + header_h + sh + footer_h
        bg_rect = pygame.Rect(rect.x, rect.y, rect.w, max(rect.h, actual_h))
        
        # The background panel uses war-table palette to match sheet_card
        panel(screen, bg_rect, hover=hover, width=2 if hover else 1)
        
        # --- floating archetypes ---
        ty = bg_rect.y + pad
        tx = bg_rect.x + pad
        for label, tcol, desc in _archetypes(unit):
            w = F["microb"].size(label)[0] + 12
            pill = pygame.Rect(tx, ty, w, 16)
            pygame.draw.rect(screen, T.STEEL_HI, pill, border_radius=4)
            pygame.draw.rect(screen, tcol, pill, 1, border_radius=4)
            text(screen, F["microb"], label, pill.center, tcol, center=True)
            if pill.collidepoint(mouse):
                self.tooltip = desc
            tx += w + T.S
            
        ty += 16 + T.S * 2

        # --- floating edit mode buttons ---
        if self.edit_mode:
            for field, lbl, val in (("race", "RACE", unit.race["name"]),
                                    ("occupation", "OCCUP", unit.occupation["name"])):
                br = pygame.Rect(bg_rect.x + pad, ty, bg_rect.w - 2 * pad, 28)
                ty += 28 + T.S
                hov = br.collidepoint(mouse)
                panel(screen, br, hover=hov)
                text(screen, F["body_sm"], f"{lbl}  {val}", (br.x + T.S * 2, br.y + 7), T.TX)
                text(screen, F["microb"], "SWAP", (br.right - T.S * 2, br.y + 8), T.BRASS if hov else T.TX_MUTED, right=True)
                self.edit_rects.append((br, unit, field))
            ty += T.S

        # --- the shared sheet component ---
        sheet_rect = pygame.Rect(bg_rect.x + pad, ty, bg_rect.w - 2 * pad, sh)
        ch = unit_to_ch(Combatant(unit))
        used_h, tip = draw_sheet(screen, F, sheet_rect, ch, density="normal", mouse=mouse)
        if tip:
            self.tooltip = tip
            
        ty += used_h + T.S * 3

        # --- footer --------------------------------------- #
        if not self.edit_mode:
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
                pygame.draw.rect(screen, T.GREEN, r, 1) # border ok
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

    def _draw_top_buttons(self, screen, mouse):
        # Place buttons to the left of the global tutorial button (26px + T.S*2 gap)
        F = self.F
        r_edit = pygame.Rect(screen.get_width() - (T.S * 4) - 26 - T.S * 2 - 96, T.S * 4, 96, 30)
        self.edit_btn_rect = r_edit
        draw_button(screen, F, r_edit, "EDITING" if self.edit_mode else "EDIT",
                    primary=self.edit_mode, mpos=mouse)

        r_reroll = pygame.Rect(r_edit.left - T.S * 2 - 96, T.S * 4, 96, 30)
        self.reroll_btn_rect = r_reroll
        draw_button(screen, F, r_reroll, "REROLL", mpos=mouse)

    # ------------------------------------------------------------------ #
    def _draw_picker(self, screen, mouse):
        F = self.F
        unit, field = self.picker
        if field == "race":
            options, current, title = data.RACE_NAMES, unit.race["name"], "Pick a race"
        else:
            options, current, title = (data.OCCUPATION_NAMES, unit.occupation["name"],
                                       "Pick an occupation")

        cols = 3
        rows = (len(options) + cols - 1) // cols
        cw, ch, pad = 220, 27, T.S * 4
        pw = cols * cw + 2 * pad
        ph = 52 + rows * ch + T.S * 4
        
        panel_r = modal_card(screen, (pw, ph), veil=True)
        text(screen, F["titleb"], title, (panel_r.x + pad, panel_r.y + 12), T.TX)

        self.picker_rects = []
        for i, name in enumerate(options):
            c, rw = i % cols, i // cols
            it = pygame.Rect(panel_r.x + pad + c * cw, panel_r.y + 46 + rw * ch,
                             cw - T.S, ch - T.S)
            sel = name == current
            hov = it.collidepoint(mouse)
            panel(screen, it, hover=(hov or sel))
            text(screen, F["body_sm"], name, (it.x + T.S * 2, it.y + 4), T.BRASS if sel else T.TX)
            self.picker_rects.append((it, name))
            
        text(screen, F["body_sm"], "click outside to cancel", (panel_r.x + pad, panel_r.bottom - 20), T.TX_FAINT)
