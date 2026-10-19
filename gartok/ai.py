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

from . import actions, data, intel, items, vision
from .board import cells, grid_distance, line_cells


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

    hold = _hex_or_roots(battle, unit, target)
    if hold is not None:
        return hold

    w_act = _weapon_action(battle, unit, target)
    if w_act is not None:
        return w_act

    opts = [a for a in (actions.ATTACK, actions.ATTACK_TONGUE)
            if a.can(battle, unit, target)]

    if "water_jet" in getattr(unit, "spells_known", []):
        jet = actions.CastSpellAction("water_jet")
        if jet.can(battle, unit, target) and (not opts or _hand_die(unit) < _jet_avg(unit)
                                              or _jet_burns(battle, jet, unit, target)):
            return jet

    spell_dmg = unit.talent_bonus("spell_damage")
    if "dragonfire" in getattr(unit, "spells_known", []):
        fire = actions.CastSpellAction("dragonfire")
        if (fire.can(battle, unit, target)
                and (not opts or _hand_die(unit) < _avg_die(actions.DragonfireAction.DICE) + spell_dmg)):
            return fire

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
        if _hand_die(unit) < 2.5 + spell_dmg:  # Magic Missile is 1d4 (avg 2.5)
            return mm
            
    if actions.ATTACK in opts and actions.ATTACK_TONGUE in opts and unit.tongue_weapon:
        return (actions.ATTACK if _hand_die(unit) >= _avg_die(unit.tongue_weapon["damage"])
                else actions.ATTACK_TONGUE)
    if actions.ATTACK in opts:
        return actions.ATTACK
    if actions.ATTACK_TONGUE in opts:
        return actions.ATTACK_TONGUE
    return opts[0]


def _hex_bites(battle, unit, target):
    """How many of the target's modifiers a Hex would drop, as far as the unit's side has read its
    attributes (None when it has not: Assess first), and whether its even CON would down it."""
    if not intel.knows(battle, unit.team, target, "attrs"):
        return None, False
    deltas = target.hex_deltas()
    return sum(1 for d in deltas.values() if d), target.hex_hp_cost(deltas) >= target.hp > 0


def _hex_or_roots(battle, unit, target):
    """Hex when it drops three modifiers or more (or an even CON would finish the foe); Grasping
    Roots on a flag runner, or on a melee foe still closing on a unit that would rather stay off."""
    known = getattr(unit, "spells_known", [])
    if "hex" in known and not target.has_condition("hexed"):
        hex_spell = actions.CastSpellAction("hex")
        bites, kills = _hex_bites(battle, unit, target)
        if hex_spell.can(battle, unit, target) and bites is not None and (bites >= 3 or kills):
            return hex_spell
    if "grasping_roots" in known and not target.has_condition("rooted"):
        roots = actions.CastSpellAction("grasping_roots")
        keeps_off = unit.ranged or ("magic_missile" in known and _hand_die(unit) < 2.5)
        closing = not target.ranged and battle.units_distance(unit, target) >= 2
        if roots.can(battle, unit, target) and (target.ctf_runner or (keeps_off and closing)):
            return roots
    return None


def _try_healing_touch(battle, unit):
    """Healing Touch on the most hurt of the unit and the allies in reach, at half health or less."""
    if "healing_touch" not in getattr(unit, "spells_known", []):
        return False
    touch = actions.CastSpellAction("healing_touch")
    hurt = [u for u in touch.highlight_targets(battle, unit) if u.alive and u.hp <= u.hp_max * 0.5]
    if not hurt or not touch.available(battle, unit):
        return False
    touch.execute(battle, unit, min(hurt, key=lambda u: u.hp / u.hp_max))
    return True


def _shield_ac(unit):
    hand = unit.equipped_offhand
    shield = items.get(hand) if hand and items.is_shield(hand) else None
    return shield.ac if shield else 0


