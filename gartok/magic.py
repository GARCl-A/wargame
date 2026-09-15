"""Magic system registry and learning math."""

from dataclasses import dataclass

@dataclass(frozen=True)
class Spell:
    id: str
    name: str
    level: int
    sources: tuple

SPELLS = {
    "light_globe": Spell("light_globe", "Light Globe", 0, ("nature", "blood", "faith")),
    "magic_missile": Spell("magic_missile", "Magic Missile", 0, ("nature", "blood", "faith")),
    "floating_disk": Spell("floating_disk", "Floating Disk", 0, ("nature", "blood", "faith")),
    "sleep": Spell("sleep", "Sleep", 1, ("nature", "blood", "faith")),
}

def spell_for_scroll(item_name):
    """The Spell a `Scroll of <Name>` item names, or None (not a scroll, or
    no spell matches)."""
    return next((s for s in SPELLS.values() if item_name == f"Scroll of {s.name}"), None)

def study_difficulty(spell):
    """The DC to learn a spell. Daily rolls check against this average to accumulate points."""
    return 15 + spell.level

def points_to_learn(spell):
    """Total points needed to master a spell. (15+lvl) * (7 days per level + 7)."""
    weeks = spell.level + 1
    return study_difficulty(spell) * (weeks * 7)
