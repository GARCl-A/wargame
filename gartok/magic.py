"""Magic system registry and learning math."""

from dataclasses import dataclass

@dataclass(frozen=True)
class Spell:
    id: str
    name: str
    level: int
    source: str

SPELLS = {
    "light_globe": Spell("light_globe", "Globo de Luz", 0, "nature"),
    "magic_missile": Spell("magic_missile", "Míssil Mágico", 0, "nature"),
    "floating_disk": Spell("floating_disk", "Disco Flutuante", 0, "nature"),
}

def study_difficulty(spell):
    """The DC to learn a spell. Daily rolls check against this average to accumulate points."""
    return 15 + spell.level

def points_to_learn(spell):
    """Total points needed to master a spell. (15+lvl) * (7 days per level + 7)."""
    weeks = spell.level + 1
    return study_difficulty(spell) * (weeks * 7)
