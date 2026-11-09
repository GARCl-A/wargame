"""One AI turn: `take_turn` runs the checks of the other modules in order."""

from .. import actions
from ..board import grid_distance
from .attack import (
    _breath_spot,
    _demoralize_victim,
    _eat_corpse,
    _finish_off,
    _pick_attack,
    _rider,
    _spin_web,
    _try_breath,
    _try_capture,
    _try_shove,
    _try_throw,
)
from .common import _spell_can, _wants_alive
from .flee import (
    _is_skittish,
    _leave_fire,
    _run_for_the_exit,
    _should_delay,
    _should_flee,
    _skitter,
    _try_escape_grapple,
    _try_stand_up,
    _try_vanish,
)
from .movement import (
    _adjust_altitude,
    _assess_target,
    _light_globe,
    _recover_shield,
    _recover_torch,
    _recover_weapon,
    _sight_cell,
    _step_over_terrain,
    _step_toward,
    _try_assess,
    _try_disarm,
    _try_secret,
)
from .scripted import (
    _ally_carries_flag,
    _ctf_goal,
    _fetch,
    _heist,
    _necromancy,
    _patrol,
)
from .support import (
    _ally_to_help,
    _sleeps_beyond_turn,
    _try_drink_potion,
    _try_healing_touch,
    _try_lift_rider,
    _try_mount,
    _try_pixie_dust,
    _try_share_magic,
    _try_signal_horn,
)
from .target import (
    _approach_reach,
    _flank_cell,
    _flank_step,
    _free_approach,
    _no_contact,
    _target,
)


