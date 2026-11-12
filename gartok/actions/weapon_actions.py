"""Weapon actions: unique tactical options granted by equipped weapon traits.

A 2-AP action is one strike for the price of two plain attacks, so out of its favoured case it is
the worse buy; in that case (`favoured`) the strike is Brutal 1 (gartok/keywords.py) plus the action's own
edge, and beats the two attacks for any weapon or modifier:
- Dagger: Sneak Attack (an off-guard foe; +1d4)
- Rapier: Precise Thrust (an off-guard foe; +2 to hit)
- Axe / Dwarf Axe: Cleave (a second foe beside both: two swings, each +2 to hit)
- Quarterstaff: Repel Strike (shoves the foe; with its back to a wall or a body it is slammed)
- Club / Hammer / Light Hammer: Maiming Strike (halves foe speed; a foe that cannot dodge)
- Pick / Light Pick: Armor Pierce (ignores worn armor AC; an armoured foe)
- Shortbow / Longbow: Power Shot (+STR; a foe at half the bow's range or farther)
- Crossbow: Extreme Shot (doubles range to 36 squares: the only shot past the normal one)
- Hatchet: Hook Shield (nullifies foe shield AC until next round; a foe with a shield)
- Javelin: Javelin Charge (1 AP, thrown after moving this turn, +1d4)
- Broadsword / Sword: Parry & Strike (gains Defending; two or more foes in reach)
- Glaive: Long Thrust (one square past its reach, +1 to hit: the only blow that lands there)
- Bare hands (`Unarmed`): Wrest (seize the weapon of an armed foe and strike with it)
- Hooves: Trample (strike, then shove, then Takedown, each step only while it can still be tried)
- Bite: Clamp (strike; a hit grabs with no roll; a foe already Grappled is bitten Brutal 1)
"""

from .. import i18n, items
from ..conditions import Defending, Maimed, ShieldHooked
from ..data import d20, resolve_bonus, roll
from ..i18n import Msg
from .base import (
    Action,
    _cell_free,
    _hostile_target,
    _land_thrown,
    _pack_flank,
    _resolve_hit,
    _sign,
    item_ref,
    off_guard,
)
from .combat import PUSH_DC_BASE, Grab, Push, Takedown, _strike

UNGUARDED = ("entangled", "sleeping", "surprised", "demoralized")
BRUTAL = 1      # every Brutal of a favoured strike; the keyword's value, see keywords.py
EDGE_TO_HIT = 2     # the circumstance bonus of Precise Thrust, Cleave and Maiming Strike
REPEL_CELLS = 1    # how far a Repel Strike that is not pinned shoves the foe
EDGE_DIE = (1, 4)   # the extra damage of Sneak Attack and of a pinned Repel Strike


def _strikable_off_guard(battle, actor, target):
    """An off-guard foe the actor can strike: within its weapon's reach, in sight and seen."""
    return (off_guard(battle, actor, target)
            and battle.units_distance(actor, target) <= actor.attack_range
            and battle.los_between(actor, target) and battle.can_see_unit(actor, target))


# --------------------------------------------------------------------------- #
# Dagger: Sneak Attack                                                        #
# --------------------------------------------------------------------------- #

class SneakAttack(Action):
    id, cost, target, aimed = "sneak_attack", 2, "enemy", True

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if not w.has_trait("sneak_attack"):
            return False, i18n.t("action.sneak_attack.reason")
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        return _strikable_off_guard(battle, actor, target)

    def label(self, battle, actor):
        return i18n.t("action.sneak_attack.label")

    def favoured(self, battle, actor, target):
        return off_guard(battle, actor, target)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        bonus_dmg = roll(*EDGE_DIE)

        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), battle=battle)
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = Msg("log.sneak_attack.head", actor=actor.name, target=target.name)
        _resolve_hit(battle, actor, target, nat, bonus, detail, prefix, bonus_damage=bonus_dmg,
                     brutal=BRUTAL, brutal_why=Msg("log.sneak_attack.brutal"))


# --------------------------------------------------------------------------- #
# Rapier: Precise Thrust                                                      #
# --------------------------------------------------------------------------- #

class PreciseThrust(Action):
    id, cost, target, aimed = "precise_thrust", 2, "enemy", True

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if not w.has_trait("precise_thrust"):
            return False, i18n.t("action.precise_thrust.reason")
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        return _strikable_off_guard(battle, actor, target)

    def label(self, battle, actor):
        return i18n.t("action.precise_thrust.label")

    def favoured(self, battle, actor, target):
        return off_guard(battle, actor, target)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), battle=battle)
        mods.append((EDGE_TO_HIT, "circumstance", i18n.t("log.mod.precise_thrust")))

        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = Msg("log.precise_thrust.head", actor=actor.name, target=target.name)
        _resolve_hit(battle, actor, target, nat, bonus, detail, prefix,
                     brutal=BRUTAL, brutal_why=Msg("log.precise_thrust.brutal"))


