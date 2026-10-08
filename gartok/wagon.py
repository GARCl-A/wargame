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

A vehicle is an object of `hd` Hit Dice of d8 with no Constitution at all (not a
zero modifier: none). It cannot die: at 0 HP it is *broken*, like an Automaton --
it stays where it is, draws nothing and carries nothing until it is repaired
(`Guild.repair_wagon`) or left behind (`Guild.abandon_wagon`). The road wears it:
every `WEAR_DISTANCE` units of map distance it has travelled cost it 1 HP.
"""

import math
from dataclasses import dataclass
from uuid import uuid4

from . import items
from .creature import Creature

WAGON_DIE = 8              # every vehicle is an object with d8 Hit Dice
WEAR_DISTANCE = 100        # map distance travelled per HP lost
REPAIR_HOURS = 1
REPAIR_DC = 15
REPAIR_ITEM = "Lumber"


@dataclass(frozen=True)
class Vehicle:
    name: str
    capacity: int          # the box; the animals may draw less
    slots: int
    price: int
    hd: int                # Hit Dice: its HP, and the Lumber a repair costs

    @property
    def hp_max(self):
        """The mean of `hd` dice, rounded up -- fixed, nobody rolls a cart."""
        return (self.hd * WAGON_DIE + 2) // 2


VEHICLES = {v.name: v for v in (
    Vehicle("Cart", 180, 1, 150, 1),
    Vehicle("Carriage", 540, 3, 600, 3),
)}


def repairer(crew):
    """Who tries the repair: whoever has the best Intelligence modifier. One place to
    change if the repair ever leans on another stat."""
    return max(crew, key=lambda u: u.mod_intelligence, default=None)


class Wagon(Creature):
    def __init__(self, kind="Cart", hp=None, contents=None, uid=None, travelled=0.0):
        vehicle = VEHICLES[kind]
        super().__init__(uid or uuid4().hex, vehicle.hp_max if hp is None else min(hp, vehicle.hp_max), contents)
        self.kind = kind
        self.vehicle = vehicle
        self.travelled = travelled     # map distance since it last lost a point
        self._group = None         # set by `Group.add_wagon`; where the pulling animals are found

    @property
    def name(self):
        return self.kind

    full_name = name

    @property
    def price(self):
        return self.vehicle.price

    @property
    def hp_max(self):
        return self.vehicle.hp_max

    @property
    def broken(self):
        return self.hp <= 0

    @property
    def repair_cost(self):
        """Lumber one repair takes: one per Hit Die."""
        return self.vehicle.hd

    @property
    def repair_amount(self):
        return math.ceil(self.hp_max / 2)

    @property
    def needs_repair(self):
        return self.hp < self.hp_max

    def wear(self, distance):
        """The road takes its toll: `WEAR_DISTANCE` of travel costs 1 HP. Returns the HP
        lost; a broken wagon does not wear further."""
        if self.broken:
            return 0
        self.travelled += distance
        points = int(self.travelled // WEAR_DISTANCE)
        self.travelled -= points * WEAR_DISTANCE
        lost = min(self.hp, points)
        self.hp -= lost
        return lost

    def repair(self):
        """Mend it by half its maximum. Returns the HP gained."""
        gained = min(self.repair_amount, self.hp_max - self.hp)
        self.hp += gained
        return gained

    @property
    def draft(self):
        """The animals hitched to it right now; none while it is broken."""
        if self.broken:
            return []
        animals = self._group.herd if self._group is not None else []
        return [a for a in animals if a.role == "draft" and a.hitch == self.uid]

    @property
    def free_slots(self):
        return 0 if self.broken else self.vehicle.slots - len(self.draft)

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
        return max(0, round(self.budget - self.passenger_weight, 1))

    @property
    def speed(self):
        """Meters per move: the slowest animal pulling it; None with none."""
        return min((a.speed for a in self.draft), default=None)

    @property
    def rations(self):
        return sum(qty for name, qty in self.stash.items if items.is_food(name.split(" (")[0]))
