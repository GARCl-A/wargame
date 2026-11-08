"""What a blow, a spell or a shove is worth: the odds to hit and the damage the AI reckons."""

import math

from .. import actions, conditions, data, intel, items, morale
from ..board import cells
from ..conditions import BLEEDING_CLAWS_TURNS
from .common import _avg_die, _hand_die, _runs_flag

D20_STEP = 0.05            # one point on a d20 roll
ROUT_ROUNDS = 3            # rounds of a foe's blows that breaking its nerve takes off the field (it may rally)


def _spell_odds(battle, unit, target, spell):
    """Chance a hostile spell lands on `target`: `d20 + INT` against the defence it reads, the AC as
    `_reckoned_ac` has it (Roots: the touch AC, a bare 10 until read), the Mental Defense once read (else a bare 10)."""
    against = getattr(spell, "against", "ac")
    if against == "ac":
        defence = _reckoned_ac(battle, unit, target)
    elif against == "touch":
        defence = target.touch_ac if intel.knows(battle, unit.team, target, "ac") else 10
    else:
        defence = target.mental_defense if intel.knows(battle, unit.team, target, "md") else 10
    return max(0.05, min(0.95, (21 - defence + spell.spell_to_hit(unit)) / 20))



def _hex_scores(battle, unit, target):
    """`{attribute: (score the modifier is read off, score the Hex can zero)}` as the unit's side
    reckons them: the real ones once read, else ten, the average roll."""
    if intel.knows(battle, unit.team, target, "attrs"):
        return {a: (target.char.attribute_score(a), getattr(target.char, a) + target.char.hunger_attribute_penalty)
                for a in data.ATTRIBUTES}
    return dict.fromkeys(data.ATTRIBUTES, (10, 10))


def _hex_worth(battle, unit, target):
    """The hit points one more Hex on `target` is expected to be worth. The better of two paths: the debuff the new stack adds
    (the HP an Constitution step takes, the blows the unit's side lands more often on the lower AC and
    the foe's own two blows landing less often and for less, for as long as the stack lasts or the foe
    is expected to), and the kill, the share of the foe's HP that one cast is of the casts left to bring
    its weakest score to zero, if the side's Hexes can keep that many stacks up at once."""
    scores = _hex_scores(battle, unit, target)
    points, step = target.hex_points(), conditions.HEX_POINTS
    drop = {a: data.mod(m - points - step) - data.mod(m - points) for a, (m, _) in scores.items()}
    dice = 1 + target.char.racial_level
    lost = -drop["constitution"] * dice
    worth = float(min(lost, max(target.hp, 0)))
    if lost >= target.hp > 0:
        worth += 2 * _blow(target)
    strikers = [a for a in battle.units if a.alive and a.team == unit.team
                and battle.units_distance(a, target) <= a.attack_range + a.speed]
    pace = sum(2 * _hit_odds(battle, a, target) * _blow(a) for a in strikers)
    span = min(conditions.HEX_TURNS, max(1, math.ceil(max(target.hp, 1) / pace))) if pace else 1
    cap = target.armor.max_dex if target.armor is not None else None
    dex = scores["dexterity"][0]
    ac_drop = ((min(data.mod(dex) + drop["dexterity"], cap) - min(data.mod(dex), cap)) if cap is not None
               else drop["dexterity"])
    debuff = -ac_drop * D20_STEP * sum(2 * _blow(a) for a in strikers)
    to_hit = -(drop["dexterity"] if target.ranged else drop["strength"])
    damage = 0 if target.ranged else -drop["strength"]
    debuff += 2 * (to_hit * D20_STEP * _blow(target) + SHOVE_HIT_ODDS * damage)
    worth += debuff * span
    base = min(base for _, base in scores.values())
    hex_cast = actions.CastSpellAction("hex")
    capacity = sum(2 * _spell_odds(battle, a, target, hex_cast) for a in battle.units
                   if a.alive and a.team == unit.team and "hex" in getattr(a, "spells_known", []))
    if base > points and capacity * step * conditions.HEX_TURNS >= base and target.hp > 0:
        worth = max(worth, target.hp / math.ceil((base - points) / step))
    return _spell_odds(battle, unit, target, hex_cast) * worth


def _roots_worth(battle, unit, target):
    """The hit points Grasping Roots on `target` is expected to be worth: a flag runner held short
    of where it is going (as much as Maiming Strike's stop), or a melee foe a walk from the unit's
    side held out of reach for its next turn, the two blows it would have landed."""
    if _runs_flag(battle, target):
        held = 2 * _blow(unit)
    elif target.ranged:
        return 0.0
    else:
        mine = [a for a in battle.units if a.alive and a.team == unit.team]
        near = min(mine, key=lambda a: battle.units_distance(a, target))
        gap = battle.units_distance(near, target)
        if not target.attack_range + 1 < gap <= target.attack_range + target.speed:
            return 0.0
        held = 2 * _hit_odds(battle, target, near) * _blow(target)
    return _spell_odds(battle, unit, target, actions.CastSpellAction("grasping_roots")) * held


