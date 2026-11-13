"""Non-attack actions: pick up, stabilise, capture, potions, racial actions, traps, End Turn."""

import random

from .. import data, draw, i18n, intel, items
from ..board import cells, chebyshev
from ..captives import capture_tool
from ..conditions import Demoralized, PixieFlight
from ..constants import fmt_money
from ..data import d20
from ..ground import GroundObject
from ..i18n import Msg, Ref, plural_key
from .base import Action, _cell_free, _pickable, item_ref

# --------------------------------------------------------------------------- #
# Pick up object                                                               #
# --------------------------------------------------------------------------- #

class PickUp(Action):
    id, cost, target = "pick_up", 1, "none"

    def available(self, battle, actor):
        return (actor.ap >= self.cost
                and any(_pickable(actor, o) for o in battle.ground_in_reach(actor)))

    def label(self, battle, actor):
        return i18n.t("action.pick_up.label")

    def options(self, battle, actor):
        """What the actor can lift now, the order the AI takes it in: `execute` takes any one of these."""
        def _score(o):
            if getattr(o, "is_relic", False) or getattr(o, "is_chest", False):
                return (0, chebyshev(o.pos, actor.pos))
            if actor.unarmed and o.is_weapon:
                return (1, chebyshev(o.pos, actor.pos))
            if o.is_shield or o.is_torch:
                return (2, chebyshev(o.pos, actor.pos))
            return (3, chebyshev(o.pos, actor.pos))
        return sorted(
            (o for o in battle.ground_in_reach(actor) if _pickable(actor, o)),
            key=_score)

    def _drop_on_ground(self, battle, actor, kind, weapon_name=None):
        dest = actor.pos
        if battle.ground_at(dest) is not None:
            for p in battle.board.neighbors(actor.pos):
                if (p not in battle.board.walls and battle.unit_at(p) is None
                        and battle.ground_at(p) is None):
                    dest = p
                    break
        battle.ground.append(GroundObject(kind, dest, weapon_name))
        if kind == GroundObject.TORCH:
            battle.log("log.drops_torch", actor=actor.name, cell=str(dest))
        else:
            battle.log("log.drops", actor=actor.name, item=item_ref(weapon_name), cell=str(dest))

    def execute(self, battle, actor, target=None):
        if actor.ap < self.cost:
            return
        queue = self.options(battle, actor)
        if not queue:
            return
        obj = target if target in queue else queue[0]
        battle.ground.remove(obj)
        actor.ap -= 1
        actor.walking = False

        if obj.is_shield:
            actor.equip_shield(obj.item_name)
            battle.log("log.picks_up", actor=actor.name, item=item_ref(obj.item_name))
        elif obj.is_torch:
            dropped = actor.equip_torch()
            battle.log("log.picks_torch", actor=actor.name, n=data.TORCH_RADIUS)
            for kind, weapon_name in dropped:
                self._drop_on_ground(battle, actor, kind, weapon_name)
        elif getattr(obj, "is_relic", False):
            item_name = getattr(obj, "item_name", "Relic")
            actor.inventory.append(item_name)
            if not hasattr(actor, "picked_up_items"):
                actor.picked_up_items = []
            actor.picked_up_items.append(item_name)
            battle.log("log.retrieves", actor=actor.name, item=item_ref(item_name))
            battle.fx(actor.pos, i18n.t("fx.got", item=item_ref(item_name)), "crit")
        elif getattr(obj, "is_chest", False):
            from .. import loot
            contents = getattr(obj, "contents", [])
            for it in contents:
                amt = loot.parse_currency(it)
                if amt:
                    actor.char.money += amt
                    battle.log("log.chest_money", actor=actor.name, money=fmt_money(amt))
                else:
                    actor.inventory.append(it)
                    if not hasattr(actor, "picked_up_items"):
                        actor.picked_up_items = []
                    actor.picked_up_items.append(it)
                    battle.log("log.chest_item", actor=actor.name, item=item_ref(it))
            battle.fx(actor.pos, i18n.t("fx.chest_opened"), "ok")
        else:
            dropped = actor.equip_weapon(obj.weapon_name)
            battle.log("log.picks_up", actor=actor.name, item=item_ref(obj.weapon_name))
            for kind, weapon_name in dropped:
                self._drop_on_ground(battle, actor, kind, weapon_name)
        battle.scenario.on_pick_up(battle, actor, obj)


