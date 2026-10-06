"""Animals, tack and the group wagon: what an animal does depends on what it wears,
the wagon is pulled by the group's harnessed animals, everyone eats from what the
group carries, and what happens to it all when the group changes."""

import os

import pytest

from gartok import items, persist
from gartok.animals import HARNESS, PACK_SADDLE, SPECIES, STARVE_DAYS, Animal
from gartok.group import HERD_BASE, Group
from gartok.guild import Guild
from gartok.wagon import HITCH_SLOTS, WAGON_CAPACITY, WAGON_WEIGHT, Wagon
from tests.helpers import Unit, packed


def _animal(species="Donkey", tack=None, cargo=()):
    a = Animal(species, tack=tack)
    for name in cargo:
        a.stash.put(name)
    return a


def _group(*animals, wagon=None, cargo=(), members=1, food=()):
    units = [Unit("player") for _ in range(members)]
    for u in units:
        u._base_inventory = packed(list(food))
    w = Wagon() if wagon else None
    g = Group(units, node="city", wagon=w, animals=list(animals))
    if w is not None:
        for name in cargo:
            w.stash.put(name)
    return Guild(None, groups=[g]), g


# --------------------------------------------------------------------------- #
# tack decides the role                                                       #
# --------------------------------------------------------------------------- #

def test_an_animal_without_tack_does_nothing():
    a = _animal()
    assert a.role is None and a.carry_room == 0 and a.pull == 0


def test_a_pack_saddle_lets_it_carry_and_a_harness_lets_it_pull():
    pack, draft = _animal(tack=PACK_SADDLE), _animal(tack=HARNESS)
    assert pack.role == "pack" and pack.carry_room == SPECIES["Donkey"]["carry"] and pack.pull == 0
    assert draft.role == "draft" and draft.pull == SPECIES["Donkey"]["pull"] and draft.carry_room == 0


def test_only_a_saddle_or_harness_can_be_worn():
    assert Animal.can_wear(PACK_SADDLE) and Animal.can_wear(HARNESS)
    assert not Animal.can_wear("Rope")


def test_tack_is_a_tagged_item():
    assert items.item_tags(PACK_SADDLE) == ["TACK"] and items.item_tags(HARNESS) == ["TACK"]


def test_an_unsaddled_animal_cannot_be_loaded():
    a = _animal()
    assert not a.stash.fits(1)
    a.give_to_tack(PACK_SADDLE)
    assert a.stash.fits(SPECIES["Donkey"]["carry"])


# --------------------------------------------------------------------------- #
# the wagon is pulled by harnessed animals                                    #
# --------------------------------------------------------------------------- #

def test_a_wagon_with_nothing_harnessed_holds_nothing():
    _, g = _group(_animal(), _animal(tack=PACK_SADDLE), wagon=True)
    assert g.wagon.capacity == 0 and g.wagon.speed is None


def test_capacity_is_what_the_harnessed_animals_draw_minus_the_wagon_itself():
    donkey = SPECIES["Donkey"]["pull"]
    _, g = _group(_animal(tack=HARNESS), wagon=True)
    assert g.wagon.capacity == donkey - WAGON_WEIGHT
    _, g = _group(_animal(tack=HARNESS), _animal(tack=HARNESS), wagon=True)
    assert g.wagon.capacity == min(WAGON_CAPACITY, 2 * donkey - WAGON_WEIGHT)


def test_capacity_never_exceeds_what_the_box_holds():
    _, g = _group(_animal("Ox", HARNESS), _animal("Ox", HARNESS), wagon=True)
    assert g.wagon.capacity == WAGON_CAPACITY


def test_only_a_few_animals_fit_the_hitch():
    _, g = _group(*[_animal("Ox", HARNESS) for _ in range(HITCH_SLOTS + 1)], wagon=True)
    assert len(g.wagon.draft) == HITCH_SLOTS


def test_speed_is_the_slowest_animal_pulling():
    _, g = _group(_animal("Donkey", HARNESS), _animal("Ox", HARNESS), wagon=True)
    assert g.wagon.speed == SPECIES["Ox"]["speed"]


def test_taking_the_harness_off_shrinks_the_cargo_room():
    _, g = _group(_animal(tack=HARNESS), _animal(tack=HARNESS), wagon=True)
    before = g.wagon.capacity
    g.animals[0].take_tack()
    assert g.wagon.capacity < before