def _demoralize_worth(battle, unit, target):
    """The hit points a Demoralize on `target` is expected to be worth through its next turn: the odds
    the CHA roll beats its Mental Defense (a bare 10 until read) times the -1 on every blow and
    defence. Each striker of the unit's side that can reach the foe lands its blows 5% more often
    (and for its own Menacing cull), the foe's own two blows land 5% less. A foe whose morale it has read
    and that this Demoralize would break (down to 0) is worth `ROUT_ROUNDS` rounds of its blows more."""
    char = unit.char
    mod = unit.mod_charisma
    if char.has_talent("intimidating_presence"):
        mod = max(mod, unit.mod_strength)
    mod += char.talent_bonus("demoralize_bonus") + actions.demoralize_language_penalty(unit, target)
    if unit.ability.demoralize_vs_weaker and unit.mod_strength > target.mod_strength:
        mod += unit.ability.demoralize_vs_weaker
    md = target.mental_defense if intel.knows(battle, unit.team, target, "md") else 10
    odds = max(0.05, min(0.95, (21 - md + mod) / 20))
    worth = 0.0
    for a in battle.units:
        if not (a.alive and a.team == unit.team) or battle.units_distance(a, target) > a.attack_range + a.speed:
            continue
        blows = max(unit.ap - 1, 0) if a is unit else 2
        cull = a.char.talent_bonus("demoralized_target_damage")
        worth += blows * (D20_STEP * _blow(a) + _hit_odds(battle, a, target) * cull)
    if battle.units_distance(unit, target) <= target.attack_range + target.speed:
        worth += 2 * D20_STEP * _blow(target)
    if (morale.has_morale(battle, target) and intel.knows(battle, unit.team, target, "morale")
            and 0 < target.morale <= -morale.DEMORALIZED):
        worth += ROUT_ROUNDS * 2 * D20_STEP * _blow(target)
    return odds * worth


def _point_worth(battle, unit, target):
    """What one point is worth as a plain strike on `target`: a swing or shot it can make now or
    after a walk this turn, else a Magic Missile, else nothing."""
    distance = battle.units_distance(unit, target)
    if actions.ATTACK.can(battle, unit, target) or (
            unit.ap >= 2 and distance <= unit.speed + unit.attack_range and not unit.ranged):
        return _strike_worth(battle, unit, target)
    if unit.resupplies_throw and actions.THROW.can(battle, unit, target):
        return _strike_worth(battle, unit, target, thrown=True)
    mm = actions.CastSpellAction("magic_missile")
    if "magic_missile" in getattr(unit, "spells_known", []) and mm.can(battle, unit, target):
        return _spell_odds(battle, unit, target, mm) * (2.5 + unit.talent_bonus("spell_damage"))
    return 0.0


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
    mods = unit.attack_mods(target, actions._pack_flank(battle, unit, target), thrown=thrown, battle=battle)
    guard_pen = actions._off_guard_penalty(battle, unit, target)
    bonus, _ = data.resolve_bonus(mods)
    need = (_reckoned_ac(battle, unit, target, armor_pierce) - guard_pen) - bonus - extra
    return max(0.05, min(0.95, (21 - need) / 20))


def _blow(unit, thrown=False):
    """Average damage of one landed blow of the held weapon (thrown, or swung / shot)."""
    if thrown:
        return _avg_die(unit.weapon["damage"]) + unit.mod_strength
    if unit.ranged:
        return _hand_die(unit) + (unit.char.talent_bonus("crossbow_damage") if unit.shoots_crossbow else 0)
    return _hand_die(unit) + unit.melee_damage_mod()


def _strike_worth(battle, unit, target, extra=0, bonus_damage=0, **kw):
    cull = 0
    if getattr(target, "demoralized", False) and hasattr(unit, "char"):
        cull = getattr(unit.char, "talent_bonus", lambda x: 0)("demoralized_target_damage")
    bleed = _bleed_worth(unit, target) if not kw.get("thrown") else 0
    return _hit_odds(battle, unit, target, extra, **kw) * (_blow(unit, kw.get("thrown", False)) + bonus_damage + cull + bleed)


def _bleed_tick(foe):
    """What the foe's open wounds take from it at the end of its next turn."""
    bleed = foe.condition("bleeding")
    return bleed.damage if bleed else 0


