"""Animals, tack and the group wagon: what an animal does depends on what it wears,
the wagon is pulled by the group's harnessed animals, everyone eats from what the
group carries, and what happens to it all when the group changes."""

import os

import pytest

from gartok import abilities, data, items, persist
from gartok.animals import HARNESS, PACK_SADDLE, STARVE_DAYS, Animal
from gartok.group import HERD_BASE, Group
from gartok.guild import Guild
from gartok.wagon import VEHICLES, Wagon
from tests.helpers import Unit, packed


def _unit(size="Huge"):
    """A Huge member weighs more than any cart can draw, so nobody boards unless a test says so."""
    u = Unit("player")
    u.size = size
    return u


def _animal(species="Donkey", tack=None, cargo=()):
    a = Animal(species, tack=tack)
    for name in cargo:
        a.stash.put(name)
    return a


def _group(*animals, wagon=None, cargo=(), members=1, food=()):
    units = [_unit() for _ in range(members)]
    for u in units:
        u._base_inventory = packed(list(food))
    w = Wagon(wagon if isinstance(wagon, str) else "Cart") if wagon else None
    g = Group(units, node="city", wagons=[w] if w else [], herd=list(animals))
    g.hitch_idle()
    if w is not None:
        for name in cargo:
            w.stash.put(name)
    return Guild(None, groups=[g]), g


# --------------------------------------------------------------------------- #
# tack decides the role                                                       #
# --------------------------------------------------------------------------- #

def test_an_animal_without_tack_does_nothing():
    a = _animal()
    assert a.role is None and a.capacity == 0 and a.pull == 0


def test_a_pack_saddle_lets_it_carry_and_a_harness_lets_it_pull():
    pack, draft = _animal(tack=PACK_SADDLE), _animal(tack=HARNESS)
    assert pack.role == "pack" and pack.capacity == pack.back_load == 30 and pack.pull == 0
    assert draft.role == "draft" and draft.pull == draft.draw == 90 and draft.capacity == 0


def test_only_a_saddle_or_harness_can_be_worn():
    assert Animal.can_wear(PACK_SADDLE) and Animal.can_wear(HARNESS)
    assert not Animal.can_wear("Rope")


def test_tack_is_a_tagged_item():
    assert items.item_tags(PACK_SADDLE) == ["TACK"] and items.item_tags(HARNESS) == ["TACK"]


def test_an_unsaddled_animal_cannot_be_loaded():
    a = _animal()
    assert not a.stash.fits(1)
    a.give_to_tack(PACK_SADDLE)
    assert a.stash.fits(30)


# --------------------------------------------------------------------------- #
# the wagon is pulled by harnessed animals                                    #
# --------------------------------------------------------------------------- #

def test_a_wagon_with_nothing_harnessed_holds_nothing():
    _, g = _group(_animal(), _animal(tack=PACK_SADDLE), wagon=True)
    assert g.wagons[0].capacity == 0 and g.wagons[0].speed is None


def test_a_cart_holds_what_its_animal_draws_up_to_the_box():
    for species, room in (("Donkey", 90), ("Horse", 120), ("Ox", 180)):
        _, g = _group(_animal(species, HARNESS), wagon=True)
        assert g.wagons[0].budget == room


def test_a_carriage_adds_up_what_its_animals_draw_up_to_the_box():
    _, g = _group(_animal("Donkey", HARNESS), _animal("Donkey", HARNESS), wagon="Carriage")
    assert g.wagons[0].budget == 180
    _, g = _group(*[_animal("Ox", HARNESS) for _ in range(3)], wagon="Carriage")
    assert g.wagons[0].budget == VEHICLES["Carriage"].capacity == 540


def test_the_hitch_has_as_many_slots_as_the_vehicle():
    _, g = _group(*[_animal("Ox", HARNESS) for _ in range(4)], wagon=True)
    assert len(g.wagons[0].draft) == VEHICLES["Cart"].slots == 1 and g.wagons[0].free_slots == 0
    _, g = _group(*[_animal("Ox", HARNESS) for _ in range(4)], wagon="Carriage")
    assert len(g.wagons[0].draft) == VEHICLES["Carriage"].slots == 3


def test_speed_is_the_slowest_animal_pulling():
    _, g = _group(_animal("Horse", HARNESS), wagon=True)
    assert g.wagons[0].speed == 12.0
    _, g = _group(_animal("Horse", HARNESS), _animal("Donkey", HARNESS), wagon="Carriage")
    assert g.wagons[0].speed == 6.0


def test_taking_the_harness_off_shrinks_the_cargo_room():
    _, g = _group(_animal(tack=HARNESS), _animal(tack=HARNESS), wagon="Carriage")
    before = g.wagons[0].capacity
    g.herd[0].take_tack()
    assert g.wagons[0].capacity < before


# --------------------------------------------------------------------------- #
# eating                                                                      #
# --------------------------------------------------------------------------- #

def test_members_eat_from_the_wagon_without_share_food():
    guild, g = _group(wagon=True, cargo=["Potato", "Potato"])
    g.members[0].share_food = False
    guild.pass_time(24)
    assert g.members[0].unfed_days == 0 and g.wagons[0].rations == 1


def test_members_eat_from_an_animals_load():
    guild, g = _group(_animal(tack=PACK_SADDLE, cargo=["Potato"] * 2))
    guild.pass_time(24)
    assert g.members[0].unfed_days == 0
    assert g.carried_rations <= 1


