"""Tests for the new combat talents and flanking mechanics:
- Strength T3: Blind Strike (reduces obscured penalty by 1)
- Wisdom T3: Peripheral Vision (reduces flanked AC penalty from 2 to 1)
- Charisma combat tree: Imposing, Menacing, Gruesome Takedown, Cull the Broken
- Intelligence combat tree: Tactical Mind, Analytical Eye, Exploit Weakness, Anatomist
"""

from gartok import actions, intel
from gartok.combatant import Combatant
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
# Intelligence Combat Tree: Tactical Mind, Analytical Eye, Exploit Weakness, Anatomist
# --------------------------------------------------------------------------- #

def test_intelligence_combat_tree_progression():
    u = _body("player", "Scholar")
    base_int = u.intelligence

    # Tier 1: Tactical Mind (+1 INT)
    u.set_track_level("combat", 1)
    assert u.choose_talent("combat", "tactical_mind")
    assert u.intelligence == base_int + 1

    # Tier 2: Analytical Eye (+2 on every read, +2 more on the Assess action)
    u.set_track_level("combat", 2)
    assert u.choose_talent("combat", "analytical_eye")
    assert u.talent_bonus("assess_bonus") == 2
    assert u.talent_bonus("assess_active_bonus") == 2

    # Tier 3: both riders ask for it; Exploit Weakness (+1 to hit vs full intel)
    u.set_track_level("combat", 3)
    assert u.choose_talent("combat", "exploit_weakness")
    assert u.talent_bonus("full_intel_to_hit") == 1
    u.set_track_level("combat", 4)
    assert u.choose_talent("combat", "anatomist")


def test_exploit_weakness_grants_plus_1_to_hit_on_full_intel():
    u = _body("player", "Analyst")
    u.set_track_level("combat", 1)
    u.choose_talent("combat", "tactical_mind")
    u.set_track_level("combat", 2)
    u.choose_talent("combat", "analytical_eye")
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
    assert any("Exploit Weakness" in label and val == 1 for val, _, label in mods_full)


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
    u.choose_talent("combat", "analytical_eye")
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
        res = actions.base._resolve_hit(b, c, cf, 19, 0, [], "Test")
        assert res == "hit"

    # Full intel: roll 19 becomes CRITICAL HIT (crit is 19-20)
    b.intel.margin["player"][cf] = 12
    with fixed_d20(19):
        res = actions.base._resolve_hit(b, c, cf, 19, 0, [], "Test")
        assert res == "crit"


def test_a_hit_logs_its_damage_roll_dice_and_modifiers():
    b, c1, _, cf = _squad_battle()
    cf.hp, cf.hp_max = 50, 50
    with fixed_d20(15):
        actions._strike(b, c1, cf)
    line = next(x for x in b.log_lines if "Damage:" in x)
    dealt = 50 - cf.hp
    assert f"= {dealt}" in line and c1.damage_detail().split("(")[0] in line


def test_a_critical_hit_logs_the_multiplier():
    b, c1, _, cf = _squad_battle()
    cf.hp, cf.hp_max = 50, 50
    with fixed_d20(20):
        actions._strike(b, c1, cf)
    assert "x2" in next(x for x in b.log_lines if "Damage:" in x)


# --------------------------------------------------------------------------- #
# Dexterity tree, tier 3-4: Steady Aim and Queen's Arrow
# --------------------------------------------------------------------------- #


def _archer(weapon, *talents):
    u = standard_unit("player")
    u.combat_xp = 1000
    for t in ("agile", "deadeye", *talents):
        assert u.choose_talent("combat", t)
    u.give_to_pack("Quiver")
    u.give_to_hand(weapon)
    shooter = Combatant(u)
    shooter.crossbow_loaded = True
    return shooter


def _top(shooter, **kw):
    return max(shooter.damage_roll(**kw) for _ in range(300))


