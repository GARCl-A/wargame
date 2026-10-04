"""Leveling and talents: one level per XP track, each with its own talent tree.

Mixed into `unit.Unit`. The mean of the track levels grants hit dice; see
`progression.py` / `talents.py`.
"""

import random

from . import economy, items, magic, progression, talents
from .data import mod, roll


class LevelingMixin:
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
    def racial_xp(self):
        """The racial track's "XP": the sum of the other track levels. Every
        level anywhere feeds it (see `progression.RACIAL_XP_THRESHOLDS`)."""
        return self.combat_level + self.work_level

    @property
    def racial_level(self):
        """Racial-track level: a sandbox-pinned value, else derived from
        `racial_xp`. Drives hit dice (`1 + racial_level`) and racial picks."""
        if self._racial_override is not None:
            return self._racial_override
        return progression.racial_level(self.racial_xp)

    @property
    def track_level(self):
        return {"combat": self.combat_level, "work": self.work_level,
                "racial": self.racial_level}

    @property
    def mean_level(self):
        """Encounter / arena difficulty scalar only -- hit points are off
        `racial_level` now."""
        return progression.mean_level(self.combat_level, self.work_level)

    def picks_available(self, track):
        """Unspent talent picks in `track`. Combat and work grant 1 pick per level;
        the racial track grants its first pick at racial level 5."""
        if track == "racial":
            earned = max(0, self.racial_level - 4)
            return earned - len(self.talents["racial"])
        return self.track_level[track] - len(self.talents[track])

    def _has_offerable(self, track):
        """The `track` has at least one node this character could still take."""
        tree = (talents.racial_tree(self.race["name"]) if track == "racial"
                else talents.TREE[track])
        return any(t.id not in self.talents[track]
                   and (not t.requires or t.requires in self.talents[track])
                   for t in tree)

    @property
    def pending_picks(self):
        """Tracks with a talent pick waiting to be spent on a node that exists --
        a racial track with no authored node for this race stays quiet."""
        return [t for t in talents.TRACKS
                if self.picks_available(t) > 0 and self._has_offerable(t)]

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
                applies=lambda item, side: side == "buy" and items.is_food(item))

    def choose_talent(self, track, talent_id):
        """Spend a pick in `track` on `talent_id`. Returns True if it took."""
        t = talents.get(talent_id)
        if (t is None or t.track != track or talent_id in self.talents[track]
                or self.picks_available(track) <= 0
                or (t.race and t.race != self.race["name"])
                or (t.requires and t.requires not in self.talents[track])):
            return False
        self.talents[track].append(talent_id)
        
        # Hooks for specific racial talents
        if talent_id == "kenku_faith_initiate":
            if not self.magic_source:
                self.magic_source = "faith"
            elif self.magic_source == "faith":
                # Find lowest level faith spell not known
                faith_spells = [s for s in magic.SPELLS.values() if "faith" in s.sources and s.id not in self.spells_known]
                if faith_spells:
                    faith_spells.sort(key=lambda s: s.level)
                    self.spells_known.append(faith_spells[0].id)
        elif talent_id == "sprite_nature_initiate":
            if not self.magic_source:
                self.magic_source = "nature"
        elif talent_id == "dwarf_crafting":
            for r in ["Dwarf Axe", "Dwarf Shield", "Dwarf Armor"]:
                if r not in self.recipes:
                    self.recipes.append(r)
        elif talent_id == "kobold_trapper":
            for r in ["Bear Trap", "Alarm Trap"]:
                if r not in self.recipes:
                    self.recipes.append(r)
        elif talent_id == "apothecary":
            unlearned = [r for r in items.APOTHECARY_RECIPES if r not in self.recipes]
            if unlearned:
                self.recipes.append(random.choice(unlearned))
            else:
                self.craft_bonuses["apothecary"] = self.craft_bonuses.get("apothecary", 0) + 1
        elif talent_id == "blacksmith":
            unlearned = [r for r in items.BLACKSMITH_RECIPES if r not in self.recipes]
            if unlearned:
                self.recipes.append(random.choice(unlearned))
            else:
                self.craft_bonuses["forge"] = self.craft_bonuses.get("forge", 0) + 1
                
        self._apply_attributes()
        self._derive_combat()
        return True

    def collect_levels(self):
        """Roll the hit dice owed for the current racial level. Idempotent; call
        after any XP gain. Not called on load -- `_level_hp_rolls` is restored."""
        rolled = False
        while len(self._level_hp_rolls) < self.racial_level:
            self._level_hp_rolls.append(roll(1, self.race["hd"]))
            rolled = True
        if rolled:
            self._derive_combat()
        return rolled

    def talent_bonus(self, channel, stat=""):
        """Total this character's picked talents contribute to `channel` (see the
        channel table in `talents.py`), narrowed to `stat` on `attr` / `to_hit`."""
        picked = [tid for lst in self.talents.values() for tid in lst]
        return talents.bonus(picked, channel, stat)

    def has_talent(self, talent_id):
        return any(talent_id in lst for lst in self.talents.values())

    def can_use_luck(self, day=1):
        d = 1 if day is None else day
        return bool(self.talent_bonus("halfling_luck") and self.last_daily_luck_day < d)

    def use_luck(self, day=1):
        d = 1 if day is None else day
        self.last_daily_luck_day = d
