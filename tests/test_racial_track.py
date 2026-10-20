"""The racial track's second pass (2026-10-20): two more nodes per playable race, one more
for the Ox -- registry, every effect, the three new actions and how the AI plays them."""

import random
from unittest.mock import patch

import pytest

from gartok import ai, campaign, cohesion, dialogue, persist, talents, vision
from gartok.actions.base import _held_line, _resolve_hit
from gartok.guild import Guild
from gartok.unit_hunger import BLOOM_FRUIT
from tests.helpers import Battle, GroundObject, Unit, actions, data, patch_action_d20


def _racial(race, *picks, team="player", seed=0):
    random.seed(seed)
    u = Unit(team, race=data.race_by_name(race))
    u.set_track_level("racial", 15)
    for p in picks:
        assert u.choose_talent("racial", p), p
    return u


def _duel(a, b, apos=(5, 5), bpos=(6, 5)):
    """A clear, lit board with `a` (player side) and `b` (enemy side) placed."""
    batt = Battle([a], [b])
    ca, cb = batt.player_units[0], batt.enemy_units[0]
    batt.board.walls = set()
    batt.ambient_light = True
    ca.pos, cb.pos = apos, bpos
    batt.clear_pf_cache()
    return batt, ca, cb


# --------------------------------------------------------------------------- #
# registry                                                                     #
# --------------------------------------------------------------------------- #

def test_every_playable_race_and_the_ox_has_three_racial_nodes_of_its_own():
    for name in [r["name"] for r in data._RACES] + ["Ox"]:
        own = [t for t in talents.racial_tree(name) if name in t.races]
        assert len(own) >= 3, name


def test_a_tier_two_racial_node_hangs_off_a_node_of_the_same_race():
    for t in talents.TREE["racial"]:
        if t.tier >= 2 and t.requires:
            parent = talents.get(t.requires)
            assert parent.track == "racial"
            assert set(t.races) <= set(parent.races), t.id


def test_a_tier_two_node_needs_its_parent_first():
    u = Unit("player", race=data.race_by_name("Centaur"))
    u.set_track_level("racial", 15)
    assert not u.choose_talent("racial", "cavalry_charge")
    assert u.choose_talent("racial", "centaur_mount")
    assert u.choose_talent("racial", "cavalry_charge")


def test_another_race_cannot_pick_them():
    u = Unit("player", race=data.race_by_name("Human"))
    u.set_track_level("racial", 15)
    assert not u.choose_talent("racial", "grudge")


@pytest.mark.parametrize("race, picks, channel, amount", [
    ("Automaton", ("iron_plating",), "ac", 1),
    ("Ox", ("thick_hide",), "ac", 1),
    ("Automaton", ("self_repair",), "post_combat_heal", 1),
    ("Elf", ("light_step",), "speed", 1),
    ("Halfling", ("brave",), "mental_defense", 2),
    ("Halfling", ("second_breakfast",), "rest_heal_bonus", 1),
    ("Gnome", ("gnome_magic_excitement", "arcane_curiosity"), "spell_range", 1),
    ("Human", ("cosmopolitan", "polyglot"), "language_study", 2),
    ("Kenku", ("eye_for_detail",), "assess_bonus", 1),
    ("Kenku", ("mimic_voices",), "tavern_perform_bonus", 1),
    ("Orc", ("war_cry",), "demoralize_bonus", 1),
])
def test_the_nodes_that_reuse_a_channel_feed_it(race, picks, channel, amount):
    u = _racial(race, *picks)
    assert u.talent_bonus(channel) == amount


def test_iron_plating_raises_the_derived_ac():
    random.seed(4)
    u = Unit("player", race=data.race_by_name("Automaton"))
    u.set_track_level("racial", 5)
    before = u.ac
    assert u.choose_talent("racial", "iron_plating")
    u._derive_combat()
    assert u.ac == before + 1


