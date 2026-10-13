"""Weapon 2-AP actions: unique tactical options granted by equipped weapon traits.

Every weapon kind in the catalog grants its own 2-AP action:
- Dagger: Sneak Attack (bonus damage against flanked foes)
- Rapier: Precise Thrust (bonus to hit against flanked foes)
- Axe / Dwarf Axe: Cleave (strikes two adjacent foes)
- Quarterstaff: Repel Strike (attacks and shoves foe with +2 bonus)
- Club / Hammer / Light Hammer: Maiming Strike (halves foe speed)
- Pick / Light Pick: Armor Pierce (ignores worn armor AC)
- Shortbow: Power Shot (adds positive STR modifier to arrow damage)
- Light Crossbow: Extreme Shot (doubles range to 36 squares)
- Hatchet: Hook Shield (nullifies foe shield AC until next round)
- Shortspear: Javelin Charge (bonus damage when thrown after moving)
- Broadsword: Parry & Strike (attacks and gains Defending condition)
"""

from .. import intel, items
from ..board import cells, cells_in_radius, grid_distance
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


def _is_flanked(battle, actor, target):
    return _flanked(battle, actor, target) or bool(_pack_flank(battle, actor, target))


# --------------------------------------------------------------------------- #
# Dagger: Sneak Attack                                                        #
# --------------------------------------------------------------------------- #

class SneakAttack(Action):
    id, name, cost, target, aimed = "sneak_attack", "Sneak Attack", 2, "enemy", True
    desc = "2 AP: If the target is flanked, deals +1d4 bonus damage."

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if getattr(actor, "unarmed", False) or w is None or not w.has_trait("sneak_attack"):
            return False, "requires dagger"
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > 1:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Sneak Attack (2 pts, +1d4 vs flanked)"

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        flanked = _is_flanked(battle, actor, target)
        bonus_dmg = roll(1, 4) if flanked else 0

        mods = actor.attack_mods(target, _pack_flank(battle, actor, target))
        if _flanked(battle, actor, target):
            mods.append((2, "circumstance", "Flank"))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Sneak Attack -> {target.name}"
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix, bonus_damage=bonus_dmg)
        if res in ("hit", "crit") and flanked:
            battle.log(f"  Sneak Attack strikes a vulnerable spot (+{bonus_dmg} damage)!")


# --------------------------------------------------------------------------- #
# Rapier: Precise Thrust                                                      #
# --------------------------------------------------------------------------- #

class PreciseThrust(Action):
    id, name, cost, target, aimed = "precise_thrust", "Precise Thrust", 2, "enemy", True
    desc = "2 AP: Gains +2 to hit against flanked foes."

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if getattr(actor, "unarmed", False) or w is None or not w.has_trait("precise_thrust"):
            return False, "requires rapier"
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > 1:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Precise Thrust (2 pts, +2 to hit vs flanked)"

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        mods = actor.attack_mods(target, _pack_flank(battle, actor, target))
        if _flanked(battle, actor, target):
            mods.append((2, "circumstance", "Flank"))
        if _is_flanked(battle, actor, target):
            mods.append((2, "circumstance", "Precise Thrust"))

        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Precise Thrust -> {target.name}"
        _resolve_hit(battle, actor, target, nat, bonus, detail, prefix)


# --------------------------------------------------------------------------- #
# Axe / Dwarf Axe: Cleave                                                     #
# --------------------------------------------------------------------------- #

