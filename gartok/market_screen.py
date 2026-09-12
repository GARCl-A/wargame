"""Market: buy and sell gear for copper.

The shopping party pools its coin into one **common purse** for the visit (the
guild has no treasury) and the members' packs sit side by side, so you can shift
items and spend freely without per-character fiddling. On the way out the purse
is split back evenly among the shoppers.

The stock is split into **category tabs** -- WEAPONS / ARMOR / CONSUMABLES & KIT
(`economy.market_categories`) -- each with a column layout tuned to what matters
for that shelf (damage and hands for weapons, AC and the Dexterity cap for armor,
a quantity stepper for the stackable kit).

Interaction (same as the guild screen): drag an item where it goes, or click to
pick it up and click the destination. Shift/ctrl-click gathers several of a
shopper's items for one move.
- a stock row  -> drop on a shopper to buy it into their pack (the kit tab buys
  the stepper's quantity in one drop); needs purse >= price and room under the
  carry max;
- a shopper's item -> drop on another shopper to hand it over, or on the SELL bar
  to sell it back (at `economy.sell_price`, always a loss);
- drop on nothing / click away to cancel.
"""

import pygame

from . import data, economy
from .dragselect import DragSelectMixin
from .screen import Screen
from .sheet_panel import SheetModalMixin
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SURFACE_1,
                    SURFACE_2, SURFACE_3, WARN, ellipsize, kg, panel, section,
                    token_badge, text, tracked)

STOCK_W = 392


