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
from .theme import (ACCENT, ACCENT_INK, DANGER, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SURFACE_1,
                    SURFACE_2, SURFACE_3, WARN, kg, panel, section, token_badge, text)
from .widgets import ButtonsMixin, footer_bar


class LootScreen(ButtonsMixin, Screen):
    native = True

    def __init__(self, fonts, guild, survivors, pool, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.survivors = survivors
        self.pool = list(pool)
        self.on_done = on_done
        self.sel = None                       # index into self.pool, or None
        self.pack_sel = None                  # (member, idx) of selected pack item, or None
        self.notice = None
        self.rows = []                        # [(rect, pool_index)]
        self.pack_rows = []                   # [(rect, member, idx)]
        self.cards = []                      # [(rect, member)]
        self.buttons = []                   # [(key, rect)]
        self._hot = False
        self.pile_rect = None
        self._pack_scroll = {}
        self._pack_areas = []
        self._pile_scroll = 0
        self._pile_area = None

    @staticmethod
    def _ground_stacks(pool):
        """`[(name, [indices])]` for the ground pile -- `loot.field_loot`
        hands back a flat, unstacked `list[str]` (it isn't a Unit pack), so
        this groups it the same way `dragselect._stacks` used to before
        `Unit._base_inventory` started keeping real quantities."""
        groups, order = {}, []
        for i, name in enumerate(pool):
            if name not in groups:
                groups[name] = []
                order.append(name)
            groups[name].append(i)
        return [(name, groups[name]) for name in order]

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            if self._pile_area and self._pile_area.collidepoint(self.mouse):
                n = len(self._ground_stacks(self.pool))
                self._pile_scroll = max(0, min(n - 1, self._pile_scroll - event.y))
                return
            hit = next((m for r, m in self._pack_areas if r.collidepoint(self.mouse)), None)
            if hit is not None:
                from .dragselect import DragSelectMixin
                n = len(DragSelectMixin._stacks(hit._base_inventory))
                cur = self._pack_scroll.get(id(hit), 0)
                self._pack_scroll[id(hit)] = max(0, min(n - 1, cur - event.y))
                return
        super().handle_event(event)

    # ------------------------------------------------------------------ #
    # soft tutorial (screen.py)                                          #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "loot"

    # ------------------------------------------------------------------ #
    @staticmethod
    def _fits(member, name, qty=1):
        return member.load + data.item_weight(name) * qty <= member.carry_max

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

        # 1. Click on a pack item in a survivor's pack
        for rect, m, idx in self.pack_rows:
            if rect.collidepoint(px):
                if self.pack_sel == (m, idx):
                    # Clicking selected item again drops it to ground
                    if idx < len(m._base_inventory):
                        name, qty = m._base_inventory[idx]
                        m.take_from_pack(idx, qty)
                        self.pool.extend([name] * qty)
                        label = name if qty == 1 else f"{name} ×{qty}"
                        self.notice = f"{m.name} dropped {label} to the ground."
                    self.pack_sel = None
                else:
                    self.pack_sel = (m, idx)
                    self.sel = None
                return

        # 2. If a pack item is selected, check dropping on ground pile or another survivor
        if self.pack_sel is not None:
            m, idx = self.pack_sel
            if idx < len(m._base_inventory):
                name, qty = m._base_inventory[idx]
                label = name if qty == 1 else f"{name} ×{qty}"
                if self.pile_rect and self.pile_rect.collidepoint(px):
                    m.take_from_pack(idx, qty)
                    self.pool.extend([name] * qty)
                    self.notice = f"{m.name} dropped {label} to the ground."
                    self.pack_sel = None
                    return
                for rect, m2 in self.cards:
                    if rect.collidepoint(px) and m2 != m:
                        if self._fits(m2, name, qty):
                            m.take_from_pack(idx, qty)
                            m2.give_to_pack(name, qty)
                            self.notice = f"Moved {label} from {m.name} to {m2.name}."
                        else:
                            self.notice = f"{m2.name} can't carry {name} (max load)."
                        self.pack_sel = None
                        return
            self.pack_sel = None

        # 3. Click on ground pool row
        for rect, i in self.rows:
            if rect.collidepoint(px):
                self.sel = None if self.sel == i else i
                self.pack_sel = None
                return

        # 4. If ground item selected, dropping on survivor
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
            self.sel = None

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
        self.pack_sel = None
        self.notice = "Grab the rest by hand or leave it behind."

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        screen.fill((18, 19, 24))
        self.rows = []
        self.pack_rows = []
        self.cards = []
        self._reset_buttons()
        self._pack_areas = []
        self._pile_area = None

        text(screen, "LOOT", f.title, INK, (MARGIN, MARGIN - 2))
        left = f"{len(self.pool)} items on the field" if self.pool else "field cleared"
        text(screen, f"{left}  ·  ceiling = each one's max load  ·  click pack item to drop or transfer",
             f.body, INK_DIM, (MARGIN, MARGIN + 30))

        top = MARGIN + 72
        pile_w = 300
        pile = pygame.Rect(MARGIN, top, pile_w, screen.get_height() - top - 72)
        self._draw_pile(screen, pile)
        self._draw_survivors(screen, pygame.Rect(pile.right + MARGIN, top,
                                                 screen.get_width() - pile.right - 2 * MARGIN,
                                                 pile.h))
        self._draw_footer(screen)

    def _draw_pile(self, screen, rect):
        f = self.fonts
        self.pile_rect = rect
        pack_hov = self.pack_sel is not None and rect.collidepoint(self.mouse)
        panel(screen, rect, fill=SURFACE_2, border=OK if pack_hov else LINE_SOFT,
              width=2 if pack_hov else 1, radius=RADIUS)
        x, w = rect.x + SP3, rect.w - 2 * SP3
        y = section(screen, "ON THE GROUND", x, rect.y + SP3, w, f)

        stacks = self._ground_stacks(self.pool)
        if not stacks:
            text(screen, "(nothing)", f.body_sm, INK_FAINT, (x, y + 2))
            return

        row_h = 26 + SP1
        max_bottom = rect.bottom - SP3
        if pack_hov:
            max_bottom -= 20
            
        self._pile_area = pygame.Rect(x, y, w, max(0, max_bottom - y))
        visible_n = max(1, (max_bottom - y) // row_h)
        self._pile_scroll = max(0, min(self._pile_scroll, max(0, len(stacks) - visible_n)))
        
        scroll = self._pile_scroll
        if scroll:
            text(screen, f"^ {scroll} more above", f.label, INK_FAINT, (x, y + 2))
            y += 14

        shown = stacks[scroll:scroll + visible_n]
        for name, idxs in shown:
            count = len(idxs)
            idx = idxs[-1]
            r = pygame.Rect(x, y, w, 26)
            sel = self.sel in idxs
            hov = r.collidepoint(self.mouse)
            panel(screen, r, fill=ACCENT if sel else SURFACE_3 if hov else SURFACE_1,
                  border=ACCENT if sel else LINE_SOFT, width=1, radius=4)
            ink = ACCENT_INK if sel else INK
            label = name if count == 1 else f"{name}  ×{count}"
            text(screen, label, f.body_sm, ink, (r.x + SP2, r.y + 6))
            text(screen, kg(data.item_weight(name)), f.mono_sm,
                 ACCENT_INK if sel else INK_DIM, (r.right - SP2, r.y + 7), right=True)
            self.rows.append((r, self.sel if sel else idx))
            y += row_h

        more_below = len(stacks) - scroll - len(shown)
        if more_below > 0:
            text(screen, f"v {more_below} more below", f.label, INK_FAINT, (x, y + 2))
            y += 14

        if pack_hov:
            text(screen, "click: drop to ground", f.label, OK,
                 (rect.centerx, rect.bottom - 16), center=True)

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
        
        has_pack_sel = self.pack_sel is not None
        sm, sidx = self.pack_sel if has_pack_sel else (None, None)
        transfer_ok = False
        if has_pack_sel and m != sm and sidx < len(sm._base_inventory):
            sname, sqty = sm._base_inventory[sidx]
            transfer_ok = self._fits(m, sname, sqty)

        panel(screen, rect, fill=SURFACE_2,
              border=OK if ((drop_ok or transfer_ok) and hov) else DANGER if ((sel or (has_pack_sel and m != sm)) and hov) else LINE_SOFT,
              width=2 if hov else 1, radius=RADIUS)

        tok = (rect.x + pad + 12, rect.y + pad + 12)
        token_badge(screen, tok, m, f)
        name_txt = m.name + (" (Stabilized)" if getattr(m, "hp", 1) <= 0 else "")
        text(screen, name_txt, f.card_name, INK, (tok[0] + 24, rect.y + pad))
        text(screen, f"{m.race['name']}  ·  {m.occupation['name']}", f.body_sm,
             INK_DIM, (tok[0] + 24, rect.y + pad + 20))

        y = rect.y + pad + 46
        over = m.load > m.carry_max
        ccol = DANGER if over else OK
        text(screen, f"Load {kg(m.load)} / {kg(m.carry_max)}", f.mono_sm, ccol,
             (rect.x + pad, y))
        y += 14
        room = max(0.0, m.carry_max - m.load)
        text(screen, f"room {kg(round(room, 1))}", f.body_sm, INK_FAINT, (rect.x + pad, y))
        y += 20

        y = section(screen, "PACK", rect.x + pad, y, rect.w - 2 * pad, f)
        from .dragselect import DragSelectMixin
        stacks = DragSelectMixin._stacks(m._base_inventory)   # real stacks: [(name, idx, qty)]
        if not stacks:
            text(screen, "(empty)", f.body_sm, INK_FAINT, (rect.x + pad, y + 2))

        row_h = 22
        max_bottom = rect.bottom - 26
        pack_area = pygame.Rect(rect.x + pad, y, rect.w - 2 * pad, max(0, max_bottom - y))
        self._pack_areas.append((pack_area, m))
        visible_n = max(1, (max_bottom - y) // row_h)
        scroll = max(0, min(self._pack_scroll.get(id(m), 0), max(0, len(stacks) - visible_n)))
        self._pack_scroll[id(m)] = scroll

        if scroll:
            text(screen, f"^ {scroll} more above", f.label, INK_FAINT, (rect.x + pad, y + 2))
            y += 14

        shown = stacks[scroll:scroll + visible_n]
        for name, idx, count in shown:
            r = pygame.Rect(rect.x + pad, y - 2, rect.w - 2 * pad, 20)
            ihov = r.collidepoint(self.mouse)
            sel_this = self.pack_sel == (m, idx)

            if sel_this or ihov:
                panel(screen, r, fill=ACCENT if sel_this else SURFACE_3,
                      border=ACCENT if sel_this else LINE_SOFT, width=1, radius=4)
            label = name if count == 1 else f"{name}  ×{count}"
            text(screen, label, f.body_sm, ACCENT_INK if sel_this else INK if ihov else INK_DIM,
                 (r.x + 4, y))
            text(screen, kg(data.item_weight(name) * count), f.mono_sm,
                 ACCENT_INK if sel_this else INK_FAINT, (r.right - 4, y), right=True)
            self.pack_rows.append((r, m, idx))
            y += row_h

        more_below = len(stacks) - scroll - len(shown)
        if more_below > 0:
            text(screen, f"v {more_below} more below", f.label, INK_FAINT, (rect.x + pad, y + 2))
            y += 14

        if sel and hov:
            msg = "click: take" if drop_ok else "won't fit"
            text(screen, msg, f.label, OK if drop_ok else DANGER,
                 (rect.centerx, rect.bottom - 16), center=True)
        elif has_pack_sel and hov:
            if m == sm:
                text(screen, "click: drop to ground", f.label, WARN,
                     (rect.centerx, rect.bottom - 16), center=True)
            else:
                msg = "click: transfer" if transfer_ok else "won't fit"
                text(screen, msg, f.label, OK if transfer_ok else DANGER,
                     (rect.centerx, rect.bottom - 16), center=True)

    def _draw_footer(self, screen):
        lbl = "DONE" if not self.pool else "LEAVE THE REST AND GO"
        footer_bar(self, screen,
                  back=("auto", "take what fits", bool(self.pool)),
                  primary=("done", lbl), notice=self.notice)
