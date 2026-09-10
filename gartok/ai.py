"""Enemy squad AI.

Simple heuristic over `actions.py`: if unarmed, recover the dropped weapon; if
holding an empty crossbow, reload it; otherwise spend the points attacking the
weakest target in range (or demoralize it if out of reach); otherwise advance.
Sees through each unit's own eyes.

**Tendency colours the edges** (§8 / "Fleeing" in RULES.md), on
the morality axis mostly:
- **Evil** finishes downed enemies -- a coup de grace on an adjacent body, so the
  player cannot stabilize it. Only in a lethal fight (the arena knocks out anyway).
- **Good** stabilizes an adjacent downed ally before doing anything else, and when
  it does run it drags the wounded out with it (that part is in `Flee.execute`).
- **Chaotic** breaks and runs sooner; **Lawful** holds the line while any ally
  still stands.
"""

from . import actions, data
from .board import grid_distance


def _axes(unit):
    """(order, morality) of the unit's tendency, each in {-1, 0, 1}."""
    return data.alignment_axes(unit.alignment)


def _target(battle, unit):
    enemies = [u for u in battle.units if u.alive and u.team != unit.team]
    if not enemies:
        return None
    visible = [e for e in enemies if battle.can_see_unit(unit, e)]
    # nobody in sight: advance toward the nearest one anyway
    pool = visible or enemies
    return min(pool, key=lambda e: (battle.units_distance(unit, e), e.hp))


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
    obj = min(weapons, key=lambda o: grid_distance(unit.pos, o.pos))
    dest = battle.path_step_toward(unit, obj.pos, unit.speed)
    if dest == unit.pos:
        return False
    battle.move_unit(unit, dest)
    unit.walking = False
    if unit.ap > 0 and any(o.is_weapon for o in battle.ground_in_reach(unit)):
        actions.PICK_UP.execute(battle, unit)
    return True


def _finish_off(battle, unit):
    """A downed enemy body this unit could hit right now -- dying (an instakill)
    before merely stable, nearest first. Only when the fight is lethal and the
    unit is of evil bent."""
    if not battle.lethal or _axes(unit)[1] >= 0:
        return None
    bodies = sorted((u for u in battle.units if u.team != unit.team and u.downed),
                    key=lambda u: (not u.dying, battle.units_distance(unit, u)))
    return next((b for b in bodies if actions.ATTACK.can(battle, unit, b)), None)


def _ally_to_help(battle, unit):
    """An adjacent downed ally this unit can stabilize -- only if it is of good
    bent (it will spend the action to save a friend before fighting)."""
    if _axes(unit)[1] <= 0:
        return None
    return next((a for a in battle.units
                 if actions.STABILIZE.can(battle, unit, a)), None)


def _step_over_elevation(battle, unit, target):
    """The unit can't walk any nearer -- a pit lip is between it and the target.
    Climb (or, failing a climb spot, drop) onto the adjacent cell that best
    closes on the target: nearer first, then matching its floor level so melee
    can connect. Acts only when that beats standing still. Returns True if it
    acted (a slipped climb still counts -- it spent the attempt)."""
    tz = battle.elevation(target)

    def score(cell):
        return (grid_distance(cell, target.pos),
                abs(battle.board.elevation_at(cell) - tz))

    now = score(unit.pos)
    best = None
    for act in (actions.CLIMB, actions.DROP):
        for c in act.highlight_cells(battle, unit):
            s = score(c)
            if s < now and act.can(battle, unit, c) and (best is None or s < best[0]):
                best = (s, act, c)
    if best is None:
        return False
    _, act, c = best
    act.execute(battle, unit, c)
    return True


def _ctf_goal(battle, unit):
    """The cell a capture-the-flag runner is racing for -- the player's flag, once
    it has been planted. None for a non-runner, or before the flag is down."""
    if not battle.is_ctf or not unit.ctf_runner:
        return None
    return battle.flags["player"]


def _should_flee(battle, unit):
    """Whether the unit breaks and runs this turn. Never from a non-lethal bout
    (the arena -- nobody dies). Needs a map edge and a clean getaway
    (`FLEE.available`). Chaotic units break sooner and while less outnumbered;
    lawful units stay while any ally is still standing."""
    if not battle.lethal or not actions.FLEE.available(battle, unit):
        return False
    order = _axes(unit)[0]
    allies = [u for u in battle.units
              if u.alive and u.team == unit.team and u is not unit]
    foes = [u for u in battle.units if u.alive and u.team != unit.team]
    if not foes:
        return False
    if order > 0 and allies:                 # lawful: hold the line
        return False
    hurt = unit.hp <= unit.hp_max * (0.5 if order < 0 else 0.34)
    outmatched = len(foes) > len(allies) + (0 if order < 0 else 1)
    return hurt and outmatched


def take_turn(battle, unit):
    for _ in range(4):  # safety stop; a turn spends at most 2 points
        if unit.ap <= 0 or not unit.alive:
            break

        ally = _ally_to_help(battle, unit)
        if ally is not None:                  # good: save the friend first
            actions.STABILIZE.execute(battle, unit, ally)
            continue

        goal = _ctf_goal(battle, unit)
        if goal is not None:                  # flag runner: race for the player's flag
            if goal in battle.cells_of(unit):
                break                         # on it -- end_turn calls the capture
            # step ONTO the flag cell (not adjacent, the way `path_step_toward`
            # stops next to a unit) -- a downed body lying on it does not block.
            reach = battle.reachable(unit)
            route = battle.path_to(unit, goal)
            step = goal if goal in reach else next(
                (c for c in reversed(route) if c in reach), None)
            if step is not None and step != unit.pos:
                battle.move_unit(unit, step)
                unit.walking = False
                continue
            # genuinely walled off from the flag -- fight through this turn

        if _should_flee(battle, unit):
            actions.FLEE.execute(battle, unit)
            break

        body = _finish_off(battle, unit)
        if body is not None:                  # evil: put the downed enemy away
            actions.ATTACK.execute(battle, unit, body)
            continue

        if _recover_weapon(battle, unit):
            continue

        target = _target(battle, unit)
        if target is None:
            break

        # a crossbow only fires loaded -- keep it fed instead of closing to melee
        if unit.can_reload:
            actions.RELOAD.execute(battle, unit)
            continue

        if actions.ATTACK.can(battle, unit, target):
            actions.ATTACK.execute(battle, unit, target)
            continue

        if not target.demoralized and actions.DEMORALIZE.can(battle, unit, target):
            actions.DEMORALIZE.execute(battle, unit, target)
            continue

        dest = battle.path_step_toward(unit, target.pos, unit.speed)
        if dest == unit.pos:
            # can't walk any closer -- maybe a pit is in the way. try to climb or
            # drop toward the target so the fight doesn't stall out.
            if _step_over_elevation(battle, unit, target):
                continue
            # cornered and out of range: defend (once) and end
            if actions.DEFEND.available(battle, unit):
                actions.DEFEND.execute(battle, unit)
            break
        battle.move_unit(unit, dest)
        unit.walking = False  # close the walk; the next action spends another point

        if unit.ap > 0 and actions.ATTACK.can(battle, unit, target):
            actions.ATTACK.execute(battle, unit, target)

    battle.end_turn()