def test_self_repair_heals_a_point_after_the_fight():
    u = _racial("Automaton", "self_repair")
    _batt, ca, _ = _duel(u, Unit("enemy"))
    ca.hp = u.hp_max - 3
    campaign._carry_forward(u, ca)
    assert u.hp == u.hp_max - 2


# --------------------------------------------------------------------------- #
# to hit                                                                       #
# --------------------------------------------------------------------------- #

def _labels(mods):
    return {m[2] for m in mods}


def test_grudge_hits_harder_at_whoever_hurt_you():
    batt, dwarf, foe = _duel(_racial("Dwarf", "grudge"), Unit("enemy"))
    foe.turns_taken = 1
    assert "Grudge" not in _labels(dwarf.racial_hit_mods(batt, foe))
    dwarf.hurt_by.add(foe)
    assert "Grudge" in _labels(dwarf.racial_hit_mods(batt, foe))


def test_a_hit_that_lands_damage_marks_the_attacker():
    batt, dwarf, foe = _duel(_racial("Dwarf", "grudge"), Unit("enemy"))
    _resolve_hit(batt, foe, dwarf, 19, 30, "", "test")
    assert foe in dwarf.hurt_by


def test_ambush_predator_only_against_a_foe_yet_to_act():
    batt, liz, foe = _duel(_racial("Lizardfolk", "ambush_predator"), Unit("enemy"))
    foe.turns_taken = 0
    assert (2, None, "Ambush Predator") in liz.racial_hit_mods(batt, foe)
    foe.start_turn(batt.log)
    assert "Ambush Predator" not in _labels(liz.racial_hit_mods(batt, foe))


def test_under_the_whip_needs_a_stronger_ally_close_by():
    goblin = _racial("Goblin", "under_the_whip")
    boss = Unit("player")
    boss.set_track_level("combat", goblin.combat_level + 3)
    batt = Battle([goblin, boss], [Unit("enemy")])
    g, b = batt.player_units
    foe = batt.enemy_units[0]
    g.pos, b.pos, foe.pos = (5, 5), (8, 5), (6, 5)
    assert "Under the Whip" in _labels(g.racial_hit_mods(batt, foe))
    b.pos = (15, 11)
    assert "Under the Whip" not in _labels(g.racial_hit_mods(batt, foe))
    b.pos = (8, 5)
    boss.set_track_level("combat", goblin.combat_level)
    assert "Under the Whip" not in _labels(g.racial_hit_mods(batt, foe))


def test_arena_born_only_in_the_pit():
    batt, gol, foe = _duel(_racial("Goliath", "arena_born"), Unit("enemy"))
    assert "Arena Born" not in _labels(gol.racial_hit_mods(batt, foe))
    batt.arena = True
    assert "Arena Born" in _labels(gol.racial_hit_mods(batt, foe))


def test_cavalry_charge_helps_the_rider_once_the_centaur_has_moved():
    centaur = _racial("Centaur", "centaur_mount", "cavalry_charge")
    random.seed(2)
    rider = Unit("player", race=data.race_by_name("Human"))
    batt = Battle([centaur, rider], [Unit("enemy")])
    c, r = batt.player_units
    foe = batt.enemy_units[0]
    r.mounted_on, c.rider = c, r
    assert "Cavalry Charge" not in _labels(r.racial_hit_mods(batt, foe))
    c.path = [(3, 5), (4, 5), (5, 5)]
    assert (2, None, "Cavalry Charge") in r.racial_hit_mods(batt, foe)


def test_the_racial_mods_reach_the_attack_roll():
    batt, liz, foe = _duel(_racial("Lizardfolk", "ambush_predator"), Unit("enemy"))
    mods = liz.attack_mods(foe, False, battle=batt)
    assert "Ambush Predator" in _labels(mods)


# --------------------------------------------------------------------------- #
# armour class                                                                 #
# --------------------------------------------------------------------------- #

def test_underfoot_against_large_attackers_only():
    _batt, gnome, foe = _duel(_racial("Gnome", "underfoot"), Unit("enemy"))
    base = gnome.ac_vs(foe, ranged=False)
    foe.char.size = "Large"
    assert gnome.ac_vs(foe, ranged=False) == base + 2


