"""The bank: the guild's strongbox, rented from the Bankers.

The guild owns nothing as a body except this -- a chest at the bank in the City,
rented from the Bankers for a flat fee (`economy.BANK_CHEST_PRICE`) and holding
`guild.bank_capacity` kg. This screen rents the chest and moves gear between it
and the visiting party's packs.

The visiting party's packs sit beside the chest. Only **pack** items move here --
spares in and out of storage; wielding a weapon or wearing armor still happens on
the gear screen. Stashing is free; the one cost is the strongbox rent, charged
across the party (poorest first) -- so members keep their own coin and there is
nothing to settle on the way out.

Interaction (same as the market): drag an item where it goes, or click to pick it
up and click the destination.
- a party member's pack item -> drop on the CHEST to stash it (needs room under
  `bank_capacity`), or on another member to hand it over;
- a chest item -> drop on a member to take it into their pack (needs room under
  their carry max);
- drop on nothing / click away to cancel.
"""

import pygame

from . import data, economy
from .dragselect import DragSelectMixin
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SURFACE_1,
                    SURFACE_2, SURFACE_3, WARN, ellipsize, kg, panel, section,
                    text, token_badge)

CHEST_W = 392
PACK_ROWS_SHOWN = 10                      # pack rows before a "+N more" line kicks in


