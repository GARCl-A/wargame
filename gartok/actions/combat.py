"""Attack-shaped actions: Attack, Reload, Defend, Throw, Demoralize, Flee, Push, Dragon Breath,
the Non-lethal toggle."""


from .. import intel
from ..board import cells, cells_in_radius, cone_cells
from ..conditions import Defending, Demoralized, Grappled
from ..data import DEMORALIZE_RANGE, d20, resolve_bonus, roll
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
    nonlethal_penalty,
)

PUSH_DC_BASE = 10          # Shove: Strength vs 10 + the target's Constitution modifier


# --------------------------------------------------------------------------- #
# Attack                                                                       #
# --------------------------------------------------------------------------- #

def _strike(battle, actor, target, *, weapon=None, prefix=None):
    """The shared attack resolution once the AP is paid: assemble the mods (feint),
    roll, resolve the hit, fire the on-miss ability. `weapon` overrides the
    held one (the Tongue). Returns 'hit'|'miss'|'crit'."""
    mods = actor.attack_mods(target, _pack_flank(battle, actor, target), weapon=weapon, battle=battle)

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
        total2 = nat2 + bonus - nonlethal_penalty(actor)
        hits = nat2 == 20 or total2 >= target.ac_vs(actor)
        battle.log(f"  Halfling Luck! {actor.name} rerolls attack: d20({nat2}) = {total2} -> "
                   + ("hit." if hits else "misses again."))
        if hits:
            target.take_damage(actor.damage_roll(crit=nat2 == 20, weapon=weapon), battle.log,
                               knockout=actor.nonlethal_blows)
            result = "hit"
    return result


class Attack(Action):
    id, name, cost, target, aimed = "attack", "Attack", 1, "enemy", True
    desc = "Melee or Ranged attack based on your equipped weapon."
    announce = False

    def flies(self, actor):
        return actor.ranged

    def label(self, battle, actor):
        natural = actor.ability.natural_weapon if actor.unarmed else None
        return natural or self.name

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
        natural = actor.ability.natural_weapon if actor.unarmed and not actor.ranged else None
        _strike(battle, actor, target,
                prefix=f"{actor.name} -> {target.name} ({natural.lower()})" if natural else None)


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
        result = _strike(battle, actor, target, weapon=actor.tongue_weapon,
                         prefix=f"{actor.name} -> {target.name} (tongue)")
        if result != "miss" and actor.char.talent_bonus("sticky_tongue"):
            self.reel(battle, actor, target)

    @staticmethod
    def reel(battle, actor, target):
        """Grippli Sticky Tongue: the lashed foe is pulled a square in and, once beside the
        Grippli, held fast."""
        if not target.alive or target.has_condition("grappled"):
            return
        if battle.units_distance(actor, target) > 1:
            dx, dy = Push.direction(actor, target)
            dest = (target.pos[0] - dx, target.pos[1] - dy)
            if Push._stopper(battle, target, dest, False) is None:
                Push.throw(battle, actor, target, [dest])
                battle.log(f"  The tongue reels {target.name} in to {dest}.")
        if target.alive and battle.units_distance(actor, target) <= 1:
            target.add_condition(Grappled(grappler=actor))
            battle.log(f"  {target.name} is stuck to the tongue: grappled!")


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
            iron = getattr(actor.char, "talent_bonus", lambda _: 0)("defend_mental_defense") if hasattr(actor, "char") else 0
            iron_txt = f", +{iron} Mental Defense [Iron Stance]" if iron else ""
            battle.log(f"{actor.name} defends: +1 AC [circumstance]{iron_txt} until next turn.")


# --------------------------------------------------------------------------- #
# Throw                                                                        #
# --------------------------------------------------------------------------- #

