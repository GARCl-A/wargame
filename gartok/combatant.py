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

from . import (
    conditions,
    data,
    draw,
    i18n,
    intel,
    items,
    morale,
    natural_weapons,
    progression,
)
from .conditions import DEMORALIZE_MAX_STACKS, Hexed, Prone
from .data import resolve_bonus, roll_dice
from .i18n import Ref
from .unit import flatten_pack

AP_PER_TURN = 2
PINNING = ("grappled", "entangled", "rooted", "prone")    # hold a body to the ground: no hovering
UNDER_THE_WHIP_RANGE = 6     # squares to the stronger ally a Goblin fights for
RUN_DOWN_RUN_UP = 4          # squares walked this turn before a Centaur's attacks run the foe down



class Combatant:
    def __init__(self, char, team=None, ai_ally=False):
        self.char = char
        self.team = team or getattr(char, "team", "player")
        self.ai_ally = ai_ally        # on the player's side, but played by ai/ (not the guild's)
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
    def winged(self):
        """Flies on its own -- the race or a talent -- not on borrowed Pixie Dust."""
        return self._ability.flies or bool(getattr(self.char, "talent_bonus", lambda _: 0)("flies"))

    @property
    def flies(self):
        return self.winged or self.has_condition("pixie_flight")

    @property
    def altitude(self):
        """Levels hovering above the floor. Anything that pins a body -- a grip, a web, roots, a fall
        to the ground -- pulls a flier down to it, no hurt."""
        if self._altitude and any(self.has_condition(c) for c in PINNING):
            self._altitude = 0
        return self._altitude

    @altitude.setter
    def altitude(self, levels):
        self._altitude = levels

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
        self._altitude = 0            # levels hovering above that floor (a flier's Fly up / Fly down)
        self.status = "up"            # up | dying | stable | broken | fled | dead
        self.death_clock = 0          # dying: own turns elapsed; save on DYING_TURNS
        self.raised = False           # stood back up by Raise Dead: undead now, falls for good
        self.nonlethal = False        # set by Battle for a non-lethal fight: 0 HP -> knocked out
        self.ferocity_pending = False # Orc downed this turn, falls at end_turn
        self.rounds_submerged = 0     # turns spent underwater in deep water (breath / drowning)
        self.initiative = 0           # set by Battle._roll_initiative
        self.extra_initiative = None  # a legendary body's second roll (the lower one): its second slot in the order
        self.delayed = False          # waiting at the end of the order; its turn resumes, not restarts
        self.delay_round = 0          # round of its last Delay: one per round (rounds start at 1)
        self.weapon_hand = c.equipped_weapon is not None
        self.let_go = None            # {"at": name} while the weapon lies thrown on the ground
        self.weapon_name = c.equipped_weapon
        self._held = items.get(c.equipped_weapon)
        self._natural = c.natural_weapon
        # the Tongue is a separate limb: its weapon rides alongside the hands
        self.tongue_weapon_name = c.equipped_tongue if c.has_tongue else None
        self.tongue_weapon = items.get(self.tongue_weapon_name)
        self.artifact_name = c.equipped_artifact
        self.torch_hand = False
        self.lantern_hand = False
        self.drew = False             # hands changed with Draw: the character carries them back (`draw.carry_back`)
        self.shield_ac_delta = 0      # the AC a shield drawn or stowed in the fight adds to the character's own
        self.on_fall = None           # set by the battle: puts what a fallen unit lets go of on the ground
        if c.equipped_offhand in (data.TORCH_ITEM, data.LANTERN_ITEM):
            weapon_hands = self.weapon.hands if self.weapon_hand else 0
            free_off_hand = weapon_hands < 2         # a 2-handed weapon leaves no off hand
            if c.equipped_offhand == data.TORCH_ITEM:
                self.torch_hand = free_off_hand
            else:
                self.lantern_hand = free_off_hand
        self.inventory = flatten_pack(c)
        self.ammo = (getattr(c, "quiver_charges", data.QUIVER_AMMO)
                     if data.AMMO_ITEM in self.inventory else 0)
        # a crossbow holds one bolt at a time and starts the fight with one chambered from the quiver
        self.crossbow_loaded = False
        self.last_damage = None
        if self.weapon.get("reload") and self.ammo > 0:
            self.ammo -= 1
            self.crossbow_loaded = True
        # first aid charges are now persistent (campaign-long).
        self.first_aid_charges = (c.first_aid_charges
                                  if data.FIRST_AID_ITEM in self.inventory else 0)
        self.spells_known = list(getattr(c, "spells_known", []))
        self.conditions = []
        self.ap = AP_PER_TURN
        self.walking = False          # a walk is in progress (same Move action)
        self.moved = 0                # movement cost already spent in the current walk
        self.free_step_used = False   # the Free Step talent's square, once a turn
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
        self.hurt_by = set()          # who has landed a blow on this unit this fight (Grudge)
        self.turns_taken = 0          # turns begun this fight (Ambush Predator)
        self.demoralized_hits = 0     # Demoralized landed on this unit, each one counted
        self.demoralize_extra = 0     # morale points a Dread Voice took on top of those hits (morale reads the rise)
        morale.start(self)

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
            log("log.down.raised", unit=self.name)
            return
        self._fall_to_the_ground()
        if self.nonlethal or knockout:
            self.status = "stable"           # knocked out, survives
            log("log.down.knocked_out_fight" if self.nonlethal else "log.down.knocked_out", unit=self.name)
            return
        if self._ability.breaks_when_downed:
            if self.status != "broken":
                self.status = "broken"
                log("log.down.broken", unit=self.name)
            return
        self.status = "dying"
        self.death_clock = 0
        log("log.down.dying", unit=self.name, turns=data.DYING_TURNS)

    def _fall_to_the_ground(self):
        """A body that goes down lies Prone and lets go of what its hands hold, which the battle puts
        on a free cell beside it (a unit with no battle around it keeps its kit)."""
        if not self.has_condition("prone"):
            self.add_condition(Prone())
        if self.on_fall is not None:
            self.on_fall(self, self.let_go_of_kit())

    def let_go_of_kit(self):
        """Empties both hands; -> [(kind, item name)] for the ground. A natural weapon cannot be let go,
        a lantern goes back to the pack (see `drop_lantern`)."""
        out = []
        shield = draw.hands(self)[1]
        weapon = self.drop_weapon()
        if weapon:
            if self.crossbow_loaded:
                self.ammo += 1
                self.crossbow_loaded = False
            out.append(weapon)
        torch = self.drop_torch()
        if torch:
            out.append(torch)
        self.drop_lantern()
        if shield and items.is_shield(shield):
            self.equipped_offhand = None
            self.shield_ac_delta -= items.get(shield).ac
            out.append(("shield", shield))
        return out

    def equip_shield(self, shield_name):
        """Takes a shield in the free off hand (the caller checked `can_take_shield`)."""
        self.equipped_offhand = shield_name
        self.shield_ac_delta += items.get(shield_name).ac

    @property
    def can_take_shield(self):
        """An empty off hand with a one-handed (or no) weapon in the other."""
        return self.free_hands >= 1 and not draw.hands(self)[1]

    def check_collapse(self, log):
        """An attribute at zero (poison, hunger and Hex counted) drops a standing unit to
        the ground, dying -- checked when the battle starts and whenever poison or Hex
        takes another point."""
        gone = self.char.zeroed_by(self.hex_points())
        if gone and self.alive:
            attribute = Ref("attribute", gone, gone.capitalize())
            poison = self.char.worst_poison(gone)
            if poison is None:
                log("log.down.zeroed", unit=self.name, attribute=attribute)
            else:
                log("log.down.zeroed_by_poison", unit=self.name, attribute=attribute,
                    poison=Ref("poison", poison.id, poison.name))
            self.go_down(log)

    # ------------------------------------------------------------------ #
    # conditions                                                         #
    # ------------------------------------------------------------------ #
    def has_condition(self, cid):
        return any(c.id == cid for c in self.conditions)

    @property
    def shaken(self):
        """The morale points Demoralize has taken from this unit so far (`morale.settle` reads the rise)."""
        return self.demoralized_hits + self.demoralize_extra

    @property
    def demoralize_stacks(self):
        held = self.condition("demoralized")
        return held.stacks if held else 0

    @property
    def routed(self):
        """Morale spent: `ai/` runs this unit for the exit (`morale.settle` sets and lifts it)."""
        return self.has_condition("routed")

    def add_condition(self, cond):
        if cond.id == "demoralized":
            if self.demoralize_stacks >= DEMORALIZE_MAX_STACKS:       # nothing more to shake out of it this turn
                return
            self.demoralized_hits += 1
        held = self.condition(cond.id)
        if held is None:
            self.conditions.append(cond)
        elif hasattr(held, "stack"):
            held.stack(cond)

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
            log("log.flickers", unit=self.name)

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
        self._held = items.get(weapon_name)
        self.weapon_hand = True
        self.let_go = None
        dropped = []
        if self._hands_used() > 2:            # two-handed weapon + a torch/lantern in the other
            dropped.append(self.drop_torch())
            self.drop_lantern()
        return [x for x in dropped if x]

    @property
    def weapon(self):
        """What the weapon hand strikes with: the item held, or the body's own weapon."""
        return self._held if self.weapon_hand and self._held else self._natural

    @property
    def held(self):
        """The item last put in the weapon hand (still the one on the ground after a throw)."""
        return self._held

    @property
    def armed(self):
        return self.weapon is self._held

    @property
    def unarmed(self):
        """Bare hands: nothing held and no natural weapon of its own (a humanoid)."""
        return not self.armed and self._natural.name == natural_weapons.DEFAULT

    @property
    def natural(self):
        """Fights with its race's own weapon (a Bite, Claws): nothing held."""
        return not self.armed and not self.unarmed

    @property
    def hand_die(self):
        """The damage die of the hand attack: the weapon's, or the body's when a crossbow is swung empty."""
        return (self._natural if self.improvised else self.weapon)["damage"]

    @property
    def attack_weapon(self):
        """The weapon that is actually swung: the body's own while a crossbow is swung empty."""
        return self._natural if self.improvised else self.weapon

    # ------------------------------------------------------------------ #
    # carry (foundation: carried weight vs capacity; no penalty yet)     #
    # ------------------------------------------------------------------ #
    @property
    def load(self):
        w = sum(items.item_weight(it) for it in self.inventory)
        if self.weapon_hand and self._held:
            w += self._held.weight
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
        return self.weapon["range"] > 0

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
        """Reach of the HAND weapon: its own (`ItemDef.reach`) plus the body's. The Tongue weapon
        has its own, longer reach (`tongue_reach`) -- see `actions.AttackTongue`."""
        if self.ranged:
            return self.weapon["range"] + self.char.talent_bonus("ranged_reach")
        return 1 + self._ability.melee_reach + self.weapon.reach

    @property
    def has_tongue_weapon(self):
        return self.tongue_weapon is not None

    @property
    def tongue_reach(self):
        return 1 + self.char.talent_bonus("melee_reach") + (self.tongue_weapon.reach if self.tongue_weapon else 0)

    @property
    def free_hand(self):
        """The off hand holds nothing: no shield, no torch or lantern in it, and the weapon is one-handed."""
        shield = bool(self.equipped_offhand) and items.is_shield(self.equipped_offhand)
        return self.free_hands >= 1 and not shield

    @property
    def _finesse_in_hand(self):
        w = self.attack_weapon
        return (w.is_finesse if hasattr(w, "is_finesse") else bool(w.get("finesse", False))) or self.ability.finesse

    def melee_damage_mod(self, weapon=None):
        """What a melee blow adds to the weapon's roll: Dexterity for a finesse weapon (and the
        Duelist's point while the off hand is empty), Strength otherwise, plus the flat bonuses."""
        w = weapon if weapon is not None else self.attack_weapon
        finesse = (w.is_finesse if hasattr(w, "is_finesse") else bool(w.get("finesse", False))) or self.ability.finesse
        bonus = self.mod_dexterity if finesse else self.mod_strength
        bonus += self._ability.melee_damage + self.char.talent_bonus("melee_damage")
        if finesse and self.free_hand:
            bonus += self.char.talent_bonus("free_hand_damage")
        return bonus

    @property
    def is_dex_melee(self):
        if self.ranged:
            return False
        return bool(self.attack_weapon.is_finesse or self.ability.finesse)

    @property
    def can_throw(self):
        return self.weapon["thrown"] > 0

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
        ac = self.ac_base + total + self.shield_ac_delta
        if self.char.talent_bonus("free_hand_ac") and self._finesse_in_hand and self.free_hand:
            ac += self.char.talent_bonus("free_hand_ac")
        if self.has_condition("shield_hooked") and self.equipped_offhand and items.is_shield(self.equipped_offhand):
            shield = items.get(self.equipped_offhand)
            if shield:
                ac -= shield.ac
        return ac

    @property
    def pierceable_ac(self):
        """The AC an Armor Pierce strike takes off: only a metal armor is pierced."""
        a = self.armor
        return a.ac if a and a.armor_material == items.ArmorMaterial.METAL else 0

    def ac_vs(self, attacker, armor_pierce=False, ranged=None):
        """AC against one particular attacker: the Leather of Biwolf adds 1 against
        anything that is not a humanoid. If armor_pierce is True, ignores worn armor AC.
        `ranged` is whether the blow comes from afar (default: the attacker's held weapon)."""
        base = self.ac
        if armor_pierce:
            base -= self.pierceable_ac
        if (self.artifact_name == items.BIWOLF_LEATHER_ITEM
                and attacker.char.race.get("kind", "humanoid") != "humanoid"):
            base += 1
        if data.SIZE_ORDER.index(attacker.size) >= data.SIZE_ORDER.index("Large"):
            base += self.char.talent_bonus("underfoot")
        if attacker.ranged if ranged is None else ranged:
            base += self.char.talent_bonus("tiny_target")
        return base

    @property
    def touch_ac(self):
        """AC against a spell that needs no blow past armour: 10 + Dexterity (the armour's cap
        ignored) + the typed bonuses, the size bonus, never the armour, the shield or a Hex (already in Dexterity)."""
        mods = [m for m in self._condition_mods("ac_mods") if m[1] != "hex"]
        if self.ac_natural:
            mods.append((self.ac_natural, "natural", "race"))
        total, _ = resolve_bonus(mods)
        return 10 + self.mod_dexterity + self.char.talent_bonus("ac") + data.SIZES[self.size]["ac"] + total

    @property
    def mental_defense(self):
        total, _ = resolve_bonus(self._condition_mods("mental_defense_mods"))
        bonus = 0
        if self.has_condition("defending") and hasattr(self, "char"):
            bonus += getattr(self.char, "talent_bonus", lambda _: 0)("defend_mental_defense")
        return self.mental_defense_base + total + bonus

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

    def hex_points(self):
        hexed = self.condition("hexed")
        return hexed.points if hexed is not None else 0

    def hex_deltas(self, points=None):
        """What `points` of Hex (the ones on this unit by default) do to each modifier: the modifier of
        the score `points` lower, against the modifier of the score as it stands."""
        score = getattr(self.char, "attribute_score", None)
        if score is None:
            return dict.fromkeys(data.ATTRIBUTES, 0)
        points = self.hex_points() if points is None else points
        return {a: data.mod(score(a) - points) - data.mod(score(a)) for a in data.ATTRIBUTES}

    def hex_hp_cost(self, deltas):
        """The max (and current) HP a Hex takes: one per hit die for each step the Constitution modifier falls."""
        if not deltas["constitution"] or getattr(self.char, "_hp_override", None) is not None:
            return 0
        return -deltas["constitution"] * (1 + len(getattr(self.char, "_level_hp_rolls", ())))

    def hex_ac_delta(self, deltas):
        """What a Hex does to the AC: the Dexterity drop, as far as worn armour lets Dexterity count."""
        dex, cap = self.char.mod_dexterity, (self.armor.max_dex if self.armor is not None else None)
        return (min(dex + deltas["dexterity"], cap) - min(dex, cap)) if cap is not None else deltas["dexterity"]

    def hex_sync(self, log):
        """Bring the Hex's modifiers, AC and max HP in line with the stacks it holds now."""
        hexed = self.condition("hexed")
        deltas = self.hex_deltas(hexed.points)
        wanted = min(self.hex_hp_cost(deltas), self.hp_max + hexed.hp_lost - 1)
        diff = wanted - hexed.hp_lost
        hexed.deltas, hexed.ac_delta, hexed.hp_lost = deltas, self.hex_ac_delta(deltas), wanted
        self.hp_max -= diff
        if diff > 0:
            self.take_damage(diff, log)

    def hex(self, log):
        """Lay one more stack of Hex on this unit."""
        hexed = self.condition("hexed")
        if hexed is None:
            hexed = Hexed()
            self.add_condition(hexed)
        hexed.add_stack(conditions.HEX_POINTS, conditions.HEX_TURNS)
        self.hex_sync(log)

    @property
    def legendary(self):
        return bool(getattr(self.char, "legendary", False))

    def set_initiative(self, rolls):
        """`rolls` (one per slot, the higher first): the first is its initiative, a second its extra slot."""
        self.initiative = rolls[0]
        self.extra_initiative = rolls[1] if len(rolls) > 1 else None

    def initiative_bonus(self):
        return (self.mod_wisdom + self._ability.initiative
                + self.talent_bonus("initiative"))

    def attack_mods(self, target, flanking=False, thrown=False, weapon=None, battle=None):
        """List of (value, type, label) that enter the attack roll. `weapon` (a
        WEAPONS dict) overrides the held one -- the Tongue weapon, always a plain
        1-handed melee strike."""
        def _is_fin(w):
            return w.is_finesse if hasattr(w, "is_finesse") else bool(w.get("finesse", False))

        if weapon is not None:
            dex = _is_fin(weapon) or self.ability.finesse
        else:                                                # a throw or a shot hits with Dexterity
            dex = thrown or self.ranged or _is_fin(self.attack_weapon) or self.ability.finesse
        if dex:
            mods = [(self.mod_dexterity, None, "DEX")]
            hit_stat = "dex"
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
        run = self.run_down_bonus("run_down_hit")
        if run:
            mods.append((run, None, i18n.t("log.mod.run_down")))
        if battle is not None and target is not None and hasattr(self, "char"):
            full_bonus = self.char.talent_bonus("full_intel_to_hit")
            if full_bonus and intel.has_full_intel(battle, self.team, target):
                mods.append((full_bonus, "circumstance", i18n.t("log.mod.exploit_weakness")))
            mods += self.racial_hit_mods(battle, target)
        return mods

    def run_down_bonus(self, effect):
        """Centaur Run Down: the talent's bonus once the unit has walked `RUN_DOWN_RUN_UP` squares this turn, else 0."""
        if len(self.path) - 1 < RUN_DOWN_RUN_UP:
            return 0
        return int(self.char.talent_bonus(effect))

    def racial_hit_mods(self, battle, target):
        """The racial talents that add to this unit's attack on `target`. Untyped, so they stack."""
        c = self.char
        mods = []
        grudge = c.talent_bonus("grudge")
        if grudge and target in self.hurt_by:
            mods.append((grudge, None, i18n.t("log.mod.grudge")))
        ambush = c.talent_bonus("ambush_predator")
        if ambush:
            from .actions.base import off_guard  # local: actions imports this module
            if off_guard(battle, self, target):
                mods.append((ambush, None, i18n.t("log.mod.ambush_predator")))
        whip = c.talent_bonus("under_the_whip")
        if whip and any(u.alive and u.team == self.team and u is not self
                        and u.combat_level > self.combat_level
                        and battle.units_distance(self, u) <= UNDER_THE_WHIP_RANGE
                        for u in battle.units):
            mods.append((whip, None, i18n.t("log.mod.under_the_whip")))
        arena = c.talent_bonus("arena_born")
        if arena and getattr(battle, "arena", False):
            mods.append((arena, None, i18n.t("log.mod.arena_born")))
        mount = self.mounted_on
        if mount is not None and len(mount.path) > 1:
            charge = mount.char.talent_bonus("cavalry_charge")
            if charge:
                mods.append((charge, None, i18n.t("log.mod.cavalry_charge")))
        return mods

    @property
    def resupplies_throw(self):
        """A thrown weapon is replaced by an identical one from the pack, at no action (Ready Hand)."""
        return self.can_throw and self.char.talent_bonus("throw_resupply") > 0 and self.weapon_name in self.inventory

    @property
    def shoots_crossbow(self):
        return self.ranged and not self.improvised and getattr(self.weapon, "family", None) == "crossbow"

    def crit_brutal(self):
        """The Brutal a critical hit of this unit carries (Savage Attacks)."""
        return int(self.char.talent_bonus("savage_attacks"))

    def damage_roll(self, crit=False, thrown=False, weapon=None, crit_mult=None, bonus_damage=0, brutal=0):
        """The damage of one blow: the weapon's roll and its modifiers, once more for each point of
        `brutal`, then `bonus_damage`; a critical hit multiplies the whole sum, last.
        `weapon` (a WEAPONS dict or ItemDef) overrides the held one -- the Tongue weapon."""
        w = weapon if weapon is not None else (self._natural if self.improvised and not thrown else self.weapon)
        n, faces = w["damage"]
        bonus = 0
        if thrown:
            bonus += self.mod_strength              # thrown: add Strength to damage
        elif weapon is not None or not self.ranged:  # melee (includes unarmed and the Tongue)
            bonus += self.melee_damage_mod(w)
        elif self.ranged:
            bonus += self.char.talent_bonus("ranged_damage")
            if self.shoots_crossbow:
                bonus += self.char.talent_bonus("crossbow_damage")
        bonus_damage += self.run_down_bonus("run_down_damage")
        if crit:
            brutal += self.crit_brutal()
        each = [roll_dice(n, faces) for _ in range(1 + brutal)]
        dice = [sum(group) for group in each]
        total = sum(d + bonus for d in dice) + bonus_damage
        mult = max(1, crit_mult or w.get("crit_mult", 2)) if crit else 1
        total *= mult
        self.last_damage = {"dice": f"{n}d{faces}" if len(dice) == 1 else f"{len(dice)}x{n}d{faces}", "rolls": dice, "each": each, "faces": faces, "mod": bonus * len(dice), "flat": bonus_damage, "mult": mult}
        return max(1, total)

    def damage_detail(self):
        """The last `damage_roll` as the log prints it: `2d6(3+5) +2 x2`, each term the rule added."""
        d = self.last_damage
        if d is None:
            return ""
        text = f"{d['dice']}({'+'.join(str(v) for group in d['each'] for v in group)})"
        extra = d["mod"] + d["flat"]
        if extra:
            text += f" {extra:+}"
        if d["mult"] > 1:
            text = f"({text}) x{d['mult']}"
        return text

    def take_damage(self, amount, log, knockout=False, ignore_dr=False):
        if not ignore_dr:
            amount = max(0, amount - self.dr)
        
        # Wakes up if sleeping
        sleeping_cond = next((c for c in self.conditions if c.id == "sleeping"), None)
        if sleeping_cond:
            self.conditions.remove(sleeping_cond)
            log("log.jolted", unit=self.name)
            
        self.hp -= amount
        log("log.takes_damage", unit=self.name, dmg=amount, hp=max(self.hp, 0), hp_max=self.hp_max)
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
        self.turns_taken += 1
        self.ap = AP_PER_TURN
        self.walking = False
        self.moved = 0
        self.free_step_used = False
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
                log("log.ferocity_ends", unit=self.name)
                self.go_down(log)
                downer = self.ferocity_downer
                if downer is not None and downer.team != self.team:
                    downer.credit_kill(self)     # the hit that brought it to 0 lands the kill now
                self.ferocity_downer = None
