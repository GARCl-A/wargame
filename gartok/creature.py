"""What a group keeps besides its people: animals and wagons.

A `Creature` is a body with hit points and a load. Like a `Unit` it is a pack
owner -- the gear screen moves items in and out through the same calls -- but
it never joins `Group.members`: animals live in `Group.herd`, wagons in
`Group.wagons`. A subclass says how much it can hold (`capacity`).
"""

from . import items
from .stash import Stash
from .unit_loadout import split_stack, stack_add


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


class Creature:
    name = full_name = "Creature"

    def __init__(self, uid, hp, contents=None):
        self.uid = uid
        self.hp = hp
        self.stash = _Load(self, contents)

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

    def locked_of(self, name):
        return 0

    def toggle_lock(self, name):
        pass

    def pack_tag(self, name):
        return items.item_tag(name)

    def _derive_combat(self):
        pass
