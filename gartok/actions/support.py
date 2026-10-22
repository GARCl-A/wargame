"""Non-attack actions: pick up, stabilise, capture, potions, racial actions, traps, End Turn."""

import random

from .. import data, intel, items
from ..board import cells, chebyshev
from ..captives import capture_tool
from ..conditions import Demoralized, PixieFlight
from ..constants import fmt_money
from ..data import d20
from ..ground import GroundObject
from .base import Action, _cell_free, _pickable

# --------------------------------------------------------------------------- #
# Pick up object                                                               #
# --------------------------------------------------------------------------- #

class PickUp(Action):
    id, name, cost, target = "pick_up", "Pick up", 1, "none"
    desc = "Pick up a dropped item or torch in your cell."

    def available(self, battle, actor):
        return (actor.ap >= self.cost
                and any(_pickable(actor, o) for o in battle.ground_in_reach(actor)))

    def label(self, battle, actor):
        return "Pick up / swap object (1 pt)"

    def _queue(self, battle, actor):
        def _score(o):
            if getattr(o, "is_relic", False) or getattr(o, "is_chest", False):
                return (0, chebyshev(o.pos, actor.pos))
            if actor.unarmed and o.is_weapon:
                return (1, chebyshev(o.pos, actor.pos))
            if o.is_torch:
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
        battle.log(f"  {actor.name} drops {'the torch' if kind == GroundObject.TORCH else weapon_name} at {dest}.")

    def execute(self, battle, actor, target=None):
        if actor.ap < self.cost:
            return
        queue = self._queue(battle, actor)
        if not queue:
            return
        obj = queue[0]
        battle.ground.remove(obj)
        actor.ap -= 1
        actor.walking = False

        if obj.is_torch:
            dropped = actor.equip_torch()
            battle.log(f"{actor.name} picks up a torch (lights {data.TORCH_RADIUS} squares).")
            for kind, weapon_name in dropped:
                self._drop_on_ground(battle, actor, kind, weapon_name)
        elif getattr(obj, "is_relic", False):
            item_name = getattr(obj, "item_name", "Relic")
            actor.inventory.append(item_name)
            if not hasattr(actor, "picked_up_items"):
                actor.picked_up_items = []
            actor.picked_up_items.append(item_name)
            battle.log(f"{actor.name} retrieves the {item_name}!")
            battle.fx(actor.pos, f"Got {item_name}!", "crit")
        elif getattr(obj, "is_chest", False):
            from .. import loot
            contents = getattr(obj, "contents", [])
            for it in contents:
                amt = loot.parse_currency(it)
                if amt:
                    actor.char.money += amt
                    battle.log(f"{actor.name} finds {fmt_money(amt)} in the chest!")
                else:
                    actor.inventory.append(it)
                    if not hasattr(actor, "picked_up_items"):
                        actor.picked_up_items = []
                    actor.picked_up_items.append(it)
                    battle.log(f"{actor.name} recovers {it} from the chest!")
            battle.fx(actor.pos, "Chest Opened!", "ok")
        else:
            dropped = actor.equip_weapon(obj.weapon_name)
            battle.log(f"{actor.name} picks up {obj.weapon_name} from the ground.")
            for kind, weapon_name in dropped:
                self._drop_on_ground(battle, actor, kind, weapon_name)
        battle.scenario.on_pick_up(battle, actor, obj)


# --------------------------------------------------------------------------- #
# Stabilize a downed ally                                                      #
# --------------------------------------------------------------------------- #

