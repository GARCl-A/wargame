"""The turns a scenario scripts: capture the flag, patrols, the heist, the necromancer."""

from .. import actions
from ..board import grid_distance
from .common import _other_side
from .movement import _reachable_step, _step_toward


def _ally_carries_flag(battle, unit):
    return any(c is not None and c.alive and c.team == unit.team for c in battle.flag_carrier.values())


def _clear_of(battle, unit, home):
    """A runner is bringing the enemy flag home and scores only by standing on `home`: a guard on
    it steps to a free neighbouring cell, anyone else stays put."""
    if home not in battle.cells_of(unit):
        return None
    taken = {c for u in battle.units if u.alive for c in battle.cells_of(u)}
    free = [c for c in battle.reachable(unit) if c not in taken and grid_distance(c, home) == 1]
    return min(free, key=lambda c: grid_distance(c, unit.pos), default=None)


def _ctf_goal(battle, unit):
    """The cell a capture-the-flag runner or defender is racing for:
    - a runner heads for the other side's flag, then races it home to score;
    - a non-runner defends their own side's flag by standing directly on its square.
    None before both flags are down or if an ally already guards the home flag."""
    if not battle.is_ctf:
        return None
    if battle.flags["player"] is None or battle.flags["enemy"] is None:
        return None
    if getattr(unit, "ctf_runner", False):
        theirs = _other_side(unit.team)
        if battle.flag_carrier[theirs] is unit:
            return battle.flags[unit.team]        # got it -- now get it home
        if battle.flag_carrier[theirs] is None:
            return battle.flag_pos(theirs)        # not carrying yet: go get it
        return None                               # a mate has it: fight on

    # Non-runner / defender:
    # If the team's flag is currently stolen, pursue the carrier (handled by _target).
    if battle.flag_carrier.get(unit.team) is not None:
        return None
    home = battle.flags.get(unit.team)
    if home is None:
        return None
    if _ally_carries_flag(battle, unit):
        return _clear_of(battle, unit, home)
    # If another living ally is already guarding directly on the flag, do not crowd it
    guardian = next((u for u in battle.units
                     if u.alive and u.team == unit.team and u is not unit and home in battle.cells_of(u)), None)
    if guardian is not None:
        return None
    # Closest living non-runner takes the post on the flag
    defenders = [u for u in battle.units
                 if u.alive and u.team == unit.team and not getattr(u, "ctf_runner", False)]
    if defenders and min(defenders, key=lambda d: grid_distance(d.pos, home)) is unit:
        return home
    return None


NECRO_KEEP_AWAY = 3          # the raiser backs off from a foe that has found it this close


def _necromancy(battle, unit):
    """A raiser's turn (Raise Dead known): vanish when it can, raise the strongest body in reach,
    walk toward the nearest one, back away from a foe that found it. It never attacks while a
    body is left to raise. -> "acted", "hold" (nothing worth the AP: end the turn) or None (no
    raiser, or no bodies left: fight on as usual)."""
    if "raise_dead" not in getattr(unit, "spells_known", ()):
        return None
    raise_dead = actions.CastSpellAction("raise_dead")
    bodies = raise_dead.bodies(battle)
    if not bodies:
        return None
    hunters = [e for e in battle.units if e.alive and e.team != unit.team and not unit.hidden_from(e.team)
               and battle.units_distance(unit, e) <= NECRO_KEEP_AWAY]
    if hunters and not unit.walking and unit.ap >= 1:
        def gap(p):
            return min(grid_distance(p, e.pos) for e in hunters)
        away = max(battle.reachable(unit), key=gap, default=unit.pos)
        if gap(away) > gap(unit.pos):
            actions.MOVE.execute(battle, unit, away)
            unit.walking = False
            return "acted"
    if "invisibility" in getattr(unit, "spells_known", ()) and not hunters:
        vanish = actions.CastSpellAction("invisibility")
        if vanish.available(battle, unit):
            vanish.execute(battle, unit)
            return "acted"
    in_reach = [b for b in bodies if raise_dead.can(battle, unit, b.pos)]
    if in_reach:
        if unit.ap < raise_dead.cost:
            return "hold"
        raise_dead.execute(battle, unit, max(in_reach, key=lambda b: b.hp_max).pos)
        return "acted"
    if unit.ap < 1 or unit.walking:
        return "hold"
    near = min(bodies, key=lambda b: battle.units_distance(unit, b))
    dest = _step_toward(battle, unit, near.pos, raise_dead.spell_range(unit, raise_dead.REACH))
    if dest == unit.pos:
        return "hold"
    actions.MOVE.execute(battle, unit, dest)
    unit.walking = False
    return "acted"


