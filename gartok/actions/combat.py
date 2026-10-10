"""Attack-shaped actions: Attack, Reload, Defend, Throw, Demoralize, Flee, Push."""


from ..board import cells, cells_in_radius
from ..conditions import Defending, Demoralized
from ..data import DEMORALIZE_RANGE, d20, resolve_bonus
from ..ground import GroundObject
from .base import (
    Action,
    _attackable_target,
    _cell_free,
    _drop_cell,
    _flanked,
    _hostile_target,
    _pack_flank,
    _resolve_hit,
    _shared_language,
    _shovable_target,
    _sign,
)

PUSH_DC_BASE = 10          # Shove: Strength vs 10 + the target's Constitution modifier


# --------------------------------------------------------------------------- #
# Attack                                                                       #
# --------------------------------------------------------------------------- #

def _strike(battle, actor, target, *, weapon=None, prefix=None):
    """The shared attack resolution once the AP is paid: assemble the mods (flank,
    feint), roll, resolve the hit, fire the on-miss ability. `weapon` overrides the
    held one (the Tongue). Returns 'hit'|'miss'|'crit'."""
    mods = actor.attack_mods(target, _pack_flank(battle, actor, target), weapon=weapon)
    if _flanked(battle, actor, target):
        mods.append((2, "circumstance", "Flank"))

    ab = actor.ability
    if ab.feint and actor.spend_once("feint"):
        mods += ab.feint(actor, target)
        battle.log(f"{actor.name} uses {ab.name} to distract.")

    bonus, applied = resolve_bonus(mods)
    detail = " ".join(f"{v:+}({r})" for v, r in applied)
    nat = d20()
    result = _resolve_hit(battle, actor, target, nat, bonus, detail,
                          prefix or f"{actor.name} -> {target.name}", weapon=weapon)

    if result == "miss" and nat != 1 and ab.on_attack_miss \
            and actor.spend_once("on_attack_miss"):
        ab.on_attack_miss(battle, actor, target, bonus, target.ac_vs(actor), battle.log)
    elif result == "miss" and actor.can_use_luck(getattr(battle, "clock_day", 1)):
        actor.use_luck(getattr(battle, "clock_day", 1))
        nat2 = d20()
        total2 = nat2 + bonus
        hits = nat2 == 20 or total2 >= target.ac_vs(actor)
        battle.log(f"  Halfling Luck! {actor.name} rerolls attack: d20({nat2}) = {total2} -> "
                   + ("hit." if hits else "misses again."))
        if hits:
            target.take_damage(actor.damage_roll(crit=nat2 == 20, weapon=weapon), battle.log)
            result = "hit"
    return result


