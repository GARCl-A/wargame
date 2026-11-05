"""Weapon traits: immutable keyword model for weapon properties and rules.

Mirrors `abilities.py`. Each trait is a frozen `WeaponTrait` defining:
- `id`: unique string identifier (e.g. "finesse", "thrown")
- `name` / `desc`: player-facing name and rule explanation, read from the catalog (`name.trait.<id>`, `desc.trait.<id>`)
- mechanical passives / flags (`finesse: bool`, `thrown: bool`)
- seam for future 2-AP weapon actions / hooks (`action_id`)

REFERENCE.md catalog, weapon descriptions, and combat resolvers read from here.
"""

from dataclasses import dataclass

from . import i18n


@dataclass(frozen=True)
class WeaponTrait:
    id: str
    finesse: bool = False
    thrown: bool = False
    crit_mult: int = 2
    crit_range: int = 20
    action_id: str | None = None      # seam for unique 2-AP action

    @property
    def name(self):
        return i18n.name("trait", self.id)

    @property
    def desc(self):
        return i18n.desc("trait", self.id)


_TRAITS = [
    WeaponTrait(
        id="finesse",
        finesse=True,
    ),
    WeaponTrait(
        id="thrown",
        thrown=True,
    ),
    WeaponTrait(
        id="crit_3x",
        crit_mult=3,
    ),
    WeaponTrait(
        id="sneak_attack",
        action_id="sneak_attack",
    ),
    WeaponTrait(
        id="precise_thrust",
        action_id="precise_thrust",
    ),
    WeaponTrait(
        id="cleave",
        action_id="cleave",
    ),
    WeaponTrait(
        id="repel_strike",
        action_id="repel_strike",
    ),
    WeaponTrait(
        id="maiming_strike",
        action_id="maiming_strike",
    ),
    WeaponTrait(
        id="armor_pierce",
        action_id="armor_pierce",
    ),
    WeaponTrait(
        id="power_shot",
        action_id="power_shot",
    ),
    WeaponTrait(
        id="extreme_shot",
        action_id="extreme_shot",
    ),
    WeaponTrait(
        id="hook_shield",
        action_id="hook_shield",
    ),
    WeaponTrait(
        id="javelin_charge",
        action_id="javelin_charge",
    ),
    WeaponTrait(
        id="parry_strike",
        action_id="parry_strike",
    ),
    WeaponTrait(
        id="wrest",
        action_id="wrest",
    ),
    WeaponTrait(
        id="long_thrust",
        action_id="long_thrust",
    ),
]

TRAITS = {t.id: t for t in _TRAITS}


def get(trait_id: str) -> WeaponTrait | None:
    """Returns the WeaponTrait for trait_id, or None if not found."""
    return TRAITS.get(trait_id)


def all_traits() -> list[WeaponTrait]:
    """Returns all registered weapon traits."""
    return list(_TRAITS)


def action_name(weapon) -> str | None:
    """The name of the 2-AP action `weapon` (an `ItemDef`, or None bare-handed) brings, if any."""
    for tid in getattr(weapon, "traits", ()):
        t = TRAITS.get(tid)
        if t is not None and t.action_id:
            return t.name
    return None
