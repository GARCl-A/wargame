"""Beasts: the first non-humanoid `kind` -- no occupation gear, a real (scaling)
Pack Tactics, the Wilds' encounter table, and the Hide they drop instead of
carrying loot."""

import random

from tests.helpers import (
    Battle,
    Unit,
    _recruit,
    abilities,
    actions,
    data,
    resolve_bonus,
)


def _wolf():
    return Unit("enemy", race=data.race_by_name("Wolf"))


def test_a_beast_has_no_occupation_and_fights_unarmed():
    random.seed(1)
    u = _wolf()
    assert u.race["kind"] == "beast"
    assert u.race["name"] == "Wolf"
    assert u.equipped_weapon is None
    assert u._base_inventory == []
    assert u.ability.id == "wolf_pack_tactics"


def test_build_enemy_with_a_race_pool_only_draws_beasts():
    from gartok import encounters
    rng = random.Random(4)
    for _ in range(20):
        u = encounters.build_enemy(2, rng, race_pool=data.BEAST_POOL)
        assert u.race["kind"] == "beast"


def test_wilds_encounter_table_can_roll_an_all_beast_pack_within_the_usual_envelope():
    from gartok import encounters
    rng = random.Random(1)
    saw_a_beast_pack = False
    for _ in range(50):
        pack = encounters.roll_encounter(encounters.WILDS_TABLE, rng=rng)
        assert 1 <= len(pack) <= 6
        assert all(0 <= u.mean_level <= 4 for u in pack)
        if pack and all(u.race["kind"] == "beast" for u in pack):
            saw_a_beast_pack = True
    assert saw_a_beast_pack


def test_the_humanoid_encounter_entry_keeps_the_racial_rarity_weights():
    """`EncounterEntry(30, None)` must fall through to `data.roll_race()`'s own
    thresholds, not draw uniformly across all 18 races -- Human is common
    (~25% of the d100), Sprite is rare (~1%); a uniform pick would flatten
    both to ~5.5% and this ratio would disappear."""
    from gartok import encounters
    rng = random.Random(7)
    names = [encounters.build_enemy(0, rng, race_pool=None).race["name"]
             for _ in range(400)]
    assert names.count("Human") > 5 * names.count("Sprite")


def _flank_battle():
    random.seed(3)
    batt = Battle([Unit("player")], [Unit("enemy"), Unit("enemy")])
    target, w1, w2 = batt.units
    for u in (w1, w2):
        u._ability = abilities.get("wolf_pack_tactics")
    target.pos, w1.pos, w2.pos = (5, 5), (4, 5), (5, 4)
    return batt, target, w1, w2


def test_wolf_pack_tactics_scales_with_the_number_of_wolves_on_the_target():
    batt, target, w1, w2 = _flank_battle()

    solo = w1.attack_mods(target, actions._pack_flank(batt, w1, target))
    total_solo, _ = resolve_bonus(solo)
    assert total_solo == 2 + max(0, w1.mod_strength)          # one ally on the target

    third = _recruit(batt, "enemy")
    third._ability = abilities.get("wolf_pack_tactics")
    third.pos = (6, 5)
    pack = w1.attack_mods(target, actions._pack_flank(batt, w1, target))
    total_pack, _ = resolve_bonus(pack)
    assert total_pack == 4 + max(0, w1.mod_strength)          # two allies now: +2 each


def test_a_defeated_beast_drops_its_own_species_material_but_never_carries_gear():
    from gartok import loot

    class AlwaysDrop:
        def random(self):
            return 0.0

    random.seed(2)
    wolf_drop = data.BEAST_POOL[0]["drop_item"]
    batt = Battle([Unit("player")], [_wolf(), _wolf()])
    pool = loot.field_loot(batt, [], rng=AlwaysDrop())
    assert pool.count(wolf_drop) == 2                           # one per beast, its own drop
    assert not any(item in data.WEAPONS or item in data.ARMOR for item in pool)


