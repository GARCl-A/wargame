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

from . import data, progression
from .data import resolve_bonus, roll

AP_PER_TURN = 2


class Combatant:
    def __init__(self, char, team=None):
        self.char = char
        self.team = team or getattr(char, "team", "player")
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

    def reset_battle_state(self):
        c = self.char
        self.hp = c.hp_max
        self.pos = (0, 0)
        self.status = "up"            # up | dying | stable | broken | fled | dead
        self.death_clock = 0          # dying: own turns elapsed; save on DYING_TURNS
        self.nonlethal = False        # set by Battle for a non-lethal fight: 0 HP -> knocked out
        self.ferocity_pending = False # Orc downed this turn, falls at end_turn
        self.initiative = 0           # set by Battle._roll_initiative
        self.weapon_hand = c.equipped_weapon is not None
        self.weapon_name = c.equipped_weapon
        self.weapon = data.WEAPONS.get(c.equipped_weapon)
        self.torch_hand = False
        if c.equipped_offhand == data.TORCH_ITEM:
            weapon_hands = self.weapon["hands"] if self.weapon_hand else 0
            self.torch_hand = weapon_hands < 2       # a 2-handed weapon leaves no off hand
        self.inventory = list(c._base_inventory)
        self.ammo = data.QUIVER_AMMO if data.AMMO_ITEM in self.inventory else 0
        self.first_aid_charges = (data.FIRST_AID_CHARGES
                                  if data.FIRST_AID_ITEM in self.inventory else 0)
        self.conditions = []
        self.ap = AP_PER_TURN
        self.walking = False          # a walk is in progress (same Move action)
        self.moved = 0                # squares already spent in the current walk
        self.path = []                # cells walked this turn: [start, ..., pos]
        self.last_path = []           # the previous turn's path (kept for future mechanics)
        self.used_abilities = set()   # keys of once-per-battle effects already spent
        self.kills = 0                # enemies this combatant downed (count, for display)
        self.combat_xp_earned = 0     # combat XP from those kills, by level difference
        self.ferocity_downer = None   # who brought this unit to 0 HP while Ferocity keeps it up

    def credit_kill(self, victim):
        """Book a downed enemy: +1 to the kill count, plus combat XP scaled by the
        level gap (`progression.xp_award` -- nothing for a victim below your level)."""
        self.kills += 1
        self.combat_xp_earned += progression.xp_award(self.combat_level,
                                                      victim.combat_level)

    def spend_once(self, key):
        """Mark a once-per-battle effect as used. Returns True the first time only."""
        if key in self.used_abilities:
            return False
        self.used_abilities.add(key)
        return True

    # ------------------------------------------------------------------ #
    # lifecycle: up -> dying -> (stable | dead)   (see GARTOK-regras.md) #
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

    def go_down(self, log):
        """Drop to 0 HP. An automaton goes `broken` (no death clock); everyone else
        enters `dying`, restarting the death counter. Called for a standing unit
        downed, or a `stable` unit that takes a hit."""
        self.hp = 0
        self.ferocity_pending = False
        if self.nonlethal:
            self.status = "stable"           # non-lethal fight: knocked out, survives
            log(f"  {self.name} is knocked out (non-lethal fight).")
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

    # ------------------------------------------------------------------ #
    # conditions                                                         #
    # ------------------------------------------------------------------ #
    def has_condition(self, cid):
        return any(c.id == cid for c in self.conditions)

    def add_condition(self, cond):
        if not self.has_condition(cond.id):
            self.conditions.append(cond)

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
    # hands / equipment  (two hands; weapon takes 1 or 2; torch takes 1) #
    # ------------------------------------------------------------------ #
    @property
    def unarmed(self):
        return not self.weapon_hand

    @property
    def has_torch(self):
        return self.torch_hand

    def _hands_used(self):
        return (self.weapon["hands"] if self.weapon_hand else 0) + (1 if self.torch_hand else 0)

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
        self.weapon_name = weapon_name
        self.weapon = data.WEAPONS[weapon_name]
        self.weapon_hand = True
        dropped = []
        if self._hands_used() > 2:                    # two-handed weapon + torch in the other
            dropped.append(self.drop_torch())
        return [x for x in dropped if x]

    # ------------------------------------------------------------------ #
    # carry (foundation: carried weight vs capacity; no penalty yet)     #
    # ------------------------------------------------------------------ #
    @property
    def load(self):
        w = sum(data.item_weight(it) for it in self.inventory)
        if self.weapon_hand:
            w += self.weapon["weight"]
        if self.torch_hand:
            w += data.TORCH_WEIGHT
        if self.armor:
            w += self.armor.get("weight", 0)
        return round(w, 1)

    # ------------------------------------------------------------------ #
    # combat                                                             #
    # ------------------------------------------------------------------ #
    @property
    def needs_ammo(self):
        """Wields a weapon that fires ammunition (the crossbow)."""
        return not self.unarmed and self.weapon["range"] > 0

    @property
    def improvised(self):
        """Wielding a ranged weapon with no ammo left -> swung as an improvised
        weapon: melee, size unarmed die, Strength."""
        return self.needs_ammo and self.ammo <= 0

    @property
    def ranged(self):
        return self.needs_ammo and not self.improvised

    @property
    def attack_range(self):
        if self.ranged:
            return self.weapon["range"] + self.char.talent_bonus("ranged_reach")
        return 1

    @property
    def can_throw(self):
        return not self.unarmed and self.weapon["thrown"] > 0

    @property
    def throw_range(self):
        if not self.can_throw:
            return 0
        return self.weapon["thrown"] + self.char.talent_bonus("ranged_reach")

    @property
    def ac(self):
        """Effective AC. Bonuses of the same type do not stack (see resolve_bonus)."""
        mods = self._condition_mods("ac_mods")
        if self.ac_natural:
            mods.append((self.ac_natural, "natural", "race"))
        total, _ = resolve_bonus(mods)
        return self.ac_base + total

    @property
    def mental_defense(self):
        total, _ = resolve_bonus(self._condition_mods("mental_defense_mods"))
        return self.mental_defense_base + total

    def initiative_bonus(self):
        return self.mod_dexterity + self._ability.initiative

    def attack_mods(self, target, flanking=False, thrown=False):
        """List of (value, type, label) that enter the attack roll."""
        if thrown:
            mods = [(self.mod_dexterity, None, "DEX")]       # a throw hits with Dexterity
            hit_stat = "dex"
        elif self.unarmed or self.improvised:
            mods = [(self.mod_strength, None, "STR")]
            hit_stat = "str"
        elif self.ranged:
            mods = [(self.mod_dexterity, None, "DEX")]
            hit_stat = "dex"
        elif self.weapon["finesse"]:
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
        return mods

    def damage_roll(self, crit=False, thrown=False):
        if (self.unarmed or self.improvised) and not thrown:
            n, faces = self.unarmed_damage
        else:
            n, faces = self.weapon["damage"]
        dice = roll(n, faces) + (roll(n, faces) if crit else 0)
        bonus = 0
        if thrown:
            bonus += self.mod_strength              # thrown: add Strength to damage
        elif not self.ranged:                       # melee (includes unarmed)
            bonus += (self.mod_strength + self._ability.melee_damage
                      + self.char.talent_bonus("melee_damage"))
        return max(1, dice + bonus)

    def take_damage(self, amount, log):
        amount = max(0, amount - self.dr)
        self.hp -= amount
        log(f"{self.name} takes {amount} damage (HP {max(self.hp, 0)}/{self.hp_max}).")
        if self.hp <= 0:
            if self._ability.on_downed and self.spend_once("on_downed"):
                self._ability.on_downed(self, log)
            else:
                self.go_down(log)

    # ------------------------------------------------------------------ #
    # turn cycle                                                         #
    # ------------------------------------------------------------------ #
    def start_turn(self, log):
        self.ap = AP_PER_TURN
        self.walking = False
        self.moved = 0
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