def _bleed_worth(unit, target):
    """What the Catfolk's Razor Claws add to a landed bare-handed blow: the new wound's whole bleed."""
    n = unit.char.talent_bonus("bleeding_claws")
    return n * BLEEDING_CLAWS_TURNS if n and not unit.armed else 0


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
    dice = drop - 1 - foe.ability.fall_free
    return _avg_die((dice, 6)) if dice > 0 else 0.0


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


WREST_TURNS = 2             # turns the AI counts a disarmed foe's lost damage for


def _wrest_worth(battle, unit, target):
    """A Wrest: the odds of tearing the weapon away times the blow struck with it at once, plus the
    damage the foe loses by being left with its bare body for a couple of turns."""
    held = target.weapon
    stolen = unit.char.natural_weapon.damage if held["range"] > 0 else held["damage"]
    need = actions.WREST.dc(target) - unit.mod_dexterity
    odds = max(0.05, min(0.95, (21 - need) / 20))
    strike = _hit_odds(battle, unit, target) * (_avg_die(stolen) + unit.mod_strength)
    lost = max(0.0, _avg_die(held["damage"]) - _avg_die(target.char.natural_weapon.damage)) * WREST_TURNS
    return odds * (strike + lost)


def _weapon_action_worth(battle, unit, act, target):
    """Expected damage (or its equivalent) of a 2-point weapon action on `target`: one strike, which
    is Brutal 1 in the action's favoured case (`act.favoured`), plus the action's own edge."""
    if act.id == "wrest":
        return _wrest_worth(battle, unit, target)
    if act.id == "extreme_shot":
        return _strike_worth(battle, unit, target) - UNLOADED_COST
    if act.id == "long_thrust":
        return _strike_worth(battle, unit, target, extra=act.TO_HIT)
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


DAMAGE_SPELLS = ("magic_missile", "water_jet", "dragonfire")


def _spell_blow(unit, spell_id):
    """Average damage of one landed cast of a damage spell."""
    bonus = unit.talent_bonus("spell_damage")
    if spell_id == "magic_missile":
        return _avg_die(actions.MagicMissileAction.DICE) + bonus
    if spell_id == "water_jet":
        return max(1.0, _jet_avg(unit))
    return _avg_die(actions.DragonfireAction.DICE) + bonus


def _spell_strike_worth(battle, unit, spell_id, target):
    """What one cast of a damage spell is expected to do to `target`: the odds `d20 + INT` beats its
    AC (as the unit reckons it) times the damage, and for the jet what the throw does to it."""
    spell = actions.CastSpellAction(spell_id)
    worth = _spell_blow(unit, spell_id)
    if spell_id == "water_jet":
        dest = spell.landing(battle, unit, target)
        if dest is not None:
            worth += _cell_damage(battle, target, dest)
    return _spell_odds(battle, unit, target, spell) * worth


def _jet_avg(unit):
    return _avg_die(actions.WaterJetAction.DICE) + unit.mod_intelligence + unit.talent_bonus("spell_damage")


def _jet_burns(battle, jet, unit, target):
    """The jet would throw `target` into the flames."""
    dest = jet.landing(battle, unit, target)
    return dest is not None and any(c in battle.fire for c in cells(dest, target.footprint))


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
    for the blows both would land before the unit's next turn. A foe that has not acted is off-guard
    anyway, so breaking the flank costs it nothing."""
    if battle.units_distance(unit, foe) > 1 or foe.turns_taken == 0 or not actions._flanked(battle, foe, unit):
        return 0.0
    pair = [f for f in battle.units if f.alive and f.team == foe.team and battle.units_distance(f, unit) <= 1]
    return FLANK_ODDS * sum(2 * _blow(f) for f in pair)


def _flank_step_worth(battle, unit, target, free):
    """What stepping to a cell that flanks `target` is worth against staying: the blows the unit still
    has, struck from the new cell (the flank's hit odds, and the Backstab damage of a Dexterity
    fighter), plus the odds the flank gives each mate beside the foe. `unit.pos` is the cell tried.
    A foe that has not acted is off-guard already, so a flank adds nothing."""
    blows = unit.ap if free else unit.ap - 1
    if blows < 1 or target.turns_taken == 0 or not actions._flanked(battle, unit, target):
        return None
    extra = unit.char.talent_bonus("off_guard_finesse_damage") if unit.is_dex_melee else 0
    own = blows * _strike_worth(battle, unit, target, bonus_damage=extra)
    mates = [m for m in battle.units if m.alive and m.team == unit.team and m is not unit
             and battle.units_distance(m, target) <= 1 and not m.ranged]
    return own + FLANK_ODDS * sum(2 * _blow(m) * m.ap for m in mates)