def test_a_defeated_beast_never_drops_below_its_own_chance():
    from gartok import loot

    class NeverDrop:
        def random(self):
            return 1.0

    random.seed(2)
    batt = Battle([Unit("player")], [_wolf(), _wolf()])
    pool = loot.field_loot(batt, [], rng=NeverDrop())
    assert data.BEAST_POOL[0]["drop_item"] not in pool


def test_a_beast_is_a_named_race_the_creator_can_pick():
    assert "Wolf" in data.BEAST_NAMES
    assert "Wolf" in data.ALL_RACE_NAMES
    assert "Wolf" not in data.RACE_NAMES                       # still never rolled as a player race
    assert data.race_by_name("Wolf")["kind"] == "beast"


def test_a_wolf_survives_a_save_round_trip():
    from gartok import persist
    random.seed(5)
    w = _wolf()
    back = Unit.from_save(persist.unit_to_dict(w))
    assert back.race["name"] == "Wolf"
    assert back.occupation["name"] == data.BEAST_OCCUPATION["name"]
    assert back.equipped_weapon is None
    assert back.ability.id == "wolf_pack_tactics"
    assert back.hp_max == w.hp_max


def test_creator_can_turn_a_unit_into_a_wolf_and_back():
    random.seed(6)
    u = Unit("player", race=data.race_by_name("Human"))
    u.set_race("Wolf")
    assert u.race["kind"] == "beast" and u.token == "w"
    assert u.equipped_weapon is None and u.equipped_armor is None
    u.set_occupation("Farmer")                                 # a beast keeps no job
    assert u.occupation["name"] == data.BEAST_OCCUPATION["name"]
    u.set_race("Human")
    assert u.race["kind"] == "humanoid"
    assert u.occupation["name"] != data.BEAST_OCCUPATION["name"]


def test_a_race_walks_at_its_own_speed_else_its_sizes():
    assert data.race_by_name("Wolf")["speed"] == 10.5
    assert _wolf().speed == data.squares(10.5) == 7
    human = Unit("player", race=data.race_by_name("Human"))
    assert human.race["speed"] == data.SIZES["Medium"]["speed"]
    assert human.speed == data.squares(9.0)


def _grown_wolf():
    random.seed(8)
    w = _wolf()
    w.set_track_level("racial", 6)
    return w


def test_rending_bite_adds_a_die_to_the_unarmed_attack():
    w = _grown_wolf()
    assert w.unarmed_damage == (1, 3)
    assert w.choose_talent("racial", "rending_bite")
    assert w.unarmed_damage == (2, 3)


def test_dire_growth_makes_a_wolf_large_and_stacks_with_the_bite():
    w = _grown_wolf()
    assert (w.size, w.footprint) == ("Medium", 1)
    assert w.choose_talent("racial", "dire_growth")
    assert (w.size, w.footprint) == ("Large", 2)
    assert w.unarmed_damage == (1, 4)                      # the Large unarmed die
    w.set_track_level("racial", 7)
    w.choose_talent("racial", "rending_bite")
    assert w.unarmed_damage == (2, 4)
    assert w.speed == data.squares(10.5)                  # Large does not slow it


def test_wolf_talents_are_wolf_only_and_survive_a_save():
    from gartok import persist, talents
    assert {t.id for t in talents.racial_tree("Wolf")} >= {"rending_bite", "dire_growth"}
    assert not {"rending_bite", "dire_growth"} & {t.id for t in talents.racial_tree("Human")}
    w = _grown_wolf()
    w.choose_talent("racial", "dire_growth")
    back = Unit.from_save(persist.unit_to_dict(w))
    assert back.size == "Large" and back.footprint == 2


def test_a_grown_wolf_takes_a_2x2_footprint_in_battle():
    w = _grown_wolf()
    w.choose_talent("racial", "dire_growth")
    batt = Battle([Unit("player")], [w])
    assert batt.enemy_units[0].footprint == 2


def test_the_creator_can_pin_racial_level_up_to_ten():
    w = _wolf()
    w.set_track_level("racial", 10)
    assert w.racial_level == 10
    assert w.picks_available("racial") == 6
    w.set_track_level("racial", 99)
    assert w.racial_level == 10