def test_steady_aim_adds_one_damage_to_a_bow_and_a_crossbow_and_to_no_other_weapon():
    for weapon in ("Shortbow", "Longbow", "Crossbow"):
        assert _top(_archer(weapon, "steady_aim")) == _top(_archer(weapon)) + 1, weapon
    sword = _archer("Shortsword", "steady_aim")
    assert not sword.ranged
    assert _top(sword) == _top(_archer("Shortsword"))


def test_steady_aim_does_not_touch_a_thrown_weapon():
    thrower = _archer("Javelin", "steady_aim")
    plain = _archer("Javelin")
    assert _top(thrower, thrown=True) == _top(plain, thrown=True)


def test_steady_aim_stacks_with_heavy_bolts_on_a_crossbow():
    both = _archer("Crossbow", "steady_aim", "heavy_bolts")
    assert _top(both) == _top(_archer("Crossbow")) + 2


def test_the_archery_ladder_hangs_from_deadeye():
    u = standard_unit("player")
    u.combat_xp = 1000
    assert not u.choose_talent("combat", "steady_aim")
    assert u.choose_talent("combat", "agile") and u.choose_talent("combat", "deadeye")
    assert not u.choose_talent("combat", "true_line")
    assert u.choose_talent("combat", "steady_aim") and u.choose_talent("combat", "true_line")


def _brutal_at(shooter, target_pos, shooter_pos=(5, 5), thrown=False):
    from gartok.actions import base
    batt = Battle([standard_unit("player")], [standard_unit("enemy")])
    foe = batt.units[1]
    foe.turns_taken = 1
    shooter.pos, foe.pos = shooter_pos, target_pos
    seen = []
    real = shooter.damage_roll
    shooter.damage_roll = lambda **kw: seen.append(kw["brutal"]) or real(**kw)
    with fixed_d20(10):
        base._resolve_hit(batt, shooter, foe, 10, 99, [], "x", thrown=thrown)
    return seen[0]


def test_true_line_makes_a_shot_brutal_on_a_row_a_column_and_a_diagonal():
    for weapon in ("Shortbow", "Crossbow"):
        shooter = _archer(weapon, "steady_aim", "true_line")
        for cell in ((9, 5), (5, 9), (1, 5), (5, 2), (8, 8), (2, 2), (8, 2), (2, 8)):
            assert _brutal_at(shooter, cell) == 1, (weapon, cell)


def test_true_line_does_not_apply_one_cell_off_the_line():
    shooter = _archer("Longbow", "steady_aim", "true_line")
    for cell in ((9, 6), (8, 9), (7, 8), (6, 8)):
        assert _brutal_at(shooter, cell) == 0, cell


def test_true_line_needs_the_talent_and_a_shot():
    assert _brutal_at(_archer("Shortbow", "steady_aim"), (9, 5)) == 0
    assert _brutal_at(_archer("Javelin", "steady_aim", "true_line"), (9, 5), thrown=True) == 0
    assert _brutal_at(_archer("Shortsword", "steady_aim", "true_line"), (6, 5)) == 0


def test_the_ai_values_an_aligned_shot_above_a_crooked_one():
    from gartok.ai import reckon
    batt = Battle([standard_unit("player")], [standard_unit("enemy")])
    foe = batt.units[1]
    shooter = _archer("Longbow", "steady_aim", "true_line")
    shooter.team = "player"
    shooter.pos = (5, 5)
    foe.pos = (9, 5)
    aligned = reckon._strike_worth(batt, shooter, foe)
    foe.pos = (9, 6)
    assert aligned > reckon._strike_worth(batt, shooter, foe)
    assert reckon._blow(_archer("Longbow", "steady_aim")) == reckon._blow(_archer("Longbow")) + 1


def _placing_battle(*talents, leader=False, allies=1):
    from gartok.battle import Battle
    from gartok.scenario import Scenario
    squad = [standard_unit("player") for _ in range(allies + 1)]
    squad[0].combat_xp = 1000
    squad[0].leads_group = leader
    for t in talents:
        assert squad[0].choose_talent("combat", t)
    return Battle(squad, [standard_unit("enemy")], scenario=Scenario(), lethal=True), squad


def _vantage(*extra, **kw):
    return _placing_battle("tactical_mind", "vantage", *extra, **kw)


