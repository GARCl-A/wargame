"""A weight-capped stack of items: the storage the bank, the house and a creature's load share.

It lives apart from `holdings` so `creature` can build on it without importing the
module that imports `animals`.
"""

from . import items
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

    # the coin-handling half of a Unit's pack interface, so money moves the same
    def count_of(self, name):
        return sum(q for n, q in self.items if n == name)

    def give_to_pack(self, name, qty=1):
        self.put(name, qty)

    def remove_named(self, name, qty=1):
        left = qty
        for idx in range(len(self.items) - 1, -1, -1):
            if left and self.items[idx][0] == name:
                left -= self.take(idx, left)[1]
        return qty - left
