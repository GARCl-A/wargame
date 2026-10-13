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

from . import actions, data, intel, items
from .board import cells, grid_distance


def _avg_die(nf):
    n, faces = nf
    return n * (faces + 1) / 2


def _hand_die(unit):
    """Average damage die of the unit's hand attack (a real swing, an improvised
    club, or bare fists)."""
    if unit.unarmed or unit.improvised:
        return _avg_die(unit.unarmed_damage)
    return _avg_die(unit.weapon["damage"])


def _pick_attack(battle, unit, target):
    """The attack to make on `target` this instant, or None. Evaluates spells,
    2-AP weapon actions when AP is available, Grippli Tongue reach lash, and basic
    attacks."""
    if "sleep" in getattr(unit, "spells_known", []):
        if not _sleep_immune(battle, unit, target) and not target.has_condition("sleeping"):
            sleep_spell = actions.CastSpellAction("sleep")
            if sleep_spell.can(battle, unit, target):
                return sleep_spell  # always prioritize putting them to sleep first

    if unit.ap >= 2 and not unit.unarmed and unit.weapon:
        for w_act in actions.WEAPON_ACTIONS:
            if w_act.can(battle, unit, target):
                if w_act.id == "cleave":
                    return w_act
                if w_act.id in ("sneak_attack", "precise_thrust"):
                    if actions._flanked(battle, unit, target) or actions._pack_flank(battle, unit, target):
                        return w_act
                elif w_act.id == "hook_shield":
                    if target.equipped_offhand and items.is_shield(target.equipped_offhand):
                        return w_act
                elif w_act.id == "armor_pierce":
                    if target.armor and target.armor.ac >= 2:
                        return w_act
                elif w_act.id == "maiming_strike":
                    if not target.has_condition("maimed"):
                        return w_act
                elif w_act.id == "parry_strike":
                    if not unit.has_condition("defending"):
                        return w_act
                elif w_act.id in ("power_shot", "extreme_shot", "repel_strike", "javelin_charge"):
                    return w_act

    opts = [a for a in (actions.ATTACK, actions.ATTACK_TONGUE)
            if a.can(battle, unit, target)]

    mm = None
    if "magic_missile" in getattr(unit, "spells_known", []):
        mm = actions.CastSpellAction("magic_missile")
        if mm.can(battle, unit, target):
            opts.append(mm)

    if not opts:
        return None
    if len(opts) == 1:
        return opts[0]
        
    if mm in opts:
        if actions.ATTACK not in opts and actions.ATTACK_TONGUE not in opts:
            return mm
        if _hand_die(unit) < 2.5:  # Magic Missile is 1d4 (avg 2.5)
            return mm
            
    if actions.ATTACK in opts and actions.ATTACK_TONGUE in opts and unit.tongue_weapon:
        return (actions.ATTACK if _hand_die(unit) >= _avg_die(unit.tongue_weapon["damage"])
                else actions.ATTACK_TONGUE)
    if actions.ATTACK in opts:
        return actions.ATTACK
    if actions.ATTACK_TONGUE in opts:
        return actions.ATTACK_TONGUE
    return opts[0]


def _sleep_immune(battle, unit, target):
    """Only a racial ability the unit's side has read can tell it the foe will not sleep."""
    return (intel.knows(battle, unit.team, target, "racial_ability")
            and getattr(target.char.ability, "sleep_immunity", False))


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
    if "magic_missile" in getattr(unit, "spells_known", []) and _hand_die(unit) < 2.5:
        return 6
    return 1


def _axes(unit):
    """(order, morality) of the unit's tendency, each in {-1, 0, 1}."""
    return data.alignment_axes(unit.alignment)


SEARCH_STEP = 4           # spacing of the waypoints an attacker sweeps
SEARCH_REACH = 3          # a waypoint counts as searched once a unit is this near
GROUP_GAP = 2             # a defender with nobody in sight closes to this far from an ally


def _role(battle, unit):
    """"attacker" for the side that brought the fight, "defender" for the other, None when neither did."""
    if battle.aggressor is None:
        return None
    return "attacker" if unit.team == battle.aggressor else "defender"


def _target(battle, unit):
    enemies = [u for u in battle.units if u.alive and u.team != unit.team]
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
        if runner in pool:
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
    if getattr(battle, "ambient_light", False) or unit.ability.darkvision or unit.torch_hand:
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


def _finish_off(battle, unit):
    """A downed enemy body this unit could hit right now -- dying (each blow ticks its death clock)
    before merely stable, nearest first. Only when the fight is lethal, the
    unit is of evil bent and no standing foe is within its reach."""
    if not battle.lethal or _axes(unit)[1] >= 0:
        return None
    if any(actions.ATTACK.can(battle, unit, u)
           for u in battle.units if u.team != unit.team and not u.downed):
        return None
    bodies = sorted((u for u in battle.units if u.team != unit.team and u.downed),
                    key=lambda u: (not u.dying, battle.units_distance(unit, u)))
    return next((b for b in bodies if actions.ATTACK.can(battle, unit, b)), None)


