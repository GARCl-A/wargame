"""Movement actions: Move, the Free Step, and the Z axis (Climb, Drop in, Jump, Swim, Fly up, Fly down)."""

from .. import i18n
from ..board import cells, cells_in_radius, grid_distance, line_cells
from ..combatant import PINNING
from ..data import d20
from ..i18n import Msg
from .base import Action, _cell_free

JUMP_DIVISOR = 5          # Jump: (d20 + Strength) / this = squares cleared, capped at speed
SWIM_DIVISOR = 5          # Swim: (d20 + Strength) / this = squares crossed, capped at half speed
MAX_ALTITUDE = 4          # levels a flier can hover above the floor


# --------------------------------------------------------------------------- #
# Move                                                                         #
# --------------------------------------------------------------------------- #

class Move(Action):
    id, cost, target = "move", 1, "cell"
    announce = False

    def available(self, battle, actor):
        if getattr(actor, "mounted_on", None) is not None:
            return False
        return bool(battle.reachable(actor))

    def can(self, battle, actor, target=None):
        if getattr(actor, "mounted_on", None) is not None:
            return False
        return target in battle.reachable(actor)

    def blocked_reason(self, battle, actor):
        """Why the actor cannot walk now, or "" when it can: the line the battle's hint shows."""
        if self.available(battle, actor):
            return ""
        if getattr(actor, "mounted_on", None) is not None:
            return i18n.t("action.move_blocked.mounted")
        for cond in ("entangled", "grappled", "prone"):
            if actor.has_condition(cond):
                return i18n.t(f"action.move_blocked.{cond}")
        if actor.walking:
            return i18n.t("action.move_blocked.spent")
        if actor.ap < 1:
            return i18n.t("action.move_blocked.no_ap")
        return i18n.t("action.move_blocked.boxed_in")

    def execute(self, battle, actor, target=None):
        if getattr(actor, "mounted_on", None) is not None:
            return
        battle.move_unit(actor, target)

    def highlight_cells(self, battle, actor):
        return list(battle.reachable(actor))

    def highlight_targets(self, battle, actor):
        return []




class FreeStep(Action):
    """The Free Step talent: one square of walking once a turn that costs no action point, the step
    taken to reach a flank. It rides on `Battle.move_unit` as a walk that is already under way, so the
    fire, the traps and the hidden foes treat it like any other step; the walk it leaves behind is the
    one the unit had."""
    id, cost, target = "free_step", 0, "cell"
    announce = False

    def _spots(self, battle, actor):
        if not actor.talent_bonus("free_step") or actor.free_step_used or getattr(actor, "mounted_on", None) is not None:
            return []
        walk = battle.reachable(actor, budget=1)
        return [c for c, cost in walk.items() if c != actor.pos and cost <= 1]

    def available(self, battle, actor):
        return bool(self._spots(battle, actor))

    def can(self, battle, actor, target=None):
        return isinstance(target, tuple) and target in self._spots(battle, actor)

    def label(self, battle, actor):
        return i18n.t("action.free_step.label")

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.free_step_used = True
        kept = (actor.walking, actor.moved, actor.diag_steps)
        actor.walking, actor.moved, actor.diag_steps = True, 0, 0
        battle.log("log.free_step", unit=actor.name)
        try:
            battle.move_unit(actor, target)
        finally:
            actor.walking, actor.moved, actor.diag_steps = kept

    def highlight_cells(self, battle, actor):
        return self._spots(battle, actor)

    def highlight_targets(self, battle, actor):
        return []


class _VerticalStep(Action):
    """Shared base for the single-square elevation moves (Climb / Drop in): the
    candidate cells are the adjacent ones at a different floor height."""

    target, aimed = "cell", True

    def _spots(self, battle, actor):
        if actor.has_condition("prone"):
            return []
        z = battle.elevation(actor)
        return [nb for nb in battle.board.neighbors(actor.pos)
                if self._wants(battle.board.elevation_at(nb), z)
                and _cell_free(battle, actor, nb)
                and not battle.board.diagonal_corner_blocked(actor.pos, nb)]

    def _wants(self, z_nb, z_here):
        raise NotImplementedError

    def available(self, battle, actor):
        return actor.ap >= self.cost and bool(self._spots(battle, actor))

    def can(self, battle, actor, target=None):
        return (actor.ap >= self.cost and isinstance(target, tuple)
                and target in self._spots(battle, actor))

    def highlight_cells(self, battle, actor):
        return self._spots(battle, actor)

    def highlight_targets(self, battle, actor):
        return []


