"""Walking: the step toward a goal, terrain and traps in the way, picking things up."""

from .. import actions, intel, vision
from ..board import cells, grid_distance, line_cells
from .common import _other_side
from .target import _approach_reach


def _weapons_on_ground(battle):
    return [o for o in battle.ground if o.is_weapon]


def _recover_weapon(battle, unit):
    """True if the unit spent the action going after / picking up a dropped weapon."""
    weapons = _weapons_on_ground(battle)
    if not unit.unarmed or not weapons:
        return False
    if any(o.is_weapon for o in battle.ground_in_reach(unit)):
        actions.PICK_UP.execute(battle, unit)
        return True
    if battle.is_ctf and (getattr(unit, "ctf_runner", False)
                          or battle.flag_carrier.get(_other_side(unit.team)) is unit):
        return False                # the flag comes first: a runner never detours for a dropped blade
    obj = min(weapons, key=lambda o: grid_distance(unit.pos, o.pos))
    dest = battle.path_step_toward(unit, obj.pos, unit.speed)
    if dest == unit.pos:
        return False
    actions.MOVE.execute(battle, unit, dest)
    unit.walking = False
    if unit.ap > 0 and any(o.is_weapon for o in battle.ground_in_reach(unit)):
        actions.PICK_UP.execute(battle, unit)
    return True


def _torches_on_ground(battle):
    return [o for o in battle.ground if o.is_torch]


def _recover_torch(battle, unit):
    """If in the dark with no darkvision and no torch in hand, and cannot see
    any enemies, prioritize fetching a torch on the ground to illuminate."""
    if getattr(battle, "ambient_light", False) or vision.dark_range(unit) or unit.torch_hand:
        return False
    if unit.free_hands < 1:               # the torch would drop a two-hander, which it would then fetch back
        return False
    if any(battle.can_see_unit(unit, e) for e in battle.units if e.alive and e.team != unit.team):
        return False
    torches = _torches_on_ground(battle)
    if not torches:
        return False
    if any(o.is_torch for o in battle.ground_in_reach(unit)):
        actions.PICK_UP.execute(battle, unit)
        return True
    obj = min(torches, key=lambda o: grid_distance(unit.pos, o.pos))
    dest = battle.path_step_toward(unit, obj.pos, unit.speed)
    if dest == unit.pos:
        return False
    actions.MOVE.execute(battle, unit, dest)
    unit.walking = False
    if unit.ap > 0 and any(o.is_torch for o in battle.ground_in_reach(unit)):
        actions.PICK_UP.execute(battle, unit)
    return True


def _step_over_terrain(battle, unit, target):
    """The unit can't walk any nearer -- a pit lip or deep water is between it and
    the target. Climb / drop / swim onto the reachable cell that best closes on
    the target: nearer first, then matching its floor level so melee can connect.
    Acts only when that beats standing still. Returns True if it acted (a slipped
    climb still counts -- it spent the attempt)."""
    tz = battle.elevation(target)

    def score(cell):
        return (grid_distance(cell, target.pos),
                abs(battle.board.elevation_at(cell) - tz))

    now = score(unit.pos)
    best = None
    for act in (actions.CLIMB, actions.DROP, actions.SWIM, actions.JUMP):
        spots = _jump_spots(battle, unit) if act is actions.JUMP else act.highlight_cells(battle, unit)
        for c in spots:
            s = score(c)
            if s < now and act.can(battle, unit, c) and (best is None or s < best[0]):
                best = (s, act, c)
    if best is None:
        return False
    _, act, c = best
    act.execute(battle, unit, c)
    return True


def _jump_spots(battle, unit):
    """Cells a jump lands on with an average roll: in a clear line, no lower than a one-level drop
    (a longer one hurts), and nothing it could have walked to."""
    if not actions.JUMP.available(battle, unit):
        return []
    sure = actions.JUMP._reach(unit, 10 + unit.mod_strength)
    z = battle.elevation(unit)
    walk = battle.reachable(unit)
    spots = []
    for c in actions.JUMP.highlight_cells(battle, unit):
        if c in walk or grid_distance(unit.pos, c) > sure:
            continue
        if z - battle.elevation_at(c, unit) > 1:
            continue
        line = line_cells(unit.pos, c)[1:]
        if all(p not in battle.board.walls and actions._cell_free(battle, unit, p) for p in line):
            spots.append(c)
    return spots


