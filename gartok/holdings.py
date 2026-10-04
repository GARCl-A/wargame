"""Things the guild owns as a body: a weight-capped `Stash`, and the City house
built around one.

`Guild.bank` (the Bankers' strongbox) and `Guild.house` (the City property)
share the same storage, so a future base reuses `Stash` rather than growing
another copy of the item bookkeeping on `Guild`. `CityProperty` adds the part
that is specific to the house: ownership, the tax cycle, repossession and
squatting. Money and the guard stay with the caller (`Guild`, `campaign`).
"""

from . import economy, items
from .unit import pack_from_raw, stack_add, stack_take


class Stash:
    """A weight-capped stack of items. `capacity == 0` means nothing is held
    yet (an unrented strongbox)."""

    def __init__(self, capacity=0, contents=None):
        self.capacity = capacity
        self.items = pack_from_raw(contents or [])

    @property
    def open(self):
        return self.capacity > 0

    @property
    def load(self):
        return sum(items.item_weight(name) * qty for name, qty in self.items)

    @property
    def free(self):
        return self.capacity - self.load

    def fits(self, weight):
        return self.load + weight <= self.capacity

    def put(self, name, qty=1):
        stack_add(self.items, name, qty)

    def take(self, idx, qty=1):
        """Remove up to `qty` from the stack at `idx`. Returns `(name, removed)`."""
        name, removed, _ = stack_take(self.items, idx, qty)
        return name, removed


class CityProperty:
    """The house the Bankers sell in the City, taxed on a cycle. A squatter
    keeps `owned` set -- the guild still holds the keys, illegally -- until the
    guard clears it (`abandon`)."""

    def __init__(self, owned=False, contents=None, tax_due_day=None,
                 missed_payments=0, squatting=False):
        self.owned = owned
        self.stash = Stash(economy.CITY_PROPERTY_CAPACITY, contents)
        self.tax_due_day = tax_due_day          # clock.day the next tax is due, or None
        self.missed_payments = missed_payments
        self.squatting = squatting              # illegal occupier, after refusing repossession

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
        self.stash.items = []
