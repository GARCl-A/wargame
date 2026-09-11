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

from .draft_screen import TEAM_SIZE as MAX_SQUAD
from .screen import Screen
from .sheet_panel import SheetModalMixin
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP2, SP3, SURFACE_1,
                    SURFACE_2, SURFACE_3, WARN, panel, token_badge, text,
                    tracked)


class SquadScreen(SheetModalMixin, Screen):
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
        self.buttons = []

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
            text(screen, f"entry {off.entry}/head  ·  purse {off.purse}  ·  "
                 f"{off.player_cap} opponent(s)", f.body_sm, INK_DIM,
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
        return top + 22

    def _draw_card(self, screen, rect, unit):
        f = self.fonts
        pad = SP3
        chosen = unit in self.picked
        off = unit in self.disabled
        hov = rect.collidepoint(self.mouse)
        panel(screen, rect, fill=SURFACE_1 if off else SURFACE_2,
              border=DANGER if off else ACCENT if chosen else (INFO if hov else LINE_SOFT),
              width=2 if (chosen or hov or off) else 1, radius=RADIUS)

        badge = self.sheet_badge(screen, (rect.right - pad, rect.y + pad), f)
        self.info_hits.append((badge, unit))

        tok = (rect.x + pad + 12, rect.y + pad + 12)
        token_badge(screen, tok, unit, f)
        text(screen, unit.name, f.card_name, INK, (tok[0] + 24, rect.y + pad))
        text(screen, f"{unit.race['name']}  ·  {unit.occupation['name']}", f.body_sm,
             INK_DIM, (tok[0] + 24, rect.y + pad + 20))

        y = rect.y + pad + 44
        text(screen, f"HP {unit.hp_max}   AC {unit.ac}   MD {unit.mental_defense}   "
             f"Speed {unit.speed}", f.mono_sm, INK_DIM, (rect.x + pad, y))
        y += 18
        n, faces = unit.weapon["damage"]
        arma = unit.weapon_name or "unarmed"
        text(screen, f"{arma}  {n}d{faces}", f.body_sm, INK_DIM, (rect.x + pad, y))
        y += 17
        lvl = f"C{unit.combat_level}"
        if unit.work_xp or unit.work_level:
            lvl += f"/W{unit.work_level}"
        if unit.pending_picks:
            lvl += " *"
        text(screen, f"{unit.gold} copper  ·  lvl {lvl}", f.mono_sm, ACCENT,
             (rect.x + pad, y))
        if unit.hunger_level:
            y += 16
            text(screen, f"HUNGER: {unit.hunger_label}", f.label,
                 DANGER if unit.hunger_level >= 2 else WARN, (rect.x + pad, y))

        mark = ("UNFIT (hunger)" if off else "PICKED" if chosen
                else "click to add")
        text(screen, mark, f.label,
             DANGER if off else ACCENT if chosen else INK_FAINT,
             (rect.x + pad, rect.bottom - 22))

    def _draw_footer(self, screen):
        f = self.fonts
        W, H = screen.get_size()
        ok = self.ok
        y = H - 56
        conf = pygame.Rect(W - MARGIN - 240, y, 240, 36)
        hov = conf.collidepoint(self.mouse)
        panel(screen, conf, fill=ACCENT if (ok and hov) else SURFACE_3 if ok else SURFACE_1,
              border=ACCENT if ok else LINE_SOFT, width=1, radius=RADIUS)
        text(screen, self.confirm_label, f.body_bd,
             ACCENT_INK if (ok and hov) else ACCENT if ok else INK_FAINT,
             conf.center, center=True)
        self.buttons.append(("confirm", conf))

        back = pygame.Rect(MARGIN, y, 140, 36)
        hovb = back.collidepoint(self.mouse)
        panel(screen, back, fill=SURFACE_3 if hovb else SURFACE_2, border=LINE_SOFT,
              width=1, radius=RADIUS)
        text(screen, "back", f.body, INK if hovb else INK_DIM, back.center, center=True)
        self.buttons.append(("back", back))
