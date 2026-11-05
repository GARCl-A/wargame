"""Attack-shaped actions: Attack, Reload, Defend, Throw, Demoralize, Flee, Push, Dragon Breath,
the Non-lethal toggle."""


from .. import i18n, intel, natural_weapons
from ..board import cells, cells_in_radius, cone_cells
from ..conditions import Defending, Demoralized, Grappled, Prone
from ..data import DEMORALIZE_RANGE, d20, resolve_bonus, roll
from ..i18n import Msg, Ref, plural_key
from .base import (
    Action,
    _attackable_target,
    _cell_free,
    _flanked,
    _hostile_target,
    _land_thrown,
    _pack_flank,
    _resolve_hit,
    _shared_language,
    _shovable_target,
    _sign,
    item_ref,
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
        battle.log("log.feint", actor=actor.name, ability=Ref("ability", ab.id, ab.name))

    bonus, applied = resolve_bonus(mods)
    detail = " ".join(f"{v:+}({r})" for v, r in applied)
    nat = d20()
    result = _resolve_hit(battle, actor, target, nat, bonus, detail,
                          prefix or Msg("log.attack.head", actor=actor.name, target=target.name), weapon=weapon)

    if result == "miss" and nat != 1 and ab.on_attack_miss \
            and actor.spend_once("on_attack_miss"):
        ab.on_attack_miss(battle, actor, target, bonus, target.ac_vs(actor), battle.log)
    elif result == "miss" and actor.can_use_luck(getattr(battle, "clock_day", 1)):
        actor.use_luck(getattr(battle, "clock_day", 1))
        nat2 = d20()
        total2 = nat2 + bonus - nonlethal_penalty(actor)
        hits = nat2 == 20 or total2 >= target.ac_vs(actor)
        battle.log("log.luck_attack.hit" if hits else "log.luck_attack.miss", actor=actor.name, nat=nat2, total=total2)
        if hits:
            target.take_damage(actor.damage_roll(crit=nat2 == 20, weapon=weapon), battle.log,
                               knockout=actor.nonlethal_blows)
            result = "hit"
    return result


class Attack(Action):
    id, cost, target, aimed = "attack", 1, "enemy", True
    announce = False

    def flies(self, actor):
        return actor.ranged

    def label(self, battle, actor):
        return actor.weapon.name if actor.natural else self.name

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
                battle.log(plural_key("log.shoot_bolt", actor.ammo), actor=actor.name, n=actor.ammo)
            else:
                actor.ammo -= 1                             # a bow draws from the quiver on every shot
                battle.log(plural_key("log.shoot_arrow", actor.ammo), actor=actor.name, n=actor.ammo)
        natural = actor.weapon.name if actor.natural else None
        _strike(battle, actor, target, prefix=Msg(
            "log.attack.head_via", actor=actor.name, target=target.name, how=item_ref(natural, lower=True)) if natural else None)


class AttackTongue(Action):
    """The Grippli's Tongue: a second weapon, an extra limb. A 1-handed weapon in
    the Tongue slot, swung at +1 square of reach. A separate action so a Grippli
    can choose it or the hand weapon each turn (a reach poke vs. a 2-handed blow)."""

    id, cost, target, aimed = "attack_tongue", 1, "enemy", True

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.has_tongue_weapon:
            return False, i18n.t("action.attack_tongue.reason")
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
            return i18n.t("action.attack_tongue.label_off")
        return i18n.t("action.attack_tongue.label", weapon=item_ref(actor.tongue_weapon_name), reach=actor.tongue_reach)

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
                         prefix=Msg("log.attack.head_tongue", actor=actor.name, target=target.name))
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
                battle.log("log.tongue_reel", target=target.name, cell=str(dest))
        if target.alive and battle.units_distance(actor, target) <= 1:
            target.add_condition(Grappled(grappler=actor))
            battle.log("log.tongue_stuck", target=target.name)


# --------------------------------------------------------------------------- #
# Reload                                                                       #
# --------------------------------------------------------------------------- #

