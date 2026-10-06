"""A wagon left outside: the squad selector for the Ancient Ruins and a Wilds hunt,
the risk it shows, and the one silent roll when the party comes back out."""

import pygame

from gartok import data, wagon_watch, world
from gartok.animals import Animal
from gartok.group import Group
from gartok.ui.tokens import fonts as ui_fonts
from gartok.wagon import Wagon
from gartok.watch_screen import WatchScreen
from tests.helpers import Unit


class _Roll:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


def _group(species=("Donkey",), members=2, wagons=1):
    g = Group([Unit("player") for _ in range(members)], node="ancient_ruins",
              wagons=[Wagon() for _ in range(wagons)], herd=[Animal(s) for s in species])
    return g


def _screen(g, node="ancient_ruins", calls=None):
    calls = calls if calls is not None else []
    return WatchScreen(ui_fonts(), g, world.node(node), "GO",
                       on_confirm=lambda party, guarded: calls.append((party, guarded)),
                       on_back=lambda: calls.append("back"))


def _keys(scr):
    pygame.init()
    scr.mouse = (0, 0)
    scr.draw(pygame.Surface((1280, 800)))
    return {k for k, _ in scr.buttons}


def test_flight_chances_live_in_the_beast_table():
    assert [data.race_by_name(s)["flight"] for s in ("Donkey", "Horse", "Ox")] == [0.05, 0.10, 0.15]
    assert data.race_by_name("Wolf")["flight"] == 0.0


def test_the_flightiest_animal_sets_the_chance():
    assert wagon_watch.flight_chance(_group(("Donkey", "Ox"))) == 0.15
    assert wagon_watch.flight_chance(_group(())) == 0.0


def test_the_ruins_add_the_old_roads_chance_to_the_animals_and_the_wilds_do_not():
    g = _group(("Horse",))
    assert wagon_watch.risk(g, world.node("ancient_ruins")) == world.ROAD_AMBUSH_CHANCE + 0.10
    assert wagon_watch.risk(g, world.node("wilds")) == 0.10


def test_only_a_group_with_a_wagon_needs_a_watch():
    assert wagon_watch.needs_watch(_group())
    assert not wagon_watch.needs_watch(_group(wagons=0))


def test_an_unguarded_wagon_is_lost_with_its_cargo_and_animals_on_a_hit():
    g = _group(("Ox",))
    g.wagons[0].stash.put("Potato")
    node = world.node("wilds")
    assert wagon_watch.leave_outside(g, node, guarded=False, rng=_Roll(0.14))
    assert g.wagons == [] and g.herd == []


def test_an_unguarded_wagon_survives_a_miss():
    g = _group(("Ox",))
    assert not wagon_watch.leave_outside(g, world.node("wilds"), guarded=False, rng=_Roll(0.15))
    assert len(g.wagons) == 1 and len(g.herd) == 1


def test_a_guarded_wagon_is_never_lost():
    g = _group(("Ox",))
    assert not wagon_watch.leave_outside(g, world.node("ancient_ruins"), guarded=True, rng=_Roll(0.0))
    assert len(g.wagons) == 1


def test_the_screen_starts_with_everyone_going_and_shows_the_risk():
    g = _group()
    scr = _screen(g)
    assert _keys(scr) >= {"toggle:0", "toggle:1", "go", "back"}
    assert scr.party == g.members and scr.guards == []


def test_one_click_leaves_a_member_minding_the_wagon():
    g = _group()
    calls = []
    scr = _screen(g, calls=calls)
    scr._click("toggle:1")
    assert scr.party == [g.members[0]] and scr.guards == [g.members[1]]
    scr._click("go")
    assert calls == [([g.members[0]], True)]


def test_nobody_can_stay_if_that_leaves_no_one_to_go():
    g = _group()
    scr = _screen(g)
    scr._click("toggle:0")
    scr._click("toggle:1")
    assert len(scr.party) == 1
    assert "toggle:1" not in _keys(scr) or "toggle:0" not in _keys(scr)


def test_going_in_alone_with_the_wagon_unguarded_reports_it():
    g = _group(members=1)
    calls = []
    scr = _screen(g, calls=calls)
    scr._click("go")
    assert calls == [([g.members[0]], False)]


def test_the_screen_draws_for_every_species_and_both_places():
    for species in (("Donkey",), ("Ox", "Horse"), ()):
        for node in ("ancient_ruins", "wilds"):
            g = _group(species)
            scr = _screen(g, node)
            _keys(scr)
            scr._click("toggle:0")
            _keys(scr)


def test_back_returns_without_choosing():
    calls = []
    scr = _screen(_group(), calls=calls)
    scr._click("back")
    assert calls == ["back"]


def _app_with_wagon(species="Ox"):
    from gartok.app import App
    from gartok.guild import Guild
    app = App.__new__(App)
    app.world, app.scene, app.ui_fonts = "x", None, ui_fonts()
    app.guild = Guild([Unit("player"), Unit("player")], node="ancient_ruins")
    app._battle_squad, app._battle_node, app._arena_offer = [], None, None
    app._hunt = app._pause_order = app._pause_group = app._claim_stage_pending = None
    app._left_outside = None
    app._map_notices, app._pending, app._pending_event = [], [], None
    app._enter_battle = lambda battle, node: None
    g = app.guild.groups[0]
    g.add_wagon(Wagon())
    g.herd.append(Animal(species))
    return app, g


def test_the_hunt_opens_the_selector_and_only_the_hunters_hunt(monkeypatch):
    app, g = _app_with_wagon()
    app._open_hunt_ground(list(g.members), world.node("wilds"), None, group=g)
    assert isinstance(app.scene, WatchScreen)
    app.scene._click("toggle:0")
    hunters = app.scene.party
    app.scene._click("go")
    assert app._hunt.party == hunters == g.members[1:] and app._left_outside[2] is True
    monkeypatch.setattr("random.random", lambda: 0.0)
    app._end_hunt()
    assert len(g.wagons) == 1 and app._left_outside is None


def test_an_unguarded_hunt_can_lose_the_wagon_and_says_nothing(monkeypatch):
    app, g = _app_with_wagon("Ox")
    app._open_hunt_ground(list(g.members), world.node("wilds"), None, group=g)
    app.scene._click("go")
    notices = list(app._map_notices)
    monkeypatch.setattr("random.random", lambda: 0.0)
    app._end_hunt()
    assert g.wagons == [] and g.herd == [] and app._map_notices == notices


def test_a_group_without_a_wagon_goes_straight_to_the_hunt():
    app, g = _app_with_wagon()
    g.remove_wagon(g.wagons[0])
    app._open_hunt_ground(list(g.members), world.node("wilds"), None, group=g)
    assert not isinstance(app.scene, WatchScreen) and app._left_outside is None


def test_the_ruins_open_the_selector_then_the_battle_with_the_wagon_left_outside():
    app, g = _app_with_wagon()
    app._enter_ancient_ruins(g, world.node("ancient_ruins"))
    assert isinstance(app.scene, WatchScreen)
    app.scene._click("toggle:0")
    app.scene._click("go")
    assert app._battle_squad == g.members[1:]
    assert app._left_outside == (g, world.node("ancient_ruins"), True)
