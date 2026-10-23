"""Spell actions: one subclass per spell, built through `CastSpellAction`."""

import random

from .. import data, intel, items, magic
from ..board import grid_distance
from ..conditions import Invisible, Rooted, Sleeping
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

    def spell_range(self, actor, base):
        return base + int(actor.talent_bonus("spell_range"))

    def spell_to_hit(self, actor):
        return actor.mod_intelligence + int(actor.talent_bonus("spell_to_hit"))

    def spell_damage_bonus(self, actor):
        return int(actor.talent_bonus("spell_damage"))

    def spell_heal_bonus(self, actor):
        return int(actor.talent_bonus("spell_heal"))


class MagicMissileAction(SpellAction):
    spell_id = "magic_missile"
    target, aimed = "enemy", True
    missile = True
    REACH = 6

    def can(self, battle, actor, target=None):
        if not super().can(battle, actor, target):
            return False
        if not _hostile_target(actor, target):
            return False
        return battle.units_distance(actor, target) <= self.spell_range(actor, self.REACH)

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
        hit_score = atk + self.spell_to_hit(actor) - pulled
        ac = target.ac_vs(actor)
        if atk == 20 or hit_score >= ac:
            dmg = data.roll(1, 4) + self.spell_damage_bonus(actor)
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
    REACH = 6

    def can(self, battle, actor, target=None):
        if not super().can(battle, actor, target):
            return False
        if not _hostile_target(actor, target):
            return False
        return battle.units_distance(actor, target) <= self.spell_range(actor, self.REACH)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        battle.log(f"{actor.name} casts {self.spell.name} on {target.name}!")
        if getattr(target.char.ability, "sleep_immunity", False) or target.raised:
            battle.log(f"  {target.name} is immune to sleep effects!")
            return

        atk = d20()
        to_hit = self.spell_to_hit(actor)
        hit_score = atk + to_hit
        md = target.mental_defense
        desc = f" d20({atk}) {to_hit:+}(INT) = {hit_score} vs MD {intel.shown(battle, target, 'md', md)}"

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
    missile = True
    DICE = (1, 6)

    @staticmethod
    def reach(actor=None):
        bonus = int(actor.talent_bonus("spell_range")) if actor is not None else 0
        return items.get("Dagger").thrown + bonus

    def can(self, battle, actor, target=None):
        if not super().can(battle, actor, target):
            return False
        if not _hostile_target(actor, target):
            return False
        return (battle.units_distance(actor, target) <= self.reach(actor)
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
        hit_score = atk + self.spell_to_hit(actor) - pulled
        ac = target.ac_vs(actor)
        shown = intel.shown(battle, target, 'ac', ac)
        if atk != 20 and hit_score < ac:
            battle.log(f" Miss ({hit_score} vs AC {shown}).")
            return
        dmg = max(1, data.roll(*self.DICE) + actor.mod_intelligence + self.spell_damage_bonus(actor))
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
    AC for 2d6. Reaches as far as a dagger is thrown."""
    spell_id = "dragonfire"
    target, aimed = "enemy", True
    missile = True
    DICE = (2, 6)

    @staticmethod
    def reach(actor=None):
        bonus = int(actor.talent_bonus("spell_range")) if actor is not None else 0
        return items.get("Dagger").thrown + bonus

    def can(self, battle, actor, target=None):
        if not super().can(battle, actor, target):
            return False
        if not _hostile_target(actor, target):
            return False
        return (battle.units_distance(actor, target) <= self.reach(actor)
                and battle.los_between(actor, target))

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        battle.log(f"{actor.name} spits {self.spell.name} at {target.name}!")
        atk = d20()
        if atk == 1:
            battle.log(" Critical miss!")
            return
        pulled = nonlethal_penalty(actor)
        hit_score = atk + self.spell_to_hit(actor) - pulled
        ac = target.ac_vs(actor)
        shown = intel.shown(battle, target, "ac", ac)
        if atk != 20 and hit_score < ac:
            battle.log(f" Miss ({hit_score} vs AC {shown}).")
            return
        dice = self.DICE[0] * (2 if atk == 20 else 1)
        dmg = data.roll(dice, self.DICE[1]) + self.spell_damage_bonus(actor)
        battle.log(f" Hit ({hit_score} vs AC {shown}) for {dmg} fire damage.")
        was_up = target.alive
        target.take_damage(dmg, battle.log, knockout=bool(pulled))
        if was_up and not target.alive and target.team != actor.team:
            actor.credit_kill(target, magic=True)


class _HostileSpellAction(SpellAction):
    """A foe in sight within `REACH`, `d20 + INT` against one of its defences (`against`): a
    natural 1 misses, a natural 20 lands. `lands` is what a landed cast does."""
    target, aimed = "enemy", True
    REACH = 6
    against = "ac"

    def can(self, battle, actor, target=None):
        if not super().can(battle, actor, target) or not _hostile_target(actor, target):
            return False
        return (battle.units_distance(actor, target) <= self.spell_range(actor, self.REACH)
                and battle.los_between(actor, target))

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        battle.log(f"{actor.name} casts {self.spell.name} on {target.name}!")
        atk = d20()
        to_hit = self.spell_to_hit(actor)
        score = atk + to_hit
        defence = target.ac_vs(actor) if self.against == "ac" else target.mental_defense
        label = "AC" if self.against == "ac" else "MD"
        desc = (f" d20({atk}) {to_hit:+}(INT) = {score} vs {label} "
                f"{intel.shown(battle, target, self.against, defence)}")
        if atk == 1:
            battle.log(desc + " -> Critical miss!")
        elif atk == 20 or score >= defence:
            battle.log(desc + " -> lands.")
            self.lands(battle, actor, target)
        else:
            battle.log(desc + " -> resisted.")


class GraspingRootsAction(_HostileSpellAction):
    """Nature's level 0: roots hold a foe to 1 cell of walking until the end of its next turn."""
    spell_id = "grasping_roots"

    def lands(self, battle, actor, target):
        old = target.condition("rooted")
        if old is not None:
            target.conditions.remove(old)
        target.add_condition(Rooted())
        battle.log(f"  Roots grip {target.name}'s legs: one cell of walking until its next turn is over.")
        battle.fx(target.pos, "rooted", "faint")


class HexAction(_HostileSpellAction):
    """Blood's level 0: -1 on each of the foe's six scores until the end of its next turn
    (`Combatant.hex`), which bites only where a score is even."""
    spell_id = "hex"
    against = "md"

    def lands(self, battle, actor, target):
        was_up = target.alive
        target.hex(battle.log)
        bit = [a[:3].upper() for a, d in target.condition("hexed").deltas.items() if d]
        battle.log(f"  {target.name} is hexed: " + (f"{', '.join(bit)} -1." if bit else "nothing gives."))
        battle.fx(target.pos, "hexed", "faint")
        if was_up and not target.alive and target.team != actor.team:
            actor.credit_kill(target, magic=True)


class _TouchSpellAction(SpellAction):
    """A Faith touch spell: an ally (or the caster) in reach of a hand, no roll."""
    target, aimed = "ally", True

    def wants(self, unit):
        return False

    def _targets(self, battle, actor):
        return [u for u in battle.units
                if u.team == actor.team and self.wants(u) and battle.units_distance(actor, u) <= 1]

    def available(self, battle, actor):
        return super().available(battle, actor) and bool(self._targets(battle, actor))

    def can(self, battle, actor, target=None):
        return (super().available(battle, actor) and target is not None
                and target in self._targets(battle, actor))

    def highlight_targets(self, battle, actor):
        return self._targets(battle, actor)


class SpareTheDyingAction(_TouchSpellAction):
    """Faith's level 0: a dying ally in reach is stable, no check."""
    spell_id = "spare_the_dying"

    def wants(self, unit):
        return unit.dying and not unit.raised

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        battle.log(f"{actor.name} lays a hand on {target.name} and casts {self.spell.name}.")
        battle.stabilize(target)
        battle.fx(target.pos, "stable", "ok")


class HealingTouchAction(_TouchSpellAction):
    """Faith's level 1: 1d6 HP to an ally in reach (or the caster), nothing added; a body on
    the ground is back on its feet."""
    spell_id = "healing_touch"
    DICE = (1, 6)

    def wants(self, unit):
        return ((unit.alive and unit.hp < unit.hp_max) or unit.dying or unit.stable) and not unit.raised

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        heal = data.roll(*self.DICE) + self.spell_heal_bonus(actor)
        revived = target.dying or target.stable
        target.hp = min(target.hp_max, max(target.hp, 0) + heal)
        if revived:
            target.status, target.death_clock = "up", 0
        who = "themself" if target is actor else target.name
        battle.log(f"{actor.name} casts {self.spell.name} on {who}, healing {heal} HP"
                   + (" -- back on their feet." if revived else "."))
        battle.fx(target.pos, f"+{heal} HP", "ok")


class _PlacedSpellAction(SpellAction):
    """Shared `can()` for the two spells that drop something on a cell
    (Light Globe, Floating Disk) instead of targeting an enemy."""
    target, aimed = "cell", True
    REACH = 6

    def can(self, battle, actor, target=None):
        if not super().can(battle, actor, target):
            return False
        if not target or not battle.board.in_bounds(target):
            return False
        dist = grid_distance(battle.cells_of(actor)[0], target)
        return dist <= self.spell_range(actor, self.REACH) and _cell_free(battle, actor, target, footprint=1)

    def highlight_cells(self, battle, actor):
        (x0, y0), r = battle.cells_of(actor)[0], self.spell_range(actor, self.REACH)
        return [(x, y) for x in range(x0 - r, x0 + r + 1) for y in range(y0 - r, y0 + r + 1)
                if self.can(battle, actor, (x, y))]


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

    def heights(self, battle, actor, tile):
        """[(z, label)] the disk may float at over `tile`, highest first: the ground, the caster's
        height and, over a pit, its floor. More than one asks the caster to pick."""
        caster_z = battle.elevation(actor)
        pit_z = battle.board.elevation_at(tile)
        opts = []
        for z in sorted({0, caster_z, pit_z}, reverse=True):
            tags = (["Ground"] if z == 0 else []) + (["Caster"] if z == caster_z else [])                 + (["Pit floor"] if z == pit_z and pit_z != 0 else [])
            opts.append((z, f"z={z}" + (f" ({'/'.join(tags)})" if tags else "")))
        return opts

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
        return (battle.units_distance(actor, body) <= self.spell_range(actor, self.REACH)
                and battle.los_between(actor, body)
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
    "grasping_roots": GraspingRootsAction,
    "hex": HexAction,
    "spare_the_dying": SpareTheDyingAction,
    "healing_touch": HealingTouchAction,
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
