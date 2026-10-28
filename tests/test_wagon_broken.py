"""A wagon cannot die: the road wears it down to 0 HP and it breaks. A broken wagon
draws nothing and carries nothing until it is mended (Lumber, an hour, an INT check)
or left behind; its animals stay in the group."""

from gartok import campaign, orders, persist
from gartok.animals import HARNESS, Animal
from gartok.group import Group
from gartok.guild import Guild
from gartok.wagon import REPAIR_DC, WEAR_DISTANCE, Wagon, repairer
from tests.helpers import Unit, fixed_d20, packed


def _unit(lumber=0, intelligence=10):
    u = Unit("player")
    u.size = "Huge"
    u.intelligence = intelligence
    u._derive_combat()
    u._base_inventory = packed(["Lumber"] * lumber)
    return u


def _setup(kind="Cart", lumber=3, members=1):
    horse = Animal("Donkey", tack=HARNESS)
    wagon = Wagon(kind)
    group = Group([_unit(lumber) for _ in range(members)], node="city", wagons=[wagon], herd=[horse])
    group.hitch_idle()
    return Guild(None, groups=[group]), group, wagon, horse


def test_wear_costs_one_hp_per_hundred_distance():
    wagon = Wagon("Cart")
    assert wagon.wear(WEAR_DISTANCE - 1) == 0 and wagon.hp == 5
    assert wagon.wear(1) == 1 and wagon.hp == 4
    assert wagon.travelled == 0


def test_wear_carries_the_remainder_over():
    wagon = Wagon("Cart")
    wagon.wear(60)
    wagon.wear(60)
    assert wagon.hp == 4 and wagon.travelled == 20


def test_a_wagon_breaks_at_zero_and_never_goes_below():
    wagon = Wagon("Cart")
    wagon.wear(WEAR_DISTANCE * 50)
    assert wagon.hp == 0 and wagon.broken
    assert wagon.wear(WEAR_DISTANCE) == 0 and wagon.hp == 0


def test_a_broken_wagon_draws_nothing_and_carries_nothing():
    _, group, wagon, horse = _setup()
    assert wagon.capacity > 0 and wagon.speed is not None
    wagon.hp = 0
    assert wagon.draft == [] and wagon.budget == 0 and wagon.capacity == 0
    assert wagon.speed is None and wagon.free_slots == 0
    assert group.pulling(horse) is None


def test_a_wagon_breaking_frees_its_animals_but_keeps_them_in_the_group():
    _, group, wagon, horse = _setup()
    wagon.hp = 1
    events = group.wear_wagons(WEAR_DISTANCE)
    assert wagon.broken and horse in group.herd and horse.hitch is None
    assert wagon in group.wagons and "breaks down" in events[0]
    group.hitch_idle()
    assert horse.hitch is None


def test_the_travel_order_wears_the_wagon_by_the_edges_it_crosses():
    guild, group, wagon, _ = _setup()
    wagon.travelled = WEAR_DISTANCE - 1
    group.order = orders.travel(group, "lumber_yard")
    campaign.advance(guild)
    assert group.node == "lumber_yard" and wagon.hp == 4


def test_a_wagon_that_breaks_on_the_road_says_so():
    guild, group, wagon, _ = _setup()
    wagon.hp, wagon.travelled = 1, WEAR_DISTANCE - 1
    group.order = orders.travel(group, "lumber_yard")
    result = campaign.advance(guild)
    assert wagon.broken and any("breaks down" in e for e in result.events)


def test_the_distance_wears_every_leg_of_a_route():
    guild, group, wagon, _ = _setup("Carriage")
    group.node = "lumber_yard"
    wagon.travelled = WEAR_DISTANCE - 1
    group.order = orders.travel(group, "market")
    campaign.advance(guild)
    assert group.node == "city" and wagon.hp == 12 and wagon.travelled == 0
    campaign.advance(guild)
    assert group.node == "market" and wagon.hp == 12 and wagon.travelled == 1


def test_the_repairer_is_whoever_has_the_best_intelligence():
    smart, dull = _unit(intelligence=18), _unit(intelligence=8)
    assert repairer([dull, smart]) is smart


def test_repair_costs_one_lumber_per_hit_die_and_an_hour():
    guild, group, wagon, _ = _setup("Carriage", lumber=5)
    wagon.hp = 1
    start = guild.clock.hour_of_day
    with fixed_d20(20):
        ok, _events, _ = guild.repair_wagon(group.members, wagon)
    assert ok and wagon.hp == 1 + 7
    assert group.members[0].count_of("Lumber") == 2
    assert guild.clock.hour_of_day == (start + 1) % 24


def test_repair_heals_half_the_maximum_rounded_up_and_stops_at_full():
    guild, group, wagon, _ = _setup("Cart", lumber=3)
    wagon.hp = 0
    with fixed_d20(20):
        guild.repair_wagon(group.members, wagon)
        assert wagon.hp == 3 and not wagon.broken
        guild.repair_wagon(group.members, wagon)
    assert wagon.hp == 5


def test_a_failed_repair_still_spends_the_lumber():
    guild, group, wagon, _ = _setup("Cart", lumber=2)
    wagon.hp = 2
    with fixed_d20(1):
        ok, events, _ = guild.repair_wagon(group.members, wagon)
    assert not ok and wagon.hp == 2
    assert group.members[0].count_of("Lumber") == 1
    assert f"DC {REPAIR_DC}" in events[0]