def _eat_corpse(battle, unit):
    """Gnoll: eat an adjacent dead enemy body (Corpse Eater talent). Resets hunger
    and AoE-demoralizes every enemy that can see the act. Returns True if acted."""
    if not actions.EAT_CORPSE.available(battle, unit):
        return False
    bodies = [u for u in battle.units if actions.EAT_CORPSE.can(battle, unit, u)]
    if not bodies:
        return False
    actions.EAT_CORPSE.execute(battle, unit, bodies[0])
    return True


def _spin_web(battle, unit, target):
    """Giant Spider: when the prey is still a few steps off, string a web between
    them instead of walking into the open -- at most one standing web near it."""
    if not actions.SPIN_WEB.available(battle, unit):
        return False
    here = battle.units_distance(unit, target)
    if not 2 <= here <= 7:
        return False
    if any(o.is_trap and o.trap_type == "web" and o.trap_owner_team == unit.team
           and grid_distance(o.pos, target.pos) <= 3 for o in battle.ground):
        return False
    anchor = min(actions.SPIN_WEB.highlight_cells(battle, unit),
                 key=lambda a: min(grid_distance(c, target.pos)
                                   for c in cells(a, unit.footprint)), default=None)
    if anchor is None or min(grid_distance(c, target.pos)
                             for c in cells(anchor, unit.footprint)) >= here:
        return False
    actions.SPIN_WEB.execute(battle, unit, anchor)
    return True


def _try_mount(battle, unit):
    """Mount an adjacent allied Centaur (centaur_mount talent) if one is available
    and the unit is not already riding. Returns True if acted."""
    if not actions.MOUNT.available(battle, unit):
        return False
    targets = actions.MOUNT.highlight_targets(battle, unit)
    if not targets:
        return False
    actions.MOUNT.execute(battle, unit, targets[0])
    return True


def _try_signal_horn(battle, unit):
    """Blow the Signal Horn while the fight is still a walk away: it takes the whole turn,
    so only when nobody is in reach to hit and at least two allies hear it."""
    horn = actions.SIGNAL_HORN
    if not horn.available(battle, unit):
        return False
    foes = intel.visible_foes(battle, unit)
    if not foes or any(battle.units_distance(unit, f) <= unit.speed + 1 for f in foes):
        return False
    if len(horn.allies_in_range(battle, unit)) < 2:
        return False
    horn.execute(battle, unit)
    return True


def _try_drink_potion(battle, unit):
    if unit.hp <= unit.hp_max * 0.5:
        if actions.DRINK_POTION.can(battle, unit, unit):
            actions.DRINK_POTION.execute(battle, unit, unit)
            return True
    return False


def _ally_to_help(battle, unit):
    """A downed ally this unit wants to stabilize -- only if it is of good
    bent (it will spend the action to save a friend before fighting)."""
    if _axes(unit)[1] <= 0:
        return None
    # Prefer an adjacent one if possible
    adj = next((a for a in battle.units
                if actions.FIRST_AID.can(battle, unit, a) or actions.STABILIZE.can(battle, unit, a)), None)
    if adj:
        return adj
    # Else nearest ally still savable -- a stable one is already saved, and
    # walking to it would leave a good unit idling beside it instead of fighting
    bodies = sorted((u for u in battle.units if u.team == unit.team and (u.dying or u.broken)),
                    key=lambda u: battle.units_distance(unit, u))
    return bodies[0] if bodies else None


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
    for act in (actions.CLIMB, actions.DROP, actions.SWIM):
        for c in act.highlight_cells(battle, unit):
            s = score(c)
            if s < now and act.can(battle, unit, c) and (best is None or s < best[0]):
                best = (s, act, c)
    if best is None:
        return False
    _, act, c = best
    act.execute(battle, unit, c)
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


def _ctf_goal(battle, unit):
    """The cell a capture-the-flag runner or defender is racing for:
    - a runner heads for the opposing flag, then races it home to score;
    - a non-runner defends their own side's flag by standing directly on its square.
    None before both flags are down or if an ally already guards the home flag."""
    if not battle.is_ctf:
        return None
    if battle.flags["player"] is None or battle.flags["enemy"] is None:
        return None
    if getattr(unit, "ctf_runner", False):
        if battle.flag_carrier["player"] is unit:
            return battle.flags["enemy"]          # got it -- now get it home
        return battle.flag_pos("player")          # not carrying yet: go get it

    # Non-runner / defender:
    # If the team's flag is currently stolen, pursue the carrier (handled by _target).
    if battle.flag_carrier.get(unit.team) is not None:
        return None
    home = battle.flags.get(unit.team)
    if home is None:
        return None
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