def test_each_animal_eats_one_ration_a_day_from_the_wagon_first():
    guild, g = _group(_animal(), _animal(), wagon=True, cargo=["Potato"] * 4)
    guild.pass_time(24)
    assert g.wagons[0].rations == 1                       # the member and both animals ate
    assert all(a.unfed_days == 0 for a in g.herd)


def test_an_animal_with_no_food_anywhere_goes_hungry_then_starves():
    _, g = _group(_animal())
    g.members[0]._base_inventory = []
    for day in range(1, STARVE_DAYS):
        assert any("went hungry" in e for e in g.feed_animals())
        assert g.herd[0].unfed_days == day
    assert any("starved" in e for e in g.feed_animals())
    assert g.herd == []


def test_a_meal_resets_an_animals_hunger():
    _, g = _group(_animal(), food=["Potato"])
    g.herd[0].unfed_days = 2
    g.feed_animals()
    assert g.herd[0].unfed_days == 0 and g.members[0].count_of("Potato") == 0


def test_eat_now_pass_feeds_a_hungry_animal_without_waiting_for_the_day():
    guild, g = _group(_animal(), food=["Potato"])
    g.herd[0].unfed_days = 1
    events = guild.eat_now_pass(g.members)
    assert g.herd[0].unfed_days == 0 and g.members[0].count_of("Potato") == 0
    assert any("Donkey" in e for e in events)


def test_eat_now_pass_leaves_a_fed_animal_and_a_foodless_one_alone():
    guild, g = _group(_animal(), _animal(), food=["Potato"])
    g.herd[0].unfed_days = 0
    g.herd[1].unfed_days = 0
    guild.eat_now_pass(g.members)
    assert g.members[0].count_of("Potato") == 1
    g.members[0]._base_inventory = []
    g.herd[1].unfed_days = 2
    assert guild.eat_now_pass(g.members) == [] and g.herd[1].unfed_days == 2


def test_food_carried_by_the_group_rots_like_any_other():
    guild, g = _group(_animal(tack=PACK_SADDLE, cargo=["Meat"]), wagon=True, cargo=["Meat"] * 3, food=["Potato"] * 5)
    guild.pass_time(24 * 3)
    stores = g.food_stores()
    assert all(it.name == "Rotten Food" for pack in stores for it in pack)


def test_the_guild_ration_count_includes_wagons_and_animals():
    guild, g = _group(_animal(tack=PACK_SADDLE, cargo=["Potato"] * 2), wagon=True, cargo=["Potato"] * 3)
    assert guild.rations == 5 and g.rations == 5


# --------------------------------------------------------------------------- #
# the group's fate                                                            #
# --------------------------------------------------------------------------- #

def test_a_wiped_group_takes_its_wagon_and_animals_with_it():
    guild, g = _group(_animal(), wagon=True)
    guild.groups.append(Group([_unit()], node="city"))
    guild.remove_members(list(g.members))
    assert g not in guild.groups


def test_a_group_that_loses_members_but_not_all_keeps_them():
    guild, g = _group(_animal(), wagon=True, members=2)
    guild.remove_members([g.members[0]])
    assert g in guild.groups and g.wagons and len(g.herd) == 1


def test_merging_brings_the_wagon_and_animals_along():
    a = Group([_unit()], node="city")
    b = Group([_unit()], node="city", wagons=[Wagon()], herd=[_animal("Ox")])
    guild = Guild(None, groups=[a, b])
    guild.merge_groups(a, b)
    assert a.wagons and [x.species for x in a.herd] == ["Ox"]
    assert a.wagons[0].draft == [] and a.wagons[0]._group is a and not b.wagons


def test_merging_two_wagons_gives_the_group_both():
    a = Group([_unit()], node="city", wagons=[Wagon()])
    b = Group([_unit()], node="city", wagons=[Wagon("Carriage")])
    guild = Guild(None, groups=[a, b])
    guild.merge_groups(a, b)
    assert [w.kind for w in a.wagons] == ["Cart", "Carriage"] and all(w._group is a for w in a.wagons)


def _herder(wis):
    u = _unit()
    u.mod_wisdom = wis
    u.mod_charisma = 3       # keeps the group within capacity, which would re-derive the stats
    u._base_inventory = []
    return u


def test_herd_capacity_is_the_base_plus_the_leaders_wisdom_modifier():
    assert Group([_herder(0)]).herd_capacity == HERD_BASE
    assert Group([_herder(2)]).herd_capacity == HERD_BASE + 2
    assert Group([_herder(-3)]).herd_capacity == 1
    assert Group([_herder(-9)]).herd_capacity == 1


def test_every_animal_costs_its_herd_weight_against_the_capacity():
    g = Group([_herder(0)], herd=[_animal() for _ in range(HERD_BASE - 1)])
    assert g.herd_load == HERD_BASE - 1 and g.can_take(_animal())
    g.herd.append(_animal())
    assert not g.can_take(_animal())


def _overgrown(extra_cargo=()):
    pets = [_animal(tack=HARNESS), _animal(cargo=extra_cargo), _animal()]
    pets.append(_animal(tack=PACK_SADDLE, cargo=("Rope",)))
    leader = _herder(-2)
    guild = Guild(None, groups=[Group([leader], node="city", herd=pets)])
    return guild, guild.groups[0], leader


def test_an_overgrown_herd_gets_a_notice_and_then_loses_an_animal():
    from gartok import cohesion
    guild, g, _leader = _overgrown()
    assert g.herd_load > g.herd_capacity
    assert "days before one strays" in cohesion.daily(guild)[0]
    assert g.herd_notice == guild.clock.day + cohesion.NOTICE_DAYS and len(g.herd) == 4
    guild.clock.advance_hours(24 * cohesion.NOTICE_DAYS)
    events = cohesion.daily(guild)
    assert "strays off" in events[0] and len(g.herd) == 3
    assert g.herd_notice == guild.clock.day + cohesion.NOTICE_DAYS


