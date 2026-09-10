"""Racial abilities: the mechanical effect of each one."""

import random

from tests.helpers import (
    abilities, actions, Battle, Combatant, SIZES, squares, Unit, _melee_battle,
    _recruit, _unit,
)


def test_passive_ability_adds_in_derivation():
    u = _unit()
    u._ability = abilities.get("none")
    u._derive_combat()
    hp0, spd0 = u.hp_max, u.speed
    random.seed(0)                                    # same HP roll
    u2 = _unit()
    u2._ability = abilities.get("strong_stomach")
    u2._derive_combat()
    assert u2.hp_max == hp0 + 3
    u2._ability = abilities.get("gallop")
    u2._derive_combat()
    assert u2.speed == spd0 + 2
    u2._ability = abilities.get("sleep_immunity")
    u2._derive_combat()
    assert u2.ac_natural == 1


def test_large_centaur_moves_12m_from_gallop_not_size():
    # a Large creature moves like a Medium by default (9 m); the Centaur only
    # exceeds that because of Gallop (+3 m) -> 12 m = 8 squares.
    assert SIZES["Large"]["speed"] == SIZES["Medium"]["speed"] == 9.0
    u = _unit(size="Large")
    u._ability = abilities.get("none")
    u._derive_combat()
    assert u.speed == squares(9.0) == 6
    u._ability = abilities.get("gallop")
    u._derive_combat()
    assert u.speed == 8


def test_large_creature_takes_2x2_blocks_and_touches():
    random.seed(2)
    batt = Battle([Unit("player")], [Unit("enemy")])
    batt.board.walls = set()
    big, foe = batt.units
    big.footprint, big.pos = 2, (4, 4)
    foe.footprint, foe.pos = 1, (6, 5)                  # right against the footprint edge
    for u in (big, foe):                                # unarmed -> pure melee
        u.weapon_hand = u.torch_hand = False

    assert set(batt.cells_of(big)) == {(4, 4), (5, 4), (4, 5), (5, 5)}
    assert batt.unit_at((5, 5)) is big and batt.unit_at((4, 4)) is big
    assert batt.units_distance(big, foe) == 1           # melee
    assert actions.ATTACK.can(batt, big, foe)           # reaches without needing to see

    reach = batt.reachable(big)
    assert (5, 5) not in reach                          # anchor whose footprint would step on the foe
    assert (2, 4) in reach                              # free space to the left


def test_ferocity_falls_at_end_of_turn_then_clock_runs():
    base = _unit()
    base.ability_id = "ferocity"
    base._ability = abilities.get("ferocity")
    u = Combatant(base)
    u.hp = 3
    u.take_damage(99, lambda _: None)
    assert u.alive and u.hp == 0 and u.ferocity_pending      # 0 PV but still standing
    assert u.death_clock == 0
    u.end_turn(lambda _: None)
    assert u.dying and not u.ferocity_pending and u.death_clock == 0
    # once per battle: a second fatal hit drops it straight into dying
    u.status, u.hp, u.death_clock = "up", 3, 0
    u.take_damage(99, lambda _: None)
    assert u.dying and not u.ferocity_pending


def test_goliath_carries_as_a_large_creature():
    small = _unit(size="Medium")
    small._ability = abilities.get("none")
    small._derive_combat()
    goliath = _unit(size="Medium")
    goliath._ability = abilities.get("strong_body")
    goliath._derive_combat()
    assert goliath.carry_normal == small.carry_normal * 2      # Large carry multiplier
    assert goliath.carry_max == small.carry_max * 2
    assert goliath.footprint == 1 and goliath.speed == small.speed   # only carry changes


def test_automaton_breaks_instead_of_dying():
    batt, a, d = _melee_battle()
    d._ability = abilities.get("inorganic_body")
    d.take_damage(999, batt.log)
    assert d.broken and d.downed and not d.dying and not d.alive
    assert d.survived and d.death_clock == 0
    batt._resolve_dangling_dying()                            # no death save ever runs
    assert d.broken


def test_ally_repairs_broken_automaton_with_intelligence():
    batt, a, d = _melee_battle()
    a._ability = abilities.get("inorganic_body")
    a.go_down(batt.log); a.pos = (5, 5)
    assert a.broken
    b = _recruit(batt)
    b.char.intelligence = 30; b.char._derive_combat()
    b.pos = (5, 6)
    for _ in range(50):                                       # keep trying (infinite time)
        if a.alive:
            break
        b.ap = 2
        actions.STABILIZE.execute(batt, b, a)
    assert a.alive and a.hp == 1