class MarketScreen(DragSelectMixin, SheetModalMixin, Screen):
    native = True

    def __init__(self, fonts, guild, shoppers, node, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.shoppers = shoppers
        self.node = node
        self.on_done = on_done
        self.purse = sum(m.gold for m in shoppers)   # pooled for the visit
        # haggling: language + charisma + alignment (and talents) bend the prices;
        # the shopping group's leader speaks for it when they're eligible (see
        # economy._haggle_fraction). `self.deal` is a list of economy.PriceMod,
        # fed straight to buy/sell_price.
        group = guild.group_of(shoppers[0]) if guild and shoppers else None
        self.deal = economy.deal_mods(shoppers, getattr(node, "language", None),
                                      getattr(node, "alignment", None),
                                      leader=group.leader if group else None)
        self.tab = economy.market_categories()[0][1]     # "weapons"
        self.qty = {}                        # kit tab: stock name -> quantity to buy
        self.sel = []                         # [("stock", name) | (member, "hand"|"offhand"|"armor"|idx), ...]
        self.notice = None
        self.stock_rows = []                 # [(rect, name)]
        self.qty_hits = []                   # [(rect, name, delta)]
        self.info_hits = []                  # [(rect, member)] -- the card's 'i' disc opens the sheet
        self._pack_scroll = {}               # id(member) -> stacks scrolled past in the pack list
        self._pack_areas = []                # [(rect, member)] -- pack list rects, for wheel hit-testing
        self.tab_hits = []                  # [(rect, key)]
        self.item_rows = []                  # [(rect, member, loc)]
        self.cards = []                      # [(rect, member)]
        self.buttons = []                   # [(key, rect)]

    # ------------------------------------------------------------------ #
    # soft tutorial (screen.py)                                          #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "market"

    def tutorial_anchor(self, size):
        return self.footer_anchor(size)

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

    def _buy_qty(self, name):
        return max(1, self.qty.get(name, 1))

    def _fits(self, member, name):
        return member.load + data.item_weight(name) <= member.carry_max

    def _stock_of(self, name):
        """Units of `name` left to buy, or None if unlimited -- also None with
        no `guild` (a few tests build a bare screen with no campaign behind it)."""
        guild = getattr(self, "guild", None)
        return economy.stock_of(guild.market_stock, name) if guild else None

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
        for rect, _name, _delta in self.qty_hits:
            if rect.collidepoint(px):
                return None                  # a stepper press starts no drag / select
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

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            hit = next((m for r, m in self._pack_areas if r.collidepoint(self.mouse)), None)
            if hit is not None:
                n = len(self._stacks(hit._base_inventory))
                cur = self._pack_scroll.get(id(hit), 0)
                self._pack_scroll[id(hit)] = max(0, min(n - 1, cur - event.y))
                return
        super().handle_event(event)

    def _bump_qty(self, name, delta):
        step = delta * (5 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1)
        self.qty[name] = max(1, self._buy_qty(name) + step)

    def _drop(self, px, dragging, src):
        if self.close_sheet_on_click():        # sheet modal up: any click just closes it
            return

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

        for rect, name, delta in self.qty_hits:
            if rect.collidepoint(px):
                self._bump_qty(name, delta)
                return

        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "done":
                    self._checkout()
                elif key == "sell":
                    self._sell()
                return

        for rect, key in self.tab_hits:
            if rect.collidepoint(px):
                self.tab, self.sel, self.notice = key, [], None
                return

        for rect, member in self.info_hits:
            if rect.collidepoint(px):
                self.open_sheet(member)
                return

        self.notice = None
        mods = pygame.key.get_mods()
        multi = src is not None and src[0] != "stock" \
            and mods & (pygame.KMOD_SHIFT | pygame.KMOD_CTRL) \
            and (not self.sel or self.sel[0][0] != "stock")
        if multi:
            group = self._expand_stack(src)
            if src in self.sel:
                self.sel = [p for p in self.sel if p not in group]
            else:
                self.sel += [p for p in group if p not in self.sel]
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
            self._buy(member, [name for _, name in picks])
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

    def _buy(self, member, names):
        """Buy each stock name (the kit tab's stepper quantity, else one), into
        `member`'s pack -- stopping the moment the purse, the load or the
        vendor's stock runs out."""
        bought = 0
        wanted = sum(self._buy_qty(n) for n in names)
        stopped = None
        for name in names:
            for _ in range(self._buy_qty(name)):
                stock = self._stock_of(name)
                if stock is not None and stock <= 0:
                    stopped = f"no {name} in stock"
                    break
                price = economy.buy_price(name, self.deal)
                if self.purse < price:
                    stopped = "out of copper"
                    break
                if not self._fits(member, name):
                    stopped = f"{name} won't fit {member.name}'s load"
                    break
                self.purse -= price
                member.give_to_pack(name)
                if stock is not None:
                    self.guild.market_stock[name] = stock - 1
                bought += 1
            if stopped:
                break
        member._derive_combat()
        for name in names:
            self.qty.pop(name, None)             # reset the steppers after a buy
        what = names[0] if len(names) == 1 else "items"
        if bought and stopped:
            self.notice = f"{member.name} bought {bought} of {wanted}  ·  {stopped}."
        elif bought:
            self.notice = f"{member.name} bought {bought}× {what}."
        elif stopped:
            self.notice = f"{stopped[0].upper()}{stopped[1:]}."

    def _sell(self):
        picks = [p for p in self.sel
                 if p[0] != "stock" and self._name_of(p) is not None]
        self.sel = []
        if not picks:
            return
        names, touched = self._collect(picks)
        total = sum(economy.sell_price(n, self.deal) for n in names)
        self.purse += total
        for n in names:
            stock = self._stock_of(n)
            if stock is not None:
                self.guild.market_stock[n] = stock + 1
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
        self.qty_hits = []
        self.tab_hits = []
        self.item_rows = []
        self.cards = []
        self.buttons = []
        self.info_hits = []
        self._pack_areas = []

        text(screen, "MARKET", f.title, INK, (MARGIN, MARGIN - 2))
        text(screen, f"common purse: {self.purse} copper", f.body_bd, ACCENT,
             (screen.get_width() - MARGIN, MARGIN + 2), right=True)
        names = self._selected_names()
        if names:
            if self._buying:
                name = names[0]
                q = self._buy_qty(name)
                one = name if q == 1 else f"{name} ×{q}"
                msg = (f"buy {one} ({economy.buy_price(name, self.deal) * q})"
                       "  ·  drop on a member")
            else:
                one = names[0] if len(names) == 1 else f"{len(names)} items"
                msg = (f"moving {one}  ·  drop on another member, or on SELL "
                       f"(+{sum(economy.sell_price(n, self.deal) for n in names)})")
            text(screen, msg + "  ·  click outside to cancel", f.body, ACCENT,
                 (MARGIN, MARGIN + 30))
        else:
            text(screen, f"{len(self.shoppers)} shopping  ·  {self._deal_note()}",
                 f.body, INK_DIM, (MARGIN, MARGIN + 30))

        top = MARGIN + 62
        self._draw_tabs(screen, pygame.Rect(MARGIN, top, STOCK_W, 28))
        body_top = top + 28 + SP2
        stock = pygame.Rect(MARGIN, body_top, STOCK_W,
                            screen.get_height() - body_top - 72)
        self._draw_stock(screen, stock)
        self._draw_shoppers(screen, pygame.Rect(stock.right + MARGIN, body_top,
                                                screen.get_width() - stock.right - 2 * MARGIN,
                                                stock.h))
        self._draw_footer(screen)

        if self._dragging and names:
            gx, gy = self.mouse
            if self._buying:
                q = self._buy_qty(names[0])
                label = names[0] if q == 1 else f"{names[0]} ×{q}"
            else:
                label = names[0] if len(names) == 1 else f"{len(names)} items"
            gr = pygame.Rect(gx + 12, gy + 6, f.body_sm.size(label)[0] + 2 * SP2, 20)
            panel(screen, gr, fill=ACCENT, border=ACCENT_INK, width=1, radius=4)
            text(screen, label, f.body_sm, ACCENT_INK, gr.center, center=True)

        self.draw_sheet_modal(screen, f)

    # ------------------------------------------------------------------ #
    def _draw_tabs(self, screen, rect):
        f = self.fonts
        cats = economy.market_categories()
        gap = SP1
        w = (rect.w - (len(cats) - 1) * gap) // len(cats)
        for i, (label, key, _names) in enumerate(cats):
            r = pygame.Rect(rect.x + i * (w + gap), rect.y, w, rect.h)
            active = self.tab == key
            hov = r.collidepoint(self.mouse)
            panel(screen, r, fill=SURFACE_3 if (active or hov) else SURFACE_1,
                  border=ACCENT if active else LINE_SOFT, width=2 if active else 1,
                  radius=RADIUS)
            text(screen, label, f.label, ACCENT if active else INK_DIM,
                 r.center, center=True)
            self.tab_hits.append((r, key))

    def _draw_stock(self, screen, rect):
        f = self.fonts
        panel(screen, rect, fill=SURFACE_2, border=LINE_SOFT, radius=RADIUS)
        x, w = rect.x + SP3, rect.w - 2 * SP3
        names = next((c[2] for c in economy.market_categories() if c[1] == self.tab), [])
        kit = self.tab == "kit"

        wt_x = rect.right - SP3                       # weight column: right edge
        price_x = wt_x - 62                           # price cluster: right edge
        tag_x = price_x - 44                          # kit tag: right edge

        y = section(screen, "FOR SALE", x, rect.y + SP3, w, f)
        text(screen, "ITEM", f.label, INK_FAINT, (x, y))
        if kit:
            text(screen, "QTY", f.label, INK_FAINT, (x + 152, y))
        text(screen, "PRICE", f.label, INK_FAINT, (price_x, y), right=True)
        text(screen, "WT", f.label, INK_FAINT, (wt_x, y), right=True)
        y += 17

        row_h = 30 if kit else 34
        for name in names:
            r = pygame.Rect(x, y, w, row_h)
            sel = ("stock", name) in self.sel
            hov = not self.sel and r.collidepoint(self.mouse)
            base = economy.buy_price(name)
            price = economy.buy_price(name, self.deal)
            stock = self._stock_of(name)
            out = stock is not None and stock <= 0
            afford = self.purse >= price and not out
            fits = any(self._fits(m, name) for m in self.shoppers)
            panel(screen, r, fill=ACCENT if sel else SURFACE_3 if hov else SURFACE_1,
                  border=ACCENT if sel else LINE_SOFT, width=1, radius=4)
            ink = ACCENT_INK if sel else INK if afford else INK_FAINT
            faint = ACCENT_INK if sel else INK_FAINT

            spec = "" if kit else self._stock_spec(name)
            name_w = 138 if kit else 148
            text(screen, ellipsize(name, f.body_sm, name_w), f.body_sm, ink,
                 (r.x + SP2, r.y + 4 if spec else r.centery - 7))
            if spec:
                text(screen, spec, f.mono_sm, faint, (r.x + SP2, r.y + 18))
            if kit:
                self._draw_stepper(screen, name, r)
                tag = self._kit_tag(name)
                if tag:
                    text(screen, tag, f.label, ACCENT_INK if sel else INFO,
                         (tag_x, r.centery - 5), right=True)
            if stock is not None:
                stock_label = "OUT OF STOCK" if out else f"{stock} in stock"
                text(screen, stock_label, f.label, ACCENT_INK if sel else DANGER if out else WARN,
                     (tag_x, r.centery + 5), right=True)

            wt = kg(data.item_weight(name))
            text(screen, wt, f.mono_sm,
                 ACCENT_INK if sel else INK_DIM if fits else DANGER,
                 (wt_x, r.centery - 5), right=True)
            prect = text(screen, str(price), f.mono,
                         ACCENT_INK if sel else INK if afford else INK_FAINT,
                         (price_x, r.centery - 7), right=True)
            if base != price:
                br = text(screen, str(base), f.mono_sm, faint,
                          (prect.x - SP2, r.centery - 5), right=True)
                pygame.draw.line(screen, faint, (br.x - 1, br.centery),
                                 (br.right + 1, br.centery), 1)

            self.stock_rows.append((r, name))
            y += row_h + SP1

    def _stock_spec(self, name):
        """The one-line stat blurb under a weapon / armor row."""
        if name in data.WEAPONS:
            wp = data.WEAPONS[name]
            n, faces = wp["damage"]
            hands = "2h" if wp["hands"] >= 2 else "1h"
            rng = f"  ·  {wp['range'] * 3 // 2}m" if wp["range"] else ""
            return f"{n}d{faces}  ·  {hands}{rng}"
        if name in data.ARMOR:
            ar = data.ARMOR[name]
            cap = "no dex cap" if ar["max_dex"] is None else f"dex cap {ar['max_dex']}"
            spd = f"  ·  -{ar['speed']} spd" if ar["speed"] else ""
            return f"+{ar['ac']} AC  ·  {cap}{spd}"
        return ""

    @staticmethod
    def _kit_tag(name):
        if name in data.FOOD_ITEMS:
            return "FOOD"
        if name == data.FIRST_AID_ITEM:
            return "HEAL"
        if name == data.AMMO_ITEM:
            return "AMMO"
        if name == data.TORCH_ITEM or name in data.LIGHT_SOURCES:
            return "LIGHT"
        return ""

    def _draw_stepper(self, screen, name, row):
        f = self.fonts
        q = self._buy_qty(name)
        sel = ("stock", name) in self.sel
        bw, bh = 16, 18
        cy = row.centery
        minus = pygame.Rect(row.x + 150, cy - bh // 2, bw, bh)
        plus = pygame.Rect(minus.right + 28, cy - bh // 2, bw, bh)
        for r, glyph, delta in ((minus, "-", -1), (plus, "+", +1)):
            hov = r.collidepoint(self.mouse)
            panel(screen, r, fill=SURFACE_3 if hov else SURFACE_1,
                  border=ACCENT if hov else LINE_SOFT, width=1, radius=3)
            text(screen, glyph, f.body_bd, ACCENT if hov else INK_DIM, r.center, center=True)
            self.qty_hits.append((r, name, delta))
        text(screen, str(q), f.mono, ACCENT if sel else INK,
             ((minus.right + plus.x) // 2, cy - 1), center=True)

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
        add = (sum(data.item_weight(n) for n in names) if not self._buying
               else data.item_weight(names[0]) * self._buy_qty(names[0]))
        take_ok = bool(names) and m.load + add <= m.carry_max
        owns_sel = any(p[0] is m for p in self.sel if p[0] != "stock")
        hov = rect.collidepoint(self.mouse)
        panel(screen, rect, fill=SURFACE_2,
              border=OK if (take_ok and hov and not owns_sel) else
              DANGER if (names and hov and not take_ok) else LINE_SOFT,
              width=2 if hov else 1, radius=RADIUS)

        badge = self.sheet_badge(screen, (rect.right - pad, rect.y + pad), f)
        self.info_hits.append((badge, m))

        tok = (rect.x + pad + 12, rect.y + pad + 12)
        token_badge(screen, tok, m, f)
        text(screen, ellipsize(m.name, f.card_name, badge.x - (tok[0] + 24) - SP1),
             f.card_name, INK, (tok[0] + 24, rect.y + pad))
        text(screen, f"{m.race['name']}  ·  {m.occupation['name']}", f.body_sm,
             INK_DIM, (tok[0] + 24, rect.y + pad + 20))

        y = rect.y + pad + 48
        over_norm = m.encumbered
        over_max = m.load > m.carry_max
        ccol = DANGER if over_max else WARN if over_norm else OK
        carrier = f"  (carrier +{m.carry_relief:g})" if m.carry_relief else ""
        text(screen, f"Load {kg(m.load)} / {kg(m.carry_normal)}{carrier}", f.mono_sm,
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

        # Identical items stack into one row (×N) -- shift/ctrl-click grabs the
        # whole stack. What does not fit in the card scrolls with the wheel.
        y = section(screen, "PACK", rect.x + pad, y + SP1, rect.w - 2 * pad, f)
        stacks = self._stacks(m._base_inventory)
        if not stacks:
            text(screen, "(empty)", f.body_sm, INK_FAINT, (rect.x + pad, y + 2))

        row_h = 24 + SP1
        max_bottom = rect.bottom - 26                 # leave room for the COPPER label
        pack_area = pygame.Rect(rect.x + pad, y, rect.w - 2 * pad, max(0, max_bottom - y))
        self._pack_areas.append((pack_area, m))
        visible_n = max(1, (max_bottom - y) // row_h)
        scroll = max(0, min(self._pack_scroll.get(id(m), 0),
                            max(0, len(stacks) - visible_n)))
        self._pack_scroll[id(m)] = scroll

        if scroll:
            text(screen, f"^ {scroll} more above", f.label, INK_FAINT, (rect.x + pad, y + 2))
            y += 14
        shown = stacks[scroll:scroll + visible_n]
        for name, idxs in shown:
            idx, count = idxs[-1], len(idxs)          # items in a stack are interchangeable
            r = pygame.Rect(rect.x + pad, y, rect.w - 2 * pad, 24)
            self._draw_item_row(screen, r, m, idx, name, count=count)
            y += row_h
        more_below = len(stacks) - scroll - len(shown)
        if more_below > 0:
            text(screen, f"v {more_below} more below", f.label, INK_FAINT,
                 (rect.x + pad, y + 2))
            y += 14

        tracked(screen, "COPPER (COMMON)", f.label, INFO, (rect.x + pad, rect.bottom - 22))

    def _draw_item_row(self, screen, r, member, loc, name, tag="", count=1):
        f = self.fonts
        sel = (member, loc) in self.sel
        hov = not self.sel and r.collidepoint(self.mouse)
        panel(screen, r, fill=ACCENT if sel else SURFACE_3 if hov else SURFACE_1,
              border=ACCENT if sel else LINE_SOFT, width=1, radius=4)
        ink = ACCENT_INK if sel else INK
        label = name if count == 1 else f"{name}  ×{count}"
        text(screen, label, f.body_sm, ink, (r.x + SP2, r.y + 5))
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
