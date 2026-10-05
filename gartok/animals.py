"""Animals a group keeps: pack animals and the draft animals that pull a wagon.

An animal is its own thing, owned by a `Group`; what it does depends on the
tack it wears. A Pack Saddle lets it carry cargo on its back, a Harness lets it
pull the group's wagon (`wagon.py`). With no tack it just eats. A riding saddle
is the natural next entry in `TACK` once mounts exist.

Cargo on an animal's back never goes into a fight. Members eat from it like they
do from the wagon, and the animals eat from the group's food, wagon first.
"""

from uuid import uuid4

from . import items
from .holdings import Stash
from .unit_loadout import split_stack, stack_add

SPECIES = {                # carry: kg on its back · pull: kg it draws · speed: meters per move, like a race's
    "Donkey": {"hp": 14, "speed": 7.5, "carry": 30, "pull": 80, "price": 60},
    "Ox": {"hp": 24, "speed": 6.0, "carry": 50, "pull": 160, "price": 150},
}
PACK_SADDLE = "Pack Saddle"
HARNESS = "Harness"
TACK = {PACK_SADDLE: "pack", HARNESS: "draft"}      # tack item -> the role it gives
MAX_ANIMALS = 4
STARVE_DAYS = 3


class _Pack(Stash):
    """The animal's load: its room follows the saddle it wears."""

    def __init__(self, animal, contents=None):
        self._animal = animal
        super().__init__(0, contents)

    @property
    def capacity(self):
        return self._animal.carry_room

    @capacity.setter
    def capacity(self, _value):
        pass


class Animal:
    def __init__(self, species, hp=None, unfed_days=0, tack=None, contents=None, uid=None):
        self.uid = uid or uuid4().hex
        self.species = species
        self.hp = SPECIES[species]["hp"] if hp is None else hp
        self.unfed_days = unfed_days
        self.tack = tack
        self.stash = _Pack(self, contents)

    # An animal is a pack owner like a Unit: the gear screen moves items in and
    # out of it through these.
    @property
    def name(self):
        return self.species

    full_name = name

    @property
    def _base_inventory(self):
        return self.stash.items

    @property
    def load(self):
        return self.stash.load

    @property
    def carry_normal(self):
        return self.carry_room

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

    # ------------------------------------------------------------------ #
    @property
    def role(self):
        """"pack", "draft", or None for an animal with no tack."""
        return TACK.get(self.tack)

    @property
    def carry_room(self):
        return SPECIES[self.species]["carry"] if self.role == "pack" else 0

    @property
    def pull(self):
        return SPECIES[self.species]["pull"] if self.role == "draft" else 0

    @property
    def speed(self):
        return SPECIES[self.species]["speed"]

    @property
    def price(self):
        return SPECIES[self.species]["price"]

    @staticmethod
    def can_wear(name):
        return name in TACK

    def give_to_tack(self, name):
        self.tack = name

    def take_tack(self):
        name, self.tack = self.tack, None
        return name

    def to_dict(self, serialize_pack):
        return {"uid": self.uid, "species": self.species, "hp": self.hp,
                "unfed_days": self.unfed_days, "tack": self.tack,
                "contents": serialize_pack(self.stash.items)}

    @classmethod
    def from_dict(cls, d):
        return cls(d["species"], d.get("hp"), d.get("unfed_days", 0), d.get("tack"),
                   d.get("contents", []), d.get("uid"))
