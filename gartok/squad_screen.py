"""Pick which guild members go on an outing -- a squad for a fight, or a party
for the market.

Click member cards to toggle them in or out; 1 to `max_pick` may go. Confirm
hands the chosen list, the location and (for an arena bout) the chosen stake tier
back to `app`; back returns to the map. Members left behind are untouched.

Arena mode (`arena_offers` given): a strip of stake tiers sits above the roster.
Entry is staked per fighter (`entry` x squad size), so confirm also needs the
picked members' combined gold to cover that whole fee. Each bout caps the squad
at its own `player_cap` (matched to the opponent count), so `max_pick` tracks the
selected tier and an over-cap pick is trimmed when you switch tiers.

Migrated fully onto `gartok.ui`: data-driven drawing via `gartok.ui.primitives`,
`gartok.ui.combat_card`, and `gartok.ui.tokens`.
"""

import pygame

from . import arena
from .draft_screen import TEAM_SIZE as MAX_SQUAD
from .screen import Screen
from .sheet_panel import SheetModalMixin
from .ui.combat_card import draw_combat_card
from .ui.primitives import (
    contained,
    draw_button,
    draw_tooltip,
    footer_bar,
    format_tooltip,
    panel,
    scrollbar,
    set_pointer,
    text,
    tracked,
)
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


