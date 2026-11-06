"""Magic system registry and learning math."""

import random
from dataclasses import dataclass

from . import data, economy, i18n, items


@dataclass(frozen=True)
class Spell:
    id: str
    level: int
    sources: tuple

    @property
    def name(self):
        return i18n.name("spell", self.id)

    @property
    def scroll_name(self):
        """The id of the scroll item that teaches it: the item of the registry whose `spell_id` this is."""
        return _SCROLLS.get(self.id)


_SCROLLS = {d.spell_id: d.name for d in items.all_items().values() if d.spell_id}

SPELLS = {
    "light_globe": Spell("light_globe", 0, ("nature", "blood", "faith")),
    "magic_missile": Spell("magic_missile", 0, ("nature", "blood", "faith")),
    "floating_disk": Spell("floating_disk", 0, ("nature", "blood", "faith")),
    "grasping_roots": Spell("grasping_roots", 0, ("nature",)),
    "hex": Spell("hex", 0, ("blood",)),
    "spare_the_dying": Spell("spare_the_dying", 0, ("faith",)),
    "sleep": Spell("sleep", 1, ("nature", "blood", "faith")),
    "water_jet": Spell("water_jet", 1, ("nature",)),
    "dragonfire": Spell("dragonfire", 1, ("blood",)),
    "healing_touch": Spell("healing_touch", 1, ("faith",)),
    "invisibility": Spell("invisibility", 2, ("nature", "blood", "faith")),
    "raise_dead": Spell("raise_dead", 2, ("faith",)),
}

SOURCES = ("nature", "blood", "faith")
MAGIC_BLOOD_CHANCE = 0.05


def roll_magic_blood(unit):
    """Whether `unit` was born with magic in the blood (the Blood rite tests it, `rite.py`): a
    Kobold always (Blood Magic), anyone else at `MAGIC_BLOOD_CHANCE`. A private roll seeded by
    the uid, so making a character does not move the shared dice."""
    if "Kobold" in unit.race.get("races", (unit.race["name"],)):
        return True
    return random.Random(f"{unit.uid}:magic_blood").random() < MAGIC_BLOOD_CHANCE

@dataclass(frozen=True)
class Language:
    id: str
    name: str

@dataclass(frozen=True)
class Recipe:
    """A recipe paper's lesson: `id` is the study target (`recipe:<Recipe name>`), `recipe` the crafting
    recipe it unlocks and `paper` the item it is read from."""
    id: str
    recipe: str
    level: int
    paper: str

    @property
    def name(self):
        return i18n.name("item", self.paper)


RECIPE_PREFIX = "recipe:"
_PAPERS = {d.recipe_id: d for d in items.all_items().values() if d.recipe_id}


def _item_str(item):
    if item is None:
        return ""
    return getattr(item, "name", str(item))

def spell_for_scroll(item_name):
    """The Spell a `Scroll of <Name>` item names, or None (not a scroll, or
    no spell matches)."""
    name = _item_str(item_name)
    return next((s for s in SPELLS.values() if name == s.scroll_name), None)

def language_for_dictionary(item_name):
    """The Language a `Dictionary of <Name>` item names, or None (not a
    dictionary, or the name isn't a language in the world)."""
    name = _item_str(item_name)
    if not name or not name.startswith("Dictionary of "):
        return None
    lang_name = name[len("Dictionary of "):]
    return Language(lang_name, lang_name) if lang_name in data.LANGUAGES else None

def recipe_for_paper(item_name):
    """The Recipe a `Recipe of <Name>` paper teaches, or None (not a paper)."""
    name = _item_str(item_name)
    paper = next((d for d in _PAPERS.values() if d.name == name), None)
    return None if paper is None else _recipe_of(paper)


def recipe_papers():
    """Every recipe paper's lesson, in registry order."""
    return [_recipe_of(d) for d in _PAPERS.values()]


def recipe_of(target_id):
    """The Recipe a study target id (`recipe:<Name>`) names, or None."""
    if not str(target_id).startswith(RECIPE_PREFIX):
        return None
    paper = _PAPERS.get(target_id[len(RECIPE_PREFIX):])
    return None if paper is None else _recipe_of(paper)


def _recipe_of(paper):
    return Recipe(f"{RECIPE_PREFIX}{paper.recipe_id}", paper.recipe_id, paper.recipe_level, paper.name)


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

def can_study(unit, target_id, group=None):
    """True if `unit` could study `target_id` (a spell id, a language name or `recipe:<Name>`) now: it is not yet
    known and its Scroll / Dictionary / Recipe paper is carried by the unit or, with `group`, by anyone in it."""
    spell = SPELLS.get(target_id)
    recipe = recipe_of(target_id)
    if spell is not None:
        learnable = can_study_spell(unit, spell)
    elif recipe is not None:
        learnable = recipe.recipe not in unit.recipes
    else:
        learnable = target_id in data.LANGUAGES and target_id not in unit.languages
    return learnable and _has_study_item(unit, study_item_name(target_id), group=group)


