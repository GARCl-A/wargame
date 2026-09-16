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
"""

import pygame

from . import arena
from .draft_screen import TEAM_SIZE as MAX_SQUAD
from .screen import Screen
from .sheet_panel import SheetModalMixin
from .theme import (ACCENT, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP2, SP3, SURFACE_1,
                    SURFACE_3, WARN, draw_tooltip, format_tooltip, panel, text, tracked)
from .widgets import ButtonsMixin, footer_bar, unit_card


class SquadScreen(ButtonsMixin, SheetModalMixin, Screen):
    native = True

    def __init__(self, fonts, roster, location, on_confirm, on_back, *,
                 max_pick=None, title="PICK SQUAD", confirm_label="CONFIRM",
                 arena_offers=None, disabled=None):
        super().__init__()
        self.fonts = fonts
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
        eligible = [u for u in roster if u not in self.disabled]
        if len(eligible) <= self.max_pick:
            self.picked = eligible

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

    # ------------------------------------------------------------------ #
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
        f = self.fonts
        W, H = screen.get_size()
        screen.fill((18, 19, 24))
        self.cards = []
        self.info_hits = []
        self.tiers = []
        self.tooltip = None
        self._reset_buttons()

        text(screen, self.title, f.title, INK, (MARGIN, MARGIN - 2))
        n = len(self.picked)
        text(screen, f"{self.location.name}  ·  {n}/{self.max_pick} picked  ·  "
             f"click to toggle (1 to {self.max_pick})", f.body,
             ACCENT if self.ok else INK_DIM, (MARGIN, MARGIN + 30))

        top = MARGIN + 68
        if self.offers:
            top = self._draw_offers(screen, top)

        gap = SP3
        n = len(self.roster)
        cols = max(1, min(n, (W - 2 * MARGIN + gap) // (300 + gap)))
        rows = (n + cols - 1) // cols
        avail_h = H - top - 72
        card_w = min(360, (W - 2 * MARGIN - (cols - 1) * gap) // cols)
        card_h = min(232, (avail_h - (rows - 1) * gap) // max(1, rows))
        x0 = (W - (cols * card_w + (cols - 1) * gap)) // 2
        for i, unit in enumerate(self.roster):
            cx = x0 + (i % cols) * (card_w + gap)
            cy = top + (i // cols) * (card_h + gap)
            rect = pygame.Rect(cx, cy, card_w, card_h)
            self._draw_card(screen, rect, unit)
            self.cards.append((rect, unit))

        self._draw_footer(screen)
        self.draw_sheet_modal(screen, f)
        if self.tooltip and not self.sheet_open:
            draw_tooltip(screen, f.body_sm, self.tooltip, self.mouse)

    # ------------------------------------------------------------------ #
    def _draw_offers(self, screen, top):
        f = self.fonts
        tracked(screen, "STAKE", f.label, INFO, (MARGIN, top))
        top += 16
        gap = SP2
        W = screen.get_size()[0]
        w = (W - 2 * MARGIN - (len(self.offers) - 1) * gap) // max(1, len(self.offers))
        for i, off in enumerate(self.offers):
            r = pygame.Rect(MARGIN + i * (w + gap), top, w, 54)
            sel = i == self.offer_idx
            hov = r.collidepoint(self.mouse)
            panel(screen, r, fill=SURFACE_3 if (sel or hov) else SURFACE_1,
                  border=ACCENT if sel else LINE_SOFT, width=2 if sel else 1, radius=RADIUS)
            text(screen, off.name, f.body_bd, ACCENT if sel else INK,
                 (r.x + SP2, r.y + 6))
            from .arena import bout_level_range
            lvl = bout_level_range(off, self.picked)
            text(screen, f"entry {off.entry}/head  ·  purse {off.purse}  ·  "
                 f"{off.player_cap} opponent(s)  ·  {lvl}", f.body_sm, INK_DIM,
                 (r.x + SP2, r.y + 26))
            self.tiers.append((r, i))
        top += 62

        off = self.offer
        cost = self.entry_cost
        gold = self.picked_gold
        can_pay = gold >= cost
        text(screen, f"entry: {off.entry} x {len(self.picked)} fighter(s) = "
             f"{cost} copper  ·  squad's combined purse: {gold} copper", f.body_sm,
             OK if can_pay else DANGER, (MARGIN, top))
        top += 18

        no_xp = self.no_xp_picked
        if no_xp:
            names = ", ".join(u.name for u in no_xp)
            max_lvl = arena.bout_max_combat_level(off)
            text(screen, f"No combat XP: {names} (level higher than enemies, max Lv {max_lvl})",
                 f.body_sm, WARN, (MARGIN, top))
            top += 18
        return top + 4

    def _draw_card(self, screen, rect, unit):
        f = self.fonts
        pad = SP3
        chosen = unit in self.picked
        off = unit in self.disabled

        n, faces = unit.weapon["damage"]
        arma = unit.weapon_name or "unarmed"
        lvl = f"C{unit.combat_level}"
        if unit.work_xp or unit.work_level:
            lvl += f"/W{unit.work_level}"
        lvl += f"/R{unit.racial_level}"
        if unit.pending_picks:
            lvl += " *"

        lines = [
            (f"HP {unit.hp_max}   AC {unit.ac}   MD {unit.mental_defense}   "
             f"Speed {unit.speed}", INK_DIM),
            (f"{arma}  {n}d{faces}", INK_DIM),
            (f"{unit.gold} copper  ·  lvl {lvl}", ACCENT),
        ]
        if unit.pending_picks:
            lines.append(("TALENT PICK READY", ACCENT))
        if unit.hunger_level:
            lines.append((f"HUNGER: {unit.hunger_label}",
                          DANGER if unit.hunger_level >= 2 else WARN))
        no_xp = self.unit_outlevels_bout(unit)
        if no_xp:
            max_lvl = arena.bout_max_combat_level(self.offer)
            lines.append((f"NO COMBAT XP (enemy max Lv {max_lvl})", WARN))

        unit_card(screen, rect, unit, f, self.mouse, selected=chosen, disabled=off,
                 lines=lines, subtitle=f"{unit.race['name']}  ·  {unit.occupation['name']}")

        chip_lbl = f"RACIAL LVL {unit.racial_level}"
        cw = f.label.size(chip_lbl)[0] + 10
        chip_r = pygame.Rect(rect.x + pad + 36, rect.y + pad + 20, cw, 18)
        if not self.sheet_open and chip_r.collidepoint(self.mouse):
            dice_cnt = 1 + len(unit._level_hp_rolls)
            die_word = "hit die" if dice_cnt == 1 else "hit dice"
            self.tooltip = format_tooltip(
                f"Racial Level {unit.racial_level}",
                f"{unit.race['name']} track · {dice_cnt} {die_word} ({unit.hp_max} HP) · unlocks racial talents. Feeds on Combat & Work levels ({unit.racial_xp} total).",
                f
            )

        badge = self.sheet_badge(screen, (rect.right - pad, rect.y + pad), f)
        self.info_hits.append((badge, unit))

        mark = ("UNFIT (hunger)" if off
                else ("PICKED (NO XP)" if (chosen and no_xp) else "PICKED") if chosen
                else "click to add")
        text(screen, mark, f.label,
             DANGER if off else WARN if (chosen and no_xp) else ACCENT if chosen else INK_FAINT,
             (rect.x + pad, rect.bottom - 22))

    def _draw_footer(self, screen):
        footer_bar(self, screen, back=("back", "BACK"),
                  primary=("confirm", self.confirm_label, self.ok))