def test_a_straying_animal_is_an_untacked_one_and_leaves_its_load_behind():
    from gartok import cohesion
    _guild, g, leader = _overgrown(extra_cargo=("Rope",))
    cohesion.stray(g)
    assert [a.tack for a in g.herd] == [HARNESS, None, PACK_SADDLE]
    cohesion.stray(g)
    assert [a.tack for a in g.herd] == [HARNESS, PACK_SADDLE]
    assert leader.count_of("Rope") == 1


def test_the_notice_drops_when_the_herd_is_back_within_control():
    from gartok import cohesion
    guild, g, _leader = _overgrown()
    cohesion.daily(guild)
    g.herd.clear()
    cohesion.daily(guild)
    assert g.herd_notice is None


def test_the_herd_notice_survives_a_save(tmp_path):
    _guild, g, _ = _overgrown()
    g.herd_notice = 12
    assert persist.group_from_dict(persist.group_to_dict(g)).herd_notice == 12


def test_merging_cannot_exceed_the_leaders_herd_capacity():
    a = Group([_herder(0)], node="city", herd=[_animal() for _ in range(HERD_BASE)])
    b = Group([_unit()], node="city", herd=[_animal()])
    guild = Guild(None, groups=[a, b])
    with pytest.raises(ValueError):
        guild.merge_groups(a, b)
    assert len(guild.groups) == 2


def test_a_wiser_leader_lets_a_merge_through():
    a = Group([_herder(1)], node="city", herd=[_animal() for _ in range(HERD_BASE)])
    b = Group([_unit()], node="city", herd=[_animal()])
    guild = Guild(None, groups=[a, b])
    guild.merge_groups(a, b)
    assert len(a.herd) == HERD_BASE + 1


def test_splitting_leaves_the_wagon_and_animals_with_the_original_group():
    a, b = _unit(), _unit()
    g = Group([a, b], node="city", wagons=[Wagon()], herd=[_animal()])
    guild = Guild(None, groups=[g])
    new = guild.split_group(g, [b])
    assert g.wagons and g.herd and not new.wagons and not new.herd


# --------------------------------------------------------------------------- #
# saves                                                                       #
# --------------------------------------------------------------------------- #

def test_animals_and_the_wagon_survive_a_save_round_trip():
    slot = "testworld_wagon"
    if os.path.exists(persist.save_path(slot)):
        return
    donkey, ox = _animal("Donkey", HARNESS), _animal("Ox", PACK_SADDLE, cargo=["Rope"])
    donkey.unfed_days = 1
    guild = Guild(None, groups=[Group([_unit()], node="city", wagons=[Wagon()], herd=[donkey, ox])])
    guild.groups[0].wagons[0].stash.put("Potato")
    guild.groups[0].hitch_idle()
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot).groups[0]
        assert [(a.species, a.tack, a.unfed_days) for a in back.herd] == [
            ("Donkey", HARNESS, 1), ("Ox", PACK_SADDLE, 0)]
        assert back.herd[1].stash.items[0].name == "Rope"
        assert back.herd[0].uid == donkey.uid
        assert [n for n, _ in back.wagons[0].stash.items] == ["Potato"]
        assert back.wagons[0].draft == [back.herd[0]]
    finally:
        persist.delete_world(slot)


def test_a_group_without_either_still_loads():
    slot = "testworld_nowagon"
    if os.path.exists(persist.save_path(slot)):
        return
    guild = Guild([_unit()])
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot).groups[0]
        assert back.wagons == [] and back.herd == []
    finally:
        persist.delete_world(slot)


# --------------------------------------------------------------------------- #
# the gear screen                                                             #
# --------------------------------------------------------------------------- #

def _gear(*animals, wagon=False, cargo=(), carried=()):
    from gartok.group_screen import GroupScreen
    guild, g = _group(*animals, wagon=wagon, cargo=cargo, members=2)
    g.members[0]._base_inventory = packed(list(carried))
    g.members[1]._base_inventory = []
    return GroupScreen(None, guild, g, on_back=lambda: None), g


def _draw(scr):
    import pygame
    pygame.init()
    scr.mouse = (0, 0)
    scr.draw(pygame.Surface((1900, 900)))


def test_a_member_item_can_be_dragged_into_the_wagon():
    scr, g = _gear(_animal(tack=HARNESS), wagon=True, carried=["Rope", "Map"])
    scr.selected = [(g.members[0], 0)]
    scr._give_many(g.wagons[0], "pack")
    assert g.members[0]._base_inventory == packed(["Map"]) and g.wagons[0].stash.items[0].name == "Rope"


def test_the_wagon_refuses_more_than_it_can_carry():
    scr, g = _gear(_animal(tack=HARNESS), wagon=True, carried=["Iron Bar"] * 19)   # 95 kg vs 90 free
    scr.selected = [(g.members[0], 0)]
    scr._give_many(g.wagons[0], "pack")
    assert g.wagons[0].stash.items == [] and g.members[0].count_of("Iron Bar") == 19
    assert "won't fit" in scr.notice and scr.selected


def test_an_unharnessed_wagon_says_why_it_is_shut():
    scr, g = _gear(_animal(tack=PACK_SADDLE), wagon=True, carried=["Rope"])
    scr.selected = [(g.members[0], 0)]
    scr._give_many(g.wagons[0], "pack")
    assert g.wagons[0].stash.items == [] and "hitched" in scr.notice