def test_tiny_target_against_ranged_blows_only():
    _batt, sprite, foe = _duel(_racial("Sprite", "tiny_target"), Unit("enemy"))
    assert sprite.ac_vs(foe, ranged=True) == sprite.ac_vs(foe, ranged=False) + 2


def test_hold_the_line_lends_ac_to_allies_beside_the_defender():
    hob = _racial("Hobgoblin", "hold_the_line")
    batt = Battle([hob, Unit("player")], [Unit("enemy")])
    h, ally = batt.player_units
    h.pos, ally.pos = (5, 5), (5, 6)
    assert _held_line(batt, ally) == 0
    actions.DEFEND.execute(batt, h)
    assert _held_line(batt, ally) == 1
    ally.pos = (9, 9)
    assert _held_line(batt, ally) == 0
    assert _held_line(batt, h) == 0          # the defender has their own Defend


# --------------------------------------------------------------------------- #
# damage                                                                       #
# --------------------------------------------------------------------------- #

def _hit(batt, attacker, target, nat=19):
    hp = target.hp
    with patch("gartok.combatant.roll", return_value=1), patch("gartok.actions.base.roll", return_value=1):
        _resolve_hit(batt, attacker, target, nat, 40, "", "test")
    return hp - target.hp


def test_blood_frenzy_on_a_target_below_half():
    batt, gnoll, foe = _duel(_racial("Gnoll", "blood_frenzy"), Unit("enemy"))
    gnoll.char.strength = 18
    gnoll.char._derive_combat()
    foe.hp = foe.hp_max = 100
    full = _hit(batt, gnoll, foe)
    foe.hp = 40
    assert _hit(batt, gnoll, foe) == full + 2


def test_savage_attacks_rolls_one_more_die_on_a_crit():
    _batt, orc, _foe = _duel(_racial("Orc", "savage_attacks"), Unit("enemy"))
    with patch("gartok.combatant.roll", return_value=1) as dice:
        savage = orc.damage_roll(crit=True)
        orc.char.talents["racial"].remove("savage_attacks")
        plain = orc.damage_roll(crit=True)
    assert savage == plain + 1
    assert dice.call_count == 5


def test_stone_endurance_softens_only_the_first_blow():
    batt, gol, foe = _duel(_racial("Goliath", "stone_endurance"), Unit("enemy"))
    gol.hp = gol.hp_max = 100
    gol.char.constitution = 14
    gol.char._derive_combat()
    gol.hp = 100
    foe.char.strength = 18
    foe.char._derive_combat()
    first = _hit(batt, foe, gol)
    second = _hit(batt, foe, gol)
    assert first == max(0, second - (1 + gol.mod_constitution))
    assert any("Stone's Endurance" in ln for ln in batt.log_lines)


def test_thornskin_pricks_a_melee_attacker():
    batt, tree, foe = _duel(_racial("Treefolk", "thornskin"), Unit("enemy"))
    foe.hp = foe.hp_max = 50
    _hit(batt, foe, tree)
    assert foe.hp == 49


def test_thornskin_does_not_prick_a_ranged_shot():
    batt, tree, foe = _duel(_racial("Treefolk", "thornskin"), Unit("enemy"), bpos=(9, 5))
    foe.hp = foe.hp_max = 50
    with patch("gartok.combatant.roll", return_value=1):
        _resolve_hit(batt, foe, tree, 19, 40, "", "shot", thrown=True)
    assert foe.hp == 50


def test_gore_charge_throws_the_target_after_a_run_up():
    batt, ox, foe = _duel(_racial("Ox", "gore_charge"), Unit("enemy"))
    foe.hp = foe.hp_max = 100
    ox.path = [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]
    _hit(batt, ox, foe)
    assert foe.pos == (8, 5)


def test_gore_charge_needs_the_run_up():
    batt, ox, foe = _duel(_racial("Ox", "gore_charge"), Unit("enemy"))
    foe.hp = foe.hp_max = 100
    ox.path = [(4, 5), (5, 5)]
    _hit(batt, ox, foe)
    assert foe.pos == (6, 5)


