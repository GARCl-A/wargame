"""Archetype catalog, candidate generation, and commission constraints for recruitment.

Defines the squad archetypes -- roles a draft candidate can fill (LEADER, STRONG,
TOUGH, etc.), never a racial trait that would just pick a race -- plus the RISKY
warning, and provides constraint-aware candidate generation so players can spend
commission tokens to guarantee functional squad roles without endless rerolling.
"""

from collections.abc import Callable
from dataclasses import dataclass

from . import i18n, items
from .data import ATTRIBUTES
from .unit import Unit

STARTER_KIT = ("Studded Leather", "Dagger", "Torch", "Potato")      # what a new recruit is expected to haul
STARTER_KIT_KG = round(sum(items.item_weight(n) for n in STARTER_KIT), 1)
RISKY_CON = 8                  # at or under: the slow healer, the poor swimmer, the one a poison drops
RISKY_TOTAL = 56               # the six attributes at or under (the average body is 63)


def risks(u: Unit) -> list[str]:
    """Why `u` is a hard pick: each reason as the card words it. Empty for an ordinary body."""
    out = []
    if u.constitution <= RISKY_CON:
        out.append(i18n.t("archetype.risk.con", con=u.constitution))
    total = sum(getattr(u, a) for a in ATTRIBUTES)
    if total <= RISKY_TOTAL:
        out.append(i18n.t("archetype.risk.total", total=total))
    if u.carry_normal < STARTER_KIT_KG:
        out.append(i18n.t("archetype.risk.carry", carry=f"{u.carry_normal:g}", kit=f"{STARTER_KIT_KG:g}"))
    return out


@dataclass(frozen=True)
class Archetype:
    key: str
    label: str
    rule: str                  # the threshold in a few characters, for the card and the tutorial
    predicate: Callable[[Unit], bool]
    style: str = "brass"
    why: Callable[[Unit], list[str]] | None = None      # reasons shown with the tag, when it needs them

    @property
    def desc(self) -> str:
        """What it is good for."""
        return i18n.desc("archetype", self.key)

    @property
    def text(self) -> str:
        return f"{self.rule}. {self.desc}"


ARCHETYPES = {
    "LEADER": Archetype(
        key="LEADER",
        label="LEADER",
        rule="CHA +2",
        style="brass",
        predicate=lambda u: u.mod_charisma >= 2,
    ),
    "STRONG": Archetype(
        key="STRONG",
        label="STRONG",
        rule="STR +2",
        style="green",
        predicate=lambda u: u.mod_strength >= 2,
    ),
    "TOUGH": Archetype(
        key="TOUGH",
        label="TOUGH",
        rule="8+ HP",
        style="green",
        predicate=lambda u: u.hp_max >= 8,
    ),
    "HEALTHY": Archetype(
        key="HEALTHY",
        label="HEALTHY",
        rule="CON +2",
        style="green",
        predicate=lambda u: u.mod_constitution >= 2,
    ),
    "NIMBLE": Archetype(
        key="NIMBLE",
        label="NIMBLE",
        rule="DEX +2",
        style="green",
        predicate=lambda u: u.mod_dexterity >= 2,
    ),
    "GENIUS": Archetype(
        key="GENIUS",
        label="GENIUS",
        rule="INT +2",
        style="green",
        predicate=lambda u: u.mod_intelligence >= 2,
    ),
    "WISE": Archetype(
        key="WISE",
        label="WISE",
        rule="WIS +2",
        style="green",
        predicate=lambda u: u.mod_wisdom >= 2,
    ),
    "RISKY": Archetype(
        key="RISKY",
        label="RISKY",
        rule=f"CON ≤ {RISKY_CON} · total ≤ {RISKY_TOTAL} · can barely carry gear",
        style="warn",
        predicate=lambda u: bool(risks(u)),
        why=risks,
    ),
}

INCOMPATIBLE_PAIRS: set[tuple[str, str]] = set()      # none today; kept so a future pair is one line


def unit_archetypes(u: Unit):
    """Returns list of (label, style, text) for all matching archetypes on this unit; a tag with reasons
    (RISKY) says them."""
    matched = []
    for arc in ARCHETYPES.values():
        if arc.predicate(u):
            text = arc.text if arc.why is None else f"{arc.desc} Here: {'; '.join(arc.why(u))}."
            matched.append((arc.label, arc.style, text))
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
