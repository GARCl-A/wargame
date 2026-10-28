"""The searches' finds in the browser: the Ancient Ruins, the Serpent's Nest and the Dragon's Lair, each behind
the wagon's watch, fought as a campaign fight and settled as pygame settles them."""

import json
import threading
import urllib.request

import pytest

from gartok import missions, persist, recorder, serpent_nest, wagon_watch
from gartok.group import Group
from gartok.guild import Guild
from gartok.lair import LairScenario
from gartok.scenario import AncientRuinsScenario, _ruins_keys
from gartok.serpent_nest import NestScenario
from gartok.wagon import Wagon
from gartok.web.battle_session import BattleSession
from gartok.web.map_session import MapSession
from gartok.web.report_session import ReportSession
from gartok.web.server import Game, serve
from gartok.web.watch_session import WatchSession
from tests.helpers import standard_unit


@pytest.fixture(autouse=True)
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    yield tmp_path
    recorder.detach()


def _guild(node, n=3, wagon=False):
    units = [standard_unit() for _ in range(n)]
    for i, u in enumerate(units):
        u.name = f"Delver {i}"
    g = Group(units, node=node, leader=units[0])
    if wagon:
        g.add_wagon(Wagon())
    guild = Guild(None, groups=[g], name="Ink Hands")
    guild.reveal_node(node)
    return guild, g


def _end(game, won=True):
    b = game.session.battle
    for c in (b.foe_units if won else b.player_units):
        c.hp, c.status = 0, "dead"
    b.winner = "player" if won else "enemy"
    game.session.done()
    report = game.session
    assert isinstance(report, ReportSession)
    while game.session is report:
        report.next()


@pytest.mark.parametrize("key, scenario", [("ancient_ruins", AncientRuinsScenario),
                                           ("serpents_nest", NestScenario),
                                           ("dragon_lair", LairScenario)])
def test_a_band_with_no_wagon_goes_straight_in_the_dark(key, scenario, saves):
    guild, g = _guild(key)
    game = Game(MapSession(guild, "w1"))
    assert game.session.act(g.gid, key) == {"screen": "battle"}
    s = game.session
    assert isinstance(s, BattleSession) and isinstance(s.battle.scenario, scenario)
    assert not s.battle.daylight and s.battle.aggressor == "player"
    assert {c.char for c in s.battle.player_units} == set(g.members)
    assert s.state()["campaign"] and s.state()["meta"]["sub"].startswith("Into the")
    assert any(x["kind"] == "auto" for x in persist.list_saves("w1"))


def test_the_wagon_needs_a_watch_and_the_guards_stay_out_of_the_fight():
    guild, g = _guild("serpents_nest", wagon=True)
    game = Game(MapSession(guild))
    assert game.session.act(g.gid, "serpents_nest") == {"screen": "watch"}
    s = game.session
    assert isinstance(s, WatchSession)
    st = s.state()
    assert st["label"] == "Enter the nest" and st["lead"] and not st["watch"]["guarded"]
    a, b, c = g.members
    s.toggle(a.uid)
    s.toggle(b.uid)
    with pytest.raises(ValueError):
        s.toggle(c.uid)
    assert s.state()["watch"]["guarded"] and s.state()["watch"]["outside"] == 2
    assert s.go() == {"screen": "battle"}
    assert [x.char for x in game.session.battle.player_units] == [c]


def test_back_from_the_watch_changes_nothing():
    guild, g = _guild("dragon_lair", wagon=True)
    game = Game(MapSession(guild))
    t0 = guild.clock.seconds
    game.session.act(g.gid, "dragon_lair")
    assert game.session.leave()["screen"] == "map" and g.wagons and guild.clock.seconds == t0


def test_an_unguarded_wagon_may_be_gone_when_the_party_comes_out(monkeypatch):
    monkeypatch.setattr(wagon_watch, "risk", lambda group, node: 1.0)
    guild, g = _guild("ancient_ruins", wagon=True)
    game = Game(MapSession(guild))
    game.session.act(g.gid, "ancient_ruins")
    game.session.go()
    _end(game)
    assert game.session.screen == "map" and not g.wagons


def test_a_guarded_wagon_is_kept(monkeypatch):
    monkeypatch.setattr(wagon_watch, "risk", lambda group, node: 1.0)
    guild, g = _guild("ancient_ruins", wagon=True)
    game = Game(MapSession(guild))
    game.session.act(g.gid, "ancient_ruins")
    game.session.toggle(g.members[0].uid)
    game.session.go()
    _end(game)
    assert g.wagons


def test_the_ruins_remember_the_foes_slain_and_once_empty_lie_silent():
    guild, g = _guild("ancient_ruins")
    game = Game(MapSession(guild))
    game.session.act(g.gid, "ancient_ruins")
    _end(game)
    assert guild.ruins_cleared
    guild.ruins_cleared |= _ruins_keys()
    st = game.session.act(g.gid, "ancient_ruins")
    assert st["screen"] == "map" and any("lie silent" in n for n in st["notices"])


def test_the_nest_wants_the_snake_dragon_alive_for_the_nature_coven():
    guild, g = _guild("serpents_nest")
    missions.accept(guild, g.members[0], missions.NATURE_SNAKE)
    game = Game(MapSession(guild))
    game.session.act(g.gid, "serpents_nest")
    b = game.session.battle
    assert b.wanted_alive == {serpent_nest.dragon_of(b)}


def test_a_wiped_delve_ends_the_campaign():
    guild, g = _guild("dragon_lair", n=1)
    game = Game(MapSession(guild))
    game.session.act(g.gid, "dragon_lair")
    _end(game, won=False)
    assert game.session.wiped


def test_the_server_routes_the_watch_verbs(saves):
    guild, _ = _guild("ancient_ruins", wagon=True)
    persist.save_game("w1", guild)
    srv = serve(Game.from_save("w1"))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"

    def post(verb, body):
        req = urllib.request.Request(url + verb, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    try:
        gid = json.loads(urllib.request.urlopen(url + "/api/map/state").read())["groups"][0]["gid"]
        assert post("/api/map/act", {"gid": gid, "key": "ancient_ruins"}) == {"screen": "watch"}
        st = json.loads(urllib.request.urlopen(url + "/api/watch/state").read())
        assert st["watch"]["going"] == 3
        assert post("/api/watch/watch", {"uid": st["watch"]["members"][0]["uid"]})["watch"]["guarded"]
        assert post("/api/watch/go", {}) == {"screen": "battle"}
    finally:
        srv.shutdown()