def _reckoned_ac(battle, unit, target, armor_pierce=False):
    """The AC the unit plays against: the number once its side has read it, else a bare 10 plus
    the armour and shield it can see the foe wearing."""
    if intel.knows(battle, unit.team, target, "ac"):
        return target.ac_vs(unit, armor_pierce=armor_pierce)
    worn = target.armor.ac if target.armor and not armor_pierce else 0
    shield = 0 if target.has_condition("shield_hooked") else _shield_ac(target)
    return 10 + worn + shield


def _hit_odds(battle, unit, target, extra=0, armor_pierce=False, thrown=False):
    mods = unit.attack_mods(target, actions._pack_flank(battle, unit, target), thrown=thrown)
    if actions._flanked(battle, unit, target):
        mods.append((2, "circumstance", "Flank"))
    bonus, _ = data.resolve_bonus(mods)
    need = _reckoned_ac(battle, unit, target, armor_pierce) - bonus - extra
    return max(0.05, min(0.95, (21 - need) / 20))


def _blow(unit, thrown=False):
    """Average damage of one landed blow of the held weapon (thrown, or swung / shot)."""
    if thrown:
        return _avg_die(unit.weapon["damage"]) + unit.mod_strength
    if unit.ranged:
        return _hand_die(unit)
    return (_hand_die(unit) + unit.mod_strength + unit.ability.melee_damage
            + unit.char.talent_bonus("melee_damage"))


def _strike_worth(battle, unit, target, extra=0, bonus_damage=0, **kw):
    return _hit_odds(battle, unit, target, extra, **kw) * (_blow(unit, kw.get("thrown", False)) + bonus_damage)


def _two_points(battle, unit, target):
    """What the unit's two points are worth as plain attacks on `target`: two swings or shots, one
    for a crossbow (the other point reloads it), none when the target is out of reach."""
    if not actions.ATTACK.can(battle, unit, target):
        return 0.0
    blows = 1 if unit.weapon and unit.weapon.get("reload") else (min(2, unit.ammo) if unit.ranged else 2)
    return blows * _strike_worth(battle, unit, target)


DEFEND_SWING_ODDS = 0.05    # +1 AC takes this much off each blow aimed at the defender
UNLOADED_COST = 0.5         # an Extreme Shot leaves the crossbow empty, where a shot + Reload does not
REPEL_PUSH_BONUS = 2


def _incoming(battle, unit):
    """Damage the foes beside `unit` would deal it with one blow each, before any to-hit roll."""
    return sum(_blow(f) for f in battle.units
               if f.alive and f.team != unit.team and not f.hidden_from(unit.team)
               and battle.units_distance(unit, f) <= f.attack_range)


def _fall_worth(battle, foe, dest):
    """Average damage of `foe` falling into `dest`: the first level is free, deep water breaks it."""
    drop = battle.elevation(foe) - battle.elevation_at(dest, foe)
    if drop <= 1 or foe.flies or battle.board.is_deep_water(dest):
        return 0.0
    return _avg_die((drop - 1, 6))


def _cell_damage(battle, foe, dest):
    """Damage `foe` takes for being thrown onto `dest`: the flames there, the fall into it."""
    fire = battle.fire and any(c in battle.fire for c in cells(dest, foe.footprint))
    return (_avg_die(data.FIRE_DICE) if fire else 0.0) + _fall_worth(battle, foe, dest)


def _repel_worth(battle, unit, target):
    """A Repel Strike's shove: what landing one square back costs the foe."""
    step, dest = actions.REPEL_STRIKE.behind(unit, target)
    if step == (0, 0) or actions.REPEL_STRIKE.favoured(battle, unit, target):
        return 0.0
    need = actions.combat.PUSH_DC_BASE + target.mod_constitution - unit.mod_strength - REPEL_PUSH_BONUS
    return max(0.05, min(0.95, (21 - need) / 20)) * _cell_damage(battle, target, dest)