def test_without_vantage_nobody_places_before_the_fight():
    batt, _ = _placing_battle()
    assert batt.place_queue == [] and batt.awaiting_place is None


def test_vantage_lets_its_holder_pick_a_start_cell_inside_the_side_zone():
    batt, squad = _vantage()
    holder = next(u for u in batt.units if u.char is squad[0])
    assert batt.place_queue == [holder] and batt.awaiting_place is holder
    cells_ = batt.place_cells(holder)
    assert cells_ and all(c in batt.start_zones["player"] for c in cells_)
    target = cells_[-1]
    batt.place(holder, target)
    assert holder.pos == target and batt.awaiting_place is None
    outside = (batt.board.cols - 1, 0)
    assert not batt.can_place(holder, outside)


def test_a_placed_unit_may_not_stand_on_another_body():
    batt, squad = _vantage()
    holder = next(u for u in batt.units if u.char is squad[0])
    mate = next(u for u in batt.units if u.team == "player" and u is not holder)
    assert not batt.can_place(holder, mate.pos)


def test_holding_position_leaves_the_holder_where_deployment_put_it():
    batt, squad = _vantage()
    holder = next(u for u in batt.units if u.char is squad[0])
    where = holder.pos
    batt.skip_place()
    assert holder.pos == where and batt.awaiting_place is None


def test_battle_plan_gives_the_leader_the_whole_side_to_place():
    batt, squad = _vantage("battle_plan", leader=True, allies=2)
    sides = [u for u in batt.units if u.team == "player"]
    assert set(batt.place_queue) == set(sides)
    batt.skip_place(rest=True)
    assert batt.place_queue == []


def test_battle_plan_does_nothing_for_a_member_who_does_not_lead():
    batt, squad = _vantage("battle_plan", leader=False, allies=2)
    holder = next(u for u in batt.units if u.char is squad[0])
    assert batt.place_queue == [holder]


def test_the_flag_and_the_traps_come_before_the_placement(monkeypatch):
    from gartok.battle import Battle
    batt, _ = _vantage()
    monkeypatch.setattr(Battle, "awaiting_flag", property(lambda self: True))
    assert batt.awaiting_place is None


def test_a_placement_goes_to_the_combat_log(tmp_path):
    from gartok import combat_log
    batt, squad = _vantage()
    log = combat_log.CombatLog(str(tmp_path / "place.jsonl"), {}, {})
    batt.record_to(log)
    holder = next(u for u in batt.units if u.char is squad[0])
    batt.place(holder, batt.place_cells(holder)[0])
    assert combat_log.load(log.path)[1]["action"] == "place"


def test_the_leader_must_be_on_the_board_for_the_whole_side_to_place():
    from gartok.battle import Battle
    from gartok.scenario import Scenario
    holder, mate = standard_unit("player"), standard_unit("player")
    holder.combat_xp = 1000
    holder.leads_group = True
    for t in ("tactical_mind", "vantage", "battle_plan"):
        assert holder.choose_talent("combat", t)
    batt = Battle([mate], [standard_unit("enemy")], scenario=Scenario(), lethal=True)
    batt.units[0].char.leads_group = False
    assert batt.place_queue == []


def test_a_surprised_side_does_not_place():
    batt, squad = _vantage()
    holder = next(u for u in batt.units if u.char is squad[0])
    assert batt.place_queue == [holder]
    batt.open_with(surprised="player")
    assert batt.place_queue == [] and batt.awaiting_place is None


def test_the_combat_log_frames_follow_a_placement(tmp_path):
    from gartok import combat_log
    batt, squad = _vantage()
    log = combat_log.CombatLog(str(tmp_path / "frames.jsonl"), {}, {})
    batt.record_to(log)
    holder = next(u for u in batt.units if u.char is squad[0])
    target = batt.place_cells(holder)[-1]
    batt.place(holder, target)
    last = combat_log.frames(combat_log.load(log.path))[-1]
    idx = batt.units.index(holder)
    assert (last["units"][idx]["x"], last["units"][idx]["y"]) == tuple(target)
