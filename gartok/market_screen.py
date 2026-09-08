"""Market: buy and sell gear for copper.

The shopping party pools its coin into one **common purse** for the visit (the
guild has no treasury) and the members' packs sit side by side, so you can shift
items and spend freely without per-character fiddling. On the way out the purse
is split back evenly among the shoppers.

Interaction (same as the guild screen): drag an item where it goes, or click to
pick it up and click the destination. Shift/ctrl-click gathers several of a
shopper's items for one move.
- a stock row  -> drop on a shopper to buy it into their pack (needs purse >=
  price and room under their carry max);
- a shopper's item -> drop on another shopper to hand it over, or on the SELL bar
  to sell it back (at `economy.sell_price`, always a loss);
- drop on nothing / click away to cancel.
"""

import pygame

from . import data, economy
from .dragselect import DragSelectMixin
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SURFACE_1,
                    SURFACE_2, SURFACE_3, WARN, kg, panel, section,
                    token_badge, text, tracked)

STOCK_W = 330


class MarketScreen(DragSelectMixin, Screen):
    native = True

    def __init__(self, fonts, guild, shoppers, node, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.shoppers = shoppers
        self.node = node
        self.on_done = on_done
        self.purse = sum(m.gold for m in shoppers)   # pooled for the visit
        # haggling: language + charisma + alignment (and talents) bend the prices.
        # `self.deal` is a list of economy.PriceMod, fed straight to buy/sell_price.
        self.deal = economy.deal_mods(shoppers, getattr(node, "language", None),
                                      getattr(node, "alignment", None))
        self.sel = []                         # [("stock", name) | (member, "hand"|"offhand"|"armor"|idx), ...]
        self.notice = None
        self.stock_rows = []                 # [(rect, name)]
        self.item_rows = []                  # [(rect, member, loc)]
        self.cards = []                      # [(rect, member)]
        self.buttons = []                   # [(key, rect)]

    # ------------------------------------------------------------------ #
    @staticmethod
    def _item_at(member, loc):
        if loc == "hand":
            return member.equipped_weapon
        if loc == "offhand":
            return member.equipped_offhand
        if loc == "armor":
            return member.equipped_armor
        return member._base_inventory[loc] if loc < len(member._base_inventory) else None

    @staticmethod
    def _take(member, loc):
        if loc == "hand":
            return member.take_from_hand()
        if loc == "offhand":
            return member.take_from_offhand()
        if loc == "armor":
            return member.take_from_armor()
        return member.take_from_pack(loc)

    def _name_of(self, pick):
        if pick[0] == "stock":
            return pick[1]
        return self._item_at(*pick)

    def _selected_names(self):
        return [n for n in (self._name_of(p) for p in self.sel) if n is not None]

    @property
    def _buying(self):
        return bool(self.sel) and self.sel[0][0] == "stock"

    def _fits(self, member, name):
        return member.load + data.item_weight(name) <= member.carry_max

    def _deal_note(self):
        """One-line summary of how the party's haggling moved the prices."""
        lang = getattr(self.node, "language", None)
        general = economy.deal_value(self.deal, None, "buy")
        food = economy.deal_value(self.deal, next(iter(data.FOOD_ITEMS)), "buy")
        food_tag = (f"  ·  food -{round(food * 100)}%"
                    if round(food, 3) != round(general, 3) else "")
        if not lang:
            return f"resale at {int(economy.SELL_FACTOR * 100)}% of price"
        pct = round(general * 100)
        speaks = any(lang in m.languages for m in self.shoppers)
        if not speaks:
            return (f"no one speaks {lang}: no haggling "
                    f"(resale at {int(economy.SELL_FACTOR * 100)}%)" + food_tag)
        how = (f"{pct}% discount" if pct > 0
               else f"{-pct}% markup" if pct < 0 else "no margin")
        return f"vendor speaks {lang} · {self.node.alignment} · {how}{food_tag}"

    # ------------------------------------------------------------------ #
    # input: click / shift-click to (multi-)select, or drag onto a card  #
    # (the press/drag machinery lives in DragSelectMixin)                #
    # ------------------------------------------------------------------ #
    def _source_at(self, px):
        for rect, name in self.stock_rows:
            if rect.collidepoint(px):
                return ("stock", name)
        for rect, member, loc in self.item_rows:
            if rect.collidepoint(px):
                return (member, loc)
        return None

    def _begin_drag(self, src):
        if src not in self.sel or src[0] == "stock":
            self.sel = [src]

    def _drop(self, px, dragging, src):
        if dragging:
            for rect, member in self.cards:
                if rect.collidepoint(px):
                    self._drop_on(member)
                    return
            for key, rect in self.buttons:
                if key == "sell" and rect.collidepoint(px):
                    self._sell()
                    return
            return

        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "done":
                    self._checkout()
                elif key == "sell":
                    self._sell()
                return

        self.notice = None
        mods = pygame.key.get_mods()
        multi = src is not None and src[0] != "stock" \
            and mods & (pygame.KMOD_SHIFT | pygame.KMOD_CTRL) \
            and (not self.sel or self.sel[0][0] != "stock")
        if multi:
            if src in self.sel:
                self.sel.remove(src)
            else:
                self.sel.append(src)
            return

        if self.sel:
            for rect, member in self.cards:
                if rect.collidepoint(px):
                    self._drop_on(member)
                    return
            self.sel = [src] if src is not None else []
            return
        self.sel = [src] if src is not None else []

    # ------------------------------------------------------------------ #
    def _drop_on(self, member):
        picks, self.sel = self.sel, []
        picks = [p for p in picks if self._name_of(p) is not None]
        if not picks:
            return

        if picks[0][0] == "stock":
            bought = 0
            for _, name in picks:
                price = economy.buy_price(name, self.deal)
                if self.purse < price:
                    self.notice = f"Not enough copper for {name} ({price})."
                    break
                if not self._fits(member, name):
                    self.notice = f"{name} won't fit {member.name}'s load."
                    continue
                self.purse -= price
                member.give_to_pack(name)
                bought += 1
            member._derive_combat()
            if bought:
                self.notice = f"{member.name} bought {bought} item(s)."
            return

        picks = [p for p in picks if p[0] is not member]   # dropped back home: skip
        if not picks:
            return
        add = sum(data.item_weight(self._name_of(p)) for p in picks)
        if member.load + add > member.carry_max:
            self.notice = f"won't fit {member.name}'s load."
            self.sel = picks
            return
        names, touched = self._collect(picks)
        for name in names:
            member.give_to_pack(name)
        for u in touched:
            u._derive_combat()
        member._derive_combat()
        self.notice = f"{len(names)} item(s) -> {member.name}."

    def _sell(self):
        picks = [p for p in self.sel
                 if p[0] != "stock" and self._name_of(p) is not None]
        self.sel = []
        if not picks:
            return
        names, touched = self._collect(picks)
        total = sum(economy.sell_price(n, self.deal) for n in names)
        self.purse += total
        for u in touched:
            u._derive_combat()
        self.notice = f"sold {len(names)} item(s) for {total}."

    def _checkout(self):
        n = max(1, len(self.shoppers))
        base, rem = divmod(self.purse, n)
        for i, m in enumerate(self.shoppers):
            m.gold = base + (1 if i < rem else 0)
        self.on_done()

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        screen.fill((18, 19, 24))
        self.stock_rows = []
        self.item_rows = []
        self.cards = []
        self.buttons = []

        text(screen, "MARKET", f.title, INK, (MARGIN, MARGIN - 2))
        text(screen, f"common purse: {self.purse} copper", f.body_bd, ACCENT,
             (screen.get_width() - MARGIN, MARGIN + 2), right=True)
        names = self._selected_names()
        if names:
            one = names[0] if len(names) == 1 else f"{len(names)} items"
            if self._buying:
                msg = (f"buy {one} ({sum(economy.buy_price(n, self.deal) for n in names)})"
                       "  ·  drop on a member")
            else:
                msg = (f"moving {one}  ·  drop on another member, or on SELL "
                       f"(+{sum(economy.sell_price(n, self.deal) for n in names)})")
            text(screen, msg + "  ·  click outside to cancel", f.body, ACCENT,
                 (MARGIN, MARGIN + 30))
        else:
            text(screen, f"common purse: {self.purse} copper  ·  {len(self.shoppers)} "
                 f"shopping  ·  {self._deal_note()}",
                 f.body, INK_DIM, (MARGIN, MARGIN + 30))

        top = MARGIN + 64
        stock = pygame.Rect(MARGIN, top, STOCK_W, screen.get_height() - top - 72)
        self._draw_stock(screen, stock)
        self._draw_shoppers(screen, pygame.Rect(stock.right + MARGIN, top,
                                                screen.get_width() - stock.right - 2 * MARGIN,
                                                stock.h))
        self._draw_footer(screen)

        if self._dragging and names:
            gx, gy = self.mouse
            label = names[0] if len(names) == 1 else f"{len(names)} items"
            gr = pygame.Rect(gx + 12, gy + 6, f.body_sm.size(label)[0] + 2 * SP2, 20)
            panel(screen, gr, fill=ACCENT, border=ACCENT_INK, width=1, radius=4)
            text(screen, label, f.body_sm, ACCENT_INK, gr.center, center=True)

    def _draw_stock(self, screen, rect):
        f = self.fonts
        panel(screen, rect, fill=SURFACE_2, border=LINE_SOFT, radius=RADIUS)
        x, w = rect.x + SP3, rect.w - 2 * SP3
        y = section(screen, "FOR SALE", x, rect.y + SP3, w, f)
        for name in economy.MARKET_STOCK:
            r = pygame.Rect(x, y, w, 26)
            sel = ("stock", name) in self.sel
            hov = not self.sel and r.collidepoint(self.mouse)
            price = economy.buy_price(name, self.deal)
            afford = self.purse >= price
            fits = any(self._fits(m, name) for m in self.shoppers)
            panel(screen, r, fill=ACCENT if sel else SURFACE_3 if hov else SURFACE_1,
                  border=ACCENT if sel else LINE_SOFT, width=1, radius=4)
            ink = ACCENT_INK if sel else INK if afford else INK_FAINT
            text(screen, name, f.body_sm, ink, (r.x + SP2, r.y + 6))
            wtext = kg(data.item_weight(name))
            text(screen, wtext, f.mono_sm,
                 ACCENT_INK if sel else INK_DIM if fits else DANGER,
                 (r.right - SP2, r.y + 7), right=True)
            wx = r.right - SP2 - f.mono_sm.size(wtext)[0] - SP2
            text(screen, str(price), f.mono_sm,
                 ACCENT_INK if sel else INK_DIM if afford else INK_FAINT,
                 (wx, r.y + 7), right=True)
            self.stock_rows.append((r, name))
            y += 26 + SP1

    def _draw_shoppers(self, screen, area):
        n = max(1, len(self.shoppers))
        gap = SP3
        card_w = min(300, (area.w - (n - 1) * gap) // n)
        for i, m in enumerate(self.shoppers):
            rect = pygame.Rect(area.x + i * (card_w + gap), area.y, card_w, area.h)
            self._draw_card(screen, rect, m)
            self.cards.append((rect, m))

    def _draw_card(self, screen, rect, m):
        f = self.fonts
        pad = SP3
        names = self._selected_names()
        add = sum(data.item_weight(n) for n in names)
        take_ok = bool(names) and m.load + add <= m.carry_max
        owns_sel = any(p[0] is m for p in self.sel if p[0] != "stock")
        hov = rect.collidepoint(self.mouse)
        panel(screen, rect, fill=SURFACE_2,
              border=OK if (take_ok and hov and not owns_sel) else
              DANGER if (names and hov and not take_ok) else LINE_SOFT,
              width=2 if hov else 1, radius=RADIUS)

        tok = (rect.x + pad + 12, rect.y + pad + 12)
        token_badge(screen, tok, m, f)
        text(screen, m.name, f.card_name, INK, (tok[0] + 24, rect.y + pad))
        text(screen, f"{m.race['name']}  ·  {m.occupation['name']}", f.body_sm,
             INK_DIM, (tok[0] + 24, rect.y + pad + 20))

        y = rect.y + pad + 48
        over_norm = m.load > m.carry_normal
        over_max = m.load > m.carry_max
        ccol = DANGER if over_max else WARN if over_norm else OK
        text(screen, f"Load {kg(m.load)} / {kg(m.carry_normal)}", f.mono_sm,
             ccol, (rect.x + pad, y))
        note = ("OVER HIGH LOAD  -2 STR/DEX, -1 speed" if over_max
                else "overloaded  -2 STR/DEX, -1 speed" if over_norm else "")
        if note:
            y += 13
            text(screen, note, f.label, ccol, (rect.x + pad, y))
        y += 18

        for loc, label in (("hand", "weapon"), ("offhand", "off hand"), ("armor", "body")):
            held = self._item_at(m, loc)
            if not held:
                continue
            r = pygame.Rect(rect.x + pad, y, rect.w - 2 * pad, 24)
            self._draw_item_row(screen, r, m, loc, held, tag=label.upper())
            y += 24 + SP1

        y = section(screen, "PACK", rect.x + pad, y + SP1, rect.w - 2 * pad, f)
        if not m._base_inventory:
            text(screen, "(empty)", f.body_sm, INK_FAINT, (rect.x + pad, y + 2))
        for idx, item in enumerate(m._base_inventory):
            r = pygame.Rect(rect.x + pad, y, rect.w - 2 * pad, 24)
            self._draw_item_row(screen, r, m, idx, item)
            y += 24 + SP1

        tracked(screen, "COPPER (COMMON)", f.label, INFO, (rect.x + pad, rect.bottom - 22))

    def _draw_item_row(self, screen, r, member, loc, name, tag=""):
        f = self.fonts
        sel = (member, loc) in self.sel
        hov = not self.sel and r.collidepoint(self.mouse)
        panel(screen, r, fill=ACCENT if sel else SURFACE_3 if hov else SURFACE_1,
              border=ACCENT if sel else LINE_SOFT, width=1, radius=4)
        ink = ACCENT_INK if sel else INK
        text(screen, name, f.body_sm, ink, (r.x + SP2, r.y + 5))
        right = f"{economy.sell_price(name, self.deal)}c"
        if tag:
            right = tag + "  ·  " + right
        text(screen, right, f.mono_sm, ACCENT_INK if sel else INK_DIM,
             (r.right - SP2, r.y + 6), right=True)
        self.item_rows.append((r, member, loc))

    def _draw_footer(self, screen):
        f = self.fonts
        y = screen.get_height() - 52
        if self.notice:
            text(screen, self.notice, f.body_sm, INFO, (MARGIN, y - 22))

        names = self._selected_names()
        can_sell = bool(names) and not self._buying
        if can_sell:
            total = sum(economy.sell_price(n, self.deal) for n in names)
            sr = pygame.Rect(MARGIN, y, 240, 36)
            hov = sr.collidepoint(self.mouse)
            panel(screen, sr, fill=DANGER if hov else SURFACE_3, border=DANGER,
                  width=1, radius=RADIUS)
            text(screen, f"SELL FOR {total}", f.body_bd,
                 ACCENT_INK if hov else DANGER, sr.center, center=True)
            self.buttons.append(("sell", sr))

        done = pygame.Rect(screen.get_width() - MARGIN - 240, y, 240, 36)
        hovd = done.collidepoint(self.mouse)
        panel(screen, done, fill=ACCENT if hovd else SURFACE_3, border=ACCENT,
              width=1, radius=RADIUS)
        text(screen, "LEAVE THE MARKET", f.body_bd, ACCENT_INK if hovd else ACCENT,
             done.center, center=True)
        self.buttons.append(("done", done))