def test_an_unsaddled_animal_says_why_it_takes_nothing():
    scr, g = _gear(_animal(), carried=["Rope"])
    scr.selected = [(g.members[0], 0)]
    scr._give_many(g.herd[0], "pack")
    assert g.herd[0].stash.items == [] and "pack saddle" in scr.notice


def test_a_saddled_animal_takes_cargo_up_to_its_limit():
    scr, g = _gear(_animal(tack=PACK_SADDLE), carried=["Rope", "Iron Bar"])
    scr.selected = [(g.members[0], 0)]
    scr._give_many(g.herd[0], "pack")
    assert g.herd[0].stash.items[0].name == "Rope"


def test_cargo_comes_out_of_the_wagon_into_a_member_pack():
    scr, g = _gear(_animal(tack=HARNESS), wagon=True, cargo=["Rope"])
    scr.selected = [(g.wagons[0], 0)]
    scr._give_many(g.members[1], "pack")
    assert g.wagons[0].stash.items == [] and g.members[1].count_of("Rope") == 1


def test_dropping_a_saddle_on_an_animal_fits_it_and_returns_what_it_wore():
    scr, g = _gear(_animal(tack=HARNESS), carried=[PACK_SADDLE])
    scr.selected = [(g.members[0], 0)]
    scr._give_many(g.herd[0], "tack")
    assert g.herd[0].tack == PACK_SADDLE
    assert g.members[0].count_of(HARNESS) == 1 and g.members[0].count_of(PACK_SADDLE) == 0


def test_an_animal_refuses_things_that_are_not_tack():
    scr, g = _gear(_animal(), carried=["Rope"])
    scr.selected = [(g.members[0], 0)]
    scr._give_many(g.herd[0], "tack")
    assert g.herd[0].tack is None and g.members[0].count_of("Rope") == 1


def test_tack_can_be_taken_off_by_dragging_it_to_a_pack():
    scr, g = _gear(_animal(tack=PACK_SADDLE))
    scr.selected = [(g.herd[0], "tack")]
    scr._give_many(g.members[0], "pack")
    assert g.herd[0].tack is None and g.members[0].count_of(PACK_SADDLE) == 1


def test_the_gear_screen_draws_animal_and_wagon_columns_and_their_cargo_rows():
    scr, g = _gear(_animal(tack=PACK_SADDLE, cargo=["Rope"]), wagon=True, cargo=["Rope"])
    _draw(scr)
    owners = {id(o) for _, o, zone in scr.zones if zone == "pack"}
    assert id(g.wagons[0]) in owners and id(g.herd[0]) in owners
    assert any(o is g.herd[0] and zone == "tack" for _, o, zone in scr.zones)
    scr.view = "cargo"
    _draw(scr)
    assert any(o is g.wagons[0] for _, o, _loc in scr.sources)
    assert any(o is g.herd[0] for _, o, _loc in scr.sources)


def test_the_send_to_menu_offers_the_stores_but_no_member_only_actions_on_their_cargo():
    scr, g = _gear(_animal(tack=PACK_SADDLE), wagon=True, carried=["Rope"], cargo=["Minor Healing Potion"])
    scr._open_menu((10, 10), picks=[(g.members[0], 0)])
    labels = [r[1] for r in scr.menu["rows"]]
    assert "to Cart" in labels and "to Donkey" in labels
    scr._open_menu((10, 10), picks=[(g.wagons[0], 0)])
    assert not any(r[0] == "drink" for r in scr.menu["rows"])


def test_a_stack_in_the_wagon_can_be_split():
    _, g = _gear(_animal(tack=HARNESS), wagon=True, cargo=["Rope", "Rope", "Rope"])
    assert g.wagons[0].split_pack(0, 1) and [it.qty for it in g.wagons[0].stash.items] == [2, 1]


# --------------------------------------------------------------------------- #
# the creature sheet                                                          #
# --------------------------------------------------------------------------- #

def test_animals_are_beast_races_that_the_wild_never_rolls():
    for name in data.LIVESTOCK:
        assert data.race_by_name(name)["kind"] == "beast" and name in data.ALL_RACE_NAMES
        assert name not in {r["name"] for r in data.BEAST_POOL}


def test_shop_animals_have_fixed_attributes():
    assert [_animal(n).strength for n in data.LIVESTOCK] == [13, 14, 16]
    assert _animal("Ox").attributes == _animal("Ox").attributes


def test_loads_come_from_strength_in_units_of_30_kg():
    assert [(a.back_load, a.draw) for a in map(_animal, data.LIVESTOCK)] == [(30, 90), (90, 180), (60, 120)]


def test_only_the_ox_has_beast_of_burden():
    assert abilities.get(data.race_by_name("Ox")["ability"]).carry_mult == 2.0
    assert {n for n in data.LIVESTOCK if _animal(n).ability.carry_mult != 1.0} == {"Ox"}


def test_beast_of_burden_multiplies_when_combined_with_another_ability():
    assert abilities.get(("beast_of_burden", "strong_body")).carry_mult == 2.0


def test_an_animal_has_hit_points_from_its_hit_die_and_constitution():
    assert [_animal(n).hp for n in data.LIVESTOCK] == [6, 7, 6]
    assert _animal("Ox", tack=HARNESS).hp_max == 7


def test_animals_and_wagons_share_the_creature_base():
    from gartok.creature import Creature
    assert isinstance(_animal(), Creature) and isinstance(Wagon(), Creature)
    assert Wagon().uid != Wagon().uid


