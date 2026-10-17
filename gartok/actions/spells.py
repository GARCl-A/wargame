"""Spell actions: one subclass per spell, built through `CastSpellAction`."""

import random

from .. import data, intel, items, magic
from ..board import grid_distance
from ..conditions import Invisible, Sleeping
from ..data import d20
from ..ground import GroundObject
from .base import Action, _cell_free, _hostile_target, _sign, nonlethal_penalty


class SpellAction(Action):
    """Shared plumbing for a spell cast as a combat action: one subclass per
    spell (same "one class = one mechanic" rule as the rest of this file),
    looked up once against `magic.SPELLS` by `spell_id`. Built through the
    `CastSpellAction(spell_id)` factory below, so `ai.py` / `battle_screen.py`
    don't need to know the id -> class mapping."""
    spell_id = ""
    cost = 1

    def __init__(self):
        self.spell = magic.SPELLS[self.spell_id]
        self.id = f"cast_{self.spell_id}"
        self.name = self.spell.name

    def available(self, battle, actor):
        return actor.ap >= self.cost and self.spell_id in actor.spells_known


class MagicMissileAction(SpellAction):
    spell_id = "magic_missile"
    target, aimed = "enemy", True

    def can(self, battle, actor, target=None):
        if not super().can(battle, actor, target):
            return False
        if not _hostile_target(actor, target):
            return False
        return battle.units_distance(actor, target) <= 6

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        battle.log(f"{actor.name} casts {self.spell.name} on {target.name}!")
        atk = d20()
        if atk == 1:
            battle.log(" Critical miss!")
            return
        pulled = nonlethal_penalty(actor)
        hit_score = atk + actor.mod_intelligence - pulled
        ac = target.ac_vs(actor)
        if atk == 20 or hit_score >= ac:
            dmg = data.roll(1, 4)
            battle.log(f" Hit ({hit_score} vs AC {intel.shown(battle, target, 'ac', ac)}) for {dmg} magic damage.")
            was_up = target.alive
            target.take_damage(dmg, battle.log, knockout=bool(pulled))
            if was_up and not target.alive and target.team != actor.team:
                actor.credit_kill(target, magic=True)
        else:
            battle.log(f" Miss ({hit_score} vs AC {intel.shown(battle, target, 'ac', ac)}).")


class SleepAction(SpellAction):
    spell_id = "sleep"
    target, aimed = "enemy", True

    def can(self, battle, actor, target=None):
        if not super().can(battle, actor, target):
            return False
        if not _hostile_target(actor, target):
            return False
        return battle.units_distance(actor, target) <= 6

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        battle.log(f"{actor.name} casts {self.spell.name} on {target.name}!")
        if getattr(target.char.ability, "sleep_immunity", False) or target.raised:
            battle.log(f"  {target.name} is immune to sleep effects!")
            return

        atk = d20()
        hit_score = atk + actor.mod_intelligence
        md = target.mental_defense
        desc = f" d20({atk}) {actor.mod_intelligence:+}(INT) = {hit_score} vs MD {intel.shown(battle, target, 'md', md)}"

        if atk == 1:
            battle.log(desc + " -> Critical miss!")
        elif atk == 20 or hit_score >= md:
            duration = max(1, 10 - target.mod_constitution - target.mod_wisdom)
            target.add_condition(Sleeping(duration=duration))
            battle.log(desc + (" -> CRITICAL HIT!" if atk == 20 else " -> lands.") + f" {target.name} falls asleep ({duration} rds)!")
        else:
            battle.log(desc + " -> resisted.")