class Reload(Action):
    """Chamber a bolt in the crossbow: takes one from the quiver, 1 action point.
    A crossbow fires only while loaded and each shot empties it, so a crossbowman
    gets one bolt away per turn (Reload + Attack = the whole turn)."""

    id, cost, target = "reload", 1, "none"

    @classmethod
    def applicable(cls, battle, actor):
        if not hasattr(actor, "weapon") or not actor.weapon:
            return False, i18n.t("action.reload.reason_none")
        if not actor.weapon.get("reload"):
            return False, i18n.t("action.reload.reason_no_need")
        return True, ""

    def available(self, battle, actor):
        return actor.ap >= self.cost and actor.can_reload

    def can(self, battle, actor, target=None):
        return self.available(battle, actor)

    def label(self, battle, actor):
        return i18n.plural("action.reload.label", actor.ammo)

    def execute(self, battle, actor, target=None):
        if not self.available(battle, actor):
            return
        actor.ap -= 1
        actor.walking = False
        actor.ammo -= 1
        actor.crossbow_loaded = True
        battle.log(plural_key("log.reload", actor.ammo), actor=actor.name, n=actor.ammo)


# --------------------------------------------------------------------------- #
# Defend                                                                       #
# --------------------------------------------------------------------------- #

class Defend(Action):
    id, cost, target = "defend", 1, "none"

    def available(self, battle, actor):
        return actor.ap >= self.cost and not actor.defending

    def label(self, battle, actor):
        return i18n.t("action.defend.label")

    def execute(self, battle, actor, target=None):
        if actor.ap < self.cost:
            return
        actor.ap -= 1
        actor.walking = False
        if actor.defending:
            battle.log("log.defend_again", actor=actor.name)
        else:
            actor.add_condition(Defending())
            iron = getattr(actor.char, "talent_bonus", lambda _: 0)("defend_mental_defense") if hasattr(actor, "char") else 0
            if iron:
                battle.log("log.defend_iron", actor=actor.name, iron=iron)
            else:
                battle.log("log.defend", actor=actor.name)


# --------------------------------------------------------------------------- #
# Throw                                                                        #
# --------------------------------------------------------------------------- #

class Throw(Action):
    id, cost, target, aimed = "throw", 1, "enemy", True
    missile = True

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
            return i18n.t("action.throw.label_off")
        return i18n.t("action.throw.label", weapon=item_ref(actor.weapon_name))

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
        prefix = Msg("log.throw.head", actor=actor.name, weapon=item_ref(weapon_name), target=target.name)
        res = _resolve_hit(battle, actor, target, nat, bonus, detail, prefix, thrown=True)
        if res == "miss" and actor.can_use_luck(getattr(battle, "clock_day", 1)):
            actor.use_luck(getattr(battle, "clock_day", 1))
            nat2 = d20()
            total2 = nat2 + bonus - nonlethal_penalty(actor)
            hits = nat2 == 20 or total2 >= target.ac_vs(actor)
            battle.log("log.luck_throw.hit" if hits else "log.luck_throw.miss", actor=actor.name, nat=nat2, total=total2)
            if hits:
                target.take_damage(actor.damage_roll(crit=nat2 == 20, thrown=True), battle.log,
                                   knockout=actor.nonlethal_blows)

        _land_thrown(battle, actor, target, weapon_name)


# --------------------------------------------------------------------------- #
# Demoralize                                                                   #
# --------------------------------------------------------------------------- #

class Demoralize(Action):
    id, cost, target, aimed = "demoralize", 1, "enemy", True

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
        return i18n.t("action.demoralize.label")

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
        mods.append((1, "circumstance", i18n.t("log.mod_champion")))
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
            battle.log("log.mimic", actor=actor.name, target=target.name)

    nat = d20()
    total = nat + bonus
    md = target.mental_defense
    if battle.arena and getattr(target, "arena_title", False):
        md += 1                                # the champion is hard to rattle in their own pit
    crit = nat == 20
    head = Msg("log.demoralize.head_free" if free else "log.demoralize.head", actor=actor.name, target=target.name)
    roll_line = {"head": head, "nat": nat, "detail": detail, "total": total, "md": intel.shown(battle, target, "md", md),
                 "target": target.name}
    if nat == 1:
        battle.log("log.demoralize.crit_miss", **roll_line)
    elif crit or total >= md:
        target.add_condition(Demoralized())
        battle.log("log.demoralize.crit" if crit else "log.demoralize.lands", **roll_line)
        init_boost = getattr(actor.char, "talent_bonus", lambda x: 0)("demoralize_ally_initiative") if hasattr(actor, "char") else 0
        if init_boost and hasattr(battle, "order") and hasattr(battle, "raise_initiative"):
            allies = [u for u in battle.order if u.alive and u.team == actor.team and u is not actor]
            if allies:
                idx = getattr(battle, "turn_idx", 0)
                after = [u for u in battle.order[idx + 1:] if u in allies]
                target_ally = after[0] if after else allies[0]
                battle.raise_initiative([target_ally], init_boost)
                battle.log("log.inspiring_shout", ally=target_ally.name, n=init_boost)
    else:
        battle.log("log.demoralize.none", **roll_line)


