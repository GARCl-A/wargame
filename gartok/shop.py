"""A shop's own state: the till and the finite shelf of one node that offers `shop`.

The guild keeps one per node (`Guild.shops`, made on first use by `Guild.shop`),
so each place has its own cash and its own count of the scarce items
(`economy.STOCK`); everything else restocks freely. `Guild._daily_upkeep` refills
the till of every node whose `functions` include "shop" (`refill`).
"""

from . import economy


class Shop:
    def __init__(self, cash=economy.MARKET_CASH_START, stock=None):
        self.cash = cash
        self.stock = dict(economy.STOCK) if stock is None else dict(stock)

    def move_cash(self, delta):
        self.cash = max(0, self.cash + delta)

    def refill(self):
        self.cash = economy.regen_market_cash(self.cash)

    def to_dict(self):
        return {"cash": self.cash, "stock": dict(self.stock)}

    @classmethod
    def from_dict(cls, d):
        return cls(d["cash"], d["stock"])