def test_a_vehicle_is_hit_dice_of_d8_with_no_constitution():
    assert (VEHICLES["Cart"].hd, VEHICLES["Carriage"].hd) == (1, 3)
    assert (Wagon("Cart").hp, Wagon("Carriage").hp) == (5, 13)


def test_group_wagons_know_their_group():
    g = Group([_unit()], node="city")
    w = Wagon()
    g.add_wagon(w)
    assert g.wagons == [w] and w._group is g
    g.remove_wagon(w)
    assert g.wagons == [] and w._group is None


def test_several_wagons_survive_a_save():
    g = Group([_unit()], node="city", wagons=[Wagon(), Wagon()], herd=[_animal()])
    back = persist.group_from_dict(persist.group_to_dict(g))
    assert [w.uid for w in back.wagons] == [w.uid for w in g.wagons] and len(back.herd) == 1


# --------------------------------------------------------------------------- #
# vehicles, the hitch, several wagons                                         #
# --------------------------------------------------------------------------- #

def _fleet(*kinds, pets=()):
    g = Group([_unit(), _unit()], node="city", wagons=[Wagon(k) for k in kinds], herd=list(pets))
    g.hitch_idle()
    return Guild(None, groups=[g]), g


def test_every_vehicle_is_a_d8_object_with_its_own_box_and_price():
    assert {v.slots for v in VEHICLES.values()} == {1, 3}
    assert VEHICLES["Cart"].capacity == 180 and VEHICLES["Carriage"].capacity == 540
    assert Wagon("Carriage").price == VEHICLES["Carriage"].price and Wagon("Carriage").name == "Carriage"


def test_the_harness_pulls_only_the_wagon_it_is_hitched_to():
    d1, d2 = _animal("Donkey", HARNESS), _animal("Ox", HARNESS)
    _, g = _fleet("Cart", "Cart", pets=[d1, d2])
    first, second = g.wagons
    assert first.draft == [d1] and second.draft == [d2]
    assert (first.budget, second.budget) == (90, 180)


def test_a_harnessed_animal_with_no_free_wagon_pulls_nothing():
    spare = _animal("Ox", HARNESS)
    _, g = _fleet("Cart", pets=[_animal("Ox", HARNESS), spare])
    assert g.pulling(spare) is None


def test_hitching_by_hand_moves_an_animal_between_wagons():
    d = _animal("Donkey", HARNESS)
    _, g = _fleet("Cart", "Cart", pets=[d])
    first, second = g.wagons
    assert g.pulling(d) is first
    g.next_hitch(d)
    assert g.pulling(d) is second
    g.next_hitch(d)
    assert g.pulling(d) is None
    g.next_hitch(d)
    assert g.pulling(d) is first


def test_hitching_refuses_a_full_wagon_and_a_bare_animal():
    pulled, other = _animal("Donkey", HARNESS), _animal("Donkey", HARNESS)
    _, g = _fleet("Cart", "Cart", pets=[pulled, other])
    first, second = g.wagons
    assert not g.hitch(other, first) and g.hitch(other, second)
    assert not g.hitch(_animal(), first)


def test_removing_a_wagon_unhitches_its_animals_and_taking_tack_off_does_too():
    d = _animal("Donkey", HARNESS)
    _, g = _fleet("Cart", pets=[d])
    g.remove_wagon(g.wagons[0])
    assert d.hitch is None
    _, g = _fleet("Cart", pets=[_animal("Donkey", HARNESS)])
    g.herd[0].take_tack()
    assert g.herd[0].hitch is None and g.wagons[0].draft == []


def test_a_new_harness_hitches_to_the_first_wagon_with_room():
    d = _animal()
    _, g = _fleet("Cart", pets=[d])
    d.give_to_tack(HARNESS)
    g.hitch_idle()
    assert g.wagons[0].draft == [d]


def test_the_hitch_and_the_vehicle_type_survive_a_save():
    d = _animal("Ox", HARNESS)
    _, g = _fleet("Cart", "Carriage", pets=[d])
    g.hitch(d, g.wagons[1])
    back = persist.group_from_dict(persist.group_to_dict(g))
    assert [w.kind for w in back.wagons] == ["Cart", "Carriage"]
    assert back.pulling(back.herd[0]) is back.wagons[1] and back.wagons[1].budget == 180


def test_merging_keeps_each_animal_on_its_own_wagon():
    a = Group([_herder(0)], node="city", wagons=[Wagon()], herd=[_animal("Donkey", HARNESS)])
    b = Group([_herder(0)], node="city", wagons=[Wagon()], herd=[_animal("Ox", HARNESS)])
    a.hitch_idle()
    b.hitch_idle()
    Guild(None, groups=[a, b]).merge_groups(a, b)
    assert [w.budget for w in a.wagons] == [90, 180]


def test_a_split_can_hand_over_a_wagon_and_its_animals():
    d, spare = _animal("Donkey", HARNESS), _animal()
    guild, g = _fleet("Cart", "Cart", pets=[d, spare])
    first = g.wagons[0]
    new = guild.split_group(g, [g.members[0]], wagons=[first], herd=[d])
    assert new.wagons == [first] and new.herd == [d] and new.pulling(d) is first
    assert len(g.wagons) == 1 and g.herd == [spare] and g.wagons[0]._group is g


def test_an_animal_split_away_from_its_wagon_is_unhitched():
    d = _animal("Donkey", HARNESS)
    guild, g = _fleet("Cart", pets=[d])
    new = guild.split_group(g, [g.members[0]], herd=[d])
    assert new.herd == [d] and d.hitch is None and g.wagons[0].draft == []


