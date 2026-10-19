"""Tests for the new combat talents and flanking mechanics:
- Strength T3: Blind Strike (reduces obscured penalty by 1)
- Wisdom T3: Peripheral Vision (reduces flanked AC penalty from 2 to 1)
- Charisma combat tree: Imposing, Menacing, Gruesome Takedown, Cull the Broken
- Intelligence combat tree: Tactical Mind, Sharp Analysis, Combat Analysis, Exploit Weakness
"""

from gartok import actions, data, intel, talents
from tests.helpers import (
    Battle,
    Unit,
    fixed_d20,
)


def _squad_battle():
    u1 = Unit("player", name="Hero", race=data.race_by_name("Human"))
    u2 = Unit("player", name="Buddy", race=data.race_by_name("Human"))
    f1 = Unit("enemy", name="Foe", race=data.race_by_name("Goblin"))
    b = Battle([u1, u2], [f1])
    c1, c2, cf = b.units
    c1.pos, cf.pos, c2.pos = (4, 5), (5, 5), (6, 5)
    return b, c1, c2, cf


# --------------------------------------------------------------------------- #
# Strength: Blind Strike                                                      #
# --------------------------------------------------------------------------- #

def test_blind_strike_reduces_obscured_penalty():
    u = Unit("player", name="Striker", race=data.race_by_name("Human"))
    u.set_track_level("combat", 1)
    u.choose_talent("combat", "strong")
    u.set_track_level("combat", 2)
    u.choose_talent("combat", "sure_strike")
    u.set_track_level("combat", 3)
    assert u.choose_talent("combat", "blind_strike")
    assert u.has_talent("blind_strike")

    f = Unit("enemy", name="DarkFoe", race=data.race_by_name("Goblin"))
    b = Battle([u], [f])
    c, foe = b.units
    c.pos, foe.pos = (0, 0), (1, 0)

    from gartok import vision
    orig_is_obscured = vision.is_obscured
    try:
        vision.is_obscured = lambda battle, attacker, target: True
        pen = actions.base.obscured_penalty(b, c, foe)
        assert pen == 3  # 4 - 1 = 3

        plain_u = Unit("player", name="Plain", race=data.race_by_name("Human"))
        plain_b = Battle([plain_u], [f])
        plain_c, _ = plain_b.units
        assert actions.base.obscured_penalty(plain_b, plain_c, foe) == 4
    finally:
        vision.is_obscured = orig_is_obscured


# --------------------------------------------------------------------------- #
# Wisdom: Peripheral Vision & Flanking AC penalty                             #
# --------------------------------------------------------------------------- #

def test_flanking_reduces_defender_ac_and_peripheral_vision_halves_it():
    b, c1, c2, cf = _squad_battle()
    # c1 at (4, 5) and c2 at (6, 5) strictly flank cf at (5, 5)
    assert actions._flanked(b, c1, cf)

    # Standard defender without talent suffers 2 AC penalty
    pen = actions._flank_penalty(b, c1, cf)
    assert pen == 2

    # Give defender Peripheral Vision
    cf.char.set_track_level("combat", 1)
    cf.char.choose_talent("combat", "alert")
    cf.char.set_track_level("combat", 2)
    cf.char.choose_talent("combat", "quick_wits")
    cf.char.set_track_level("combat", 3)
    assert cf.char.choose_talent("combat", "peripheral_vision")

    pen_with_talent = actions._flank_penalty(b, c1, cf)
    assert pen_with_talent == 1

    # In attack resolution, log shows [Flank -1]
    with fixed_d20(15):
        actions._strike(b, c1, cf)
        assert any("[Flank -1]" in line for line in b.log_lines)


# --------------------------------------------------------------------------- #
# Charisma Combat Tree: Imposing, Menacing, Gruesome Takedown, Cull the Broken#
# --------------------------------------------------------------------------- #

def test_charisma_combat_tree_progression():
    u = Unit("player", name="Warlord", race=data.race_by_name("Human"))
    base_cha = u.charisma

    # Tier 1: Imposing (+1 CHA)
    u.set_track_level("combat", 1)
    assert u.choose_talent("combat", "imposing")
    assert u.charisma == base_cha + 1

    # Tier 2a: Menacing (+1 Demoralize)
    u.set_track_level("combat", 2)
    assert u.choose_talent("combat", "menacing")
    assert u.talent_bonus("demoralize_bonus") == 1

    # Tier 3: Cull the Broken (+2 damage vs demoralized)
    u.set_track_level("combat", 3)
    assert u.choose_talent("combat", "cull_the_broken")
    assert u.talent_bonus("demoralized_target_damage") == 2


def test_menacing_adds_bonus_to_demoralize():
    b, c1, c2, cf = _squad_battle()
    c1.char.set_track_level("combat", 1)
    c1.char.choose_talent("combat", "imposing")
    c1.char.set_track_level("combat", 2)
    c1.char.choose_talent("combat", "menacing")
    c1.torch_hand = True
    cf.char.languages = c1.char.languages  # shared language so Demoralize can be performed

    with fixed_d20(10):
        actions.DEMORALIZE.execute(b, c1, cf)
        assert any("Menacing" in line for line in b.log_lines)


