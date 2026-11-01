"""The body as a weapon: `Unarmed` (a humanoid's empty hands) and the natural weapon of a beast.

These are `ItemDef`s kept out of the item registry on purpose: never sold, looted, picked up from the
ground or drawn in the shop. A weapon grows with its own size, and a natural weapon is as big as the
body that carries it, so each one has a variant per size on the same `DAMAGE_STEPS` ladder the held
weapons use (a Large wolf has a Large `Bite`).

The race carries the weapon (`RACE_WEAPON`); talents only modify it.
"""

from . import data, items
from .items import ItemDef, ItemRarity, ItemType, WeaponSize

BASE_DIE = (1, 3)               # Medium; the ladder runs up from here
_SMALL_DIE = (1, 2)             # Small and Tiny: the ladder has no step down

# name -> (finesse, traits). Every race that fights with its body names one of these.
_WEAPONS = {
    "Unarmed": (False, ()),
    "Bite": (False, ()),
    "Fangs": (True, ()),
    "Claws": (False, ()),
    "Hooves": (False, ()),
    "Horns": (False, ()),
}

RACE_WEAPON = {
    "Wolf": "Bite",
    "Giant Spider": "Bite",
    "Snake": "Fangs",
    "Dragon": "Claws",
    "Donkey": "Hooves",
    "Horse": "Hooves",
    "Ox": "Horns",
}
DEFAULT = "Unarmed"


def _die(size):
    if size in (WeaponSize.TINY, WeaponSize.SMALL):
        return _SMALL_DIE
    die = BASE_DIE
    for _ in range(data.SIZE_ORDER.index(size) - data.SIZE_ORDER.index(WeaponSize.MEDIUM)):
        die = items.step_damage_die(die)
    return die


def _build():
    table = {}
    for name, (finesse, traits) in _WEAPONS.items():
        for size in data.SIZE_ORDER:
            table[(name, size)] = ItemDef(
                id=f"{name.lower()}_{size.lower()}", name=name, type=ItemType.WEAPON,
                rarity=ItemRarity.COMMON, weight=0.0, price=0, size=WeaponSize(size),
                damage=_die(size), finesse=finesse, traits=traits)
    return table


_TABLE = _build()
NAMES = tuple(_WEAPONS)


def get(name, size="Medium"):
    """The natural weapon `name` at body size `size`, or None for a name that is not one."""
    return _TABLE.get((name, size))


def for_race(race_name, size="Medium"):
    """The weapon a body of `race_name` and `size` fights with when nothing is in its hand."""
    return _TABLE[(RACE_WEAPON.get(race_name, DEFAULT), size)]