# --------------------------------------------------------------------------- #
# senses                                                                       #
# --------------------------------------------------------------------------- #

def test_twilight_sight_sees_a_short_way_into_the_dark():
    batt, elf, foe = _duel(_racial("Elf", "twilight_sight"), Unit("enemy"))
    batt.ambient_light = False
    batt.ground = []
    elf.torch_hand = foe.torch_hand = elf.lantern_hand = foe.lantern_hand = False
    assert vision.dark_range(elf) == 4
    assert vision.can_see(batt, elf, (8, 5))
    assert not vision.can_see(batt, elf, (11, 5))
    assert "twilight sight" in vision.vision_desc(elf)


def test_without_twilight_sight_the_dark_is_dark():
    random.seed(0)
    batt, elf, _foe = _duel(Unit("player", race=data.race_by_name("Elf")), Unit("enemy"))
    batt.ambient_light = False
    elf.torch_hand = False
    batt.ground = []
    assert not vision.can_see(batt, elf, (8, 5))


def test_bloodscent_finds_the_wounded_through_a_wall():
    batt, gnoll, foe = _duel(_racial("Gnoll", "bloodscent"), Unit("enemy"), bpos=(9, 5))
    batt.board.walls = {(7, y) for y in range(batt.board.rows)}
    foe.hp = foe.hp_max
    assert not batt.can_see_unit(gnoll, foe)
    foe.hp = foe.hp_max // 2 - 1
    assert batt.can_see_unit(gnoll, foe)
    foe.pos = (14, 5)
    assert not batt.can_see_unit(gnoll, foe)


# --------------------------------------------------------------------------- #
# movement and grappling                                                       #
# --------------------------------------------------------------------------- #

def test_frog_leap_jumps_two_squares_farther():
    random.seed(0)
    plain = Unit("player", race=data.race_by_name("Grippli"))
    batt, frog, _ = _duel(_racial("Grippli", "frog_leap"), Unit("enemy"), bpos=(0, 0))
    batt2, other, _ = _duel(plain, Unit("enemy"), bpos=(0, 0))
    frog.char.strength = other.char.strength = 10
    assert actions.JUMP._max_reach(batt, frog) == actions.JUMP._max_reach(batt2, other) + 2


def test_sticky_tongue_reels_in_and_grabs():
    grippli = _racial("Grippli", "tongue", "sticky_tongue")
    assert grippli.give_to_tongue("Dagger") or grippli.give_to_tongue("Club")
    batt, g, foe = _duel(grippli, Unit("enemy"), bpos=(7, 5))
    foe.hp = foe.hp_max = 100
    with patch_action_d20(return_value=19):
        actions.ATTACK_TONGUE.execute(batt, g, foe)
    assert foe.pos == (6, 5)
    assert foe.has_condition("grappled")


# --------------------------------------------------------------------------- #
# traps                                                                        #
# --------------------------------------------------------------------------- #

def test_trap_master_plants_further_out():
    kobold = _racial("Kobold", "kobold_trapper")
    batt, k, _ = _duel(kobold, Unit("enemy"), bpos=(0, 0))
    assert batt.can_plant_trap(k, (6, 5))
    assert not batt.can_plant_trap(k, (8, 5))
    kobold.choose_talent("racial", "trap_master")
    assert batt.can_plant_trap(k, (8, 5))
    assert not batt.can_plant_trap(k, (9, 5))
    assert (8, 5) in batt.trap_cells(k)


def test_an_unplayed_squad_plants_its_trap_toward_the_foe():
    kobold = _racial("Kobold", "kobold_trapper", "trap_master")
    kobold.give_to_pack("Bear Trap")
    batt, k, _foe = _duel(kobold, Unit("enemy"), bpos=(12, 5))
    batt.trap_setup_queue = [k]
    cell = ai.trap_cell(batt, k)
    assert cell[0] == 8 and abs(cell[1] - 5) <= 1