def _weapon_action_worth(battle, unit, act, target):
    """Expected damage (or its equivalent) of a 2-point weapon action on `target`: one strike, which
    lands twice over in the action's favoured case (`act.favoured`), plus the action's own edge."""
    if act.id == "extreme_shot":
        return _strike_worth(battle, unit, target) - UNLOADED_COST
    twice = _blow(unit) if act.favoured(battle, unit, target) else 0
    if act.id == "sneak_attack":
        return _strike_worth(battle, unit, target, bonus_damage=twice + (2.5 if twice else 0))
    if act.id == "precise_thrust":
        return _strike_worth(battle, unit, target, extra=2 if twice else 0, bonus_damage=twice)
    if act.id == "cleave":
        second = act.second(battle, unit, target)
        if second is None:
            return _strike_worth(battle, unit, target)
        return _strike_worth(battle, unit, target, extra=2) + _strike_worth(battle, unit, second, extra=2)
    if act.id == "repel_strike":
        shove = 0 if twice else _hit_odds(battle, unit, target) * _repel_worth(battle, unit, target)
        return _strike_worth(battle, unit, target, bonus_damage=twice + (2.5 if twice else 0)) + shove
    if act.id == "maiming_strike":
        runner = battle.is_ctf and target in battle.flag_carrier.values()
        stop = 2 * _blow(unit) if runner and not target.has_condition("maimed") else 0
        return (_strike_worth(battle, unit, target, extra=2 if twice else 0, bonus_damage=twice)
                + _hit_odds(battle, unit, target) * stop)
    if act.id == "armor_pierce":
        return _strike_worth(battle, unit, target, armor_pierce=True, bonus_damage=twice)
    if act.id == "power_shot":
        return _strike_worth(battle, unit, target, bonus_damage=max(1 if twice else 0, unit.mod_strength) + twice)
    if act.id == "hook_shield":
        if not twice:
            return _strike_worth(battle, unit, target)
        helpers = sum(1 for a in battle.units if a.alive and a.team == unit.team and a is not unit
                      and battle.units_distance(a, target) <= a.attack_range)
        opened = _shield_ac(target) * DEFEND_SWING_ODDS * _blow(unit) * helpers
        own = _hit_odds(battle, unit, target, extra=_shield_ac(target)) * 2 * _blow(unit)
        return own + opened
    if act.id == "parry_strike":
        guard = 0 if unit.has_condition("defending") else DEFEND_SWING_ODDS * _incoming(battle, unit)
        return _strike_worth(battle, unit, target, bonus_damage=twice) + guard
    return 0.0


def _weapon_action(battle, unit, target):
    """The 2-point weapon action worth at least the two plain attacks it costs, the best one, or None."""
    if unit.ap < 2 or unit.unarmed or not unit.weapon:
        return None
    best, best_worth = None, _two_points(battle, unit, target)
    for act in actions.WEAPON_ACTIONS:
        if act.cost < 2 or not act.can(battle, unit, target):
            continue
        worth = _weapon_action_worth(battle, unit, act, target)
        if worth >= best_worth and worth > 0:
            best, best_worth = act, worth
    return best


def _jet_avg(unit):
    return _avg_die(actions.WaterJetAction.DICE) + unit.mod_intelligence + unit.talent_bonus("spell_damage")


def _jet_burns(battle, jet, unit, target):
    """The jet would throw `target` into the flames."""
    dest = jet.landing(battle, unit, target)
    return dest is not None and any(c in battle.fire for c in cells(dest, target.footprint))


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


def _wants_alive(battle, unit, target):
    """The player's side pulls its blows on a foe it means to capture (`Battle.wanted_alive`);
    the enemy side never captures."""
    return unit.team == "player" and target in battle.wanted_alive