def test_a_split_takes_only_what_is_picked_and_cannot_outgrow_the_new_herd():
    pets = [_animal() for _ in range(HERD_BASE + 1)]
    guild, g = _fleet("Cart", pets=pets)
    for u in g.members:
        u.mod_wisdom = 0
    with pytest.raises(ValueError):
        guild.split_group(g, [g.members[0]], herd=pets)
    assert len(g.herd) == HERD_BASE + 1 and len(guild.groups) == 1
    new = guild.split_group(g, [g.members[0]])
    assert not new.wagons and not new.herd and len(g.wagons) == 1


# --------------------------------------------------------------------------- #
# hitching by swap and by dragging on the gear screen                         #
# --------------------------------------------------------------------------- #

def test_hitching_onto_a_full_wagon_swaps_the_two_animals():
    a, b = _animal("Donkey", HARNESS), _animal("Ox", HARNESS)
    _, g = _fleet("Cart", "Cart", pets=[a, b])
    first, second = g.wagons
    assert g.pulling(a) is first and g.pulling(b) is second
    assert g.hitch(a, second, swap=True)
    assert g.pulling(a) is second and g.pulling(b) is first


def test_dragging_to_a_full_wagon_from_no_wagon_bumps_one_animal_out():
    a, b = _animal("Donkey", HARNESS), _animal("Ox", HARNESS)
    _, g = _fleet("Cart", pets=[a, b])
    assert g.pulling(a) is g.wagons[0] and g.pulling(b) is None
    assert g.hitch(b, g.wagons[0], swap=True)
    assert g.pulling(b) is g.wagons[0] and g.pulling(a) is None


def test_an_animal_without_a_harness_cannot_be_hitched_or_swapped_in():
    bare = _animal()
    _, g = _fleet("Cart", pets=[_animal("Ox", HARNESS), bare])
    assert not g.hitch(bare, g.wagons[0], swap=True) and bare.hitch is None


def _drag(scr, src, dst):
    import pygame
    scr.pinned = []                       # leave room for every animal and wagon column
    _draw(scr)
    a = next(r for r, o, loc in scr.sources if o is src and loc == "hitch")
    b = next(r for r, o, zone in scr.zones if o is dst and zone == "hitch")
    scr.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=a.center))
    scr.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=b.center, rel=(0, 0), buttons=(1, 0, 0)))
    scr.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=b.center))


def test_dragging_an_animal_header_onto_a_wagon_header_hitches_it():
    d = _animal("Donkey", HARNESS)
    scr, g = _gear(d, wagon=True)
    g.add_wagon(Wagon("Carriage"))
    g.hitch(d, g.wagons[1])
    _drag(scr, d, g.wagons[0])
    assert g.pulling(d) is g.wagons[0] and "pulls the cart" in scr.notice


def test_dragging_swaps_when_the_wagon_is_full():
    a, b = _animal("Donkey", HARNESS), _animal("Ox", HARNESS)
    scr, g = _gear(a, b, wagon=True)
    g.add_wagon(Wagon())
    g.hitch(b, g.wagons[1])
    assert g.pulling(a) is g.wagons[0]
    _drag(scr, a, g.wagons[1])
    assert g.pulling(a) is g.wagons[1] and g.pulling(b) is g.wagons[0]


def test_only_harnessed_animals_can_be_picked_up_by_the_header_and_cargo_still_drops_in_the_wagon():
    pack = _animal(tack=PACK_SADDLE)
    scr, g = _gear(pack, _animal(tack=HARNESS), wagon=True, carried=["Rope"])
    _draw(scr)
    assert not any(o is pack and loc == "hitch" for _, o, loc in scr.sources)
    scr.selected = [(g.members[0], 0)]
    scr._give_many(g.wagons[0], "pack")
    assert g.wagons[0].stash.items[0].name == "Rope"


def test_the_animal_header_says_what_it_pulls():
    d = _animal("Donkey", HARNESS)
    scr, _g = _gear(d, wagon=True)
    assert scr._store_dict(d, [])["name"].endswith("pulls cart")
    d.hitch = None
    assert scr._store_dict(d, [])["name"].endswith("unhitched")


def test_group_speed_is_the_slowest_of_members_and_animals():
    a, b = _unit(), _unit()
    g = Group([a, b], node="city")
    walk = min(a.speed, b.speed) * 1.5
    assert g.speed == walk
    g.herd.append(_animal("Donkey"))
    assert g.speed == min(walk, 6.0)
    g.herd.append(_animal("Horse"))
    assert g.speed == min(walk, 6.0)


def test_a_loaded_down_member_slows_the_group():
    a = _unit()
    a.strength = 18
    a._base_inventory = []
    a._derive_combat()
    g = Group([a], node="city")
    free = g.speed
    a._base_inventory.append(("Iron Bar", int(a.carry_normal / items.item_weight("Iron Bar")) + 1))
    a._derive_combat()
    assert a.encumbered and g.speed < free


# --------------------------------------------------------------------------- #
# load and herd loose ends                                                    #
# --------------------------------------------------------------------------- #

def test_distribute_load_fills_the_pack_animals_and_the_wagon_too():
    _, g = _group(_animal(tack=PACK_SADDLE), _animal(tack=HARNESS), wagon=True)
    g.members[0]._base_inventory = packed(["Iron Bar"] * 40)
    pack, wagon = g.herd[0], g.wagons[0]
    g.distribute_load()
    assert pack.stash.load > 0 and wagon.stash.load > 0
    bars = sum(q for c in (*g.members, pack, wagon) for n, q in c._base_inventory if n == "Iron Bar")
    assert bars == 40