def test_natural_armor_is_flat_ac_that_ignores_armor_rules():
    from gartok import constants
    random.seed(9)
    u = Unit("player", race=data.race_by_name("Human"))
    u.give_to_armor(next(iter(data.ARMOR)))
    base_ac, base_speed = u.ac, u.speed
    u.set_natural_armor(3)
    assert u.ac == base_ac + 3
    assert u.speed == base_speed                              # no drag
    assert dict(u.ac_breakdown())["natural armor"] == 3
    u.set_natural_armor(99)
    assert u.natural_armor == constants.NATURAL_ARMOR_MAX == 5
    u.set_natural_armor(-4)
    assert u.natural_armor == 0


def test_natural_armor_counts_in_battle_and_survives_a_save():
    from gartok import persist
    random.seed(10)
    w = _wolf()
    plain = Battle([Unit("player")], [w]).enemy_units[0].ac
    w.set_natural_armor(4)
    assert Battle([Unit("player")], [w]).enemy_units[0].ac == plain + 4
    back = Unit.from_save(persist.unit_to_dict(w))
    assert back.natural_armor == 4 and back.ac == w.ac


def test_the_creator_can_pin_combat_and_work_up_to_ten_without_moving_enemy_caps():
    from gartok import encounters
    u = _wolf()
    u.set_track_level("combat", 10)
    u.set_track_level("work", 10)
    assert (u.combat_level, u.work_level) == (10, 10)
    u.set_track_level("combat", 99)
    assert u.combat_level == 10
    assert u.racial_level == 10                       # (10 + 10) lands on the top racial level
    assert (encounters._COMBAT_CAP, encounters._WORK_CAP) == (7, 6)
    for lvl in range(0, 7):
        rng = random.Random(lvl)
        built = encounters.build_enemy(lvl, rng)
        assert built.combat_level <= 7 and built.work_level <= 6


def test_turning_a_unit_into_a_beast_keeps_its_pack_and_stows_held_gear():
    random.seed(11)
    u = Unit("player", race=data.race_by_name("Human"))
    u.give_to_pack("Torch")
    u.give_to_hand(next(iter(data.WEAPONS)))
    held = u.equipped_weapon
    before = sum(q for _, q in u._base_inventory)
    u.set_race("Wolf")
    assert u.equipped_weapon is None and u.equipped_armor is None
    names = [n for n, _ in u._base_inventory]
    assert "Torch" in names and held in names
    assert sum(q for _, q in u._base_inventory) >= before


def test_skeleton_and_giant_spider_are_creator_races_but_never_wild_encounters():
    from gartok import encounters
    for name, kind in (("Skeleton", "undead"), ("Giant Spider", "beast")):
        assert name in data.ALL_RACE_NAMES and name not in data.RACE_NAMES
        assert data.race_by_name(name)["kind"] == kind
    assert {r["name"] for r in data.WILD_POOL} == {"Wolf"}
    rng = random.Random(3)
    seen = {u.race["name"] for _ in range(60)
            for u in encounters.roll_encounter(encounters.WILDS_TABLE, rng=rng)
            if u.race["kind"] == "beast"}
    assert seen == {"Wolf"}


def _skeleton():
    return Unit("enemy", race=data.race_by_name("Skeleton"))


def _spider(*picks):
    random.seed(13)
    sp = Unit("enemy", race=data.race_by_name("Giant Spider"))
    sp.set_track_level("racial", 10)
    for p in picks:
        assert sp.choose_talent("racial", p)
    return sp


def test_a_race_can_carry_a_list_of_abilities_merged_into_one():
    from gartok import abilities
    both = abilities.get(("darkvision", "sleep_immunity"))
    assert both.darkvision == data.DARKVISION and both.sleep_immunity
    assert both.id == "darkvision+sleep_immunity"
    solo = abilities.get("wolf_pack_tactics")
    merged = abilities.get(("wolf_pack_tactics", "climber"))
    assert merged.melee_damage == solo.melee_damage and merged.auto_climb_dc == 25
    assert merged.attack_mods is solo.attack_mods or merged.attack_mods(None, None, 2) == solo.attack_mods(None, None, 2)