class WaterJetAction(SpellAction):
    """Nature's own: a jet of water, INT to hit against AC, 1d6 + INT and a hit throws the
    target a square away from the caster. Reaches as far as a dagger is thrown."""
    spell_id = "water_jet"
    target, aimed = "enemy", True
    DICE = (1, 6)

    @staticmethod
    def reach():
        return items.get("Dagger").thrown

    def can(self, battle, actor, target=None):
        if not super().can(battle, actor, target):
            return False
        if not _hostile_target(actor, target):
            return False
        return (battle.units_distance(actor, target) <= self.reach()
                and battle.los_between(actor, target))

    def landing(self, battle, actor, target):
        """The cell the jet throws `target` onto, or None when something is in the way."""
        dx, dy = _sign(target.pos[0] - actor.pos[0]), _sign(target.pos[1] - actor.pos[1])
        if (dx, dy) == (0, 0):
            return None
        dest = (target.pos[0] + dx, target.pos[1] + dy)
        if battle.board.diagonal_corner_blocked(target.pos, dest) or not _cell_free(battle, target, dest):
            return None
        return dest

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        battle.log(f"{actor.name} casts {self.spell.name} on {target.name}!")
        atk = d20()
        if atk == 1:
            battle.log(" Critical miss!")
            return
        pulled = nonlethal_penalty(actor)
        hit_score = atk + actor.mod_intelligence - pulled
        ac = target.ac_vs(actor)
        shown = intel.shown(battle, target, 'ac', ac)
        if atk != 20 and hit_score < ac:
            battle.log(f" Miss ({hit_score} vs AC {shown}).")
            return
        dmg = max(1, data.roll(*self.DICE) + actor.mod_intelligence)
        battle.log(f" Hit ({hit_score} vs AC {shown}) for {dmg} damage.")
        was_up = target.alive
        dest = self.landing(battle, actor, target)
        target.take_damage(dmg, battle.log, knockout=bool(pulled))
        if dest is not None and not target.dead:
            before = set(battle.cells_of(target))
            z_from = battle.elevation(target)
            target.pos = dest
            target.z = battle.elevation_at(dest, target)
            battle.log(f"  The water throws {target.name} back to {dest}.")
            battle.burn(target, set(battle.cells_of(target)) - before)
            if target.z < z_from:
                battle.apply_fall(target, z_from - target.z, battle.log)
        if was_up and not target.alive and target.team != actor.team:
            actor.credit_kill(target, magic=True)


class DragonfireAction(SpellAction):
    """Blood's own, on the Dragon branch: fire spat from the caster's blood, INT to hit against
    AC for 2d6. The blood is the price: casting costs the caster 1d4 hit points, hit or miss,
    and nobody casts it with that much or less left. Reaches as far as a dagger is thrown."""
    spell_id = "dragonfire"
    target, aimed = "enemy", True
    DICE = (2, 6)
    PRICE = (1, 4)

    @staticmethod
    def reach():
        return items.get("Dagger").thrown

    def can(self, battle, actor, target=None):
        if not super().can(battle, actor, target):
            return False
        if actor.hp <= self.PRICE[0] * self.PRICE[1] or not _hostile_target(actor, target):
            return False
        return (battle.units_distance(actor, target) <= self.reach()
                and battle.los_between(actor, target))

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        price = data.roll(*self.PRICE)
        actor.hp -= price
        battle.log(f"{actor.name} bleeds {price} HP into {self.spell.name} at {target.name}!")
        atk = d20()
        if atk == 1:
            battle.log(" Critical miss!")
            return
        pulled = nonlethal_penalty(actor)
        hit_score = atk + actor.mod_intelligence - pulled
        ac = target.ac_vs(actor)
        shown = intel.shown(battle, target, "ac", ac)
        if atk != 20 and hit_score < ac:
            battle.log(f" Miss ({hit_score} vs AC {shown}).")
            return
        dice = self.DICE[0] * (2 if atk == 20 else 1)
        dmg = data.roll(dice, self.DICE[1])
        battle.log(f" Hit ({hit_score} vs AC {shown}) for {dmg} fire damage.")
        was_up = target.alive
        target.take_damage(dmg, battle.log, knockout=bool(pulled))
        if was_up and not target.alive and target.team != actor.team:
            actor.credit_kill(target, magic=True)


class _PlacedSpellAction(SpellAction):
    """Shared `can()` for the two spells that drop something on a cell
    (Light Globe, Floating Disk) instead of targeting an enemy."""
    target, aimed = "cell", True

    def can(self, battle, actor, target=None):
        if not super().can(battle, actor, target):
            return False
        if not target or not battle.board.in_bounds(target):
            return False
        dist = grid_distance(battle.cells_of(actor)[0], target)
        return dist <= 6 and _cell_free(battle, actor, target, footprint=1)


class LightGlobeAction(_PlacedSpellAction):
    spell_id = "light_globe"

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        battle.log(f"{actor.name} casts {self.spell.name}.")
        battle.ground.append(GroundObject.torch(target))