def test_cull_the_broken_adds_extra_damage_vs_demoralized():
    b, c1, c2, cf = _squad_battle()
    c1.char.set_track_level("combat", 1)
    c1.char.choose_talent("combat", "imposing")
    c1.char.set_track_level("combat", 2)
    c1.char.choose_talent("combat", "menacing")
    c1.char.set_track_level("combat", 3)
    c1.char.choose_talent("combat", "cull_the_broken")

    from gartok.conditions import Demoralized
    cf.add_condition(Demoralized())
    cf.hp, cf.hp_max = 50, 50

    c1.damage_roll = lambda **kw: 5 + kw.get("bonus_damage", 0)

    with fixed_d20(18):
        actions._strike(b, c1, cf)
        # 5 base + 2 cull = 7 damage taken (cf had 50 hp -> 43)
        assert cf.hp == 43


def test_gruesome_takedown_demoralizes_nearest_foe_on_down():
    u1 = Unit("player", name="Executioner", race=data.race_by_name("Human"))
    u1.set_track_level("combat", 1)
    u1.choose_talent("combat", "imposing")
    u1.set_track_level("combat", 2)
    u1.choose_talent("combat", "gruesome_takedown")

    f1 = Unit("enemy", name="Weakling", race=data.race_by_name("Goblin"))
    f2 = Unit("enemy", name="Bystander", race=data.race_by_name("Orc"))
    # Ensure no shared language between Human and Orc
    f2.languages = ("Orcish",)

    b = Battle([u1], [f1, f2])
    c1, cf1, cf2 = b.units
    c1.pos, cf1.pos, cf2.pos = (5, 5), (6, 5), (5, 7)
    cf1.hp = 2  # 1 hit away from downing

    c1.damage_roll = lambda **kw: 10

    with fixed_d20(18):  # hit to kill and hit to demoralize
        actions._strike(b, c1, cf1)
        assert not cf1.alive or cf1.hp <= 0
        assert any("Gruesome Takedown!" in line for line in b.log_lines)
        assert cf2.has_condition("demoralized")


# --------------------------------------------------------------------------- #
# Intelligence Combat Tree: Tactical Mind, Sharp/Combat Analysis, Exploit Weakness
# --------------------------------------------------------------------------- #

def test_intelligence_combat_tree_progression():
    u = Unit("player", name="Scholar", race=data.race_by_name("Human"))
    base_int = u.intelligence

    # Tier 1: Tactical Mind (+1 INT)
    u.set_track_level("combat", 1)
    assert u.choose_talent("combat", "tactical_mind")
    assert u.intelligence == base_int + 1

    # Tier 2a: Sharp Analysis (+1 on all Assess / observation)
    u.set_track_level("combat", 2)
    assert u.choose_talent("combat", "sharp_analysis")
    assert u.talent_bonus("assess_bonus") == 1

    # Tier 2b / Tier 3: on another unit
    u2 = Unit("player", name="Tactician", race=data.race_by_name("Human"))
    u2.set_track_level("combat", 1)
    u2.choose_talent("combat", "tactical_mind")
    u2.set_track_level("combat", 2)
    assert u2.choose_talent("combat", "combat_analysis")
    assert u2.talent_bonus("assess_active_bonus") == 2

    # Tier 3: Exploit Weakness (+2 to hit vs full intel)
    u2.set_track_level("combat", 3)
    assert u2.choose_talent("combat", "exploit_weakness")
    assert u2.talent_bonus("full_intel_to_hit") == 2


def test_exploit_weakness_grants_plus_2_to_hit_on_full_intel():
    u = Unit("player", name="Analyst", race=data.race_by_name("Human"))
    u.set_track_level("combat", 1)
    u.choose_talent("combat", "tactical_mind")
    u.set_track_level("combat", 2)
    u.choose_talent("combat", "combat_analysis")
    u.set_track_level("combat", 3)
    u.choose_talent("combat", "exploit_weakness")

    f = Unit("enemy", name="Subject", race=data.race_by_name("Goblin"))
    b = Battle([u], [f])
    c, foe = b.units
    c.pos, foe.pos = (5, 5), (6, 5)

    # When intel is not full:
    b.intel.margin["player"][foe] = 2  # EASY band only
    assert not intel.has_full_intel(b, "player", foe)
    mods = c.attack_mods(foe, battle=b)
    assert not any("Exploit Weakness" in label for _, _, label in mods)

    # When intel reaches HARD (>= 10): full intel!
    b.intel.margin["player"][foe] = 12
    assert intel.has_full_intel(b, "player", foe)
    mods_full = c.attack_mods(foe, battle=b)
    assert any("Exploit Weakness" in label and val == 2 for val, _, label in mods_full)
