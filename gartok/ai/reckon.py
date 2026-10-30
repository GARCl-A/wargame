"""What a blow, a spell or a shove is worth: the odds to hit and the damage the AI reckons."""

from .. import actions, data, intel, items
from ..board import cells
from .common import _avg_die, _hand_die, _runs_flag


D20_STEP = 0.05            # one point on a d20 roll


def _spell_odds(battle, unit, target, spell):
    """Chance a hostile spell lands on `target`: `d20 + INT` against the defence it reads, the AC as
    `_reckoned_ac` has it, the Mental Defense once read (else a bare 10)."""
    if getattr(spell, "against", "ac") == "ac":
        defence = _reckoned_ac(battle, unit, target)
    else:
        defence = target.mental_defense if intel.knows(battle, unit.team, target, "md") else 10
    return max(0.05, min(0.95, (21 - defence + spell.spell_to_hit(unit)) / 20))


def _hex_worth(battle, unit, target):
    """The hit points a Hex on `target` is expected to be worth through the foe's next turn, or None
    while the unit's side has not read its attributes (Assess first): what an even Constitution
    takes (and the foe's next blows, when that downs it), the blows the unit's side lands more often
    on the lower AC, and the foe's own two blows landing less often and for less."""
    if not intel.knows(battle, unit.team, target, "attrs"):
        return None
    deltas = target.hex_deltas()
    lost = target.hex_hp_cost(deltas)
    worth = float(min(lost, max(target.hp, 0)))
    if lost >= target.hp > 0:
        worth += 2 * _blow(target)
    strikers = [a for a in battle.units if a.alive and a.team == unit.team
                and battle.units_distance(a, target) <= a.attack_range + a.speed]
    worth += -target.hex_ac_delta(deltas) * D20_STEP * sum(2 * _blow(a) for a in strikers)
    to_hit = -(deltas["dexterity"] if target.ranged else deltas["strength"])
    damage = 0 if target.ranged else -deltas["strength"]
    worth += 2 * (to_hit * D20_STEP * _blow(target) + SHOVE_HIT_ODDS * damage)
    return _spell_odds(battle, unit, target, actions.CastSpellAction("hex")) * worth


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


def _point_worth(battle, unit, target):
    """What one point is worth as a plain strike on `target`: a swing or shot it can make now or
    after a walk this turn, else a Magic Missile, else nothing."""
    distance = battle.units_distance(unit, target)
    if actions.ATTACK.can(battle, unit, target) or (
            unit.ap >= 2 and distance <= unit.speed + unit.attack_range and not unit.ranged):
        return _strike_worth(battle, unit, target)
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
    flank_pen = actions._flank_penalty(battle, unit, target)
    bonus, _ = data.resolve_bonus(mods)
    need = (_reckoned_ac(battle, unit, target, armor_pierce) - flank_pen) - bonus - extra
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
    cull = 0
    if getattr(target, "demoralized", False) and hasattr(unit, "char"):
        cull = getattr(unit.char, "talent_bonus", lambda x: 0)("demoralized_target_damage")
    return _hit_odds(battle, unit, target, extra, **kw) * (_blow(unit, kw.get("thrown", False)) + bonus_damage + cull)


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
    for the blows both would land before the unit's next turn."""
    if battle.units_distance(unit, foe) > 1 or not actions._flanked(battle, foe, unit):
        return 0.0
    pair = [f for f in battle.units if f.alive and f.team == foe.team and battle.units_distance(f, unit) <= 1]
    return FLANK_ODDS * sum(2 * _blow(f) for f in pair)
