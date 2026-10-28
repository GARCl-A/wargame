"""Things the guild owns as a body: a weight-capped `Stash`, and the City house
built around one.

`Guild.bank` (the Bankers' strongbox) and `Guild.house` (the City property)
share the same storage, so a future base reuses `Stash` rather than growing
another copy of the item bookkeeping on `Guild`. `CityProperty` adds the part
that is specific to the house: ownership, the tax cycle, repossession and
squatting. Money and the guard stay with the caller (`Guild`, `campaign`).
`GarageDesk` is a garage's counter (the house's or the Claim's), with no window.
"""

import math

from . import animals, economy
from .constants import fmt_money
from .stash import Stash  # noqa: F401 -- re-exported


class Garage:
    """Where a holding keeps wagons and animals out of the group's hands. The house
    garage holds one wagon and one animal per tier, safe, nothing to roll. The Claim's
    is `unlimited`: it is open the moment its garrison is, and only safe while someone
    is there (`guild_claim.py`). Cargo stays in its wagon; the animals eat from the
    holding's food and the garaged wagons' cargo, and do not count against a group's
    `herd_capacity`."""

    def __init__(self, tier=0, wagons=None, herd=None, unlimited=False):
        self.tier = tier
        self.unlimited = unlimited
        self.wagons = list(wagons or [])
        self.herd = list(herd or [])

    @property
    def open(self):
        return self.unlimited or self.tier > 0

    @property
    def wagon_room(self):
        return math.inf if self.unlimited else self.tier - len(self.wagons)

    @property
    def animal_room(self):
        return math.inf if self.unlimited else self.tier - len(self.herd)

    @property
    def empty(self):
        return not self.wagons and not self.herd

    def food_stores(self):
        return [*(w.stash.items for w in self.wagons), *(a.stash.items for a in self.herd)]

    def feed(self, *packs):
        """One day's feeding: each animal's own load, then `packs` (lists of items), then
        the wagons' cargo. Returns the log lines."""
        def packs_for(animal):
            own = animal.stash.items
            return [own, *packs, *(w.stash.items for w in self.wagons)]

        return animals.feed_herd(self.herd, packs_for)

    def clear(self):
        self.tier = 0
        self.wagons, self.herd = [], []


class CityProperty:
    """The house the Bankers sell in the City, taxed on a cycle. A squatter
    keeps `owned` set -- the guild still holds the keys, illegally -- until the
    guard clears it (`abandon`)."""

    def __init__(self, owned=False, contents=None, tax_due_day=None,
                 missed_payments=0, squatting=False, oven=False, garage=None):
        self.owned = owned
        self.stash = Stash(economy.CITY_PROPERTY_CAPACITY, contents)
        self.tax_due_day = tax_due_day          # clock.day the next tax is due, or None
        self.missed_payments = missed_payments
        self.squatting = squatting              # illegal occupier, after refusing repossession
        self.oven = oven                        # bought from the Bankers: unlocks cooking at the house
        self.garage = garage or Garage()

    @property
    def repossession_due(self):
        return self.owned and self.missed_payments >= economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT

    def buy(self, today):
        """The caller collects the price first -- this flips ownership on and
        starts the tax clock."""
        self.owned = True
        self.missed_payments = 0
        self.tax_due_day = today + economy.CITY_PROPERTY_TAX_PERIOD_DAYS

    def repossess(self):
        """Hand the property back. Returns the missed rent now owed to the Bankers."""
        owed = self.missed_payments * economy.CITY_PROPERTY_TAX
        self.owned = False
        self.oven = False
        self.garage.clear()
        self.stash.items = []
        self.missed_payments = 0
        self.tax_due_day = None
        return owed

    def squat(self):
        self.squatting = True
        self.missed_payments = 0
        self.tax_due_day = None

    def abandon(self):
        """The property is simply gone (guild gave up, or the guard cleared it) -- no debt."""
        self.squatting = False
        self.owned = False
        self.oven = False
        self.garage.clear()
        self.stash.items = []


class GarageDesk:
    """A garage's counter with no window: park the band's wagons and animals, take them out, repair a wagon,
    and (at the house) add bays. The party pays out of its pooled coin, richest first, like the stables.
    The Claim's garage (`claim=True`) has no bays and no limit, and is only safe while a garrison stands
    there. pygame's `GarageScreen` and `web/garage_tab.py` are the windows over it."""

    def __init__(self, guild, group, claim=False, on_tick=None):
        self.guild, self.group, self.claim, self.on_tick = guild, group, claim, on_tick
        self.notice = None

    @property
    def garage(self):
        return self.guild.claim_garage if self.claim else self.guild.house.garage

    @property
    def wealth(self):
        return sum(m.money for m in (*self.group.members, *getattr(self.group, "stores", ())))

    def _act(self, key):
        """Run one of the garage's verbs, named `kind:index` as pygame's buttons name them."""
        g, garage, guild = self.group, self.garage, self.guild
        kind, _, arg = key.partition(":")
        if kind == "bay":
            if self.wealth < economy.GARAGE_PRICE:
                self.notice = f"a bay costs {fmt_money(economy.GARAGE_PRICE)} -- the party has {fmt_money(self.wealth)}."
                return
            economy.charge_richest_first((*g.members, *getattr(g, "stores", ())), economy.GARAGE_PRICE)
            guild.buy_garage_tier()
            self.notice = "a new bay: room for one more wagon and one more animal."
        elif kind in ("repair_garaged", "repair_group"):
            wagon = (garage.wagons if kind == "repair_garaged" else g.wagons)[int(arg)]
            ok, events, _ = guild.repair_wagon(g.members, wagon, self.on_tick)
            if ok and wagon in g.wagons:
                g.hitch_idle()
            self.notice = "  ".join(events)
        elif kind == "park_wagon":
            wagon = g.wagons[int(arg)]
            if guild.park_wagon(g, wagon, garage):
                self.notice = f"the {wagon.kind.lower()} is parked in the garage."
            else:
                self.notice = "every bay already holds a wagon."
        elif kind == "take_wagon":
            wagon = garage.wagons[int(arg)]
            if guild.take_wagon(g, wagon, garage):
                self.notice = f"the {wagon.kind.lower()} rejoins the group."
        elif kind == "park_animal":
            animal = g.herd[int(arg)]
            if guild.park_animal(g, animal, garage):
                self.notice = f"the {animal.species} is stabled in the garage."
            else:
                self.notice = "every bay already holds an animal."
        elif kind == "take_animal":
            animal = garage.herd[int(arg)]
            if guild.take_animal(g, animal, garage):
                self.notice = f"the {animal.species} rejoins the group."
            else:
                keeper = g.leader or g.members[0]
                self.notice = f"{keeper.name} can control a herd of {g.herd_capacity} at most."
