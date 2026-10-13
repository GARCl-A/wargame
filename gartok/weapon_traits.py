"""Weapon traits: immutable keyword model for weapon properties and rules.

Mirrors `abilities.py`. Each trait is a frozen `WeaponTrait` defining:
- `id`: unique string identifier (e.g. "finesse", "thrown")
- `name`: player-facing name ("Finesse", "Thrown")
- `desc`: player-facing rule explanation
- mechanical passives / flags (`finesse: bool`, `thrown: bool`)
- seam for future 2-AP weapon actions / hooks (`action_id`)

REFERENCE.md catalog, weapon descriptions, and combat resolvers read from here.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WeaponTrait:
    id: str
    name: str
    desc: str
    finesse: bool = False
    thrown: bool = False
    action_id: str | None = None      # seam for unique 2-AP action


_TRAITS = [
    WeaponTrait(
        id="finesse",
        name="Finesse",
        desc="Uses Dexterity for attack rolls if it is higher than Strength.",
        finesse=True,
    ),
    WeaponTrait(
        id="thrown",
        name="Thrown",
        desc="Can be thrown up to its thrown range. Adds Strength modifier to attack and damage.",
        thrown=True,
    ),
]

TRAITS = {t.id: t for t in _TRAITS}


def get(trait_id: str) -> WeaponTrait | None:
    """Returns the WeaponTrait for trait_id, or None if not found."""
    return TRAITS.get(trait_id)


def all_traits() -> list[WeaponTrait]:
    """Returns all registered weapon traits."""
    return list(_TRAITS)
