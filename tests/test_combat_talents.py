"""Tests for the new combat talents and flanking mechanics:
- Strength T3: Blind Strike (reduces obscured penalty by 1)
- Wisdom T3: Peripheral Vision (reduces flanked AC penalty from 2 to 1)
- Charisma combat tree: Imposing, Menacing, Gruesome Takedown, Cull the Broken
- Intelligence combat tree: Tactical Mind, Sharp Analysis, Combat Analysis, Exploit Weakness
"""

from gartok import actions, intel
from tests.helpers import (
    Battle,
    fitted,
    fixed_d20,
    standard_unit,
)


def _body(team, name, race="Human"):
    """A `standard_unit` under `name`; another race keeps its hit die at the top, unrolled."""
    u = standard_unit(team)
    u.name = name
    if race != "Human":
        u.set_race(race)
        u._hp_roll = u.race["hd"]
        u._derive_combat()
        u.hp = u.hp_max
    return u


def _squad_battle():
    u1 = _body("player", "Hero")
    u2 = _body("player", "Buddy")
    f1 = _body("enemy", "Foe", "Goblin")
    b = Battle([u1, u2], [f1])
    c1, c2, cf = b.units
    c1.turns_taken = c2.turns_taken = cf.turns_taken = 1
    c1.pos, cf.pos, c2.pos = (4, 5), (5, 5), (6, 5)
    return b, c1, c2, cf


# --------------------------------------------------------------------------- #
# Strength: Blind Strike                                                      #
# --------------------------------------------------------------------------- #

def test_blind_strike_reduces_obscured_penalty():
    u = _body("player", "Striker")
    u.set_track_level("combat", 1)
    u.choose_talent("combat", "strong")
    u.set_track_level("combat", 2)
    u.choose_talent("combat", "sure_strike")
    u.set_track_level("combat", 3)
    assert u.choose_talent("combat", "blind_strike")
    assert u.has_talent("blind_strike")

    f = _body("enemy", "DarkFoe", "Goblin")
    b = Battle([u], [f])
    c, foe = b.units
    c.pos, foe.pos = (0, 0), (1, 0)

    from gartok import vision
    orig_is_obscured = vision.is_obscured
    try:
        vision.is_obscured = lambda battle, attacker, target: True
        pen = actions.base.obscured_penalty(b, c, foe)
        assert pen == 3  # 4 - 1 = 3

        plain_u = _body("player", "Plain")
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
    pen = actions._off_guard_penalty(b, c1, cf)
    assert pen == 2

    # Give defender Peripheral Vision
    cf.char.set_track_level("combat", 1)
    cf.char.choose_talent("combat", "alert")
    cf.char.set_track_level("combat", 2)
    cf.char.choose_talent("combat", "quick_wits")
    cf.char.set_track_level("combat", 3)
    assert cf.char.choose_talent("combat", "peripheral_vision")

    pen_with_talent = actions._off_guard_penalty(b, c1, cf)
    assert pen_with_talent == 1

    # In attack resolution, log shows [Off-guard -1]
    with fixed_d20(15):
        actions._strike(b, c1, cf)
        assert any("[Off-guard -1: flanked]" in line for line in b.log_lines)


# --------------------------------------------------------------------------- #
# Charisma Combat Tree: Imposing, Menacing, Gruesome Takedown, Cull the Broken#
# --------------------------------------------------------------------------- #

