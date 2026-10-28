"""The City house's GARAGE in the browser, and the Wilds Claim's: on leather what is parked there (each wagon
with its HP and cargo, each animal with what it eats), on paper what the band keeps and can park, and the house's
bays and the price of the next one, or the Claim's risk with no garrison to watch it.

The rules are pygame's own `GarageScreen`, held headless as `jobs_tab` holds a board: a verb names a wagon
or an animal by its uid and the tab calls the screen's own click on its index, so the bays, the herd limit,
the pooled purse and the repair stay one source. The repair's hour runs through the `tick` the hub hands in.
"""

from .. import economy, wagon_watch
from .. import wagon as wagon_mod
from ..garage_screen import GarageScreen
from .stable_tab import WAGON_GLYPH, _face


class GarageTab:
    def __init__(self, guild, group, node, tick=None, claim=False):
        self.s = GarageScreen(None, guild, group, lambda: None, claim=claim, on_tick=tick)
        self.claim = claim
        self.guild, self.group, self.node = guild, group, node

    @property
    def garage(self):
        return self.s.garage

    def _index(self, where, uid):
        i = next((i for i, x in enumerate(where) if x.uid == uid), None)
        if i is None:
            raise ValueError("nothing by that id here")
        return i

    def bay(self):
        self.s._click("bay")

    def park(self, uid):
        g = self.group
        if any(w.uid == uid for w in g.wagons):
            self.s._click(f"park_wagon:{self._index(g.wagons, uid)}")
        else:
            self.s._click(f"park_animal:{self._index(g.herd, uid)}")

    def take(self, uid):
        garage = self.garage
        if any(w.uid == uid for w in garage.wagons):
            self.s._click(f"take_wagon:{self._index(garage.wagons, uid)}")
        else:
            self.s._click(f"take_animal:{self._index(garage.herd, uid)}")

    def repair(self, uid):
        garage, g = self.garage, self.group
        if any(w.uid == uid for w in garage.wagons):
            self.s._click(f"repair_garaged:{self._index(garage.wagons, uid)}")
        else:
            self.s._click(f"repair_group:{self._index(g.wagons, uid)}")

    def _wagon(self, w, parked):
        have = sum(u.count_of(wagon_mod.REPAIR_ITEM) for u in self.group.members)
        room = self.garage.wagon_room > 0
        return {"uid": w.uid, "name": w.kind, "glyph": WAGON_GLYPH, "parked": parked, "broken": w.broken,
                "sub": f"HP {w.hp} / {w.hp_max} · cargo {w.stash.load:g} kg",
                "can": True if parked else room, "why": None if parked or room else "every bay holds a wagon",
                "repair": {"cost": w.repair_cost, "item": wagon_mod.REPAIR_ITEM, "can": have >= w.repair_cost}
                if w.needs_repair else None}

    def _animal(self, a, parked):
        g = self.group
        if parked:
            can, why = g.can_take(a), None if g.can_take(a) else "the herd is full"
            fed_by = "the garrison's food" if self.claim else "the house stash"
            sub = f"unfed {a.unfed_days} day(s)" if a.unfed_days else f"eats from {fed_by}"
        else:
            can = self.garage.animal_room > 0
            why, sub = None if can else "every bay holds an animal", f"{a.tack or 'no tack'} · speed {a.speed:g} m"
        return {"uid": a.uid, "name": a.species, "portrait": _face(a.species, a.uid), "parked": parked,
                "unfed": a.unfed_days if parked else 0, "sub": sub, "can": can, "why": why, "repair": None}

    def hub_cards(self):
        garage = self.garage
        cards = [{"label": "party purse", "value": f"${self.s.wealth}", "tone": "money"}]
        if garage.open and not self.claim:
            cards.insert(0, {"label": "bays", "value": f"{garage.tier}"})
        return cards

    def state(self):
        s, garage, g = self.s, self.garage, self.group
        notice, s.notice = s.notice, None
        return {"cards": self.hub_cards(), "purse": s.wealth, "open": garage.open, "tier": garage.tier,
                "price": economy.GARAGE_PRICE, "can_bay": s.wealth >= economy.GARAGE_PRICE,
                "wagons": len(garage.wagons), "animals": len(garage.herd), "claim": self.claim,
                "watch": None if not self.claim or self.guild.claim_garrison() is not None
                else f"{wagon_watch.flight_chance(garage):.0%}",
                "parked": [*(self._wagon(w, True) for w in garage.wagons), *(self._animal(a, True) for a in garage.herd)],
                "kept": [*(self._wagon(w, False) for w in g.wagons), *(self._animal(a, False) for a in g.herd)],
                "notice": notice}