class Climb(_VerticalStep):
    """Haul yourself one square up or down a pit wall. Strength vs the surface DC
    (bare stone 15, a rope 10); the Lizardfolk's Climber clears it with no roll.
    A slip just costs the action."""

    id, cost = "climb", 1

    def _wants(self, z_nb, z_here):
        return z_nb != z_here

    def label(self, battle, actor):
        return i18n.t("action.climb.label")

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        z_from = battle.elevation(actor)
        z_to = battle.elevation_at(target, actor)
        low_cell = target if z_to < z_from else actor.pos
        dc = battle.board.surface_dc(low_cell)
        way = Msg("log.climb.down" if z_to < z_from else "log.climb.up")
        if actor.auto_climb(dc):
            actor.pos = target
            actor.z = z_to
            battle.log("log.climb.auto", actor=actor.name, way=way)
            return
        nat = d20()
        total = nat + actor.mod_strength
        roll = Msg("log.climb.roll", actor=actor.name, way=way, nat=nat, str=actor.mod_strength, total=total, dc=dc)
        if nat == 20 or total >= dc:
            actor.pos = target
            actor.z = z_to
            battle.log("log.climb.over" if z_to > z_from else "log.climb.clear", roll=roll)
        else:
            battle.log("log.climb.slips", roll=roll)


class DropIn(_VerticalStep):
    """Throw yourself into the pit -- a deliberate drop into a lower adjacent
    square, no check, but you take the fall (every level past the first is 1d6)."""

    id, cost = "drop", 1

    def _wants(self, z_nb, z_here):
        return z_nb < z_here

    def label(self, battle, actor):
        return i18n.t("action.drop.label")

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        z_from = battle.elevation(actor)
        z_to = battle.elevation_at(target, actor)
        actor.pos = target
        actor.z = z_to
        battle.log("log.drop.into", actor=actor.name, cell=str(target))
        battle.apply_fall(actor, z_from - z_to, battle.log)


class _Hover(Action):
    """Shared base for Fly up / Fly down: a flier changing how high it hovers, paid out of its walking
    speed like any step (the first one opens a walk, 1 point). No target; the AI and the bar both
    read `available`."""

    cost, target = 1, "none"
    announce = False
    squares = 1                          # movement squares one level costs

    def _free(self, actor):
        return not (any(actor.has_condition(c) for c in PINNING) or getattr(actor, "mounted_on", None) is not None)

    def _room(self, actor):
        raise NotImplementedError

    def available(self, battle, actor):
        return (actor.flies and self._free(actor) and self._room(actor)
                and battle.can_spend_walk(actor, self.squares))

    def can(self, battle, actor, target=None):
        return self.available(battle, actor)

    def label(self, battle, actor):
        return i18n.t(f"action.{self.id}.label", n=self.squares)

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        battle.spend_walk(actor, self.squares)
        actor.altitude += self.step
        battle.log(f"log.{self.id}", actor=actor.name, n=actor.altitude)


class FlyUp(_Hover):
    """Climb one level of air. Rising is hard going -- double the squares of a plain step -- so a
    flier of speed 6 gains three levels from a whole walk. Past a foe's reach it cannot be struck in melee."""

    id, step, squares = "fly_up", 1, 2

    def _room(self, actor):
        return actor.altitude < MAX_ALTITUDE


class FlyDown(_Hover):
    """Sink one level toward the ground: a plain step's worth of movement."""

    id, step, squares = "fly_down", -1, 1

    def _room(self, actor):
        return actor.altitude > 0


