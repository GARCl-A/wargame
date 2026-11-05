"""Spell actions: one subclass per spell, built through `CastSpellAction`."""

import random

from .. import data, i18n, intel, items, magic
from ..board import grid_distance
from ..conditions import Invisible, Rooted, Sleeping
from ..data import d20
from ..ground import GroundObject
from ..i18n import Msg, Ref
from .base import Action, _cell_free, _hostile_target, _sign, nonlethal_penalty

_DAGGER_THROW = items.get("Dagger").thrown


def _dice(dice):
    return f"{dice[0]}d{dice[1]}"


class SpellAction(Action):
    """Shared plumbing for a spell cast as a combat action: one subclass per
    spell (same "one class = one mechanic" rule as the rest of this file),
    looked up once against `magic.SPELLS` by `spell_id`. Built through the
    `CastSpellAction(spell_id)` factory below, so `ai/` / `battle_screen.py`
    don't need to know the id -> class mapping."""
    spell_id = ""
    cost = 1

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        if cls.__dict__.get("spell_id"):
            cls.id = f"cast_{cls.spell_id}"

    def __init__(self):
        self.spell = magic.SPELLS[self.spell_id]
        self.name = self.spell.name

    @property
    def spell_ref(self):
        return Ref("spell", self.spell_id, self.spell.name)

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
    DICE = (1, 4)
    desc = i18n.Text("action", "desc", reach=REACH, dice=_dice(DICE))

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
        battle.log("log.spell.casts", actor=actor.name, spell=self.spell_ref, target=target.name)
        atk = d20()
        if atk == 1:
            battle.log("log.spell.crit_miss")
            return
        pulled = nonlethal_penalty(actor)
        hit_score = atk + self.spell_to_hit(actor) - pulled
        ac = target.ac_vs(actor)
        if atk == 20 or hit_score >= ac:
            dmg = data.roll(*self.DICE) + self.spell_damage_bonus(actor)
            battle.log("log.spell.hit_magic", score=hit_score, ac=intel.shown(battle, target, "ac", ac), dmg=dmg)
            was_up = target.alive
            target.take_damage(dmg, battle.log, knockout=bool(pulled))
            if was_up and not target.alive and target.team != actor.team:
                actor.credit_kill(target, magic=True)
        else:
            battle.log("log.spell.miss", score=hit_score, ac=intel.shown(battle, target, "ac", ac))


class SleepAction(SpellAction):
    spell_id = "sleep"
    target, aimed = "enemy", True
    REACH = 6
    desc = i18n.Text("action", "desc", reach=REACH)

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
        battle.log("log.spell.casts", actor=actor.name, spell=self.spell_ref, target=target.name)
        if getattr(target.char.ability, "sleep_immunity", False) or target.raised:
            battle.log("log.sleep.immune", target=target.name)
            return

        atk = d20()
        to_hit = self.spell_to_hit(actor)
        hit_score = atk + to_hit
        md = target.mental_defense
        roll = Msg("log.spell.roll_md", atk=atk, bonus=to_hit, score=hit_score,
                   md=intel.shown(battle, target, "md", md))

        if atk == 1:
            battle.log("log.spell.roll_crit_miss", roll=roll)
        elif atk == 20 or hit_score >= md:
            duration = max(1, 10 - target.mod_constitution - target.mod_wisdom)
            target.add_condition(Sleeping(duration=duration))
            battle.log("log.sleep.crit" if atk == 20 else "log.sleep.lands", roll=roll, target=target.name, n=duration)
        else:
            battle.log("log.spell.roll_resisted", roll=roll)


