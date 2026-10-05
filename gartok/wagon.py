"""A group's wagon.

The wagon belongs to a `Group` (`Group.wagon`), travels with it and is lost with
it: if every member dies the group is gone, and so is the wagon; if anyone
survives, even by fleeing, it is still there. Its cargo never goes into a fight.

The wagon does not own its animals. The group's animals wearing a Harness
(`animals.HARNESS`) pull it, up to `HITCH_SLOTS` of them; with none, it is a box
that cannot move. Cargo room is the smaller of what the box holds and what the
animals draw once the wagon's own weight is taken off. Members eat from the cargo
like a `share_food` mate.
"""

from . import items
from .holdings import Stash
from .unit_loadout import split_stack, stack_add

WAGON_PRICE = 150
WAGON_WEIGHT = 40          # kg of the wagon itself -- the animals draw this too
WAGON_CAPACITY = 80        # kg the box holds, whatever the animals could pull
WAGON_HP = 30
HITCH_SLOTS = 2


class _Hold(Stash):
    """The cargo box: its capacity follows the animals pulling the wagon."""

    def __init__(self, wagon, contents=None):
        self._wagon = wagon
        super().__init__(0, contents)

    @property
    def capacity(self):
        return self._wagon.capacity

    @capacity.setter
    def capacity(self, _value):
        pass


class Wagon:
    def __init__(self, hp=WAGON_HP, contents=None):
        self.hp = hp
        self.stash = _Hold(self, contents)
        self._group = None         # set by `Group.wagon`; where the pulling animals are found

    # The wagon is a pack owner like a Unit: the gear screen moves items in and
    # out through these, the same way it does for a member's pack.
    name = full_name = "Wagon"
    uid = "wagon"

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

    @property
    def draft(self):
        """The animals pulling it right now."""
        animals = self._group.animals if self._group is not None else []
        return [a for a in animals if a.role == "draft"][:HITCH_SLOTS]

    @property
    def haul(self):
        return sum(a.pull for a in self.draft)

    @property
    def capacity(self):
        """kg of cargo it can take right now; 0 with nothing to pull it."""
        return max(0, min(WAGON_CAPACITY, self.haul - WAGON_WEIGHT))

    @property
    def speed(self):
        """Meters per move: the slowest animal pulling it; None with none."""
        return min((a.speed for a in self.draft), default=None)

    @property
    def rations(self):
        return sum(qty for name, qty in self.stash.items if items.is_food(name.split(" (")[0]))
