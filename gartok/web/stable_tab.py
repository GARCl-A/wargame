"""The Farm's STABLES and the Carpenter's WAGONS in the browser: on leather what the band keeps (each
animal with its tack and job, each wagon with its cargo and what pulls it) and sells back; on paper what
is for sale.

The rules are `stables`' (`Stables`, `WagonYard`), which pygame's tabs read too: the purse, the herd limit,
the tack and the resale.
"""

from .. import animals, art_files, data, i18n, items, wagon
from ..stables import Stables, WagonYard, resale
from .session import asset_url

WAGON_GLYPH = "item/old-wagon"


def _face(species, uid=None):
    return asset_url(art_files.portrait_path(species, int(uid[:8], 16) if uid else 0))


class StableTab(Stables):
    def __init__(self, guild, group, node):
        super().__init__(guild, group)
        self.node = node

    def _animal(self, uid):
        a = next((a for a in self.group.herd if a.uid == uid), None)
        if a is None:
            raise ValueError(i18n.t("stable_tab.no_such_animal_in_herd"))
        return a

    def buy(self, species):
        if species not in data.LIVESTOCK:
            raise ValueError(i18n.t("stable_tab.no_for_sale", species=repr(species)))
        self._buy_animal(species)

    def fit(self, uid, tack):
        if tack not in (animals.HARNESS, animals.PACK_SADDLE):
            raise ValueError(i18n.t("stable_tab.no_tack", tack=repr(tack)))
        a = self._animal(uid)
        if a.tack:
            raise ValueError(i18n.t("stable_tab.already_wears", species=a.ref(), tack=i18n.Ref("item", a.tack)))
        self._fit(a, tack)

    def sell(self, uid):
        self._sell_animal(self._animal(uid))

    def _offer(self, species):
        a = animals.Animal(species)
        fits = self.group.can_take(a)
        return {"name": species, "portrait": _face(species), "price": a.price,
                "sub": i18n.t("stable_tab.carries_kg_draws_kg_speed", back_load=a.back_load, draw=a.draw, speed=a.speed),
                "can": fits and self.wealth >= a.price, "why": None if fits else i18n.t("stable_tab.herd_is_full")}

    def _kept(self, a):
        pulled = self.group.pulling(a)
        job = (i18n.t("stable_tab.pulls", lower=pulled.ref(lower=True)) if pulled else i18n.t("animals.unhitched") if a.role == "draft"
               else i18n.t("stable_tab.carries_cargo") if a.role == "pack" else i18n.t("stable_tab.no_tack_2"))
        price = {t: items.get(t).price for t in (animals.HARNESS, animals.PACK_SADDLE)}
        return {"uid": a.uid, "name": a.species, "portrait": _face(a.species, a.uid), "tack": a.tack, "job": job,
                "sub": i18n.t("stable_tab.speed_m_hp", speed=a.speed, hp=a.hp, hp_max=a.hp_max) + (i18n.t("stable_tab.kg_aboard", load=a.stash.load) if a.stash.items else ""),
                "unfed": a.unfed_days, "loaded": bool(a.stash.items), "resale": resale(a.price),
                "fits": [] if a.tack else [{"tack": t, "price": p, "can": self.wealth >= p} for t, p in price.items()]}

    def state(self):
        g = self.group
        notice, self.notice = self.notice, None
        return {"cards": self.hub_cards(), "purse": self.wealth, "keeper": self._keeper.name,
                "load": g.herd_load, "capacity": g.herd_capacity, "full": g.herd_load >= g.herd_capacity,
                "offers": [self._offer(s) for s in data.LIVESTOCK], "herd": [self._kept(a) for a in g.herd],
                "notice": notice}


class WagonTab(StableTab, WagonYard):

    def buy(self, kind):
        if kind not in wagon.VEHICLES:
            raise ValueError(i18n.t("stable_tab.no_for_sale_2", kind=repr(kind)))
        self._buy_wagon(kind)

    def sell(self, uid):
        w = next((w for w in self.group.wagons if w.uid == uid), None)
        if w is None:
            raise ValueError(i18n.t("stable_tab.no_such_wagon"))
        self._sell_wagon(w)

    def _offer(self, v):
        return {"name": v.name, "glyph": WAGON_GLYPH, "price": v.price, "can": self.wealth >= v.price,
                "sub": i18n.plural("stable_tab.holds", v.slots, capacity=v.capacity)}

    def _kept(self, w):
        riders = i18n.t("stable_tab.kg_of_riders", passenger_weight=w.passenger_weight) if w.passengers else ""
        return {"uid": w.uid, "name": self._wagon_label(w), "glyph": WAGON_GLYPH,
                "pulled": [a.species for a in w.draft], "broken": w.broken,
                "cargo": round(w.stash.load, 2), "capacity": w.capacity, "budget": w.budget,
                "sub": i18n.t("stable_tab.hp_speed_meals_aboard", hp=w.hp, hp_max=w.hp_max, value=f'{w.speed:g} m' if w.speed else '--', rations=w.rations, riders=riders),
                "loaded": bool(w.stash.items), "resale": resale(w.price)}

    def state(self):
        notice, self.notice = self.notice, None
        return {"cards": self.hub_cards(), "purse": self.wealth,
                "offers": [self._offer(v) for v in wagon.VEHICLES.values()],
                "wagons": [self._kept(w) for w in self.group.wagons], "notice": notice}