def study_item_name(target_id):
    """The pack item a study target is read from: a scroll for a spell id, a recipe paper for a
    recipe, a dictionary for a language."""
    spell = SPELLS.get(target_id)
    if spell is not None:
        return spell.scroll_name
    recipe = recipe_of(target_id)
    return recipe.paper if recipe is not None else f"Dictionary of {target_id}"


def begin_study(unit, target_id, mates=()):
    """Set `unit` studying `target_id`. The study item is pulled into the student's
    own pack -- one copy peeled off a mate's stack if they don't hold it -- and
    locked there so redistributing the load doesn't carry it off. Returns the
    mate it came from, or None. The points made on any target stay with it: going
    back to one picks up where it was left."""
    if unit.study_target and unit.study_target != target_id:
        end_study(unit)
    unit.study_target = target_id
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
    """Stop `unit` studying: clear the target (its points are kept) and release the lock
    `begin_study` put on the study item."""
    if unit.study_target:
        name = study_item_name(unit.study_target)
        if unit.locked_of(name) > 1:
            unit.locked_items[name] -= 1
        else:
            unit.locked_items.pop(name, None)
    unit.study_target = None


def progress_study(unit, group=None):
    """One day of `unit` studying at a tavern's "study" garrison job: charge
    the daily rent, then roll progress toward `study_target` -- a spell id
    (needs a school in `magic_sources` and a `Scroll of <Spell>`), a recipe (`recipe:<Name>`, needs its
    paper) or a language name (needs a `Dictionary of <Language>`), whichever `study_target` names. Returns an
    event string worth telling the player about, or None for a quiet day (no
    target set, no matching item, not initiated -- rent still comes due)."""
    if not unit.study_target:
        return None
    cost = economy.TAVERN_STUDY_COST_PER_DAY
    stores = getattr(group, "stores", ()) if group else ()
    mates = [m for m in (*group.members, *stores) if m is not unit] if group else []
    if unit.money + sum(m.money for m in mates) < cost:
        return i18n.t("magic.could_not_afford_rent_to", name=unit.name)
    own = min(unit.money, cost)
    unit.money -= own
    economy.charge_richest_first(mates, cost - own)
    spell = SPELLS.get(unit.study_target)
    if spell is not None:
        return _progress_spell(unit, spell, group=group)
    recipe = recipe_of(unit.study_target)
    if recipe is not None:
        return _progress_recipe(unit, recipe, group=group)
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
    if not can_study_spell(unit, spell) or not _has_study_item(unit, spell.scroll_name, group=group):
        return None
    bonus = 2 if "Kobold" in unit.race.get("races", (unit.race["name"],)) and "blood" in spell.sources else 0
    dice_qty = (2 if "gnome_magic_excitement" in unit.talents["racial"]
                and spell.id not in unit.study_progress else 1)
    points = unit.study_progress.get(spell.id, 0) + max(0, data.roll(dice_qty, 20) + unit.mod_intelligence + bonus)
    unit.study_progress[spell.id] = points
    if points >= points_to_learn(spell.level):
        unit.study_progress.pop(spell.id)
        unit.spells_known.append(spell.id)
        end_study(unit)
        unit.magic_xp += study_xp(spell)
        unit.collect_levels()
        return i18n.t("magic.masters_spell_magic_xp", name=unit.name, spell=spell.name, study_xp=study_xp(spell))
    return None

def _progress_language(unit, language, group=None):
    if not _has_study_item(unit, f"Dictionary of {language}", group=group):
        return None
    bonus = unit.talent_bonus("language_study")
    points = unit.study_progress.get(language, 0) + max(0, data.roll(1, 20) + unit.mod_intelligence + bonus)
    unit.study_progress[language] = points
    if points >= points_to_learn(0):     # same threshold as a level-0 spell
        unit.study_progress.pop(language)
        unit.languages.append(language)
        unit._sync_dictionary_recipes()
        end_study(unit)
        return i18n.t("magic.learns_to_speak", name=unit.name, language=language)
    return None

def _progress_recipe(unit, recipe, group=None):
    if recipe.recipe in unit.recipes or not _has_study_item(unit, recipe.paper, group=group):
        return None
    points = unit.study_progress.get(recipe.id, 0) + max(0, data.roll(1, 20) + unit.mod_intelligence)
    unit.study_progress[recipe.id] = points
    if points >= points_to_learn(recipe.level):
        unit.study_progress.pop(recipe.id)
        unit.recipes.append(recipe.recipe)
        end_study(unit)
        return i18n.t("magic.learns_recipe", name=unit.name, recipe=i18n.name("item", recipe.recipe))
    return None