def trap_cell(battle, trapper):
    """Where an unplayed squad plants `trapper`'s next trap: the open cell closest to a foe."""
    foes = [u for u in battle.units if u.alive and u.team != trapper.team]
    spots = battle.trap_cells(trapper)
    if not foes or not spots:
        return None
    return min(spots, key=lambda c: min(grid_distance(c, f.pos) for f in foes))


def _visible_traps(battle, unit):
    """Traps that would spring under `unit` and that it can see."""
    return [o for o in battle.ground if o.is_trap and battle.springs(o, unit)
            and vision.can_see(battle, unit, o.pos)]


def _trap_avoid(battle, unit):
    return frozenset(o.pos for o in _visible_traps(battle, unit))


def _try_disarm(battle, unit, target):
    """Clear a trap beside the unit that stands on its way to `target` with no way round. Only
    when the trap Disarm would pick is one that springs on this unit."""
    disarm = actions.DISARM
    if not disarm.available(battle, unit):
        return False
    first = disarm._adjacent_traps(battle, unit)[0]
    if first not in _visible_traps(battle, unit):
        return False
    reach = _approach_reach(unit)
    walk = battle.path_step_toward(unit, target.pos, unit.speed, reach=reach)
    if walk == unit.pos or first.pos not in battle.path_to(unit, walk):
        return False
    disarm.execute(battle, unit)
    return True


def _try_secret(battle, unit):
    """Stalled beside a wall the Investigate button reads as a secret: open it."""
    if not actions.INVESTIGATE.available(battle, unit) or not actions.INVESTIGATE._adjacent_secrets(battle, unit):
        return False
    actions.INVESTIGATE.execute(battle, unit)
    return True


def _try_assess(battle, unit):
    """With nothing better to spend a point on, read the foe in sight it knows least about."""
    if not actions.ASSESS.available(battle, unit):
        return False
    foes = [f for f in intel.visible_foes(battle, unit) if actions.ASSESS.can(battle, unit, f)]
    foes = [f for f in foes if battle.intel.margin[unit.team].get(f, -99) < intel.HARD]
    if not foes:
        return False
    foe = min(foes, key=lambda f: battle.intel.margin[unit.team].get(f, -99))
    actions.ASSESS.execute(battle, unit, foe)
    return True


def _step_toward(battle, unit, goal, reach):
    """`path_step_toward`, around the flames and the traps it can see when a way round exists."""
    traps = _trap_avoid(battle, unit)
    avoid = traps | (battle.fire_avoid(unit) if battle.fire else frozenset())
    if avoid:
        dest = battle.path_step_toward(unit, goal, unit.speed, reach=reach, avoid=avoid)
        if dest != unit.pos:
            return dest
    dest = battle.path_step_toward(unit, goal, unit.speed, reach=reach)
    return _short_of_traps(battle, unit, dest, traps)


def _short_of_traps(battle, unit, dest, traps):
    """`dest`, or the last cell of the walk there before it would step on one of `traps`."""
    if not traps or dest == unit.pos:
        return dest
    route = battle.path_to(unit, dest)
    for i, c in enumerate(route[1:], start=1):
        if any(p in traps for p in cells(c, unit.footprint)):
            return route[i - 1]
    return dest


def _sight_cell(battle, unit, target):
    """A step toward a cell beside `target` with a clear line to it, for a unit that stands next to a
    foe it cannot see (across a wall corner); None when it sees the foe or no such cell is reachable."""
    if battle.can_see_unit(unit, target):
        return None
    board = battle.board
    goals = [p for p in board.neighbors(target.pos)
             if p not in board.walls and (battle.unit_at(p) in (None, unit)) and board.los_clear(p, target.pos)]
    dest = _reachable_step(battle, unit, goals, reach=0)
    return dest if dest is not None and dest != unit.pos else None


def _reachable_step(battle, unit, goals, reach=1):
    """The step toward the nearest of `goals` (ground objects or cells) the unit can get to, or None."""
    cells = [getattr(g, "pos", g) for g in goals]
    for goal in sorted(cells, key=lambda c: grid_distance(unit.pos, c)):
        if battle.can_reach(unit, goal, reach):
            return battle.path_step_toward(unit, goal, unit.speed, reach=reach)
    return None