# --------------------------------------------------------------------------- #
# eating                                                                      #
# --------------------------------------------------------------------------- #

def test_members_eat_from_the_wagon_without_share_food():
    guild, g = _group(wagon=True, cargo=["Potato", "Potato"])
    g.members[0].share_food = False
    guild.pass_time(24)
    assert g.members[0].unfed_days == 0 and g.wagon.rations == 1


def test_members_eat_from_an_animals_load():
    guild, g = _group(_animal(tack=PACK_SADDLE, cargo=["Potato"] * 2))
    guild.pass_time(24)
    assert g.members[0].unfed_days == 0
    assert g.carried_rations <= 1


def test_each_animal_eats_one_ration_a_day_from_the_wagon_first():
    guild, g = _group(_animal(), _animal(), wagon=True, cargo=["Potato"] * 4)
    guild.pass_time(24)
    assert g.wagon.rations == 1                       # the member and both animals ate
    assert all(a.unfed_days == 0 for a in g.animals)


def test_an_animal_with_no_food_anywhere_goes_hungry_then_starves():
    _, g = _group(_animal())
    g.members[0]._base_inventory = []
    for day in range(1, STARVE_DAYS):
        assert any("went hungry" in e for e in g.feed_animals())
        assert g.animals[0].unfed_days == day
    assert any("starved" in e for e in g.feed_animals())
    assert g.animals == []


def test_a_meal_resets_an_animals_hunger():
    _, g = _group(_animal(), food=["Potato"])
    g.animals[0].unfed_days = 2
    g.feed_animals()
    assert g.animals[0].unfed_days == 0 and g.members[0].count_of("Potato") == 0


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
    guild.groups.append(Group([Unit("player")], node="city"))
    guild.remove_members(list(g.members))
    assert g not in guild.groups


def test_a_group_that_loses_members_but_not_all_keeps_them():
    guild, g = _group(_animal(), wagon=True, members=2)
    guild.remove_members([g.members[0]])
    assert g in guild.groups and g.wagon is not None and len(g.animals) == 1


def test_merging_brings_the_wagon_and_animals_along():
    a = Group([Unit("player")], node="city")
    b = Group([Unit("player")], node="city", wagon=Wagon(), animals=[_animal("Ox")])
    guild = Guild(None, groups=[a, b])
    guild.merge_groups(a, b)
    assert a.wagon is not None and [x.species for x in a.animals] == ["Ox"]
    assert a.wagon.draft == [] and a.wagon._group is a


def test_two_wagons_cannot_merge():
    a = Group([Unit("player")], node="city", wagon=Wagon())
    b = Group([Unit("player")], node="city", wagon=Wagon())
    guild = Guild(None, groups=[a, b])
    with pytest.raises(ValueError):
        guild.merge_groups(a, b)
    assert len(guild.groups) == 2


def _herder(wis):
    u = Unit("player")
    u.mod_wisdom = wis
    return u


def test_herd_capacity_is_the_base_plus_the_leaders_wisdom_modifier():
    assert Group([_herder(0)]).herd_capacity == HERD_BASE
    assert Group([_herder(2)]).herd_capacity == HERD_BASE + 2
    assert Group([_herder(-3)]).herd_capacity == 1
    assert Group([_herder(-9)]).herd_capacity == 1


def test_every_animal_costs_its_herd_weight_against_the_capacity():
    g = Group([_herder(0)], animals=[_animal() for _ in range(HERD_BASE - 1)])
    assert g.herd_load == HERD_BASE - 1 and g.can_take(_animal())
    g.animals.append(_animal())
    assert not g.can_take(_animal())


def _overgrown(extra_cargo=()):
    pets = [_animal(tack=HARNESS), _animal(cargo=extra_cargo), _animal()]
    pets.append(_animal(tack=PACK_SADDLE, cargo=("Rope",)))
    leader = _herder(-2)
    guild = Guild(None, groups=[Group([leader], node="city", animals=pets)])
    return guild, guild.groups[0], leader