def test_trap_salvage_takes_the_unsprung_traps_home():
    kobold = _racial("Kobold", "kobold_trapper", "trap_salvage")
    batt, _k, _ = _duel(kobold, Unit("enemy"))
    batt.ground.append(GroundObject.trap((2, 2), "bear trap", "player"))
    batt.ground.append(GroundObject.trap((3, 3), "web", "player"))
    batt.ground.append(GroundObject.trap((4, 4), "alarm trap", "enemy"))
    campaign._salvage_traps(batt, [kobold])
    assert kobold.has_item("Bear Trap")
    assert not kobold.has_item("Alarm Trap")


def test_without_salvage_the_traps_stay_on_the_field():
    kobold = _racial("Kobold", "kobold_trapper")
    batt, _k, _ = _duel(kobold, Unit("enemy"))
    batt.ground.append(GroundObject.trap((2, 2), "bear trap", "player"))
    campaign._salvage_traps(batt, [kobold])
    assert not kobold.has_item("Bear Trap")


# --------------------------------------------------------------------------- #
# the world                                                                    #
# --------------------------------------------------------------------------- #

def test_deep_miner_cuts_the_mine_ambush_odds():
    from gartok import orders
    dwarf = _racial("Dwarf", "deep_miner")
    g = Guild([dwarf], name="Delvers")
    group = g.groups[0]
    group.node = "mine"
    seen = []

    def spy(node_id, hours, mult=1.0, rng=None):
        seen.append(mult)
        return False

    with patch("gartok.gather.ambushed", side_effect=spy):
        g.gather_shift(group, orders.Order("work", hours=8, gather=True))
        group.node = "lumber_yard"
        g.gather_shift(group, orders.Order("work", hours=8, gather=True))
    assert seen[0] == pytest.approx(seen[1] * 0.75)


def test_quartermaster_holds_the_group_he_leads():
    hob = _racial("Hobgoblin", "quartermaster")
    g = Guild([hob, Unit("player")], name="Line")
    group = g.groups[0]
    group.set_leader(hob)
    assert cohesion.quartermaster(group) == 2
    group.set_leader(group.members[1])
    assert cohesion.quartermaster(group) == 0


def test_parley_adds_to_the_three_talking_verbs():
    human = _racial("Human", "parley")
    talk = dialogue.Ambush([Unit("enemy")])
    plain = human.mod_charisma
    assert talk.mod("persuade", human) == plain + 1
    assert talk.mod("bluff", human) == plain + 1
    assert talk.mod("intimidate", human) == plain + 1
    assert talk.mod("teach", human) == human.mod_intelligence


def test_small_appetite_eats_every_other_day():
    goblin = _racial("Goblin", "small_appetite")
    goblin._base_inventory = []
    goblin.give_to_pack("Potato", 5)
    for _ in range(4):
        assert goblin.consume_daily_food() == "ate"
    assert goblin.rations == 3
    assert goblin.unfed_days == 0


def test_small_appetite_does_not_save_a_starving_goblin():
    goblin = _racial("Goblin", "small_appetite")
    goblin._base_inventory = []
    goblin.full_belly = True
    goblin.unfed_days = 2
    assert goblin.consume_daily_food() == "hungry"


def test_full_belly_survives_a_save():
    goblin = _racial("Goblin", "small_appetite")
    goblin.full_belly = True
    back = Unit.from_save(persist.unit_to_dict(goblin))
    assert back.full_belly


def test_bountiful_harvest_bears_two_bloom_fruit_that_heal():
    tree = _racial("Treefolk", "fruitful", "bountiful_harvest")
    assert tree.dawn_bloom() == (BLOOM_FRUIT, 2)
    assert _racial("Treefolk", "fruitful").dawn_bloom() == ("Fruit", 1)
    random.seed(0)
    human = Unit("player", race=data.race_by_name("Human"))
    human._base_inventory = []
    human.give_to_pack(BLOOM_FRUIT)
    human.hp = 1
    human.unfed_days = 1
    assert human.eat_now()
    assert 2 <= human.hp <= 5


