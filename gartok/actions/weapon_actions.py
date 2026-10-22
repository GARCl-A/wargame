"""Weapon actions: unique tactical options granted by equipped weapon traits.

A 2-AP action is one strike for the price of two plain attacks, so out of its favoured case it is
the worse buy; in that case (`favoured`) the strike lands twice over -- a second roll of the
weapon's damage -- plus the action's own edge, and beats the two attacks for any weapon or
modifier:
- Dagger: Sneak Attack (a flanked foe; +1d4)
- Rapier: Precise Thrust (a flanked foe; +2 to hit)
- Axe / Dwarf Axe: Cleave (a second foe beside both: two swings, each +2 to hit)
- Quarterstaff: Repel Strike (shoves the foe; with its back to a wall or a body it is slammed)
- Club / Hammer / Light Hammer: Maiming Strike (halves foe speed; a foe that cannot dodge)
- Pick / Light Pick: Armor Pierce (ignores worn armor AC; an armoured foe)
- Shortbow: Power Shot (+STR; a foe at half the bow's range or farther)
- Light Crossbow: Extreme Shot (doubles range to 36 squares: the only shot past the normal one)
- Hatchet: Hook Shield (nullifies foe shield AC until next round; a foe with a shield)
- Shortspear: Javelin Charge (1 AP, thrown after moving this turn, +1d4)
- Broadsword: Parry & Strike (gains Defending; two or more foes in reach)
"""

from .. import items
from ..conditions import Defending, Maimed, ShieldHooked
from ..data import d20, resolve_bonus, roll
from ..ground import GroundObject
from .base import (
    Action,
    _cell_free,
    _drop_cell,
    _flanked,
    _hostile_target,
    _pack_flank,
    _resolve_hit,
    _sign,
)
from .combat import PUSH_DC_BASE

UNGUARDED = ("entangled", "sleeping", "surprised", "demoralized")


def _second_blow(actor, favoured, **kw):
    """A favoured strike lands twice over: one more roll of the weapon's damage, or 0."""
    return actor.damage_roll(**kw) if favoured else 0


def _log_twice(battle, res, favoured, why):
    if favoured and res in ("hit", "crit"):
        battle.log(f"  {why}: the blow lands twice over!")


# --------------------------------------------------------------------------- #
# Dagger: Sneak Attack                                                        #
# --------------------------------------------------------------------------- #

class SneakAttack(Action):
    id, name, cost, target, aimed = "sneak_attack", "Sneak Attack", 2, "enemy", True
    desc = "2 AP: Only against a flanked foe: the blow lands twice over, +1d4."

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if getattr(actor, "unarmed", False) or w is None or not w.has_trait("sneak_attack"):
            return False, "requires dagger"
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        return _flanked(battle, actor, target) and battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Sneak Attack (2 pts, double damage +1d4 vs flanked)"

    def favoured(self, battle, actor, target):
        return _flanked(battle, actor, target)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        bonus_dmg = roll(1, 4) + _second_blow(actor, True)

        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), battle=battle)
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Sneak Attack -> {target.name}"
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix, bonus_damage=bonus_dmg)
        _log_twice(battle, res, True, "Sneak Attack strikes a vulnerable spot")


# --------------------------------------------------------------------------- #
# Rapier: Precise Thrust                                                      #
# --------------------------------------------------------------------------- #

class PreciseThrust(Action):
    id, name, cost, target, aimed = "precise_thrust", "Precise Thrust", 2, "enemy", True
    desc = "2 AP: Only against a flanked foe: +2 to hit, the blow lands twice over."

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if getattr(actor, "unarmed", False) or w is None or not w.has_trait("precise_thrust"):
            return False, "requires rapier"
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        return _flanked(battle, actor, target) and battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Precise Thrust (2 pts, +2 to hit & double damage vs flanked)"

    def favoured(self, battle, actor, target):
        return _flanked(battle, actor, target)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), battle=battle)
        mods.append((2, "circumstance", "Precise Thrust"))

        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Precise Thrust -> {target.name}"
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix,
                           bonus_damage=_second_blow(actor, True))
        _log_twice(battle, res, True, "The thrust finds the gap")


# --------------------------------------------------------------------------- #
# Axe / Dwarf Axe: Cleave                                                     #
# --------------------------------------------------------------------------- #

