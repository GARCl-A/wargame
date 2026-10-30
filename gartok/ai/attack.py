"""Action choice: which attack, spell or special move the AI makes on a target this instant."""

from .. import actions, intel
from ..board import cells, grid_distance
from .common import _avg_die, _axes, _hand_die, _runs_flag, _wants_alive
from . import reckon
from .reckon import _blow, _hex_worth, _hit_odds, _jet_avg, _jet_burns, _point_worth, _roots_worth, _shove_worth, _two_points, _weapon_action_worth


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

    if _tail_sweep_pays(battle, unit, target):
        return actions.TAIL_SWEEP

    w_act = _weapon_action(battle, unit, target)
    if w_act is not None:
        return w_act

    if actions.ZOMBIE_BITE.can(battle, unit, target):
        return actions.ZOMBIE_BITE

    if _should_grab(battle, unit, target):
        return actions.GRAB

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


HOLDING_SPELLS = (("hex", "hexed", _hex_worth), ("grasping_roots", "rooted", _roots_worth))


def _hex_or_roots(battle, unit, target):
    """Hex or Grasping Roots on `target`, whichever is expected to be worth more than the point
    buys as a strike (`_point_worth`), or None."""
    known = getattr(unit, "spells_known", [])
    best, best_worth = None, _point_worth(battle, unit, target)
    for spell_id, condition, worth_of in HOLDING_SPELLS:
        if spell_id not in known or target.has_condition(condition):
            continue
        spell = actions.CastSpellAction(spell_id)
        if not spell.can(battle, unit, target):
            continue
        worth = worth_of(battle, unit, target)
        if worth is not None and worth > best_worth:
            best, best_worth = spell, worth
    return best


def _weapon_action(battle, unit, target):
    """The 2-point weapon action worth at least the two plain attacks it costs, the best one, or None."""
    if unit.ap < 2:
        return None
    char = getattr(unit, "char", unit)
    has_unarmed_cleave = getattr(char, "has_talent", lambda _: False)("sweeping_claws")
    if (unit.unarmed or not unit.weapon) and not has_unarmed_cleave:
        return None
    best, best_worth = None, _two_points(battle, unit, target)
    for act in actions.WEAPON_ACTIONS:
        if act.cost < 2 or not act.can(battle, unit, target):
            continue
        worth = _weapon_action_worth(battle, unit, act, target)
        if worth >= best_worth and worth > 0:
            best, best_worth = act, worth
    return best


def _tail_sweep_pays(battle, unit, target):
    """Sweep when the two tail strikes and the two shoves beat the two points as plain attacks."""
    sweep = actions.TAIL_SWEEP
    if not sweep.can(battle, unit, target):
        return False
    tail = _avg_die(unit.unarmed_damage) + unit.mod_strength + unit.char.talent_bonus("melee_damage")
    foes = [target] + [u for u in (sweep.second(battle, unit, target),) if u is not None]
    worth = sum(_hit_odds(battle, unit, f) * tail + _shove_worth(battle, unit, f) for f in foes)
    return worth >= _two_points(battle, unit, target) and worth > 0


def _should_grab(battle, unit, target):
    """Grab when the unit has grab/bite talents (pins the foe to bite it), or when stopping
    a fleeing enemy or flag runner."""
    if not actions.GRAB.can(battle, unit, target):
        return False
    char = getattr(unit, "char", unit)
    has_bite = getattr(char, "has_talent", lambda _: False)("zombie_bite")
    has_grip = getattr(char, "has_talent", lambda _: False)("death_grip")
    if (has_bite or has_grip) and target.hp > 3:
        return True
    if _runs_flag(battle, target) or getattr(target, "fleeing", False):
        return True
    return False


def _sleep_immune(battle, unit, target):
    """Only a racial ability the unit's side has read can tell it the foe will not sleep."""
    return (intel.knows(battle, unit.team, target, "racial_ability")
            and getattr(target.char.ability, "sleep_immunity", False))


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


BREATH_MIN_FOES = 3


def _best_cone(battle, unit):
    """`(cell, foes)` of the cone from where the unit stands that catches the most foes, at least
    `BREATH_MIN_FOES` and more foes than allies, or `(None, 0)`."""
    breath = actions.DRAGON_BREATH
    best, best_foes = None, 0
    for cell in breath.highlight_cells(battle, unit):
        caught = breath.caught(battle, unit, cell)
        foes = sum(1 for u in caught if u.team != unit.team)
        if foes >= BREATH_MIN_FOES and foes > len(caught) - foes and foes > best_foes:
            best, best_foes = cell, foes
    return best, best_foes


def _try_breath(battle, unit):
    """Dragon Breath, only when a cone catches at least `BREATH_MIN_FOES` foes and fewer
    allies than foes. Returns True if it breathed."""
    if not actions.DRAGON_BREATH.available(battle, unit):
        return False
    best, _ = _best_cone(battle, unit)
    if best is None:
        return False
    actions.DRAGON_BREATH.execute(battle, unit, best)
    return True


def _breath_spot(battle, unit, target):
    """At the start of its turn, with no cone worth breathing from here: the cell it can walk to
    from which one is (the most foes, then the shortest walk), for next turn's breath, kept within
    a blow of `target` when it already stands within one. None when there is none."""
    breath = actions.DRAGON_BREATH
    if unit.ap < breath.cost or not breath.applicable(battle, unit)[0] or _best_cone(battle, unit)[0]:
        return None
    in_reach = battle.units_distance(unit, target) <= unit.attack_range
    home, best = unit.pos, None
    for pos, cost in battle.reachable(unit).items():
        if pos == home or (battle.fire and any(c in battle.fire for c in cells(pos, unit.footprint))):
            continue
        unit.pos = pos
        try:
            if in_reach and battle.units_distance(unit, target) > unit.attack_range:
                continue
            foes = _best_cone(battle, unit)[1]
        finally:
            unit.pos = home
        if foes and (best is None or (-foes, cost) < best[0]):
            best = ((-foes, cost), pos)
    return best[1] if best else None


def _try_shove(battle, unit):
    """Push a foe when the shove is worth more than a swing: into the flames, or with a Mighty
    Shove against a wall. Returns the foe if it shoved, else None."""
    push = actions.PUSH
    if not push.available(battle, unit):
        return None
    swing = reckon.SHOVE_HIT_ODDS * (_hand_die(unit) + unit.mod_strength)
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
