"""Unit: a randomly generated GARTOK character -- the persistent *character*.

Ported from the original generator's `personagem.py` and extended with the
tactical-combat derivatives (speed in squares, HP, AC, carry, ...).

This is the roster entity: race / occupation / attributes / alignment / gold /
hunger / the equipped loadout (`equipped_weapon`, `equipped_offhand`,
`_base_inventory`). It is what `persist.py` saves and the guild screens edit.

Everything that only exists *inside a fight* -- hit points, action points,
position, status, conditions, which hand holds what right now -- lives on a
`combatant.Combatant`, which wraps one of these for the duration of a battle
(see `battle.py`). A few read-only combat previews (`ac`, `weapon`, `load`, ...)
stay here so the roster screens can show a character at a glance without
spinning up a Combatant.

- The effect of racial abilities comes from `abilities.py`.
- `self.armor` = armor slot (starts empty, no armor data yet).
"""

import random
import uuid

from . import abilities, data, economy, items, magic, names, talents
from .data import ATTRIBUTES, mod, roll
from .unit_derive import DerivationMixin
from .unit_edit import EditMixin
from .unit_hunger import HungerMixin
from .unit_levels import LevelingMixin
from .unit_loadout import (  # noqa: F401 -- re-exported
    LoadoutMixin,
    distribute_load,
    flatten_pack,
    pack_from_raw,
    stack_add,
    stack_take,
)
from .unit_poison import PoisonMixin