def test_charisma_combat_tree_progression():
    u = _body("player", "Warlord")
    base_cha = u.charisma

    # Tier 1: Imposing (+1 CHA)
    u.set_track_level("combat", 1)
    assert u.choose_talent("combat", "imposing")
    assert u.charisma == base_cha + 1

    # Tier 2a: Menacing (+1 Demoralize)
    u.set_track_level("combat", 2)
    assert u.choose_talent("combat", "menacing")
    assert u.talent_bonus("demoralize_bonus") == 2

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
    u1 = _body("player", "Executioner")
    u1.set_track_level("combat", 1)
    u1.choose_talent("combat", "imposing")
    u1.set_track_level("combat", 2)
    u1.choose_talent("combat", "gruesome_takedown")

    f1 = _body("enemy", "Weakling", "Goblin")
    f2 = _body("enemy", "Bystander", "Orc")
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
    u = _body("player", "Scholar")
    base_int = u.intelligence

    # Tier 1: Tactical Mind (+1 INT)
    u.set_track_level("combat", 1)
    assert u.choose_talent("combat", "tactical_mind")
    assert u.intelligence == base_int + 1

    # Tier 2a: Sharp Analysis (+1 on all Assess / observation)
    u.set_track_level("combat", 2)
    assert u.choose_talent("combat", "sharp_analysis")
    assert u.talent_bonus("assess_bonus") == 2

    # Tier 2b / Tier 3: on another unit
    u2 = _body("player", "Tactician")
    u2.set_track_level("combat", 1)
    u2.choose_talent("combat", "tactical_mind")
    u2.set_track_level("combat", 2)
    assert u2.choose_talent("combat", "combat_analysis")
    assert u2.talent_bonus("assess_active_bonus") == 4

    # Tier 3: Exploit Weakness (+2 to hit vs full intel)
    u2.set_track_level("combat", 3)
    assert u2.choose_talent("combat", "exploit_weakness")
    assert u2.talent_bonus("full_intel_to_hit") == 2


def test_exploit_weakness_grants_plus_2_to_hit_on_full_intel():
    u = _body("player", "Analyst")
    u.set_track_level("combat", 1)
    u.choose_talent("combat", "tactical_mind")
    u.set_track_level("combat", 2)
    u.choose_talent("combat", "combat_analysis")
    u.set_track_level("combat", 3)
    u.choose_talent("combat", "exploit_weakness")

    f = _body("enemy", "Subject", "Goblin")
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


# --------------------------------------------------------------------------- #
# New Tier 3 Combat Talents (30-talent expansion)                             #
# --------------------------------------------------------------------------- #

def test_wrestler_bonus_push_and_grab():
    u = _body("player", "Grappler")
    u.set_track_level("combat", 1)
    u.choose_talent("combat", "strong")
    u.set_track_level("combat", 2)
    u.choose_talent("combat", "heavy_hand")
    u.set_track_level("combat", 3)
    assert u.choose_talent("combat", "wrestler")
    assert u.talent_bonus("push_bonus") == 1
    assert u.talent_bonus("grab_bonus") == 1

    f = _body("enemy", "Gobbo", "Goblin")
    b = Battle([u], [f])
    c, foe = b.units
    c.pos, foe.pos = (5, 5), (6, 5)

    # Push with wrestler
    with fixed_d20(10):
        actions.PUSH.execute(b, c, foe)
    assert any("push talent" in line for line in b.log_lines)


def test_nimble_skirmisher_flank_damage():
    u1 = _body("player", "Rogue")
    u1.set_track_level("combat", 1)
    u1.choose_talent("combat", "agile")
    u1.set_track_level("combat", 2)
    u1.choose_talent("combat", "deadeye")
    u1.set_track_level("combat", 3)
    assert u1.choose_talent("combat", "nimble_skirmisher")
    assert u1.talent_bonus("off_guard_finesse_damage") == 2

    u2 = _body("player", "Buddy")
    f = _body("enemy", "FlankTarget", "Goblin")
    f.hp = 30
    f.max_hp = 30

    b = Battle([u1, u2], [f])
    c1, c2, cf = b.units
    c1.equip_weapon(fitted(c1, "Rapier"))
    # Flank positions: c1 at (4, 5), cf at (5, 5), c2 at (6, 5)
    c1.pos, cf.pos, c2.pos = (4, 5), (5, 5), (6, 5)

    initial_hp = cf.hp
    with fixed_d20(15):
        actions.ATTACK.execute(b, c1, cf)
    dmg = initial_hp - cf.hp
    # Rapier 1d8 + DEX mod + 2 flank damage
    assert dmg > 0
    assert any("hit" in line for line in b.log_lines)


