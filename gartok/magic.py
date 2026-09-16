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

@dataclass(frozen=True)
class Language:
    id: str
    name: str

def spell_for_scroll(item_name):
    """The Spell a `Scroll of <Name>` item names, or None (not a scroll, or
    no spell matches)."""
    return next((s for s in SPELLS.values() if item_name == f"Scroll of {s.name}"), None)

def language_for_dictionary(item_name):
    """The Language a `Dictionary of <Name>` item names, or None (not a
    dictionary, or the name isn't a language in the world)."""
    if not item_name or not item_name.startswith("Dictionary of "):
        return None
    name = item_name[len("Dictionary of "):]
    return Language(name, name) if name in data.LANGUAGES else None

def study_difficulty(level):
    """The DC to learn something at this level. Daily rolls check against this
    average to accumulate points."""
    return 15 + level

def points_to_learn(level):
    """Total points needed to master something at this level. (15+lvl) * (7 days per level + 7)."""
    weeks = level + 1
    return study_difficulty(level) * (weeks * 7)

def progress_study(unit):
    """One day of `unit` studying at a tavern's "study" garrison job: charge
    the daily rent, then roll progress toward `study_target` -- a spell id
    (needs `magic_source` and a `Scroll of <Spell>`) or a language name (needs
    a `Dictionary of <Language>`), whichever `study_target` names. Returns an
    event string worth telling the player about, or None for a quiet day (no
    target set, no matching item, not initiated -- rent still comes due)."""
    if unit.gold < economy.TAVERN_STUDY_COST_PER_DAY:
        return f"{unit.name} could not afford the rent to study."
    unit.gold -= economy.TAVERN_STUDY_COST_PER_DAY
    spell = SPELLS.get(unit.study_target)
    if spell is not None:
        return _progress_spell(unit, spell)
    if unit.study_target in data.LANGUAGES:
        return _progress_language(unit, unit.study_target)
    return None

def _progress_spell(unit, spell):
    if not unit.magic_source or f"Scroll of {spell.name}" not in unit._base_inventory:
        return None
    bonus = 2 if unit.race["name"] == "Kobold" and "blood" in spell.sources else 0
    dice_qty = (2 if "gnome_magic_excitement" in unit.talents["racial"]
                and unit.study_progress == 0 else 1)
    unit.study_progress += max(0, data.roll(dice_qty, 20) + unit.mod_intelligence + bonus)
    if unit.study_progress >= points_to_learn(spell.level):
        unit.spells_known.append(spell.id)
        unit.study_target = None
        unit.study_progress = 0
        return f"{unit.name} masters the spell {spell.name}!"
    return None

def _progress_language(unit, language):
    if f"Dictionary of {language}" not in unit._base_inventory:
        return None
    unit.study_progress += max(0, data.roll(1, 20) + unit.mod_intelligence)
    if unit.study_progress >= points_to_learn(0):     # same threshold as a level-0 spell
        unit.languages.append(language)
        unit.study_target = None
        unit.study_progress = 0
        return f"{unit.name} learns to speak {language}!"
    return None