class Unit(HungerMixin, LevelingMixin, EditMixin, DerivationMixin, LoadoutMixin, PoisonMixin):
    def __init__(self, team, name=None, race=None):
        self.team = team                     # "player" / "enemy" (vestigial: Combatant owns the real one)
        self.uid = uuid.uuid4().hex          # stable identity: survives save/load, outlives the name
        self.recruited_by = None             # uid of the guild member who recruited this one, or None
        self.talents = {t: [] for t in talents.TRACKS}   # picked talent ids per XP track
        self.poisons = {}                    # poison id -> {"level", "hours", "dc"} (see unit_poison.py)
        self.antidote_cooldown = 0           # hours until another Antidote may be used
        self._level_hp_rolls = []            # 1dHD per mean-level gained (see collect_levels)
        self.magic_source = None
        self.spells_known = []
        self.study_target = None
        self.study_progress = 0
        self.recipes = []
        self.crafting_target = None
        self.crafting_progress = 0
        self.craft_bonuses = {}
        self._roll_attributes()
        if race is not None:                 # a specific body (e.g. encounters' race_pool draw)
            self.race = dict(race)
            self._configure_race()
        else:
            self._apply_race()
        if self.race["kind"] == "beast":
            self._apply_beast()
        else:
            self._apply_occupation()
        self.alignment = data.roll_alignment()
        purse = roll(*economy.STARTING_WEALTH_DICE)       # copper coins -- lives on the character, as a pack item
        self.money = 0 if self.race["kind"] == "beast" else purse
        self.crime = 0                                  # rap sheet; the guard tests it at a jurisdiction node (justice.py)
        self.unfed_days = 0                            # consecutive days without a meal
        self.sick = False                              # food poisoning
        self.medicine_attempted_today = False          # if a medkit treatment was attempted today
        self.treated = False                           # if a medkit treatment succeeded (cures after 8h rest)
        self.share_food = True                         # pools rations for hungry guild-mates
        self.combat_xp = 0                             # +1 per enemy this character downs in a fight
        self.work_hours = 0                            # lifetime hours of day-labour (see work_xp)
        self.bio = ""                                  # free-text backstory (authored NPCs; editable in the creator)
        self.arena_title = False                       # holds the arena's "Champion of the Pit" (see arena.py)
        self._hp_roll = None                          # 1dHD, rolled once in _derive_combat
        self._hp_override = None                       # sandbox: a hand-set HP max that wins over the derived one
        self.natural_armor = 0                         # flat AC from the body itself (sandbox-set; see _derive_ac)
        self._racial_override = None                   # sandbox: a pinned racial level (hit dice + racial picks), else derived
        self.equipped_tongue = None                    # Grippli Tongue slot: a 1-handed weapon, an extra limb (see the `tongue` talent)
        self.group_overextension = 0                    # set by Guild._sync_leadership, not persisted -- see group.py
        self.consecutive_rest_hours = 0
        self.last_daily_luck_day = 0

        self._auto_name = name is None
        self.name = name or names.random_name()
        self.token = self.race["token"]
        self.portrait_id = int(self.uid[:8], 16)

        self._derive_combat()
        self._sync_dictionary_recipes()

    @classmethod
    def from_save(cls, d):
        """Rebuild a persisted player unit (see `persist.unit_to_dict`).

        Bypasses `__init__` so nothing is re-rolled: the saved raw attributes,
        rolled `hp_max` and sorted `languages` are restored verbatim, only the
        deterministic derivations run again.
        """
        u = cls.__new__(cls)
        u.team = "player"
        u.uid = d.get("uid") or uuid.uuid4().hex     # back-fill: pre-uid saves get one now
        u.recruited_by = d.get("recruited_by")
        u.talents = {t: list(d.get("talents", {}).get(t, [])) for t in talents.TRACKS}
        u.poisons = {pid: dict(st) for pid, st in d.get("poisons", {}).items()}
        u.antidote_cooldown = d.get("antidote_cooldown", 0)
        u._level_hp_rolls = list(d.get("level_hp_rolls", []))
        u.base_attributes = dict(d["base_attributes"])
        for a in ATTRIBUTES:
            setattr(u, a, u.base_attributes[a])
        u._age_base = d["age_base"]
        u.magic_source = None                            # set for real below; _configure_race needs it to exist first
        u.spells_known = []
        u.race = data.race_by_name(d["race"])
        u._configure_race()
        u.age = d.get("age", u.age)                     # creator-set age wins; older saves fall back to the derived one
        u.languages = [l for l in d["languages"] if l]   # keep the saved picks, don't re-sort; drop blanks
        u.occupation = data.occupation_by_name(d["occupation"])
        if u.race["kind"] == "beast":
            u._apply_beast()
        else:
            u._configure_occupation()
        u._base_inventory = pack_from_raw(d["inventory"])
        u.locked_items = dict(d.get("locked_items", {}))
        u.equipped_weapon = d.get("equipped_weapon", u.occupation["weapon"])
        u.equipped_offhand = d.get("equipped_offhand")
        u.equipped_armor = d.get("equipped_armor")
        u.equipped_tongue = d.get("equipped_tongue")
        u.alignment = d["alignment"]
        if "gold" in d:                                  # pre-coin-item saves kept the purse as a number
            u.money = d["gold"]
        u.crime = d.get("crime", 0)
        u.unfed_days = d.get("unfed_days", 0)
        u.sick = d.get("sick", False)
        u.medicine_attempted_today = d.get("medicine_attempted_today", False)
        u.treated = d.get("treated", False)
        if "first_aid_charges" in d:                     # older saves kept the charges on the character
            u.first_aid_charges = d["first_aid_charges"]
        if "quiver_charges" in d:
            u.quiver_charges = d["quiver_charges"]
        u.consecutive_rest_hours = d.get("consecutive_rest_hours", 0)
        u.last_daily_luck_day = d.get("last_daily_luck_day", 0)
        u.share_food = d.get("share_food", True)
        u.combat_xp = d.get("combat_xp", 0)
        u.work_hours = d.get("work_hours", 0)
        u.bio = d.get("bio", "")
        u.arena_title = d.get("arena_title", False)
        
        u.magic_source = d.get("magic_source")
        u.spells_known = list(d.get("spells_known", []))
        u.study_target = d.get("study_target")
        u.study_progress = d.get("study_progress", 0)
        u.recipes = list(d.get("recipes", []))
        u.crafting_target = d.get("crafting_target")
        u.crafting_progress = d.get("crafting_progress", 0)
        u.craft_bonuses = dict(d.get("craft_bonuses", {}))

        u._auto_name = d["auto_name"]
        u.name = d["name"]
        u.group_overextension = 0                        # recomputed by Guild._sync_leadership on load
        u.token = u.race["token"]
        pid = d.get("portrait_id")                       # old saves: derive it like __init__ -- hash() changes per run
        u.portrait_id = int(u.uid[:8], 16) if pid is None else pid
        u._hp_roll = d.get("hp_roll")
        u._hp_override = d.get("hp_override")            # creator-set HP max, or None
        u.natural_armor = d.get("natural_armor", 0)
        u._racial_override = d.get("racial_override")    # creator-pinned racial level, or None
        u.dormant = d.get("dormant", False)
        u.awareness_radius = d.get("awareness_radius", 0)
        if u._hp_roll is None:                           # pre-hunger save: back it out of hp_max
            u._hp_roll = max(1, d["hp_max"] - mod(u.constitution) - u._ability.hp_max)
        u._derive_combat()                               # rebuilds hp_max from _hp_roll
        u.hp = d.get("hp", u.hp_max)
        u._sync_dictionary_recipes()
        return u

    def _sync_dictionary_recipes(self):
        """Ensures the unit knows the crafting recipe for a dictionary of any language they speak."""
        self.recipes = [r for r in self.recipes if r != "Dictionary of "]
        for lang in self.languages:
            recipe = f"Dictionary of {lang}"
            if recipe not in self.recipes:
                self.recipes.append(recipe)

    @property
    def ability(self):
        return self._ability
    # ------------------------------------------------------------------ #
    # generation                                                         #
    # ------------------------------------------------------------------ #
    def _roll_attributes(self):
        # keep the raw 3d6 roll so the draft can re-apply a different race
        self.base_attributes = {a: roll(3, 6) for a in ATTRIBUTES}
        for a in ATTRIBUTES:
            setattr(self, a, self.base_attributes[a])
        self._age_base = random.randint(1, 100)

    def _apply_attributes(self):
        """Each attribute score = raw 3d6 roll + racial mod + talent bonus.
        Rebuilt from scratch so it is safe to re-run when a talent is picked."""
        for a, m in zip(ATTRIBUTES, self.race["mods"]):
            setattr(self, a, self.base_attributes[a] + m + self.talent_bonus("attr", a)
                    - self.poison_penalty(a))
        if getattr(self, "sick", False):
            self.constitution -= 4
            self.strength -= 2
            self.dexterity -= 2
            self.intelligence -= 2
            self.wisdom -= 2
            self.charisma -= 2

    def _apply_race(self):
        self.race = data.roll_race()
        self._configure_race()

    def _configure_race(self):
        self._apply_attributes()
        self.ability_id = self.race["ability"]
        self._ability = abilities.get(self.ability_id)
        self.size = self.race["size"]
        self.footprint = data.SIZES[self.size]["footprint"]   # squares per side (Large = 2 -> 2x2)
        self.languages = [self.race["language"]] if self.race["language"] else []   # the dead speak none
        for _ in range(self._ability.extra_languages):
            extras = [i for i in data.LANGUAGES if i not in self.languages]
            if extras:
                self.languages.append(random.choice(extras))
        self.age = int(round(self._age_base * self.race["age_mult"]))

        if self.race["name"] == "Gnome":
            self.magic_source = "nature"
            if not self.spells_known:
                nature_spells = [s for s in magic.SPELLS.values() if "nature" in s.sources and s.level == 0]
                if nature_spells:
                    self.spells_known.append(random.choice(nature_spells).id)
        elif self.race["name"] == "Kobold":
            self.magic_source = "blood"

    def _apply_occupation(self):
        self.occupation = data.roll_occupation()
        self._configure_occupation()

    def _apply_beast(self):
        """A beast has no job -- it fights with its own body, not a rolled
        weapon (see `combatant.unarmed`/`data.UNARMED_ATTACK`; the extra bite
        comes off its racial ability's `melee_damage`, like `_configure_race`
        already wires up for anything else the ability grants)."""
        self.occupation = dict(data.BEAST_OCCUPATION)
        self.equipped_weapon = None
        self.equipped_offhand = None
        self.equipped_armor = None
        self.item = None
        self.starting_creature = None
        self._base_inventory = []
        self.locked_items = {}

    def _configure_occupation(self):
        # A weapon is just a held item: `equipped_weapon` is the one in the weapon
        # hand (None = fighting unarmed); spares ride in `_base_inventory`.
        self.locked_items = {}
        self.equipped_weapon = self.occupation["weapon"]
        self.equipped_offhand = None                  # off hand: a torch or a light source
        self.equipped_armor = None                    # body slot: bought at the market
        self.item = self.occupation["item"]
        if self.item in data.CREATURE_ITEMS:         # e.g. the Shepherd's sheep
            self.starting_creature = self.item
            self._base_inventory = []
        else:
            self.starting_creature = None
            if self.item == "Scroll":
                nature_spells = [s for s in magic.SPELLS.values() if "nature" in s.sources and s.level == 0]
                if nature_spells:
                    self.item = f"Scroll of {random.choice(nature_spells).name}"
            elif self.item == "Dictionary":
                foreign = [l for l in data.LANGUAGES if l not in self.languages]
                if foreign:
                    self.item = f"Dictionary of {random.choice(foreign)}"
            self._base_inventory = [items.create_instance(self.item, 1)]

    @property
    def title(self):
        if getattr(self, "arena_title", False):
            return "Champion of the Pit"
        return ""

    @property
    def full_name(self):
        t = self.title
        return f"{self.name}, {t}" if t else self.name
