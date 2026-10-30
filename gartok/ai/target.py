"""Target choice and finding foes: who to fight, where to flank, how to search or group up."""

from .. import actions, intel
from ..board import cells, grid_distance
from .common import _avg_die, _hand_die
from .reckon import _jet_avg


def _focus_key(battle, unit, foe):
    """How a unit ranks the foes it may hit: nearest first, then the lowest health it can tell
    (the exact hit points once read, the health step before that)."""
    exact = foe.hp if intel.knows(battle, unit.team, foe, "hp") else 99
    return (battle.units_distance(unit, foe), intel.health_steps(foe), exact)


def _flank_cell(battle, unit, target):
    """A cell the unit can walk to this turn, beside `target`, where an ally already at the foe makes
    a flank (+2 to hit): the nearest such cell, or None."""
    if unit.ranged or unit.ap < 1 or battle.units_distance(unit, target) <= 1:
        return None
    if not any(a.alive and a.team == unit.team and a is not unit and battle.units_distance(a, target) <= 1
               for a in battle.units):
        return None
    home, best = unit.pos, None
    for pos, cost in battle.reachable(unit).items():
        if battle.fire and any(c in battle.fire for c in cells(pos, unit.footprint)):
            continue
        unit.pos = pos
        try:
            flanks = battle.units_distance(unit, target) <= 1 and actions._flanked(battle, unit, target)
        finally:
            unit.pos = home
        if flanks and (best is None or cost < best[0]):
            best = (cost, pos)
    return best[1] if best else None


def _approach_reach(unit):
    """How close the unit needs to get to a foe to strike -- so the path stops
    there instead of always closing to adjacent. 1 normally; the Tongue's longer
    reach only when the lash is the attack it would actually pick (no hand weapon,
    or the tongue's die is at least as big) -- otherwise it keeps closing for the
    hand weapon and still lashes if the walk falls short."""
    if unit.has_tongue_weapon and (unit.unarmed or unit.improvised
                                   or _avg_die(unit.tongue_weapon["damage"]) >= _hand_die(unit)):
        return unit.tongue_reach
    spell_dmg = unit.talent_bonus("spell_damage")
    if "magic_missile" in getattr(unit, "spells_known", []) and _hand_die(unit) < 2.5 + spell_dmg:
        return 6 + int(unit.talent_bonus("spell_range"))
    if "water_jet" in getattr(unit, "spells_known", []) and _hand_die(unit) < _jet_avg(unit):
        return actions.WaterJetAction.reach(unit)
    if ("dragonfire" in getattr(unit, "spells_known", [])
            and _hand_die(unit) < _avg_die(actions.DragonfireAction.DICE) + spell_dmg):
        return actions.DragonfireAction.reach(unit)
    return 1 if unit.ranged else unit.attack_range


SEARCH_STEP = 4           # spacing of the waypoints an attacker sweeps


SEARCH_REACH = 3          # a waypoint counts as searched once a unit is this near


GROUP_GAP = 2             # a defender with nobody in sight closes to this far from an ally


def _role(battle, unit):
    """"attacker" for the side that brought the fight, "defender" for the other, None when neither did."""
    if battle.aggressor is None:
        return None
    return "attacker" if unit.team == battle.aggressor else "defender"


def _target(battle, unit):
    enemies = [u for u in battle.units if u.alive and u.team != unit.team and not u.hidden_from(unit.team)]
    if not enemies:
        return None
    visible = [e for e in enemies if battle.can_see_unit(unit, e)]
    if not visible and _role(battle, unit):
        # nobody in its own sight: it closes on what a teammate sees, else it searches or groups up
        visible = intel.visible_foes(battle, unit)
        if not visible:
            return None
    # no role (the arena): advance toward the nearest one anyway
    pool = visible or enemies
    if battle.is_ctf:
        # someone is running off with OUR flag -- stopping them beats whatever
        # else this unit would otherwise pick a fight over
        runner = battle.flag_carrier[unit.team]
        if runner and runner in enemies:
            return runner
    return min(pool, key=lambda e: _focus_key(battle, unit, e))


def _search_goal(battle, unit):
    """`(cell, reach)` an attacker walks to: the nearest place its side last saw a foe, and once
    that is empty a sweep of waypoints across the board, skipping the ones a teammate has been near."""
    memory = battle.intel.last_seen[unit.team]
    while memory:
        goal = min(memory.values(), key=lambda p: grid_distance(unit.pos, p))
        if grid_distance(unit.pos, goal) > 1:
            return goal, 1
        for foe in [f for f, p in memory.items() if p == goal]:     # it was here and is gone
            del memory[foe]
    board = battle.board
    visited = battle.intel.visited[unit.team]
    points = [(x, y) for x in range(SEARCH_STEP // 2, board.cols, SEARCH_STEP)
              for y in range(SEARCH_STEP // 2, board.rows, SEARCH_STEP) if (x, y) not in board.walls]
    for p in points:
        if any(u.alive and u.team == unit.team and grid_distance(u.pos, p) <= SEARCH_REACH for u in battle.units):
            visited.add(p)
    left = [p for p in points if p not in visited]
    if not left:
        visited.clear()
        left = points
    return (min(left, key=lambda p: grid_distance(unit.pos, p)), 0) if left else (None, 0)


def _search(battle, unit):
    """An attacker with nobody in sight goes looking. True if it moved."""
    goal, reach = _search_goal(battle, unit)
    if goal is None:
        return False
    dest = battle.path_step_toward(unit, goal, unit.speed, reach=reach)
    if dest == unit.pos:                      # walled off from it: do not try again
        battle.intel.visited[unit.team].add(goal)
        battle.intel.last_seen[unit.team] = {f: p for f, p in battle.intel.last_seen[unit.team].items() if p != goal}
        return False
    actions.MOVE.execute(battle, unit, dest)
    unit.walking = False
    return True


def _group_up(battle, unit):
    """A defender with nobody in sight closes on its nearest ally and holds there. True if it moved."""
    mates = [u for u in battle.units if u.alive and u.team == unit.team and u is not unit]
    if not mates:
        return False
    near = min(mates, key=lambda m: battle.units_distance(unit, m))
    if battle.units_distance(unit, near) <= GROUP_GAP:
        return False
    dest = battle.path_step_toward(unit, near.pos, unit.speed, reach=GROUP_GAP)
    if dest == unit.pos:
        return False
    actions.MOVE.execute(battle, unit, dest)
    unit.walking = False
    return True


def _no_contact(battle, unit):
    """What a unit does when no foe is in sight, by role. True if it spent a point."""
    role = _role(battle, unit)
    if role == "attacker":
        return _search(battle, unit)
    if role == "defender":
        return _group_up(battle, unit)
    return False
