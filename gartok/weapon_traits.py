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
        desc="2 AP: One strike; against a flanked foe the blow lands twice over (a second roll of the weapon's damage), +1d4.",
        action_id="sneak_attack",
    ),
    WeaponTrait(
        id="precise_thrust",
        name="Precise Thrust",
        desc="2 AP: One strike; against a flanked foe +2 to hit and the blow lands twice over (a second roll of the weapon's damage).",
        action_id="precise_thrust",
    ),
    WeaponTrait(
        id="cleave",
        name="Cleave",
        desc="2 AP: One strike; with a second foe beside both, the sweep strikes it too, each swing +2 to hit.",
        action_id="cleave",
    ),
    WeaponTrait(
        id="repel_strike",
        name="Repel Strike",
        desc="2 AP: One strike that shoves the target (+2 to the push); against a foe with its back to a wall or a body the blow lands twice over (a second roll of the weapon's damage), +1d4.",
        action_id="repel_strike",
    ),
    WeaponTrait(
        id="maiming_strike",
        name="Maiming Strike",
        desc="2 AP: One strike that halves the target's speed until next round; against a foe Entangled, Sleeping, Surprised or Demoralized +2 to hit and the blow lands twice over (a second roll of the weapon's damage).",
        action_id="maiming_strike",
    ),
    WeaponTrait(
        id="armor_pierce",
        name="Armor Pierce",
        desc="2 AP: One strike that ignores worn armor AC; against an armoured foe the blow lands twice over (a second roll of the weapon's damage).",
        action_id="armor_pierce",
    ),
    WeaponTrait(
        id="power_shot",
        name="Power Shot",
        desc="2 AP: One shot with +STR damage; at half the bow's range or farther +STR (at least +1) and the blow lands twice over (a second roll of the weapon's damage).",
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
        desc="2 AP: Against a foe with a shield: hooks it first (no shield AC until next round, this strike included), then one strike that lands twice over (a second roll of the weapon's damage). Otherwise one plain strike.",
        action_id="hook_shield",
    ),
    WeaponTrait(
        id="javelin_charge",
        name="Javelin Charge",
        desc="1 AP: Throws the spear after moving this turn, +1d4 bonus damage.",
        action_id="javelin_charge",
    ),
    WeaponTrait(
        id="parry_strike",
        name="Parry & Strike",
        desc="2 AP: One strike and Defending (+1 AC) until next round; with two or more foes in reach the blow lands twice over (a second roll of the weapon's damage).",
        action_id="parry_strike",
    ),
    WeaponTrait(
        id="long_thrust",
        name="Long Thrust",
        desc="2 AP: One strike one square past the weapon's reach, +1 to hit: the only blow that lands that far.",
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