# --------------------------------------------------------------------------- #
# Axe / Dwarf Axe: Cleave                                                     #
# --------------------------------------------------------------------------- #

class Cleave(Action):
    id, cost, target, aimed = "cleave", 2, "enemy", True

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.weapon.has_trait("cleave"):
            return False, i18n.t("action.cleave.reason")
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.attack_range:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return i18n.t("action.cleave.label" if actor.armed else "action.cleave.label_claws")

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
            mods.append((EDGE_TO_HIT, "circumstance", i18n.t("log.mod.cleave")))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        head_key = "log.cleave.head" if actor.armed else "log.cleave.head_claws"
        prefix = Msg(head_key, actor=actor.name, target=target.name)
        _resolve_hit(battle, actor, target, nat, bonus, detail, prefix)

        # 2. Secondary strike on adjacent foe
        if sec is not None and sec.alive:
            mods2 = actor.attack_mods(sec, _pack_flank(battle, actor, sec), battle=battle)
            mods2.append((EDGE_TO_HIT, "circumstance", i18n.t("log.mod.cleave")))
            bonus2, applied2 = resolve_bonus(mods2)
            detail2 = " ".join(f"{v:+}({r})" for v, r in applied2)
            nat2 = d20()
            prefix2 = Msg(head_key + "_sweeps", target=sec.name)
            _resolve_hit(battle, actor, sec, nat2, bonus2, detail2, prefix2)


# --------------------------------------------------------------------------- #
# Quarterstaff: Repel Strike                                                  #
# --------------------------------------------------------------------------- #

class RepelStrike(Action):
    id, cost, target, aimed = "repel_strike", 2, "enemy", True

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if not w.has_trait("repel_strike"):
            return False, i18n.t("action.repel_strike.reason")
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.attack_range:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return i18n.t("action.repel_strike.label")

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
        prefix = Msg("log.repel_strike.head", actor=actor.name, target=target.name)
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix,
                           bonus_damage=roll(*EDGE_DIE) if pinned else 0, brutal=BRUTAL * pinned,
                           brutal_why=Msg("log.repel_strike.brutal", target=target.name))

        if res in ("hit", "crit") and not pinned:
            dc = PUSH_DC_BASE + target.mod_constitution
            shove_nat = d20()
            shove_total = shove_nat + actor.mod_strength + 2
            check = {"nat": shove_nat, "str": actor.mod_strength, "total": shove_total, "dc": dc}
            if shove_nat != 20 and (shove_nat == 1 or shove_total < dc):
                battle.log("log.repel_strike.holds", **check)
                return

            ax, ay = actor.pos
            tx, ty = target.pos
            dx, dy = _sign(tx - ax), _sign(ty - ay)
            if dx == 0 and dy == 0:
                return
            dest = (tx + dx * REPEL_CELLS, ty + dy * REPEL_CELLS)
            if (not battle.board.diagonal_corner_blocked(target.pos, dest)
                    and _cell_free(battle, actor, dest, target.footprint)):
                battle.log("log.repel_strike.pushed", cell=str(dest), **check)
                target.pos = dest
            else:
                battle.log("log.repel_strike.blocked", **check)


# --------------------------------------------------------------------------- #
# Club / Hammer / Light Hammer: Maiming Strike                                #
# --------------------------------------------------------------------------- #

class MaimingStrike(Action):
    id, cost, target, aimed = "maiming_strike", 2, "enemy", True

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if not w.has_trait("maiming_strike"):
            return False, i18n.t("action.maiming_strike.reason")
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.attack_range:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return i18n.t("action.maiming_strike.label")

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
            mods.append((EDGE_TO_HIT, "circumstance", i18n.t("log.mod.maiming_strike")))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = Msg("log.maiming_strike.head", actor=actor.name, target=target.name)
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix, brutal=BRUTAL * unguarded,
                           brutal_why=Msg("log.maiming_strike.brutal", target=target.name))

        if res in ("hit", "crit"):
            target.add_condition(Maimed())
            battle.log("log.maimed", target=target.name)


# --------------------------------------------------------------------------- #
# Pick / Light Pick: Armor Pierce                                             #
# --------------------------------------------------------------------------- #

