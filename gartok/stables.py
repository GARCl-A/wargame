"""The Stables (the Farm) and the Carpenter's wagon yard, with no window: the animals and the tack that
decides what each one does, and the wagons.

Nothing is stored here -- the wagons and the animals live on the `Group` and travel with it (see
`wagon.py`, `animals.py`). The party pays out of its pooled coin, richest first; selling back returns
`economy.SELL_FACTOR` of the price to the group's leader. `StablesScreen` / `WagonYardScreen` are the
pygame windows over them and `web/stable_tab.py` the browser's.
"""

from . import animals, economy, items, recorder, wagon
from .constants import fmt_money


def resale(price):
    return max(1, int(price * economy.SELL_FACTOR))


def tack_price(name):
    return items.get(name).price


class Stables:
    def __init__(self, guild, group):
        self.guild, self.group = guild, group
        self.notice = None

    def hub_cards(self):
        g = self.group
        return [{"label": "herd", "value": f"{len(g.herd)} / {g.herd_capacity}"},
                {"label": "party purse", "value": fmt_money(self.wealth), "tone": "money"}]

    @property
    def wealth(self):
        return sum(m.money for m in (*self.group.members, *getattr(self.group, "stores", ())))

    @property
    def _keeper(self):
        return self.group.leader or self.group.members[0]

    def _pay(self, price, what):
        if self.wealth < price:
            self.notice = f"{what} costs {fmt_money(price)} -- the party has {fmt_money(self.wealth)}."
            return False
        economy.charge_richest_first((*self.group.members, *getattr(self.group, "stores", ())), price)
        return True

    def _receive(self, amount):
        self._keeper.money += amount

    def _buy_animal(self, species):
        animal = animals.Animal(species)
        if not self.group.can_take(animal):
            self.notice = f"{self._keeper.name} can control a herd of {self.group.herd_capacity} at most."
        elif self._pay(animal.price, f"a {species}"):
            self.group.herd.append(animal)
            recorder.emit("animal", what="buy", species=species, price=animal.price)
            self.notice = f"a {species} joins the group."

    def _fit(self, animal, tack):
        if animal.tack is None and self._pay(tack_price(tack), f"a {tack}"):
            animal.give_to_tack(tack)
            self.group.hitch_idle()
            self.notice = f"the {animal.species} now wears a {tack}."

    def _sell_animal(self, animal):
        if animal.stash.items:
            self.notice = f"unload the {animal.species} first."
            return
        if animal.tack:
            self._keeper.give_to_pack(animal.take_tack())
        self.group.herd.remove(animal)
        self._receive(resale(animal.price))
        recorder.emit("animal", what="sell", species=animal.species, price=resale(animal.price))
        self.notice = f"sold the {animal.species}."


class WagonYard(Stables):
    """The Carpenter's WAGONS: buy a cart or a carriage, sell an empty one back."""

    def hub_cards(self):
        return [{"label": "wagons", "value": str(len(self.group.wagons))},
                {"label": "party purse", "value": fmt_money(self.wealth), "tone": "money"}]

    def _buy_wagon(self, kind):
        if self._pay(wagon.VEHICLES[kind].price, f"a {kind.lower()}"):
            self.group.add_wagon(wagon.Wagon(kind))
            self.group.hitch_idle()
            self.notice = f"the {kind.lower()} is yours -- harness an animal to pull it."

    def _sell_wagon(self, sold):
        if sold.stash.items:
            self.notice = f"unload the {sold.kind.lower()} first."
            return
        self.group.remove_wagon(sold)
        self._receive(resale(sold.price))
        self.notice = f"sold the {sold.kind.lower()}."

    def _wagon_label(self, w):
        """"Cart" alone, "Cart 2" when the group keeps several."""
        same = [x for x in self.group.wagons if x.kind == w.kind]
        return w.kind if len(same) == 1 else f"{w.kind} {same.index(w) + 1}"
