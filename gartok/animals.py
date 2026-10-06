"""Animals a group keeps: pack animals and the draft animals that pull a wagon.

An animal is its own thing, owned by a `Group`; what it does depends on the
tack it wears. A Pack Saddle lets it carry cargo on its back, a Harness lets it
pull the group's wagon (`wagon.py`). With no tack it just eats. A riding saddle
is the natural next entry in `TACK` once mounts exist.

Cargo on an animal's back never goes into a fight. Members eat from it like they
do from the wagon, and the animals eat from the group's food, wagon first.
"""

from uuid import uuid4

from . import abilities, data
from .creature import Creature
from .unit_derive import carry_thresholds

PRICE = {"Donkey": 180, "Ox": 300, "Horse": 480}
HERD_WEIGHT = {"Donkey": 1, "Ox": 1, "Horse": 1}     # what each costs against `Group.herd_capacity`
AVERAGE_SCORE = 11                                    # a shop animal is not rolled: 3d6 averages 10.5, rounded up
LOAD_UNIT = 30                                        # kg: what a chest holds, and the step every capacity moves in
PACK_SADDLE = "Pack Saddle"
HARNESS = "Harness"
TACK = {PACK_SADDLE: "pack", HARNESS: "draft"}      # tack item -> the role it gives
STARVE_DAYS = 3


def _to_units(kg):
    return max(LOAD_UNIT, round(kg / LOAD_UNIT) * LOAD_UNIT)


class Animal(Creature):
    """A creature sheet from the race table (`data.BEASTS`) with fixed
    attributes. Its Strength sets the two loads it can take: `back_load` with a
    Pack Saddle, `draw` pulling a wagon with a Harness."""

    def __init__(self, species, hp=None, unfed_days=0, tack=None, contents=None, uid=None, hitch=None):
        self.species = species
        self.race = data.race_by_name(species)
        self.ability = abilities.get(self.race["ability"])
        self.attributes = {a: AVERAGE_SCORE + m for a, m in zip(data.ATTRIBUTES, self.race["mods"])}
        self.size = self.race["size"]
        self.hp_max = max(1, (self.race["hd"] + 2) // 2 + data.mod(self.attributes["constitution"]))
        super().__init__(uid or uuid4().hex, self.hp_max if hp is None else hp, contents)
        self.unfed_days = unfed_days
        self.tack = tack
        self.hitch = hitch              # uid of the wagon it pulls (needs a Harness), or None

    @property
    def name(self):
        return self.species

    full_name = name

    @property
    def strength(self):
        return self.attributes["strength"]

    @property
    def _loads(self):
        return carry_thresholds(self.strength, self.size, self.ability)

    @property
    def back_load(self):
        return _to_units(self._loads[0])

    @property
    def draw(self):
        return _to_units(self._loads[1])

    @property
    def role(self):
        """"pack", "draft", or None for an animal with no tack."""
        return TACK.get(self.tack)

    @property
    def capacity(self):
        return self.back_load if self.role == "pack" else 0

    @property
    def pull(self):
        return self.draw if self.role == "draft" else 0

    @property
    def speed(self):
        return self.race["speed"]

    @property
    def price(self):
        return PRICE[self.species]

    @property
    def herd_weight(self):
        return HERD_WEIGHT[self.species]

    @staticmethod
    def can_wear(name):
        return name in TACK

    def give_to_tack(self, name):
        self.tack = name
        self.hitch = None

    def take_tack(self):
        name, self.tack, self.hitch = self.tack, None, None
        return name

    def to_dict(self, serialize_pack):
        return {"uid": self.uid, "species": self.species, "hp": self.hp,
                "unfed_days": self.unfed_days, "tack": self.tack, "hitch": self.hitch,
                "contents": serialize_pack(self.stash.items)}

    @classmethod
    def from_dict(cls, d):
        return cls(d["species"], d.get("hp"), d.get("unfed_days", 0), d.get("tack"),
                   d.get("contents", []), d.get("uid"), d.get("hitch"))