class FloatingDiskAction(_PlacedSpellAction):
    spell_id = "floating_disk"

    def execute(self, battle, actor, target=None, elevation=None):
        if not self.can(battle, actor, target):
            return
        if elevation is None:
            elevation = battle.elevation(actor)
        elevation = int(elevation)
        actor.ap -= self.cost
        battle.log(f"{actor.name} casts {self.spell.name} at height {elevation}.")
        battle.ground.append(GroundObject.disk(target, elevation=elevation))
        battle.clear_pf_cache()


class InvisibilityAction(SpellAction):
    """Level 2, every school: the caster vanishes from every other side's sight until it
    hurts someone (`conditions.Invisible`, `Combatant.hidden_from`)."""
    spell_id = "invisibility"
    cost = 2

    def available(self, battle, actor):
        return super().available(battle, actor) and not actor.has_condition("invisible")

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        actor.add_condition(Invisible())
        battle.log(f"{actor.name} casts {self.spell.name} and fades from sight.")


class RaiseDeadAction(SpellAction):
    """Level 2, Faith: a dead body in reach stands up again on the caster's side with 1 HP.
    A body raised once and fallen again stays down. The ground stirs where it rises, which
    is all an unseen caster gives away."""
    spell_id = "raise_dead"
    target, aimed = "cell", True
    cost = 2
    REACH = 6

    @staticmethod
    def bodies(battle):
        """The dead on the field that can still be raised."""
        return [u for u in battle.units if u.dead and not u.raised and not u.captured]

    def body_at(self, battle, pos):
        return next((u for u in self.bodies(battle) if pos in battle.cells_of(u)), None)

    def can(self, battle, actor, target=None):
        if not super().can(battle, actor, target) or target is None:
            return False
        body = self.body_at(battle, target)
        if body is None:
            return False
        return (battle.units_distance(actor, body) <= self.REACH and battle.los_between(actor, body)
                and _cell_free(battle, body, body.pos))

    def highlight_cells(self, battle, actor):
        return [u.pos for u in self.bodies(battle) if self.can(battle, actor, u.pos)]

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        body = self.body_at(battle, target)
        body.raise_from_dead(actor.team)
        battle.log(f"The earth stirs at {body.pos} -- {body.name} rises again!")
        battle.fx(body.pos, "rises!", "crit")


_SPELL_ACTIONS = {
    "magic_missile": MagicMissileAction,
    "sleep": SleepAction,
    "light_globe": LightGlobeAction,
    "floating_disk": FloatingDiskAction,
    "water_jet": WaterJetAction,
    "dragonfire": DragonfireAction,
    "invisibility": InvisibilityAction,
    "raise_dead": RaiseDeadAction,
}


def CastSpellAction(spell_id):
    """Build the Action for `spell_id` (see `_SPELL_ACTIONS`)."""
    return _SPELL_ACTIONS[spell_id]()

class ShareMagicAction(Action):
    id = "share_magic"
    name = "Share Magic"
    desc = "Temporarily share a known spell with a random ally for this battle."
    cost = 1
    target = "none"
    
    @classmethod
    def applicable(cls, battle, actor):
        if not actor.char.has_talent("sprite_nature_initiate"):
            return False, "Not a Sprite Initiate."
        if not actor.spells_known:
            return False, "No spells known."
        return True, ""

    def available(self, battle, actor):
        return (actor.ap >= self.cost
                and actor.char.has_talent("sprite_nature_initiate")
                and len(actor.spells_known) > 0)

    def execute(self, battle, actor, target=None):
        if not self.available(battle, actor): return
        actor.ap -= self.cost

        allies = [u for u in battle.units if u.alive and u.team == actor.team and u != actor]
        if not allies:
            battle.log(f"{actor.name} tries to share magic, but no allies are nearby!")
            return

        ally = random.choice(allies)
        spell_id = random.choice(actor.spells_known)
        spell_name = magic.SPELLS[spell_id].name if spell_id in magic.SPELLS else spell_id

        if spell_id not in ally.spells_known:
            ally.spells_known.append(spell_id)
            battle.log(f"{actor.name} shares magic! {ally.name} temporarily learns {spell_name}.")
        else:
            battle.log(f"{actor.name} tries to share magic, but {ally.name} already knows {spell_name}.")