def test_iron_stance_defend_mental_defense():
    u = _body("player", "Monk")
    u.set_track_level("combat", 1)
    u.choose_talent("combat", "alert")
    u.set_track_level("combat", 2)
    u.choose_talent("combat", "iron_will")
    u.set_track_level("combat", 3)
    assert u.choose_talent("combat", "iron_stance")
    assert u.talent_bonus("defend_mental_defense") == 2

    b = Battle([u], [_body("enemy", "Foe", "Goblin")])
    c, _ = b.units
    base_md = c.mental_defense
    actions.DEFEND.execute(b, c)
    assert c.has_condition("defending")
    assert c.mental_defense == base_md + 2


def _taught(unit, *ids):
    for level, tid in enumerate(ids, 1):
        unit.set_track_level("combat", level)
        assert unit.choose_talent("combat", tid)


def test_inspiring_shout_gives_the_weariest_ally_a_point_of_morale_back():
    u1, u2, u3 = _body("player", "Leader"), _body("player", "Follower"), _body("player", "Weary")
    _taught(u1, "imposing", "gruesome_takedown", "inspiring_shout")
    assert u1.talent_bonus("demoralize_rally") == 1
    f = _body("enemy", "WeakFoe", "Goblin")
    f.languages = u1.languages
    b = Battle([u1, u2, u3], [f], lethal=True)
    c1, c2, c3, cf = b.units
    c1.pos, c2.pos, c3.pos, cf.pos = (5, 5), (5, 6), (5, 7), (6, 5)
    c2.morale, c3.morale = c2.morale_max - 1, c3.morale_max - 3
    with fixed_d20(20):
        actions.DEMORALIZE.execute(b, c1, cf)
    assert cf.has_condition("demoralized")
    assert c3.morale == c3.morale_max - 2 and c2.morale == c2.morale_max - 1
    assert any("Inspiring Shout" in line and "morale" in line for line in b.log_lines)


def test_inspiring_shout_with_no_weary_ally_speeds_the_last_one_in_the_order():
    u1, u2, u3 = _body("player", "Leader"), _body("player", "First"), _body("player", "Last")
    _taught(u1, "imposing", "gruesome_takedown", "inspiring_shout")
    f = _body("enemy", "WeakFoe", "Goblin")
    f.languages = u1.languages
    b = Battle([u1, u2, u3], [f], lethal=True)
    c1, c2, c3, cf = b.units
    c1.pos, c2.pos, c3.pos, cf.pos = (5, 5), (5, 6), (5, 7), (6, 5)
    last = [u for u in b.order if u in (c2, c3)][-1]
    other = c2 if last is c3 else c3
    before, other_before = last.initiative, other.initiative
    with fixed_d20(20):
        actions.DEMORALIZE.execute(b, c1, cf)
    assert last.initiative == before + 1 and other.initiative == other_before
    assert last.morale == last.morale_max and not any("morale back" in line for line in b.log_lines)


def test_inspiring_shout_speeds_the_weariest_ally_and_gives_it_morale_back():
    u1, u2, u3 = _body("player", "Leader"), _body("player", "Fine"), _body("player", "Weary")
    _taught(u1, "imposing", "gruesome_takedown", "inspiring_shout")
    f = _body("enemy", "WeakFoe", "Goblin")
    f.languages = u1.languages
    b = Battle([u1, u2, u3], [f], lethal=True)
    c1, c2, c3, cf = b.units
    c1.pos, c2.pos, c3.pos, cf.pos = (5, 5), (5, 6), (5, 7), (6, 5)
    c3.morale = c3.morale_max - 2
    before, fine_before = c3.initiative, c2.initiative
    with fixed_d20(20):
        actions.DEMORALIZE.execute(b, c1, cf)
    assert c3.initiative == before + 1 and c3.morale == c3.morale_max - 1 and c2.initiative == fine_before


