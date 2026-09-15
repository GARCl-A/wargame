"""Magic system registry and learning math."""

from dataclasses import dataclass

from . import data, economy

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

def progress_study(unit):
    """One day of `unit` studying a scroll at a tavern's "study" garrison job:
    charge the daily rent, then roll progress toward `study_target` if the rent
    is paid, the unit is magically initiated, and the scroll is still in hand.
    Returns an event string worth telling the player about, or None for a quiet
    day (no target set, no scroll, not initiated -- rent still comes due)."""
    if unit.gold < economy.TAVERN_STUDY_COST_PER_DAY:
        return f"{unit.name} could not afford the rent to study."
    unit.gold -= economy.TAVERN_STUDY_COST_PER_DAY
    if not unit.study_target or not unit.magic_source:
        return None
    spell = SPELLS.get(unit.study_target)
    if spell is None or f"Scroll of {spell.name}" not in unit._base_inventory:
        return None
    bonus = 2 if unit.race["name"] == "Kobold" and "blood" in spell.sources else 0
    dice_qty = (2 if "gnome_magic_excitement" in unit.talents["racial"]
                and unit.study_progress == 0 else 1)
    unit.study_progress += max(0, data.roll(dice_qty, 20) + unit.mod_intelligence + bonus)
    if unit.study_progress >= points_to_learn(spell):
        unit.spells_known.append(spell.id)
        unit.study_target = None
        unit.study_progress = 0
        return f"{unit.name} masters the spell {spell.name}!"
    return None
