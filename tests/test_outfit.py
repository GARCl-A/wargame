import random

from gartok import ai, data, economy, encounters, items, loot, outfit
from gartok.battle import Battle
from gartok.unit import Unit


def _race(name):
    return next(r for r in data.RACE_POOL if r["name"] == name)


def _body(seed=0, race="Human", weapon="Club", strength=14, dexterity=10):
    random.seed(seed)
    u = Unit("enemy", race=_race(race))
    u.strength, u.dexterity = strength, dexterity
    u.equipped_weapon = weapon
    u.equipped_armor = u.equipped_offhand = None
    u.inventory = []
    u._derive_combat()
    return u


class _Dice:
    """`random()` always `roll`; `choice` the first option."""

    def __init__(self, roll):
        self.roll = roll

    def random(self):
        return self.roll

    def choice(self, options):
        return options[0]


SHOOTS, STABS = _Dice(0.0), _Dice(0.99)


class _Seq:
    """`random()` always `roll` (keeps the archetype fixed); `choice` a seeded draw."""

    def __init__(self, roll, seed):
        self.roll, self.rng = roll, random.Random(seed)

    def random(self):
        return self.roll

    def choice(self, options):
        return self.rng.choice(options)


def _kit_price(u):
    worn = [n for n in (u.equipped_weapon, u.equipped_armor) if n]
    return (sum(economy.buy_price(n) for n in worn)
            + u.count_of(outfit.POTION) * economy.buy_price(outfit.POTION))


def test_the_budget_climbs_with_the_level_and_holds_past_the_table():
    levels = sorted(outfit.KIT_BUDGET)
    assert levels == list(range(len(levels)))
    costs = [outfit.KIT_BUDGET[n] for n in levels]
    assert costs == sorted(costs)
    assert outfit.budget(levels[-1] + 5) == costs[-1]
    assert outfit.budget(-1) == costs[0]


def test_level_zero_keeps_the_occupation_kit():
    u = _body()
    outfit.outfit(u, 0)
    assert u.equipped_weapon == "Club" and u.equipped_armor is None
    assert u.count_of(outfit.POTION) == 0


def test_a_level_six_body_wears_armour_wields_better_and_carries_potions():
    u = _body()
    spent = outfit.outfit(u, 6, random.Random(1))
    assert items.is_armor(u.equipped_armor)
    assert economy.buy_price(u.equipped_weapon) > economy.buy_price("Club")
    assert 0 < u.count_of(outfit.POTION) <= outfit.POTION_CAP
    assert not u.encumbered
    assert spent == _kit_price(u) <= outfit.budget(6)


def test_each_part_stays_inside_its_share_of_the_budget():
    for level in range(1, 9):
        u = _body(seed=level)
        outfit.outfit(u, level, random.Random(level))
        cost = outfit.budget(level)
        if u.equipped_armor:
            assert economy.buy_price(u.equipped_armor) <= cost * outfit.ARMOR_SHARE
        assert economy.buy_price(u.equipped_weapon) <= max(cost * outfit.WEAPON_SHARE,
                                                           economy.buy_price("Club"))


def test_armour_too_heavy_for_the_body_is_left_on_the_shelf():
    u = _body(strength=6, dexterity=8)
    assert not u.encumbered
    outfit.outfit(u, 8, random.Random(0))
    assert u.equipped_armor != "Plate Armor"
    assert not u.encumbered


def test_dexterity_already_filling_the_armour_cap_stops_at_studded_leather():
    nimble = _body(dexterity=16)
    assert nimble.mod_dexterity == 3
    outfit.outfit(nimble, 8, STABS)
    assert nimble.equipped_armor == "Studded Leather"


def test_a_clumsy_body_buys_the_heaviest_armour_it_carries():
    clumsy = _body(strength=18, dexterity=8)
    outfit.outfit(clumsy, 8, STABS)
    assert clumsy.equipped_armor == "Plate Armor"


def test_the_archetype_comes_from_the_stats_not_the_occupation():
    assert outfit.archetype(_body(strength=16, dexterity=10), SHOOTS) == outfit.STRENGTH
    assert outfit.archetype(_body(strength=10, dexterity=16), SHOOTS) == outfit.RANGED
    assert outfit.archetype(_body(strength=10, dexterity=16), STABS) == outfit.FINESSE


