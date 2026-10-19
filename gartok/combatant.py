"""Combatant: a `unit.Unit` for the duration of one battle.

`Battle` wraps every character it is given (players and rolled enemies) in a
Combatant. The Combatant owns everything that only makes sense inside a fight --
hit points, action points, board position, `status`, `conditions`, which hand
holds what right now, ammo and first-aid charges -- and every battle behaviour
(attack rolls, taking damage, falling, the turn cycle). It reads the character's
stats (`mod_strength`, `speed`, `ability`, ...) straight through: any attribute
it does not define itself is looked up on the wrapped `char`.

Because the Combatant holds its own copy of the mutable bits (`inventory` is a
copy of the pack, `weapon_hand` etc. are fresh), a fight never touches the
persistent roster. When it is over, `campaign.absorb_battle` folds the result
back (permadeath, a torch that carried forward); everything else is discarded
and the next fight re-seeds a new Combatant from the character.
"""

from . import data, intel, items, progression
from .conditions import Hexed
from .data import resolve_bonus, roll
from .unit import flatten_pack

AP_PER_TURN = 2



class Combatant:
    def __init__(self, char, team=None, ai_ally=False):
        self.char = char
        self.team = team or getattr(char, "team", "player")
        self.ai_ally = ai_ally        # on the player's side, but played by ai.py (not the guild's)
        self.reset_battle_state()

    def __getattr__(self, name):
        # only reached when normal lookup fails -> read it off the character
        try:
            char = self.__dict__["char"]
        except KeyError:                      # during unpickling / early init
            raise AttributeError(name)
        return getattr(char, name)

    @property
    def ability(self):
        return self._ability

    # ------------------------------------------------------------------ #
    # the Z axis: pits, climbing, falling                                #
    # ------------------------------------------------------------------ #
    @property
    def flies(self):
        return self._ability.flies or bool(getattr(self.char, "talent_bonus", lambda _: 0)("flies"))

    @property
    def can_move_vertically(self):
        """Changes floor height as ordinary movement -- a flier or a climber --
        so the pathfinder is allowed to route them in and out of a pit."""
        return self.flies or self._ability.climb_speed

    @property
    def water_breathing(self):
        """Never runs out of breath while submerged (the Grippli's Amphibious)."""
        return self._ability.water_breathing

    def auto_climb(self, dc):
        """Clears a climb of this DC with no roll (the Lizardfolk's Climber)."""
        return dc <= self._ability.auto_climb_dc

    def reset_battle_state(self):
        c = self.char
        cur_hp = getattr(c, "hp", c.hp_max)
        self.hp = min(c.hp_max, max(1, cur_hp))
        self.pos = (0, 0)
        self.z = None                 # floor elevation standing on (None = query board)
        self.status = "up"            # up | dying | stable | broken | fled | dead
        self.death_clock = 0          # dying: own turns elapsed; save on DYING_TURNS
        self.raised = False           # stood back up by Raise Dead: undead now, falls for good
        self.nonlethal = False        # set by Battle for a non-lethal fight: 0 HP -> knocked out
        self.ferocity_pending = False # Orc downed this turn, falls at end_turn
        self.rounds_submerged = 0     # turns spent underwater in deep water (breath / drowning)
        self.initiative = 0           # set by Battle._roll_initiative
        self.delayed = False          # waiting at the end of the order; its turn resumes, not restarts
        self.delay_round = 0          # round of its last Delay: one per round (rounds start at 1)
        self.weapon_hand = c.equipped_weapon is not None
        self.weapon_name = c.equipped_weapon
        self.weapon = items.get(c.equipped_weapon)
        # the Tongue is a separate limb: its weapon rides alongside the hands
        self.tongue_weapon_name = c.equipped_tongue if c.has_tongue else None
        self.tongue_weapon = items.get(self.tongue_weapon_name)
        self.artifact_name = c.equipped_artifact
        self.torch_hand = False
        self.lantern_hand = False
        if c.equipped_offhand in (data.TORCH_ITEM, data.LANTERN_ITEM):
            weapon_hands = self.weapon.hands if (self.weapon_hand and self.weapon) else 0
            free_off_hand = weapon_hands < 2         # a 2-handed weapon leaves no off hand
            if c.equipped_offhand == data.TORCH_ITEM:
                self.torch_hand = free_off_hand
            else:
                self.lantern_hand = free_off_hand
        self.inventory = flatten_pack(c)
        self.ammo = (getattr(c, "quiver_charges", data.QUIVER_AMMO)
                     if data.AMMO_ITEM in self.inventory else 0)
        # a crossbow holds one bolt at a time and starts the fight empty: spend an
        # action to Reload (chambers one from the quiver), fire, repeat.
        self.crossbow_loaded = False
        # first aid charges are now persistent (campaign-long).
        self.first_aid_charges = (c.first_aid_charges
                                  if data.FIRST_AID_ITEM in self.inventory else 0)
        self.spells_known = list(getattr(c, "spells_known", []))
        self.conditions = []
        self.ap = AP_PER_TURN
        self.walking = False          # a walk is in progress (same Move action)
        self.moved = 0                # movement cost already spent in the current walk
        self.diag_steps = 0          # diagonals taken in the current walk (1,2,1,2… cost)
        self.path = []                # cells walked this turn: [start, ..., pos]
        self.last_path = []           # the previous turn's path (kept for future mechanics)
        self.used_abilities = set()   # keys of once-per-battle effects already spent
        self.kills = 0                # enemies this combatant downed (count, for display)
        self.combat_xp_earned = 0     # combat XP from those kills, by level difference
        self.magic_xp_earned = 0      # the same, for kills dealt with magic
        self.nonlethal_blows = False  # the Non-lethal toggle: -1 to hit, a foe dropped is knocked out
        self.captured = False         # bound by the other side (actions.Capture): out of the fight for good
        self.capture_tools_used = []  # Ropes / Chains this unit spent binding captives
        self.downed_by = None         # the combatant whose blow first put this one down (arena title)
        self.ferocity_downer = None   # who brought this unit to 0 HP while Ferocity keeps it up
        self.ctf_runner = False       # capture-the-flag: this enemy rushes the player's flag (set by Battle)
        self.mounted_on = None        # another Combatant this unit is riding (Centaur mount)
        self.rider = None             # a Combatant riding this one (Centaur mount)

    def credit_kill(self, victim, magic=False):
        """Book a downed enemy: +1 to the kill count, plus XP scaled by the level gap
        (`progression.xp_award` -- nothing for a victim below your level): combat XP, or
        magic XP for a blow dealt with magic. Also records who put the victim down (the
        arena title goes to whoever lands the blow on the champion)."""
        self.kills += 1
        if magic:
            self.magic_xp_earned += progression.xp_award(self.magic_level, victim.combat_level)
        else:
            self.combat_xp_earned += progression.xp_award(self.combat_level, victim.combat_level)
        victim.downed_by = self

    def spend_once(self, key):
        """Mark a once-per-battle effect as used. Returns True the first time only."""
        if key in self.used_abilities:
            return False
        self.used_abilities.add(key)
        return True

    # ------------------------------------------------------------------ #
    # lifecycle: up -> dying -> (stable | dead)   (see RULES.md)         #
    # ------------------------------------------------------------------ #
    @property
    def alive(self):
        """Standing combatant: acts, counts for victory, blocks, is seen/targeted
        normally. A body on the ground (dying/stable) is NOT alive in this sense."""
        return self.status == "up"

    @property
    def dying(self):
        return self.status == "dying"

    @property
    def stable(self):
        return self.status == "stable"

    @property
    def dead(self):
        return self.status == "dead"

    @property
    def broken(self):
        """Automaton at 0 HP: on the ground with no death clock, waits for an ally
        to repair it (see abilities `breaks_when_downed`)."""
        return self.status == "broken"

    @property
    def downed(self):
        """Has a body on the field but is out of the fight (dying, stable or broken)."""
        return self.status in ("dying", "stable", "broken")

    @property
    def fled(self):
        """Ran off the map edge -- out of the fight, but alive and free."""
        return self.status == "fled"

    @property
    def survived(self):
        """Made it through the battle (for the persistence layer). A broken
        automaton is recovered afterwards and a runaway is fine, so both count."""
        return self.status in ("up", "stable", "broken", "fled")

    def raise_from_dead(self, team):
        """Raise Dead: this dead body stands again with 1 HP, on `team`'s side."""
        self.status = "up"
        self.hp = 1
        self.death_clock = 0
        self.raised = True
        self.team = team
        self.ai_ally = False
        self.conditions = []
        self.ap = 0

    def go_down(self, log, knockout=False):
        """Drop to 0 HP. An automaton goes `broken` (no death clock); everyone else
        enters `dying`, restarting the death counter. Called for a standing unit
        downed, or a `stable` unit that takes a hit."""
        # Dismount hook
        if self.rider:
            self.rider.mounted_on = None
            self.rider = None
        if self.mounted_on:
            self.mounted_on.rider = None
            self.mounted_on = None

        self.hp = 0
        self.ferocity_pending = False
        if self.raised:
            self.status = "dead"
            log(f"  {self.name} collapses, dead for good.")
            return
        if self.nonlethal or knockout:
            self.status = "stable"           # knocked out, survives
            log(f"  {self.name} is knocked out" + (" (non-lethal fight)." if self.nonlethal else "."))
            return
        if self._ability.breaks_when_downed:
            if self.status != "broken":
                self.status = "broken"
                log(f"  {self.name} stops working: BROKEN "
                    f"(only back up if an ally repairs it).")
            return
        self.status = "dying"
        self.death_clock = 0
        log(f"  {self.name} goes down, dying ({data.DYING_TURNS} turns to the death save).")

    def check_collapse(self, log):
        """A physical attribute (Str / Dex / Con) at zero drops a standing unit to
        the ground, dying -- checked when the battle starts and whenever poison
        takes another point."""
        gone = self.char.zeroed_attribute
        if gone and self.alive:
            log(f"  {self.name}'s {gone.capitalize()} is gone -- collapses.")
            self.go_down(log)

    # ------------------------------------------------------------------ #
    # conditions                                                         #
    # ------------------------------------------------------------------ #
    def has_condition(self, cid):
        return any(c.id == cid for c in self.conditions)

    def add_condition(self, cond):
        if not self.has_condition(cond.id):
            self.conditions.append(cond)

    def condition(self, cid):
        return next((c for c in self.conditions if c.id == cid), None)

    def hidden_from(self, team):
        """Invisible to `team`: another side that has not found it this round."""
        inv = self.condition("invisible")
        return inv is not None and team != self.team and not inv.wounded and team not in inv.seen_by

    def reveal_to(self, *teams):
        inv = self.condition("invisible")
        if inv is not None:
            inv.seen_by.update(teams)

    def drop_invisibility(self, log):
        inv = self.condition("invisible")
        if inv is not None:
            self.conditions.remove(inv)
            log(f"{self.name} flickers into sight!")

    def _condition_mods(self, field):
        mods = []
        for c in self.conditions:
            mods += getattr(c, field)()
        return mods

    @property
    def defending(self):
        return self.has_condition("defending")

    @property
    def demoralized(self):
        return self.has_condition("demoralized")

    # ------------------------------------------------------------------ #
    # hands / equipment (two hands; weapon takes 1 or 2; a torch or a     #
    # lantern takes the off hand -- only one of the two at a time)        #
    # ------------------------------------------------------------------ #
    @property
    def unarmed(self):
        return not self.weapon_hand

    @property
    def has_torch(self):
        return self.torch_hand

    @property
    def has_lantern(self):
        return self.lantern_hand

    @property
    def light_radius(self):
        """How far this combatant's own held light reaches, 0 if none. Only
        an equipped light source counts -- one riding in the pack stays dark."""
        if self.torch_hand:
            return data.TORCH_RADIUS
        if self.lantern_hand:
            return data.LIGHT_SOURCES[data.LANTERN_ITEM]
        return 0

    def _hands_used(self):
        return ((self.weapon["hands"] if self.weapon_hand else 0)
                + (1 if self.torch_hand else 0) + (1 if self.lantern_hand else 0))

    @property
    def free_hands(self):
        return 2 - self._hands_used()

    def drop_weapon(self):
        """Lets go of the weapon; returns ('weapon', name) so the action can put it
        on the ground, or None."""
        if not self.weapon_hand:
            return None
        self.weapon_hand = False
        return ("weapon", self.weapon_name)

    def drop_torch(self):
        if not self.torch_hand:
            return None
        self.torch_hand = False
        return ("torch", None)

    def drop_lantern(self):
        """A lantern bumped out of the off hand goes back in the pack, not the
        ground -- it is not a torch stuck in dirt, and never appears as loot."""
        if not self.lantern_hand:
            return
        self.lantern_hand = False
        self.inventory.append(data.LANTERN_ITEM)
        return

    def disarm(self):
        """Empties the weapon hand (thrown: the action already handles the ground object)."""
        self.weapon_hand = False

    def equip_torch(self):
        """Takes a torch; drops whatever does not fit in two hands. Returns [dropped]."""
        self.torch_hand = True
        dropped = []
        if self._hands_used() > 2:                    # a two-handed weapon took everything
            dropped.append(self.drop_weapon())
        return [x for x in dropped if x]

    def equip_weapon(self, weapon_name):
        """Equips (or recovers) a weapon; drops whatever does not fit. Returns [dropped]."""
        if not self.char.can_wield(weapon_name):
            return []
        self.weapon_name = weapon_name
        self.weapon = items.get(weapon_name)
        self.weapon_hand = True
        dropped = []
        if self._hands_used() > 2:            # two-handed weapon + a torch/lantern in the other
            dropped.append(self.drop_torch())
            self.drop_lantern()
        return [x for x in dropped if x]

    @property
    def unarmed(self):
        return (not self.weapon_hand) or (self.weapon is None)

    # ------------------------------------------------------------------ #
    # carry (foundation: carried weight vs capacity; no penalty yet)     #
    # ------------------------------------------------------------------ #
    @property
    def load(self):
        w = sum(items.item_weight(it) for it in self.inventory)
        if self.weapon_hand and self.weapon:
            w += self.weapon.weight
        if self.tongue_weapon:
            w += self.tongue_weapon.weight
        if self.torch_hand:
            w += data.TORCH_WEIGHT
        if self.lantern_hand:
            w += items.item_weight(data.LANTERN_ITEM)
        if self.armor:
            relief = min(self.char.talent_bonus("armor_weight_relief") if hasattr(self.char, "talent_bonus") else 0, self.armor.weight)
            w += max(0.0, self.armor.weight - relief)
        return round(w, 1)

    # ------------------------------------------------------------------ #
    # combat                                                             #
    # ------------------------------------------------------------------ #
    @property
    def needs_ammo(self):
        """Wields a weapon that fires ammunition (the crossbow)."""
        return not self.unarmed and self.weapon["range"] > 0

    @property
    def can_reload(self):
        """Crossbow is empty but there are bolts in the quiver -> the Reload
        action can chamber one (1 AP)."""
        return self.needs_ammo and self.weapon.get("reload") and not self.crossbow_loaded and self.ammo > 0

    @property
    def improvised(self):
        """Holding a crossbow that isn't loaded -> swung as an improvised weapon
        (melee, size unarmed die, Strength) until an action is spent to Reload.
        With no bolts left in the quiver that is the only option."""
        if not self.needs_ammo:
            return False
        if not self.weapon.get("reload"):
            return self.ammo == 0
        return not self.crossbow_loaded

    @property
    def ranged(self):
        """Can loose a bolt right now: a crossbow with one chambered."""
        if not self.needs_ammo:
            return False
        if not self.weapon.get("reload"):
            return self.ammo > 0
        return self.crossbow_loaded

    @property
    def attack_range(self):
        """Reach of the HAND weapon. The Tongue weapon has its own, longer reach
        (`tongue_reach`) -- see `actions.AttackTongue`."""
        if self.ranged:
            return self.weapon["range"] + self.char.talent_bonus("ranged_reach")
        return 1 + self._ability.melee_reach

    @property
    def has_tongue_weapon(self):
        return self.tongue_weapon is not None

    @property
    def tongue_reach(self):
        return 1 + self.char.talent_bonus("melee_reach")

    @property
    def can_throw(self):
        return not self.unarmed and self.weapon["thrown"] > 0

    @property
    def throw_range(self):
        if not self.can_throw:
            return 0
        return self.weapon["thrown"] + self.char.talent_bonus("ranged_reach")

    @property
    def speed(self):
        if self.has_condition("grappled"):
            return 0
        s = getattr(self, "_override_speed", None)
        if s is None:
            s = self.char.speed
        for c in self.conditions:
            if hasattr(c, "modify_speed"):
                s = c.modify_speed(s)
        return max(1, s)

    @speed.setter
    def speed(self, val):
        self._override_speed = val

    @property
    def ac(self):
        """Effective AC. Bonuses of the same type do not stack (see resolve_bonus)."""
        mods = self._condition_mods("ac_mods")
        if self.ac_natural:
            mods.append((self.ac_natural, "natural", "race"))
        total, _ = resolve_bonus(mods)
        ac = self.ac_base + total
        if self.has_condition("shield_hooked") and self.equipped_offhand and items.is_shield(self.equipped_offhand):
            shield = items.get(self.equipped_offhand)
            if shield:
                ac -= shield.ac
        return ac

    def ac_vs(self, attacker, armor_pierce=False):
        """AC against one particular attacker: the Leather of Biwolf adds 1 against
        anything that is not a humanoid. If armor_pierce is True, ignores worn armor AC."""
        base = self.ac
        if armor_pierce and self.armor:
            base -= self.armor.ac
        if (self.artifact_name == items.BIWOLF_LEATHER_ITEM
                and attacker.char.race.get("kind", "humanoid") != "humanoid"):
            return base + 1
        return base

    @property
    def mental_defense(self):
        total, _ = resolve_bonus(self._condition_mods("mental_defense_mods"))
        return self.mental_defense_base + total

    def _attr_delta(self, a):
        hexed = self.condition("hexed")
        return hexed.deltas.get(a, 0) if hexed is not None else 0

    def _hexed_mod(a):
        key = f"mod_{a}"
        return property(lambda self: getattr(self.char, key) + self._attr_delta(a),
                        lambda self, value: setattr(self.char, key, value))

    mod_strength = _hexed_mod("strength")
    mod_dexterity = _hexed_mod("dexterity")
    mod_constitution = _hexed_mod("constitution")
    mod_intelligence = _hexed_mod("intelligence")
    mod_wisdom = _hexed_mod("wisdom")
    mod_charisma = _hexed_mod("charisma")
    del _hexed_mod

    def hex_deltas(self):
        """What a Hex does to each modifier: -1 where the score is even, 0 where it is odd."""
        score = getattr(self.char, "attribute_score", None)
        if score is None:
            return dict.fromkeys(data.ATTRIBUTES, 0)
        return {a: data.mod(score(a) - 1) - data.mod(score(a)) for a in data.ATTRIBUTES}

    def hex_hp_cost(self, deltas):
        """The max (and current) HP a Hex takes: one per hit die on an even Constitution."""
        if not deltas["constitution"] or getattr(self.char, "_hp_override", None) is not None:
            return 0
        return min(1 + len(getattr(self.char, "_level_hp_rolls", ())), self.hp_max - 1)

    def hex(self, log):
        """Lay a Hex on this unit; a recast on a hexed unit only renews its length. The AC follows
        the Dexterity drop as far as worn armour lets Dexterity count; an even Constitution takes
        `hex_hp_cost`, the max coming back when the hex wears off."""
        old = self.condition("hexed")
        if old is not None:
            old.held = False
            return
        deltas = self.hex_deltas()
        dex, cap = self.char.mod_dexterity, (self.armor.max_dex if self.armor is not None else None)
        ac_delta = (min(dex + deltas["dexterity"], cap) - min(dex, cap)) if cap is not None else deltas["dexterity"]
        lost = self.hex_hp_cost(deltas)
        self.add_condition(Hexed(deltas, ac_delta, lost))
        if lost:
            self.hp_max -= lost
            self.take_damage(lost, log)

    def initiative_bonus(self):
        return (self.mod_wisdom + self._ability.initiative
                + self.talent_bonus("initiative"))

    def attack_mods(self, target, flanking=False, thrown=False, weapon=None, battle=None):
        """List of (value, type, label) that enter the attack roll. `weapon` (a
        WEAPONS dict) overrides the held one -- the Tongue weapon, always a plain
        1-handed melee strike."""
        def _is_fin(w):
            if w is None:
                return False
            if hasattr(w, "has_trait") and w.has_trait("finesse"):
                return True
            return bool(w.get("finesse", False))

        if weapon is not None:
            if _is_fin(weapon) or self.ability.finesse:
                mods = [(max(self.mod_strength, self.mod_dexterity), None, "STR/DEX")]
                hit_stat = "dex" if self.mod_dexterity >= self.mod_strength else "str"
            else:
                mods = [(self.mod_strength, None, "STR")]
                hit_stat = "str"
        elif thrown:
            mods = [(self.mod_dexterity, None, "DEX")]       # a throw hits with Dexterity
            hit_stat = "dex"
        elif (self.unarmed or self.improvised) and (self.char.talent_bonus("unarmed_finesse") or self.ability.finesse):
            mods = [(max(self.mod_strength, self.mod_dexterity), None, "STR/DEX")]
            hit_stat = "dex" if self.mod_dexterity >= self.mod_strength else "str"
        elif self.unarmed or self.improvised:
            mods = [(self.mod_strength, None, "STR")]
            hit_stat = "str"
        elif self.ranged:
            mods = [(self.mod_dexterity, None, "DEX")]
            hit_stat = "dex"
        elif _is_fin(self.weapon) or self.ability.finesse:
            mods = [(max(self.mod_strength, self.mod_dexterity), None, "STR/DEX")]
            hit_stat = "dex" if self.mod_dexterity >= self.mod_strength else "str"
        else:
            mods = [(self.mod_strength, None, "STR")]
            hit_stat = "str"
        # tier-2 combat talent: +hit on the attribute this attack actually uses
        talent = self.char.talent_bonus(
            "to_hit", "dexterity" if hit_stat == "dex" else "strength")
        if talent:
            mods.append((talent, None, f"{hit_stat.upper()} talent"))
        if self._ability.attack_mods:
            mods += self._ability.attack_mods(self, target, flanking)
        mods += self._condition_mods("attack_mods")
        if battle is not None and target is not None and hasattr(self, "char"):
            full_bonus = self.char.talent_bonus("full_intel_to_hit")
            if full_bonus and intel.has_full_intel(battle, self.team, target):
                mods.append((full_bonus, "circumstance", "Exploit Weakness"))
        return mods

    def damage_roll(self, crit=False, thrown=False, weapon=None, crit_mult=None, bonus_damage=0):
        """`weapon` (a WEAPONS dict or ItemDef) overrides the held one -- the Tongue weapon."""
        if weapon is not None:
            n, faces = weapon["damage"]
            mult = crit_mult or weapon.get("crit_mult", 2)
        elif (self.unarmed or self.improvised) and not thrown:
            n, faces = self.unarmed_damage
            mult = crit_mult or 2
        else:
            n, faces = self.weapon["damage"]
            mult = crit_mult or (self.weapon.get("crit_mult", 2) if self.weapon else 2)
        
        crit_dice = sum(roll(n, faces) for _ in range(max(1, mult) - 1)) if crit else 0
        dice = roll(n, faces) + crit_dice + bonus_damage
        bonus = 0
        if thrown:
            bonus += self.mod_strength              # thrown: add Strength to damage
        elif weapon is not None or not self.ranged:  # melee (includes unarmed and the Tongue)
            bonus += (self.mod_strength + self._ability.melee_damage
                      + self.char.talent_bonus("melee_damage"))
        return max(1, dice + bonus)

    def take_damage(self, amount, log, knockout=False):
        amount = max(0, amount - self.dr)
        
        # Wakes up if sleeping
        sleeping_cond = next((c for c in self.conditions if c.id == "sleeping"), None)
        if sleeping_cond:
            self.conditions.remove(sleeping_cond)
            log(f"{self.name} is jolted awake by the attack!")
            
        self.hp -= amount
        log(f"{self.name} takes {amount} damage (HP {max(self.hp, 0)}/{self.hp_max}).")
        inv = self.condition("invisible")
        if inv is not None and amount > 0:
            inv.wounded = True
        if self.hp <= 0:
            if self._ability.on_downed and self.spend_once("on_downed"):
                self._ability.on_downed(self, log)
            else:
                self.go_down(log, knockout)

    # ------------------------------------------------------------------ #
    # turn cycle                                                         #
    # ------------------------------------------------------------------ #
    def start_turn(self, log):
        self.ap = AP_PER_TURN
        self.walking = False
        self.moved = 0
        self.diag_steps = 0
        self.last_path = self.path
        self.path = [self.pos]
        self.conditions = [c for c in self.conditions
                           if not c.on_turn_start(self, log)]
        if self._ability.on_turn_start and self.alive:
            self._ability.on_turn_start(self, log)

    def end_turn(self, log):
        self.conditions = [c for c in self.conditions
                           if not c.on_turn_end(self, log)]
        if self.ferocity_pending:
            self.ferocity_pending = False
            if self.hp <= 0 and self.alive:
                log(f"{self.name}: ferocity runs out.")
                self.go_down(log)
                downer = self.ferocity_downer
                if downer is not None and downer.team != self.team:
                    downer.credit_kill(self)     # the hit that brought it to 0 lands the kill now
                self.ferocity_downer = None
