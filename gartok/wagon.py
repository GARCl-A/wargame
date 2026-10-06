"""A group's wagons.

A wagon belongs to a `Group` (`Group.wagons`), travels with it and is lost with
it: if every member dies the group is gone, and so is the wagon; if anyone
survives, even by fleeing, it is still there. Its cargo never goes into a fight.

A wagon is a `Vehicle` type -- a cart for two people and their packs, a carriage
for six -- with its own box, hitch slots and price. It does not own its animals:
an animal wearing a Harness (`animals.HARNESS`) is hitched to one wagon of the
group (`Animal.hitch`, see `Group.hitch`), up to the type's slots; with none
hitched it is a box that cannot move. Its budget is the smaller of what the box
holds and what its own animals draw; passengers (`Group.boarding`, by weight) and
cargo share it. Members eat from the cargo like a `share_food` mate.
"""

from dataclasses import dataclass
from uuid import uuid4

from . import items
from .creature import Creature

WAGON_HD = 8               # every vehicle is an object with a d8
WAGON_HP = (WAGON_HD + 2) // 2


@dataclass(frozen=True)
class Vehicle:
    name: str
    capacity: int          # the box; the animals may draw less
    slots: int
    price: int


VEHICLES = {v.name: v for v in (
    Vehicle("Cart", 180, 1, 150),
    Vehicle("Carriage", 540, 3, 600),
)}


class Wagon(Creature):
    def __init__(self, kind="Cart", hp=WAGON_HP, contents=None, uid=None):
        super().__init__(uid or uuid4().hex, hp, contents)
        self.kind = kind
        self.vehicle = VEHICLES[kind]
        self._group = None         # set by `Group.add_wagon`; where the pulling animals are found

    @property
    def name(self):
        return self.kind

    full_name = name

    @property
    def price(self):
        return self.vehicle.price

    @property
    def draft(self):
        """The animals hitched to it right now."""
        animals = self._group.herd if self._group is not None else []
        return [a for a in animals if a.role == "draft" and a.hitch == self.uid]

    @property
    def free_slots(self):
        return self.vehicle.slots - len(self.draft)

    @property
    def haul(self):
        return sum(a.pull for a in self.draft)

    @property
    def budget(self):
        """kg it can carry in all, passengers and cargo alike: the box, or what its
        animals draw if that is less; 0 with nothing to pull it."""
        return min(self.vehicle.capacity, self.haul)

    @property
    def passengers(self):
        """The members riding it right now -- see `Group.boarding`."""
        return self._group.boarding()[self.uid] if self._group is not None else []

    @property
    def passenger_weight(self):
        return sum(u.ride_weight for u in self.passengers)

    @property
    def capacity(self):
        """kg of cargo it can take right now: what is left of the budget once its
        passengers, and everything they carry, are aboard."""
        return max(0, self.budget - self.passenger_weight)

    @property
    def speed(self):
        """Meters per move: the slowest animal pulling it; None with none."""
        return min((a.speed for a in self.draft), default=None)

    @property
    def rations(self):
        return sum(qty for name, qty in self.stash.items if items.is_food(name.split(" (")[0]))
