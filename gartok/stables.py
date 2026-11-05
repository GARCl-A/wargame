"""The Stables (the Farm) and the Carpenter's wagon yard, with no window: the animals and the tack that
decides what each one does, and the wagons.

Nothing is stored here -- the wagons and the animals live on the `Group` and travel with it (see
`wagon.py`, `animals.py`). The party pays out of its pooled coin, richest first; selling back returns
`economy.SELL_FACTOR` of the price to the group's leader. `web/stable_tab.py` draws them.
"""

from . import animals, economy, i18n, items, recorder, wagon
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
        return [{"label": i18n.lab("herd"), "value": f"{len(g.herd)} / {g.herd_capacity}"},
                {"label": i18n.t("stables.party_purse"), "value": fmt_money(self.wealth), "tone": "money"}]

    @property
    def wealth(self):
        return sum(m.money for m in (*self.group.members, *getattr(self.group, "stores", ())))

    @property
    def _keeper(self):
        return self.group.leader or self.group.members[0]

    def _pay(self, price, what):
        if self.wealth < price:
            self.notice = i18n.t("stables.costs_party_has", what=what, cost=fmt_money(price), wealth=fmt_money(self.wealth))
            return False
        economy.charge_richest_first((*self.group.members, *getattr(self.group, "stores", ())), price)
        return True

    def _receive(self, amount):
        self._keeper.money += amount

    def _buy_animal(self, species):
        animal = animals.Animal(species)
        if not self.group.can_take(animal):
            self.notice = i18n.t("stables.can_control_herd_of_at", name=self._keeper.name, herd_capacity=self.group.herd_capacity)
        elif self._pay(animal.price, f"a {species}"):
            self.group.herd.append(animal)
            recorder.emit("animal", what="buy", species=species, price=animal.price)
            self.notice = i18n.t("stables.joins_group", species=animal.ref())

    def _fit(self, animal, tack):
        if animal.tack is None and self._pay(tack_price(tack), f"a {tack}"):
            animal.give_to_tack(tack)
            self.group.hitch_idle()
            self.notice = i18n.t("stables.now_wears", species=animal.ref(), tack=i18n.Ref("item", tack))

    def _sell_animal(self, animal):
        if animal.stash.items:
            self.notice = i18n.t("stables.unload_first", species=animal.ref())
            return
        if animal.tack:
            self._keeper.give_to_pack(animal.take_tack())
        self.group.herd.remove(animal)
        self._receive(resale(animal.price))
        recorder.emit("animal", what="sell", species=animal.species, price=resale(animal.price))
        self.notice = i18n.t("stables.sold", species=animal.ref())


class WagonYard(Stables):
    """The Carpenter's WAGONS: buy a cart or a carriage, sell an empty one back."""

    def hub_cards(self):
        return [{"label": i18n.lab("wagons"), "value": str(len(self.group.wagons))},
                {"label": i18n.t("stables.party_purse"), "value": fmt_money(self.wealth), "tone": "money"}]

    def _buy_wagon(self, kind):
        if self._pay(wagon.VEHICLES[kind].price, f"a {kind.lower()}"):
            self.group.add_wagon(wagon.Wagon(kind))
            self.group.hitch_idle()
            self.notice = i18n.t("stables.is_yours_harness_animal_to", lower=i18n.Ref("vehicle", kind, lower=True))

    def _sell_wagon(self, sold):
        if sold.stash.items:
            self.notice = i18n.t("stables.unload_first_2", lower=sold.ref(lower=True))
            return
        self.group.remove_wagon(sold)
        self._receive(resale(sold.price))
        self.notice = i18n.t("stables.sold_2", lower=sold.ref(lower=True))

    def _wagon_label(self, w):
        """"Cart" alone, "Cart 2" when the group keeps several."""
        same = [x for x in self.group.wagons if x.kind == w.kind]
        return w.name if len(same) == 1 else f"{w.name} {same.index(w) + 1}"