class Cleave(Action):
    id, name, cost, target, aimed = "cleave", "Cleave", 2, "enemy", True
    desc = "2 AP: Strikes two adjacent foes in a single wide swing."

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        unarmed = getattr(actor, "unarmed", False)
        char = getattr(actor, "char", actor)
        has_unarmed_cleave = bool(getattr(char, "talent_bonus", lambda _: 0)("unarmed_cleave"))
        if unarmed:
            if not has_unarmed_cleave:
                return False, "requires axe"
        elif w is None or not w.has_trait("cleave"):
            return False, "requires axe"
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.attack_range:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        char = getattr(actor, "char", actor)
        if getattr(actor, "unarmed", False) and getattr(char, "talent_bonus", lambda _: 0)("unarmed_cleave"):
            return "Sweeping Claws (2 pts, strike 2 adjacent foes at +2)"
        return "Cleave (2 pts, strike 2 adjacent foes at +2)"

    @staticmethod
    def second(battle, actor, target):
        """The foe the sweep carries into: beside both, the weakest."""
        candidates = [
            u for u in battle.units
            if u.alive and u.team != actor.team and u is not target and not u.hidden_from(actor.team)
            and battle.units_distance(actor, u) <= 1
            and battle.units_distance(target, u) <= 1
            and battle.los_between(actor, u)
        ]
        return min(candidates, key=lambda c: c.hp) if candidates else None

    def favoured(self, battle, actor, target):
        return self.second(battle, actor, target) is not None

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        sec = self.second(battle, actor, target)

        # 1. Primary strike
        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), battle=battle)
        if sec is not None:
            mods.append((2, "circumstance", "Cleave"))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix_name = "Sweeping Claws" if getattr(actor, "unarmed", False) else "Cleave"
        prefix = f"{actor.name} {prefix_name} -> {target.name}"
        _resolve_hit(battle, actor, target, nat, bonus, detail, prefix)

        # 2. Secondary strike on adjacent foe
        if sec is not None and sec.alive:
            mods2 = actor.attack_mods(sec, _pack_flank(battle, actor, sec), battle=battle)
            mods2.append((2, "circumstance", "Cleave"))
            bonus2, applied2 = resolve_bonus(mods2)
            detail2 = " ".join(f"{v:+}({r})" for v, r in applied2)
            nat2 = d20()
            prefix2 = f"  {prefix_name} sweeps into -> {sec.name}"
            _resolve_hit(battle, actor, sec, nat2, bonus2, detail2, prefix2)


# --------------------------------------------------------------------------- #
# Quarterstaff: Repel Strike                                                  #
# --------------------------------------------------------------------------- #

class RepelStrike(Action):
    id, name, cost, target, aimed = "repel_strike", "Repel Strike", 2, "enemy", True
    desc = "2 AP: Attacks and shoves target back with a +2 bonus to the push check."

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if getattr(actor, "unarmed", False) or w is None or not w.has_trait("repel_strike"):
            return False, "requires quarterstaff"
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.attack_range:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Repel Strike (2 pts, attack & push +2; double +1d4 vs a foe against a wall)"

    @staticmethod
    def behind(actor, target):
        dx, dy = _sign(target.pos[0] - actor.pos[0]), _sign(target.pos[1] - actor.pos[1])
        return (dx, dy), (target.pos[0] + dx, target.pos[1] + dy)

    def favoured(self, battle, actor, target):
        """Its back to a wall or a body: the shove has nowhere to go and slams it instead."""
        step, dest = self.behind(actor, target)
        if step == (0, 0):
            return False
        return (battle.board.diagonal_corner_blocked(target.pos, dest)
                or not _cell_free(battle, actor, dest, target.footprint))

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        pinned = self.favoured(battle, actor, target)
        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), battle=battle)
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Repel Strike -> {target.name}"
        slam = roll(1, 4) + _second_blow(actor, True) if pinned else 0
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix, bonus_damage=slam)
        _log_twice(battle, res, pinned, f"{target.name} is slammed against what stands behind")

        if res in ("hit", "crit") and not pinned:
            dc = PUSH_DC_BASE + target.mod_constitution
            shove_nat = d20()
            shove_total = shove_nat + actor.mod_strength + 2
            desc = (f"  Repel check: d20({shove_nat}) + {actor.mod_strength}(STR) + 2(Staff) "
                    f"= {shove_total} vs DC {dc}")
            if shove_nat != 20 and (shove_nat == 1 or shove_total < dc):
                battle.log(desc + " -> holds ground.")
                return

            ax, ay = actor.pos
            tx, ty = target.pos
            dx, dy = _sign(tx - ax), _sign(ty - ay)
            if dx == 0 and dy == 0:
                return
            dest = (tx + dx, ty + dy)
            if (not battle.board.diagonal_corner_blocked(target.pos, dest)
                    and _cell_free(battle, actor, dest, target.footprint)):
                battle.log(desc + f" -> pushed back to {dest}!")
                target.pos = dest
            else:
                battle.log(desc + " -> blocked by terrain/body.")