class ArmorPierce(Action):
    id, cost, target, aimed = "armor_pierce", 2, "enemy", True

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if not w.has_trait("armor_pierce"):
            return False, i18n.t("action.armor_pierce.reason")
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.attack_range:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return i18n.t("action.armor_pierce.label")

    def favoured(self, battle, actor, target):
        return target.pierceable_ac > 0

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
        prefix = Msg("log.armor_pierce.head", actor=actor.name, target=target.name)
        _resolve_hit(battle, actor, target, nat, bonus, detail, prefix, armor_pierce=True,
                     brutal=BRUTAL * armoured, brutal_why=Msg("log.armor_pierce.brutal"))


# --------------------------------------------------------------------------- #
# Shortbow: Power Shot                                                        #
# --------------------------------------------------------------------------- #

class PowerShot(Action):
    id, cost, target, aimed = "power_shot", 2, "enemy", True
    missile = True

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if not w.has_trait("power_shot"):
            return False, i18n.t("action.power_shot.reason")
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
        return i18n.t("action.power_shot.label")

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
        prefix = Msg("log.power_shot.head", actor=actor.name, target=target.name)
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix, bonus_damage=str_bonus,
                           brutal=BRUTAL * far, brutal_why=Msg("log.power_shot.brutal"))

        actor.ammo = max(0, actor.ammo - 1)
        if res in ("hit", "crit") and str_bonus > 0:
            battle.log("log.power_shot.drawn", n=str_bonus)


# --------------------------------------------------------------------------- #
# Crossbow: Extreme Shot                                                #
# --------------------------------------------------------------------------- #

class ExtremeShot(Action):
    id, cost, target, aimed = "extreme_shot", 2, "enemy", True
    missile = True

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if not w.has_trait("extreme_shot"):
            return False, i18n.t("action.extreme_shot.reason")
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not actor.ranged or not _hostile_target(actor, target):
            return False
        reach = 36 + actor.char.talent_bonus("ranged_reach")
        if battle.units_distance(actor, target) > reach or battle.units_distance(actor, target) <= 1:
            return False
        return battle.can_see_unit(actor, target) and battle.los_between(actor, target)

    def label(self, battle, actor):
        return i18n.t("action.extreme_shot.label")

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
        prefix = Msg("log.extreme_shot.head", actor=actor.name, target=target.name)
        _resolve_hit(battle, actor, target, nat, bonus, detail, prefix)

        actor.crossbow_loaded = False
        actor.ammo = max(0, actor.ammo - 1)


# --------------------------------------------------------------------------- #
# Hatchet: Hook Shield                                                        #
# --------------------------------------------------------------------------- #

class HookShield(Action):
    id, cost, target, aimed = "hook_shield", 2, "enemy", True

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if not w.has_trait("hook_shield"):
            return False, i18n.t("action.hook_shield.reason")
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.attack_range:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return i18n.t("action.hook_shield.label")

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
            battle.log("log.hook_shield.hooked", actor=actor.name, target=target.name)
        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), battle=battle)
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = Msg("log.hook_shield.head", actor=actor.name, target=target.name)
        _resolve_hit(battle, actor, target, nat, bonus, detail, prefix, brutal=BRUTAL * shielded,
                     brutal_why=Msg("log.hook_shield.brutal"))


# --------------------------------------------------------------------------- #
# Javelin: Javelin Charge                                                     #
# --------------------------------------------------------------------------- #

class JavelinCharge(Action):
    id, cost, target, aimed = "javelin_charge", 1, "enemy", True
    missile = True

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if not w.has_trait("javelin_charge"):
            return False, i18n.t("action.javelin_charge.reason")
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
        return i18n.t("action.javelin_charge.label")

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
        prefix = Msg("log.javelin_charge.head", actor=actor.name, target=target.name)
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix, thrown=True, bonus_damage=bonus_dmg)
        if res in ("hit", "crit"):
            battle.log("log.javelin_charge.impact", n=bonus_dmg)

        _land_thrown(battle, actor, target, weapon_name)


# --------------------------------------------------------------------------- #
# Broadsword: Parry & Strike                                                  #
# --------------------------------------------------------------------------- #

class ParryStrike(Action):
    id, cost, target, aimed = "parry_strike", 2, "enemy", True

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if not w.has_trait("parry_strike"):
            return False, i18n.t("action.parry_strike.reason")
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.attack_range:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return i18n.t("action.parry_strike.label")

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
        prefix = Msg("log.parry_strike.head", actor=actor.name, target=target.name)
        _resolve_hit(battle, actor, target, nat, bonus, detail, prefix, brutal=BRUTAL * pressed,
                     brutal_why=Msg("log.parry_strike.brutal"))

        actor.add_condition(Defending())
        battle.log("log.parry_strike.stance", actor=actor.name)


# --------------------------------------------------------------------------- #
# Glaive: Long Thrust                                                         #
# --------------------------------------------------------------------------- #