def test_dread_voice_takes_two_morale_per_demoralize():
    u1 = _body("player", "Tyrant")
    _taught(u1, "imposing", "menacing", "dread_voice")
    f = _body("enemy", "Victim", "Goblin")
    f.languages = u1.languages
    b = Battle([u1], [f], lethal=True)
    c1, cf = b.units
    c1.pos, cf.pos = (5, 5), (6, 5)
    before = cf.morale
    with fixed_d20(20):
        actions.DEMORALIZE.execute(b, c1, cf)
    b.settle_morale()
    assert cf.morale == before - 2


def test_dread_voice_costs_nothing_when_the_demoralize_misses():
    u1 = _body("player", "Tyrant")
    _taught(u1, "imposing", "menacing", "dread_voice")
    f = _body("enemy", "Victim", "Goblin")
    f.languages = u1.languages
    b = Battle([u1], [f], lethal=True)
    c1, cf = b.units
    c1.pos, cf.pos = (5, 5), (6, 5)
    before = cf.morale
    with fixed_d20(2):
        actions.DEMORALIZE.execute(b, c1, cf)
    b.settle_morale()
    assert cf.morale == before and cf.demoralize_extra == 0


def test_grim_chorus_makes_a_free_demoralize_when_an_ally_downs_a_foe():
    u1, u2 = _body("player", "Executioner"), _body("player", "Chorus")
    _taught(u2, "imposing", "gruesome_takedown", "grim_chorus")
    f1, f2 = _body("enemy", "Weakling", "Goblin"), _body("enemy", "Bystander", "Orc")
    f2.languages = ("Orcish",)
    b = Battle([u1, u2], [f1, f2])
    c1, c2, cf1, cf2 = b.units
    c1.pos, c2.pos, cf1.pos, cf2.pos = (5, 5), (4, 8), (6, 5), (4, 10)
    cf1.hp = 2
    c1.damage_roll = lambda **kw: 10
    with fixed_d20(20):
        actions._strike(b, c1, cf1)
    assert cf1.hp <= 0
    assert any("Grim Chorus" in line for line in b.log_lines)
    assert cf2.has_condition("demoralized")


def test_grim_chorus_stays_quiet_for_an_ally_without_the_talent():
    u1, u2 = _body("player", "Executioner"), _body("player", "Plain")
    f1, f2 = _body("enemy", "Weakling", "Goblin"), _body("enemy", "Bystander", "Orc")
    b = Battle([u1, u2], [f1, f2])
    c1, c2, cf1, cf2 = b.units
    c1.pos, c2.pos, cf1.pos, cf2.pos = (5, 5), (4, 8), (6, 5), (4, 10)
    cf1.hp = 2
    c1.damage_roll = lambda **kw: 10
    with fixed_d20(20):
        actions._strike(b, c1, cf1)
    assert not any("Grim Chorus" in line for line in b.log_lines)


def test_anatomist_crit_range_full_intel():
    u = _body("player", "Doctor")
    u.set_track_level("combat", 1)
    u.choose_talent("combat", "tactical_mind")
    u.set_track_level("combat", 2)
    u.choose_talent("combat", "sharp_analysis")
    u.set_track_level("combat", 3)
    assert u.choose_talent("combat", "anatomist")
    assert u.talent_bonus("full_intel_crit_range") == 1

    f = _body("enemy", "Specimen", "Goblin")
    f.hp = 30
    f.max_hp = 30
    b = Battle([u], [f])
    c, cf = b.units
    c.pos, cf.pos = (5, 5), (6, 5)

    # Not full intel: roll 19 is normal hit (crit is 20)
    b.intel.margin["player"][cf] = 2
    with fixed_d20(19):
        res = actions.base._resolve_hit(b, c, cf, 19, 0, "+0", "Test")
        assert res == "hit"

    # Full intel: roll 19 becomes CRITICAL HIT (crit is 19-20)
    b.intel.margin["player"][cf] = 12
    with fixed_d20(19):
        res = actions.base._resolve_hit(b, c, cf, 19, 0, "+0", "Test")
        assert res == "crit"
