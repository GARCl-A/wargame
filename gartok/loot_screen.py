"""Loot screen: split the spoils after a won fight.

The pile on the left is everything left on the field (see `loot.field_loot`):
the defeated enemies' gear, your own dead's gear, loose weapons and torches.
Click an item, then click a survivor to drop it in their pack -- if it fits
under their `carry_max` (a hard ceiling). "Take what fits" fills packs
greedily. Whatever is still in the pile when you finish is left behind.

Re-equipping (draw which weapon, light a torch) happens later on the guild screen.
"""

import pygame

from . import data
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SURFACE_1,
                    SURFACE_2, SURFACE_3, WIN_H, WIN_W, panel, section,
                    token_badge, text)


def _kg(w):
    return f"{w:g} kg"


class LootScreen(Screen):
    def __init__(self, fonts, guild, survivors, pool, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.survivors = survivors
        self.pool = list(pool)
        self.on_done = on_done
        self.sel = None                       # index into self.pool, or None
        self.notice = None
        self.rows = []                        # [(rect, pool_index)]
        self.cards = []                      # [(rect, member)]
        self.buttons = []                   # [(key, rect)]

    # ------------------------------------------------------------------ #
    @staticmethod
    def _fits(member, name):
        return member.load + data.item_weight(name) <= member.carry_max

    def _give(self, member, name):
        member.give_to_pack(name)

    def _click(self, px):
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "done":
                    self.on_done()
                elif key == "auto":
                    self._auto_pick()
                return
        for rect, i in self.rows:
            if rect.collidepoint(px):
                self.sel = None if self.sel == i else i
                return
        if self.sel is not None:
            for rect, member in self.cards:
                if rect.collidepoint(px):
                    name = self.pool[self.sel]
                    if self._fits(member, name):
                        self._give(member, name)
                        self.pool.pop(self.sel)
                        self.sel = None
                        self.notice = None
                    else:
                        self.notice = f"{member.name} can't carry {name} (max load)."
                    return

    def _auto_pick(self):
        for name in list(self.pool):
            takers = sorted(self.survivors,
                            key=lambda m: m.carry_max - m.load, reverse=True)
            for m in takers:
                if self._fits(m, name):
                    self._give(m, name)
                    self.pool.remove(name)
                    break
        self.sel = None
        self.notice = "Grab the rest by hand or leave it behind."

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        screen.fill((18, 19, 24))
        self.rows = []
        self.cards = []
        self.buttons = []

        text(screen, "LOOT", f.title, INK, (MARGIN, MARGIN - 2))
        left = f"{len(self.pool)} items on the field" if self.pool else "field cleared"
        text(screen, f"{left}  ·  ceiling = each one's max load  ·  whatever's left stays behind",
             f.body, INK_DIM, (MARGIN, MARGIN + 30))

        top = MARGIN + 72
        pile_w = 300
        pile = pygame.Rect(MARGIN, top, pile_w, WIN_H - top - 72)
        self._draw_pile(screen, pile)
        self._draw_survivors(screen, pygame.Rect(pile.right + MARGIN, top,
                                                 WIN_W - pile.right - 2 * MARGIN,
                                                 pile.h))
        self._draw_footer(screen)

    def _draw_pile(self, screen, rect):
        f = self.fonts
        panel(screen, rect, fill=SURFACE_2, border=LINE_SOFT, radius=RADIUS)
        x, w = rect.x + SP3, rect.w - 2 * SP3
        y = section(screen, "ON THE GROUND", x, rect.y + SP3, w, f)
        if not self.pool:
            text(screen, "(nothing)", f.body_sm, INK_FAINT, (x, y + 2))
            return
        for i, name in enumerate(self.pool):
            r = pygame.Rect(x, y, w, 26)
            sel = self.sel == i
            hov = r.collidepoint(self.mouse)
            panel(screen, r, fill=ACCENT if sel else SURFACE_3 if hov else SURFACE_1,
                  border=ACCENT if sel else LINE_SOFT, width=1, radius=4)
            ink = ACCENT_INK if sel else INK
            text(screen, name, f.body_sm, ink, (r.x + SP2, r.y + 6))
            text(screen, _kg(data.item_weight(name)), f.mono_sm,
                 ACCENT_INK if sel else INK_DIM, (r.right - SP2, r.y + 7), right=True)
            self.rows.append((r, i))
            y += 26 + SP1

    def _draw_survivors(self, screen, area):
        n = max(1, len(self.survivors))
        gap = SP3
        card_w = (area.w - (n - 1) * gap) // n
        for i, m in enumerate(self.survivors):
            rect = pygame.Rect(area.x + i * (card_w + gap), area.y, card_w, area.h)
            self._draw_card(screen, rect, m)
            self.cards.append((rect, m))

    def _draw_card(self, screen, rect, m):
        f = self.fonts
        pad = SP3
        sel = self.sel is not None
        name = self.pool[self.sel] if sel else None
        drop_ok = sel and self._fits(m, name)
        hov = rect.collidepoint(self.mouse)
        panel(screen, rect, fill=SURFACE_2,
              border=OK if (drop_ok and hov) else DANGER if (sel and hov) else LINE_SOFT,
              width=2 if hov else 1, radius=RADIUS)

        tok = (rect.x + pad + 12, rect.y + pad + 12)
        token_badge(screen, tok, m, f)
        text(screen, m.name, f.card_name, INK, (tok[0] + 24, rect.y + pad))
        text(screen, f"{m.race['name']}  ·  {m.occupation['name']}", f.body_sm,
             INK_DIM, (tok[0] + 24, rect.y + pad + 20))

        y = rect.y + pad + 46
        over = m.load > m.carry_max
        ccol = DANGER if over else OK
        text(screen, f"Load {_kg(m.load)} / {_kg(m.carry_max)}", f.mono_sm, ccol,
             (rect.x + pad, y))
        y += 14
        room = max(0.0, m.carry_max - m.load)
        text(screen, f"room {_kg(round(room, 1))}", f.body_sm, INK_FAINT, (rect.x + pad, y))
        y += 20

        y = section(screen, "PACK", rect.x + pad, y, rect.w - 2 * pad, f)
        if not m._base_inventory:
            text(screen, "(empty)", f.body_sm, INK_FAINT, (rect.x + pad, y + 2))
        for it in m._base_inventory:
            text(screen, it, f.body_sm, INK_DIM, (rect.x + pad, y))
            text(screen, _kg(data.item_weight(it)), f.mono_sm, INK_FAINT,
                 (rect.right - pad, y), right=True)
            y += 16

        if sel and hov:
            msg = "click: take" if drop_ok else "won't fit"
            text(screen, msg, f.label, OK if drop_ok else DANGER,
                 (rect.centerx, rect.bottom - 16), center=True)

    def _draw_footer(self, screen):
        f = self.fonts
        y = WIN_H - 52
        if self.notice:
            text(screen, self.notice, f.body_sm, INFO, (MARGIN, y - 22))

        auto = pygame.Rect(MARGIN, y, 220, 36)
        hova = auto.collidepoint(self.mouse)
        on = bool(self.pool)
        panel(screen, auto, fill=SURFACE_3 if (on and hova) else SURFACE_2 if on else SURFACE_1,
              border=LINE_SOFT, width=1, radius=RADIUS)
        text(screen, "take what fits", f.body, INK if on else INK_FAINT,
             auto.center, center=True)
        if on:
            self.buttons.append(("auto", auto))

        done = pygame.Rect(WIN_W - MARGIN - 240, y, 240, 36)
        hovd = done.collidepoint(self.mouse)
        panel(screen, done, fill=ACCENT if hovd else SURFACE_3, border=ACCENT,
              width=1, radius=RADIUS)
        lbl = "DONE" if not self.pool else "LEAVE THE REST AND GO"
        text(screen, lbl, f.body_bd, ACCENT_INK if hovd else ACCENT, done.center, center=True)
        self.buttons.append(("done", done))
