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
    "water_jet": Spell("water_jet", "Water Jet", 1, ("nature",)),
    "dragonfire": Spell("dragonfire", "Dragonfire", 1, ("blood",)),
    "invisibility": Spell("invisibility", "Invisibility", 2, ("nature", "blood", "faith")),
    "raise_dead": Spell("raise_dead", "Raise Dead", 2, ("faith",)),
}

SOURCES = ("nature", "blood", "faith")

@dataclass(frozen=True)
class Language:
    id: str
    name: str

def _item_str(item):
    if item is None:
        return ""
    return getattr(item, "name", str(item))

def spell_for_scroll(item_name):
    """The Spell a `Scroll of <Name>` item names, or None (not a scroll, or
    no spell matches)."""
    name = _item_str(item_name)
    return next((s for s in SPELLS.values() if name == f"Scroll of {s.name}"), None)

def language_for_dictionary(item_name):
    """The Language a `Dictionary of <Name>` item names, or None (not a
    dictionary, or the name isn't a language in the world)."""
    name = _item_str(item_name)
    if not name or not name.startswith("Dictionary of "):
        return None
    lang_name = name[len("Dictionary of "):]
    return Language(lang_name, lang_name) if lang_name in data.LANGUAGES else None

def study_xp(spell):
    """Magic XP for studying `spell` to the end."""
    return spell.level + 1


def study_difficulty(level):
    """The DC to learn something at this level. Daily rolls check against this
    average to accumulate points."""
    return 15 + level

def points_to_learn(level):
    """Total points needed to master something at this level. (15+lvl) * (7 days per level + 7)."""
    weeks = level + 1
    return study_difficulty(level) * (weeks * 7)

def _has_study_item(unit, item_name, group=None):
    return unit.has_item(item_name) or (
        group is not None and any(m.has_item(item_name) for m in (*group.members, *group.wagons, *group.herd)))

def study_item_name(target_id):
    """The pack item a study target is read from: a scroll for a spell id, a
    dictionary for a language."""
    spell = SPELLS.get(target_id)
    return f"Scroll of {spell.name}" if spell is not None else f"Dictionary of {target_id}"


def begin_study(unit, target_id, mates=()):
    """Set `unit` studying `target_id`. The study item is pulled into the student's
    own pack -- one copy peeled off a mate's stack if they don't hold it -- and
    locked there so redistributing the load doesn't carry it off. Returns the
    mate it came from, or None."""
    unit.study_target = target_id
    unit.study_progress = 0
    name = study_item_name(target_id)
    donor = None
    if not unit.has_item(name):
        donor = next((m for m in mates if m is not unit and m.has_item(name)), None)
        if donor is not None:
            donor.remove_named(name)
            donor._derive_combat()
            unit.give_to_pack(name)
    if unit.has_item(name) and unit.locked_of(name) < 1:
        unit.locked_items[name] = 1
    return donor


def end_study(unit):
    """Stop `unit` studying: clear the target and progress, and release the lock
    `begin_study` put on the study item."""
    if unit.study_target:
        name = study_item_name(unit.study_target)
        if unit.locked_of(name) > 1:
            unit.locked_items[name] -= 1
        else:
            unit.locked_items.pop(name, None)
    unit.study_target = None
    unit.study_progress = 0


def progress_study(unit, group=None):
    """One day of `unit` studying at a tavern's "study" garrison job: charge
    the daily rent, then roll progress toward `study_target` -- a spell id
    (needs a school in `magic_sources` and a `Scroll of <Spell>`) or a language name (needs
    a `Dictionary of <Language>`), whichever `study_target` names. Returns an
    event string worth telling the player about, or None for a quiet day (no
    target set, no matching item, not initiated -- rent still comes due)."""
    if not unit.study_target:
        return None
    cost = economy.TAVERN_STUDY_COST_PER_DAY
    stores = getattr(group, "stores", ()) if group else ()
    mates = [m for m in (*group.members, *stores) if m is not unit] if group else []
    if unit.money + sum(m.money for m in mates) < cost:
        return f"{unit.name} could not afford the rent to study."
    own = min(unit.money, cost)
    unit.money -= own
    economy.charge_richest_first(mates, cost - own)
    spell = SPELLS.get(unit.study_target)
    if spell is not None:
        return _progress_spell(unit, spell, group=group)
    if unit.study_target in data.LANGUAGES:
        return _progress_language(unit, unit.study_target, group=group)
    return None


def rent_covered(group):
    """The studying members of `group` whose day's rent the group can pay, in
    member order: each pays from their own purse and the rest falls on their
    mates, so a penniless student rooms on a mate's coin instead of starving."""
    cost = economy.TAVERN_STUDY_COST_PER_DAY
    stores = getattr(group, "stores", ()) if group else ()
    purse = sum(m.money for m in (*group.members, *stores))
    covered = set()
    for m in group.members:
        if m.study_target and purse >= cost:
            covered.add(m)
            purse -= cost
    return covered


def casts(unit, spell):
    return any(s in spell.sources for s in unit.magic_sources)


def can_study_spell(unit, spell):
    """True if `unit` has an affinity matching `spell.sources` and has not already mastered it."""
    return casts(unit, spell) and spell.id not in unit.spells_known

def _progress_spell(unit, spell, group=None):
    if not can_study_spell(unit, spell) or not _has_study_item(unit, f"Scroll of {spell.name}", group=group):
        return None
    bonus = 2 if unit.race["name"] == "Kobold" and "blood" in spell.sources else 0
    dice_qty = (2 if "gnome_magic_excitement" in unit.talents["racial"]
                and unit.study_progress == 0 else 1)
    unit.study_progress += max(0, data.roll(dice_qty, 20) + unit.mod_intelligence + bonus)
    if unit.study_progress >= points_to_learn(spell.level):
        unit.spells_known.append(spell.id)
        end_study(unit)
        unit.magic_xp += study_xp(spell)
        unit.collect_levels()
        return f"{unit.name} masters the spell {spell.name}! (+{study_xp(spell)} magic XP)"
    return None

def _progress_language(unit, language, group=None):
    if not _has_study_item(unit, f"Dictionary of {language}", group=group):
        return None
    bonus = unit.talent_bonus("language_study")
    unit.study_progress += max(0, data.roll(1, 20) + unit.mod_intelligence + bonus)
    if unit.study_progress >= points_to_learn(0):     # same threshold as a level-0 spell
        unit.languages.append(language)
        unit._sync_dictionary_recipes()
        end_study(unit)
        return f"{unit.name} learns to speak {language}!"
    return None
