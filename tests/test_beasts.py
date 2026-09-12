"""Beasts: the first non-humanoid `kind` -- no occupation gear, a real (scaling)
Pack Tactics, the Wilds' encounter table, and the Hide they drop instead of
carrying loot."""

import random

from tests.helpers import Battle, Unit, _recruit, abilities, actions, data, resolve_bonus


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
