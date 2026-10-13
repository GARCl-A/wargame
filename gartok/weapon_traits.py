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
    crit_mult: int = 2
    crit_range: int = 20
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
    WeaponTrait(
        id="crit_3x",
        name="Crit 3x",
        desc="Critical hits deal 3x weapon damage dice instead of 2x.",
        crit_mult=3,
    ),
    WeaponTrait(
        id="sneak_attack",
        name="Sneak Attack",
        desc="2 AP: Deals +1d4 bonus damage against flanked foes.",
        action_id="sneak_attack",
    ),
    WeaponTrait(
        id="precise_thrust",
        name="Precise Thrust",
        desc="2 AP: Gains +2 to hit against flanked foes.",
        action_id="precise_thrust",
    ),
    WeaponTrait(
        id="cleave",
        name="Cleave",
        desc="2 AP: Strikes two adjacent foes in a single sweep.",
        action_id="cleave",
    ),
    WeaponTrait(
        id="repel_strike",
        name="Repel Strike",
        desc="2 AP: Attacks and shoves the target with a +2 bonus to the push roll.",
        action_id="repel_strike",
    ),
    WeaponTrait(
        id="maiming_strike",
        name="Maiming Strike",
        desc="2 AP: Attacks and halves the target's movement speed until next round.",
        action_id="maiming_strike",
    ),
    WeaponTrait(
        id="armor_pierce",
        name="Armor Pierce",
        desc="2 AP: Attack ignores worn armor AC bonus.",
        action_id="armor_pierce",
    ),
    WeaponTrait(
        id="power_shot",
        name="Power Shot",
        desc="2 AP: Adds positive Strength modifier to arrow damage.",
        action_id="power_shot",
    ),
    WeaponTrait(
        id="extreme_shot",
        name="Extreme Shot",
        desc="2 AP: Doubles attack range to 36 squares.",
        action_id="extreme_shot",
    ),
    WeaponTrait(
        id="hook_shield",
        name="Hook Shield",
        desc="2 AP: Attacks and nullifies target's shield AC bonus until next round.",
        action_id="hook_shield",
    ),
    WeaponTrait(
        id="javelin_charge",
        name="Javelin Charge",
        desc="2 AP: Deals +1d4 bonus damage when thrown after moving this turn.",
        action_id="javelin_charge",
    ),
    WeaponTrait(
        id="parry_strike",
        name="Parry & Strike",
        desc="2 AP: Attacks and grants Defending (+1 AC) to attacker until next round.",
        action_id="parry_strike",
    ),
]

TRAITS = {t.id: t for t in _TRAITS}


def get(trait_id: str) -> WeaponTrait | None:
    """Returns the WeaponTrait for trait_id, or None if not found."""
    return TRAITS.get(trait_id)


def all_traits() -> list[WeaponTrait]:
    """Returns all registered weapon traits."""
    return list(_TRAITS)