def _try_capture(battle, unit):
    """Bind a fallen foe the player's side wants alive, walking up to it first if it lies out of
    reach. Returns True if it acted."""
    if not actions.CAPTURE.applicable(battle, unit)[0]:
        return False
    bodies = [u for u in battle.wanted_alive
              if u.status in ("dying", "stable", "broken") and not u.captured
              and _wants_alive(battle, unit, u)]
    if not bodies:
        return False
    body = min(bodies, key=lambda b: battle.units_distance(unit, b))
    if actions.CAPTURE.can(battle, unit, body):
        actions.CAPTURE.execute(battle, unit, body)
        return True
    dest = battle.path_step_toward(unit, body.pos, unit.speed, reach=1)
    if dest == unit.pos:
        return False
    actions.MOVE.execute(battle, unit, dest)
    unit.walking = False
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
    bodies = sorted((u for u in battle.units if u.team != unit.team and u.downed
                     and not _wants_alive(battle, unit, u)),
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
    if any(actions.ATTACK.can(battle, unit, f) for f in battle.units if f.team != unit.team and f.alive):
        return False                      # a foe in reach: fight on foot rather than climb up
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


def _try_share_magic(battle, unit):
    """Sprite Nature Initiate: share a known spell with an ally who lacks it."""
    if not actions.SHARE_MAGIC.available(battle, unit):
        return False
    allies = [u for u in battle.units if u.alive and u.team == unit.team and u != unit]
    needy = [u for u in allies if any(s not in getattr(u, "spells_known", []) for s in unit.spells_known)]
    if not needy:
        return False
    enemies = [u for u in battle.units if u.alive and u.team != unit.team]
    in_melee = any(battle.units_distance(unit, e) <= 1 for e in enemies)
    if in_melee and unit.ap < 2:
        return False
    actions.SHARE_MAGIC.execute(battle, unit)
    return True


def _spell_can(battle, unit, spell_id, target):
    return (spell_id in getattr(unit, "spells_known", [])
            and actions.CastSpellAction(spell_id).can(battle, unit, target))


def _ally_to_help(battle, unit):
    """A downed ally this unit wants to stabilize -- only if it is of good
    bent (it will spend the action to save a friend before fighting)."""
    if _axes(unit)[1] <= 0:
        return None
    # Prefer an adjacent one if possible
    adj = next((a for a in battle.units
                if actions.FIRST_AID.can(battle, unit, a) or actions.STABILIZE.can(battle, unit, a)
                or any(_spell_can(battle, unit, sid, a) for sid in ("healing_touch", "spare_the_dying"))), None)
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
    sure = max(0, min((10 + unit.mod_strength) // actions.movement.JUMP_DIVISOR, unit.speed))
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


def _try_throw(battle, unit, target, stalled):
    """Out of reach of a swing after a walk: a Javelin Charge when it can. Else throw the held
    weapon with the turn's last point when it may drop the foe, stop a flag runner, or the unit
    cannot get any nearer -- a thrown weapon is a point to pick up again, so not as a matter of
    course."""
    if actions.JAVELIN_CHARGE.can(battle, unit, target) and not actions.ATTACK.can(battle, unit, target):
        actions.JAVELIN_CHARGE.execute(battle, unit, target)
        return True
    throw = actions.THROW
    if unit.ap != 1 or unit.ranged or not throw.can(battle, unit, target):
        return False
    if actions.ATTACK.can(battle, unit, target):
        return False
    hp = target.hp if intel.knows(battle, unit.team, target, "hp") else None
    worth = _blow(unit, thrown=True)
    downs = hp is not None and worth >= hp or hp is None and intel.health_steps(target) <= 1
    runner = battle.is_ctf and target in battle.flag_carrier.values()
    if not (stalled or downs or runner) or _hit_odds(battle, unit, target, thrown=True) < 0.3:
        return False
    throw.execute(battle, unit, target)
    return True


def _rider(battle, unit, target):
    """A unit on a mount does not walk: the mount carries it. Out of reach, a melee rider gets off
    beside the foe when it still has the point to swing, or off a mount that cannot move; else
    it waits for the mount's turn. -> "acted", "delayed", "hold" (end the turn) or None (not
    riding, or the foe is in reach: fight on as usual)."""
    mount = getattr(unit, "mounted_on", None)
    if mount is None or target is None or _pick_attack(battle, unit, target) is not None:
        return None
    stuck = mount.has_condition("entangled") or mount.demoralized or mount.dormant
    spots = actions.DISMOUNT.highlight_cells(battle, unit) if unit.ap >= 1 else []
    if spots and not unit.ranged:
        striking = [c for c in spots if grid_distance(c, target.pos) <= unit.attack_range]
        if striking and unit.ap >= 2 or stuck:
            spot = min(striking or spots, key=lambda c: grid_distance(c, target.pos))
            actions.DISMOUNT.execute(battle, unit, spot)
            return "acted"
    if mount in battle.order[battle.turn_idx + 1:] and actions.DELAY.available(battle, unit):
        actions.DELAY.execute(battle, unit)
        return "delayed"
    return "hold"


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


def _mindless(unit):
    """The dead do not break and run: an undead body, or one raised from the dead."""
    return getattr(unit, "raised", False) or unit.race.get("kind") == "undead"


def _should_flee(battle, unit):
    """Whether the unit breaks and runs this turn. Never from a non-lethal bout
    (the arena -- nobody dies). Chaotic units break sooner and while less outnumbered;
    lawful units stay while any ally is still standing."""
    if not battle.lethal or _mindless(unit):
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


def _try_vanish(battle, unit):
    """Invisibility as a way out of a lethal fight: cast when the unit would break and run, or
    when it is down to a third and a foe it sees can reach it this round. Returns True if it vanished."""
    vanish = actions.CastSpellAction("invisibility")
    if not battle.lethal or _mindless(unit) or not vanish.available(battle, unit):
        return False
    if _should_flee(battle, unit):
        vanish.execute(battle, unit)
        return True
    foes = intel.visible_foes(battle, unit)
    if unit.hp <= unit.hp_max * 0.34 and any(
            battle.units_distance(unit, f) <= (f.attack_range if f.ranged else f.speed + 1) for f in foes):
        vanish.execute(battle, unit)
        return True
    return False


def _slipping_away(battle, unit):
    """An invisible unit at half its HP or less makes for the edge instead of striking (a blow
    would show it)."""
    return (battle.lethal and unit.has_condition("invisible") and not _mindless(unit)
            and unit.hp <= unit.hp_max * 0.5)


def _should_delay(battle, unit):
    """A melee unit that cannot reach anyone this turn waits for an ally that is
    already in the fight, so it arrives after the line has formed. Never a flag
    runner (it has somewhere to be)."""
    if (unit.ranged or getattr(unit, "ctf_runner", False) or not actions.DELAY.available(battle, unit)
            or "raise_dead" in getattr(unit, "spells_known", ())):
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


BREATH_MIN_FOES = 3


def _try_breath(battle, unit):
    """Dragon Breath, only when a cone catches at least `BREATH_MIN_FOES` foes and fewer
    allies than foes. Returns True if it breathed."""
    breath = actions.DRAGON_BREATH
    if not breath.available(battle, unit):
        return False
    best, best_foes = None, 0
    for cell in breath.highlight_cells(battle, unit):
        caught = breath.caught(battle, unit, cell)
        foes = sum(1 for u in caught if u.team != unit.team)
        if foes >= BREATH_MIN_FOES and foes > len(caught) - foes and foes > best_foes:
            best, best_foes = cell, foes
    if best is None:
        return False
    breath.execute(battle, unit, best)
    return True


SHOVE_HIT_ODDS = 0.6        # how often the AI reckons a swing lands, to weigh a shove against it


def _shove_odds(unit, foe):
    """Chance the shove beats Strength vs 10 + the foe's Constitution."""
    need = actions.combat.PUSH_DC_BASE + foe.mod_constitution - unit.mod_strength
    return max(0.05, min(0.95, (21 - need) / 20))


def _shove_worth(battle, unit, foe):
    """The damage a shove of `foe` is expected to do: the flames it lands in, and a Mighty
    Shove's blows."""
    push = actions.PUSH
    path, stop = push.landing(battle, unit, foe)
    before = set(battle.cells_of(foe))
    entered = {c for p in path for c in cells(p, foe.footprint)} - before
    n, faces = data.FIRE_DICE
    worth = sum(1 for c in entered if c in battle.fire) * _avg_die((n, faces))
    if path:
        worth += _fall_worth(battle, foe, path[-1])
        trap = battle.ground_at(path[-1])
        if trap is not None and trap.trap_type == "bear trap":
            worth += _avg_die(BEAR_TRAP_DIE)
        worth += _unflank_worth(battle, unit, foe)
    if unit.char.talent_bonus("mighty_shove"):
        worth += _avg_die(push.MIGHTY_DIE) * (2 if stop is not None else 1)
    return worth * _shove_odds(unit, foe)


BEAR_TRAP_DIE = (1, 8)
FLANK_ODDS = 0.1            # the +2 a flank gives each blow of the pair


def _unflank_worth(battle, unit, foe):
    """`foe` and a mate of its stand on opposite sides of `unit`: shoving it out breaks the flank
    for the blows both would land before the unit's next turn."""
    if battle.units_distance(unit, foe) > 1 or not actions._flanked(battle, foe, unit):
        return 0.0
    pair = [f for f in battle.units if f.alive and f.team == foe.team and battle.units_distance(f, unit) <= 1]
    return FLANK_ODDS * sum(2 * _blow(f) for f in pair)


def _try_shove(battle, unit):
    """Push a foe when the shove is worth more than a swing: into the flames, or with a Mighty
    Shove against a wall. Returns the foe if it shoved, else None."""
    push = actions.PUSH
    if not push.available(battle, unit):
        return None
    swing = SHOVE_HIT_ODDS * (_hand_die(unit) + unit.mod_strength)
    best, best_worth = None, max(0.0, swing)
    for foe in push.highlight_targets(battle, unit):
        if foe.team == unit.team:
            continue
        worth = _shove_worth(battle, unit, foe)
        if worth > best_worth:
            best, best_worth = foe, worth
    if best is None:
        return None
    push.execute(battle, unit, best)
    return best


def _retreat_from(battle, unit, foe):
    """Back away from `foe` into a safe cell that increases distance from it,
    or Defend if no retreat cell is available. Returns True if acted."""
    if unit.ap < 1 or not unit.alive:
        return False
    reach = battle.reachable(unit)
    cur_dist = battle.units_distance(unit, foe)
    safe = [
        p for p in reach
        if all(c not in battle.fire for c in cells(p, unit.footprint))
        and grid_distance(p, foe.pos) > cur_dist
    ]
    if safe:
        dest = max(safe, key=lambda p: grid_distance(p, foe.pos))
        actions.MOVE.execute(battle, unit, dest)
        unit.walking = False
        return True
    if actions.DEFEND.available(battle, unit):
        actions.DEFEND.execute(battle, unit)
        return True
    return False


def _leave_fire(battle, unit):
    """Standing in the flames: walk to the nearest cell that is not burning, toward the foe
    when there is one. Returns True if it moved."""
    if not battle.burning_under(unit) or unit.ap < 1:
        return False
    foe = _target(battle, unit)
    safe = [p for p in battle.reachable(unit)
            if not any(c in battle.fire for c in cells(p, unit.footprint))]
    if not safe:
        return False
    goal = foe.pos if foe is not None else unit.pos
    dest = min(safe, key=lambda p: (grid_distance(p, goal), grid_distance(p, unit.pos)))
    actions.MOVE.execute(battle, unit, dest)
    unit.walking = False
    return True


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

    if _should_delay(battle, unit):
        actions.DELAY.execute(battle, unit)
        return

    searched = None
    for _ in range(4):  # safety stop; a turn spends at most 2 points
        if unit.ap <= 0 or not unit.alive:
            break

        if _leave_fire(battle, unit):
            continue

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
                if (unit.hp <= unit.hp_max * 0.35 and battle.units_distance(unit, target) <= 1
                        and actions.DEFEND.available(battle, unit)):
                    actions.DEFEND.execute(battle, unit)
                else:
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