# --------------------------------------------------------------------------- #
# Flee the battle                                                              #
# --------------------------------------------------------------------------- #

class Flee(Action):
    """Run off the map. Only from a border cell, and only if the pursuers cannot
    keep up: you are faster than the quickest of them, or already far enough
    ahead that the chase fizzles. Deterministic -- the button lights up exactly
    when the escape would work. Ends your turn; downed allies are left behind."""

    id, cost, target = "flee", 1, "none"

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
                and not actor.has_condition("prone") and self._at_edge(battle, actor) and self._escapes(battle, actor))

    def blocked_reason(self, battle, actor):
        if actor.ap < self.cost:
            return i18n.t("action.flee.reason_ap")
        if actor.has_condition("grappled"):
            return i18n.t("action.flee.reason_grappled")
        if actor.has_condition("prone"):
            return i18n.t("action.flee.reason_prone")
        if not self._at_edge(battle, actor):
            return i18n.t("action.flee.reason_edge")
        pursuers = self._pursuers(battle, actor)
        if not pursuers:
            return ""
        fastest = max(p.speed for p in pursuers)
        nearest = min(battle.units_distance(actor, p) for p in pursuers)
        if actor.speed <= fastest and nearest <= fastest:
            close = [p for p in pursuers if battle.units_distance(actor, p) == nearest]
            seen = any(battle.can_see_unit(actor, p) for p in close)
            if nearest <= 1:
                return i18n.t("action.flee.reason_beside" if seen else "action.flee.reason_beside_heard")
            return i18n.t("action.flee.reason_close" if seen else "action.flee.reason_close_heard")
        return ""

    def label(self, battle, actor):
        if not self.available(battle, actor):
            reason = self.blocked_reason(battle, actor)
            return i18n.t("action.flee.label_blocked", reason=reason) if reason else i18n.t("action.flee.label_plain")
        return i18n.t("action.flee.label")

    def execute(self, battle, actor, target=None):
        if not self.available(battle, actor):
            return
        actor.ap = 0
        actor.walking = False
        actor.status = "fled"
        battle.log("log.flee", actor=actor.name)
        # drag out any downed ally you are standing next to -- the rest are left
        for ally in battle.units:
            if (ally is not actor and ally.team == actor.team and ally.downed
                    and battle.units_distance(actor, ally) <= 1):
                ally.status = "fled"
                battle.log("log.flee_drag", actor=actor.name, ally=ally.name)
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

    id, cost, target, aimed = "push", 1, "unit", True
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
            return i18n.t("action.push.label_mighty", n=self.MIGHTY_SQUARES)
        return i18n.t("action.push.label")

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
        head = Msg("log.push.head_heave" if mighty else "log.push.head_shove", actor=actor.name, target=target.name,
                   nat=nat, str=actor.mod_strength, total=total, dc=dc,
                   talent=Msg("log.push.talent", n=push_b) if push_b else "")
        if nat != 20 and (nat == 1 or total < dc):
            battle.log("log.push.holds", head=head)
            return
        if cls.direction(actor, target) == (0, 0):
            battle.log("log.push.no_room", head=head)
            return
        path, stopper = cls.landing(battle, actor, target)
        if not path and not mighty:
            battle.log("log.push.blocked", head=head, target=target.name)
            return

        was_up = target.alive
        if path:
            battle.log("log.push.thrown", head=head, target=target.name, cell=str(path[-1]))
        else:
            battle.log("log.push.slammed", head=head, target=target.name)

        if mighty:
            target.take_damage(roll(*cls.MIGHTY_DIE), battle.log)
            if stopper is not None:
                if stopper == "wall":
                    battle.log("log.push.crash_wall", target=target.name)
                else:
                    battle.log("log.push.crash_unit", target=target.name, other=stopper.name)
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
    id, cost, target, aimed = "dragon_breath", 2, "cell", True
    DEPTH = 3
    DICE = (2, 6)

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.char.talent_bonus("dragon_breath"):
            return False, i18n.t("action.dragon_breath.reason")
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
        battle.log("log.breath.head", actor=actor.name, nat=nat, con=actor.mod_constitution, total=total,
                   pulled=Msg("log.breath.pulled", n=pulled) if pulled else "")
        if nat == 1:
            battle.log("log.breath.sputters")
            return
        for u in victims:
            ac = u.ac_vs(actor)
            shown = intel.shown(battle, u, "ac", ac)
            if nat != 20 and total < ac:
                battle.log("log.breath.miss", target=u.name, shown=shown)
                battle.fx(u.pos, i18n.t("fx.vs_ac", total=total, shown=shown), "faint")
                battle.cue("miss", u.pos)
                continue
            battle.fx(u.pos, i18n.t("fx.vs_ac", total=total, shown=shown), "crit" if nat == 20 else "ok")
            if nat == 20:
                battle.cue("crit", u.pos)
            dice = self.DICE[0] * (2 if nat == 20 else 1)
            battle.log("log.breath.crit" if nat == 20 else "log.breath.hit", target=u.name, shown=shown)
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
    id, cost, target, aimed = "grab", 1, "enemy", True

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
            return i18n.t("action.grab.label_bonus", bonus=bonus)
        return i18n.t("action.grab.label")

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
        roll_line = {"actor": actor.name, "target": target.name, "nat": nat, "bonus": bonus, "total": total, "dc": dc}
        if nat == 20 or total >= dc:
            target.add_condition(Grappled(grappler=actor))
            battle.log("log.grab.hit", **roll_line)
            battle.fx(target.pos, i18n.t("fx.grappled"), "ok")
        else:
            battle.log("log.grab.miss", **roll_line)