class Stabilize(Action):
    id, name, cost, target, aimed = "stabilize", "Stabilize", 1, "ally", True
    desc = "50% chance to stabilize an adjacent dying ally."

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
        return (f"Stabilize a downed ally (1 pt: 50%, or repair automaton "
                f"INT vs {data.AUTOMATON_REPAIR_DC})")

    def highlight_targets(self, battle, actor):
        return self._downed_allies(battle, actor)

    def _attempt(self, battle, actor, target):
        """Stabilize a dying ally (death save) or repair a broken automaton
        (d20 + INT vs DC). Returns True on success."""
        if target.broken:
            nat = d20()
            total = nat + actor.mod_intelligence
            ok = total >= data.AUTOMATON_REPAIR_DC
            battle.log(f"{actor.name} tries to repair {target.name}: "
                       f"d20({nat}) {actor.mod_intelligence:+}(INT) = {total} vs "
                       f"{data.AUTOMATON_REPAIR_DC} -> "
                       + ("repaired." if ok else "fails."))
            battle.fx(target.pos, f"{total} vs {data.AUTOMATON_REPAIR_DC}", "ok" if ok else "faint")
            if ok:
                battle.repair(target)
            return ok
        nat = d20()
        ok = nat >= data.DEATH_SAVE_MIN
        battle.log(f"{actor.name} tries to stabilize {target.name}: d20({nat}) -> "
                   + ("success." if ok else "fails."))
        battle.fx(target.pos, f"d20({nat}) " + ("Success" if ok else "Fail"), "ok" if ok else "faint")
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
    id, name, cost, target, aimed = "first_aid", "First Aid", 1, "ally", True
    desc = "Use a medkit: 100% chance to stabilize, or cure sickness."

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
        return (f"First Aid (1 pt, WIS vs {data.FIRST_AID_DC}, "
                f"{actor.first_aid_charges} charges)")

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

        battle.log(f"{actor.name} uses the kit on {target.name}: "
                   f"d20({nat}) {actor.mod_wisdom:+}(WIS) = {total} vs {data.FIRST_AID_DC} -> "
                   + ("success." if ok else "fails.")
                   + f"  ({actor.first_aid_charges} charge(s))")
        if ok:
            if target_dying:
                battle.stabilize(target)
            if target_sick:
                target.char.sick = False
                battle.log(f"  {target.name} is cured of their sickness!")
                target.char._derive_combat()
                target.hp_max = target.char.hp_max
                target.hp = min(target.hp, target.hp_max)


class DrinkPotion(Action):
    id, name, cost, target, aimed = "drink_potion", "Drink Potion", 1, "ally", True
    desc = "Drink a Minor Healing Potion or feed it to an adjacent ally (heals 1d6 HP)."

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
            return False, "No Minor Healing Potion."
        return True, ""

    def available(self, battle, actor):
        return self._has_potion(actor) and actor.ap >= self.cost and bool(self._targets(battle, actor))

    def can(self, battle, actor, target=None):
        return (self._has_potion(actor) and actor.ap >= self.cost
                and target is not None and target in self._targets(battle, actor))

    def label(self, battle, actor):
        n = actor.inventory.count("Minor Healing Potion") if hasattr(actor, "inventory") else actor.count_of("Minor Healing Potion")
        return f"Drink Potion (1 pt, {n} in pack)"

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

        verb = "drinks" if actor == target else f"feeds {target.name}"
        battle.log(f"{actor.name} {verb} a Minor Healing Potion, recovering {heal} HP"
                   + (" -- back on their feet." if revived else "."))
        battle.fx(target.pos, f"+{heal} HP", "ok")


# --------------------------------------------------------------------------- #
# Racial Actions                                                               #
# --------------------------------------------------------------------------- #

class EatCorpse(Action):
    id, name, cost, target, aimed = "eat_corpse", "Eat Corpse", 1, "enemy", True
    desc = "Devour a corpse to reset hunger and terrify foes."

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.char.has_talent("corpse_eater"):
            return False, "Missing 'corpse_eater' talent."
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
        battle.log(f"{actor.name} devours {target.name}'s corpse (hunger reset to 0).")
        
        nat = d20()
        bonus = max(actor.mod_strength, actor.mod_charisma)
        total = nat + bonus
        battle.log(f"  Terrifying feast: d20({nat}) {bonus:+} = {total} (AoE Demoralize)")
        
        for u in battle.units:
            if u.team != actor.team and u.alive and battle.can_see_unit(u, actor):
                md = u.mental_defense
                if total >= md:
                    u.add_condition(Demoralized())
                    battle.log(f"    {u.name} (MD {intel.shown(battle, u, 'md', md)}) is terrified -> DEMORALIZED.")
                else:
                    battle.log(f"    {u.name} (MD {intel.shown(battle, u, 'md', md)}) resists the horror.")


class SpinWeb(Action):
    id, name, cost, target, aimed = "spin_web", "Spin Web", 1, "cell", True
    desc = "Spin a web trap beside you, as wide as your own body."

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.char.has_talent("spin_web"):
            return False, "Missing 'spin_web' talent."
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
        battle.log(f"{actor.name} spins a {n}x{n} web.")
        battle.fx(target, "Web!", "ok")


class Mount(Action):
    id, name, cost, target, aimed = "mount", "Mount", 1, "ally", True
    desc = "Mount an allied centaur."

    @classmethod
    def applicable(cls, battle, actor):
        if getattr(actor, "mounted_on", None) is not None:
            return False, "Already mounted."
        if actor.size not in ("Small", "Medium"):
            return False, "Too large to ride a mount."
        has_mount = any(u.alive and u.team == actor.team and u is not actor and u.char.has_talent("centaur_mount") for u in battle.units)
        if not has_mount:
            return False, "No mount in squad."
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
        battle.log(f"{actor.name} mounts {target.name}.")