class Draw(Action):
    """Take an item from the pack into the hand it fits, or stow what a hand holds (`draw.py`)."""
    id, cost, target = "draw", 1, "none"

    @classmethod
    def applicable(cls, battle, actor):
        if not draw.drawable(actor):
            return False, i18n.t("action.draw.reason")
        return True, ""

    def label(self, battle, actor):
        return i18n.t("action.draw.label")

    def options(self, battle, actor):
        """What the card offers: every drawable kind in the pack, blocked ones with their reason, then the stows."""
        return draw.options(actor)

    def can(self, battle, actor, target=None):
        if not self.available(battle, actor):
            return False
        return target is None or any(o.target == target and o.ok for o in draw.options(actor))

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        target = target or draw.drawable(actor)[0].target
        actor.ap -= self.cost
        actor.walking = False
        back = draw.apply(actor, target)
        if not target.startswith(draw.STOW):
            battle.log("log.draws", actor=actor.name, item=item_ref(target))
        for name in back:
            battle.log("log.stows", actor=actor.name, item=item_ref(name))


# --------------------------------------------------------------------------- #
# Stabilize a downed ally                                                      #
# --------------------------------------------------------------------------- #

class Stabilize(Action):
    id, cost, target, aimed = "stabilize", 1, "ally", True

    def _downed_allies(self, battle, actor):
        """Adjacent allied bodies this action can work on: dying units, or broken
        automatons (repaired with an INT check instead of a death save)."""
        return [u for u in battle.units
                if (u.dying or u.broken) and u.team == actor.team and u is not actor
                and battle.units_distance(actor, u) <= 1]

    def available(self, battle, actor):
        return actor.ap >= self.cost and bool(self._downed_allies(battle, actor))

    def can(self, battle, actor, target=None):
        return (actor.ap >= self.cost and target is not None
                and target in self._downed_allies(battle, actor))

    def label(self, battle, actor):
        return i18n.t("action.stabilize.label", dc=data.AUTOMATON_REPAIR_DC)

    def highlight_targets(self, battle, actor):
        return self._downed_allies(battle, actor)

    def _attempt(self, battle, actor, target):
        """Stabilize a dying ally (death save) or repair a broken automaton
        (d20 + INT vs DC). Returns True on success."""
        if target.broken:
            nat = d20()
            total = nat + actor.mod_intelligence
            ok = total >= data.AUTOMATON_REPAIR_DC
            battle.rolled(actor, target, nat, actor.mod_intelligence, total, "dc", str(data.AUTOMATON_REPAIR_DC), ok)
            battle.log("log.repair.ok" if ok else "log.repair.fail", actor=actor.name, target=target.name, nat=nat,
                       int=actor.mod_intelligence, total=total, dc=data.AUTOMATON_REPAIR_DC)
            if ok:
                battle.repair(target)
            return ok
        nat = d20()
        ok = nat >= data.DEATH_SAVE_MIN
        battle.rolled(actor, target, nat, 0, nat, "dc", str(data.DEATH_SAVE_MIN), ok)
        battle.log("log.stabilize.ok" if ok else "log.stabilize.fail", actor=actor.name, target=target.name, nat=nat)
        battle.fx(target.pos, i18n.t("fx.stabilize_ok" if ok else "fx.stabilize_fail", nat=nat), "ok" if ok else "faint")
        if ok:
            battle.stabilize(target)
        return ok

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        self._attempt(battle, actor, target)


class FirstAid(Stabilize):
    id, cost, target, aimed = "first_aid", 1, "ally", True

    def _downed_allies(self, battle, actor):
        # a med kit is for the dying and the sick; a broken automaton needs the plain Stabilize
        return [u for u in battle.units
                if (u.dying or getattr(u.char, "sick", False)) and u.team == actor.team and u is not actor
                and battle.units_distance(actor, u) <= 1]

    def available(self, battle, actor):
        return actor.first_aid_charges > 0 and super().available(battle, actor)

    def can(self, battle, actor, target=None):
        return actor.first_aid_charges > 0 and super().can(battle, actor, target)

    def label(self, battle, actor):
        return i18n.plural("action.first_aid.label", actor.first_aid_charges, dc=data.FIRST_AID_DC)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        actor.first_aid_charges -= 1
        nat = d20()
        total = nat + actor.mod_wisdom
        ok = total >= data.FIRST_AID_DC
        target_sick = getattr(target.char, "sick", False)
        target_dying = target.dying
        battle.rolled(actor, target, nat, actor.mod_wisdom, total, "dc", str(data.FIRST_AID_DC), ok)

        battle.log(plural_key("log.first_aid.ok" if ok else "log.first_aid.fail", actor.first_aid_charges),
                   actor=actor.name, target=target.name, nat=nat, wis=actor.mod_wisdom, total=total,
                   dc=data.FIRST_AID_DC, n=actor.first_aid_charges)
        if ok:
            if target_dying:
                battle.stabilize(target)
            if target_sick:
                target.char.sick = False
                battle.log("log.cured", target=target.name)
                target.char._derive_combat()
                target.hp_max = target.char.hp_max
                target.hp = min(target.hp, target.hp_max)


