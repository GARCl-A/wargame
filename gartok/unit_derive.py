"""Derived combat stats and read-only previews of the equipped loadout.

Mixed into `unit.Unit`: carry, attribute mods, HP, AC, speed and their
breakdowns, so roster screens can show a character without a Combatant.
"""

from . import data, items
from .data import ATTRIBUTES, mod, roll


def carry_thresholds(score, size, ability):
    """(normal, max) kg a body of this Strength `score` and `size` carries: the
    one formula for characters and for the group's animals. An ability may raise
    the size bracket (`carry_size`) or scale the result (`carry_mult`)."""
    cm = data.SIZES[ability.carry_size or size]["carry"] * ability.carry_mult
    str_carry = mod(score)
    return max(1, round((str_carry * 4 + 15) * cm)), max(2, round((str_carry * 6 + 35) * cm))


class DerivationMixin:

    def _carry_relief(self):
        """Kg the Carrier talent adds to the stagger threshold: up to the talent's
        `carry_buffer`, but no more than the real weight of the pack cargo that is
        neither a weapon nor a consumable -- it is headroom for hauling gear, not
        for food or spare weapons. No such cargo -> no relief."""
        buf = self.talent_bonus("carry_buffer")
        if not buf:
            return 0.0
        cargo = sum(items.item_weight(name) * qty for name, qty in self._base_inventory
                    if not self.is_weapon(name) and not items.is_consumable(name))
        return round(min(buf, cargo), 1)

    # ------------------------------------------------------------------ #
    # combat derivation                                                  #
    # ------------------------------------------------------------------ #
    def _derive_combat(self):
        """Recompute every stat that hangs off attributes + hunger + encumbrance
        + armor + talents. Order matters: `_derive_carry` sets `encumbered`,
        which the attribute mods read, which everything after them reads."""
        if self.equipped_tongue and not self.has_tongue:   # lost the talent (race / drop): stow it
            self._pack_add(self.equipped_tongue)
            self.equipped_tongue = None
        self._derive_size()
        self._derive_carry()
        self._derive_attribute_mods()
        self._derive_hp()
        self._derive_ac()
        self._derive_speed()
        n, faces = data.UNARMED_ATTACK.get(self.size, (1, 2))              # die by size
        self.unarmed_damage = (n + self.talent_bonus("unarmed_dice"), faces)
        self.dr = self._ability.damage_reduction

    def _derive_size(self):
        """The race's size, stepped up by talents (capped at Large); the board
        footprint follows it."""
        order = data.SIZE_ORDER
        step = order.index(self.race["size"]) + self.talent_bonus("size_up")
        self.size = order[min(step, len(order) - 1)]
        self.footprint = data.SIZES[self.size]["footprint"]

    def _derive_carry(self):
        """Carry thresholds (kg) and the `encumbered` flag. A normal person
        (FOR 10 -> mod 0, Medio) hauls 15 kg freely and 35 kg at a stagger; every
        point of FOR mod is +4 / +6. Judged from the hunger-adjusted Strength --
        encumbrance then penalises FOR/DES/speed, so it must not feed back and
        shrink its own threshold. An ability may raise the size bracket used here
        and nowhere else (the Goliath carries as Large). The Carrier talent
        widens only the stagger threshold, never `load` or the `carry_max` ceiling."""
        pen = self.hunger_attribute_penalty
        base_normal, self.carry_max = carry_thresholds(self.strength + pen, self.size, self._ability)
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

    def recalculate_hp(self):
        """Re-derive attribute mods and HP max, preserving/shifting current HP by any delta."""
        self._derive_attribute_mods()
        self._derive_hp()

    def _derive_hp(self):
        """Max HP: the creation roll + Con + ability bonus, one kept die per
        racial level, and the Hardy talent per Hit Die. `_hp_roll` / `_level_hp_rolls`
        are fixed, so re-deriving never re-rolls. A sandbox `_hp_override` (set in
        the creator) replaces the whole formula. Starving (tier 2+) caps it at 1."""
        old_max = getattr(self, "hp_max", None)
        old_hp = getattr(self, "hp", None)
        if self._hp_roll is None:
            self._hp_roll = roll(1, self.race["hd"])
        con = self.mod_constitution
        hit_dice = 1 + len(self._level_hp_rolls)
        if self._hp_override is not None:
            self.hp_max = max(1, self._hp_override)
        else:
            dice_sum = self._hp_roll + sum(self._level_hp_rolls)
            self.hp_max = (dice_sum 
                           + (con * hit_dice) 
                           + self._ability.hp_max 
                           + self.talent_bonus("hp_per_hd") * hit_dice)
            self.hp_max = max(self.hp_max, 1)
        if self.hunger_level >= 2:
            self.hp_max = 1
        if old_max is not None and old_hp is not None:
            delta = self.hp_max - old_max
            self.hp = max(1, min(old_hp + delta, self.hp_max))
        else:
            self.hp = getattr(self, "hp", self.hp_max)

    def hp_breakdown(self):
        """Detailed breakdown of how this unit's max HP was calculated.

        Returns a dict containing:
          - hd: Hit Die face (e.g. 8 for 1d8)
          - base_roll: creation roll (Level 0)
          - level_rolls: list of rolls for each gained racial level (Level 1..N)
          - hit_dice: total hit dice count (1 + len(level_rolls))
          - dice_sum: sum of hit dice rolls
          - con_mod: Constitution modifier
          - con_total: con_mod * hit_dice
          - ability_name: racial ability name
          - ability_bonus: flat HP bonus from racial ability
          - talent_per_hd: HP per Hit Die from talents (e.g. Hardy)
          - talent_total: talent_per_hd * hit_dice
          - raw_total: uncapped total (dice_sum + con_total + ability_bonus + talent_total)
          - final_max: actual hp_max
          - override: _hp_override if pinned, else None
          - starving: whether hunger_level >= 2
          - min_floor: whether raw_total was < 1 and clamped to 1
        """
        hd = self.race["hd"]
        base_roll = self._hp_roll if self._hp_roll is not None else 1
        level_rolls = list(self._level_hp_rolls)
        hit_dice = 1 + len(level_rolls)
        dice_sum = base_roll + sum(level_rolls)
        con_mod = self.mod_constitution
        con_total = con_mod * hit_dice
        ability_name = self._ability.name
        ability_bonus = self._ability.hp_max
        talent_per_hd = self.talent_bonus("hp_per_hd")
        talent_total = talent_per_hd * hit_dice
        raw_total = dice_sum + con_total + ability_bonus + talent_total
        final_max = self.hp_max
        is_starving = self.hunger_level >= 2
        return {
            "hd": hd,
            "base_roll": base_roll,
            "level_rolls": level_rolls,
            "hit_dice": hit_dice,
            "dice_sum": dice_sum,
            "con_mod": con_mod,
            "con_total": con_total,
            "ability_name": ability_name,
            "ability_bonus": ability_bonus,
            "talent_per_hd": talent_per_hd,
            "talent_total": talent_total,
            "raw_total": raw_total,
            "final_max": final_max,
            "override": self._hp_override,
            "starving": is_starving,
            "min_floor": raw_total < 1 and self._hp_override is None and not is_starving,
        }

    def hp_formula(self):
        """Concise one-line string summarizing the HP calculation."""
        b = self.hp_breakdown()
        if b["override"] is not None:
            return f"manual override: {b['override']}"
        parts = []
        rolls = [str(b["base_roll"])] + [str(r) for r in b["level_rolls"]]
        if len(rolls) == 1:
            parts.append(f"{rolls[0]} (d{b['hd']})")
        else:
            parts.append(f"{b['dice_sum']} ({len(rolls)}d{b['hd']}: {', '.join(rolls)})")
        if b["con_total"]:
            parts.append(f"{b['con_total']:+} (CON)")
        if b["talent_total"]:
            parts.append(f"+{b['talent_total']} (talents)")
        if b["ability_bonus"]:
            parts.append(f"+{b['ability_bonus']} ({b['ability_name']})")
        expr = " ".join(parts)
        if b["starving"]:
            return f"{expr} -> starving: 1 max"
        if b["min_floor"]:
            return f"{expr} -> min floor: 1 max"
        return f"{expr} = {b['final_max']} max"

    def _breakdown(self, terms, actual):
        """`terms` without zero entries, plus a closing "minimum" term when a
        floor made the plain sum differ from `actual`."""
        out = [(label, v) for label, v in terms if v or label == "base"]
        gap = actual - sum(v for _, v in out)
        if gap:
            out.append(("minimum", gap))
        return out

    def ac_breakdown(self):
        """Where `ac` comes from, as `[(label, value)]` summing to it."""
        armor = self.armor
        dex = self.mod_dexterity
        capped = armor is not None and armor.max_dex is not None and dex > armor.max_dex
        if capped:
            dex = armor.max_dex
        shield = items.get(self.equipped_offhand) if (
            self.equipped_offhand and items.is_shield(self.equipped_offhand)) else None
        return self._breakdown([
            ("base", 10), ("DEX (armor cap)" if capped else "DEX", dex),
            (self.armor_name if armor else "armor", armor.ac if armor else 0),
            (shield.name if shield else "shield", shield.ac if shield else 0),
            ("talents", self.talent_bonus("ac")), (f"{self._ability.name} (natural)", self._ability.ac_natural),
            ("natural armor", self.natural_armor),
        ], self.ac)

    def md_breakdown(self):
        """Where `mental_defense` comes from, as `[(label, value)]`."""
        return self._breakdown([
            ("base", 10), ("WIS", self.mod_wisdom), ("talents", self.talent_bonus("mental_defense")),
            ("group overextended", -self.group_overextension),
        ], self.mental_defense)

    def speed_breakdown(self):
        """Where `speed` (squares per turn) comes from, as `[(label, value)]`."""
        armor = self.armor
        return self._breakdown([
            (f"{self.race['name']} base", data.squares(self.race["speed"])),
            (self._ability.name, self._ability.speed), ("talents", self.talent_bonus("speed")),
            (f"{self.armor_name} (drag)" if armor else "armor", -(armor.speed_penalty if armor else 0)),
            ("overloaded", -1 if self.encumbered else 0),
        ], self.speed)

    def initiative_breakdown(self):
        """Where `Combatant.initiative_bonus()` comes from, as `[(label, value)]`."""
        terms = [("WIS", self.mod_wisdom), (self._ability.name, self._ability.initiative),
                 ("talents", self.talent_bonus("initiative"))]
        return self._breakdown(terms, sum(v for _, v in terms))

    def _derive_ac(self):
        """AC base (10 + Dex + worn armor; armor caps how much Dex still counts)
        and Mental Defense (10 + Wis, the Demoralize target). The racial natural
        bonus and Defend enter as typed mods on the Combatant, not here.
        `group_overextension` (set by `Guild._sync_leadership`, see `group.py`)
        docks Mental Defense flat: a group stretched past its leader's
        Charisma is individually easier to rattle."""
        armor = self.armor
        dex_ac = self.mod_dexterity
        if armor is not None and armor.max_dex is not None:
            dex_ac = min(dex_ac, armor.max_dex)
        self.ac_base = (10 + dex_ac + (armor.ac if armor else 0)
                        + self.talent_bonus("ac"))
        if self.equipped_offhand and items.is_shield(self.equipped_offhand):
            shield = items.get(self.equipped_offhand)
            self.ac_base += shield.ac if shield else 0
        self.ac_natural = self._ability.ac_natural + self.natural_armor
        self.mental_defense_base = (10 + self.mod_wisdom
                                    + self.talent_bonus("mental_defense")
                                    - self.group_overextension)

    def _derive_speed(self):
        """Speed in squares: race base (the size's unless the race sets its own)
        + ability + talents, minus heavy-armor drag, minus one more while
        overloaded. Floored at 1."""
        self.speed = (data.squares(self.race["speed"])
                      + self._ability.speed + self.talent_bonus("speed"))
        armor = self.armor
        if armor is not None and armor.speed_penalty:
            self.speed = max(1, self.speed - armor.speed_penalty)
        if self.encumbered:
            self.speed = max(1, self.speed - 1)

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
        return items.get(self.equipped_weapon)

    @property
    def armor_name(self):
        return self.equipped_armor

    @property
    def armor(self):
        """The worn armor's stat dict / ItemDef, or None."""
        return items.get(self.equipped_armor)

    @property
    def ranged(self):
        """Wields a weapon that fires at range (the crossbow)."""
        w = self.weapon
        return bool(w) and w.range > 0

    @property
    def has_tongue(self):
        """Carries the Grippli Tongue -- a third limb with its own weapon slot
        (`equipped_tongue`), granted by the `tongue` racial talent."""
        return "tongue" in self.talents["racial"]

    @property
    def tongue_reach(self):
        """Squares a tongue attack reaches: 1 + the `melee_reach` talent bonus.
        Only the weapon in the Tongue slot gets this -- the hands stay at 1."""
        return 1 + self.talent_bonus("melee_reach")

    @property
    def attack_bonus(self):
        """Base to-hit modifier and the attribute feeding it, as `(value, src)`.
        Includes the flat talent bonus (Sure Strike / Deadeye); no target, flank
        or condition mods -- those are situational and need the Combatant. Empty
        hands hit with Strength (the unarmed attack)."""
        w = self.weapon
        if w is None and self.talent_bonus("unarmed_finesse"):
            base = max(self.mod_strength, self.mod_dexterity)
            stat = "dex" if self.mod_dexterity >= self.mod_strength else "str"
            src = "STR/DEX"
        elif w is None:
            base, stat, src = self.mod_strength, "str", "STR"
        elif w.range > 0:
            base, stat, src = self.mod_dexterity, "dex", "DEX"
        elif w.finesse:
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
    def ride_weight(self):
        """What a wagon carries them as: their body (by size) and everything they carry."""
        return data.SIZES[self.size]["kg"] + self.load

    @property
    def load(self):
        """Weight of the equipped loadout: weapon hand + off hand + tongue + artifact + pack + armor."""
        w = sum(items.item_weight(name) * qty for name, qty in self._base_inventory)
        if self.equipped_weapon:
            w += items.item_weight(self.equipped_weapon)
        if self.equipped_tongue:
            w += items.item_weight(self.equipped_tongue)
        if self.equipped_offhand:
            w += items.item_weight(self.equipped_offhand)
        if self.equipped_artifact:
            w += items.item_weight(self.equipped_artifact)
        if self.armor:
            w += self.armor.weight
        return round(w, 1)
