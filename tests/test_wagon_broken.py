"""A wagon cannot die: the road wears it down to 0 HP and it breaks. A broken wagon
draws nothing and carries nothing until it is mended (Lumber, an hour, an INT check)
or left behind; its animals stay in the group."""

from gartok import campaign, orders, persist
from gartok.animals import HARNESS, Animal
from gartok.group import Group
from gartok.guild import Guild
from gartok.wagon import REPAIR_DC, VEHICLES, WEAR_DISTANCE, Wagon, repairer
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


def test_the_garage_repairs_a_broken_wagon_parked_there():
    from gartok.garage_screen import GarageScreen
    from gartok.ui.tokens import fonts as ui_fonts
    guild, group, wagon, _ = _setup("Cart", lumber=1)
    guild.house.garage.tier = 1
    wagon.hp = 0
    guild.park_wagon(group, wagon)
    scr = GarageScreen(ui_fonts(), guild, group, lambda: None)
    assert "repair_garaged:0" in _draw(scr)
    with fixed_d20(20):
        scr._click("repair_garaged:0")
    assert wagon.hp == 3 and "mends" in scr.notice
    assert "repair_garaged:0" not in _draw(scr)           # the one Lumber is spent


def test_the_garage_withholds_repair_without_lumber_and_for_a_sound_wagon():
    from gartok.garage_screen import GarageScreen
    from gartok.ui.tokens import fonts as ui_fonts
    guild, group, wagon, _ = _setup("Cart", lumber=0)
    scr = GarageScreen(ui_fonts(), guild, group, lambda: None)
    wagon.hp = 1
    assert "repair_group:0" not in _draw(scr)
    group.members[0]._base_inventory = packed(["Lumber"])
    assert "repair_group:0" in _draw(scr)
    wagon.hp = wagon.hp_max
    assert "repair_group:0" not in _draw(scr)


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


def test_the_abandon_card_offers_the_cargo_only_when_there_is_some():
    from gartok.abandon_screen import AbandonScreen
    from gartok.ui.tokens import fonts as ui_fonts
    wagon = Wagon("Cart", hp=0)
    calls = []
    scr = AbandonScreen(ui_fonts(), wagon, lambda: calls.append("manage"),
                        lambda: calls.append("leave"), lambda: calls.append("stay"))
    assert _draw(scr) == {"leave", "stay"}
    wagon.stash.put("Lumber", 2)
    assert _draw(scr) == {"manage", "leave", "stay"}
    for key, rect in scr.buttons:
        scr._click(rect.center)
    assert calls == ["manage", "leave", "stay"]
    assert scr.handle_escape() and calls[-1] == "stay"


def _app(guild):
    """An App with only what the abandon flow touches; returns it and the list that
    records each `_start_map`."""
    from gartok.app import App
    app = App.__new__(App)
    app.guild = guild
    app.scene = None
    app.ui_fonts = None
    app._map_notices = []
    app._pending = []
    app._pending_event = None
    app._save = lambda: None
    started = []
    app._start_map = lambda: started.append(True)
    return app, started


def test_travelling_with_a_broken_wagon_asks_before_leaving_it():
    from gartok.abandon_screen import AbandonScreen
    guild, group, wagon, _horse = _setup()
    wagon.hp = 0
    app, started = _app(guild)
    app._abandon_broken(group, "market")
    assert isinstance(app.scene, AbandonScreen) and group.order is None and wagon in group.wagons
    app.scene.on_stay()
    assert started == [True] and group.order is None and wagon in group.wagons


def test_leaving_the_wagon_drops_it_keeps_the_herd_and_sets_off():
    guild, group, wagon, horse = _setup()
    wagon.hp = 0
    app, started = _app(guild)
    app._abandon_broken(group, "market")
    app.scene.on_leave()
    assert group.wagons == [] and horse in group.herd
    assert group.order is not None and group.order.kind == "travel" and group.order.final_dest == "market"
    assert started == [True] and any("leaves its broken cart" in n for n in app._map_notices)