def _patrol(battle, unit):
    """A patrol on its rounds (`lair.py`): a foe it sees within its sight goes to the scenario's
    `contact` (a challenge, a parley or the alarm); otherwise it walks on to its next waypoint.
    True when its turn is spent; False when it now fights."""
    seen = [e for e in battle.units if e.alive and e.team == "player"
            and battle.can_see_unit(unit, e) and battle.units_distance(unit, e) <= unit.awareness_radius]
    if seen:
        verdict = battle.scenario.contact(battle, unit, seen)
        if verdict == "fight":
            return False
        if verdict == "wait":
            unit.ap = 0
            battle.end_turn()
            return True
    route = unit.patrol_route
    goal = route[unit.patrol_step % len(route)]
    if grid_distance(unit.pos, goal) <= 1:
        unit.patrol_step += 1
        goal = route[unit.patrol_step % len(route)]
    dest = _step_toward(battle, unit, goal, reach=1)
    if dest != unit.pos:
        actions.MOVE.execute(battle, unit, dest)
        unit.walking = False
    if battle.winner is None and battle.active is unit:
        battle.end_turn()
    return True


def _heist(battle, unit):
    """The squad's side in a heist (`lair.py`): leave the moment the scenario allows it, lift what
    is in reach, and otherwise make for the scenario's goal -- at a creep (half speed) while the
    thing it robs still sleeps. A foe on top of it is fought instead. True when the turn is spent."""
    if battle.can_withdraw:
        battle.withdraw()
        return True
    if any(f.alive and getattr(f, "alerted", False) and battle.units_distance(unit, f) <= 1
           for f in battle.foe_units):
        return False
    if actions.PICK_UP.available(battle, unit) and any(o.is_relic for o in battle.ground_in_reach(unit)):
        actions.PICK_UP.execute(battle, unit)
    aim = battle.scenario.heist_goal(battle, unit)
    if aim is None:
        if battle.winner is None and battle.active is unit:
            battle.end_turn()             # in place: wait for the rest
        return True
    goal, reach = aim
    budget = unit.speed if battle.scenario.stage == "awake" else unit.speed // 2
    dest = battle.path_step_toward(unit, goal, max(1, budget), reach=reach)
    if dest == unit.pos and grid_distance(unit.pos, goal) > reach:
        return False                      # walled off from it: fight instead
    if dest != unit.pos and unit.ap >= 1:
        actions.MOVE.execute(battle, unit, dest)
        unit.walking = False
    if battle.can_withdraw:
        battle.withdraw()
        return True
    if battle.winner is None and battle.active is unit:
        battle.end_turn()
    return True


def _fetch(battle, unit):
    """Every foe is down and the scenario still holds the field (`Scenario.holds_field`): lift what
    lies in reach, walk to the nearest chest or relic it can reach, and with none left make for
    the way out and flee through it. True when the turn is spent."""
    if any(f.alive for f in battle.foe_units):
        return False
    treasure = battle.scenario.treasure_on_floor(battle)
    while (actions.PICK_UP.available(battle, unit)
           and any(o in treasure for o in battle.ground_in_reach(unit))):
        actions.PICK_UP.execute(battle, unit)
        treasure = battle.scenario.treasure_on_floor(battle)
    dest = (_reachable_step(battle, unit, treasure)
            or _reachable_step(battle, unit, sorted(battle.escape_cells), reach=0))
    if dest is not None and dest != unit.pos and unit.ap >= 1:
        actions.MOVE.execute(battle, unit, dest)
        unit.walking = False
    if actions.FLEE.available(battle, unit) and _reachable_step(battle, unit, treasure) is None:
        actions.FLEE.execute(battle, unit)
    battle.check_objective()
    if battle.winner is None and battle.active is unit:
        battle.end_turn()
    return True
