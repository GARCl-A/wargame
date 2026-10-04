"""Non-attack actions: pick up, stabilise, potions, racial actions, traps, End Turn."""

import random

from .. import data
from ..board import chebyshev
from ..conditions import Demoralized
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
                    actor.char.gold += amt
                    battle.log(f"{actor.name} finds {amt} copper in the chest!")
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
        
        verb = "drinks" if actor == target else f"feeds {target.name}"
        battle.log(f"{actor.name} {verb} a Minor Healing Potion, recovering {heal} HP.")
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
                    battle.log(f"    {u.name} (MD {md}) is terrified -> DEMORALIZED.")
                else:
                    battle.log(f"    {u.name} (MD {md}) resists the horror.")


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
        return target in battle.board.neighbors(actor.mounted_on.pos) and _cell_free(battle, actor, target)

    def highlight_cells(self, battle, actor):
        if not getattr(actor, "mounted_on", None):
            return []
        return [c for c in battle.board.neighbors(actor.mounted_on.pos) if _cell_free(battle, actor, c)]

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
    desc = "End your turn."

    def available(self, battle, actor):
        return battle.winner is None

    def execute(self, battle, actor, target=None):
        battle.end_turn()


class Investigate(Action):
    id, name, cost, target = "investigate", "Investigate", 1, "none"
    desc = "Inspect nearby walls and surfaces for secret doors or hidden switches."

    def _adjacent_secrets(self, battle, actor):
        secrets = getattr(battle, "secret_walls", set())
        return [p for p in secrets if chebyshev(actor.pos, p) <= 1]

    def available(self, battle, actor):
        return actor.ap >= self.cost and bool(self._adjacent_secrets(battle, actor))

    def label(self, battle, actor):
        return "Investigate secret (1 pt)"

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
        if ok:
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