def test_every_broken_wagon_is_asked_about_in_turn():
    guild, group, wagon, _ = _setup()
    second = Wagon("Carriage", hp=0)
    group.add_wagon(second)
    wagon.hp = 0
    app, _started = _app(guild)
    app._abandon_broken(group, "market")
    first = app.scene.wagon
    app.scene.on_leave()
    assert app.scene.wagon is not first and group.order is None
    app.scene.on_leave()
    assert group.wagons == [] and group.order is not None


def test_a_sound_wagon_travels_without_a_question():
    guild, group, wagon, _ = _setup()
    app, _started = _app(guild)
    app._abandon_broken(group, "market")
    assert wagon in group.wagons and group.order is not None and app.scene is None


def test_managing_the_cargo_lets_the_packs_take_it_and_leaves_the_rest_on_the_wagon():
    from gartok.loot_screen import LootScreen
    guild, group, wagon, _ = _setup(lumber=0)
    wagon.hp = 0
    wagon.stash.put("Lumber", 3)
    app, _started = _app(guild)
    app._abandon_broken(group, "market")
    app.scene.on_manage()
    assert isinstance(app.scene, LootScreen)
    loot = app.scene
    loot.pool[:] = [("Lumber", 1)]                       # the party took two
    loot.on_done()
    assert [(i.name, i.qty) for i in wagon.stash.items] == [("Lumber", 1)]
    assert app.scene.wagon is wagon


def test_the_map_asks_before_a_group_with_a_broken_wagon_sets_out():
    from gartok import world
    from gartok.map_screen import MapScreen
    guild, group, wagon, _ = _setup()
    wagon.hp = 0
    scr = MapScreen.__new__(MapScreen)
    scr.guild, scr.selected, scr._pending_event = guild, group, None
    asked = []
    scr.on_abandon = lambda g, dest: asked.append((g, dest))
    scr.on_advance = lambda: None
    scr._go(world.node("market"))
    assert asked == [(group, "market")] and group.order is None


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


def test_the_world_keeps_pace_with_an_hour_spent_on_a_screen():
    guild, group, _wagon, _ = _setup()
    other = Group([_unit()], node="city")
    guild.groups.append(other)
    other.order = orders.Order("travel", eta=5, remaining=5, dest="lumber_yard")
    app, _ = _app(guild)
    _events, dead = app._tick_outside_map(1, busy=group.members)
    assert dead == [] and other.order.remaining == 4


def test_what_falls_due_during_that_hour_is_queued_for_the_map():
    guild, group, _wagon, _ = _setup()
    other = Group([_unit()], node="city")
    guild.groups.append(other)
    other.order = orders.interactive("market", hours=1)
    app, _ = _app(guild)
    app._tick_outside_map(1, busy=group.members)
    assert [(g, o.kind) for g, o in app._pending] == [(other, "market")]


def test_leaving_the_screen_reports_whoever_starved_there():
    from gartok.alert_screen import AlertScreen
    guild, _group, _wagon, _ = _setup()
    app, _started = _app(guild)
    gone = _unit()
    app._screen_dead = (gone,)
    app.scene = None
    app._after_activity()
    assert isinstance(app.scene, AlertScreen) and app._screen_dead == ()


def test_a_trip_with_no_route_keeps_the_broken_wagon(monkeypatch):
    from gartok import world
    guild, group, wagon, _ = _setup()
    wagon.hp = 0
    monkeypatch.setattr(world, "route", lambda a, b: ([], float("inf")))
    app, started = _app(guild)
    app._abandon_broken(group, "market")
    assert wagon in group.wagons and group.order is None and started == [True]
    assert any("no way" in n.lower() for n in app._map_notices)


def test_the_screen_tick_keeps_the_shape_of_pass_time():
    import inspect

    from gartok.app import App

    def shape(fn):
        return [(p.name, p.default) for p in inspect.signature(fn).parameters.values() if p.name != "self"]

    assert shape(App._tick_outside_map) == shape(Guild.pass_time)