def test_a_strong_body_fights_with_a_plain_blade_and_a_light_or_a_broadsword():
    for seed in range(10):
        u = _body(seed=seed, weapon="Dagger", strength=16)
        outfit.outfit(u, 4, random.Random(seed))
        w = items.get(u.equipped_weapon)
        assert not w.range and not w.finesse
        assert w.hands == 2 or u.equipped_offhand in (items.TORCH_ITEM, items.LANTERN_ITEM)


def test_a_nimble_melee_body_fights_with_a_finesse_blade_and_a_light():
    u = _body(weapon="Club", dexterity=16)
    outfit.outfit(u, 4, STABS)
    w = items.get(u.equipped_weapon)
    assert w.finesse and w.hands == 1 and not w.range
    assert u.equipped_offhand == items.TORCH_ITEM


def test_a_lantern_in_the_pack_goes_to_the_off_hand_instead_of_a_torch():
    u = _body(weapon="Club", dexterity=16)
    u.give_to_pack(items.LANTERN_ITEM)
    outfit.outfit(u, 4, STABS)
    assert u.equipped_offhand == items.LANTERN_ITEM
    assert u.count_of(items.LANTERN_ITEM) == 0


def test_an_archer_gets_a_bow_and_a_quiver_whatever_the_occupation():
    u = _body(weapon="Hammer", dexterity=16)
    outfit.outfit(u, 6, SHOOTS)
    assert items.get(u.equipped_weapon).range
    assert u.has_item(items.AMMO_ITEM)


def test_an_archer_who_cannot_pay_for_a_bow_fights_with_finesse_unless_it_holds_one():
    poor = _body(weapon="Club", dexterity=16)
    outfit.outfit(poor, 2, SHOOTS)
    assert items.get(poor.equipped_weapon).finesse
    crossbowman = _body(weapon="Light Crossbow", dexterity=16)
    crossbowman.give_to_pack(items.AMMO_ITEM)
    outfit.outfit(crossbowman, 2, SHOOTS)
    assert crossbowman.equipped_weapon == "Light Crossbow"


def test_the_old_weapon_is_not_left_in_the_pack():
    u = _body()
    outfit.outfit(u, 4, random.Random(0))
    assert u.equipped_weapon != "Club"
    assert u.count_of("Club") == 0


def test_a_large_body_may_buy_a_large_weapon():
    seen = set()
    for seed in range(30):
        u = _body(seed=seed, race="Centaur", strength=18)
        outfit.outfit(u, 8, random.Random(seed))
        seen.add(items.get(u.equipped_weapon).size)
    assert "Large" in seen


def test_the_band_does_not_all_carry_the_same_weapon():
    rng = random.Random(0)
    weapons = set()
    for seed in range(20):
        u = _body(seed=seed)
        outfit.outfit(u, 2, rng)
        weapons.add(u.equipped_weapon)
    assert len(weapons) > 1


def test_beasts_are_never_outfitted():
    random.seed(0)
    wolf = encounters.build_enemy(6, race_pool=data.WILD_POOL)
    assert wolf.equipped_armor is None and wolf.count_of(outfit.POTION) == 0


def test_build_enemy_outfits_a_humanoid_by_its_racial_level():
    random.seed(4)
    u = encounters.build_enemy(5)
    assert u.racial_level == 5
    assert u.equipped_armor is not None or u.encumbered
    assert u.count_of(outfit.POTION) > 0 or u.encumbered


def test_the_ai_drinks_the_potion_it_was_outfitted_with():
    foe = _body()
    outfit.outfit(foe, 6, random.Random(0))
    before = foe.count_of(outfit.POTION)
    random.seed(0)
    batt = Battle([Unit("player")], [foe])
    me = batt.enemy_units[0]
    me.hp, me.ap = 1, 2
    assert ai._try_drink_potion(batt, me)
    assert me.hp > 1
    assert sum(1 for name in me.inventory if str(name) == outfit.POTION) == before - 1


def test_a_beaten_outfitted_foe_leaves_its_weapon_and_potions_but_not_its_armour():
    foe = _body()
    outfit.outfit(foe, 6, random.Random(0))
    random.seed(0)
    batt = Battle([Unit("player")], [foe])
    pool = loot.field_loot(batt, [])
    assert foe.equipped_weapon in pool
    assert pool.count(outfit.POTION) == foe.count_of(outfit.POTION)
    assert foe.equipped_armor not in pool


