"""Tests for 2-AP weapon actions, traits expansion, critical hit multipliers, and AI usage."""

import random
import pytest

from gartok import items, weapon_traits
from tests.helpers import (
    Battle,
    Board,
    Combatant,
    GroundObject,
    Unit,
    _combatant,
    _melee_battle,
    _recruit,
    _unit,
    actions,
    fixed_d20,
)


def test_weapon_traits_catalog_and_properties():
    dagger = items.get("dagger")
    assert dagger.has_trait("sneak_attack")
    assert dagger.has_trait("finesse")
    assert dagger.has_trait("thrown")
    assert dagger.thrown == 6
    assert dagger.crit_mult == 2

    pick = items.get("pick")
    assert pick.has_trait("armor_pierce")
    assert pick.has_trait("crit_3x")
    assert pick.crit_mult == 3

    light_pick = items.get("light_pick")
    assert light_pick.has_trait("armor_pierce")
    assert light_pick.has_trait("crit_3x")
    assert light_pick.has_trait("finesse")
    assert light_pick.has_trait("thrown")
    assert light_pick.thrown == 6
    assert light_pick.crit_mult == 3

    hatchet = items.get("hatchet")
    assert hatchet.has_trait("hook_shield")
    assert hatchet.has_trait("thrown")
    assert hatchet.thrown == 4

    staff = items.get("quarterstaff")
    assert staff.has_trait("repel_strike")
    assert staff.has_trait("finesse")
    assert staff.finesse is True

    shortspear = items.get("shortspear")
    assert shortspear.has_trait("javelin_charge")
    assert shortspear.thrown == 12

    shortbow = items.get("shortbow")
    assert shortbow.has_trait("power_shot")
    assert shortbow.range == 14

    l_xbow = items.get("light_crossbow")
    assert l_xbow.has_trait("extreme_shot")
    assert l_xbow.range == 18


def test_crit_mult_triples_damage_dice():
    batt, a, d = _melee_battle()
    a.equip_weapon("Pick")
    random.seed(42)
    dmg = a.damage_roll(crit=True)
    # 3d8 + STR mod
    assert dmg >= 3


def test_sneak_attack_action():
    batt, a, d = _melee_battle()
    d.hp = 20
    a.equip_weapon("Dagger")
    a.ap = 2
    assert actions.SNEAK_ATTACK.applicable(batt, a)[0] is True

    ally = _recruit(batt, team="player")
    ally.pos = (5, 6)
    d.pos = (5, 5)
    a.pos = (4, 5)
    assert actions.SNEAK_ATTACK.can(batt, a, d) is False
    ally.pos = (6, 5)
    assert actions.SNEAK_ATTACK.can(batt, a, d) is True

    with fixed_d20(18):
        actions.SNEAK_ATTACK.execute(batt, a, d)
    assert a.ap == 0
    assert any("Sneak Attack strikes a vulnerable spot" in log for log in batt.log_lines)


def test_precise_thrust_action():
    batt, a, d = _melee_battle()
    d.hp = 20
    a.equip_weapon("Rapier")
    a.ap = 2
    assert actions.PRECISE_THRUST.applicable(batt, a)[0] is True

    ally = _recruit(batt, team="player")
    d.pos = (5, 5)
    a.pos = (4, 5)
    ally.pos = (9, 9)
    assert actions.PRECISE_THRUST.can(batt, a, d) is False
    ally.pos = (6, 5)
    assert actions.PRECISE_THRUST.can(batt, a, d) is True

    with fixed_d20(15):
        actions.PRECISE_THRUST.execute(batt, a, d)
    assert a.ap == 0
    assert any("Precise Thrust" in log for log in batt.log_lines)


def test_cleave_action_hits_two_foes():
    batt, a, d1 = _melee_battle()
    d1.hp = 20
    a.equip_weapon("Axe")
    a.ap = 2
    d2 = _recruit(batt, team="enemy")
    d2.hp = 20
    a.pos = (5, 5)
    d1.pos = (5, 6)
    d2.pos = (6, 6) # adjacent to a and adjacent to d1

    assert actions.CLEAVE.applicable(batt, a)[0] is True
    assert actions.CLEAVE.can(batt, a, d1) is True

    with fixed_d20(18):
        actions.CLEAVE.execute(batt, a, d1)
    assert a.ap == 0
    assert any("Cleave sweeps into" in log for log in batt.log_lines)


def test_repel_strike_shoves_foe():
    batt, a, d = _melee_battle()
    d.hp = 20
    a.equip_weapon("Quarterstaff")
    a.ap = 2
    a.pos = (5, 5)
    d.pos = (6, 5)
    assert actions.REPEL_STRIKE.applicable(batt, a)[0] is True

    with fixed_d20(20):
        actions.REPEL_STRIKE.execute(batt, a, d)
    assert a.ap == 0
    assert d.pos == (7, 5)