# --------------------------------------------------------------------------- #
# Takedown / Stand Up                                                         #
# --------------------------------------------------------------------------- #

class Takedown(Action):
    """Knock an adjacent foe to the ground: 1 AP, d20 + STR against the foe's d20 + DEX; matching it
    is enough, and a natural 20 always lands. The foe is Prone. A flier cannot be brought down."""
    id, cost, target, aimed = "takedown", 1, "enemy", True

    def _targets(self, battle, actor):
        return [u for u in battle.units
                if u.alive and u.team != actor.team and self.can(battle, actor, u)]

    def available(self, battle, actor):
        return actor.ap >= self.cost and bool(self._targets(battle, actor))

    def can(self, battle, actor, target=None):
        if actor.ap < self.cost or not _hostile_target(actor, target):
            return False
        if target.has_condition("prone") or target.flies:
            return False
        if battle.units_distance(actor, target) > 1:
            return False
        if abs(battle.elevation(actor) - battle.elevation(target)) > 1:
            return False
        return battle.los_between(actor, target) and battle.can_see_unit(actor, target)

    def label(self, battle, actor):
        return i18n.t("action.takedown.label")

    def highlight_targets(self, battle, actor):
        return self._targets(battle, actor)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        mine, theirs = d20(), d20()
        total = mine + actor.mod_strength
        resist = theirs + target.mod_dexterity
        roll_line = {"actor": actor.name, "target": target.name, "mine": mine, "str": actor.mod_strength, "total": total,
                     "theirs": theirs, "dex": target.mod_dexterity, "resist": resist}
        if mine == 20 or total >= resist:
            target.add_condition(Prone())
            battle.log("log.takedown.hit", **roll_line)
            battle.fx(target.pos, i18n.t("fx.prone"), "ok")
        else:
            battle.log("log.takedown.miss", **roll_line)


class StandUp(Action):
    """Get back on your feet: 1 AP, only while Prone."""
    id, cost, target = "stand_up", 1, "none"

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.has_condition("prone"):
            return False, i18n.t("action.stand_up.reason")
        return True, ""

    def available(self, battle, actor):
        return actor.ap >= self.cost and actor.has_condition("prone")

    def label(self, battle, actor):
        return i18n.t("action.stand_up.label")

    def execute(self, battle, actor, target=None):
        if not self.available(battle, actor):
            return
        actor.ap -= 1
        actor.walking = False
        actor.conditions.remove(actor.condition("prone"))
        battle.log("log.stand_up", actor=actor.name)
        battle.fx(actor.pos, i18n.t("fx.up"), "ok")


# --------------------------------------------------------------------------- #
# Escape Grapple                                                              #
# --------------------------------------------------------------------------- #

class EscapeGrapple(Action):
    """Attempt to break free from a grapple (1 AP: Strength or Dexterity vs 10 + grappler Strength)."""
    id, cost, target = "escape_grapple", 1, "none"

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.has_condition("grappled"):
            return False, i18n.t("action.escape_grapple.reason")
        return True, ""

    def available(self, battle, actor):
        return actor.ap >= self.cost and actor.has_condition("grappled")

    def label(self, battle, actor):
        return i18n.t("action.escape_grapple.label")

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
        roll_line = {"actor": actor.name, "nat": nat, "bonus": esc_bonus, "total": total, "dc": dc}
        if nat == 20 or total >= dc:
            if cond in actor.conditions:
                actor.conditions.remove(cond)
            battle.log("log.escape.hit", **roll_line)
            battle.fx(actor.pos, i18n.t("fx.free"), "ok")
        else:
            battle.log("log.escape.miss", **roll_line)


