"""The bank: the guild's strongbox, rented from the Bankers.

The guild owns nothing as a body except this -- a chest at the bank in the City,
rented from the Bankers for a flat fee (`economy.BANK_CHEST_PRICE`) and holding
`guild.bank.capacity` kg. This screen rents the chest and moves gear between it
and the visiting party's packs (the mechanics live in `stash_screen.StashScreen`)
-- and lets a member equip straight out of either side: the hand/armor slots are
drop zones here exactly like on the gear screen, not a separate trip. The Bankers
also sell the City house from here (`city_property_screen.py` is where it's used).

It is also the only place Gold Coins are made or melted: a coin stack's menu, on a
member's pack or in the chest, opens a quantity picker in gold units
(`economy.buy_gold` / `sell_gold`, `economy.GOLD_FEE` per coin each way).
"""

import pygame

from . import economy, items
from .constants import fmt_money
from .stash_screen import StashScreen
from .ui import loadout_panel
from .ui.tokens import T


class BankScreen(StashScreen):
    OWNER = "bank"
    TITLE = "The Bank"
    SUBTITLE = "the Bankers rent one strongbox  ·  coin stacks turn into gold here, for a fee"
    LABEL = "the strongbox"
    LEAVE_LABEL = "leave the bank"
    CLOSED_NOTICE = "rent a strongbox first."
    WHERE = "in the chest"
    CAN_DISTRIBUTE = True

    exchange = None              # {"holder","mode","amount","max"} while picking gold to mint or melt

    def tutorial_key(self):
        return "bank"

    def tutorial_badge_rect(self, size):
        W, H = size
        return pygame.Rect(W - T.S * 3 - 28, T.S * 2, 28, 28)

    def _stash(self):
        return self.guild.bank

    def _open(self):
        return self.guild.bank.open

    def _services(self):
        g = self.guild
        services = []
        if not g.house.owned and not g.house.squatting and g.bankers_debt <= 0:
            rep_ok = g.reputation.get("bankers", 0) >= economy.CITY_PROPERTY_REP_GATE
            can_buy = rep_ok and not g.bankers_services_blocked and self.purse >= economy.CITY_PROPERTY_PRICE
            sub = (f"{fmt_money(economy.CITY_PROPERTY_PRICE)}  ·  needs {economy.CITY_PROPERTY_REP_GATE} "
                  "standing with the Bankers")
            services.append(("buy_property", "BUY THE HOUSE", sub, can_buy))
        if not g.bank.open:
            can_rent = self.purse >= economy.BANK_CHEST_PRICE
            services.append(("rent", "RENT A STRONGBOX",
                            f"{fmt_money(economy.BANK_CHEST_PRICE)}  ·  {economy.BANK_CHEST_CAPACITY} kg held in the City",
                            can_rent))
        return services

    def _run_service(self, key):
        if key == "rent":
            if self.purse < economy.BANK_CHEST_PRICE:
                self.notice = (f"the strongbox costs {fmt_money(economy.BANK_CHEST_PRICE)} -- "
                               f"the party has {fmt_money(self.purse)}.")
                return
            self.purse -= economy.BANK_CHEST_PRICE
            self.guild.rent_bank_chest()
            self.notice = (f"rented a strongbox -- {self.guild.bank.capacity} kg of "
                           "storage at the bank.")
        elif key == "buy_property":
            if self.purse < economy.CITY_PROPERTY_PRICE:
                self.notice = (f"the Bankers want {fmt_money(economy.CITY_PROPERTY_PRICE)} for "
                               f"the house -- the party has {fmt_money(self.purse)}.")
                return
            self.purse -= economy.CITY_PROPERTY_PRICE
            self.guild.buy_city_property()
            self.notice = "bought a house in the City -- the Bankers' tax starts now."

    # ------------------------------------------------------------------ #
    # the gold exchange                                                  #
    # ------------------------------------------------------------------ #
    def _holder_of(self, owner):
        return self._stash() if owner == self.OWNER else owner

    def _menu_rows(self, picks):
        rows = super()._menu_rows(picks)
        if len(picks) != 1 or not rows:
            return rows
        holder = self._holder_of(picks[0][0])
        name = self._item_at(*picks[0])
        if name == items.COIN_ITEM and economy.max_gold_buyable(holder):
            rows.insert(0, ("buy_gold", "mint gold coins", holder))
        elif name == items.GOLD_ITEM and economy.max_gold_sellable(holder):
            rows.insert(0, ("sell_gold", "melt gold coins", holder))
        return rows

    def _menu_run(self, picks, kind, arg):
        if kind not in ("buy_gold", "sell_gold"):
            super()._menu_run(picks, kind, arg)
            return
        buy = kind == "buy_gold"
        most = economy.max_gold_buyable(arg) if buy else economy.max_gold_sellable(arg)
        self.selected, self._sel_qty = [], {}
        self.exchange = {"holder": arg, "mode": kind, "amount": 1, "max": most}

    def _exchange_click(self, px):
        p = self.exchange
        if not p.get("rect") or not p["rect"].collidepoint(px):
            self.exchange = None
            return
        for r, key in p["hits"]:
            if not r.collidepoint(px):
                continue
            if key == "minus":
                p["amount"] = max(1, p["amount"] - 1)
            elif key == "plus":
                p["amount"] = min(p["max"], p["amount"] + 1)
            else:
                n = p["amount"]
                if p["mode"] == "buy_gold":
                    economy.buy_gold(p["holder"], n)
                    self.notice = f"minted {n} gold coins for {fmt_money(economy.gold_price(n))}."
                else:
                    economy.sell_gold(p["holder"], n)
                    self.notice = f"melted {n} gold coins into {fmt_money(economy.gold_payout(n))}."
                if hasattr(p["holder"], "_derive_combat"):
                    p["holder"]._derive_combat()
                self.exchange = None
            return

    def handle_event(self, event):
        if self.exchange is not None and event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self._exchange_click(event.pos)
            else:
                self.exchange = None
            return
        super().handle_event(event)

    def handle_escape(self):
        if self.exchange is not None:
            self.exchange = None
            return True
        return super().handle_escape()

    def _draw_menu(self, screen):
        super()._draw_menu(screen)
        p = self.exchange
        if p is None:
            return
        W, H = screen.get_size()
        n = p["amount"]
        buy = p["mode"] == "buy_gold"
        confirm = (f"PAY {fmt_money(economy.gold_price(n))}" if buy
                   else f"RECEIVE {fmt_money(economy.gold_payout(n))}")
        title = "mint gold coins" if buy else "melt gold coins"
        res = loadout_panel.quantity_prompt(screen, self._ui_fonts(), (W // 2, H // 2),
                                            title, n, p["max"], confirm, self.mouse)
        p["rect"], p["hits"] = res["rect"], res["hits"]

    def _hovering(self):
        if self.exchange is not None:
            return any(r.collidepoint(self.mouse) for r, _ in self.exchange.get("hits", ()))
        return super()._hovering()