class LongThrust(Action):
    id, cost, target, aimed = "long_thrust", 2, "enemy", True
    EXTRA_REACH = 1
    TO_HIT = 1

    @classmethod
    def applicable(cls, battle, actor):
        w = actor.weapon
        if not w.has_trait("long_thrust"):
            return False, i18n.t("action.long_thrust.reason")
        return True, ""

    @classmethod
    def reach(cls, actor):
        return actor.attack_range + cls.EXTRA_REACH

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or actor.ranged or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > self.reach(actor):
            return False
        return battle.los_between(actor, target) and battle.can_see_unit(actor, target)

    def label(self, battle, actor):
        return i18n.t("action.long_thrust.label", reach=self.reach(actor), n=self.TO_HIT)

    def highlight_targets(self, battle, actor):
        return [u for u in battle.units if u.alive and u.team != actor.team and self.can(battle, actor, u)]

    def favoured(self, battle, actor, target):
        """A foe past the plain reach: no other blow lands there."""
        return battle.units_distance(actor, target) > actor.attack_range

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), battle=battle)
        mods.append((self.TO_HIT, "circumstance", i18n.t("log.mod.long_thrust")))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        prefix = Msg("log.long_thrust.head", actor=actor.name, target=target.name)
        _resolve_hit(battle, actor, target, d20(), bonus, detail, prefix)


# --------------------------------------------------------------------------- #
# Bare hands: Wrest                                                           #
# --------------------------------------------------------------------------- #

class Wrest(Action):
    id, cost, target, aimed = "wrest", 2, "enemy", True
    BASE_DC = 15

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.weapon.has_trait("wrest"):
            return False, i18n.t("action.wrest.reason")
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if not target.armed or not actor.char.can_wield(target.weapon_name):
            return False
        if actor.free_hands < target.weapon["hands"]:
            return False
        if battle.units_distance(actor, target) > actor.attack_range:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return i18n.t("action.wrest.label")

    @classmethod
    def dc(cls, target):
        return cls.BASE_DC + target.mod_strength

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False

        name = target.weapon_name
        dc = self.dc(target)
        nat = d20()
        total = nat + actor.mod_dexterity
        roll_line = {"actor": actor.name, "target": target.name, "nat": nat, "dex": actor.mod_dexterity,
                     "total": total, "dc": dc, "weapon": item_ref(name)}
        if nat != 20 and (nat == 1 or total < dc):
            battle.log("log.wrest.keeps", **roll_line)
            return

        battle.log("log.wrest.tears", **roll_line)
        target.drop_weapon()
        actor.equip_weapon(name)
        _strike(battle, actor, target, prefix=Msg(
            "log.attack.head_via_indented", actor=actor.name, target=target.name, how=item_ref(name, lower=True)))


# --------------------------------------------------------------------------- #
# Hooves: Trample                                                             #
# --------------------------------------------------------------------------- #

class Trample(Action):
    id, cost, target, aimed = "trample", 2, "enemy", True

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.weapon.has_trait("trample"):
            return False, i18n.t("action.trample.reason")
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.attack_range:
            return False
        return battle.los_between(actor, target) and battle.can_see_unit(actor, target)

    def label(self, battle, actor):
        return i18n.t("action.trample.label")

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        _strike(battle, actor, target, prefix=Msg("log.trample.head", actor=actor.name, target=target.name))
        if target.alive and Push.in_reach(battle, actor, target):
            Push.shove(battle, actor, target)
        if target.alive and Takedown.in_reach(battle, actor, target):
            Takedown.knock_down(battle, actor, target)


# --------------------------------------------------------------------------- #
# Bite: Clamp                                                                 #
# --------------------------------------------------------------------------- #

class Clamp(Action):
    id, cost, target, aimed = "clamp", 2, "enemy", True

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.weapon.has_trait("clamp"):
            return False, i18n.t("action.clamp.reason")
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.attack_range:
            return False
        return battle.los_between(actor, target) and battle.can_see_unit(actor, target)

    def label(self, battle, actor):
        return i18n.t("action.clamp.label")

    def favoured(self, battle, actor, target):
        """A foe already held: the jaws find a body that cannot twist away."""
        return target.has_condition("grappled")

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        held = self.favoured(battle, actor, target)
        res = _strike(battle, actor, target, prefix=Msg("log.clamp.head", actor=actor.name, target=target.name),
                      brutal=BRUTAL * held, brutal_why=Msg("log.clamp.brutal", target=target.name))
        if res in ("hit", "crit") and target.alive and not held:
            Grab.hold(battle, actor, target)
            battle.log("log.clamp.holds", actor=actor.name, target=target.name)