def test_distribute_load_skips_a_creature_with_no_room_and_never_gives_it_coins():
    _, g = _group(_animal(), wagon=True, members=2)
    g.members[0]._base_inventory = packed(["Iron Bar"] * 4)
    g.members[1].give_to_pack(items.COIN_ITEM, 500)
    g.distribute_load()
    assert g.herd[0].stash.load == 0 and g.wagons[0].stash.load == 0


def test_coins_stay_on_people_when_animals_share_the_load():
    _, g = _group(_animal(tack=PACK_SADDLE), members=2)
    g.members[0].give_to_pack(items.COIN_ITEM, 4000)
    g.distribute_load()
    assert all(items.COIN_ITEM not in [n for n, _ in a.stash.items] for a in g.herd)


def test_a_new_leader_who_cannot_control_the_herd_starts_the_notice_at_once():
    from gartok import cohesion
    wise, dim = _herder(2), _herder(-2)
    pets = [_animal() for _ in range(HERD_BASE + 1)]
    guild = Guild(None, groups=[Group([wise, dim], node="city", herd=pets, leader=wise)])
    g = guild.groups[0]
    assert g.herd_notice is None
    events = guild.set_group_leader(g, dim)
    assert g.herd_notice == guild.clock.day + cohesion.NOTICE_DAYS and "days before one strays" in events[0]
    assert guild.set_group_leader(g, wise) == [] and g.herd_notice is None


def test_a_leader_dying_starts_the_herd_notice_for_the_successor():
    wise, dim = _herder(2), _herder(-2)
    pets = [_animal() for _ in range(HERD_BASE + 1)]
    guild = Guild(None, groups=[Group([wise, dim], node="city", herd=pets, leader=wise)])
    g = guild.groups[0]
    g.members.remove(wise)
    guild._sync_leadership()
    assert g.leader is dim and g.herd_notice is not None


# --------------------------------------------------------------------------- #
# passengers, by weight                                                       #
# --------------------------------------------------------------------------- #

def _rider(speed, size="Medium"):
    u = _unit(size)
    u._base_inventory = []
    u.speed = speed
    return u


def _coach(*riders, pets=(("Ox", HARNESS),), kind="Carriage", cargo=()):
    g = Group(list(riders), node="city", wagons=[Wagon(kind)], herd=[_animal(*p) for p in pets])
    g.hitch_idle()
    for name in cargo:
        g.wagons[0].stash.put(name)
    return g


def _weight(u):
    return u.ride_weight


def test_a_body_weighs_what_its_size_says():
    assert [data.SIZES[s]["kg"] for s in data.SIZE_ORDER] == [15, 30, 60, 120, 240]


def test_everyone_who_fits_rides_and_the_wagons_pace_stands_in_for_theirs():
    slow, other = _rider(6), _rider(7)
    g = _coach(slow, other, pets=(("Ox", HARNESS), ("Ox", HARNESS)))
    assert g.wagons[0].passengers == [slow, other] and set(g.riders) == {slow, other}
    assert g.speed == g.herd[0].speed < slow.speed * data.METERS_PER_SQUARE


def test_a_wagon_with_nothing_to_pull_it_seats_nobody():
    g = _coach(_rider(2), pets=())
    assert g.wagons[0].passengers == [] and g.speed == _rider(2).speed * data.METERS_PER_SQUARE


def test_a_passenger_counts_with_everything_they_carry():
    light, heavy = _rider(5), _rider(5)
    heavy._base_inventory = packed(["Iron Bar"] * 30)
    assert _coach(light, pets=(("Donkey", HARNESS),), kind="Cart").wagons[0].passengers == [light]
    assert _coach(heavy, pets=(("Donkey", HARNESS),), kind="Cart").wagons[0].passengers == []


def test_the_slowest_board_first_and_whoever_is_left_walks():
    slow, mid, fast = _rider(2), _rider(4), _rider(6)
    g = _coach(fast, slow, mid, pets=(("Horse", HARNESS),), kind="Cart")
    assert g.wagons[0].budget == 120 and _weight(slow) + _weight(mid) > 120 >= _weight(slow)
    assert g.wagons[0].passengers == [slow]
    assert g.speed == min(mid.speed * data.METERS_PER_SQUARE, g.herd[0].speed)


def test_passengers_and_cargo_share_one_budget():
    rider = _rider(5)
    g = _coach(rider, pets=(("Ox", HARNESS),), kind="Cart")
    wagon = g.wagons[0]
    assert wagon.budget == 180 and wagon.capacity == 180 - _weight(rider)
    assert not wagon.stash.fits(wagon.capacity + 1) and wagon.stash.fits(wagon.capacity)


def test_cargo_that_leaves_no_room_for_a_passenger_puts_them_back_on_foot():
    rider = _rider(5)
    g = _coach(rider, pets=(("Ox", HARNESS),), kind="Cart", cargo=["Iron Bar"] * 30)
    assert g.wagons[0].stash.load == 150 and g.wagons[0].passengers == []
    assert g.wagons[0].capacity == 180 and g.wagons[0].stash.fits(30) and not g.wagons[0].stash.fits(31)


def test_several_wagons_seat_the_group_between_them():
    a, b, c = _rider(2), _rider(3), _rider(4)
    g = Group([a, b, c], node="city", wagons=[Wagon("Cart"), Wagon("Cart")],
              herd=[_animal("Ox", HARNESS), _animal("Ox", HARNESS)])
    g.hitch_idle()
    seated = g.boarding()
    assert sorted(len(v) for v in seated.values()) == [1, 2] and set(g.riders) == {a, b, c}