def test_the_dawn_bloom_lands_in_the_pack():
    tree = _racial("Treefolk", "fruitful", "bountiful_harvest")
    g = Guild([tree], name="Grove")
    events, _ = g._daily_upkeep()
    assert any("2 fresh Bloom Fruit" in e for e in events)


# --------------------------------------------------------------------------- #
# Lift Rider                                                                   #
# --------------------------------------------------------------------------- #

def _centaur_and_friend(downed=False):
    centaur = _racial("Centaur", "lift_rider")
    random.seed(3)
    friend = Unit("player", race=data.race_by_name("Human"))
    batt = Battle([centaur, friend], [Unit("enemy")])
    c, f = batt.player_units
    batt.board.walls = set()
    c.pos, f.pos = (5, 5), (5, 7)
    batt.enemy_units[0].pos = (14, 1)
    if downed:
        f.hp = 0
        f.status = "dying"
    batt.clear_pf_cache()
    return batt, c, f


def test_lift_rider_carries_a_fallen_ally():
    batt, c, f = _centaur_and_friend(downed=True)
    assert actions.LIFT_RIDER.can(batt, c, f)
    actions.LIFT_RIDER.execute(batt, c, f)
    assert f.mounted_on is c and c.rider is f and f.pos == c.pos
    dest = next(p for p in batt.reachable(c) if p[0] < 3)
    actions.MOVE.execute(batt, c, dest)
    assert f.pos == c.pos == dest


def test_lift_rider_lifts_a_standing_ally_who_can_climb_down():
    batt, c, f = _centaur_and_friend()
    actions.LIFT_RIDER.execute(batt, c, f)
    assert f.mounted_on is c
    f.ap = 2
    spot = actions.DISMOUNT.highlight_cells(batt, f)[0]
    actions.DISMOUNT.execute(batt, f, spot)
    assert f.mounted_on is None and c.rider is None


def test_lift_rider_limits():
    batt, c, f = _centaur_and_friend()
    f.pos = (9, 9)
    assert not actions.LIFT_RIDER.can(batt, c, f)          # not beside
    f.pos = (5, 7)
    f.char.size = "Large"
    assert not actions.LIFT_RIDER.can(batt, c, f)          # too big
    f.char.size = "Medium"
    foe = batt.enemy_units[0]
    foe.pos = (6, 6)
    assert not actions.LIFT_RIDER.can(batt, c, foe)        # not a foe
    plain = Battle([Unit("player", race=data.race_by_name("Centaur"))], [Unit("enemy")])
    assert not actions.LIFT_RIDER.applicable(plain, plain.player_units[0])[0]


def test_ai_centaur_lifts_a_dying_ally():
    batt, c, f = _centaur_and_friend(downed=True)
    c.ai_ally = True
    with patch_action_d20(return_value=10):
        ai.take_turn(batt, c)
    assert f.mounted_on is c


def test_ai_centaur_leaves_a_standing_ally_alone():
    batt, c, f = _centaur_and_friend()
    with patch_action_d20(return_value=10):
        ai.take_turn(batt, c)
    assert f.mounted_on is None


# --------------------------------------------------------------------------- #
# Tail Sweep                                                                   #
# --------------------------------------------------------------------------- #

def _sweep_board(second=True):
    liz = _racial("Lizardfolk", "tail_sweep")
    liz.strength = 18
    liz._derive_combat()
    foes = [Unit("enemy"), Unit("enemy")] if second else [Unit("enemy")]
    batt = Battle([liz], foes)
    l = batt.player_units[0]
    batt.board.walls = set()
    batt.ambient_light = True
    l.pos = (5, 5)
    batt.enemy_units[0].pos = (6, 5)
    if second:
        batt.enemy_units[1].pos = (4, 5)
    for f in batt.enemy_units:
        f.hp = f.hp_max = 100
        f.char.constitution = 10
        f.char._derive_combat()
        f.hp = 100
    batt.clear_pf_cache()
    return batt, l