class Cleave(Action):
    id, name, cost, target, aimed = "cleave", "Cleave", 2, "enemy", True
    desc = "2 AP: Strikes two adjacent foes in a single wide swing."

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if getattr(actor, "unarmed", False) or w is None or not w.has_trait("cleave"):
            return False, "requires axe"
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > 1:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Cleave (2 pts, strike 2 adjacent foes)"

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        # 1. Primary strike
        mods = actor.attack_mods(target, _pack_flank(battle, actor, target))
        if _flanked(battle, actor, target):
            mods.append((2, "circumstance", "Flank"))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Cleave -> {target.name}"
        _resolve_hit(battle, actor, target, nat, bonus, detail, prefix)

        # 2. Secondary strike on adjacent foe
        candidates = [
            u for u in battle.units
            if u.alive and u.team != actor.team and u is not target
            and battle.units_distance(actor, u) <= 1
            and battle.units_distance(target, u) <= 1
            and battle.los_between(actor, u)
        ]
        if candidates:
            sec = min(candidates, key=lambda c: c.hp)
            mods2 = actor.attack_mods(sec, _pack_flank(battle, actor, sec))
            if _flanked(battle, actor, sec):
                mods2.append((2, "circumstance", "Flank"))
            bonus2, applied2 = resolve_bonus(mods2)
            detail2 = " ".join(f"{v:+}({r})" for v, r in applied2)
            nat2 = d20()
            prefix2 = f"  Cleave sweeps into -> {sec.name}"
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
        if battle.units_distance(actor, target) > 1:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Repel Strike (2 pts, attack & push +2)"

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        mods = actor.attack_mods(target, _pack_flank(battle, actor, target))
        if _flanked(battle, actor, target):
            mods.append((2, "circumstance", "Flank"))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Repel Strike -> {target.name}"
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix)

        if res in ("hit", "crit"):
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
        if battle.units_distance(actor, target) > 1:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Maiming Strike (2 pts, halves speed)"

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        mods = actor.attack_mods(target, _pack_flank(battle, actor, target))
        if _flanked(battle, actor, target):
            mods.append((2, "circumstance", "Flank"))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Maiming Strike -> {target.name}"
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix)

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
        if battle.units_distance(actor, target) > 1:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Armor Pierce (2 pts, ignores armor AC)"

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        mods = actor.attack_mods(target, _pack_flank(battle, actor, target))
        if _flanked(battle, actor, target):
            mods.append((2, "circumstance", "Flank"))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Armor Pierce -> {target.name}"
        _resolve_hit(battle, actor, target, nat, bonus, detail, prefix, armor_pierce=True)


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
        return "Power Shot (2 pts, +STR to damage)"

    def highlight_targets(self, battle, actor):
        w = actor.weapon
        reach = (w.range if w else 14) + actor.char.talent_bonus("ranged_reach")
        return [u for u in battle.units if u.alive and u.team != actor.team and self.can(battle, actor, u)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        str_bonus = max(0, actor.mod_strength)
        mods = actor.attack_mods(target, _pack_flank(battle, actor, target))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Power Shot -> {target.name}"
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix, bonus_damage=str_bonus)

        actor.ammo = max(0, actor.ammo - 1)
        if res in ("hit", "crit") and str_bonus > 0:
            battle.log(f"  Drawn with great power (+{str_bonus} STR damage)!")


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
        reach = 36 + actor.char.talent_bonus("ranged_reach")
        return [u for u in battle.units if u.alive and u.team != actor.team and self.can(battle, actor, u)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        mods = actor.attack_mods(target, _pack_flank(battle, actor, target))
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
        if battle.units_distance(actor, target) > 1:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Hook Shield (2 pts, strip shield AC)"

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        mods = actor.attack_mods(target, _pack_flank(battle, actor, target))
        if _flanked(battle, actor, target):
            mods.append((2, "circumstance", "Flank"))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Hook Shield -> {target.name}"
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix)

        if res in ("hit", "crit"):
            target.add_condition(ShieldHooked())
            battle.log(f"  {target.name}'s shield is hooked and wrenched aside (loses shield AC)!")


# --------------------------------------------------------------------------- #
# Shortspear: Javelin Charge                                                  #
# --------------------------------------------------------------------------- #

class JavelinCharge(Action):
    id, name, cost, target, aimed = "javelin_charge", "Javelin Charge", 2, "enemy", True
    desc = "2 AP: Throws spear after moving this turn for +1d4 bonus damage."

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
        return "Javelin Charge (2 pts, throw after move +1d4 dmg)"

    def highlight_targets(self, battle, actor):
        w = actor.weapon
        reach = (w.thrown if w else 12) + actor.char.talent_bonus("ranged_reach")
        return [u for u in battle.units if u.alive and u.team != actor.team and self.can(battle, actor, u)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        weapon_name = actor.weapon_name

        bonus_dmg = roll(1, 4)
        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), thrown=True)
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
        if battle.units_distance(actor, target) > 1:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Parry & Strike (2 pts, attack & Defend)"

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        mods = actor.attack_mods(target, _pack_flank(battle, actor, target))
        if _flanked(battle, actor, target):
            mods.append((2, "circumstance", "Flank"))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Parry & Strike -> {target.name}"
        _resolve_hit(battle, actor, target, nat, bonus, detail, prefix)

        actor.add_condition(Defending())
        battle.log(f"  {actor.name} falls back into a parrying stance (+1 AC until next turn)!")
