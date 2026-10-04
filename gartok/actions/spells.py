"""Spell actions: one subclass per spell, built through `CastSpellAction`."""

import random

from .. import data, magic
from ..board import grid_distance
from ..conditions import Sleeping
from ..data import d20
from ..ground import GroundObject
from .base import Action, _cell_free, _hostile_target


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
        hit_score = atk + actor.mod_intelligence
        if atk == 20 or hit_score >= target.ac:
            dmg = data.roll(1, 4)
            battle.log(f" Hit ({hit_score} vs AC {target.ac}) for {dmg} magic damage.")
            was_up = target.alive
            target.take_damage(dmg, battle.log)
            if was_up and not target.alive and target.team != actor.team:
                actor.credit_kill(target)
        else:
            battle.log(f" Miss ({hit_score} vs AC {target.ac}).")


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
        if getattr(target.char.ability, "sleep_immunity", False):
            battle.log(f"  {target.name} is immune to sleep effects!")
            return

        atk = d20()
        hit_score = atk + actor.mod_intelligence
        md = target.mental_defense
        desc = f" d20({atk}) {actor.mod_intelligence:+}(INT) = {hit_score} vs MD {md}"

        if atk == 1:
            battle.log(desc + " -> Critical miss!")
        elif atk == 20 or hit_score >= md:
            duration = max(1, 10 - target.mod_constitution - target.mod_wisdom)
            target.add_condition(Sleeping(duration=duration))
            battle.log(desc + (" -> CRITICAL HIT!" if atk == 20 else " -> lands.") + f" {target.name} falls asleep ({duration} rds)!")
        else:
            battle.log(desc + " -> resisted.")


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


_SPELL_ACTIONS = {
    "magic_missile": MagicMissileAction,
    "sleep": SleepAction,
    "light_globe": LightGlobeAction,
    "floating_disk": FloatingDiskAction,
}


def CastSpellAction(spell_id):
    """Build the Action for `spell_id` (see `_SPELL_ACTIONS`)."""
    return _SPELL_ACTIONS[spell_id]()

class ShareMagicAction(Action):
    id = "share_magic"
    name = "Share Magic"
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