class Jump(Action):
    """A running jump: d20 + Strength, clear (result / 5) squares (never more than
    your speed) straight toward the aimed cell, sailing over any pit in between.
    A wall or a body ends the jump short; land lower than you left and you fall."""

    id, cost, target, aimed = "jump", 1, "cell", True

    @staticmethod
    def _reach(actor, total):
        """Squares a jump of `total` clears: never past your speed, plus Frog Leap's squares."""
        return max(0, min(total // JUMP_DIVISOR, actor.speed)) + int(actor.char.talent_bonus("jump_reach"))

    def _max_reach(self, battle, actor):
        if any(actor.has_condition(c) for c in ("prone", "entangled", "grappled")):
            return 0
        return self._reach(actor, 20 + actor.mod_strength)

    def available(self, battle, actor):
        return actor.ap >= self.cost and self._max_reach(battle, actor) >= 1

    def can(self, battle, actor, target=None):
        if actor.ap < self.cost or not isinstance(target, tuple):
            return False
        if not battle.board.in_bounds(target) or target == actor.pos:
            return False
        return grid_distance(actor.pos, target) <= self._max_reach(battle, actor)

    def label(self, battle, actor):
        return i18n.t("action.jump.label")

    def highlight_cells(self, battle, actor):
        r = self._max_reach(battle, actor)
        return [p for p in cells_in_radius(actor.pos, r) if battle.board.in_bounds(p)]

    def highlight_targets(self, battle, actor):
        return []

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        nat = d20()
        total = nat + actor.mod_strength
        dist = self._reach(actor, total)
        landing = actor.pos
        for step, cell in enumerate(line_cells(actor.pos, target)[1:], start=1):
            if step > dist or cell in battle.board.walls \
                    or not _cell_free(battle, actor, cell):
                break
            landing = cell
        z_from = battle.elevation(actor)
        z_to = battle.elevation_at(landing, actor)
        actor.pos = landing
        actor.z = z_to
        battle.log("log.jump", actor=actor.name, nat=nat, str=actor.mod_strength, total=total, dist=dist, cell=str(landing))
        if z_to < z_from:
            battle.apply_fall(actor, z_from - z_to, battle.log)


class Swim(Action):
    """Strike out through deep water: d20 + Strength, cross (result / 5) squares
    toward the aimed cell, never more than half your speed. You swim only through
    water -- a wall, a body or the water's edge ends the swim there (haul yourself
    out of the pit with a Climb). No check to stay afloat; a poor roll just means
    a short swim."""

    id, cost, target, aimed = "swim", 1, "cell", True

    @staticmethod
    def _touches(battle, actor, anchor):
        """Some cell of the body would be in deep water at `anchor`."""
        return any(battle.board.is_deep_water(c) for c in cells(anchor, actor.footprint))

    @staticmethod
    def _afloat(battle, actor, anchor):
        """The whole body would be in deep water at `anchor`. A Large body is never half in and half out: the cell where
        it only touches the water is passed through (it costs a square of the swim), never stopped on."""
        return all(battle.board.is_deep_water(c) for c in cells(anchor, actor.footprint))

    def _at_water(self, battle, actor):
        """The actor is in deep water, or on a cell touching it (can push off)."""
        for c in battle.cells_of(actor):
            if battle.board.is_deep_water(c):
                return True
            if any(battle.board.is_deep_water(nb) for nb in battle.board.neighbors(c)):
                return True
        return False

    @staticmethod
    def _squares(actor, rolled):
        """Squares a swim covers: the roll plus the talent, capped at half speed (plus the talent) and at full speed."""
        bonus = actor.char.talent_bonus("swim_reach")
        return max(1, min(rolled + bonus, actor.speed, max(1, actor.speed // 2) + bonus))

    def _max_reach(self, battle, actor):
        return self._squares(actor, (20 + actor.mod_strength) // SWIM_DIVISOR)

    def available(self, battle, actor):
        return (actor.ap >= self.cost and not actor.flies and not actor.has_condition("prone")
                and self._at_water(battle, actor))

    def can(self, battle, actor, target=None):
        if actor.ap < self.cost or actor.flies or actor.has_condition("prone") or not isinstance(target, tuple):
            return False
        if not battle.board.in_bounds(target) or target == actor.pos:
            return False
        if not self._at_water(battle, actor):
            return False
        if grid_distance(actor.pos, target) > self._max_reach(battle, actor):
            return False
        line = line_cells(actor.pos, target)[1:self._max_reach(battle, actor) + 1]
        return (self._touches(battle, actor, line[0]) and _cell_free(battle, actor, line[0])
                and any(self._afloat(battle, actor, c) for c in line))

    def label(self, battle, actor):
        return i18n.t("action.swim.label")

    def highlight_cells(self, battle, actor):
        r = self._max_reach(battle, actor)
        return [p for p in cells_in_radius(actor.pos, r)
                if battle.board.in_bounds(p)
                and (self._afloat(battle, actor, p) or grid_distance(actor.pos, p) == 1)]

    def highlight_targets(self, battle, actor):
        return []

    def execute(self, battle, actor, target=None):
        if not self.can(battle, actor, target):
            return
        actor.ap -= 1
        actor.walking = False
        nat = d20()
        total = nat + actor.mod_strength
        dist = self._squares(actor, total // SWIM_DIVISOR)
        landing = actor.pos
        for step, cell in enumerate(line_cells(actor.pos, target)[1:], start=1):
            if step > dist or cell in battle.board.walls \
                    or not _cell_free(battle, actor, cell):
                break
            if self._afloat(battle, actor, cell):
                landing = cell
            elif not self._touches(battle, actor, cell):
                break                        # left the water -- climb out from here
        z_from = battle.elevation(actor)
        z_to = battle.board.elevation_at(landing)
        actor.pos = landing
        battle.log("log.swim", actor=actor.name, nat=nat, str=actor.mod_strength, total=total,
                   dist=total // SWIM_DIVISOR, cell=str(landing))
        if z_to < z_from:
            battle.apply_fall(actor, z_from - z_to, battle.log)