class DrinkPotion(Action):
    id, cost, target, aimed = "drink_potion", 1, "ally", True

    def _targets(self, battle, actor):
        # Can target self or adjacent ally, if missing HP.
        return [u for u in battle.units
                if u.team == actor.team and u.hp < u.hp_max and not getattr(u, "broken", False)
                and battle.units_distance(actor, u) <= 1]

    def _has_potion(self, actor):
        if hasattr(actor, "inventory") and "Minor Healing Potion" in actor.inventory:
            return True
        return actor.has_item("Minor Healing Potion")

    @classmethod
    def applicable(cls, battle, actor):
        has = (hasattr(actor, "inventory") and "Minor Healing Potion" in actor.inventory) or actor.has_item("Minor Healing Potion")
        if not has:
            return False, i18n.t("action.drink_potion.reason", potion=item_ref("Minor Healing Potion"))
        return True, ""

    def available(self, battle, actor):
        return self._has_potion(actor) and actor.ap >= self.cost and bool(self._targets(battle, actor))

    def can(self, battle, actor, target=None):
        return (self._has_potion(actor) and actor.ap >= self.cost
                and target is not None and target in self._targets(battle, actor))

    def label(self, battle, actor):
        n = actor.inventory.count("Minor Healing Potion") if hasattr(actor, "inventory") else actor.count_of("Minor Healing Potion")
        return i18n.t("action.drink_potion.label", n=n)

    def highlight_targets(self, battle, actor):
        return self._targets(battle, actor)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        actor.remove_named("Minor Healing Potion")
        if hasattr(actor, "inventory") and isinstance(actor.inventory, list) and "Minor Healing Potion" in actor.inventory:
            actor.inventory.remove("Minor Healing Potion")
        
        heal = random.randint(1, 6)
        target.hp = min(target.hp_max, target.hp + heal)
        revived = target.dying or target.stable
        if revived:
            target.status, target.death_clock = "up", 0

        if actor == target:
            key = "log.potion.drinks_up" if revived else "log.potion.drinks"
        else:
            key = "log.potion.feeds_up" if revived else "log.potion.feeds"
        battle.log(key, actor=actor.name, target=target.name,
                   potion=item_ref("Minor Healing Potion"), heal=heal)
        battle.fx(target.pos, i18n.t("fx.heal", heal=heal), "ok")


# --------------------------------------------------------------------------- #
# Racial Actions                                                               #
# --------------------------------------------------------------------------- #