class Attack(Action):
    id, name, cost, target, aimed = "attack", "Attack", 1, "enemy", True
    desc = "Melee or Ranged attack based on your equipped weapon."

    def can(self, battle, actor, target=None):
        if actor.ap < self.cost or not _attackable_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.attack_range:
            return False
        # melee only crosses a one-level lip; a deeper drop is out of reach
        if not actor.ranged \
                and abs(battle.elevation(actor) - battle.elevation(target)) > 1:
            return False
        if not battle.los_between(actor, target):
            return False
        if not battle.can_see_unit(actor, target):
            return False
        return True

    def highlight_cells(self, battle, actor):
        rng = actor.attack_range
        return [p for c in cells(actor.pos, actor.footprint)
                for p in cells_in_radius(c, rng)]

    def highlight_targets(self, battle, actor):
        return [u for u in battle.units
                if not u.dead and u.team != actor.team and self.can(battle, actor, u)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        if actor.ranged:
            if actor.weapon.get("reload"):
                actor.crossbow_loaded = False               # spent -- needs a Reload before the next shot
                battle.log(f"{actor.name} shoots ({actor.ammo} bolt(s) in the quiver).")
            else:
                actor.ammo -= 1                             # a bow draws from the quiver on every shot
                battle.log(f"{actor.name} shoots ({actor.ammo} arrow(s) left in the quiver).")
        _strike(battle, actor, target)


class AttackTongue(Action):
    """The Grippli's Tongue: a second weapon, an extra limb. A 1-handed weapon in
    the Tongue slot, swung at +1 square of reach. A separate action so a Grippli
    can choose it or the hand weapon each turn (a reach poke vs. a 2-handed blow)."""

    id, name, cost, target, aimed = "attack_tongue", "Lash", 1, "enemy", True
    desc = "Lash an enemy with your tongue."

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.has_tongue_weapon:
            return False, "Not a Grippli with Tongue."
        return True, ""

    def available(self, battle, actor):
        return actor.ap >= self.cost and actor.has_tongue_weapon

    def can(self, battle, actor, target=None):
        if actor.ap < self.cost or not actor.has_tongue_weapon:
            return False
        if not _attackable_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.tongue_reach:
            return False
        if abs(battle.elevation(actor) - battle.elevation(target)) > 1:
            return False
        return battle.los_between(actor, target) and battle.can_see_unit(actor, target)

    def label(self, battle, actor):
        if not self.available(battle, actor):
            return "Lash with the tongue (1 pt)"
        return f"Lash {actor.tongue_weapon_name} (1 pt, reach {actor.tongue_reach})"

    def highlight_cells(self, battle, actor):
        return [p for c in cells(actor.pos, actor.footprint)
                for p in cells_in_radius(c, actor.tongue_reach)]

    def highlight_targets(self, battle, actor):
        return [u for u in battle.units
                if not u.dead and u.team != actor.team and self.can(battle, actor, u)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        _strike(battle, actor, target, weapon=actor.tongue_weapon,
                prefix=f"{actor.name} -> {target.name} (tongue)")


# --------------------------------------------------------------------------- #
# Reload                                                                       #
# --------------------------------------------------------------------------- #

class Reload(Action):
    """Chamber a bolt in the crossbow: takes one from the quiver, 1 action point.
    A crossbow fires only while loaded and each shot empties it, so a crossbowman
    gets one bolt away per turn (Reload + Attack = the whole turn)."""

    id, name, cost, target = "reload", "Reload", 1, "none"
    desc = "Reload your crossbow."

    @classmethod
    def applicable(cls, battle, actor):
        if not hasattr(actor, "weapon") or not actor.weapon:
            return False, "Not holding a weapon."
        if not actor.weapon.get("reload"):
            return False, "Weapon does not need reloading."
        return True, ""

    def available(self, battle, actor):
        return actor.ap >= self.cost and actor.can_reload

    def can(self, battle, actor, target=None):
        return self.available(battle, actor)

    def label(self, battle, actor):
        return f"Reload the weapon (1 pt, {actor.ammo} bolts left)"

    def execute(self, battle, actor, target=None):
        if not self.available(battle, actor):
            return
        actor.ap -= 1
        actor.walking = False
        actor.ammo -= 1
        actor.crossbow_loaded = True
        battle.log(f"{actor.name} reloads the weapon ({actor.ammo} bolt(s) left).")


# --------------------------------------------------------------------------- #
# Defend                                                                       #
# --------------------------------------------------------------------------- #

class Defend(Action):
    id, name, cost, target = "defend", "Defend", 1, "none"
    desc = "+1 AC until your next turn."

    def available(self, battle, actor):
        return actor.ap >= self.cost and not actor.defending

    def label(self, battle, actor):
        return "Defend (1 pt, +1 AC)"

    def execute(self, battle, actor, target=None):
        if actor.ap < self.cost:
            return
        actor.ap -= 1
        actor.walking = False
        if actor.defending:
            battle.log(f"{actor.name} is already defending (circumstance bonus doesn't stack).")
        else:
            actor.add_condition(Defending())
            battle.log(f"{actor.name} defends: +1 AC [circumstance] until next turn.")


# --------------------------------------------------------------------------- #
# Throw                                                                        #
# --------------------------------------------------------------------------- #

class Throw(Action):
    id, name, cost, target, aimed = "throw", "Throw", 1, "enemy", True
    desc = "Throw your equipped weapon at a target in range."

    def available(self, battle, actor):
        return actor.ap >= self.cost and actor.can_throw

    def can(self, battle, actor, target=None):
        if not actor.can_throw or actor.ap < self.cost:
            return False
        if not _attackable_target(actor, target):
            return False
        if battle.units_distance(actor, target) > actor.throw_range:
            return False
        return battle.los_between(actor, target) and battle.can_see_unit(actor, target)

    def label(self, battle, actor):
        if not self.available(battle, actor):
            return "Throw weapon (1 pt)"
        return f"Throw {actor.weapon_name} (1 pt)"

    def highlight_cells(self, battle, actor):
        return [p for c in cells(actor.pos, actor.footprint)
                for p in cells_in_radius(c, actor.throw_range)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        weapon_name = actor.weapon_name

        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), thrown=True)
        if _flanked(battle, actor, target):
            mods.append((2, "circumstance", "Flank"))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} throws {weapon_name} at {target.name}"
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix, thrown=True)
        if res == "miss" and actor.can_use_luck(getattr(battle, "clock_day", 1)):
            actor.use_luck(getattr(battle, "clock_day", 1))
            nat2 = d20()
            total2 = nat2 + bonus
            hits = nat2 == 20 or total2 >= target.ac_vs(actor)
            battle.log(f"  Halfling Luck! {actor.name} rerolls throw: d20({nat2}) = {total2} -> "
                       + ("hit." if hits else "misses again."))
            if hits:
                target.take_damage(actor.damage_roll(crit=nat2 == 20, thrown=True), battle.log)

        actor.disarm()
        landing = _drop_cell(battle, target)
        battle.ground.append(GroundObject.weapon(landing, weapon_name))
        battle.log(f"  {weapon_name} lands at {landing}; {actor.name} is disarmed.")


