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


def _wolf(rng=random):
    return Unit("enemy", race=rng.choice(data.BEAST_POOL))


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