class EatCorpse(Action):
    id, cost, target, aimed = "eat_corpse", 1, "enemy", True

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.char.has_talent("corpse_eater"):
            return False, i18n.t("action.eat_corpse.reason")
        return True, ""

    def available(self, battle, actor):
        if not super().available(battle, actor) or getattr(actor, "mounted_on", None) is not None:
            return False
        if not actor.char.has_talent("corpse_eater"):
            return False
        for u in battle.units:
            if u.team != actor.team and u.dead and getattr(u, "eaten", False) is False and battle.units_distance(u, actor) <= 1:
                return True
        return False

    def can(self, battle, actor, target=None):
        return (super().can(battle, actor, target) and target is not None 
                and target.team != actor.team and target.dead 
                and battle.units_distance(target, actor) <= 1
                and getattr(target, "eaten", False) is False)

    def highlight_targets(self, battle, actor):
        return [u for u in battle.units if self.can(battle, actor, u)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        target.eaten = True
        actor.char.unfed_days = 0
        battle.log("log.eat_corpse", actor=actor.name, target=target.name)
        
        nat = d20()
        bonus = max(actor.mod_strength, actor.mod_charisma)
        total = nat + bonus
        battle.log("log.feast", nat=nat, bonus=bonus, total=total)
        
        for u in battle.units:
            if u.team != actor.team and u.alive and battle.can_see_unit(u, actor):
                md = u.mental_defense
                battle.rolled(actor, u, nat, bonus, total, "md", intel.shown(battle, u, "md", md), total >= md)
                if total >= md:
                    u.add_condition(Demoralized())
                    battle.log("log.feast_terrified", target=u.name, md=intel.shown(battle, u, "md", md))
                else:
                    battle.log("log.feast_resists", target=u.name, md=intel.shown(battle, u, "md", md))


class SpinWeb(Action):
    id, cost, target, aimed = "spin_web", 1, "cell", True

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.char.has_talent("spin_web"):
            return False, i18n.t("action.spin_web.reason")
        return True, ""

    def _legal(self, battle, actor, anchor):
        """The web's footprint (the spider's own size) must sit wholly on open
        ground right up against the spider -- no walls, bodies, deep water or
        anything already lying there."""
        area = cells(anchor, actor.footprint)
        mine = battle.cells_of(actor)
        if not all(battle.board.in_bounds(c) for c in area):
            return False
        blocked = battle.board.walls | battle.occupied() | battle.creature_cells()
        if blocked.intersection(area):
            return False
        if any(battle.board.is_deep_water(c) or battle.ground_at(c) for c in area):
            return False
        return min(chebyshev(a, m) for a in area for m in mine) <= 1

    def available(self, battle, actor):
        return (super().available(battle, actor)
                and getattr(actor, "mounted_on", None) is None
                and bool(self.highlight_cells(battle, actor)))

    def can(self, battle, actor, target=None):
        return (super().available(battle, actor) and target is not None
                and self._legal(battle, actor, target))

    def highlight_cells(self, battle, actor):
        reach = actor.footprint + 1
        x0, y0 = actor.pos
        return [(x, y) for x in range(x0 - reach, x0 + reach + 1)
                for y in range(y0 - reach, y0 + reach + 1)
                if self._legal(battle, actor, (x, y))]

    def highlight_targets(self, battle, actor):
        return []

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        battle.plant_web(actor, target)
        n = actor.footprint
        battle.log("log.spin_web", actor=actor.name, n=n)
        battle.fx(target, i18n.t("fx.web"), "ok")


class Mount(Action):
    id, cost, target, aimed = "mount", 1, "ally", True

    @classmethod
    def applicable(cls, battle, actor):
        if getattr(actor, "mounted_on", None) is not None:
            return False, i18n.t("action.mount.reason_mounted")
        if actor.size not in ("Small", "Medium"):
            return False, i18n.t("action.mount.reason_large")
        has_mount = any(u.alive and u.team == actor.team and u is not actor and u.char.has_talent("centaur_mount") for u in battle.units)
        if not has_mount:
            return False, i18n.t("action.mount.reason_none")
        return True, ""

    def available(self, battle, actor):
        if not super().available(battle, actor):
            return False
        if getattr(actor, "mounted_on", None) is not None or actor.size not in ("Small", "Medium"):
            return False
        for u in battle.units:
            if u.alive and u.team == actor.team and u is not actor and u.char.has_talent("centaur_mount") and not getattr(u, "rider", None) and battle.units_distance(actor, u) <= 1:
                return True
        return False

    def can(self, battle, actor, target=None):
        return (super().can(battle, actor, target) and target is not None
                and target.alive and target.team == actor.team and target is not actor
                and target.char.has_talent("centaur_mount") and not getattr(target, "rider", None)
                and battle.units_distance(actor, target) <= 1)

    def highlight_targets(self, battle, actor):
        return [u for u in battle.units if self.can(battle, actor, u)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        actor.mounted_on = target
        target.rider = actor
        actor.pos = target.pos
        battle.log("log.mounts", actor=actor.name, target=target.name)


class LiftRider(Action):
    """Centaur Lift Rider: the centaur swings an adjacent ally onto its back, standing or
    fallen -- the way a body is carried off. A rider who is up climbs down with Dismount."""
    id, cost, target, aimed = "lift_rider", 1, "ally", True

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.char.talent_bonus("lift_rider"):
            return False, i18n.t("action.lift_rider.reason")
        return True, ""

    def available(self, battle, actor):
        return (super().available(battle, actor) and actor.rider is None
                and any(self.can(battle, actor, u) for u in battle.units))

    def can(self, battle, actor, target=None):
        return (actor.ap >= self.cost and actor.char.talent_bonus("lift_rider") and actor.alive
                and actor.rider is None and actor.mounted_on is None
                and target is not None and target is not actor and target.team == actor.team
                and (target.alive or target.downed) and not target.captured
                and target.size in ("Small", "Medium")
                and target.mounted_on is None and target.rider is None
                and battle.units_distance(actor, target) <= 1)

    def highlight_targets(self, battle, actor):
        return [u for u in battle.units if self.can(battle, actor, u)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        target.mounted_on = actor
        actor.rider = target
        target.pos = actor.pos
        target.z = actor.z
        battle.log("log.lift_fallen" if target.downed else "log.lift", actor=actor.name, target=target.name)


class PixieDust(Action):
    """Sprite Pixie Dust: an adjacent ally flies through the end of their next turn -- over pits
    and deep water, with no fall."""
    id, cost, target, aimed = "pixie_dust", 1, "ally", True

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.char.talent_bonus("pixie_dust"):
            return False, i18n.t("action.pixie_dust.reason")
        return True, ""

    def available(self, battle, actor):
        return super().available(battle, actor) and any(self.can(battle, actor, u) for u in battle.units)

    def can(self, battle, actor, target=None):
        return (actor.ap >= self.cost and actor.char.talent_bonus("pixie_dust")
                and target is not None and target is not actor and target.alive
                and target.team == actor.team and not target.flies
                and battle.units_distance(actor, target) <= 1)

    def highlight_targets(self, battle, actor):
        return [u for u in battle.units if self.can(battle, actor, u)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        target.add_condition(PixieFlight())
        battle.log("log.pixie_dust", actor=actor.name, target=target.name)


class Dismount(Action):
    id, cost, target, aimed = "dismount", 1, "cell", True

    @classmethod
    def applicable(cls, battle, actor):
        if getattr(actor, "mounted_on", None) is None:
            return False, i18n.t("action.dismount.reason")
        return True, ""

    def available(self, battle, actor):
        return super().available(battle, actor) and getattr(actor, "mounted_on", None) is not None

    def can(self, battle, actor, target=None):
        if not super().can(battle, actor, target):
            return False
        if getattr(actor, "mounted_on", None) is None or target is None:
            return False
        return target in self.highlight_cells(battle, actor)

    def highlight_cells(self, battle, actor):
        """The free cells around the mount's whole body, never one under it."""
        mount = getattr(actor, "mounted_on", None)
        if not mount:
            return []
        body = set(battle.cells_of(mount))
        around = {n for c in body for n in battle.board.neighbors(c)} - body
        return sorted(c for c in around if _cell_free(battle, actor, c))

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        mount = actor.mounted_on
        actor.mounted_on = None
        mount.rider = None
        actor.pos = target
        battle.log("log.dismounts", actor=actor.name, cell=str(target))

class WakeUp(Action):
    id, cost, target, aimed = "wake_up", 1, "ally", True

    @classmethod
    def applicable(cls, battle, actor):
        has_sleeping = any(u.alive and u.team == actor.team and u.has_condition("sleeping") for u in battle.units)
        if not has_sleeping:
            return False, i18n.t("action.wake_up.reason")
        return True, ""

    def _sleeping_allies(self, battle, actor):
        return [u for u in battle.units
                if u.alive and u.team == actor.team and u is not actor
                and u.has_condition("sleeping")
                and battle.units_distance(actor, u) <= 1]

    def available(self, battle, actor):
        return actor.ap >= self.cost and bool(self._sleeping_allies(battle, actor))

    def can(self, battle, actor, target=None):
        return (actor.ap >= self.cost and target is not None
                and target in self._sleeping_allies(battle, actor))

    def label(self, battle, actor):
        return i18n.t("action.wake_up.label")

    def highlight_targets(self, battle, actor):
        return self._sleeping_allies(battle, actor)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        
        sleeping_cond = next((c for c in target.conditions if c.id == "sleeping"), None)
        if sleeping_cond:
            target.conditions.remove(sleeping_cond)
        
        battle.log("log.wake_up", actor=actor.name, target=target.name)


# --------------------------------------------------------------------------- #
# End turn                                                                     #
# --------------------------------------------------------------------------- #

class EndTurn(Action):
    id, cost, target = "end", 0, "none"
    announce = False

    def available(self, battle, actor):
        return battle.winner is None

    def execute(self, battle, actor, target=None):
        battle.end_turn()


class Delay(Action):
    id, cost, target = "delay", 0, "none"
    announce = False

    @classmethod
    def applicable(cls, battle, actor):
        why = battle.delay_block(actor)
        return not why, why

    def execute(self, battle, actor, target=None):
        if self.available(battle, actor):
            battle.delay_turn(actor)

    def label(self, battle, actor):
        return i18n.t("action.delay.label")


class SignalHorn(Action):
    id, cost, target = "signal_horn", 2, "none"
    RADIUS = 10
    BONUS = 2
    desc = i18n.Text("action", "desc", radius=RADIUS, bonus=BONUS)

    @classmethod
    def applicable(cls, battle, actor):
        if actor.artifact_name != items.SIGNAL_HORN_ITEM:
            return False, i18n.t("action.signal_horn.reason_none")
        if "signal_horn" in actor.used_abilities:
            return False, i18n.t("action.signal_horn.reason_used")
        return True, ""

    def allies_in_range(self, battle, actor):
        return [u for u in battle.units
                if u.alive and u.team == actor.team and u is not actor
                and battle.units_distance(actor, u) <= self.RADIUS]

    def available(self, battle, actor):
        return super().available(battle, actor) and bool(self.allies_in_range(battle, actor))

    def label(self, battle, actor):
        return i18n.t("action.signal_horn.label", cost=self.cost, radius=self.RADIUS, bonus=self.BONUS)

    def execute(self, battle, actor, target=None):
        if not self.available(battle, actor):
            return
        actor.ap -= self.cost
        actor.walking = False
        actor.spend_once("signal_horn")
        allies = self.allies_in_range(battle, actor)
        battle.raise_initiative(allies, self.BONUS)
        battle.fx(actor.pos, i18n.t("fx.signal_horn"), "crit")
        battle.log("log.signal_horn", actor=actor.name, allies=", ".join(a.name for a in allies), n=self.BONUS)


class Assess(Action):
    id, cost, target, aimed = "assess", 1, "enemy", True
    desc = i18n.Text("action", "desc", bonus=intel.ASSESS_BONUS)

    def can(self, battle, actor, target=None):
        return actor.ap >= self.cost and not intel.assess_block(battle, actor, target)

    def label(self, battle, actor):
        return i18n.t("action.assess.label")

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        total, _margin, opened = intel.assess(battle, actor, target)
        need = intel.dc(battle, actor.team, target)
        learned = ", ".join(intel.label(f) for f in opened) or Msg("log.assess_nothing")
        battle.log("log.assess", actor=actor.name, target=target.name, bonus=intel.ASSESS_BONUS, total=total,
                   dc=need, learned=learned)


class Investigate(Action):
    """Look around: an adjacent secret wall opens, and a foe nobody can see within `RADIUS` is
    found on d20 + WIS against 10 + its INT (its side then sees it until it slips away)."""
    id, cost, target = "investigate", 1, "none"
    RADIUS = 3

    def _adjacent_secrets(self, battle, actor):
        secrets = getattr(battle, "secret_walls", set())
        return [p for p in secrets if chebyshev(actor.pos, p) <= 1]

    @staticmethod
    def _lurkers(battle, actor):
        return [u for u in battle.units if u.alive and u.hidden_from(actor.team)]

    def available(self, battle, actor):
        return actor.ap >= self.cost and bool(self._adjacent_secrets(battle, actor)
                                              or self._lurkers(battle, actor))

    def label(self, battle, actor):
        if self._adjacent_secrets(battle, actor):
            return i18n.t("action.investigate.label_secret")
        return i18n.t("action.investigate.label", n=self.RADIUS)

    def execute(self, battle, actor, target=None):
        if not self.available(battle, actor):
            return
        actor.ap -= self.cost
        actor.walking = False
        secrets = self._adjacent_secrets(battle, actor)
        for p in secrets:
            battle.board.walls.discard(p)
            battle.secret_walls.discard(p)
            battle.log("log.secret_door", actor=actor.name, cell=str(p))
            battle.fx(p, i18n.t("fx.secret_opened"), "crit")
        lurkers = self._lurkers(battle, actor)
        if not lurkers:
            return
        found = False
        for u in lurkers:
            if battle.units_distance(actor, u) > self.RADIUS:
                continue
            nat = d20()
            total, dc = nat + actor.mod_wisdom, 10 + u.mod_intelligence
            battle.rolled(actor, u, nat, actor.mod_wisdom, total, "dc", "?", total >= dc)
            if total >= dc:
                u.reveal_to(actor.team)
                found = True
                battle.log("log.finds_hiding", actor=actor.name, target=u.name, cell=str(u.pos))
                battle.fx(u.pos, i18n.t("fx.found"), "crit")
        if not found and not secrets:
            battle.log("log.finds_nothing", actor=actor.name)


class Disarm(Action):
    id, cost, target = "disarm", 1, "none"

    def _adjacent_traps(self, battle, actor):
        return [o for o in battle.ground if o.is_trap and chebyshev(actor.pos, o.pos) <= 1]

    def available(self, battle, actor):
        return actor.ap >= self.cost and bool(self._adjacent_traps(battle, actor))

    def label(self, battle, actor):
        return i18n.t("action.disarm.label")

    def execute(self, battle, actor, target=None):
        if not self.available(battle, actor):
            return
        traps = self._adjacent_traps(battle, actor)
        if not traps:
            return
        trap = traps[0]
        actor.ap -= self.cost
        actor.walking = False
        nat = d20()
        bonus = actor.mod_dexterity
        total = nat + bonus
        dc = 12
        ok = total >= dc
        battle.rolled(actor, trap.pos, nat, bonus, total, "dc", str(dc), ok)
        kind = Ref("trap", trap.trap_type, trap.trap_type)
        battle.log("log.disarm.ok" if ok else "log.disarm.fail", actor=actor.name, trap=kind, nat=nat, dex=bonus,
                   total=total, dc=dc)
        if ok and trap.trap_type == "web":
            battle.remove_web(trap)
            battle.log("log.disarm.web", actor=actor.name)
            battle.fx(trap.pos, i18n.t("fx.web_cleared"), "ok")
        elif ok:
            battle.ground.remove(trap)
            trap_name = "Bear Trap" if "bear" in trap.trap_type.lower() else "Alarm Trap"
            actor.inventory.append(trap_name)
            if not hasattr(actor, "picked_up_items"):
                actor.picked_up_items = []
            actor.picked_up_items.append(trap_name)
            battle.log("log.disarm.recovered", actor=actor.name, trap=kind, item=item_ref(trap_name))
            battle.fx(trap.pos, i18n.t("fx.trap_disarmed"), "ok")
        elif nat == 1 or total <= dc - 5:
            battle.log("log.disarm.fumble", actor=actor.name)
            battle.trigger_trap(actor, trap)


# --------------------------------------------------------------------------- #
# Capture                                                                      #
# --------------------------------------------------------------------------- #

class Capture(Action):
    """Bind an adjacent fallen foe (dying or knocked out) with a Rope or Chains, used up. The
    captive is out of the fight for good: no coup de grace, no death save; after a won battle
    it joins the group as a captured unit (`captives.py`)."""
    id, cost, target, aimed = "capture", 1, "enemy", True

    @classmethod
    def applicable(cls, battle, actor):
        if capture_tool(actor) is None:
            return False, i18n.t("action.capture.reason")
        return True, ""

    def _bodies(self, battle, actor):
        return [u for u in battle.units
                if u.team != actor.team and u.status in ("dying", "stable", "broken")
                and not u.captured and battle.units_distance(actor, u) <= 1]

    def available(self, battle, actor):
        return super().available(battle, actor) and bool(self._bodies(battle, actor))

    def can(self, battle, actor, target=None):
        return super().available(battle, actor) and target in self._bodies(battle, actor)

    def highlight_targets(self, battle, actor):
        return self._bodies(battle, actor) if super().available(battle, actor) else []

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        tool = capture_tool(actor)
        actor.inventory.remove(tool)
        actor.capture_tools_used.append(tool)
        target.captured = True
        if target.status == "dying":
            target.status = "stable"
        battle.log("log.capture", actor=actor.name, target=target.name, tool=item_ref(tool))
        battle.fx(target.pos, i18n.t("fx.captured"), "ok")
