"""Archetype catalog, candidate generation, and commission constraints for recruitment.

Defines the 12 core squad archetypes (LEADER, PACK MULE, TOUGH, etc.) and
provides constraint-aware candidate generation so players can spend commission
tokens to guarantee functional squad roles without endless rerolling.
"""

from dataclasses import dataclass
from typing import Callable

from . import items
from .ui.tokens import T
from .unit import Unit


@dataclass(frozen=True)
class Archetype:
    key: str
    label: str
    color: tuple
    desc: str
    predicate: Callable[[Unit], bool]


def expected_damage(u: Unit) -> float:
    """Expected damage output for a unit based on equipped weapon and stats."""
    wep_name = u.equipped_weapon
    if not wep_name:
        count, sides = u.unarmed_damage
        return count * ((sides + 1) / 2) + u.mod_strength
    wep = items.get(wep_name)
    if not wep:
        count, sides = u.unarmed_damage
        return count * ((sides + 1) / 2) + u.mod_strength
    count, sides = wep.damage or (1, 2)
    stat_mod = u.mod_dexterity if wep.finesse else u.mod_strength
    return count * ((sides + 1) / 2) + stat_mod


ARCHETYPES = {
    "LEADER": Archetype(
        key="LEADER",
        label="LEADER",
        color=T.BRASS,
        desc="Highly charismatic (+2 mod). Critical for recruiting in taverns, bargaining, and guild morale.",
        predicate=lambda u: u.mod_charisma >= 2,
    ),
    "PACK MULE": Archetype(
        key="PACK MULE",
        label="PACK MULE",
        color=T.GREEN,
        desc="Can carry 35+ kg. Hauls heavy armor, tools, and spoils without encumbrance penalties.",
        predicate=lambda u: u.carry_normal >= 35,
    ),
    "TOUGH": Archetype(
        key="TOUGH",
        label="TOUGH",
        color=T.GREEN,
        desc="Massive health pool (8+ max HP). Durable frontline combatant with strong survivability.",
        predicate=lambda u: u.hp_max >= 8,
    ),
    "DAMAGE DEALER": Archetype(
        key="DAMAGE DEALER",
        label="DAMAGE DEALER",
        color=T.BRASS,
        desc="Heavy hitter (6+ expected damage). Deals punishing strikes in melee or at range.",
        predicate=lambda u: expected_damage(u) >= 6,
    ),
    "NIMBLE": Archetype(
        key="NIMBLE",
        label="NIMBLE",
        color=T.GREEN,
        desc="Superior dexterity (+2 mod). High evasion, accuracy with finesse weapons, and natural defense.",
        predicate=lambda u: u.mod_dexterity >= 2,
    ),
    "RANGED": Archetype(
        key="RANGED",
        label="RANGED",
        color=T.TX_MUTED,
        desc="Equipped with bow, sling, or crossbow. Engages hostile targets from safe standoff distance.",
        predicate=lambda u: bool(u.ranged),
    ),
    "GENIUS": Archetype(
        key="GENIUS",
        label="GENIUS",
        color=T.GREEN,
        desc="Brilliant intellect (+2 mod). Accelerated crafting, manual reading, and arcane research.",
        predicate=lambda u: u.mod_intelligence >= 2,
    ),
    "WISE": Archetype(
        key="WISE",
        label="WISE",
        color=T.GREEN,
        desc="Perceptive mind (+2 mod). High combat initiative, mental defense, and skilled field medicine.",
        predicate=lambda u: u.mod_wisdom >= 2,
    ),
    "FAST": Archetype(
        key="FAST",
        label="FAST",
        color=T.GREEN,
        desc="Exceptional speed (7+ cells). Moves rapidly across grid encounters and controls positioning.",
        predicate=lambda u: u.speed >= 7,
    ),
    "LARGE": Archetype(
        key="LARGE",
        label="LARGE",
        color=T.TX_MUTED,
        desc="Large creature (2x2 footprint). High base hit die, expanded battlefield reach, and physical weight.",
        predicate=lambda u: u.size == "Large",
    ),
    "SEES IN DARK": Archetype(
        key="SEES IN DARK",
        label="SEES IN DARK",
        color=T.TX_MUTED,
        desc="Racial Darkvision. Operates and fights unhindered in deep darkness without needing torches.",
        predicate=lambda u: bool(u.ability.darkvision),
    ),
    "MAGIC": Archetype(
        key="MAGIC",
        label="MAGIC",
        color=T.TX_MUTED,
        desc="Arcane or natural initiate. Starts with a magic source or known spells and can read scrolls.",
        predicate=lambda u: bool(getattr(u, "magic_source", None) or getattr(u, "spells_known", [])),
    ),
}

INCOMPATIBLE_PAIRS = {
    ("PACK MULE", "SEES IN DARK"),
    ("MAGIC", "PACK MULE"),
    ("FAST", "SEES IN DARK"),
    ("FAST", "MAGIC"),
    ("LARGE", "SEES IN DARK"),
    ("LARGE", "MAGIC"),
    ("MAGIC", "SEES IN DARK"),
}


def unit_archetypes(u: Unit):
    """Returns list of (label, color, desc) for all matching archetypes on this unit."""
    matched = []
    for key, arc in ARCHETYPES.items():
        if arc.predicate(u):
            matched.append((arc.label, arc.color, arc.desc))
    return matched


def is_compatible(selected_labels: list, candidate_label: str) -> bool:
    """Checks whether adding `candidate_label` to `selected_labels` forms a valid combination."""
    if candidate_label in selected_labels:
        return False
    for s in selected_labels:
        pair = (min(s, candidate_label), max(s, candidate_label))
        if pair in INCOMPATIBLE_PAIRS:
            return False
    return True


def generate_candidate(labels: list, max_attempts: int = 2500) -> Unit:
    """Generate a player Unit that satisfies all requested archetype labels."""
    if not labels:
        return Unit("player")

    best_candidate = None
    best_matches = -1

    for _ in range(max_attempts):
        u = Unit("player")
        matched = 0
        all_ok = True
        for lbl in labels:
            if ARCHETYPES[lbl].predicate(u):
                matched += 1
            else:
                all_ok = False
        if all_ok:
            return u
        if matched > best_matches:
            best_matches = matched
            best_candidate = u

    return best_candidate or Unit("player")