# --------------------------------------------------------------------------- #
# Club / Hammer / Light Hammer: Maiming Strike                                #
# --------------------------------------------------------------------------- #

class MaimingStrike(Action):
    id, name, cost, target, aimed = "maiming_strike", "Maiming Strike", 2, "enemy", True
    desc = "2 AP: Attacks and halves the target's movement speed until next round."

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if getattr(actor, "unarmed", False) or w is None or not w.has_trait("maiming_strike"):
            return False, "requires bludgeon"
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.attack_range:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Maiming Strike (2 pts, halves speed; +2 & double vs a foe that cannot dodge)"

    def favoured(self, battle, actor, target):
        """Caught, asleep, surprised or shaken: it cannot get its legs out of the way."""
        return any(target.has_condition(c) for c in UNGUARDED)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        unguarded = self.favoured(battle, actor, target)
        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), battle=battle)
        if unguarded:
            mods.append((2, "circumstance", "Maiming Strike"))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Maiming Strike -> {target.name}"
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix,
                           bonus_damage=_second_blow(actor, unguarded))
        _log_twice(battle, res, unguarded, f"{target.name} cannot get out of the way")

        if res in ("hit", "crit"):
            target.add_condition(Maimed())
            battle.log(f"  {target.name} is maimed (movement halved until next round).")


# --------------------------------------------------------------------------- #
# Pick / Light Pick: Armor Pierce                                             #
# --------------------------------------------------------------------------- #

class ArmorPierce(Action):
    id, name, cost, target, aimed = "armor_pierce", "Armor Pierce", 2, "enemy", True
    desc = "2 AP: Attack ignores worn armor AC bonus."

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if getattr(actor, "unarmed", False) or w is None or not w.has_trait("armor_pierce"):
            return False, "requires pick"
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.attack_range:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Armor Pierce (2 pts, ignores armor AC; double vs an armoured foe)"

    def favoured(self, battle, actor, target):
        return target.armor is not None and target.armor.ac > 0

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        armoured = self.favoured(battle, actor, target)
        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), battle=battle)
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Armor Pierce -> {target.name}"
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix, armor_pierce=True,
                           bonus_damage=_second_blow(actor, armoured))
        _log_twice(battle, res, armoured, "The point punches through the armour")


# --------------------------------------------------------------------------- #
# Shortbow: Power Shot                                                        #
# --------------------------------------------------------------------------- #

class PowerShot(Action):
    id, name, cost, target, aimed = "power_shot", "Power Shot", 2, "enemy", True
    desc = "2 AP: Adds positive Strength modifier to arrow damage."

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if getattr(actor, "unarmed", False) or w is None or not w.has_trait("power_shot"):
            return False, "requires shortbow"
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not actor.ranged or not _hostile_target(actor, target):
            return False
        w = actor.weapon
        reach = (w.range if w else 14) + actor.char.talent_bonus("ranged_reach")
        if battle.units_distance(actor, target) > reach or battle.units_distance(actor, target) <= 1:
            return False
        return battle.can_see_unit(actor, target) and battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Power Shot (2 pts, +STR to damage; double at half range or farther)"

    def highlight_targets(self, battle, actor):
        return [u for u in battle.units if u.alive and u.team != actor.team and self.can(battle, actor, u)]

    def favoured(self, battle, actor, target):
        """A long shot: half the bow's range or farther, where a full draw tells."""
        w = actor.weapon
        return battle.units_distance(actor, target) * 2 >= (w.range if w else 14)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        far = self.favoured(battle, actor, target)
        str_bonus = max(1 if far else 0, actor.mod_strength)
        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), battle=battle)
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Power Shot -> {target.name}"
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix,
                           bonus_damage=str_bonus + _second_blow(actor, far))

        actor.ammo = max(0, actor.ammo - 1)
        if res in ("hit", "crit") and str_bonus > 0:
            battle.log(f"  Drawn with great power (+{str_bonus} STR damage)!")
        _log_twice(battle, res, far, "A full draw at long range")


# --------------------------------------------------------------------------- #
# Light Crossbow: Extreme Shot                                                #
# --------------------------------------------------------------------------- #