# --------------------------------------------------------------------------- #
# Zombie Bite                                                                 #
# --------------------------------------------------------------------------- #

class ZombieBite(Action):
    """Zombie Bite: a savage bite targeting a grappled foe; +2 to hit, deals 1d8 + Strength damage."""
    id, cost, target, aimed = "zombie_bite", 1, "enemy", True

    @classmethod
    def applicable(cls, battle, actor):
        char = getattr(actor, "char", actor)
        if not getattr(char, "has_talent", lambda _: False)("zombie_bite"):
            return False, i18n.t("action.zombie_bite.reason")
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
        return i18n.t("action.zombie_bite.label")

    def highlight_targets(self, battle, actor):
        return self._targets(battle, actor)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        mods = actor.attack_mods(target, _pack_flank(battle, actor, target), battle=battle)
        mods.append((2, "circumstance", i18n.t("log.mod_bite")))
        bonus, applied = resolve_bonus(mods)
        detail = " ".join(f"{v:+}({r})" for v, r in applied)
        nat = d20()
        head = Msg("log.bite.head", actor=actor.name, target=target.name)
        total = nat + bonus
        ac = target.ac_vs(actor)
        crit = nat == 20 or (nat != 1 and total >= ac + 10)
        hit = nat != 1 and (nat == 20 or total >= ac)
        if not hit:
            battle.log("log.bite.miss", head=head, nat=nat, detail=detail, total=total, ac=ac)
            battle.fx(target.pos, i18n.t("fx.miss"), "miss")
            battle.cue("miss", target.pos)
            return
        res = "crit" if crit else "hit"
        if crit:
            battle.cue("crit", target.pos)
        dice = roll(2, 8) if crit else roll(1, 8)
        char = getattr(actor, "char", actor)
        dmg = max(1, dice + actor.mod_strength + getattr(char, "talent_bonus", lambda _: 0)("melee_damage"))
        battle.log("log.bite.crit" if crit else "log.bite.hit", head=head, nat=nat, detail=detail, total=total, ac=ac, dmg=dmg)
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
    id, cost, target, aimed = "nonlethal", 0, "none", False
    toggle = True

    @classmethod
    def applicable(cls, battle, actor):
        if not battle.lethal:
            return False, i18n.t("action.nonlethal.reason")
        return True, ""

    def label(self, battle, actor):
        return i18n.t("action.nonlethal.label_on" if actor.nonlethal_blows else "action.nonlethal.label_off")

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.nonlethal_blows = not actor.nonlethal_blows
        battle.log("log.nonlethal_on" if actor.nonlethal_blows else "log.nonlethal_off", actor=actor.name)


# --------------------------------------------------------------------------- #
# Tail Sweep                                                                   #
# --------------------------------------------------------------------------- #

class TailSweep(Action):
    """Lizardfolk Tail Sweep: 2 points, the tail sweeps two adjacent foes -- an unarmed strike
    and a shove (`Push.shove`, its own roll) on each. With one foe beside you it sweeps that one."""
    id, cost, target, aimed = "tail_sweep", 2, "enemy", True

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.char.talent_bonus("tail_sweep"):
            return False, i18n.t("action.tail_sweep.reason")
        return True, ""

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor) or not _hostile_target(actor, target):
            return False
        return battle.units_distance(actor, target) <= 1 and battle.los_between(actor, target)

    def label(self, battle, actor):
        return i18n.t("action.tail_sweep.label")

    def highlight_targets(self, battle, actor):
        return [u for u in battle.units if self.can(battle, actor, u)]

    @staticmethod
    def tail(actor):
        """The tail as a weapon: the unarmed die, swung with Strength."""
        return {"name": "Tail", "damage": natural_weapons.get(natural_weapons.DEFAULT, actor.size)["damage"], "crit_mult": 2, "crit_range": 20}

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
                _strike(battle, actor, foe, weapon=tail, prefix=Msg("log.tail_sweep.head", actor=actor.name, foe=foe.name))
        for foe in swept:
            if foe.alive and battle.units_distance(actor, foe) <= 1:
                Push.shove(battle, actor, foe)