def test_skeleton_has_its_sheet_and_both_abilities():
    s = _skeleton()
    assert data.race_by_name("Skeleton")["mods"] == (0, 2, 4, -4, -2, -4)
    assert (s.size, s.footprint, s.race["hd"], data.squares(s.race["speed"])) == ("Medium", 1, 8, 6)
    assert s.ability.darkvision and s.ability.sleep_immunity and s.dr == 0


def test_elder_skeleton_adds_four_int_and_four_cha():
    s = _skeleton()
    s.set_track_level("racial", 6)
    int0, cha0 = s.intelligence, s.charisma
    assert s.choose_talent("racial", "elder_skeleton")
    assert (s.intelligence, s.charisma) == (int0 + 4, cha0 + 4)


def test_skeleton_faith_initiate_opens_faith_magic():
    s = _skeleton()
    s.set_track_level("racial", 6)
    assert s.magic_source is None
    assert s.choose_talent("racial", "skeleton_faith_initiate")
    assert s.magic_source == "faith"


def test_deft_bones_lets_unarmed_attacks_hit_with_dexterity():
    s = _skeleton()
    s.take_from_hand()
    s.set_track_level("racial", 6)
    s.set_base_attribute("strength", 3)
    s.set_base_attribute("dexterity", 18)
    before = s.attack_bonus[0]
    s.choose_talent("racial", "deft_bones")
    after, src = s.attack_bonus
    assert after > before and src == "STR/DEX" and after == s.mod_dexterity
    batt = Battle([Unit("player")], [s])
    mods = batt.enemy_units[0].attack_mods(batt.player_units[0])
    assert (s.mod_dexterity, None, "STR/DEX") in mods


def test_giant_spider_is_medium_and_grows_twice_to_a_3x3_body():
    from gartok import persist
    sp = _spider()
    assert data.race_by_name("Giant Spider")["mods"] == (1, 2, 1, -4, 1, -4)
    assert (sp.size, sp.footprint) == ("Medium", 1) and sp.ability.auto_climb_dc == 25
    assert not sp.choose_talent("racial", "titanic_growth")          # needs the first growth
    sp.choose_talent("racial", "giant_growth")
    assert (sp.size, sp.footprint, sp.unarmed_damage) == ("Large", 2, (1, 4))
    sp.choose_talent("racial", "titanic_growth")
    assert (sp.size, sp.footprint, sp.unarmed_damage) == ("Huge", 3, (1, 6))
    back = Unit.from_save(persist.unit_to_dict(sp))
    assert back.size == "Huge" and back.footprint == 3
    batt = Battle([Unit("player")], [sp])
    assert len(batt.cells_of(batt.enemy_units[0])) == 9


def _web_battle(*picks):
    sp = _spider("spin_web", *picks)
    victim = Unit("player")
    batt = Battle([victim], [sp])
    web_user, prey = batt.enemy_units[0], batt.player_units[0]
    web_user.pos, prey.pos = (5, 5), (12, 5)
    web_user.ap = 2
    batt.board.walls.clear()
    batt.ground[:] = [o for o in batt.ground if not o.is_torch]
    return batt, web_user, prey


def test_spin_web_needs_the_talent_and_a_clear_spot_beside_the_spider():
    sp = _spider()
    batt = Battle([Unit("player")], [sp])
    web_user = batt.enemy_units[0]
    web_user.pos = (5, 5)
    assert not actions.SPIN_WEB.applicable(batt, web_user)[0]
    batt, web_user, _ = _web_battle()
    assert actions.SPIN_WEB.available(batt, web_user)
    assert actions.SPIN_WEB.can(batt, web_user, (6, 5))
    assert not actions.SPIN_WEB.can(batt, web_user, (5, 5))           # on the spider itself
    assert not actions.SPIN_WEB.can(batt, web_user, (9, 5))           # not beside it
    batt.board.walls.add((6, 6))
    assert not actions.SPIN_WEB.can(batt, web_user, (6, 6))           # a wall