class SquadScreen(SheetModalMixin, Screen):
    native = True

    def __init__(self, fonts, roster, location, on_confirm, on_back, *,
                 max_pick=None, title="PICK SQUAD", confirm_label="CONFIRM",
                 arena_offers=None, disabled=None):
        super().__init__()
        self.fonts = fonts
        self._F = None
        self.roster = roster
        self.location = location
        self.on_confirm = on_confirm
        self.on_back = on_back
        self._max_pick = max_pick or MAX_SQUAD
        self.title = title
        self.confirm_label = confirm_label
        self.offers = arena_offers or []
        self.offer_idx = 0                     # cheapest tier selected by default
        self.disabled = set(disabled or ())   # units that cannot be picked (e.g. starving)
        self.picked = []                      # units, in click order
        self.cards = []                      # [(rect, unit)]
        self.info_hits = []                # [(rect, unit)] -- the card's 'i' disc opens the sheet
        self.tiers = []                      # [(rect, index)]
        self.buttons = []                   # [(key, rect)]
        self._hot = False
        self.tooltip = None
        self._scroll = 0
        self._max_scroll = 0

        eligible = [u for u in roster if u not in self.disabled]
        if len(eligible) <= self.max_pick:
            self.picked = eligible

    def _ui_fonts(self):
        if self._F is None:
            if hasattr(pygame, "font") and hasattr(pygame.font, "init") and not pygame.font.get_init():
                pygame.font.init()
            self._F = ui_fonts()
        return self._F

    def _reset_buttons(self):
        self.buttons = []
        self._hot = False

    def add_button(self, surf, rect, key, label, enabled=True, primary=False, danger=False):
        F = self._ui_fonts()
        hov = enabled and rect.collidepoint(self.mouse)
        draw_button(surf, F, rect, label, enabled=enabled, primary=primary, danger=danger, mpos=self.mouse)
        if enabled:
            self.buttons.append((key, rect))
            if hov:
                self._hot = True
        return hov

    # ------------------------------------------------------------------ #
    @property
    def offer(self):
        return self.offers[self.offer_idx] if self.offers else None

    @property
    def max_pick(self):
        """Fighters the current outing allows: the selected bout's cap, else the
        ctor's `max_pick` (a plain party picker passes the whole roster)."""
        off = self.offer
        return off.player_cap if off is not None else self._max_pick

    @property
    def picked_gold(self):
        return sum(u.gold for u in self.picked)

    @property
    def entry_cost(self):
        """Total arena stake for the current pick: `entry` per fighter."""
        off = self.offer
        return off.entry * len(self.picked) if off else 0

    @property
    def ok(self):
        if not (1 <= len(self.picked) <= self.max_pick):
            return False
        return self.offer is None or self.picked_gold >= self.entry_cost

    @property
    def no_xp_picked(self):
        """Picked units that will not earn combat XP in the selected arena bout."""
        if not self.offer:
            return []
        max_lvl = arena.bout_max_combat_level(self.offer)
        return [u for u in self.picked if u.combat_level > max_lvl]

    def unit_outlevels_bout(self, unit):
        """Whether a unit's combat level strictly exceeds the max enemy level in this bout."""
        if not self.offer:
            return False
        return unit.combat_level > arena.bout_max_combat_level(self.offer)

    # ------------------------------------------------------------------ #
    # soft tutorial (screen.py)                                          #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "squad"

    def tutorial_badge_rect(self, size):
        W, H = size
        pad = 16 if W < 1500 else 24
        return pygame.Rect(W - pad - 28, pad - 4, 28, 28)

    def tutorial_anchor(self, size):
        W, H = size
        pad = 16 if W < 1500 else 24
        return (W - pad - 340, pad + 32, 340, "down")

    # ------------------------------------------------------------------ #
    def handle_event(self, event):
        super().handle_event(event)
        if event.type == pygame.MOUSEWHEEL:
            self._scroll = max(0, min(self._max_scroll, self._scroll - event.y * 36))
            return
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_k):
                self._scroll = max(0, min(self._max_scroll, self._scroll - 36))
                return
            elif event.key in (pygame.K_DOWN, pygame.K_j):
                self._scroll = max(0, min(self._max_scroll, self._scroll + 36))
                return
            elif event.key == pygame.K_PAGEUP:
                self._scroll = max(0, min(self._max_scroll, self._scroll - 200))
                return
            elif event.key == pygame.K_PAGEDOWN:
                self._scroll = max(0, min(self._max_scroll, self._scroll + 200))
                return

    def handle_escape(self):
        if self.close_sheet_on_click():
            return True
        return False

    def _click(self, px):
        if self.close_sheet_on_click():
            return
        for rect, unit in self.info_hits:
            if rect.collidepoint(px):
                self.open_sheet(unit)
                return
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "back":
                    self.on_back()
                elif key == "confirm" and self.ok:
                    self.on_confirm(list(self.picked), self.location, self.offer)
                return
        for rect, i in self.tiers:
            if rect.collidepoint(px):
                self.offer_idx = i
                del self.picked[self.max_pick:]     # a tighter tier drops the overflow
                return
        for rect, unit in self.cards:
            if rect.collidepoint(px):
                self._toggle(unit)
                return

    def _toggle(self, unit):
        if unit in self.disabled:
            return
        if unit in self.picked:
            self.picked.remove(unit)
        elif len(self.picked) < self.max_pick:
            self.picked.append(unit)

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self._ui_fonts()
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self.cards = []
        self.info_hits = []
        self.tiers = []
        self.tooltip = None
        self._reset_buttons()

        pad = 16 if W < 1500 else 24
        text(screen, F["titleb"], self.title, (pad, pad - 2), T.TX)
        n = len(self.picked)
        sub_col = T.BRASS if self.ok else T.TX_MUTED
        text(screen, F["body"],
             f"{self.location.name}   ·   {n}/{self.max_pick} picked   ·   click to toggle (1 to {self.max_pick})",
             (pad, pad + 30), sub_col)

        top = pad + 68
        if self.offers:
            top = self._draw_offers(screen, F, top, pad)

        gap = 16
        n = len(self.roster)
        cols = max(1, min(n, (W - 2 * pad + gap) // (300 + gap)))
        rows = (n + cols - 1) // max(1, cols)
        card_w = min(360, (W - 2 * pad - (cols - 1) * gap) // cols)
        avail_h = H - top - 64
        card_h = min(232, max(210, (avail_h - (rows - 1) * gap) // max(1, rows)))
        total_grid_h = rows * card_h + (rows - 1) * gap
        self._max_scroll = max(0, total_grid_h - avail_h)
        self._scroll = min(self._scroll, self._max_scroll)

        x0 = (W - (cols * card_w + (cols - 1) * gap)) // 2
        grid_rect = pygame.Rect(pad, top, W - 2 * pad, avail_h)

        with contained(screen, grid_rect):
            for i, unit in enumerate(self.roster):
                cx = x0 + (i % cols) * (card_w + gap)
                cy = top + (i // cols) * (card_h + gap) - self._scroll
                rect = pygame.Rect(cx, cy, card_w, card_h)
                self._draw_card(screen, F, rect, unit)
                self.cards.append((rect, unit))

        if self._max_scroll > 0:
            scrollbar(screen, grid_rect, self._scroll, self._max_scroll, total_grid_h)

        self._draw_footer(screen, F, W, H, pad)
        self.draw_sheet_modal(screen, F)
        if self.tooltip and not self.sheet_open:
            draw_tooltip(screen, F, self.tooltip, self.mouse)

        set_pointer(self._hot)

    # ------------------------------------------------------------------ #
    def _draw_offers(self, screen, F, top, pad):
        tracked(screen, F["microb"], "STAKE", (pad, top), T.BRASS)
        top += 18
        gap = T.S
        W = screen.get_size()[0]
        w = (W - 2 * pad - (len(self.offers) - 1) * gap) // max(1, len(self.offers))
        for i, off in enumerate(self.offers):
            r = pygame.Rect(pad + i * (w + gap), top, w, 56)
            sel = i == self.offer_idx
            hov = r.collidepoint(self.mouse)
            if hov and not sel:
                self._hot = True

            panel(screen, r, hover=(sel or hov))
            if sel:
                pygame.draw.rect(screen, T.BRASS, r, 2)

            text(screen, F["bodyb"], off.name, (r.x + T.S, r.y + 6), T.BRASS if sel else T.TX)
            from .arena import bout_level_range
            lvl = bout_level_range(off, self.picked)
            text(screen, F["body_sm"],
                 f"entry {off.entry}/head  ·  purse {off.purse}  ·  {off.player_cap} opponent(s)  ·  {lvl}",
                 (r.x + T.S, r.y + 28), T.TX_MUTED)
            self.tiers.append((r, i))
        top += 66

        off = self.offer
        cost = self.entry_cost
        gold = self.picked_gold
        can_pay = gold >= cost
        cost_col = T.GREEN if can_pay else T.BLOOD
        text(screen, F["body_sm"],
             f"entry: {off.entry} x {len(self.picked)} fighter(s) = {cost} copper  ·  squad's combined purse: {gold} copper",
             (pad, top), cost_col)
        top += 20

        no_xp = self.no_xp_picked
        if no_xp:
            names = ", ".join(u.name for u in no_xp)
            max_lvl = arena.bout_max_combat_level(off)
            text(screen, F["body_sm"],
                 f"No combat XP: {names} (level higher than enemies, max Lv {max_lvl})",
                 (pad, top), T.BRASS)
            top += 20
        return top + 4

    def _draw_card(self, screen, F, rect, unit):
        chosen = unit in self.picked
        off = unit in self.disabled

        if unit.weapon:
            n, faces = unit.weapon["damage"]
        else:
            n, faces = unit.unarmed_damage
        arma = unit.weapon_name or "unarmed"

        ch = {
            "name": unit.name,
            "race": unit.race["name"],
            "occ": unit.occupation["name"],
            "hp": unit.hp_max,
            "hp_max": unit.hp_max,
            "ac": unit.ac,
            "md": unit.mental_defense,
            "spd": unit.speed,
            "weapon": arma,
            "dmg": f"{n}d{faces}"
        }

        lvl = f"C{unit.combat_level}"
        if unit.work_xp or unit.work_level:
            lvl += f"/W{unit.work_level}"
        lvl += f"/R{unit.racial_level}"
        if unit.pending_picks:
            lvl += " *"

        extra = [
            (None, f"{unit.gold} copper  ·  lvl {lvl}", T.BRASS)
        ]
        if unit.pending_picks:
            extra.append((None, "TALENT PICK READY", T.BRASS))
        if unit.hunger_level:
            extra.append((None, f"HUNGER: {unit.hunger_label}", T.BLOOD if unit.hunger_level >= 2 else T.BRASS))

        no_xp = self.unit_outlevels_bout(unit)
        if no_xp:
            max_lvl = arena.bout_max_combat_level(self.offer)
            extra.append((None, f"NO COMBAT XP (enemy max Lv {max_lvl})", T.BRASS))

        mark = ("UNFIT (hunger)" if off
                else ("PICKED (NO XP)" if (chosen and no_xp) else "PICKED") if chosen
                else "CLICK TO ADD")

        state_msg = (mark, T.BLOOD if off else T.BRASS if (chosen and no_xp) else T.BRASS) if (off or chosen) else None
        action_msg = None if (off or chosen) else mark

        hov = rect.collidepoint(self.mouse)
        if hov and not off:
            self._hot = True

        tooltips, _ = draw_combat_card(screen, rect, ch, action=action_msg, hovered=hov, selected=chosen, disabled=off, state_msg=state_msg, extra_lines=extra)

        if not self.sheet_open:
            for t_rect, t_text in tooltips:
                if t_rect.collidepoint(self.mouse):
                    self.tooltip = format_tooltip("Vitals", t_text, F)
                    break

        badge = self.sheet_badge(screen, (rect.right - T.S * 3, rect.y + T.S * 3), F)
        if badge.collidepoint(self.mouse):
            self._hot = True
        self.info_hits.append((badge, unit))

    def _draw_footer(self, screen, F, W, H, pad):
        footer_bar(self, screen, F,
                   back=("back", "BACK"),
                   primary=("confirm", self.confirm_label, self.ok),
                   margin=pad,
                   hint=None)