def test_a_wagon_never_holds_more_hp_than_its_vehicle_allows():
    assert Wagon("Cart", hp=30).hp == VEHICLES["Cart"].hp_max
    saved = persist.wagon_to_dict(Wagon("Cart", hp=30))
    assert persist.wagon_from_dict(saved).hp == VEHICLES["Cart"].hp_max
    assert Wagon("Cart", hp=2).hp == 2


def test_wagon_capacity_carries_no_float_noise(monkeypatch):
    g = Group([_unit()], node="city")
    g.add_wagon(Wagon("Cart"))
    ox = Animal("Ox", tack=HARNESS)
    g.herd.append(ox)
    ox.hitch = g.wagons[0].uid
    monkeypatch.setattr(Wagon, "passenger_weight", property(lambda self: 63.0 + 40.3 + 75.0))
    assert g.wagons[0].capacity == 1.7


# --------------------------------------------------------------------------- #
# the Market shows the group's wagon and animals as more packs                #
# --------------------------------------------------------------------------- #

def _market(*animals, **kw):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok import world
    from gartok.market_screen import MarketScreen
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))
    guild, g = _group(*animals, **kw)
    node = next(n for n in world.NODES if n.kind == "market")
    scr = MarketScreen(ui_fonts(), guild, list(g.members), node, lambda: None)
    scr.draw(pygame.Surface((1800, 900)))
    return scr, g


def test_the_market_shows_the_wagon_and_the_herd_beside_the_shoppers():
    scr, g = _market(_animal("Ox", HARNESS), wagon=True)
    assert scr.stores == [*g.herd, *g.wagons]
    assert any(o is g.wagons[0] for _, o in scr._pack_areas)


def test_a_purchase_can_be_dropped_on_the_wagon_and_stops_at_its_room():
    scr, g = _market(_animal("Ox", HARNESS), wagon=True)
    wagon, buyer = g.wagons[0], g.members[0]
    buyer.money = 100
    scr._buy(wagon, ["Torch"])
    assert [i.name for i in wagon.stash.items] == ["Torch"]
    assert buyer.money < 100
    bare, g2 = _market(wagon=True)                                  # no animal hitched: no room
    g2.members[0].money = 100
    bare._buy(g2.wagons[0], ["Torch"])
    assert not g2.wagons[0].stash.items and g2.members[0].money == 100


def test_selling_from_the_wagon_pays_the_shopper():
    scr, g = _market(_animal("Ox", HARNESS), wagon=True, cargo=["Torch"])
    wagon, seller = g.wagons[0], g.members[0]
    seller.money = 0
    scr.selected = [(wagon, 0)]
    scr._sell()
    assert not wagon.stash.items and seller.money > 0


def test_the_wagon_column_names_who_is_riding():
    from gartok import store_column
    slow, other = _rider(6), _rider(7)
    slow.name, other.name = "Ana", "Bo"
    g = _coach(slow, other, pets=(("Ox", HARNESS), ("Ox", HARNESS)))
    status = store_column.store_dict(g, g.wagons[0], set(), [])["status"]["text"]
    assert "riding: Ana, Bo" in status
    walker = _coach(_rider(6, "Huge"))
    assert "riding" not in store_column.store_dict(walker, walker.wagons[0], set(), [])["status"]["text"]


# --------------------------------------------------------------------------- #
# the Guild screen shows an animal like a member                              #
# --------------------------------------------------------------------------- #

def _guild_screen(*animals, **kw):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.guild_screen import GuildScreen
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))
    guild, g = _group(*animals, **kw)
    scr = GuildScreen(ui_fonts(), guild, on_back=lambda: None, on_manage=lambda grp: None)
    scr.draw(pygame.Surface((1700, 950)))
    return scr, g


def test_the_guild_roster_lists_the_herd_and_its_sheet_opens():
    import pygame
    ox = _animal("Ox", HARNESS)
    scr, g = _guild_screen(ox, wagon=True)
    hit = next(r for r, o in scr.member_hits if o is ox)
    scr.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=hit.center))
    assert scr.member is ox
    surf = pygame.Surface((1700, 950))
    scr.draw(surf)
    assert scr.member is ox                          # the draw keeps an animal selected


def test_an_animal_selected_in_the_guild_ignores_member_only_buttons():
    ox = _animal("Ox")
    scr, g = _guild_screen(ox)
    scr.member = ox
    for key in ("level", "share_food", "group_leader", "guild_leader"):
        scr._press(key)
    assert g.leader is not ox


def test_a_hungry_animal_is_an_alert_and_wears_the_badge():
    ox = _animal("Ox")
    scr, g = _guild_screen(ox)
    ox.unfed_days = 1
    scr.filter_mode = "alerts"
    bands = scr._roster_bands()
    assert [m["name"] for m in bands[0]["members"]] == ["Ox"]
    assert ("HUNGRY",) == tuple(b[0] for b in bands[0]["members"][0]["badges"])


def test_the_band_header_counts_people_not_animals():
    scr, _g = _guild_screen(_animal("Ox"), _animal("Donkey"))
    band = scr._roster_bands()[0]
    assert band["count"] == 1 and len(band["members"]) == 3


def test_the_animal_sheet_scrolls_when_the_window_is_short():
    import pygame
    ox = _animal("Ox", HARNESS)
    scr, _g = _guild_screen(ox, wagon=True)
    scr.member = ox
    scr.draw(pygame.Surface((1700, 950)))
    assert scr._detail_max_scroll == 0
    scr.draw(pygame.Surface((1700, 420)))
    assert scr._detail_max_scroll > 0