def test_a_web_is_as_wide_as_the_spider():
    for picks, side in (((), 1), (("giant_growth",), 2), (("giant_growth", "titanic_growth"), 3)):
        batt, web_user, _ = _web_battle(*picks)
        anchor = (5 + side, 5)
        assert actions.SPIN_WEB.can(batt, web_user, anchor)
        actions.SPIN_WEB.execute(batt, web_user, anchor)
        webs = [o for o in batt.ground if o.trap_type == "web"]
        assert len(webs) == side * side and web_user.ap == 1
        assert len({o.trap_group for o in webs}) == 1


def test_a_foe_touching_any_cell_is_stuck_and_the_whole_web_goes():
    batt, web_user, prey = _web_battle("giant_growth")
    actions.SPIN_WEB.execute(batt, web_user, (7, 5))
    prey.pos = (9, 5)
    prey.ap = 2
    batt.move_unit(prey, (8, 5))
    assert prey.has_condition("entangled")
    assert not [o for o in batt.ground if o.trap_type == "web"]
    assert batt.reachable(prey) == {}
    prey.end_turn(batt.log)
    assert prey.has_condition("entangled")                  # caught mid-turn: still held next turn
    prey.start_turn(batt.log)
    assert batt.reachable(prey) == {}
    prey.end_turn(batt.log)
    assert not prey.has_condition("entangled")


def test_the_spiders_own_side_walks_through_its_web():
    batt, web_user, _ = _web_battle()
    ally = _recruit(batt, "enemy")
    ally.pos = (8, 5)
    actions.SPIN_WEB.execute(batt, web_user, (6, 5))
    ally.ap = 2
    ally.pos = (7, 5)
    batt.move_unit(ally, (6, 5))
    assert not ally.has_condition("entangled")
    assert len([o for o in batt.ground if o.trap_type == "web"]) == 1


def test_disarming_a_web_clears_it_without_a_trap_item(monkeypatch):
    batt, web_user, prey = _web_battle()
    actions.SPIN_WEB.execute(batt, web_user, (6, 5))
    prey.pos = (7, 5)
    prey.ap = 1
    from gartok.actions import support
    monkeypatch.setattr(support, "d20", lambda: 20)
    carried = list(prey.inventory)
    actions.DISARM.execute(batt, prey)
    assert not [o for o in batt.ground if o.trap_type == "web"]
    assert prey.inventory == carried


def test_the_ai_spider_strings_a_web_when_the_prey_is_still_far():
    from gartok import ai
    batt, web_user, prey = _web_battle()
    ai.take_turn(batt, web_user)
    assert any(o.trap_type == "web" for o in batt.ground)


def test_a_skeleton_has_a_job_but_a_spider_does_not():
    random.seed(21)
    sk = _skeleton()
    assert sk.occupation["name"] != data.BEAST_OCCUPATION["name"]
    assert sk.occupation["name"] in data.OCCUPATION_NAMES
    assert sk.equipped_weapon == sk.occupation["weapon"]
    sp = Unit("enemy", race=data.race_by_name("Giant Spider"))
    assert sp.occupation["name"] == data.BEAST_OCCUPATION["name"] and sp.equipped_weapon is None
    sk.set_occupation("Guard")
    assert sk.occupation["name"] == "Guard"


def test_a_skeleton_keeps_its_job_through_a_save_and_a_race_swap():
    from gartok import persist
    random.seed(22)
    sk = _skeleton()
    sk.set_occupation("Guard")
    back = Unit.from_save(persist.unit_to_dict(sk))
    assert back.race["name"] == "Skeleton" and back.occupation["name"] == "Guard"
    wolf = Unit("player", race=data.race_by_name("Human"))
    wolf.set_race("Giant Spider")
    wolf.set_race("Skeleton")
    assert wolf.occupation["name"] in data.OCCUPATION_NAMES
