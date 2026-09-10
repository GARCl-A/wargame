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

from . import abilities, data, economy, names, progression, talents
from .data import mod, roll

ATTRIBUTES = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]


class Unit:
    def __init__(self, team, name=None):
        self.team = team                     # "player" / "enemy" (vestigial: Combatant owns the real one)
        self.uid = uuid.uuid4().hex          # stable identity: survives save/load, outlives the name
        self.recruited_by = None             # uid of the guild member who recruited this one, or None
        self.talents = {t: [] for t in talents.TRACKS}   # picked talent ids per XP track
        self._level_hp_rolls = []            # 1dHD per mean-level gained (see collect_levels)
        self._roll_attributes()
        self._apply_race()
        self._apply_occupation()
        self.alignment = data.roll_alignment()
        self.gold = roll(*economy.STARTING_WEALTH_DICE)   # copper coins -- lives on the character
        self.unfed_days = 0                            # consecutive days without a meal
        self.share_food = True                         # pools rations for hungry guild-mates
        self.combat_xp = 0                             # +1 per enemy this character downs in a fight
        self.work_hours = 0                            # lifetime hours of day-labour (see work_xp)
        self.bio = ""                                  # free-text backstory (authored NPCs; editable in the creator)
        self.arena_title = False                       # holds the arena's "Champion of the Pit" (see arena.py)
        self._hp_roll = None                          # 1dHD, rolled once in _derive_combat
        self._hp_override = None                       # sandbox: a hand-set HP max that wins over the derived one

        self._auto_name = name is None
        self.name = name or names.random_name()
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
        u.talents = {t: list(d.get("talents", {}).get(t, [])) for t in talents.TRACKS}
        u._level_hp_rolls = list(d.get("level_hp_rolls", []))
        u.base_attributes = dict(d["base_attributes"])
        for a in ATTRIBUTES:
            setattr(u, a, u.base_attributes[a])
        u._age_base = d["age_base"]
        u.race = data.race_by_name(d["race"])
        u._configure_race()
        u.age = d.get("age", u.age)                     # creator-set age wins; older saves fall back to the derived one
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
        u.share_food = d.get("share_food", True)
        u.combat_xp = d.get("combat_xp", 0)
        u.work_hours = d.get("work_hours", 0)
        u.bio = d.get("bio", "")
        u.arena_title = d.get("arena_title", False)
        u._auto_name = d["auto_name"]
        u.name = d["name"]
        u.token = u.race["token"]
        u._hp_roll = d.get("hp_roll")
        u._hp_override = d.get("hp_override")            # creator-set HP max, or None
        if u._hp_roll is None:                           # pre-hunger save: back it out of hp_max
            u._hp_roll = max(1, d["hp_max"] - mod(u.constitution) - u._ability.hp_max)
        u._derive_combat()                               # rebuilds hp_max from _hp_roll
        return u

    @property
    def ability(self):
        return self._ability

    # ------------------------------------------------------------------ #
    # hunger: one meal a day, or the body starts giving out               #
    #   (see RULES.md; the Leshy "Autotroph" is exempt)                   #
    # ------------------------------------------------------------------ #
    @property
    def hunger_level(self):
        """0 fed · 1 hungry · 2 starving · 3 starving to death."""
        if self._ability.id == "autotroph":
            return 0
        return min(self.unfed_days, 3)

    @property
    def hunger_attribute_penalty(self):
        return (0, -2, -4, -4)[self.hunger_level]

    @property
    def hunger_label(self):
        return ("", "hungry", "starving", "starving to death")[self.hunger_level]

    @property
    def incapacitated(self):
        """Collapsed from hunger -- cannot be sent into a fight."""
        return self.hunger_level >= 3

    def _take_ration(self, larder=None):
        """Eat one ration: this character's own pack first, then each pack in
        `larder` (guild-mates sharing food). Returns True if one was found."""
        for pack in (self._base_inventory, *(larder or ())):
            food = next((it for it in pack if it in data.FOOD_ITEMS), None)
            if food is not None:
                pack.remove(food)
                return True
        return False

    def consume_daily_food(self, larder=None):
        """Resolve one day's meal: eat a ration (own pack, then `larder`) if one
        is to be had, else go hungrier. Returns 'ate' | 'hungry' | 'dead'. The
        caller re-derives combat stats and clears the dead from the roster."""
        if self._ability.id == "autotroph":
            return "ate"
        if self._take_ration(larder):
            self.unfed_days = 0
            return "ate"
        self.unfed_days += 1
        return "dead" if self.unfed_days >= data.STARVATION_DEATH_DAYS else "hungry"

    def eat_now(self, larder=None):
        """Eat a ration this instant -- the guild stopping to have a meal rather
        than waiting for the day to turn. Only bites if the character is actually
        hungry and a ration is to be had (own pack, then `larder`); never advances
        hunger. Returns True if a meal was eaten. The caller re-derives combat."""
        if self.hunger_level == 0:
            return False
        if not self._take_ration(larder):
            return False
        self.unfed_days = 0
        return True

    @property
    def rations(self):
        """Meals sitting in this character's pack."""
        return sum(1 for it in self._base_inventory if it in data.FOOD_ITEMS)

    @property
    def work_xp(self):
        """Marks of work experience -- one per `economy.LUMBER_XP_HOURS` hours of
        day-labour at the lumber yard. Feeds the work level / talent tree."""
        return self.work_hours // economy.LUMBER_XP_HOURS

    # ------------------------------------------------------------------ #
    # leveling: one level per XP track, its own talent tree; the mean of #
    # the track levels grants hit dice. See progression.py / talents.py. #
    # ------------------------------------------------------------------ #
    @property
    def combat_level(self):
        return progression.combat_level(self.combat_xp)

    @property
    def work_level(self):
        return progression.work_level(self.work_xp)

    @property
    def track_level(self):
        return {"combat": self.combat_level, "work": self.work_level}

    @property
    def mean_level(self):
        return progression.mean_level(self.combat_level, self.work_level)

    def picks_available(self, track):
        """Unspent talent picks in `track` (one earned per level in it)."""
        return self.track_level[track] - len(self.talents[track])

    @property
    def pending_picks(self):
        """Tracks with a talent pick waiting to be spent."""
        return [t for t in talents.TRACKS if self.picks_available(t) > 0]

    @property
    def haggle_charisma_mod(self):
        """Charisma modifier for market haggling only -- the Negotiator talent
        lifts it without touching the real Charisma score."""
        return mod(self.charisma + self.hunger_attribute_penalty
                   + self.talent_bonus("haggle_cha"))

    def price_mods(self):
        """This member's talent contributions to a market visit's deal fraction
        (`economy.PriceMod`). Yielded, not situational -- economy scopes each by
        item and by buy/sell."""
        n = self.talent_bonus("food_haggle")
        if n:
            yield economy.PriceMod(
                round(economy.CHA_DEAL_STEP * n, 3), "Provisioner",
                applies=lambda item, side: side == "buy" and item in data.FOOD_ITEMS)

    def choose_talent(self, track, talent_id):
        """Spend a pick in `track` on `talent_id`. Returns True if it took."""
        t = talents.get(talent_id)
        if (t is None or t.track != track or talent_id in self.talents[track]
                or self.picks_available(track) <= 0
                or (t.requires and t.requires not in self.talents[track])):
            return False
        self.talents[track].append(talent_id)
        self._apply_attributes()
        self._derive_combat()
        return True

    def collect_levels(self):
        """Roll the hit dice owed for the current mean level. Idempotent; call
        after any XP gain. Not called on load -- `_level_hp_rolls` is restored."""
        rolled = False
        while len(self._level_hp_rolls) < self.mean_level:
            self._level_hp_rolls.append(roll(1, self.race["hd"]))
            rolled = True
        if rolled:
            self._derive_combat()
        return rolled

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
            setattr(self, a, self.base_attributes[a] + m + self.talent_bonus("attr", a))

    def talent_bonus(self, channel, stat=""):
        """Total this character's picked talents contribute to `channel` (see the
        channel table in `talents.py`), narrowed to `stat` on `attr` / `to_hit`."""
        picked = [tid for lst in self.talents.values() for tid in lst]
        return talents.bonus(picked, channel, stat)

    def _carry_relief(self):
        """Kg the Carrier talent adds to the stagger threshold: up to the talent's
        `carry_buffer`, but no more than the real weight of the pack cargo that is
        neither a weapon nor a consumable -- it is headroom for hauling gear, not
        for food or spare weapons. No such cargo -> no relief."""
        buf = self.talent_bonus("carry_buffer")
        if not buf:
            return 0.0
        cargo = sum(data.item_weight(it) for it in self._base_inventory
                    if not self.is_weapon(it) and it not in data.CONSUMABLE_ITEMS)
        return round(min(buf, cargo), 1)

    def _apply_race(self):
        self.race = data.roll_race()
        self._configure_race()

    def _configure_race(self):
        self._apply_attributes()
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
        self.token = self.race["token"]
        self._derive_combat()

    # ------------------------------------------------------------------ #
    # sandbox editing: the Editor's character creator sets fields straight #
    # to any valid value -- no draft / XP gating. Each keeps the model     #
    # whole (re-applies attributes, re-derives combat) and round-trips     #
    # through `persist.unit_to_dict` unchanged.                            #
    # ------------------------------------------------------------------ #
    def set_name(self, name):
        """A blank name hands the unit a fresh procedural one and marks it a nobody."""
        name = (name or "").strip()
        self._auto_name = not name
        self.name = name or names.random_name()

    def set_alignment(self, alignment):
        self.alignment = alignment                 # one of data.ALIGNMENTS

    def set_bio(self, text):
        self.bio = (text or "").strip()

    def set_base_attribute(self, attr, score):
        """Set the raw (pre-racial) score for `attr`, clamped to the 3..18 a 3d6
        roll can produce. Racial mods and talents still apply on top."""
        self.base_attributes[attr] = max(3, min(18, int(score)))
        self._apply_attributes()
        self._derive_combat()

    def set_age(self, years):
        """Set the shown age directly -- persisted as-is (see `persist.unit_to_dict`).
        `_age_base` stays the generator's d100 roll; a race swap re-derives the age
        from it, so `age / age_mult` is the roll this age is equivalent to at x1."""
        self.age = max(1, int(years))

    def set_language(self, name, on):
        """Toggle a language on/off; never drops the last one."""
        if on and name in data.LANGUAGES and name not in self.languages:
            self.languages.append(name)
        elif not on and name in self.languages and len(self.languages) > 1:
            self.languages.remove(name)

    def set_gold(self, copper):
        self.gold = max(0, int(copper))

    def set_hp(self, value):
        """Pin the HP max to `value` (>= 1), or pass `None` to drop back to the
        rolled formula. The override is sticky: it survives race / level / Con
        edits until cleared, and round-trips through `persist.unit_to_dict`."""
        self._hp_override = None if value is None else max(1, int(value))
        self._derive_combat()

    def set_track_level(self, track, level):
        """Set the combat / work level directly: `combat_xp` (or `work_hours`)
        jumps to that level's threshold, hit dice and talent picks resync to the
        new mean level -- picks the level no longer supports are dropped."""
        thresholds = (progression.COMBAT_XP_THRESHOLDS if track == "combat"
                      else progression.WORK_XP_THRESHOLDS)
        level = max(0, min(len(thresholds), int(level)))
        marks = thresholds[level - 1] if level else 0
        if track == "combat":
            self.combat_xp = marks
        else:
            self.work_hours = marks * economy.LUMBER_XP_HOURS
        del self._level_hp_rolls[self.mean_level:]          # a lower level owes fewer dice
        for t in talents.TRACKS:
            del self.talents[t][self.track_level[t]:]       # ...and fewer picks (pick order = valid prefix)
        self.collect_levels()                              # roll any dice a higher level now owes
        self._apply_attributes()
        self._derive_combat()

    def drop_talent(self, track, talent_id):
        """Un-pick a talent and, cascading, anything that required it."""
        picked = self.talents[track]
        if talent_id not in picked:
            return False
        doomed = {talent_id}
        grew = True
        while grew:
            grew = False
            for tid in picked:
                t = talents.get(tid)
                if t and t.requires in doomed and tid not in doomed:
                    doomed.add(tid)
                    grew = True
        self.talents[track] = [tid for tid in picked if tid not in doomed]
        self._apply_attributes()
        self._derive_combat()
        return True

    # ------------------------------------------------------------------ #
    # combat derivation                                                  #
    # ------------------------------------------------------------------ #
    def _derive_combat(self):
        """Recompute every stat that hangs off attributes + hunger + encumbrance
        + armor + talents. Order matters: `_derive_carry` sets `encumbered`,
        which the attribute mods read, which everything after them reads."""
        self._derive_carry()
        self._derive_attribute_mods()
        self._derive_hp()
        self._derive_ac()
        self._derive_speed()
        self.unarmed_damage = data.UNARMED_ATTACK.get(self.size, (1, 2))   # die by size
        self.dr = self._ability.damage_reduction

    def _derive_carry(self):
        """Carry thresholds (kg) and the `encumbered` flag. A normal person
        (FOR 10 -> mod 0, Medio) hauls 15 kg freely and 35 kg at a stagger; every
        point of FOR mod is +4 / +6. Judged from the hunger-adjusted Strength --
        encumbrance then penalises FOR/DES/speed, so it must not feed back and
        shrink its own threshold. An ability may raise the size bracket used here
        and nowhere else (the Goliath carries as Large). The Carrier talent
        widens only the stagger threshold, never `load` or the `carry_max` ceiling."""
        pen = self.hunger_attribute_penalty
        cm = data.SIZES[self._ability.carry_size or self.size]["carry"]
        str_carry = mod(self.strength + pen)
        base_normal = max(1, round((str_carry * 4 + 15) * cm))
        self.carry_max = max(2, round((str_carry * 6 + 35) * cm))
        self.carry_relief = self._carry_relief()
        self.carry_normal = round(base_normal + self.carry_relief, 1)
        self.encumbered = self.load > self.carry_normal

    def _derive_attribute_mods(self):
        """`mod_<attr>` for all six: the score, minus hunger on every attribute
        (0 / -2 / -4), minus 2 more on Strength and Dexterity while overloaded."""
        pen = self.hunger_attribute_penalty
        enc = -2 if self.encumbered else 0
        for a in ATTRIBUTES:
            extra = enc if a in ("strength", "dexterity") else 0
            setattr(self, f"mod_{a}", mod(getattr(self, a) + pen + extra))

    def _derive_hp(self):
        """Max HP: the creation roll + Con + ability bonus, one kept die per mean
        level, and the Hardy talent per Hit Die. `_hp_roll` / `_level_hp_rolls`
        are fixed, so re-deriving never re-rolls. A sandbox `_hp_override` (set in
        the creator) replaces the whole formula. Starving (tier 2+) caps it at 1."""
        if self._hp_roll is None:
            self._hp_roll = roll(1, self.race["hd"])
        con = self.mod_constitution
        hit_dice = 1 + len(self._level_hp_rolls)
        if self._hp_override is not None:
            self.hp_max = max(1, self._hp_override)
        else:
            self.hp_max = (max(1, self._hp_roll + con + self._ability.hp_max)
                           + sum(max(1, die + con) for die in self._level_hp_rolls)
                           + self.talent_bonus("hp_per_hd") * hit_dice)
        if self.hunger_level >= 2:
            self.hp_max = 1

    def _derive_ac(self):
        """AC base (10 + Dex + worn armor; armor caps how much Dex still counts)
        and Mental Defense (10 + Wis, the Demoralize target). The racial natural
        bonus and Defend enter as typed mods on the Combatant, not here."""
        armor = self.armor
        dex_ac = self.mod_dexterity
        if armor is not None and armor["max_dex"] is not None:
            dex_ac = min(dex_ac, armor["max_dex"])
        self.ac_base = (10 + dex_ac + (armor["ac"] if armor else 0)
                        + self.talent_bonus("ac"))
        self.ac_natural = self._ability.ac_natural
        self.mental_defense_base = 10 + self.mod_wisdom

    def _derive_speed(self):
        """Speed in squares: size base + ability, minus heavy-armor drag, minus
        one more while overloaded. Floored at 1."""
        self.speed = data.squares(data.SIZES[self.size]["speed"]) + self._ability.speed
        armor = self.armor
        if armor is not None and armor["speed"]:
            self.speed = max(1, self.speed - armor["speed"])
        if self.encumbered:
            self.speed = max(1, self.speed - 1)

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
    def attack_bonus(self):
        """Base to-hit modifier and the attribute feeding it, as `(value, src)`.
        Includes the flat talent bonus (Sure Strike / Deadeye); no target, flank
        or condition mods -- those are situational and need the Combatant. Empty
        hands hit with Strength (the unarmed attack)."""
        w = self.weapon
        if w is None:
            base, stat, src = self.mod_strength, "str", "STR"
        elif w["range"] > 0:
            base, stat, src = self.mod_dexterity, "dex", "DEX"
        elif w["finesse"]:
            base = max(self.mod_strength, self.mod_dexterity)
            stat = "dex" if self.mod_dexterity >= self.mod_strength else "str"
            src = "STR/DEX"
        else:
            base, stat, src = self.mod_strength, "str", "STR"
        base += self.talent_bonus("to_hit", "dexterity" if stat == "dex" else "strength")
        return base, src

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