def test_tail_sweep_strikes_and_shoves_two_foes():
    batt, l = _sweep_board()
    a, b = batt.enemy_units
    with patch_action_d20(return_value=19):
        actions.TAIL_SWEEP.execute(batt, l, a)
    assert l.ap == 0
    assert a.hp < 100 and b.hp < 100
    assert a.pos == (7, 5) and b.pos == (3, 5)


def test_tail_sweep_with_one_foe_sweeps_that_one():
    batt, l = _sweep_board(second=False)
    a = batt.enemy_units[0]
    with patch_action_d20(return_value=19):
        actions.TAIL_SWEEP.execute(batt, l, a)
    assert a.hp < 100 and a.pos == (7, 5)


def test_tail_sweep_needs_the_talent_and_two_points():
    batt, l = _sweep_board()
    l.ap = 1
    assert not actions.TAIL_SWEEP.can(batt, l, batt.enemy_units[0])
    random.seed(0)
    plain = Unit("player", race=data.race_by_name("Lizardfolk"))
    b2 = Battle([plain], [Unit("enemy")])
    assert not actions.TAIL_SWEEP.applicable(b2, b2.player_units[0])[0]


def test_ai_sweeps_two_foes_at_its_sides():
    batt, l = _sweep_board()
    assert ai._pick_attack(batt, l, batt.enemy_units[0]) is actions.TAIL_SWEEP


# --------------------------------------------------------------------------- #
# Pixie Dust                                                                   #
# --------------------------------------------------------------------------- #

def _moat():
    """A sprite and a friend on one bank of a deep moat, a foe on the other."""
    sprite = _racial("Sprite", "pixie_dust")
    random.seed(5)
    friend = Unit("player", race=data.race_by_name("Human"))
    batt = Battle([sprite, friend], [Unit("enemy")])
    s, f = batt.player_units
    foe = batt.enemy_units[0]
    batt.board.walls = set()
    batt.ambient_light = True
    moat = {(8, y) for y in range(batt.board.rows)}
    batt.board.elevation = dict.fromkeys(moat, -2)
    batt.board.water = set(moat)
    batt.board.refresh_terrain()
    s.pos, f.pos, foe.pos = (5, 5), (6, 5), (11, 5)
    batt.clear_pf_cache()
    return batt, s, f, foe


def test_pixie_dust_lets_an_ally_fly_over_deep_water():
    batt, s, f, _foe = _moat()
    assert (9, 5) not in batt.reachable(f)
    actions.PIXIE_DUST.execute(batt, s, f)
    batt.clear_pf_cache()
    assert f.flies
    assert (9, 5) in batt.reachable(f)


def test_pixie_dust_wears_off_after_the_allys_turn():
    batt, s, f, _foe = _moat()
    actions.PIXIE_DUST.execute(batt, s, f)
    f.end_turn(batt.log)
    assert f.flies                            # its turn has not come yet
    f.start_turn(batt.log)
    f.end_turn(batt.log)
    assert not f.flies


def test_pixie_dust_limits():
    batt, s, f, foe = _moat()
    f.pos = (5, 9)
    assert not actions.PIXIE_DUST.can(batt, s, f)
    f.pos = (6, 5)
    assert not actions.PIXIE_DUST.can(batt, s, s)
    assert not actions.PIXIE_DUST.can(batt, s, foe)


def test_ai_sprite_dusts_the_ally_the_moat_cuts_off():
    batt, s, f, _foe = _moat()
    s.ai_ally = True
    with patch_action_d20(return_value=10):
        ai.take_turn(batt, s)
    assert f.has_condition("pixie_flight")


def test_ai_sprite_keeps_its_dust_when_the_way_is_open():
    batt, s, f, _foe = _moat()
    batt.board.elevation, batt.board.water = {}, set()
    batt.board.refresh_terrain()
    batt.clear_pf_cache()
    with patch_action_d20(return_value=10):
        ai.take_turn(batt, s)
    assert not f.has_condition("pixie_flight")