class LiftRider(Action):
    """Centaur Lift Rider: the centaur swings an adjacent ally onto its back, standing or
    fallen -- the way a body is carried off. A rider who is up climbs down with Dismount."""
    id, name, cost, target, aimed = "lift_rider", "Lift Rider", 1, "ally", True
    desc = "Put an adjacent Small or Medium ally, awake or fallen, on your back."

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.char.talent_bonus("lift_rider"):
            return False, "Missing 'lift_rider' talent."
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
        how = "hauls the fallen" if target.downed else "swings"
        battle.log(f"{actor.name} {how} {target.name} onto their back.")


class PixieDust(Action):
    """Sprite Pixie Dust: an adjacent ally flies through the end of their next turn -- over pits
    and deep water, with no fall."""
    id, name, cost, target, aimed = "pixie_dust", "Pixie Dust", 1, "ally", True
    desc = "An adjacent ally takes wing through the end of their next turn."

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.char.talent_bonus("pixie_dust"):
            return False, "Missing 'pixie_dust' talent."
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
        battle.log(f"{actor.name} showers {target.name} in pixie dust: they take wing.")


class Dismount(Action):
    id, name, cost, target, aimed = "dismount", "Dismount", 1, "cell", True
    desc = "Dismount from your current mount."

    @classmethod
    def applicable(cls, battle, actor):
        if getattr(actor, "mounted_on", None) is None:
            return False, "Not currently mounted."
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
        battle.log(f"{actor.name} dismounts to {target}.")

class WakeUp(Action):
    id, name, cost, target, aimed = "wake_up", "Wake Up", 1, "ally", True
    desc = "Wake up an adjacent sleeping ally."

    @classmethod
    def applicable(cls, battle, actor):
        has_sleeping = any(u.alive and u.team == actor.team and u.has_condition("sleeping") for u in battle.units)
        if not has_sleeping:
            return False, "No sleeping allies."
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
        return "Wake Up (1 pt, wake a sleeping ally)"

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
        
        battle.log(f"{actor.name} shakes {target.name} awake!")


# --------------------------------------------------------------------------- #
# End turn                                                                     #
# --------------------------------------------------------------------------- #

class EndTurn(Action):
    id, name, cost, target = "end", "End Turn", 0, "none"
    announce = False
    desc = "End your turn."

    def available(self, battle, actor):
        return battle.winner is None

    def execute(self, battle, actor, target=None):
        battle.end_turn()


class Delay(Action):
    id, name, cost, target = "delay", "Delay", 0, "none"
    announce = False
    desc = "Drop to the end of the initiative order, once per round. Only before you spend any points."

    @classmethod
    def applicable(cls, battle, actor):
        why = battle.delay_block(actor)
        return not why, why

    def execute(self, battle, actor, target=None):
        if self.available(battle, actor):
            battle.delay_turn(actor)


class SignalHorn(Action):
    id, name, cost, target = "signal_horn", "Signal Horn", 2, "none"
    RADIUS = 10
    BONUS = 2
    desc = (f"Blow the horn, once per battle: allies within {RADIUS} squares gain +{BONUS} "
            "initiative, which can reorder the turns.")

    @classmethod
    def applicable(cls, battle, actor):
        if actor.artifact_name != items.SIGNAL_HORN_ITEM:
            return False, "No Signal Horn equipped."
        if "signal_horn" in actor.used_abilities:
            return False, "Already blown this battle."
        return True, ""

    def allies_in_range(self, battle, actor):
        return [u for u in battle.units
                if u.alive and u.team == actor.team and u is not actor
                and battle.units_distance(actor, u) <= self.RADIUS]

    def available(self, battle, actor):
        return super().available(battle, actor) and bool(self.allies_in_range(battle, actor))

    def label(self, battle, actor):
        return f"Signal Horn ({self.cost} pts, allies within {self.RADIUS} +{self.BONUS} initiative)"

    def execute(self, battle, actor, target=None):
        if not self.available(battle, actor):
            return
        actor.ap -= self.cost
        actor.walking = False
        actor.spend_once("signal_horn")
        allies = self.allies_in_range(battle, actor)
        battle.raise_initiative(allies, self.BONUS)
        battle.fx(actor.pos, "Signal Horn!", "crit")
        battle.log(f"{actor.name} blows the Signal Horn! "
                   + ", ".join(a.name for a in allies) + f" gain +{self.BONUS} initiative.")