def _should_flee(battle, unit):
    """Whether the unit breaks and runs this turn. Never from a non-lethal bout
    (the arena -- nobody dies). Chaotic units break sooner and while less outnumbered;
    lawful units stay while any ally is still standing."""
    if not battle.lethal:
        return False
    order = _axes(unit)[0]
    allies = [u for u in battle.units
              if u.alive and u.team == unit.team and u is not unit]
    foes = intel.visible_foes(battle, unit)
    if not foes:
        return False
    if order > 0 and allies:                 # lawful: hold the line
        return False
    hurt = unit.hp <= unit.hp_max * (0.5 if order < 0 else 0.34)
    outmatched = len(foes) > len(allies) + (0 if order < 0 else 1)
    return hurt and outmatched


def _should_delay(battle, unit):
    """A melee unit that cannot reach anyone this turn waits for an ally that is
    already in the fight, so it arrives after the line has formed. Never a flag
    runner (it has somewhere to be)."""
    if unit.ranged or getattr(unit, "ctf_runner", False) or not actions.DELAY.available(battle, unit):
        return False
    foes = intel.visible_foes(battle, unit)
    if not foes or any(battle.units_distance(unit, f) <= unit.speed + 1 for f in foes):
        return False
    after = battle.order[battle.turn_idx + 1:]
    return any(u.alive and u.team == unit.team
               and any(battle.units_distance(u, f) <= 1 for f in foes) for u in after)


SKITTISH_SLUGS = frozenset({"aurochs"})
SKITTISH_ALARM = 12       # squares: a beast this near anyone runs
SKITTISH_STAMINA = 3      # turns of running before it turns and charges
SKITTISH_CHARGE_ROUNDS = 2    # rounds it then stands and fights


def _is_skittish(unit):
    return getattr(getattr(unit, "char", None), "npc_slug", None) in SKITTISH_SLUGS


def _skitter(battle, unit):
    """A hunted beast's turn: "idle" (nobody near enough to spook it), "moved"
    (ran for the open ground farthest from the party), or "fight" -- cornered, or
    winded after `SKITTISH_STAMINA` turns of running, when it lowers its head and
    charges. The cells it likes are far from every foe and out in the open, so a
    straight chase just herds it round the groves; it is pinned in a canyon or
    pincered."""
    foes = [e for e in battle.units if e.alive and e.team != unit.team]
    if not foes:
        return "idle"
    here = min(grid_distance(unit.pos, f.pos) for f in foes)
    if getattr(unit, "charging_until", 0) >= battle.round_no:
        return "fight"
    if here > SKITTISH_ALARM:
        unit.fled_turns = 0
        return "idle"
    if getattr(unit, "flee_round", None) != battle.round_no:
        if getattr(unit, "fled_turns", 0) >= SKITTISH_STAMINA:
            unit.fled_turns = 0
            unit.charging_until = battle.round_no + SKITTISH_CHARGE_ROUNDS - 1
            battle.log(f"{unit.name} is winded -- it lowers its head and charges!")
            return "fight"
        unit.fled_turns = getattr(unit, "fled_turns", 0) + 1
        unit.flee_round = battle.round_no
    board = battle.board

    def score(cell):
        near = min(grid_distance(cell, f.pos) for f in foes)
        open_ground = sum(1 for n in board.neighbors(cell) if n not in board.walls)
        edge = min(cell[0], cell[1], board.cols - 1 - cell[0], board.rows - 1 - cell[1])
        return near * 2 + open_ground + min(edge, 4)

    best = max(battle.reachable(unit), key=score, default=None)
    if best is None or best == unit.pos or min(
            grid_distance(best, f.pos) for f in foes) <= here:
        battle.log(f"{unit.name} is cornered and turns to fight!")
        return "fight"
    actions.MOVE.execute(battle, unit, best)
    unit.walking = False
    return "moved"


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

    if _should_delay(battle, unit):
        actions.DELAY.execute(battle, unit)
        return

    for _ in range(4):  # safety stop; a turn spends at most 2 points
        if unit.ap <= 0 or not unit.alive:
            break

        if _is_skittish(unit):
            mode = _skitter(battle, unit)
            if mode == "moved":
                continue
            if mode == "idle":
                break

        if _try_mount(battle, unit):          # mount a Centaur ally if adjacent
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

        ally = _ally_to_help(battle, unit)
        if ally is not None:                  # good: save the friend first
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

        if _should_flee(battle, unit):
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
            if _no_contact(battle, unit):
                continue
            break

        # a crossbow only fires loaded -- keep it fed instead of closing to melee
        if unit.can_reload:
            actions.RELOAD.execute(battle, unit)
            continue
            
        if "light_globe" in getattr(unit, "spells_known", []):
            lg = actions.CastSpellAction("light_globe")
            if lg.available(battle, unit) and lg.can(battle, unit, target.pos):
                if not any(o.is_torch for o in battle.ground if grid_distance(o.pos, target.pos) <= 3):
                    lg.execute(battle, unit, target.pos)
                    continue

        atk = _pick_attack(battle, unit, target)
        if atk is not None:
            atk.execute(battle, unit, target)
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

        dest = battle.path_step_toward(unit, target.pos, unit.speed,
                                       reach=_approach_reach(unit))
        if dest == unit.pos:
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

    battle.end_turn()