class Throw(Action):
    id, name, cost, target, aimed = "throw", "Throw", 1, "enemy", True
    missile = True
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

        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), thrown=True, battle=battle)
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
            total2 = nat2 + bonus - nonlethal_penalty(actor)
            hits = nat2 == 20 or total2 >= target.ac_vs(actor)
            battle.log(f"  Halfling Luck! {actor.name} rerolls throw: d20({nat2}) = {total2} -> "
                       + ("hit." if hits else "misses again."))
            if hits:
                target.take_damage(actor.damage_roll(crit=nat2 == 20, thrown=True), battle.log,
                                   knockout=actor.nonlethal_blows)

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
        execute_demoralize(battle, actor, target)


def execute_demoralize(battle, actor, target, *, free=False, ignore_language=False):
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
    demo_bonus = getattr(actor.char, "talent_bonus", lambda x: 0)("demoralize_bonus") if hasattr(actor, "char") else 0
    if demo_bonus:
        mods.append((demo_bonus, "training", "Menacing"))
    bonus, applied = resolve_bonus(mods)
    detail = " ".join(f"{v:+}({r})" for v, r in applied)

    if (actor.ability.demoralize_ignores_language or ignore_language) and not _shared_language(actor, target):
        if not free:
            battle.log(f"{actor.name} mimics {target.name}'s voice to provoke them.")

    nat = d20()
    total = nat + bonus
    md = target.mental_defense
    if battle.arena and getattr(target, "arena_title", False):
        md += 1                                # the champion is hard to rattle in their own pit
    crit = nat == 20
    prefix = f"{actor.name} tries to demoralize {target.name}" if not free else f"  {actor.name} intimidates {target.name}"
    desc = (f"{prefix}: "
            f"d20({nat}) {detail} = {total} vs MD {intel.shown(battle, target, 'md', md)}")
    if nat == 1:
        battle.log(desc + "  -> critical miss.")
    elif crit or total >= md:
        target.add_condition(Demoralized())
        battle.log(desc + ("  -> CRITICAL HIT!" if crit else "  -> lands.")
                   + f" {target.name} is demoralized (-1 status until the end of their turn).")
        init_boost = getattr(actor.char, "talent_bonus", lambda x: 0)("demoralize_ally_initiative") if hasattr(actor, "char") else 0
        if init_boost and hasattr(battle, "order") and hasattr(battle, "raise_initiative"):
            allies = [u for u in battle.order if u.alive and u.team == actor.team and u is not actor]
            if allies:
                idx = getattr(battle, "turn_idx", 0)
                after = [u for u in battle.order[idx + 1:] if u in allies]
                target_ally = after[0] if after else allies[0]
                battle.raise_initiative([target_ally], init_boost)
                battle.log(f"  Inspiring Shout! {target_ally.name} gains +{init_boost} initiative.")
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
        return (actor.ap >= self.cost and not actor.has_condition("grappled")
                and self._at_edge(battle, actor) and self._escapes(battle, actor))

    def blocked_reason(self, battle, actor):
        if actor.ap < self.cost:
            return "need 1 AP"
        if actor.has_condition("grappled"):
            return "grappled"
        if not self._at_edge(battle, actor):
            return "reach map edge"
        pursuers = self._pursuers(battle, actor)
        if not pursuers:
            return ""
        fastest = max(p.speed for p in pursuers)
        nearest = min(battle.units_distance(actor, p) for p in pursuers)
        if actor.speed <= fastest and nearest <= fastest:
            close = [p for p in pursuers if battle.units_distance(actor, p) == nearest]
            seen = any(battle.can_see_unit(actor, p) for p in close)
            if nearest <= 1:
                return "enemy right beside you" if seen else "enemy sounds right beside you"
            return "pursuers too close" if seen else "sounds of pursuers nearby"
        return ""

    def label(self, battle, actor):
        if not self.available(battle, actor):
            reason = self.blocked_reason(battle, actor)
            return f"Flee ({reason})" if reason else "Flee"
        return "Flee (1 pt, ends the turn)"

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
    shove dead. Mighty Shove (the Ogre's talent) throws them `MIGHTY_SQUARES` back
    for 1d6, and whatever stops them on the way -- a wall, or a body, which takes
    the blow too -- deals 1d6 more."""

    id, name, cost, target, aimed = "push", "Push", 1, "unit", True
    desc = "Push an adjacent unit."
    MIGHTY_SQUARES = 3
    MIGHTY_DIE = (1, 6)

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
        if actor.char.talent_bonus("mighty_shove"):
            return f"Mighty Shove (1 pt, STR vs 10 + target CON, {self.MIGHTY_SQUARES} sq, 1d6)"
        return "Push (1 pt, STR vs 10 + target CON)"

    def highlight_targets(self, battle, actor):
        return self._targets(battle, actor)

    @staticmethod
    def direction(actor, target):
        return _sign(target.pos[0] - actor.pos[0]), _sign(target.pos[1] - actor.pos[1])

    @staticmethod
    def _stopper(battle, target, dest, mighty):
        """What stops `target` stepping onto `dest`: None (it can), "wall", or the unit standing
        there -- a downed body too under a Mighty Shove (a plain shove lands on a fallen one)."""
        shape = cells(dest, target.footprint)
        if not all(battle.board.in_bounds(c) for c in shape)                 or battle.board.diagonal_corner_blocked(target.pos, dest)                 or battle.board.walls.intersection(shape) or battle.creature_cells().intersection(shape):
            return "wall"
        for u in battle.units:
            if u is not target and (u.alive or (mighty and u.downed)) and set(battle.cells_of(u)) & set(shape):
                return u
        return None

    @classmethod
    def landing(cls, battle, actor, target, squares=None):
        """Where a shove would leave `target` and what stops it: `(cells walked, stopper)`, the
        stopper None when the shove ran its full length. Read by the AI before it shoves."""
        dx, dy = cls.direction(actor, target)
        mighty = bool(actor.char.talent_bonus("mighty_shove"))
        if squares is None:
            squares = cls.MIGHTY_SQUARES if mighty else 1
        pos, path = target.pos, []
        z = battle.elevation(target)
        for _ in range(squares):
            dest = (pos[0] + dx, pos[1] + dy)
            stop = cls._stopper(battle, target, dest, mighty)
            if stop is not None:
                return path, stop
            path.append(dest)
            pos = dest
            if battle.elevation_at(dest, target) < z:
                break                          # over the lip: it falls in, the shove ends there
        return path, None

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        self.shove(battle, actor, target)

    @classmethod
    def shove(cls, battle, actor, target):
        """The shove itself, with no point spent: the roll, then the throw (Tail Sweep shoves too)."""
        dc = PUSH_DC_BASE + target.mod_constitution
        nat = d20()
        push_b = getattr(actor.char, "talent_bonus", lambda x: 0)("push_bonus") if hasattr(actor, "char") else 0
        total = nat + actor.mod_strength + push_b
        mighty = bool(actor.char.talent_bonus("mighty_shove"))
        b_txt = f" {push_b:+}(push talent)" if push_b else ""
        desc = (f"{actor.name} {'heaves' if mighty else 'shoves'} {target.name}: d20({nat}) "
                f"{actor.mod_strength:+}(STR){b_txt} = {total} vs {dc}")
        if nat != 20 and (nat == 1 or total < dc):
            battle.log(desc + "  -> holds their ground.")
            return
        if cls.direction(actor, target) == (0, 0):
            battle.log(desc + "  -> no room to shove.")
            return
        path, stopper = cls.landing(battle, actor, target)
        if not path and not mighty:
            battle.log(desc + f"  -> {target.name} is shoved against something and can't move.")
            return

        was_up = target.alive
        battle.log(desc + (f"  -> {target.name} is thrown to {path[-1]}." if path
                           else f"  -> {target.name} is slammed where they stand."))

        if mighty:
            target.take_damage(roll(*cls.MIGHTY_DIE), battle.log)
            if stopper is not None:
                what = "a wall" if stopper == "wall" else stopper.name
                battle.log(f"  {target.name} crashes into {what}!")
                target.take_damage(roll(*cls.MIGHTY_DIE), battle.log)
                if stopper != "wall":
                    body_up = stopper.alive
                    stopper.take_damage(roll(*cls.MIGHTY_DIE), battle.log)
                    if body_up and not stopper.alive and stopper.team != actor.team:
                        actor.credit_kill(stopper)

        cls.throw(battle, actor, target, path, was_up)

    @staticmethod
    def throw(battle, actor, target, path, was_up=None):
        """Carry `target` along `path` (cells from `landing`): what lies at the end springs, the
        flames on the way burn, a drop is a fall; whatever that drops is `actor`'s kill."""
        was_up = target.alive if was_up is None else was_up
        z_from = battle.elevation(target)
        before = set(battle.cells_of(target))
        entered = set()
        for dest in path:
            target.pos = dest
            entered |= set(battle.cells_of(target))
        target.walking = False
        z_to = battle.elevation_at(target.pos, target)
        target.z = z_to
        trap = battle.ground_at(target.pos)
        if trap and battle.springs(trap, target):
            battle.trigger_trap(target, trap)
        battle.burn(target, entered - before)

        if z_to < z_from:
            battle.apply_fall(target, z_from - z_to, battle.log)

        if was_up and target.team != actor.team:
            if not target.alive:
                actor.credit_kill(target)
            elif target.hp <= 0 and target.ferocity_downer is None:
                target.ferocity_downer = actor

        battle.check_grapples()


# --------------------------------------------------------------------------- #
# Dragon Breath                                                                #
# --------------------------------------------------------------------------- #

class DragonBreath(Action):
    """A cone of breath from the Dragon Breath magic talent: one Constitution attack roll
    against every standing unit in it, allies included. Aimed by clicking a cell beside the
    breather, which sets the direction."""
    id, name, cost, target, aimed = "dragon_breath", "Dragon Breath", 2, "cell", True
    desc = "2 points: a cone 3 squares deep; one attack roll against everyone in it, allies too."
    DEPTH = 3
    DICE = (2, 6)

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.char.talent_bonus("dragon_breath"):
            return False, "Needs the Dragon Breath talent."
        return True, ""

    @staticmethod
    def direction(battle, actor, cell):
        """Which of the 8 directions `cell` lies in from the breather's body, or (0, 0)."""
        body = battle.cells_of(actor)
        xs, ys = [x for x, _ in body], [y for _, y in body]
        x, y = cell
        return ((x > max(xs)) - (x < min(xs)), (y > max(ys)) - (y < min(ys)))

    def can(self, battle, actor, target=None):
        return (self.available(battle, actor) and target is not None
                and battle.board.in_bounds(target)
                and self.direction(battle, actor, target) != (0, 0))

    def highlight_cells(self, battle, actor):
        body = set(battle.cells_of(actor))
        ring = {n for c in body for n in battle.board.neighbors(c)} - body
        return sorted(c for c in ring if self.can(battle, actor, c))

    def highlight_targets(self, battle, actor):
        return []

    def area_cells(self, battle, actor, cell):
        """The cone toward `cell`: open ground the breath reaches past no wall."""
        sx, sy = self.direction(battle, actor, cell)
        if (sx, sy) == (0, 0):
            return []
        body = battle.cells_of(actor)
        area = set()
        for origin in body:
            area.update(c for c in cone_cells(origin, (sx, sy), self.DEPTH)
                        if battle.board.in_bounds(c) and c not in battle.board.walls
                        and battle.board.los_clear(origin, c))
        return sorted(area - set(body))

    def caught(self, battle, actor, cell):
        """The standing units the cone toward `cell` reaches."""
        area = set(self.area_cells(battle, actor, cell))
        return [u for u in battle.units
                if u is not actor and u.alive and area.intersection(battle.cells_of(u))]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        victims = self.caught(battle, actor, target)
        nat = d20()
        pulled = nonlethal_penalty(actor)
        total = nat + actor.mod_constitution - pulled
        battle.log(f"{actor.name} breathes fire! d20({nat}) {actor.mod_constitution:+}(CON)"
                   + (f" -{pulled}(non-lethal)" if pulled else "") + f" = {total}")
        if nat == 1:
            battle.log("  -> the breath sputters out.")
            return
        for u in victims:
            ac = u.ac_vs(actor)
            shown = intel.shown(battle, u, "ac", ac)
            if nat != 20 and total < ac:
                battle.log(f"  {u.name} (AC {shown}) -> misses.")
                battle.fx(u.pos, f"{total} vs AC {shown}", "faint")
                battle.cue("miss", u.pos)
                continue
            battle.fx(u.pos, f"{total} vs AC {shown}", "crit" if nat == 20 else "ok")
            if nat == 20:
                battle.cue("crit", u.pos)
            dice = self.DICE[0] * (2 if nat == 20 else 1)
            battle.log(f"  {u.name} (AC {shown}) -> " + ("CRITICAL HIT!" if nat == 20 else "hit."))
            was_up = u.alive
            u.take_damage(roll(dice, self.DICE[1]), battle.log, knockout=bool(pulled))
            if was_up and u.team != actor.team:
                if not u.alive:
                    actor.credit_kill(u, magic=True)
                elif u.hp <= 0 and u.ferocity_downer is None:
                    u.ferocity_downer = actor
        if getattr(battle.scenario, "breath_burns", False):
            battle.fire.update(self.area_cells(battle, actor, target))
# --------------------------------------------------------------------------- #
# Grab                                                                        #
# --------------------------------------------------------------------------- #

class Grab(Action):
    """Grab an adjacent enemy: 1 AP, Strength vs 10 + target's higher of STR/DEX.
    On success, the target is Grappled (speed 0, -2 AC) until they break free
    or the grappler is downed or moves away."""
    id, name, cost, target, aimed = "grab", "Grab", 1, "enemy", True
    desc = "Grab an adjacent foe to hold them in place (0 speed, -2 AC)."

    def _targets(self, battle, actor):
        return [u for u in battle.units
                if u.alive and u.team != actor.team and self.can(battle, actor, u)]

    def available(self, battle, actor):
        return actor.ap >= self.cost and bool(self._targets(battle, actor))

    def can(self, battle, actor, target=None):
        if actor.ap < self.cost or not _hostile_target(actor, target):
            return False
        if not target.alive or target.has_condition("grappled"):
            return False
        if battle.units_distance(actor, target) > 1:
            return False
        if abs(battle.elevation(actor) - battle.elevation(target)) > 1:
            return False
        return battle.los_between(actor, target) and battle.can_see_unit(actor, target)

    def label(self, battle, actor):
        char = getattr(actor, "char", actor)
        bonus = getattr(char, "talent_bonus", lambda _: 0)("grab_bonus")
        if bonus:
            return f"Grab (1 pt, STR{bonus:+} vs 10 + target STR/DEX)"
        return "Grab (1 pt, STR vs 10 + target STR/DEX)"

    def highlight_targets(self, battle, actor):
        return self._targets(battle, actor)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        dc = 10 + max(target.mod_strength, target.mod_dexterity)
        nat = d20()
        char = getattr(actor, "char", actor)
        bonus = actor.mod_strength + getattr(char, "talent_bonus", lambda _: 0)("grab_bonus")
        total = nat + bonus
        desc = (f"{actor.name} grabs {target.name}: d20({nat}) "
                f"{bonus:+}(STR) = {total} vs DC {dc}")
        if nat == 20 or total >= dc:
            target.add_condition(Grappled(grappler=actor))
            battle.log(desc + f" -> {target.name} is grappled!")
            battle.fx(target.pos, "grappled", "ok")
        else:
            battle.log(desc + " -> failed.")


# --------------------------------------------------------------------------- #
# Escape Grapple                                                              #
# --------------------------------------------------------------------------- #

class EscapeGrapple(Action):
    """Attempt to break free from a grapple (1 AP: Strength or Dexterity vs 10 + grappler Strength)."""
    id, name, cost, target = "escape_grapple", "Escape Grapple", 1, "none"
    desc = "Break free from a grapple (STR or DEX vs 10 + grappler STR)."

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.has_condition("grappled"):
            return False, "not grappled"
        return True, ""

    def available(self, battle, actor):
        return actor.ap >= self.cost and actor.has_condition("grappled")

    def label(self, battle, actor):
        return "Escape Grapple (1 pt, STR/DEX)"

    def execute(self, battle, actor, target=None):
        if not self.available(battle, actor):
            return
        actor.ap -= 1
        actor.walking = False
        cond = actor.condition("grappled")
        grappler = getattr(cond, "grappler", None)
        g_char = getattr(grappler, "char", grappler) if grappler else None
        g_bonus = getattr(g_char, "talent_bonus", lambda _: 0)("grab_bonus") if g_char else 0
        dc = 10 + (grappler.mod_strength + g_bonus if grappler else 0)
        nat = d20()
        esc_bonus = max(actor.mod_strength, actor.mod_dexterity)
        total = nat + esc_bonus
        desc = (f"{actor.name} attempts to break free: d20({nat}) "
                f"{esc_bonus:+} = {total} vs DC {dc}")
        if nat == 20 or total >= dc:
            if cond in actor.conditions:
                actor.conditions.remove(cond)
            battle.log(desc + " -> Escaped!")
            battle.fx(actor.pos, "free", "ok")
        else:
            battle.log(desc + " -> failed.")


# --------------------------------------------------------------------------- #
# Zombie Bite                                                                 #
# --------------------------------------------------------------------------- #

class ZombieBite(Action):
    """Zombie Bite: a savage bite targeting a grappled foe; +2 to hit, deals 1d8 + Strength damage."""
    id, name, cost, target, aimed = "zombie_bite", "Bite", 1, "enemy", True
    desc = "Sink teeth into a grappled foe (+2 to hit, 1d8 + STR damage)."

    @classmethod
    def applicable(cls, battle, actor):
        char = getattr(actor, "char", actor)
        if not getattr(char, "has_talent", lambda _: False)("zombie_bite"):
            return False, "requires Zombie Bite talent"
        return True, ""

    def _targets(self, battle, actor):
        return [u for u in battle.units
                if u.alive and u.team != actor.team and self.can(battle, actor, u)]

    def available(self, battle, actor):
        char = getattr(actor, "char", actor)
        has_talent = getattr(char, "has_talent", lambda _: False)("zombie_bite")
        return actor.ap >= self.cost and has_talent and bool(self._targets(battle, actor))

    def can(self, battle, actor, target=None):
        if actor.ap < self.cost or not _hostile_target(actor, target):
            return False
        char = getattr(actor, "char", actor)
        if not getattr(char, "has_talent", lambda _: False)("zombie_bite"):
            return False
        if not target.alive or not target.has_condition("grappled"):
            return False
        if battle.units_distance(actor, target) > 1:
            return False
        if abs(battle.elevation(actor) - battle.elevation(target)) > 1:
            return False
        return battle.los_between(actor, target) and battle.can_see_unit(actor, target)

    def label(self, battle, actor):
        return "Zombie Bite (1 pt, +2 to hit, 1d8+STR)"

    def highlight_targets(self, battle, actor):
        return self._targets(battle, actor)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), battle=battle)
        mods.append((2, "circumstance", "Bite Grappled Foe"))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        prefix = f"{actor.name} Bite -> {target.name}"
        total = nat + bonus
        ac = target.ac_vs(actor)
        crit = nat == 20 or (nat != 1 and total >= ac + 10)
        hit = nat != 1 and (nat == 20 or total >= ac)
        if not hit:
            battle.log(f"{prefix}: d20({nat}) {detail} = {total} vs AC {ac} -> miss.")
            battle.fx(target.pos, "miss", "miss")
            battle.cue("miss", target.pos)
            return
        res = "crit" if crit else "hit"
        if crit:
            battle.cue("crit", target.pos)
        dice = roll(2, 8) if crit else roll(1, 8)
        char = getattr(actor, "char", actor)
        dmg = max(1, dice + actor.mod_strength + getattr(char, "talent_bonus", lambda _: 0)("melee_damage"))
        battle.log(f"{prefix}: d20({nat}) {detail} = {total} vs AC {ac} -> {res.upper()} for {dmg} damage!")
        battle.fx(target.pos, f"-{dmg}", res)
        target.take_damage(dmg, battle.log, knockout=actor.nonlethal_blows)
        if not target.alive and target.team != actor.team:
            actor.credit_kill(target)
        battle.check_grapples()


