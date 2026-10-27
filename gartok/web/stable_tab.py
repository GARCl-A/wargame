"""The Farm's STABLES and the Carpenter's WAGONS in the browser: on leather what the band keeps (each
animal with its tack and job, each wagon with its cargo and what pulls it) and sells back; on paper what
is for sale.

The rules are pygame's own (`StablesScreen`, `WagonYardScreen`), borrowed as `medic_tab` borrows
`MedicScreen`'s: the purse, the herd limit, the tack and the resale stay one source.
"""

from .. import animals, artwork, data, items, wagon
from ..stables_screen import StablesScreen, WagonYardScreen, _resale
from .session import asset_url

WAGON_GLYPH = "item/old-wagon"


def _face(species, uid=None):
    return asset_url(artwork.portrait_path(species, int(uid[:8], 16) if uid else 0))


class StableTab:
    wealth = StablesScreen.wealth
    _keeper = StablesScreen._keeper
    _pay = StablesScreen._pay
    _receive = StablesScreen._receive
    _buy_animal = StablesScreen._buy_animal
    _fit = StablesScreen._fit
    _sell_animal = StablesScreen._sell_animal
    hub_cards = StablesScreen.hub_cards

    def __init__(self, guild, group, node):
        self.guild, self.group, self.node = guild, group, node
        self.notice = None

    def _animal(self, uid):
        a = next((a for a in self.group.herd if a.uid == uid), None)
        if a is None:
            raise ValueError("no such animal in the herd")
        return a

    def buy(self, species):
        if species not in data.LIVESTOCK:
            raise ValueError(f"no {species!r} for sale")
        self._buy_animal(species)

    def fit(self, uid, tack):
        if tack not in (animals.HARNESS, animals.PACK_SADDLE):
            raise ValueError(f"no tack {tack!r}")
        a = self._animal(uid)
        if a.tack:
            raise ValueError(f"the {a.species} already wears a {a.tack}")
        self._fit(a, tack)

    def sell(self, uid):
        self._sell_animal(self._animal(uid))

    def _offer(self, species):
        a = animals.Animal(species)
        fits = self.group.can_take(a)
        return {"name": species, "portrait": _face(species), "price": a.price,
                "sub": f"carries {a.back_load:g} kg · draws {a.draw:g} kg · speed {a.speed:g} m",
                "can": fits and self.wealth >= a.price, "why": None if fits else "the herd is full"}

    def _kept(self, a):
        pulled = self.group.pulling(a)
        job = (f"pulls the {pulled.kind.lower()}" if pulled else "unhitched" if a.role == "draft"
               else "carries cargo" if a.role == "pack" else "no tack")
        price = {t: items.get(t).price for t in (animals.HARNESS, animals.PACK_SADDLE)}
        return {"uid": a.uid, "name": a.species, "portrait": _face(a.species, a.uid), "tack": a.tack, "job": job,
                "sub": f"speed {a.speed:g} m · HP {a.hp} / {a.hp_max}" + (f" · {a.stash.load:g} kg aboard" if a.stash.items else ""),
                "unfed": a.unfed_days, "loaded": bool(a.stash.items), "resale": _resale(a.price),
                "fits": [] if a.tack else [{"tack": t, "price": p, "can": self.wealth >= p} for t, p in price.items()]}

    def state(self):
        g = self.group
        notice, self.notice = self.notice, None
        return {"cards": self.hub_cards(), "purse": self.wealth, "keeper": self._keeper.name,
                "load": g.herd_load, "capacity": g.herd_capacity, "full": g.herd_load >= g.herd_capacity,
                "offers": [self._offer(s) for s in data.LIVESTOCK], "herd": [self._kept(a) for a in g.herd],
                "notice": notice}


class WagonTab(StableTab):
    _buy_wagon = WagonYardScreen._buy_wagon
    _sell_wagon = WagonYardScreen._sell_wagon
    _wagon_label = WagonYardScreen._wagon_label
    hub_cards = WagonYardScreen.hub_cards

    def buy(self, kind):
        if kind not in wagon.VEHICLES:
            raise ValueError(f"no {kind!r} for sale")
        self._buy_wagon(kind)

    def sell(self, uid):
        w = next((w for w in self.group.wagons if w.uid == uid), None)
        if w is None:
            raise ValueError("no such wagon")
        self._sell_wagon(w)

    def _offer(self, v):
        return {"name": v.name, "glyph": WAGON_GLYPH, "price": v.price, "can": self.wealth >= v.price,
                "sub": f"holds {v.capacity} kg · {v.slots} animal{'s' if v.slots != 1 else ''} to pull"}

    def _kept(self, w):
        riders = f" · {w.passenger_weight:g} kg of riders" if w.passengers else ""
        return {"uid": w.uid, "name": self._wagon_label(w), "glyph": WAGON_GLYPH,
                "pulled": [a.species for a in w.draft], "broken": w.broken,
                "cargo": round(w.stash.load, 2), "capacity": w.capacity, "budget": w.budget,
                "sub": f"HP {w.hp} / {w.hp_max} · speed {f'{w.speed:g} m' if w.speed else '--'} · "
                       f"{w.rations} meals aboard{riders}",
                "loaded": bool(w.stash.items), "resale": _resale(w.price)}

    def state(self):
        notice, self.notice = self.notice, None
        return {"cards": self.hub_cards(), "purse": self.wealth,
                "offers": [self._offer(v) for v in wagon.VEHICLES.values()],
                "wagons": [self._kept(w) for w in self.group.wagons], "notice": notice}
