"""Enemy squad AI.

Simple heuristic over `actions.py`: if unarmed, recover the dropped weapon;
otherwise spend the points attacking the weakest target in range (or demoralize
it if out of reach); otherwise advance. Sees through each unit's own eyes.

**Tendency colours the edges** (§8 / "Fugir do combate" in GARTOK-regras.md), on
the morality axis mostly:
- **Mau** finishes downed enemies -- a coup de grace on an adjacent body, so the
  player cannot stabilize it. Only in a lethal fight (the arena knocks out anyway).
- **Bom** stabilizes an adjacent downed ally before doing anything else, and when
  it does run it drags the wounded out with it (that part is in `Flee.execute`).
- **Caótico** breaks and runs sooner; **Leal** holds the line while any ally
  still stands.
"""

from . import actions, data
from .board import chebyshev


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
    obj = min(weapons, key=lambda o: chebyshev(unit.pos, o.pos))
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

        if actions.ATTACK.can(battle, unit, target):
            actions.ATTACK.execute(battle, unit, target)
            continue

        if not target.demoralized and actions.DEMORALIZE.can(battle, unit, target):
            actions.DEMORALIZE.execute(battle, unit, target)
            continue

        dest = battle.path_step_toward(unit, target.pos, unit.speed)
        if dest == unit.pos:
            # cornered and out of range: defend (once) and end
            if actions.DEFEND.available(battle, unit):
                actions.DEFEND.execute(battle, unit)
            break
        battle.move_unit(unit, dest)
        unit.walking = False  # close the walk; the next action spends another point

        if unit.ap > 0 and actions.ATTACK.can(battle, unit, target):
            actions.ATTACK.execute(battle, unit, target)

    battle.end_turn()
