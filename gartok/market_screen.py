"""Market: buy and sell gear for copper.

The shopping party pools its coin into one **common purse** for the visit (the
guild has no treasury) and the members' packs sit side by side, so you can shift
items and spend freely without per-character fiddling. On the way out the purse
is split back evenly among the shoppers.

Interaction (same as the guild screen): click an item to pick it up, then click
where it goes.
- a stock row  -> picked "to buy"; click a shopper to buy it into their pack
  (needs purse >= price and room under their carry max);
- a shopper's item -> click another shopper to hand it over, or the SELL bar to
  sell it back (at `economy.sell_price`, always a loss);
- click anywhere else to cancel.
"""

import pygame

from . import data, economy
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SURFACE_1,
                    SURFACE_2, SURFACE_3, WARN, WIN_H, WIN_W, panel, section,
                    token_badge, text, tracked)

STOCK_W = 300


def _kg(w):
    return f"{w:g} kg"


class MarketScreen(Screen):
    def __init__(self, fonts, guild, shoppers, node, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.shoppers = shoppers
        self.node = node
        self.on_done = on_done
        self.purse = sum(m.gold for m in shoppers)   # pooled for the visit
        # haggling: shared language + charisma + alignment bend every price
        self.deal = economy.market_deal(shoppers, getattr(node, "language", None),
                                     getattr(node, "alignment", None))
        self.sel = None                       # ("stock", name) | (member, "hand"|"offhand"|idx)
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

    def _selected_name(self):
        if self.sel is None:
            return None
        if self.sel[0] == "stock":
            return self.sel[1]
        return self._item_at(*self.sel)

    def _fits(self, member, name):
        return member.load + data.item_weight(name) <= member.carry_max

    def _deal_note(self):
        """One-line summary of how the party's haggling moved the prices."""
        lang = getattr(self.node, "language", None)
        if not lang:
            return f"revenda a {int(economy.SELL_FACTOR * 100)}% do preco"
        pct = round(self.deal * 100)
        speaks = any(lang in m.languages for m in self.shoppers)
        if not speaks:
            return f"ninguem fala {lang}: sem negociacao (revenda a {int(economy.SELL_FACTOR * 100)}%)"
        how = (f"desconto de {pct}%" if pct > 0
               else f"agio de {-pct}%" if pct < 0 else "sem margem")
        return f"vendedor fala {lang} · {self.node.alignment} · {how}"

    # ------------------------------------------------------------------ #
    def _click(self, px):
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "done":
                    self._checkout()
                elif key == "sell":
                    self._sell()
                return

        if self.sel is None:
            for rect, name in self.stock_rows:
                if rect.collidepoint(px):
                    self.sel = ("stock", name)
                    self.notice = None
                    return
            for rect, member, loc in self.item_rows:
                if rect.collidepoint(px):
                    self.sel = (member, loc)
                    self.notice = None
                    return
            return

        for rect, member in self.cards:
            if rect.collidepoint(px):
                self._drop_on(member)
                return
        self.sel = None                       # clicked nowhere useful: cancel

    # ------------------------------------------------------------------ #
    def _drop_on(self, member):
        name = self._selected_name()
        if name is None:
            self.sel = None
            return

        if self.sel[0] == "stock":
            price = economy.buy_price(name, self.deal)
            if self.purse < price:
                self.notice = f"Sem cobre para {name} ({price})."
                return
            if not self._fits(member, name):
                self.notice = f"{name} nao cabe na carga de {member.name}."
                return
            self.purse -= price
            member.give_to_pack(name)
            self.notice = f"{member.name} compra {name} por {price}."
            self.sel = None
            return

        src, loc = self.sel
        if src is member:                     # dropped back on the owner: cancel
            self.sel = None
            return
        if not self._fits(member, name):
            self.notice = f"{name} nao cabe na carga de {member.name}."
            return
        self._take(src, loc)
        member.give_to_pack(name)
        self.notice = f"{name}: {src.name} -> {member.name}."
        self.sel = None

    def _sell(self):
        if self.sel is None or self.sel[0] == "stock":
            return
        src, loc = self.sel
        name = self._item_at(src, loc)
        if name is None:
            self.sel = None
            return
        price = economy.sell_price(name, self.deal)
        self._take(src, loc)
        self.purse += price
        self.notice = f"{src.name} vende {name} por {price}."
        self.sel = None

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

        text(screen, "MERCADO", f.title, INK, (MARGIN, MARGIN - 2))
        text(screen, f"bolsa comum: {self.purse} cobre", f.body_bd, ACCENT,
             (WIN_W - MARGIN, MARGIN + 2), right=True)
        sel_name = self._selected_name()
        if sel_name is not None:
            buying = self.sel[0] == "stock"
            msg = (f"comprar {sel_name} ({economy.buy_price(sel_name, self.deal)})  ·  "
                   "clique num membro"
                   if buying else
                   f"movendo {sel_name}  ·  clique em outro membro, ou VENDER "
                   f"({economy.sell_price(sel_name, self.deal)})")
            text(screen, msg + "  ·  clique fora para cancelar", f.body, ACCENT,
                 (MARGIN, MARGIN + 30))
        else:
            text(screen, f"bolsa comum: {self.purse} cobre  ·  {len(self.shoppers)} "
                 f"comprando  ·  {self._deal_note()}",
                 f.body, INK_DIM, (MARGIN, MARGIN + 30))

        top = MARGIN + 64
        stock = pygame.Rect(MARGIN, top, STOCK_W, WIN_H - top - 72)
        self._draw_stock(screen, stock)
        self._draw_shoppers(screen, pygame.Rect(stock.right + MARGIN, top,
                                                WIN_W - stock.right - 2 * MARGIN,
                                                stock.h))
        self._draw_footer(screen)

    def _draw_stock(self, screen, rect):
        f = self.fonts
        panel(screen, rect, fill=SURFACE_2, border=LINE_SOFT, radius=RADIUS)
        x, w = rect.x + SP3, rect.w - 2 * SP3
        y = section(screen, "A VENDA", x, rect.y + SP3, w, f)
        for name in economy.MARKET_STOCK:
            r = pygame.Rect(x, y, w, 26)
            sel = self.sel == ("stock", name)
            hov = self.sel is None and r.collidepoint(self.mouse)
            price = economy.buy_price(name, self.deal)
            afford = self.purse >= price
            panel(screen, r, fill=ACCENT if sel else SURFACE_3 if hov else SURFACE_1,
                  border=ACCENT if sel else LINE_SOFT, width=1, radius=4)
            ink = ACCENT_INK if sel else INK if afford else INK_FAINT
            text(screen, name, f.body_sm, ink, (r.x + SP2, r.y + 6))
            text(screen, str(price), f.mono_sm,
                 ACCENT_INK if sel else INK_DIM if afford else INK_FAINT,
                 (r.right - SP2, r.y + 7), right=True)
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
        sel_name = self._selected_name()
        take_ok = sel_name is not None and self._fits(m, sel_name)
        owns_sel = self.sel is not None and self.sel[0] != "stock" and self.sel[0] is m
        hov = rect.collidepoint(self.mouse)
        panel(screen, rect, fill=SURFACE_2,
              border=OK if (take_ok and hov and not owns_sel) else
              DANGER if (sel_name and hov and not take_ok) else LINE_SOFT,
              width=2 if hov else 1, radius=RADIUS)

        tok = (rect.x + pad + 12, rect.y + pad + 12)
        token_badge(screen, tok, m.token, f)
        text(screen, m.name, f.card_name, INK, (tok[0] + 24, rect.y + pad))
        text(screen, f"{m.race['name']}  ·  {m.occupation['name']}", f.body_sm,
             INK_DIM, (tok[0] + 24, rect.y + pad + 20))

        y = rect.y + pad + 48
        over_norm = m.load > m.carry_normal
        over_max = m.load > m.carry_max
        ccol = DANGER if over_max else WARN if over_norm else OK
        text(screen, f"Carga {_kg(m.load)} / {_kg(m.carry_normal)}", f.mono_sm,
             ccol, (rect.x + pad, y))
        note = ("ACIMA DA CARGA ALTA  -2 FOR/DES, -1 desloc" if over_max
                else "sobrecarregado  -2 FOR/DES, -1 desloc" if over_norm else "")
        if note:
            y += 13
            text(screen, note, f.label, ccol, (rect.x + pad, y))
        y += 18

        for loc, label in (("hand", "arma"), ("offhand", "outra mao"), ("armor", "corpo")):
            held = self._item_at(m, loc)
            if not held:
                continue
            r = pygame.Rect(rect.x + pad, y, rect.w - 2 * pad, 24)
            self._draw_item_row(screen, r, m, loc, held, tag=label.upper())
            y += 24 + SP1

        y = section(screen, "MOCHILA", rect.x + pad, y + SP1, rect.w - 2 * pad, f)
        if not m._base_inventory:
            text(screen, "(vazia)", f.body_sm, INK_FAINT, (rect.x + pad, y + 2))
        for idx, item in enumerate(m._base_inventory):
            r = pygame.Rect(rect.x + pad, y, rect.w - 2 * pad, 24)
            self._draw_item_row(screen, r, m, idx, item)
            y += 24 + SP1

        tracked(screen, "COBRE (COMUM)", f.label, INFO, (rect.x + pad, rect.bottom - 22))

    def _draw_item_row(self, screen, r, member, loc, name, tag=""):
        f = self.fonts
        sel = self.sel == (member, loc)
        hov = self.sel is None and r.collidepoint(self.mouse)
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
        y = WIN_H - 52
        if self.notice:
            text(screen, self.notice, f.body_sm, INFO, (MARGIN, y - 22))

        sel_name = self._selected_name()
        can_sell = self.sel is not None and self.sel[0] != "stock" and sel_name
        if can_sell:
            sr = pygame.Rect(MARGIN, y, 240, 36)
            hov = sr.collidepoint(self.mouse)
            panel(screen, sr, fill=DANGER if hov else SURFACE_3, border=DANGER,
                  width=1, radius=RADIUS)
            text(screen, f"VENDER POR {economy.sell_price(sel_name, self.deal)}", f.body_bd,
                 ACCENT_INK if hov else DANGER, sr.center, center=True)
            self.buttons.append(("sell", sr))

        done = pygame.Rect(WIN_W - MARGIN - 240, y, 240, 36)
        hovd = done.collidepoint(self.mouse)
        panel(screen, done, fill=ACCENT if hovd else SURFACE_3, border=ACCENT,
              width=1, radius=RADIUS)
        text(screen, "SAIR DO MERCADO", f.body_bd, ACCENT_INK if hovd else ACCENT,
             done.center, center=True)
        self.buttons.append(("done", done))