# --------------------------------------------------------------------------- #
# Demoralize                                                                   #
# --------------------------------------------------------------------------- #

class Demoralize(Action):
    id, name, cost, target, aimed = "demoralize", "Demoralize", 1, "enemy", True
    desc = "Cha vs MD. Target is demoralized (cannot move, lower defenses)."

    def _can_provoke(self, battle, actor, target):
        return (actor.ability.demoralize_ignores_language
                or _shared_language(actor, target)
                or (battle.arena and getattr(actor, "arena_title", False)))

    def can(self, battle, actor, target=None):
        if actor.ap < self.cost or not _hostile_target(actor, target):
            return False
        if battle.units_distance(actor, target) > DEMORALIZE_RANGE:
            return False
        if not (battle.can_see_unit(actor, target) and battle.can_see_unit(target, actor)):
            return False
        return self._can_provoke(battle, actor, target)

    def label(self, battle, actor):
        return "Demoralize (1 pt, CHA vs Mental Defense)"

    def highlight_cells(self, battle, actor):
        return [p for c in cells(actor.pos, actor.footprint)
                for p in cells_in_radius(c, DEMORALIZE_RANGE)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False

        base_mod = actor.mod_charisma
        using_str = False
        has_talent = getattr(actor.char, "has_talent", lambda x: False)
        if has_talent("intimidating_presence") and actor.mod_strength > actor.mod_charisma:
            base_mod = actor.mod_strength
            using_str = True

        mods = [(base_mod, None, "STR" if using_str else "CHA")]
        titled = battle.arena and getattr(actor, "arena_title", False)
        if titled and _shared_language(actor, target):
            mods.append((1, "circumstance", "Champion of the Pit"))
        browbeat = actor.ability.demoralize_vs_weaker
        if browbeat and actor.mod_strength > target.mod_strength:
            mods.append((browbeat, "circumstance", "Browbeat"))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)

        if actor.ability.demoralize_ignores_language and not _shared_language(actor, target):
            battle.log(f"{actor.name} mimics {target.name}'s voice to provoke them.")

        nat = d20()
        total = nat + bonus
        md = target.mental_defense
        if battle.arena and getattr(target, "arena_title", False):
            md += 1                                # the champion is hard to rattle in their own pit
        crit = nat == 20
        desc = (f"{actor.name} tries to demoralize {target.name}: "
                f"d20({nat}) {detail} = {total} vs MD {md}")
        if nat == 1:
            battle.log(desc + "  -> critical miss.")
        elif crit or total >= md:
            target.add_condition(Demoralized())
            battle.log(desc + ("  -> CRITICAL HIT!" if crit else "  -> lands.")
                       + f" {target.name} is demoralized (-1 status until the end of their turn).")
        else:
            battle.log(desc + "  -> no effect.")


# --------------------------------------------------------------------------- #
# Flee the battle                                                              #
# --------------------------------------------------------------------------- #

