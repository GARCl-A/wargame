"""Editing a character in place: the draft's race/occupation swap and the
sandbox creator's direct setters.

Mixed into `unit.Unit`. Each setter keeps the model whole (re-applies
attributes, re-derives combat) and round-trips through `persist.unit_to_dict`.
"""

from . import constants, data, economy, names, progression, talents


class EditMixin:
    # ------------------------------------------------------------------ #
    # draft editing: swap race / occupation before the battle            #
    # ------------------------------------------------------------------ #
    def set_race(self, name):
        self.race = data.race_by_name(name)
        self._hp_roll = None                  # new hit die -> re-roll HP
        offered = {t.id for t in talents.racial_tree(name)}
        self.talents["racial"] = [tid for tid in self.talents["racial"] if tid in offered]
        self._configure_race()
        if self.race["kind"] == "beast":
            self._become_beast()
        elif self.occupation["name"] == data.BEAST_OCCUPATION["name"]:
            self._apply_occupation()          # leaving a beast body: it needs a real job again
        self._after_edit()

    def _become_beast(self):
        """A beast fights with its own body but keeps what it carries: held gear
        is stowed in the pack first (a pack wolf, a cart horse down the road)."""
        for held in (self.take_from_hand(), self.take_from_offhand(), self.take_from_armor()):
            if held:
                self._pack_add(held)
        pack, locked = self._base_inventory, self.locked_items
        self._apply_beast()
        self._base_inventory, self.locked_items = pack, locked

    def set_occupation(self, name):
        if self.race["kind"] == "beast":
            return                            # a beast has no job -- it fights with its own body
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

    def set_natural_armor(self, value):
        """Flat AC the body gives, 0..`constants.NATURAL_ARMOR_MAX`. Stacks with
        worn armor and ignores its Dex cap and drag."""
        self.natural_armor = max(0, min(constants.NATURAL_ARMOR_MAX, int(value)))
        self._derive_combat()

    def set_hp(self, value):
        """Pin the HP max to `value` (>= 1), or pass `None` to drop back to the
        rolled formula. The override is sticky: it survives race / level / Con
        edits until cleared, and round-trips through `persist.unit_to_dict`."""
        self._hp_override = None if value is None else max(1, int(value))
        self._derive_combat()

    def set_track_level(self, track, level):
        """Set a track level directly. `combat` / `work` jump `combat_xp` /
        `work_hours` to that level's threshold. `racial` pins `_racial_override`
        (hit dice + racial picks), or `level=None` drops it back to derived.
        Hit dice and talent picks resync -- picks the new level no longer
        supports are dropped."""
        if track not in talents.XP_TRACKS:                  # "racial": derived, or a sandbox pin
            self._racial_override = (None if level is None else
                max(0, min(len(progression.RACIAL_XP_THRESHOLDS), int(level))))
        else:
            thresholds = (progression.COMBAT_XP_THRESHOLDS if track == "combat"
                          else progression.WORK_XP_THRESHOLDS)
            level = max(0, min(len(thresholds), int(level)))
            marks = thresholds[level - 1] if level else 0
            if track == "combat":
                self.combat_xp = marks
            else:
                self.work_hours = marks * economy.LUMBER_XP_HOURS
        del self._level_hp_rolls[self.racial_level:]        # a lower level owes fewer dice
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
        if "apothecary" in doomed:
            self.craft_bonuses.pop("apothecary", None)
        if "blacksmith" in doomed:
            self.craft_bonuses.pop("forge", None)
        self._apply_attributes()
        self._derive_combat()
        return True
