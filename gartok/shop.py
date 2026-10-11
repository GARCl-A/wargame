"""A shop's own state: the till and the finite shelf of one node that offers `shop`.

The guild keeps one per node (`Guild.shops`, made on first use by `Guild.shop`),
so each place has its own cash and its own count of every item on its shelf
(`economy.SHELVES`). `Guild._daily_upkeep` refills the till and walks each count
back toward its target (`refill`).
"""

from . import economy


class Shop:
    def __init__(self, cash=economy.MARKET_CASH_START, stock=None, node_id=None, progress=None):
        self.targets = economy.targets_of(node_id)
        self.stock = {name: target for name, (target, _rate) in self.targets.items()}
        self.stock.update(stock or {})
        self.progress = dict(progress or {})    # the fraction of a unit a slow item has earned so far
        self.cash = cash

    def move_cash(self, delta):
        self.cash = max(0, self.cash + delta)

    def strays(self):
        """Items on the shelf only because the player sold them here, with a unit left."""
        return [n for n, c in self.stock.items() if n not in self.targets and c > 0]

    def add(self, name, qty):
        self.stock[name] = self.stock.get(name, 0) + qty

    def refill(self):
        self.cash = economy.regen_market_cash(self.cash)
        for name, (target, rate) in self.targets.items():
            have = self.stock.get(name, target)
            if have == target or not rate:
                self.progress.pop(name, None)
                continue
            earned = self.progress.get(name, 0) + rate
            step = int(earned + 1e-9)
            self.progress[name] = earned - step
            if step:
                self.stock[name] = min(target, have + step) if have < target else max(target, have - step)

    def to_dict(self):
        return {"cash": self.cash, "stock": dict(self.stock), "progress": dict(self.progress)}

    @classmethod
    def from_dict(cls, d, node_id=None):
        return cls(d["cash"], d["stock"], node_id, d.get("progress"))