class BankScreen(DragSelectMixin, Screen):
    native = True

    def __init__(self, fonts, guild, party, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.party = party
        self.on_done = on_done
        self.sel = None                              # ("bank", idx) | (member, idx) | None
        self.notice = None
        self.chest_rows = []                         # [(rect, idx)]
        self.item_rows = []                          # [(rect, member, idx)]
        self.cards = []                              # [(rect, member)]
        self.buttons = []                            # [(key, rect)]

    # ------------------------------------------------------------------ #
    def _name_of(self, pick):
        if pick is None:
            return None
        who, idx = pick
        if who == "bank":
            return self.guild.bank_items[idx] if idx < len(self.guild.bank_items) else None
        return who._base_inventory[idx] if idx < len(who._base_inventory) else None

    @property
    def purse(self):
        """The visiting party's coin, live -- the only thing it ever spends here
        is the strongbox rent. Stashing gear is free, so members keep their own
        money; nothing is pooled and redivided on the way out."""
        return sum(m.gold for m in self.party)

    def _charge(self, amount):
        """Take `amount` copper from the party as evenly as the coins allow --
        poorest first, the shortfall rolling onto whoever still has money."""
        for i, m in enumerate(sorted(self.party, key=lambda x: x.gold)):
            share = min(m.gold, -(-amount // (len(self.party) - i)))
            m.gold -= share
            amount -= share

    @property
    def _from_chest(self):
        return self.sel is not None and self.sel[0] == "bank"

    def _chest_room(self, name):
        return self.guild.bank_load + data.item_weight(name) <= self.guild.bank_capacity

    def _fits(self, member, name):
        return member.load + data.item_weight(name) <= member.carry_max

    # ------------------------------------------------------------------ #
    # input                                                              #
    # ------------------------------------------------------------------ #
    def _source_at(self, px):
        for rect, idx in self.chest_rows:
            if rect.collidepoint(px):
                return ("bank", idx)
        for rect, member, idx in self.item_rows:
            if rect.collidepoint(px):
                return (member, idx)
        return None

    def _begin_drag(self, src):
        self.sel = src

    def _drop(self, px, dragging, src):
        for key, rect in self.buttons:
            if key in ("done", "rent") and rect.collidepoint(px):
                (self._leave if key == "done" else self._rent)()
                return

        if dragging:
            self._resolve(px)
            self.sel = None
            return

        if self.sel is not None:
            if self._resolve(px):
                self.sel = None
                return
            self.sel = None if src == self.sel else src
            return
        self.sel = src

    def _resolve(self, px):
        """Land the carried item on whatever is under `px`. Returns True if the
        release was spent (moved, or bounced off a full target)."""
        if self.sel is None or self._name_of(self.sel) is None:
            return False
        name = self._name_of(self.sel)

        for rect, member in self.cards:
            if rect.collidepoint(px):
                if self._from_chest:
                    self._withdraw(member)
                elif self.sel[0] is not member:
                    self._hand_over(member)
                return True

        for key, rect in self.buttons:
            if key == "chest" and rect.collidepoint(px) and not self._from_chest:
                self._deposit()
                return True
        return False

    # ------------------------------------------------------------------ #
    def _rent(self):
        if self.guild.bank_unlocked:
            return
        if self.purse < economy.BANK_CHEST_PRICE:
            self.notice = (f"the strongbox costs {economy.BANK_CHEST_PRICE} copper — "
                           f"the party has {self.purse}.")
            return
        self._charge(economy.BANK_CHEST_PRICE)
        self.guild.rent_bank_chest()
        self.notice = (f"rented a strongbox — {self.guild.bank_capacity} kg of "
                       "storage at the bank.")

    def _deposit(self):
        name = self._name_of(self.sel)
        member = self.sel[0]
        if not self.guild.bank_unlocked:
            self.notice = "rent a strongbox first."
            return
        if not self._chest_room(name):
            free = self.guild.bank_capacity - self.guild.bank_load
            self.notice = f"{name} won't fit — {free:g} kg free in the chest."
            return
        member.take_from_pack(self.sel[1])
        self.guild.bank_items.append(name)
        member._derive_combat()
        self.notice = f"stashed {name}."

    def _withdraw(self, member):
        name = self._name_of(self.sel)
        if not self._fits(member, name):
            self.notice = f"{name} won't fit {member.name}'s load."
            return
        self.guild.bank_items.pop(self.sel[1])
        member.give_to_pack(name)
        member._derive_combat()
        self.notice = f"{member.name} took {name}."

    def _hand_over(self, member):
        name = self._name_of(self.sel)
        src = self.sel[0]
        if not self._fits(member, name):
            self.notice = f"{name} won't fit {member.name}'s load."
            return
        src.take_from_pack(self.sel[1])
        member.give_to_pack(name)
        src._derive_combat()
        member._derive_combat()
        self.notice = f"{name} → {member.name}."

    def _leave(self):
        self.on_done()               # members kept their own coin -- nothing to settle

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        screen.fill((18, 19, 24))
        self.chest_rows = []
        self.item_rows = []
        self.cards = []
        self.buttons = []

        text(screen, "THE BANK", f.title, INK, (MARGIN, MARGIN - 2))
        text(screen, f"common purse: {self.purse} copper", f.body_bd, ACCENT,
             (screen.get_width() - MARGIN, MARGIN + 2), right=True)

        name = self._name_of(self.sel)
        if name:
            where = "the chest" if self._from_chest else self.sel[0].name + "'s pack"
            text(screen, f"moving {name} from {where}  ·  drop on the chest or a "
                 "member  ·  click outside to cancel", f.body, ACCENT,
                 (MARGIN, MARGIN + 30))
        else:
            text(screen, f"{len(self.party)} at the bank  ·  the Bankers rent one "
                 "strongbox — a flat fee, no questions", f.body, INK_DIM,
                 (MARGIN, MARGIN + 30))

        top = MARGIN + 62
        chest = pygame.Rect(MARGIN, top, CHEST_W, screen.get_height() - top - 72)
        self._draw_chest(screen, chest)
        self._draw_party(screen, pygame.Rect(chest.right + MARGIN, top,
                                             screen.get_width() - chest.right - 2 * MARGIN,
                                             chest.h))
        self._draw_footer(screen)

        if self._dragging and name:
            gx, gy = self.mouse
            gr = pygame.Rect(gx + 12, gy + 6, f.body_sm.size(name)[0] + 2 * SP2, 20)
            panel(screen, gr, fill=ACCENT, border=ACCENT_INK, width=1, radius=4)
            text(screen, name, f.body_sm, ACCENT_INK, gr.center, center=True)

    # ------------------------------------------------------------------ #
    def _draw_chest(self, screen, rect):
        f = self.fonts
        carried = self._name_of(self.sel)
        depositing = bool(carried) and not self._from_chest
        hov = rect.collidepoint(self.mouse)
        panel(screen, rect, fill=SURFACE_2,
              border=INFO if (depositing and hov) else LINE_SOFT,
              width=2 if (depositing and hov) else 1, radius=RADIUS)
        self.buttons.append(("chest", rect))

        x, w = rect.x + SP3, rect.w - 2 * SP3
        y = section(screen, "THE STRONGBOX", x, rect.y + SP3, w, f)

        if not self.guild.bank_unlocked:
            for ln in ("The guild has no strongbox yet.",
                       f"The Bankers rent one for {economy.BANK_CHEST_PRICE} copper:",
                       f"{economy.BANK_CHEST_CAPACITY} kg of storage, held safe in "
                       "the City."):
                text(screen, ln, f.body_sm, INK_DIM, (x, y))
                y += 17
            y += SP2
            r = pygame.Rect(x, y, w, 38)
            can = self.purse >= economy.BANK_CHEST_PRICE
            hovr = r.collidepoint(self.mouse)
            panel(screen, r, fill=ACCENT if (can and hovr) else SURFACE_3,
                  border=ACCENT if can else LINE_SOFT, width=1, radius=RADIUS)
            text(screen, f"RENT A STRONGBOX — {economy.BANK_CHEST_PRICE} COPPER", f.body_bd,
                 ACCENT_INK if (can and hovr) else ACCENT if can else INK_FAINT,
                 r.center, center=True)
            self.buttons.append(("rent", r))
            return

        # capacity bar
        used, cap = self.guild.bank_load, self.guild.bank_capacity
        over = used > cap
        bar = pygame.Rect(x, y, w, 10)
        panel(screen, bar, fill=SURFACE_1, border=LINE_SOFT, width=1, radius=4)
        span = bar.w - 2
        fillw = int(span * min(1.0, used / max(1, cap)))
        if fillw > 0:
            pygame.draw.rect(screen, DANGER if over else OK,
                             (bar.x + 1, bar.y + 1, fillw, bar.h - 2), border_radius=3)
        y += 15
        text(screen, f"{kg(used)}  /  {kg(cap)}", f.mono_sm,
             DANGER if over else INK_DIM, (x, y))
        y += 18

        y = section(screen, f"STASHED  ({len(self.guild.bank_items)})", x, y, w, f)
        if not self.guild.bank_items:
            text(screen, "(empty)", f.body_sm, INK_FAINT, (x, y + 2))
        for idx, item in enumerate(self.guild.bank_items):
            r = pygame.Rect(x, y, w, 28)
            if r.bottom > rect.bottom - SP3:
                text(screen, f"+{len(self.guild.bank_items) - idx} more", f.label,
                     INK_FAINT, (x, y + 4))
                break
            sel = self.sel == ("bank", idx)
            ihov = not self.sel and r.collidepoint(self.mouse)
            panel(screen, r, fill=ACCENT if sel else SURFACE_3 if ihov else SURFACE_1,
                  border=ACCENT if sel else LINE_SOFT, width=1, radius=4)
            text(screen, ellipsize(item, f.body, w - 70), f.body,
                 ACCENT_INK if sel else INK, (r.x + SP2, r.y + 6))
            text(screen, kg(data.item_weight(item)), f.mono_sm,
                 ACCENT_INK if sel else INK_DIM, (r.right - SP2, r.y + 7), right=True)
            self.chest_rows.append((r, idx))
            y += 28 + SP1

    # ------------------------------------------------------------------ #
    def _draw_party(self, screen, area):
        n = max(1, len(self.party))
        gap = SP3
        card_w = min(300, (area.w - (n - 1) * gap) // n)
        for i, m in enumerate(self.party):
            rect = pygame.Rect(area.x + i * (card_w + gap), area.y, card_w, area.h)
            self._draw_card(screen, rect, m)
            self.cards.append((rect, m))

    def _draw_card(self, screen, rect, m):
        f = self.fonts
        pad = SP3
        name = self._name_of(self.sel)
        incoming = bool(name) and not (self.sel[0] is m)
        take_ok = incoming and self._fits(m, name)
        hov = rect.collidepoint(self.mouse)
        panel(screen, rect, fill=SURFACE_2,
              border=OK if (take_ok and hov) else DANGER if (incoming and hov and not take_ok)
              else LINE_SOFT, width=2 if hov else 1, radius=RADIUS)

        tok = (rect.x + pad + 12, rect.y + pad + 12)
        token_badge(screen, tok, m, f)
        text(screen, m.name, f.card_name, INK, (tok[0] + 24, rect.y + pad))
        text(screen, f"{m.race['name']}  ·  {m.occupation['name']}", f.body_sm,
             INK_DIM, (tok[0] + 24, rect.y + pad + 20))

        y = rect.y + pad + 48
        over = m.load > m.carry_max
        ccol = DANGER if over else WARN if m.encumbered else OK
        text(screen, f"Load {kg(m.load)} / {kg(m.carry_normal)}", f.mono_sm, ccol,
             (rect.x + pad, y))
        y += 18

        y = section(screen, f"PACK  ({len(m._base_inventory)})", rect.x + pad, y,
                    rect.w - 2 * pad, f)
        if not m._base_inventory:
            text(screen, "(empty)", f.body_sm, INK_FAINT, (rect.x + pad, y + 2))
        shown = m._base_inventory[:PACK_ROWS_SHOWN]
        for idx, item in enumerate(shown):
            r = pygame.Rect(rect.x + pad, y, rect.w - 2 * pad, 24)
            sel = self.sel == (m, idx)
            ihov = not self.sel and r.collidepoint(self.mouse)
            panel(screen, r, fill=ACCENT if sel else SURFACE_3 if ihov else SURFACE_1,
                  border=ACCENT if sel else LINE_SOFT, width=1, radius=4)
            text(screen, ellipsize(item, f.body_sm, rect.w - 2 * pad - 60), f.body_sm,
                 ACCENT_INK if sel else INK, (r.x + SP2, r.y + 5))
            text(screen, kg(data.item_weight(item)), f.mono_sm,
                 ACCENT_INK if sel else INK_DIM, (r.right - SP2, r.y + 6), right=True)
            self.item_rows.append((r, m, idx))
            y += 24 + SP1
        extra = len(m._base_inventory) - len(shown)
        if extra > 0:
            text(screen, f"+{extra} more in the pack", f.label, INK_FAINT,
                 (rect.x + pad, y + 2))

    # ------------------------------------------------------------------ #
    def _draw_footer(self, screen):
        f = self.fonts
        y = screen.get_height() - 52
        if self.notice:
            text(screen, self.notice, f.body_sm, INFO, (MARGIN, y - 22))

        done = pygame.Rect(screen.get_width() - MARGIN - 240, y, 240, 36)
        hovd = done.collidepoint(self.mouse)
        panel(screen, done, fill=ACCENT if hovd else SURFACE_3, border=ACCENT,
              width=1, radius=RADIUS)
        text(screen, "LEAVE THE BANK", f.body_bd, ACCENT_INK if hovd else ACCENT,
             done.center, center=True)
        self.buttons.append(("done", done))
