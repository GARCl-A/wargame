"""One AI turn: `take_turn` runs the checks of the other modules in order."""

from .. import actions
from ..board import grid_distance
from .attack import _breath_spot, _eat_corpse, _finish_off, _pick_attack, _rider, _spin_web, _try_breath, _try_capture, _try_shove, _try_throw
from .common import _hand_die, _spell_can, _wants_alive
from .flee import _is_skittish, _leave_fire, _retreat_from, _should_delay, _should_flee, _skitter, _slipping_away, _try_escape_grapple, _try_vanish
from .movement import _recover_torch, _recover_weapon, _sight_cell, _step_over_terrain, _step_toward, _try_assess, _try_disarm, _try_secret
from .scripted import _ctf_goal, _fetch, _heist, _necromancy, _patrol
from .support import _ally_to_help, _try_drink_potion, _try_healing_touch, _try_lift_rider, _try_mount, _try_pixie_dust, _try_share_magic, _try_signal_horn
from .target import _approach_reach, _flank_cell, _no_contact, _target


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
            targets = actions.WAKE_UP.highlight_targets(battle, unit)
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

        if _should_flee(battle, unit) or _slipping_away(battle, unit):
            if actions.FLEE.available(battle, unit):
                actions.FLEE.execute(battle, unit)
                break
            else:
                cols, rows = battle.board.cols, battle.board.rows
                edges = []
                for x in range(cols):
                    edges.extend([(x, 0), (x, rows - 1)])
                for y in range(1, rows - 1):
                    edges.extend([(0, y), (cols - 1, y)])
                target_edge = min(edges, key=lambda c: grid_distance(unit.pos, c))
                dest = battle.path_step_toward(unit, target_edge, unit.speed, reach=0)
                if dest != unit.pos:
                    actions.MOVE.execute(battle, unit, dest)
                    unit.walking = False
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

        if _recover_weapon(battle, unit):
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
            
        if "light_globe" in getattr(unit, "spells_known", []):
            lg = actions.CastSpellAction("light_globe")
            if lg.available(battle, unit) and lg.can(battle, unit, target.pos):
                if not any(o.is_torch for o in battle.ground if grid_distance(o.pos, target.pos) <= 3):
                    lg.execute(battle, unit, target.pos)
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
            if unit.ap > 0 and unit.alive:
                # Compound 2-action tactical replanning:
                # If shove succeeded (foe displaced): execute planned Retreat or Ranged Attack
                # If shove failed (foe remained adjacent): pivot to Defend (+2 AC)
                shove_succeeded = (shoved_foe not in battle.units or not shoved_foe.alive
                                   or battle.units_distance(unit, shoved_foe) > 1)
                if shove_succeeded:
                    atk = _pick_attack(battle, unit, shoved_foe)
                    if atk is not None:
                        atk.execute(battle, unit, shoved_foe)
                    else:
                        _retreat_from(battle, unit, shoved_foe)
                else:
                    if actions.DEFEND.available(battle, unit):
                        actions.DEFEND.execute(battle, unit)
                    else:
                        atk = _pick_attack(battle, unit, shoved_foe)
                        if atk is not None:
                            atk.execute(battle, unit, shoved_foe)
            continue

        # Compound [Demoralize, Attack] evaluation when 2 AP available
        if (unit.ap >= 2 and not target.demoralized and actions.DEMORALIZE.can(battle, unit, target)
                and target.hp > _hand_die(unit)):
            actions.DEMORALIZE.execute(battle, unit, target)
            if unit.ap > 0 and unit.alive:
                atk = _pick_attack(battle, unit, target)
                if atk is not None:
                    atk.execute(battle, unit, target)
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

        if _spin_web(battle, unit, target):
            continue

        if not target.demoralized and actions.DEMORALIZE.can(battle, unit, target):
            actions.DEMORALIZE.execute(battle, unit, target)
            continue

        if (battle.is_ctf and not getattr(unit, "ctf_runner", False)
                and battle.flags.get(unit.team) in battle.cells_of(unit)
                and battle.flag_carrier.get(unit.team) is None):
            if actions.DEFEND.available(battle, unit):
                actions.DEFEND.execute(battle, unit)
            break

        flank = _flank_cell(battle, unit, target)
        if flank is not None:
            actions.MOVE.execute(battle, unit, flank)
            unit.walking = False
            continue

        dest = _step_toward(battle, unit, target.pos, _approach_reach(unit))
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
