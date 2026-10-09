"""Things the guild owns as a body: a weight-capped `Stash`, and the City house
built around one.

`Guild.bank` (the Bankers' strongbox) and `Guild.house` (the City property)
share the same storage, so a future base reuses `Stash` rather than growing
another copy of the item bookkeeping on `Guild`. `CityProperty` adds the part
that is specific to the house: ownership, the tax cycle, repossession and
squatting. Money and the guard stay with the caller (`Guild`, `campaign`).
"""

import math

from . import animals, economy, items
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
