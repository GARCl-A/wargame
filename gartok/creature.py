"""What a group keeps besides its people: animals and wagons.

A `Creature` is a body with hit points and a load. Like a `Unit` it is a pack
owner -- the gear screen moves items in and out through the same calls -- but
it never joins `Group.members`: animals live in `Group.herd`, wagons in
`Group.wagons`. A subclass says how much it can hold (`capacity`).
"""

from . import items
from .stash import Stash
from .unit_loadout import CoinPurse, split_stack, stack_add


class _Load(Stash):
    """The creature's load: its room follows whatever the creature says it is."""

    def __init__(self, creature, contents=None):
        self._creature = creature
        super().__init__(0, contents)

    @property
    def capacity(self):
        return self._creature.capacity

    @capacity.setter
    def capacity(self, _value):
        pass


class Creature(CoinPurse):
    name = full_name = "Creature"

    def __init__(self, uid, hp, contents=None, locked_items=None):
        self.uid = uid
        self.hp = hp
        self.stash = _Load(self, contents)
        self.locked_items = dict(locked_items or {})

    @property
    def capacity(self):
        """kg of cargo it can take right now."""
        return 0

    @property
    def _base_inventory(self):
        return self.stash.items

    @property
    def load(self):
        return self.stash.load

    @property
    def carry_normal(self):
        return self.capacity

    carry_max = carry_normal

    def give_to_pack(self, name, qty=1, charges=None, days_old=0):
        stack_add(self.stash.items, name, qty, charges=charges, days_old=days_old)

    def take_from_pack(self, idx, qty=1):
        name, _ = self.stash.take(idx, qty)
        return name

    def split_pack(self, idx, qty):
        return split_stack(self.stash.items, idx, qty)

    @property
    def inventory(self):
        return self.stash.items

    def count_of(self, name):
        return self.stash.count_of(name)

    def has_item(self, name):
        return self.count_of(name) > 0

    def locked_of(self, name):
        return min(self.locked_items.get(name, 0), self.count_of(name))

    def toggle_lock(self, name):
        held = self.count_of(name)
        if held == 0:
            return
        if self.locked_of(name) >= held:
            self.locked_items.pop(name, None)
        else:
            self.locked_items[name] = held

    def unlocked_of(self, name):
        return self.count_of(name) - self.locked_of(name)

    def remove_named(self, name, qty=1):
        return self.stash.remove_named(name, qty)

    def pack_tag(self, name):
        return items.item_tag(name)

    def _derive_combat(self):
        pass
