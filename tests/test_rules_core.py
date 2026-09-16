"""Typed bonuses, conditions and flanking -- the modifier arithmetic."""

import random

from tests.helpers import (
    abilities, actions, Battle, Defending, Demoralized, resolve_bonus, Unit,
    _combatant,
)


# --------------------------------------------------------------------------- #
# resolve_bonus                                                                #
# --------------------------------------------------------------------------- #

def test_typed_bonus_does_not_stack():
    total, _ = resolve_bonus([(2, "circumstance", "A"), (4, "circumstance", "B")])
    assert total == 4, total


def test_untyped_bonus_stacks():
    total, _ = resolve_bonus([(2, None, "A"), (3, None, "B")])
    assert total == 5, total


def test_penalties_always_stack():
    total, _ = resolve_bonus([(-1, "status", "A"), (-1, "status", "B"), (2, "circumstance", "C")])
    assert total == 0, total


# --------------------------------------------------------------------------- #
# conditions                                                                   #
# --------------------------------------------------------------------------- #

def test_defend_gives_1_ac_and_expires_next_turn():
    u = _combatant()
    base = u.ac
    u.add_condition(Defending())
    assert u.ac == base + 1
    u.start_turn(lambda _: None)
    assert u.ac == base and not u.defending


def test_demoralized_penalizes_and_expires_at_turn_end():
    u = _combatant()
    ac, md = u.ac, u.mental_defense
    u.add_condition(Demoralized())
    assert u.ac == ac - 1 and u.mental_defense == md - 1
    u.end_turn(lambda _: None)
    assert not u.demoralized


def test_condition_does_not_duplicate():
    u = _combatant()
    u.add_condition(Demoralized())
    u.add_condition(Demoralized())
    assert len(u.conditions) == 1


# --------------------------------------------------------------------------- #
# flanking                                                                     #
# --------------------------------------------------------------------------- #

def _flank_battle():
    random.seed(3)
    batt = Battle([Unit("player"), Unit("player")], [Unit("enemy")])
    a, b, e = batt.units
    for u in batt.units:
        u._ability = abilities.get("none")
    a.pos, e.pos = (4, 5), (5, 5)
    return batt, a, b, e


def test_strict_flank_needs_opposite_sides():
    batt, a, b, e = _flank_battle()
    b.pos = (6, 5)                                    # opposite side of a
    assert actions._flanked(batt, a, e)
    b.pos = (4, 4)                                    # adjacent but same side
    assert not actions._flanked(batt, a, e)
    assert actions._pack_flank(batt, a, e)           # loose flank still true


def test_strict_flank_against_large_target_opposite_sides():
    batt, a, b, e = _flank_battle()
    e.footprint, e.pos = 2, (5, 5)                    # Large, occupies (5,5)-(6,6)
    a.pos, b.pos = (5, 4), (5, 7)                     # due north / due south
    assert actions._flanked(batt, a, e)
    a.pos, b.pos = (4, 5), (7, 5)                     # due west / due east
    assert actions._flanked(batt, a, e)
    a.pos, b.pos = (4, 4), (6, 5)                     # both off the NW corner
    assert not actions._flanked(batt, a, e)


def test_pack_tactics_and_flank_do_not_stack():
    batt, a, b, e = _flank_battle()
    a._ability = abilities.get("pack_tactics")
    b.pos = (6, 5)
    mods = a.attack_mods(e, actions._pack_flank(batt, a, e))
    if actions._flanked(batt, a, e):
        mods.append((2, "circumstance", "Flank"))
    total, _ = resolve_bonus(mods)
    assert total == 2 + max(0, a.mod_strength)        # +2 circ once, not +4

# --------------------------------------------------------------------------- #
# data.item_tooltip                                                            #
# --------------------------------------------------------------------------- #

def test_item_tooltip():
    from gartok.data import item_tooltip
    
    # Weapon
    title, desc = item_tooltip("Dagger")
    assert title == "Dagger"
    assert "Weapon: 1d4 damage" in desc
    assert "Finesse" in desc
    
    # Armor
    title, desc = item_tooltip("Leather Jerkin")
    assert title == "Leather Jerkin"
    assert "+1 Armor Class" in desc
    
    # Kit
    title, desc = item_tooltip("First Aid Kit")
    assert title == "First Aid Kit"
    assert "Restores HP" in desc
    
    # Food
    title, desc = item_tooltip("Meat")
    assert title == "Meat"
    assert "day's ration" in desc
    assert "Spoils in 2 day(s)" in desc
