"""Archetype catalog, candidate generation, and commission constraints for recruitment.

Defines the 7 squad archetypes -- roles a draft candidate can fill (LEADER, STRONG,
TOUGH, etc.), never a racial trait that would just pick a race -- and
provides constraint-aware candidate generation so players can spend commission
tokens to guarantee functional squad roles without endless rerolling.
"""

from collections.abc import Callable
from dataclasses import dataclass

from .unit import Unit


@dataclass(frozen=True)
class Archetype:
    key: str
    label: str
    desc: str
    predicate: Callable[[Unit], bool]
    style: str = "brass"


ARCHETYPES = {
    "LEADER": Archetype(
        key="LEADER",
        label="LEADER",
        style="brass",
        desc="Highly charismatic (+2 mod). Critical for recruiting in taverns, bargaining, and guild morale.",
        predicate=lambda u: u.mod_charisma >= 2,
    ),
    "STRONG": Archetype(
        key="STRONG",
        label="STRONG",
        style="green",
        desc="Powerful build (+2 Strength mod). Hits hard in melee and hauls heavy armor, tools, and spoils.",
        predicate=lambda u: u.mod_strength >= 2,
    ),
    "TOUGH": Archetype(
        key="TOUGH",
        label="TOUGH",
        style="green",
        desc="Massive health pool (8+ max HP). Durable frontline combatant with strong survivability.",
        predicate=lambda u: u.hp_max >= 8,
    ),
    "NIMBLE": Archetype(
        key="NIMBLE",
        label="NIMBLE",
        style="green",
        desc="Superior dexterity (+2 mod). High evasion, accuracy with finesse weapons, and natural defense.",
        predicate=lambda u: u.mod_dexterity >= 2,
    ),
    "RANGED": Archetype(
        key="RANGED",
        label="RANGED",
        style="muted",
        desc="Equipped with bow, sling, or crossbow. Engages hostile targets from safe standoff distance.",
        predicate=lambda u: bool(u.ranged),
    ),
    "GENIUS": Archetype(
        key="GENIUS",
        label="GENIUS",
        style="green",
        desc="Brilliant intellect (+2 mod). Accelerated crafting, manual reading, and arcane research.",
        predicate=lambda u: u.mod_intelligence >= 2,
    ),
    "WISE": Archetype(
        key="WISE",
        label="WISE",
        style="green",
        desc="Perceptive mind (+2 mod). High combat initiative, mental defense, and skilled field medicine.",
        predicate=lambda u: u.mod_wisdom >= 2,
    ),
}

INCOMPATIBLE_PAIRS: set[tuple[str, str]] = set()      # none today; kept so a future pair is one line


def unit_archetypes(u: Unit):
    """Returns list of (label, style, desc) for all matching archetypes on this unit."""
    matched = []
    for key, arc in ARCHETYPES.items():
        if arc.predicate(u):
            matched.append((arc.label, arc.style, arc.desc))
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