class ExtremeShot(Action):
    id, name, cost, target, aimed = "extreme_shot", "Extreme Shot", 2, "enemy", True
    desc = "2 AP: Doubles attack range to 36 squares."

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if getattr(actor, "unarmed", False) or w is None or not w.has_trait("extreme_shot"):
            return False, "requires crossbow"
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not actor.ranged or not _hostile_target(actor, target):
            return False
        reach = 36 + actor.char.talent_bonus("ranged_reach")
        if battle.units_distance(actor, target) > reach or battle.units_distance(actor, target) <= 1:
            return False
        return battle.can_see_unit(actor, target) and battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Extreme Shot (2 pts, 36 sq range)"

    def highlight_targets(self, battle, actor):
        return [u for u in battle.units if u.alive and u.team != actor.team and self.can(battle, actor, u)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), battle=battle)
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Extreme Shot -> {target.name}"
        _resolve_hit(battle, actor, target, nat, bonus, detail, prefix)

        actor.crossbow_loaded = False
        actor.ammo = max(0, actor.ammo - 1)


# --------------------------------------------------------------------------- #
# Hatchet: Hook Shield                                                        #
# --------------------------------------------------------------------------- #

class HookShield(Action):
    id, name, cost, target, aimed = "hook_shield", "Hook Shield", 2, "enemy", True
    desc = "2 AP: Attacks and nullifies target's shield AC bonus until next round."

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if getattr(actor, "unarmed", False) or w is None or not w.has_trait("hook_shield"):
            return False, "requires hatchet"
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.attack_range:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Hook Shield (2 pts, strip shield AC; double vs a shield)"

    def favoured(self, battle, actor, target):
        hand = target.equipped_offhand
        return bool(hand and items.is_shield(hand)) and not target.has_condition("shield_hooked")

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        shielded = self.favoured(battle, actor, target)
        if shielded:
            target.add_condition(ShieldHooked())
            battle.log(f"  {actor.name} hooks {target.name}'s shield and wrenches it aside (loses shield AC)!")
        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), battle=battle)
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Hook Shield -> {target.name}"
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix,
                           bonus_damage=_second_blow(actor, shielded))
        _log_twice(battle, res, shielded, "The hook bites behind the shield")


# --------------------------------------------------------------------------- #
# Shortspear: Javelin Charge                                                  #
# --------------------------------------------------------------------------- #

class JavelinCharge(Action):
    id, name, cost, target, aimed = "javelin_charge", "Javelin Charge", 1, "enemy", True
    desc = "1 AP: Throws the spear after moving this turn for +1d4 bonus damage."

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if getattr(actor, "unarmed", False) or w is None or not w.has_trait("javelin_charge"):
            return False, "requires shortspear"
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if actor.moved <= 0:
            return False
        w = actor.weapon
        reach = (w.thrown if w else 12) + actor.char.talent_bonus("ranged_reach")
        if battle.units_distance(actor, target) > reach or battle.units_distance(actor, target) <= 1:
            return False
        return battle.can_see_unit(actor, target) and battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Javelin Charge (1 pt, throw after a move, +1d4 dmg)"

    def highlight_targets(self, battle, actor):
        return [u for u in battle.units if u.alive and u.team != actor.team and self.can(battle, actor, u)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        weapon_name = actor.weapon_name

        bonus_dmg = roll(1, 4)
        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), thrown=True, battle=battle)
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Javelin Charge -> {target.name}"
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix, thrown=True, bonus_damage=bonus_dmg)
        if res in ("hit", "crit"):
            battle.log(f"  The running throw impacts with brutal force (+{bonus_dmg} damage)!")

        actor.disarm()
        landing = _drop_cell(battle, target)
        battle.ground.append(GroundObject.weapon(landing, weapon_name))
        battle.log(f"  {weapon_name} lands at {landing}; {actor.name} is disarmed.")


# --------------------------------------------------------------------------- #
# Broadsword: Parry & Strike                                                  #
# --------------------------------------------------------------------------- #

class ParryStrike(Action):
    id, name, cost, target, aimed = "parry_strike", "Parry & Strike", 2, "enemy", True
    desc = "2 AP: Attacks and assumes a Defending guard (+1 AC until next turn)."

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if getattr(actor, "unarmed", False) or w is None or not w.has_trait("parry_strike"):
            return False, "requires broadsword"
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.attack_range:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Parry & Strike (2 pts, attack & Defend; double with 2+ foes in reach)"

    def favoured(self, battle, actor, target):
        """Pressed by two or more: every parry opens a riposte."""
        return sum(1 for u in battle.units
                   if u.alive and u.team != actor.team and not u.hidden_from(actor.team)
                   and battle.units_distance(actor, u) <= max(1, u.attack_range if not u.ranged else 1)) >= 2

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        pressed = self.favoured(battle, actor, target)
        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), battle=battle)
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Parry & Strike -> {target.name}"
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix,
                           bonus_damage=_second_blow(actor, pressed))
        _log_twice(battle, res, pressed, "Parry and riposte")

        actor.add_condition(Defending())
        battle.log(f"  {actor.name} falls back into a parrying stance (+1 AC until next turn)!")