def test_a_strong_body_draws_two_hands_or_one_hand_and_a_light():
    heavy = _body(weapon="Dagger", strength=16)
    outfit.outfit(heavy, 4, SHOOTS)
    assert heavy.equipped_weapon == "Broadsword" and heavy.equipped_offhand is None
    light = _body(weapon="Dagger", strength=16)
    outfit.outfit(light, 4, STABS)
    w = items.get(light.equipped_weapon)
    assert w.hands == 1 and not w.finesse and not w.range
    assert light.equipped_offhand == items.TORCH_ITEM


def test_a_strong_body_that_cannot_pay_for_two_hands_fights_with_one():
    u = _body(weapon="Dagger", strength=16)
    outfit.outfit(u, 2, SHOOTS)
    assert items.get(u.equipped_weapon).hands == 1
    assert u.equipped_offhand == items.TORCH_ITEM


def test_finesse_weapons_are_drawn_evenly_not_by_price():
    seen = set()
    for seed in range(40):
        u = _body(seed=seed, weapon="Club", dexterity=16)
        outfit.outfit(u, 6, _Seq(0.99, seed))
        seen.add(u.equipped_weapon)
    assert {"Dagger", "Rapier"} <= seen


def _veteran(**kw):
    u = _body(**kw)
    u.set_track_level("combat", 2)
    u._derive_combat()
    return u


def _broadswords(n):
    return [_veteran(seed=seed, weapon="Broadsword", strength=16) for seed in range(n)]


def test_a_band_with_no_light_hands_a_torch_to_a_free_hand():
    band = _broadswords(2) + [_veteran(weapon="Axe", strength=16)]
    outfit.light_the_band(band)
    assert band[2].equipped_offhand == items.TORCH_ITEM
    assert [u.equipped_weapon for u in band[:2]] == ["Broadsword", "Broadsword"]


def test_a_band_of_two_handed_blades_has_one_switch_to_a_blade_and_a_torch():
    band = _broadswords(3)
    outfit.light_the_band(band)
    lit = [u for u in band if u.equipped_offhand == items.TORCH_ITEM]
    assert len(lit) == 1
    w = items.get(lit[0].equipped_weapon)
    assert w.hands == 1 and economy.buy_price(lit[0].equipped_weapon) <= economy.buy_price("Broadsword")


def test_a_band_that_already_holds_a_light_is_left_alone():
    band = _broadswords(2) + [_veteran(weapon="Axe", strength=16)]
    band[2].equipped_offhand = items.LANTERN_ITEM
    outfit.light_the_band(band)
    assert [u.equipped_offhand for u in band] == [None, None, items.LANTERN_ITEM]


def test_a_band_of_beasts_or_of_archers_gets_no_torch():
    random.seed(0)
    wolves = [encounters.build_enemy(3, race_pool=data.WILD_POOL) for _ in range(3)]
    outfit.light_the_band(wolves)
    assert all(w.equipped_offhand is None for w in wolves)
    archers = [_veteran(weapon="Shortbow", dexterity=16) for _ in range(2)]
    outfit.light_the_band(archers)
    assert all(a.equipped_offhand is None for a in archers)


def test_a_level_zero_band_keeps_its_hands_as_they_are():
    band = [_body(seed=seed, weapon="Broadsword", strength=16) for seed in range(2)]
    outfit.light_the_band(band)
    assert all(u.equipped_offhand is None and u.equipped_weapon == "Broadsword" for u in band)


def test_a_battle_lights_each_side_the_player_does_not_play():
    random.seed(0)
    batt = Battle([Unit("player")], _broadswords(2), others={"bandits": _broadswords(2)})
    for side in (batt.enemy_units, batt.other_units):
        assert sum(c.char.equipped_offhand == items.TORCH_ITEM for c in side) == 1


def test_weapons_of_one_price_are_tried_in_name_order_not_the_set_s():
    tied = [n for n in outfit._SOLD if economy.buy_price(n) == economy.buy_price("Axe")]
    assert len(tied) > 1 and tied == sorted(tied)