def test_an_overgrown_herd_gets_a_notice_and_then_loses_an_animal():
    from gartok import cohesion
    guild, g, leader = _overgrown()
    assert g.herd_load > g.herd_capacity
    assert "days before one strays" in cohesion.daily(guild)[0]
    assert g.herd_notice == guild.clock.day + cohesion.NOTICE_DAYS and len(g.animals) == 4
    guild.clock.advance_hours(24 * cohesion.NOTICE_DAYS)
    events = cohesion.daily(guild)
    assert "strays off" in events[0] and len(g.animals) == 3
    assert g.herd_notice == guild.clock.day + cohesion.NOTICE_DAYS


def test_a_straying_animal_is_an_untacked_one_and_leaves_its_load_behind():
    from gartok import cohesion
    guild, g, leader = _overgrown(extra_cargo=("Rope",))
    cohesion.stray(g)
    assert [a.tack for a in g.animals] == [HARNESS, None, PACK_SADDLE]
    cohesion.stray(g)
    assert [a.tack for a in g.animals] == [HARNESS, PACK_SADDLE]
    assert leader.count_of("Rope") == 1


def test_the_notice_drops_when_the_herd_is_back_within_control():
    from gartok import cohesion
    guild, g, leader = _overgrown()
    cohesion.daily(guild)
    g.animals.clear()
    cohesion.daily(guild)
    assert g.herd_notice is None


def test_the_herd_notice_survives_a_save(tmp_path):
    guild, g, _ = _overgrown()
    g.herd_notice = 12
    assert persist.group_from_dict(persist.group_to_dict(g)).herd_notice == 12


def test_merging_cannot_exceed_the_leaders_herd_capacity():
    a = Group([_herder(0)], node="city", animals=[_animal() for _ in range(HERD_BASE)])
    b = Group([Unit("player")], node="city", animals=[_animal()])
    guild = Guild(None, groups=[a, b])
    with pytest.raises(ValueError):
        guild.merge_groups(a, b)
    assert len(guild.groups) == 2


def test_a_wiser_leader_lets_a_merge_through():
    a = Group([_herder(1)], node="city", animals=[_animal() for _ in range(HERD_BASE)])
    b = Group([Unit("player")], node="city", animals=[_animal()])
    guild = Guild(None, groups=[a, b])
    guild.merge_groups(a, b)
    assert len(a.animals) == HERD_BASE + 1


def test_splitting_leaves_the_wagon_and_animals_with_the_original_group():
    a, b = Unit("player"), Unit("player")
    g = Group([a, b], node="city", wagon=Wagon(), animals=[_animal()])
    guild = Guild(None, groups=[g])
    new = guild.split_group(g, [b])
    assert g.wagon is not None and g.animals and new.wagon is None and not new.animals


# --------------------------------------------------------------------------- #
# saves                                                                       #
# --------------------------------------------------------------------------- #

def test_animals_and_the_wagon_survive_a_save_round_trip():
    slot = "testworld_wagon"
    if os.path.exists(persist.save_path(slot)):
        return
    donkey, ox = _animal("Donkey", HARNESS), _animal("Ox", PACK_SADDLE, cargo=["Rope"])
    donkey.unfed_days = 1
    guild = Guild(None, groups=[Group([Unit("player")], node="city", wagon=Wagon(), animals=[donkey, ox])])
    guild.groups[0].wagon.stash.put("Potato")
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot).groups[0]
        assert [(a.species, a.tack, a.unfed_days) for a in back.animals] == [
            ("Donkey", HARNESS, 1), ("Ox", PACK_SADDLE, 0)]
        assert back.animals[1].stash.items[0].name == "Rope"
        assert back.animals[0].uid == donkey.uid
        assert [n for n, _ in back.wagon.stash.items] == ["Potato"]
        assert back.wagon.draft == [back.animals[0]]
    finally:
        persist.delete_world(slot)


def test_a_group_without_either_still_loads():
    slot = "testworld_nowagon"
    if os.path.exists(persist.save_path(slot)):
        return
    guild = Guild([Unit("player")])
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot).groups[0]
        assert back.wagon is None and back.animals == []
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
    scr._give_many(g.wagon, "pack")
    assert g.members[0]._base_inventory == packed(["Map"]) and g.wagon.stash.items[0].name == "Rope"


def test_the_wagon_refuses_more_than_it_can_carry():
    scr, g = _gear(_animal(tack=HARNESS), wagon=True, carried=["Iron Bar"] * 9)    # 45 kg vs 40 free
    scr.selected = [(g.members[0], 0)]
    scr._give_many(g.wagon, "pack")
    assert g.wagon.stash.items == [] and g.members[0].count_of("Iron Bar") == 9
    assert "won't fit" in scr.notice and scr.selected