def test_maiming_strike_halves_speed():
    batt, a, d = _melee_battle()
    d.hp = 20
    a.equip_weapon("Hammer")
    a.ap = 2
    assert actions.MAIMING_STRIKE.applicable(batt, a)[0] is True

    base_speed = d.speed
    with fixed_d20(18):
        actions.MAIMING_STRIKE.execute(batt, a, d)
    assert a.ap == 0
    assert d.has_condition("maimed")
    assert d.speed == max(1, base_speed // 2)

    # Expires at end of target's turn
    d.start_turn(batt.log)
    assert d.has_condition("maimed")
    d.end_turn(batt.log)
    assert not d.has_condition("maimed")
    assert d.speed == base_speed


def test_armor_pierce_ignores_armor_ac():
    batt, a, d = _melee_battle()
    d.hp = 20
    a.equip_weapon("Pick")
    d.char.give_to_armor("Plate Armor")  # Plate Armor is +5 AC
    a.ap = 2
    assert actions.ARMOR_PIERCE.applicable(batt, a)[0] is True

    full_ac = d.ac_vs(a, armor_pierce=False)
    pierced_ac = d.ac_vs(a, armor_pierce=True)
    assert full_ac - pierced_ac == 5

    with fixed_d20(15):
        actions.ARMOR_PIERCE.execute(batt, a, d)
    assert a.ap == 0
    assert any("Armor Pierce" in log for log in batt.log_lines)


def test_power_shot_adds_str():
    batt, a, d = _melee_battle()
    d.hp = 20
    a.equip_weapon("Shortbow")
    a.char.base_attributes["strength"] = 16
    a.ammo = 10
    a.pos = (3, 3)
    d.pos = (7, 3)
    a.ap = 2

    assert actions.POWER_SHOT.applicable(batt, a)[0] is True
    assert actions.POWER_SHOT.can(batt, a, d) is True

    with fixed_d20(18):
        actions.POWER_SHOT.execute(batt, a, d)
    assert a.ap == 0
    assert a.ammo == 9
    assert any(f"+{a.mod_strength} STR damage" in log for log in batt.log_lines)


def test_extreme_shot_reaches_double_range():
    batt, a, d = _melee_battle()
    d.hp = 20
    batt.board = Board(cols=40, rows=12)
    batt.ambient_light = True
    a.equip_weapon("Light Crossbow")
    a.ammo = 10
    a.crossbow_loaded = True
    a.pos = (2, 2)
    d.pos = (25, 2)  # Distance 23 (> standard 18 range, <= 36 extreme range)
    a.ap = 2

    assert actions.EXTREME_SHOT.applicable(batt, a)[0] is True
    assert actions.EXTREME_SHOT.can(batt, a, d) is True

    with fixed_d20(18):
        actions.EXTREME_SHOT.execute(batt, a, d)
    assert a.ap == 0
    assert not a.crossbow_loaded
    assert any("Extreme Shot" in log for log in batt.log_lines)


def test_hook_shield_nullifies_shield_ac():
    batt, a, d = _melee_battle()
    d.hp = 20
    a.equip_weapon("Hatchet")
    d.char.give_to_offhand("Dwarf Shield")  # +2 shield AC
    base_ac = d.ac
    a.ap = 2

    assert actions.HOOK_SHIELD.applicable(batt, a)[0] is True
    with fixed_d20(18):
        actions.HOOK_SHIELD.execute(batt, a, d)
    assert a.ap == 0
    assert d.has_condition("shield_hooked")
    assert d.ac == base_ac - 2


def test_javelin_charge_requires_moving():
    batt, a, d = _melee_battle()
    d.hp = 20
    a.equip_weapon("Shortspear")
    a.pos = (3, 3)
    d.pos = (8, 3)
    a.ap = 2
    assert actions.JAVELIN_CHARGE.applicable(batt, a)[0] is True

    # Cannot charge without moving
    a.moved = 0
    assert not actions.JAVELIN_CHARGE.can(batt, a, d)

    # Moved this turn
    a.moved = 2
    assert actions.JAVELIN_CHARGE.can(batt, a, d)
    with fixed_d20(18):
        actions.JAVELIN_CHARGE.execute(batt, a, d)
    assert a.ap == 1                       # one point: a walk and the throw fill a turn
    assert a.unarmed
    assert any("Javelin Charge" in log for log in batt.log_lines)


def test_parry_strike_grants_defending():
    batt, a, d = _melee_battle()
    d.hp = 20
    a.equip_weapon("Broadsword")
    a.ap = 2
    assert actions.PARRY_STRIKE.applicable(batt, a)[0] is True

    with fixed_d20(18):
        actions.PARRY_STRIKE.execute(batt, a, d)
    assert a.ap == 0
    assert a.has_condition("defending")