def take_turn(battle, unit):
    if unit.dormant:
        enemies = [u for u in battle.units if u.alive and u.team != unit.team]
        r = unit.awareness_radius
        close_visible = [e for e in enemies if battle.can_see_unit(unit, e) and battle.units_distance(unit, e) <= r]
        alarm = getattr(battle, "alarm_triggered", False)
        if close_visible or alarm or getattr(unit, "alerted", False):
            unit.dormant = False
            unit.alerted = True
            battle.log(f"{unit.name} awakens and enters the fight!")
        else:
            unit.ap = 0
            battle.end_turn()
            return

    if getattr(unit, "patrol_route", None) and not getattr(unit, "alerted", False) and _patrol(battle, unit):
        return
    if unit.team == "player" and hasattr(battle.scenario, "heist_goal") and _heist(battle, unit):
        return
    if unit.team == "player" and hasattr(battle.scenario, "treasure_on_floor") and _fetch(battle, unit):
        return

    if _should_delay(battle, unit):
        actions.DELAY.execute(battle, unit)
        return

    searched = None
    for _ in range(4):  # safety stop; a turn spends at most 2 points
        if unit.ap <= 0 or not unit.alive:
            break

        if _leave_fire(battle, unit):
            continue

        if _try_stand_up(battle, unit):
            continue

        if _try_escape_grapple(battle, unit):
            continue

        if _is_skittish(unit):
            mode = _skitter(battle, unit)
            if mode == "moved":
                continue
            if mode == "idle":
                break

        if _try_mount(battle, unit):          # mount a Centaur ally if adjacent
            continue

        if _try_lift_rider(battle, unit):
            continue

        if _try_pixie_dust(battle, unit):
            continue

        if _try_signal_horn(battle, unit):
            continue

        if actions.WAKE_UP.available(battle, unit):
            targets = [t for t in actions.WAKE_UP.highlight_targets(battle, unit) if _sleeps_beyond_turn(t)]
            if targets:
                actions.WAKE_UP.execute(battle, unit, targets[0])
                continue

        if _try_drink_potion(battle, unit):
            continue

        if _try_healing_touch(battle, unit):
            continue

        if _try_share_magic(battle, unit):
            continue

        ally = _ally_to_help(battle, unit)
        if ally is not None:                  # good: save the friend first
            if ally.dying and actions.DRINK_POTION.can(battle, unit, ally):
                actions.DRINK_POTION.execute(battle, unit, ally)     # up again, not just stable
                continue
            if ally.dying and _spell_can(battle, unit, "healing_touch", ally):
                actions.CastSpellAction("healing_touch").execute(battle, unit, ally)
                continue
            if _spell_can(battle, unit, "spare_the_dying", ally):
                actions.CastSpellAction("spare_the_dying").execute(battle, unit, ally)   # no roll, unlike Stabilize
                continue
            if actions.FIRST_AID.can(battle, unit, ally):
                actions.FIRST_AID.execute(battle, unit, ally)
                continue
            elif actions.STABILIZE.can(battle, unit, ally):
                actions.STABILIZE.execute(battle, unit, ally)
                continue
            else:
                dest = battle.path_step_toward(unit, ally.pos, unit.speed, reach=1)
                if dest == unit.pos:
                    if _step_over_terrain(battle, unit, ally):
                        continue
                    break # walled off from the ally
                actions.MOVE.execute(battle, unit, dest)
                unit.walking = False
                continue

        if _try_capture(battle, unit):
            continue

        raised = _necromancy(battle, unit)
        if raised == "acted":
            continue
        if raised == "hold":
            break

        goal = _ctf_goal(battle, unit)
        if goal is not None:                  # flag runner or defender
            if goal in battle.cells_of(unit):
                if getattr(unit, "ctf_runner", False):
                    break                     # on it -- end_turn picks it up / scores it
                # defender is on the flag tile: hold position, but allow attacks/actions below
            else:
                # step ONTO the flag cell (not adjacent, the way `path_step_toward`
                # stops next to a unit) -- a downed body lying on it does not block.
                reach = battle.reachable(unit)
                route = battle.path_to(unit, goal)
                step = goal if goal in reach else next(
                    (c for c in reversed(route) if c in reach), None)
                if step is not None and step != unit.pos:
                    actions.MOVE.execute(battle, unit, step)
                    unit.walking = False
                    continue
                # genuinely walled off from the flag -- fight through this turn

        if _try_vanish(battle, unit):
            continue

        if _should_flee(battle, unit):
            if actions.FLEE.available(battle, unit):
                actions.FLEE.execute(battle, unit)
                break
            elif _run_for_the_exit(battle, unit):
                continue
            else:
                battle.log(f"{unit.name} is cornered and turns to fight!")
                # fall through to normal combat below

        body = _finish_off(battle, unit)
        if body is not None:                  # evil: put the downed enemy away
            actions.ATTACK.execute(battle, unit, body)
            continue

        if _eat_corpse(battle, unit):         # Gnoll: devour a dead enemy
            continue

        if _recover_weapon(battle, unit) or _recover_shield(battle, unit):
            continue

        if _recover_torch(battle, unit):
            continue

        target = _target(battle, unit)
        if target is None:
            if searched != battle.round_no and actions.INVESTIGATE.available(battle, unit):
                searched = battle.round_no
                actions.INVESTIGATE.execute(battle, unit)
                continue
            if _no_contact(battle, unit):
                continue
            break
        if battle.lethal and unit.nonlethal_blows != _wants_alive(battle, unit, target):
            actions.NONLETHAL.execute(battle, unit)

        if _adjust_altitude(battle, unit, target):
            continue

        # a crossbow only fires loaded -- keep it fed instead of closing to melee
        if unit.can_reload:
            actions.RELOAD.execute(battle, unit)
            continue

        riding = _rider(battle, unit, target)
        if riding == "acted":
            continue
        if riding == "delayed":
            return
        if riding == "hold":
            break
            
        foe = _assess_target(battle, unit)
        if foe is not None:
            actions.ASSESS.execute(battle, unit, foe)
            continue

        if _light_globe(battle, unit, target):
            continue

        if _try_breath(battle, unit):
            continue

        spot = _breath_spot(battle, unit, target)
        if spot is not None:                  # there for next turn's breath: strike or brace, not walk off
            actions.MOVE.execute(battle, unit, spot)
            unit.walking = False
            atk = _pick_attack(battle, unit, target)
            if atk is not None:
                atk.execute(battle, unit, target)
            elif actions.DEFEND.available(battle, unit):
                actions.DEFEND.execute(battle, unit)
            break

        shoved_foe = _try_shove(battle, unit)
        if shoved_foe is not None:
            if unit.ap > 0 and unit.alive and shoved_foe.alive and shoved_foe in battle.units:
                # the shove was the opening, not the plan: hit the foe if it can be reached (a failed shove
                # leaves it adjacent), else the next pass closes in on it again; never back off
                atk = _pick_attack(battle, unit, shoved_foe)
                if atk is not None:
                    atk.execute(battle, unit, shoved_foe)
                elif battle.units_distance(unit, shoved_foe) <= 1 and actions.DEFEND.available(battle, unit):
                    actions.DEFEND.execute(battle, unit)
            continue

        victim = _demoralize_victim(battle, unit, target)
        if victim is not None:
            actions.DEMORALIZE.execute(battle, unit, victim)
            continue

        step = _flank_step(battle, unit, target)
        if step is not None:
            if actions.FREE_STEP.can(battle, unit, step):
                actions.FREE_STEP.execute(battle, unit, step)
            else:
                actions.MOVE.execute(battle, unit, step)
                unit.walking = False
            continue

        atk = _pick_attack(battle, unit, target)
        if atk is not None:
            atk.execute(battle, unit, target)
            if unit.ap > 0 and unit.alive:
                if _try_escape_grapple(battle, unit):
                    continue
                second_atk = _pick_attack(battle, unit, target)
                if second_atk is not None:
                    second_atk.execute(battle, unit, target)
            continue

        if unit.resupplies_throw and _try_throw(battle, unit, target, stalled=False):
            continue

        if _spin_web(battle, unit, target):
            continue

        if actions.DEMORALIZE.can(battle, unit, target):
            actions.DEMORALIZE.execute(battle, unit, target)
            continue

        if (battle.is_ctf and not getattr(unit, "ctf_runner", False)
                and battle.flags.get(unit.team) in battle.cells_of(unit)
                and battle.flag_carrier.get(unit.team) is None
                and not _ally_carries_flag(battle, unit)):
            if actions.DEFEND.available(battle, unit):
                actions.DEFEND.execute(battle, unit)
            break

        flank = _flank_cell(battle, unit, target)
        if flank is not None:
            actions.MOVE.execute(battle, unit, flank)
            unit.walking = False
            continue

        free = _free_approach(battle, unit, target)
        if free is not None:
            actions.FREE_STEP.execute(battle, unit, free)
            continue

        reach = _approach_reach(unit)
        cut_off = (battle.board.deep_water and not unit.flies
                   and not battle.can_reach(unit, target.pos, reach))
        dest = unit.pos if cut_off else _step_toward(battle, unit, target.pos, reach)
        if dest == unit.pos:
            sight = _sight_cell(battle, unit, target)
            if sight is not None:
                actions.MOVE.execute(battle, unit, sight)
                unit.walking = False
                continue
            # can't walk any closer -- maybe a pit or deep water is in the way.
            
            if "floating_disk" in getattr(unit, "spells_known", []):
                fd = actions.CastSpellAction("floating_disk")
                if fd.available(battle, unit):
                    # Pick an adjacent cell towards the target that is empty
                    adj = min((c for c in battle.board.neighbors(unit.pos) 
                               if fd.can(battle, unit, c)),
                              key=lambda c: grid_distance(c, target.pos), default=None)
                    if adj:
                        fd.execute(battle, unit, adj, elevation=battle.elevation(unit))
                        continue
            
            # try to climb / drop / swim toward the target so the fight doesn't
            # stall out.
            if _step_over_terrain(battle, unit, target):
                continue
            if _try_disarm(battle, unit, target) or _try_secret(battle, unit):
                continue
            if _try_throw(battle, unit, target, stalled=True):
                continue
            if _try_assess(battle, unit):
                continue
            # cornered and out of range: defend (once) and end
            if actions.DEFEND.available(battle, unit):
                actions.DEFEND.execute(battle, unit)
            break
        actions.MOVE.execute(battle, unit, dest)
        unit.walking = False  # close the walk; the next action spends another point

        atk = _pick_attack(battle, unit, target)
        if unit.ap > 0 and atk is not None:
            atk.execute(battle, unit, target)
        elif unit.ap > 0:
            _try_throw(battle, unit, target, stalled=False)

    battle.end_turn()