# --------------------------------------------------------------------------- #
# Non-lethal toggle                                                            #
# --------------------------------------------------------------------------- #

class NonLethal(Action):
    """Pull your blows, or stop pulling them: a free switch, kept for the rest of the
    fight. Pulled blows are -1 to hit; a foe they drop is knocked out (`stable`) instead of
    dying, and a blow on a dying body spares it."""
    id, name, cost, target, aimed = "nonlethal", "Non-lethal", 0, "none", False
    desc = "Free: pull your blows (-1 to hit); a foe you drop is knocked out, not dying."
    toggle = True

    @classmethod
    def applicable(cls, battle, actor):
        if not battle.lethal:
            return False, "the fight is non-lethal already."
        return True, ""

    def label(self, battle, actor):
        return "Non-lethal: ON" if actor.nonlethal_blows else "Non-lethal: OFF"

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.nonlethal_blows = not actor.nonlethal_blows
        battle.log(f"{actor.name} " + ("pulls their blows (non-lethal)." if actor.nonlethal_blows
                                       else "fights to kill again."))


# --------------------------------------------------------------------------- #
# Tail Sweep                                                                   #
# --------------------------------------------------------------------------- #

class TailSweep(Action):
    """Lizardfolk Tail Sweep: 2 points, the tail sweeps two adjacent foes -- an unarmed strike
    and a shove (`Push.shove`, its own roll) on each. With one foe beside you it sweeps that one."""
    id, name, cost, target, aimed = "tail_sweep", "Tail Sweep", 2, "enemy", True
    desc = "2 points: an unarmed tail strike and a Push on two adjacent foes."

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.char.talent_bonus("tail_sweep"):
            return False, "Missing 'tail_sweep' talent."
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        return battle.units_distance(actor, target) <= 1 and battle.los_between(actor, target)

    def label(self, battle, actor):
        return "Tail Sweep (2 pts, strike and shove 2 adjacent foes)"

    def highlight_targets(self, battle, actor):
        return [u for u in battle.units if self.can(battle, actor, u)]

    @staticmethod
    def tail(actor):
        """The tail as a weapon: the unarmed die, swung with Strength."""
        return {"name": "Tail", "damage": actor.unarmed_damage, "crit_mult": 2, "crit_range": 20}

    @staticmethod
    def second(battle, actor, target):
        """The other foe the sweep carries into: beside the sweeper, the weakest."""
        candidates = [u for u in battle.units
                      if u.alive and u.team != actor.team and u is not target
                      and not u.hidden_from(actor.team) and battle.units_distance(actor, u) <= 1
                      and battle.los_between(actor, u)]
        return min(candidates, key=lambda c: c.hp) if candidates else None

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        swept = [target] + [u for u in (self.second(battle, actor, target),) if u is not None]
        tail = self.tail(actor)
        for foe in swept:
            if foe.alive:
                _strike(battle, actor, foe, weapon=tail, prefix=f"{actor.name} Tail Sweep -> {foe.name}")
        for foe in swept:
            if foe.alive and battle.units_distance(actor, foe) <= 1:
                Push.shove(battle, actor, foe)