def test_repair_without_the_lumber_does_nothing():
    guild, group, wagon, _ = _setup("Carriage", lumber=2)
    wagon.hp = 0
    with fixed_d20(20):
        ok, events, _ = guild.repair_wagon(group.members, wagon)
    assert not ok and wagon.broken and group.members[0].count_of("Lumber") == 2
    assert "3 Lumber" in events[0]


def test_the_lumber_may_be_spread_across_the_crew():
    guild, group, wagon, _ = _setup("Carriage", lumber=2, members=2)
    wagon.hp = 0
    group.members[1]._base_inventory = packed(["Lumber"])
    with fixed_d20(20):
        ok, _, _ = guild.repair_wagon(group.members, wagon)
    assert ok and sum(u.count_of("Lumber") for u in group.members) == 0


def test_a_full_wagon_needs_no_repair_and_keeps_the_lumber():
    guild, group, wagon, _ = _setup("Cart", lumber=2)
    ok, events, _ = guild.repair_wagon(group.members, wagon)
    assert not ok and group.members[0].count_of("Lumber") == 2 and "no repair" in events[0]


def test_a_repaired_wagon_takes_its_animals_back():
    guild, group, wagon, horse = _setup("Cart", lumber=1)
    wagon.hp = 1
    group.wear_wagons(WEAR_DISTANCE)
    assert horse.hitch is None
    with fixed_d20(20):
        guild.repair_wagon(group.members, wagon)
    group.hitch_idle()
    assert horse.hitch == wagon.uid and wagon.speed is not None


def test_abandoning_drops_the_wagon_and_its_cargo_but_not_the_animals():
    guild, group, wagon, horse = _setup()
    wagon.stash.put("Lumber")
    assert guild.abandon_wagon(group, wagon)
    assert group.wagons == [] and horse in group.herd and horse.hitch is None
    assert not guild.abandon_wagon(group, wagon)


def test_a_broken_wagon_keeps_its_garage_bay_and_can_be_mended_there():
    guild, group, wagon, _ = _setup()
    guild.house.garage.tier = 1
    wagon.hp = 0
    assert guild.park_wagon(group, wagon)
    assert guild.house.garage.wagon_room == 0 and wagon.broken
    assert guild.take_wagon(group, wagon) and wagon.broken


def test_wear_and_hp_survive_a_save():
    _, _group, wagon, _ = _setup("Carriage")
    wagon.hp, wagon.travelled = 4, 42.5
    back = persist.wagon_from_dict(persist.wagon_to_dict(wagon))
    assert (back.hp, back.travelled, back.kind) == (4, 42.5, "Carriage")


def test_a_broken_save_stays_broken():
    wagon = Wagon("Cart", hp=0, travelled=10)
    assert persist.wagon_from_dict(persist.wagon_to_dict(wagon)).broken


# --------------------------------------------------------------------------- #
# screens                                                                      #
# --------------------------------------------------------------------------- #

def _draw(scr, size=(1280, 800)):
    import pygame
    pygame.init()
    scr.mouse = (0, 0)
    scr.draw(pygame.Surface(size))
    return {k for k, _ in scr.buttons}


def test_the_group_screen_shows_the_wagon_hp_and_repairs_it():
    from gartok.group_screen import GroupScreen
    guild, group, wagon, horse = _setup("Cart", lumber=1)
    wagon.hp = 0
    group.wear_wagons(0)
    scr = GroupScreen(None, guild, group, on_back=lambda: None)
    scr.pinned = list(group.members)
    keys = _draw(scr)
    assert f"repair:{wagon.uid}" in keys
    with fixed_d20(20):
        scr._handle_button(f"repair:{wagon.uid}")
    assert wagon.hp == 3 and group.pulling(horse) is wagon
    assert f"repair:{wagon.uid}" not in _draw(scr)         # the one Lumber is spent


def test_the_group_screen_hides_repair_on_a_sound_wagon():
    from gartok.group_screen import GroupScreen
    guild, group, wagon, _ = _setup("Cart", lumber=1)
    scr = GroupScreen(None, guild, group, on_back=lambda: None)
    scr.pinned = list(group.members)
    assert f"repair:{wagon.uid}" not in _draw(scr)


# --------------------------------------------------------------------------- #
# the hour of a repair goes through the world's clock                           #
# --------------------------------------------------------------------------- #

def test_the_repair_hour_runs_through_the_tick_it_is_given():
    guild, group, wagon, _ = _setup("Cart", lumber=1)
    wagon.hp = 1
    seen = []

    def tick(hours, busy=()):
        seen.append((hours, list(busy)))
        return ["a quiet hour."], []

    with fixed_d20(20):
        ok, events, _ = guild.repair_wagon(group.members, wagon, tick)
    assert ok and seen == [(1, group.members)] and "a quiet hour." in events


def test_someone_who_starves_during_the_repair_is_reported():
    guild, group, wagon, _ = _setup("Cart", lumber=1)
    wagon.hp = 1
    victim = group.members[0]
    with fixed_d20(20):
        ok, events, dead = guild.repair_wagon(group.members, wagon, lambda hours, busy=(): ([], [victim]))
    assert ok and dead == [victim] and f"{victim.name} starved to death." in events


def test_a_refused_repair_does_not_run_the_clock():
    guild, group, wagon, _ = _setup("Carriage", lumber=1)
    wagon.hp = 1
    ticks = []
    ok, _events, _ = guild.repair_wagon(group.members, wagon, lambda *a, **k: ticks.append(a) or ([], []))
    assert not ok and ticks == [] and group.members[0].count_of("Lumber") == 1