class WaterJetAction(SpellAction):
    """Nature's own: a jet of water, INT to hit against AC, 1d6 + INT and a hit throws the
    target a square away from the caster. Reaches as far as a dagger is thrown."""
    spell_id = "water_jet"
    target, aimed = "enemy", True
    missile = True
    DICE = (1, 6)
    desc = i18n.Text("action", "desc", reach=_DAGGER_THROW, dice=_dice(DICE))

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
        battle.log("log.spell.casts", actor=actor.name, spell=self.spell_ref, target=target.name)
        atk = d20()
        if atk == 1:
            battle.log("log.spell.crit_miss")
            return
        pulled = nonlethal_penalty(actor)
        hit_score = atk + self.spell_to_hit(actor) - pulled
        ac = target.ac_vs(actor)
        shown = intel.shown(battle, target, "ac", ac)
        if atk != 20 and hit_score < ac:
            battle.log("log.spell.miss", score=hit_score, ac=shown)
            return
        dmg = max(1, data.roll(*self.DICE) + actor.mod_intelligence + self.spell_damage_bonus(actor))
        battle.log("log.spell.hit_plain", score=hit_score, ac=shown, dmg=dmg)
        was_up = target.alive
        dest = self.landing(battle, actor, target)
        target.take_damage(dmg, battle.log, knockout=bool(pulled))
        if dest is not None and not target.dead:
            before = set(battle.cells_of(target))
            z_from = battle.elevation(target)
            target.pos = dest
            target.z = battle.elevation_at(dest, target)
            battle.log("log.water_jet.throws", target=target.name, cell=str(dest))
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
    desc = i18n.Text("action", "desc", reach=_DAGGER_THROW, dice=_dice(DICE))

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
        battle.log("log.dragonfire.spits", actor=actor.name, spell=self.spell_ref, target=target.name)
        atk = d20()
        if atk == 1:
            battle.log("log.spell.crit_miss")
            return
        pulled = nonlethal_penalty(actor)
        hit_score = atk + self.spell_to_hit(actor) - pulled
        ac = target.ac_vs(actor)
        shown = intel.shown(battle, target, "ac", ac)
        if atk != 20 and hit_score < ac:
            battle.log("log.spell.miss", score=hit_score, ac=shown)
            return
        dice = self.DICE[0] * (2 if atk == 20 else 1)
        dmg = data.roll(dice, self.DICE[1]) + self.spell_damage_bonus(actor)
        battle.log("log.spell.hit_fire", score=hit_score, ac=shown, dmg=dmg)
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
        battle.log("log.spell.casts", actor=actor.name, spell=self.spell_ref, target=target.name)
        atk = d20()
        to_hit = self.spell_to_hit(actor)
        score = atk + to_hit
        defence = target.ac_vs(actor) if self.against == "ac" else target.mental_defense
        roll = Msg("log.spell.roll_ac" if self.against == "ac" else "log.spell.roll_md", atk=atk, bonus=to_hit,
                   score=score, **{self.against: intel.shown(battle, target, self.against, defence)})
        if atk == 1:
            battle.log("log.spell.roll_crit_miss", roll=roll)
        elif atk == 20 or score >= defence:
            battle.log("log.spell.roll_lands", roll=roll)
            self.lands(battle, actor, target)
        else:
            battle.log("log.spell.roll_resisted", roll=roll)


class GraspingRootsAction(_HostileSpellAction):
    """Nature's level 0: roots hold a foe to 1 cell of walking until the end of its next turn."""
    spell_id = "grasping_roots"
    desc = i18n.Text("action", "desc", reach=_HostileSpellAction.REACH)

    def lands(self, battle, actor, target):
        old = target.condition("rooted")
        if old is not None:
            target.conditions.remove(old)
        target.add_condition(Rooted())
        battle.log("log.grasping_roots.grip", target=target.name)
        battle.fx(target.pos, i18n.t("fx.rooted"), "faint")


class HexAction(_HostileSpellAction):
    """Blood's level 0: -1 on each of the foe's six scores until the end of its next turn
    (`Combatant.hex`), which bites only where a score is even."""
    spell_id = "hex"
    against = "md"
    desc = i18n.Text("action", "desc", reach=_HostileSpellAction.REACH)

    def lands(self, battle, actor, target):
        was_up = target.alive
        target.hex(battle.log)
        bit = [a[:3].upper() for a, d in target.condition("hexed").deltas.items() if d]
        if bit:
            battle.log("log.hex.bites", target=target.name, scores=", ".join(bit))
        else:
            battle.log("log.hex.nothing", target=target.name)
        battle.fx(target.pos, i18n.t("fx.hexed"), "faint")
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
    desc = i18n.Text("action", "desc")

    def wants(self, unit):
        return unit.dying and not unit.raised

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        battle.log("log.spare_the_dying.touch", actor=actor.name, target=target.name, spell=self.spell_ref)
        battle.stabilize(target)
        battle.fx(target.pos, i18n.t("fx.stable"), "ok")