class Flee(Action):
    """Run off the map. Only from a border cell, and only if the pursuers cannot
    keep up: you are faster than the quickest of them, or already far enough
    ahead that the chase fizzles. Deterministic -- the button lights up exactly
    when the escape would work. Ends your turn; downed allies are left behind."""

    id, name, cost, target = "flee", "Flee", 1, "none"
    desc = "Flee the battle from the map edge."

    @staticmethod
    def _at_edge(battle, actor):
        escape_cells = getattr(battle, "escape_cells", None)
        if escape_cells and any(c in escape_cells for c in battle.cells_of(actor)):
            return True
        b = battle.board
        return any(x == 0 or x == b.cols - 1 or y == 0 or y == b.rows - 1
                   for x, y in battle.cells_of(actor))

    @staticmethod
    def _pursuers(battle, actor):
        return [u for u in battle.units if u.alive and u.team != actor.team]

    def _escapes(self, battle, actor):
        pursuers = self._pursuers(battle, actor)
        if not pursuers:
            return True
        fastest = max(p.speed for p in pursuers)
        nearest = min(battle.units_distance(actor, p) for p in pursuers)
        return actor.speed > fastest or nearest > fastest

    def available(self, battle, actor):
        return (actor.ap >= self.cost and self._at_edge(battle, actor)
                and self._escapes(battle, actor))

    def label(self, battle, actor):
        if not self._at_edge(battle, actor):
            return "Flee (reach the map edge)"
        if not self._escapes(battle, actor):
            return "Flee (pursuers too fast / too close)"
        return "Flee the fight (1 pt, ends the turn)"

    def execute(self, battle, actor, target=None):
        if not self.available(battle, actor):
            return
        actor.ap = 0
        actor.walking = False
        actor.status = "fled"
        battle.log(f"{actor.name} flees the fight off the map edge.")
        # drag out any downed ally you are standing next to -- the rest are left
        for ally in battle.units:
            if (ally is not actor and ally.team == actor.team and ally.downed
                    and battle.units_distance(actor, ally) <= 1):
                ally.status = "fled"
                battle.log(f"  {actor.name} drags {ally.name} out of the fight.")
        battle._check_winner()


# --------------------------------------------------------------------------- #
# Push                                                                         #
# --------------------------------------------------------------------------- #

class Push(Action):
    """Shove an adjacent unit -- foe or friend -- one square straight back.
    Strength vs 10 + their Constitution modifier. If the square behind them is
    a pit, they go in (and take the fall). A wall / body behind them stops the
    shove dead."""

    id, name, cost, target, aimed = "push", "Push", 1, "unit", True
    desc = "Push an adjacent unit."

    def _targets(self, battle, actor):
        return [u for u in battle.units
                if u.alive and u is not actor and self.can(battle, actor, u)]

    def available(self, battle, actor):
        return actor.ap >= self.cost and bool(self._targets(battle, actor))

    def can(self, battle, actor, target=None):
        if actor.ap < self.cost or not _shovable_target(actor, target):
            return False
        if battle.units_distance(actor, target) > 1:
            return False
        if abs(battle.elevation(actor) - battle.elevation(target)) > 1:
            return False
        return battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Push (1 pt, STR vs 10 + target CON)"

    def highlight_targets(self, battle, actor):
        return self._targets(battle, actor)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        dc = PUSH_DC_BASE + target.mod_constitution
        nat = d20()
        total = nat + actor.mod_strength
        desc = (f"{actor.name} shoves {target.name}: d20({nat}) "
                f"{actor.mod_strength:+}(STR) = {total} vs {dc}")
        if nat != 20 and (nat == 1 or total < dc):
            battle.log(desc + "  -> holds their ground.")
            return

        ax, ay = actor.pos
        tx, ty = target.pos
        dx, dy = _sign(tx - ax), _sign(ty - ay)
        if dx == 0 and dy == 0:
            battle.log(desc + "  -> no room to shove.")
            return
        dest = (tx + dx, ty + dy)
        if battle.board.diagonal_corner_blocked(target.pos, dest) \
                or not _cell_free(battle, actor, dest, target.footprint):
            battle.log(desc + f"  -> {target.name} is shoved against something and can't move.")
            return
        z_from = battle.elevation(target)
        z_to = battle.elevation_at(dest, target)
        target.pos = dest
        target.z = z_to
        target.walking = False
        battle.log(desc + f"  -> {target.name} is shoved to {dest}.")
        
        was_up = target.alive
        trap = battle.ground_at(dest)
        if trap and battle.springs(trap, target):
            battle.trigger_trap(target, trap)
            
        if z_to < z_from:
            battle.apply_fall(target, z_from - z_to, battle.log)

        if was_up and target.team != actor.team:
            if not target.alive:
                actor.credit_kill(target)
            elif target.hp <= 0 and target.ferocity_downer is None:
                target.ferocity_downer = actor