class Assess(Action):
    id, name, cost, target, aimed = "assess", "Assess", 1, "enemy", True
    desc = (f"INT +{intel.ASSESS_BONUS} against the foe's DC: learn more of its stats. "
            "One foe in sight, once per foe each round.")

    def can(self, battle, actor, target=None):
        return actor.ap >= self.cost and not intel.assess_block(battle, actor, target)

    def label(self, battle, actor):
        return "Assess (1 pt, INT vs the foe)"

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        total, _margin, opened = intel.assess(battle, actor, target)
        need = intel.dc(battle, actor.team, target)
        learned = ", ".join(intel.LABELS[f] for f in opened) or "nothing new"
        battle.log(f"{actor.name} studies {target.name}: d20 + INT + {intel.ASSESS_BONUS} = {total} "
                   f"vs DC {need}  -> {learned}.")
        battle.fx(target.pos, f"{total} vs DC {need}", "ok" if opened else "faint")


class Investigate(Action):
    """Look around: an adjacent secret wall opens, and a foe nobody can see within `RADIUS` is
    found on d20 + WIS against 10 + its INT (its side then sees it until it slips away)."""
    id, name, cost, target = "investigate", "Investigate", 1, "none"
    desc = "Inspect nearby walls for secret doors, and look and listen for something unseen."
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
            return "Investigate secret (1 pt)"
        return f"Investigate ({self.RADIUS} squares, WIS)"

    def execute(self, battle, actor, target=None):
        if not self.available(battle, actor):
            return
        actor.ap -= self.cost
        actor.walking = False
        secrets = self._adjacent_secrets(battle, actor)
        for p in secrets:
            battle.board.walls.discard(p)
            battle.secret_walls.discard(p)
            battle.log(f"{actor.name} inspects the wall and triggers a hidden lever! A secret door slides open at {p}.")
            battle.fx(p, "Secret Opened!", "crit")
        lurkers = self._lurkers(battle, actor)
        if not lurkers:
            return
        found = False
        for u in lurkers:
            if battle.units_distance(actor, u) <= self.RADIUS and d20() + actor.mod_wisdom >= 10 + u.mod_intelligence:
                u.reveal_to(actor.team)
                found = True
                battle.log(f"{actor.name} searches and finds {u.name} hiding at {u.pos}!")
                battle.fx(u.pos, "Found!", "crit")
        if not found and not secrets:
            battle.log(f"{actor.name} searches the dark around them and finds nothing.")


class Disarm(Action):
    id, name, cost, target = "disarm", "Disarm Trap", 1, "none"
    desc = "Disarm an adjacent trap (d20 + DEX vs DC 12)."

    def _adjacent_traps(self, battle, actor):
        return [o for o in battle.ground if o.is_trap and chebyshev(actor.pos, o.pos) <= 1]

    def available(self, battle, actor):
        return actor.ap >= self.cost and bool(self._adjacent_traps(battle, actor))

    def label(self, battle, actor):
        return "Disarm trap (1 pt, DEX vs DC 12)"

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
        battle.log(f"{actor.name} attempts to disarm {trap.trap_type}: d20({nat}) {bonus:+}(DEX) = {total} vs DC {dc} -> "
                   + ("success!" if ok else "failed."))
        if ok and trap.trap_type == "web":
            battle.remove_web(trap)
            battle.log(f"  {actor.name} tears the web down.")
            battle.fx(trap.pos, "Web Cleared!", "ok")
        elif ok:
            battle.ground.remove(trap)
            trap_name = "Bear Trap" if "bear" in trap.trap_type.lower() else "Alarm Trap"
            actor.inventory.append(trap_name)
            if not hasattr(actor, "picked_up_items"):
                actor.picked_up_items = []
            actor.picked_up_items.append(trap_name)
            battle.log(f"  {actor.name} disarms the {trap.trap_type} and recovers a {trap_name}!")
            battle.fx(trap.pos, "Trap Disarmed!", "ok")
        elif nat == 1 or total <= dc - 5:
            battle.log(f"  Critical fumble! {actor.name} accidentally triggers the trap!")
            battle.trigger_trap(actor, trap)


# --------------------------------------------------------------------------- #
# Capture                                                                      #
# --------------------------------------------------------------------------- #

class Capture(Action):
    """Bind an adjacent fallen foe (dying or knocked out) with a Rope or Chains, used up. The
    captive is out of the fight for good: no coup de grace, no death save; after a won battle
    it joins the group as a captured unit (`captives.py`)."""
    id, name, cost, target, aimed = "capture", "Capture", 1, "enemy", True
    desc = "Bind an adjacent fallen foe with a Rope or Chains; it leaves the fight as your captive."

    @classmethod
    def applicable(cls, battle, actor):
        if capture_tool(actor) is None:
            return False, "Needs a Rope or Chains."
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
        battle.log(f"{actor.name} binds {target.name} with {tool}: captured.")
        battle.fx(target.pos, "Captured", "ok")
