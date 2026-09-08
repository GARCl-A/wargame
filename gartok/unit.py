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

from . import abilities, data, economy
from .data import mod, roll

ATTRIBUTES = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]


class Unit:
    def __init__(self, team, name=None):
        self.team = team                     # "player" / "enemy" (vestigial: Combatant owns the real one)
        self.uid = uuid.uuid4().hex          # stable identity: survives save/load, outlives the name
        self.recruited_by = None             # uid of the guild member who recruited this one, or None
        self._roll_attributes()
        self._apply_race()
        self._apply_occupation()
        self.alignment = data.roll_alignment()
        self.gold = roll(*economy.STARTING_WEALTH_DICE)   # copper coins -- lives on the character
        self.unfed_days = 0                            # consecutive days without a meal
        self.combat_xp = 0                             # +1 per enemy this character downs in a fight
        self._hp_roll = None                          # 1dHD, rolled once in _derive_combat

        self._auto_name = name is None
        self.name = name or f"{self.race['name']} {self.occupation['name']}"
        self.token = self.race["token"]

        self._derive_combat()

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
        u.base_attributes = dict(d["base_attributes"])
        for a in ATTRIBUTES:
            setattr(u, a, u.base_attributes[a])
        u._age_base = d["age_base"]
        u.race = data.race_by_name(d["race"])
        u._configure_race()
        u.languages = list(d["languages"])              # keep the saved picks, don't re-sort
        u.occupation = data.occupation_by_name(d["occupation"])
        u._configure_occupation()
        u._base_inventory = list(d["inventory"])
        u.equipped_weapon = d.get("equipped_weapon", u.occupation["weapon"])
        u.equipped_offhand = d.get("equipped_offhand")
        u.equipped_armor = d.get("equipped_armor")
        u.alignment = d["alignment"]
        u.gold = d.get("gold", 0)
        u.unfed_days = d.get("unfed_days", 0)
        u.combat_xp = d.get("combat_xp", 0)
        u._auto_name = d["auto_name"]
        u.name = d["name"]
        u.token = u.race["token"]
        u._hp_roll = d.get("hp_roll")
        if u._hp_roll is None:                           # pre-hunger save: back it out of hp_max
            u._hp_roll = max(1, d["hp_max"] - mod(u.constitution) - u._ability.hp_max)
        u._derive_combat()                               # rebuilds hp_max from _hp_roll
        return u

    @property
    def ability(self):
        return self._ability

    # ------------------------------------------------------------------ #
    # hunger: one meal a day, or the body starts giving out               #
    #   (see GARTOK-regras.md; the Leshy "Autotrofo" is exempt)           #
    # ------------------------------------------------------------------ #
    @property
    def hunger_level(self):
        """0 fed · 1 com fome · 2 esfomeado · 3 morrendo de fome."""
        if self._ability.id == "autotroph":
            return 0
        return min(self.unfed_days, 3)

    @property
    def hunger_attribute_penalty(self):
        return (0, -2, -4, -4)[self.hunger_level]

    @property
    def hunger_label(self):
        return ("", "com fome", "esfomeado", "morrendo de fome")[self.hunger_level]

    @property
    def incapacitated(self):
        """Collapsed from hunger -- cannot be sent into a fight."""
        return self.hunger_level >= 3

    def consume_daily_food(self):
        """Resolve one day's meal: eat a ration from the pack if there is one,
        else go hungrier. Returns 'ate' | 'hungry' | 'dead'. The caller re-derives
        combat stats and clears the dead from the roster."""
        if self._ability.id == "autotroph":
            return "ate"
        food = next((it for it in self._base_inventory if it in data.FOOD_ITEMS), None)
        if food is not None:
            self._base_inventory.remove(food)
            self.unfed_days = 0
            return "ate"
        self.unfed_days += 1
        return "dead" if self.unfed_days >= data.STARVATION_DEATH_DAYS else "hungry"

    # ------------------------------------------------------------------ #
    # generation                                                         #
    # ------------------------------------------------------------------ #
    def _roll_attributes(self):
        # keep the raw 3d6 roll so the draft can re-apply a different race
        self.base_attributes = {a: roll(3, 6) for a in ATTRIBUTES}
        for a in ATTRIBUTES:
            setattr(self, a, self.base_attributes[a])
        self._age_base = random.randint(1, 100)

    def _apply_race(self):
        self.race = data.roll_race()
        self._configure_race()

    def _configure_race(self):
        for a, m in zip(ATTRIBUTES, self.race["mods"]):
            setattr(self, a, self.base_attributes[a] + m)
        self.ability_id = self.race["ability"]
        self._ability = abilities.get(self.ability_id)
        self.size = self.race["size"]
        self.footprint = data.SIZES[self.size]["footprint"]   # squares per side (Large = 2 -> 2x2)
        self.languages = [self.race["language"]]
        for _ in range(self._ability.extra_languages):
            extras = [i for i in data.LANGUAGES if i not in self.languages]
            if extras:
                self.languages.append(random.choice(extras))
        self.age = int(round(self._age_base * self.race["age_mult"]))

    def _apply_occupation(self):
        self.occupation = data.roll_occupation()
        self._configure_occupation()

    def _configure_occupation(self):
        # A weapon is just a held item: `equipped_weapon` is the one in the weapon
        # hand (None = fighting unarmed); spares ride in `_base_inventory`.
        self.equipped_weapon = self.occupation["weapon"]
        self.equipped_offhand = None                  # off hand: only a torch fits, for now
        self.equipped_armor = None                    # body slot: bought at the market
        self.item = self.occupation["item"]
        if self.item in data.CREATURE_ITEMS:         # e.g. the Shepherd's sheep
            self.starting_creature = self.item
            self._base_inventory = []
        else:
            self.starting_creature = None
            self._base_inventory = [self.item]

    # ------------------------------------------------------------------ #
    # draft editing: swap race / occupation before the battle            #
    # ------------------------------------------------------------------ #
    def set_race(self, name):
        self.race = data.race_by_name(name)
        self._hp_roll = None                  # new hit die -> re-roll HP
        self._configure_race()
        self._after_edit()

    def set_occupation(self, name):
        self.occupation = data.occupation_by_name(name)
        self._configure_occupation()
        self._after_edit()

    def _after_edit(self):
        if self._auto_name:
            self.name = f"{self.race['name']} {self.occupation['name']}"
        self.token = self.race["token"]
        self._derive_combat()

    # ------------------------------------------------------------------ #
    # combat derivation                                                  #
    # ------------------------------------------------------------------ #
    def _derive_combat(self):
        pen = self.hunger_attribute_penalty          # 0 / -2 / -4, hits every attribute
        ab = self._ability

        # Carry capacity (kg). A normal person (FOR 10 -> mod 0, Medio) hauls
        # 15 kg freely and 35 kg at a stagger; every point of FOR mod is +4 / +6.
        # Judged from the hunger-adjusted Strength; encumbrance then penalises
        # FOR/DES/speed -- it is the consequence of carrying too much, so it must
        # not feed back and shrink this threshold. An ability may raise the size
        # bracket used here and nowhere else -- the Goliath carries as Large.
        cm = data.SIZES[ab.carry_size or self.size]["carry"]
        str_carry = mod(self.strength + pen)
        self.carry_normal = max(1, round((str_carry * 4 + 15) * cm))
        self.carry_max = max(2, round((str_carry * 6 + 35) * cm))
        self.encumbered = self.load > self.carry_normal
        enc = -2 if self.encumbered else 0           # -2 FOR and -2 DES while overloaded

        for a in ATTRIBUTES:
            extra = enc if a in ("strength", "dexterity") else 0
            setattr(self, f"mod_{a}", mod(getattr(self, a) + pen + extra))

        # Unarmed attack (die comes from the creature's size)
        self.unarmed_damage = data.UNARMED_ATTACK.get(self.size, (1, 2))

        # HP: 1dHD rolled once, kept in _hp_roll so re-deriving (e.g. after a
        # hunger tick) never re-rolls. Starving (tier 2+) caps it at 1.
        if self._hp_roll is None:
            self._hp_roll = roll(1, self.race["hd"])
        self.hp_max = max(1, self._hp_roll + self.mod_constitution + ab.hp_max)
        if self.hunger_level >= 2:
            self.hp_max = 1

        # AC base: 10 + Dexterity + worn armor. Armor caps how much Dexterity
        # still counts (heavier plate caps it harder). Racial natural bonus and
        # Defend enter via condition on the Combatant.
        armor = self.armor
        dex_ac = self.mod_dexterity
        if armor is not None and armor["max_dex"] is not None:
            dex_ac = min(dex_ac, armor["max_dex"])
        self.ac_base = 10 + dex_ac + (armor["ac"] if armor else 0)
        self.ac_natural = ab.ac_natural

        # Mental Defense (target of the Demoralize action; AC-like, uses Wisdom)
        self.mental_defense_base = 10 + self.mod_wisdom

        # Speed (squares). Heavy armor shaves squares off; being overloaded costs
        # one more. Floored at 1.
        self.speed = data.squares(data.SIZES[self.size]["speed"]) + ab.speed
        if armor is not None and armor["speed"]:
            self.speed = max(1, self.speed - armor["speed"])
        if self.encumbered:
            self.speed = max(1, self.speed - 1)

        # Damage reduction
        self.dr = ab.damage_reduction

    # ------------------------------------------------------------------ #
    # roster management: shuffling items between the two hands and the   #
    # pack. A weapon is an item; the weapon hand holds one (1-2 hands),  #
    # the off hand a torch. `equipped_weapon` / `equipped_offhand` are   #
    # the persistent loadout every battle re-seeds a Combatant from.     #
    # ------------------------------------------------------------------ #
    @staticmethod
    def is_weapon(name):
        return name in data.WEAPONS

    @staticmethod
    def fits_offhand(name):
        return name == data.TORCH_ITEM

    @staticmethod
    def fits_armor(name):
        return name in data.ARMOR

    def give_to_hand(self, name):
        """Wield `name`; the weapon already held goes to the pack. A 2-handed
        weapon also bumps whatever was in the off hand. No-op if not a weapon."""
        if not self.is_weapon(name):
            return False
        if self.equipped_weapon:
            self._base_inventory.append(self.equipped_weapon)
        self.equipped_weapon = name
        if data.WEAPONS[name]["hands"] >= 2 and self.equipped_offhand:
            self._base_inventory.append(self.equipped_offhand)
            self.equipped_offhand = None
        return True

    def give_to_offhand(self, name):
        if not self.fits_offhand(name):
            return False
        if self.equipped_offhand:
            self._base_inventory.append(self.equipped_offhand)
        self.equipped_offhand = name
        return True

    def give_to_pack(self, name):
        self._base_inventory.append(name)

    def take_from_hand(self):
        name, self.equipped_weapon = self.equipped_weapon, None
        return name

    def take_from_offhand(self):
        name, self.equipped_offhand = self.equipped_offhand, None
        return name

    def give_to_armor(self, name):
        """Don `name`; whatever was worn goes back to the pack. Armor changes the
        derived AC and speed, so re-derive. No-op if `name` is not armor."""
        if not self.fits_armor(name):
            return False
        if self.equipped_armor:
            self._base_inventory.append(self.equipped_armor)
        self.equipped_armor = name
        self._derive_combat()
        return True

    def take_from_armor(self):
        name, self.equipped_armor = self.equipped_armor, None
        self._derive_combat()
        return name

    def take_from_pack(self, idx):
        return self._base_inventory.pop(idx)

    # ------------------------------------------------------------------ #
    # combat previews: read-only views of the equipped loadout, so the   #
    # roster screens can show a character without a Combatant. Bonuses   #
    # from conditions / Defend are NOT here -- those need the Combatant. #
    # ------------------------------------------------------------------ #
    @property
    def weapon_name(self):
        return self.equipped_weapon

    @property
    def weapon(self):
        return data.WEAPONS.get(self.equipped_weapon)

    @property
    def armor_name(self):
        return self.equipped_armor

    @property
    def armor(self):
        """The worn armor's stat dict (`ac` / `max_dex` / `speed` / `weight`), or None."""
        return data.ARMOR.get(self.equipped_armor)

    @property
    def ranged(self):
        """Wields a weapon that fires at range (the crossbow)."""
        w = self.weapon
        return bool(w) and w["range"] > 0

    @property
    def ac(self):
        return self.ac_base + self.ac_natural

    @property
    def mental_defense(self):
        return self.mental_defense_base

    @property
    def load(self):
        """Weight of the equipped loadout: weapon hand + off hand + pack + armor."""
        w = sum(data.item_weight(it) for it in self._base_inventory)
        if self.equipped_weapon:
            w += data.WEAPONS[self.equipped_weapon]["weight"]
        if self.equipped_offhand == data.TORCH_ITEM:
            w += data.TORCH_WEIGHT
        if self.armor:
            w += self.armor.get("weight", 0)
        return round(w, 1)