class HealingTouchAction(_TouchSpellAction):
    """Faith's level 1: 1d6 HP to an ally in reach (or the caster), nothing added; a body on
    the ground is back on its feet."""
    spell_id = "healing_touch"
    DICE = (1, 6)
    desc = i18n.Text("action", "desc", dice=_dice(DICE))

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
        key = ("log.healing_touch.self" if target is actor else "log.healing_touch.other") + ("_up" if revived else "")
        battle.log(key, actor=actor.name, spell=self.spell_ref, target=target.name, heal=heal)
        battle.fx(target.pos, i18n.t("fx.heal", heal=heal), "ok")


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
    desc = i18n.Text("action", "desc", reach=_PlacedSpellAction.REACH)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        battle.log("log.light_globe.casts", actor=actor.name, spell=self.spell_ref)
        battle.ground.append(GroundObject.torch(target))


class FloatingDiskAction(_PlacedSpellAction):
    spell_id = "floating_disk"
    desc = i18n.Text("action", "desc", reach=_PlacedSpellAction.REACH)

    def heights(self, battle, actor, tile):
        """[(z, label)] the disk may float at over `tile`, highest first: the ground, the caster's
        height and, over a pit, its floor. More than one asks the caster to pick."""
        caster_z = battle.elevation(actor)
        pit_z = battle.board.elevation_at(tile)
        opts = []
        for z in sorted({0, caster_z, pit_z}, reverse=True):
            tags = ([i18n.t("action.cast_floating_disk.ground")] if z == 0 else [])
            tags += [i18n.t("action.cast_floating_disk.caster")] if z == caster_z else []
            tags += [i18n.t("action.cast_floating_disk.pit_floor")] if z == pit_z and pit_z != 0 else []
            opts.append((z, f"z={z}" + (f" ({'/'.join(tags)})" if tags else "")))
        return opts

    def execute(self, battle, actor, target=None, elevation=None):
        if not self.can(battle, actor, target):
            return
        if elevation is None:
            elevation = battle.elevation(actor)
        elevation = int(elevation)
        actor.ap -= self.cost
        battle.log("log.floating_disk.casts", actor=actor.name, spell=self.spell_ref, z=elevation)
        battle.ground.append(GroundObject.disk(target, elevation=elevation))
        battle.clear_pf_cache()


class InvisibilityAction(SpellAction):
    """Level 2, every school: the caster vanishes from every other side's sight until it
    hurts someone (`conditions.Invisible`, `Combatant.hidden_from`)."""
    spell_id = "invisibility"
    cost = 2
    desc = i18n.Text("action", "desc")

    def available(self, battle, actor):
        return super().available(battle, actor) and not actor.has_condition("invisible")

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= self.cost
        actor.walking = False
        actor.add_condition(Invisible())
        battle.log("log.invisibility.casts", actor=actor.name, spell=self.spell_ref)


class RaiseDeadAction(SpellAction):
    """Level 2, Faith: a dead body in reach stands up again on the caster's side with 1 HP.
    A body raised once and fallen again stays down. The ground stirs where it rises, which
    is all an unseen caster gives away."""
    spell_id = "raise_dead"
    target, aimed = "cell", True
    cost = 2
    REACH = 6
    desc = i18n.Text("action", "desc", reach=REACH)

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
        battle.log("log.raise_dead.rises", cell=str(body.pos), body=body.name)
        battle.fx(body.pos, i18n.t("fx.rises"), "crit")


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
    cost = 1
    target = "none"

    @classmethod
    def applicable(cls, battle, actor):
        if not actor.char.has_talent("sprite_nature_initiate"):
            return False, i18n.t("action.share_magic.reason_initiate")
        if not actor.spells_known:
            return False, i18n.t("action.share_magic.reason_spells")
        return True, ""

    def available(self, battle, actor):
        return (actor.ap >= self.cost
                and actor.char.has_talent("sprite_nature_initiate")
                and len(actor.spells_known) > 0)

    def execute(self, battle, actor, target=None):
        if not self.available(battle, actor):
            return
        actor.ap -= self.cost

        allies = [u for u in battle.units if u.alive and u.team == actor.team and u != actor]
        if not allies:
            battle.log("log.share_magic.alone", actor=actor.name)
            return

        ally = random.choice(allies)
        spell_id = random.choice(actor.spells_known)
        spell = Ref("spell", spell_id, magic.SPELLS[spell_id].name if spell_id in magic.SPELLS else spell_id)

        if spell_id not in ally.spells_known:
            ally.spells_known.append(spell_id)
            battle.log("log.share_magic.learns", actor=actor.name, ally=ally.name, spell=spell)
        else:
            battle.log("log.share_magic.knows", actor=actor.name, ally=ally.name, spell=spell)