def test_an_unharnessed_wagon_says_why_it_is_shut():
    scr, g = _gear(_animal(tack=PACK_SADDLE), wagon=True, carried=["Rope"])
    scr.selected = [(g.members[0], 0)]
    scr._give_many(g.wagon, "pack")
    assert g.wagon.stash.items == [] and "harnessed" in scr.notice


def test_an_unsaddled_animal_says_why_it_takes_nothing():
    scr, g = _gear(_animal(), carried=["Rope"])
    scr.selected = [(g.members[0], 0)]
    scr._give_many(g.animals[0], "pack")
    assert g.animals[0].stash.items == [] and "pack saddle" in scr.notice


def test_a_saddled_animal_takes_cargo_up_to_its_limit():
    scr, g = _gear(_animal(tack=PACK_SADDLE), carried=["Rope", "Iron Bar"])
    scr.selected = [(g.members[0], 0)]
    scr._give_many(g.animals[0], "pack")
    assert g.animals[0].stash.items[0].name == "Rope"


def test_cargo_comes_out_of_the_wagon_into_a_member_pack():
    scr, g = _gear(_animal(tack=HARNESS), wagon=True, cargo=["Rope"])
    scr.selected = [(g.wagon, 0)]
    scr._give_many(g.members[1], "pack")
    assert g.wagon.stash.items == [] and g.members[1].count_of("Rope") == 1


def test_dropping_a_saddle_on_an_animal_fits_it_and_returns_what_it_wore():
    scr, g = _gear(_animal(tack=HARNESS), carried=[PACK_SADDLE])
    scr.selected = [(g.members[0], 0)]
    scr._give_many(g.animals[0], "tack")
    assert g.animals[0].tack == PACK_SADDLE
    assert g.members[0].count_of(HARNESS) == 1 and g.members[0].count_of(PACK_SADDLE) == 0


def test_an_animal_refuses_things_that_are_not_tack():
    scr, g = _gear(_animal(), carried=["Rope"])
    scr.selected = [(g.members[0], 0)]
    scr._give_many(g.animals[0], "tack")
    assert g.animals[0].tack is None and g.members[0].count_of("Rope") == 1


def test_tack_can_be_taken_off_by_dragging_it_to_a_pack():
    scr, g = _gear(_animal(tack=PACK_SADDLE))
    scr.selected = [(g.animals[0], "tack")]
    scr._give_many(g.members[0], "pack")
    assert g.animals[0].tack is None and g.members[0].count_of(PACK_SADDLE) == 1


def test_the_gear_screen_draws_animal_and_wagon_columns_and_their_cargo_rows():
    scr, g = _gear(_animal(tack=PACK_SADDLE, cargo=["Rope"]), wagon=True, cargo=["Rope"])
    _draw(scr)
    owners = {id(o) for _, o, zone in scr.zones if zone == "pack"}
    assert id(g.wagon) in owners and id(g.animals[0]) in owners
    assert any(o is g.animals[0] and zone == "tack" for _, o, zone in scr.zones)
    scr.view = "cargo"
    _draw(scr)
    assert any(o is g.wagon for _, o, _loc in scr.sources)
    assert any(o is g.animals[0] for _, o, _loc in scr.sources)


def test_the_send_to_menu_offers_the_stores_but_no_member_only_actions_on_their_cargo():
    scr, g = _gear(_animal(tack=PACK_SADDLE), wagon=True, carried=["Rope"], cargo=["Minor Healing Potion"])
    scr._open_menu((10, 10), picks=[(g.members[0], 0)])
    labels = [r[1] for r in scr.menu["rows"]]
    assert "to Wagon" in labels and "to Donkey" in labels
    scr._open_menu((10, 10), picks=[(g.wagon, 0)])
    assert not any(r[0] == "drink" for r in scr.menu["rows"])


def test_a_stack_in_the_wagon_can_be_split():
    _, g = _gear(_animal(tack=HARNESS), wagon=True, cargo=["Rope", "Rope", "Rope"])
    assert g.wagon.split_pack(0, 1) and [it.qty for it in g.wagon.stash.items] == [2, 1]
