"""The hunt in the browser: who minds the wagon, the quarry and the shift, a stretch on the clock, an ambush
fought on the board and back to the hunt, the haul, the ox's trail by daylight, and the routing."""

import json
import threading
import urllib.request

import pytest

from gartok import hunt, missions, orders, ox, persist, recorder, wagon_watch
from gartok.clock import Clock
from gartok.group import Group
from gartok.guild import Guild
from gartok.wagon import Wagon
from gartok.web.battle_session import BattleSession
from gartok.web.hunt_session import HuntSession
from gartok.web.map_session import MapSession
from gartok.web.report_session import ReportSession
from gartok.web.server import Game, serve
from gartok.web.talent_session import TalentSession
from tests.helpers import standard_unit


@pytest.fixture(autouse=True)
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    yield tmp_path
    recorder.detach()


def _guild(n=3, node="wilds", hour=8):
    units = [standard_unit() for _ in range(n)]
    for i, u in enumerate(units):
        u.name = f"Hunter {i}"
        u.give_to_pack("Potato", 6)
    g = Group(units, node=node, leader=units[0])
    guild = Guild(None, groups=[g], name="Ink Hands")
    guild.clock = Clock(hour * 3600)
    return guild, g


def _hunt(guild, g, key="hunt", world_id=None):
    game = Game(MapSession(guild, world_id))
    assert game.session.act(g.gid, key) == {"screen": "hunt"}
    return game, game.session


def _ambush_on(s):
    s.state_.ambush_mult = 1000.0


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


def test_a_band_with_no_wagon_opens_on_the_quarry_and_the_shift():
    guild, g = _guild()
    _, s = _hunt(guild, g)
    st = s.state()
    assert st["phase"] == "setup" and st["title"] == "The Wilds"
    assert [t["id"] for t in st["setup"]["targets"]] == ["meat", "shrooms"]
    assert [x["hours"] for x in st["setup"]["shifts"]] == list(hunt.HUNT_SHIFT_HOURS)
    assert s.set_target("shrooms")["setup"]["targets"][1]["on"]
    assert s.set_hours(16)["setup"]["shifts"][-1]["on"]
    with pytest.raises(ValueError):
        s.set_hours(5)
    with pytest.raises(ValueError):
        s.set_target("ox")


def test_a_quiet_shift_spends_the_hours_and_banks_the_meat(saves):
    guild, g = _guild()
    persist.save_game("w1", guild)
    game, s = _hunt(guild, g, world_id="w1")
    s.state_.ambush_mult = 0.0
    t0 = guild.clock.seconds
    s.set_hours(8)
    st = s.start()
    assert st["phase"] == "done" and guild.clock.seconds - t0 == 8 * 3600
    assert sum(u.count_of(hunt.MEAT_ITEM) for u in g.members) == s.state_.meat > 0
    assert any("meat" in ln for ln in st["done"]["lines"])
    with pytest.raises(ValueError):
        s.hunt_on()
    assert s.done()["screen"] == "map" and game.session is s.map
    assert s.state_.hours_hunted == 8


def test_an_ambush_goes_to_the_board_and_a_win_comes_back_to_the_hunt(saves):
    guild, g = _guild()
    persist.save_game("w1", guild)
    game, s = _hunt(guild, g, world_id="w1")
    _ambush_on(s)
    s.set_hours(8)
    st = s.start()
    assert st["phase"] == "ambush" and st["ambush"]["foes"] and s.state_.hours_left == 7
    assert s.fight() == {"screen": "battle"}
    assert isinstance(game.session, BattleSession) and game.session.battle.aggressor == "enemy"
    assert any(e["kind"] == "auto" for e in persist.list_saves("w1"))
    _end(game)
    assert game.session is s and s.phase == "interlude" and s.state_.fights == 1
    s.state_.ambush_mult = 0.0
    assert s.hunt_on()["phase"] == "done" and s.state_.hours_hunted == 8


def test_heading_back_after_a_fight_banks_what_there_is():
    guild, g = _guild()
    game, s = _hunt(guild, g)
    _ambush_on(s)
    s.start()
    s.fight()
    _end(game)
    st = s.head_back()
    assert st["phase"] == "done" and "Fought off 1 pack along the way." in st["done"]["lines"]


def test_a_lost_ambush_ends_the_hunt_and_does_not_count():
    guild, g = _guild(n=4)
    game, s = _hunt(guild, g)
    _ambush_on(s)
    s.start()
    s.fight()
    b = game.session.battle
    b.player_units[0].hp, b.player_units[0].status = 0, "dead"
    for c in b.player_units[1:]:
        c.status = "fled"
    b.winner = "enemy"
    game.session.done()
    report = game.session
    while game.session is report:
        report.next()
    assert game.session is s and s.phase == "done" and s.state_.fights == 0


def test_the_wagon_needs_a_watch_and_someone_must_go_in():
    guild, g = _guild()
    g.add_wagon(Wagon())
    _, s = _hunt(guild, g)
    st = s.state()
    assert st["phase"] == "watch" and not st["watch"]["guarded"] and st["watch"]["going"] == 3
    with pytest.raises(ValueError):
        s.start()
    a, b, c = g.members
    s.toggle_watch(a.uid)
    s.toggle_watch(b.uid)
    with pytest.raises(ValueError):
        s.toggle_watch(c.uid)
    assert s.state()["watch"]["guarded"]
    st = s.go()
    assert st["phase"] == "setup" and [m["uid"] for m in st["members"]] == [c.uid]
    assert set(st["guards"]) == {a.name, b.name}


def test_an_unguarded_wagon_may_be_gone_when_the_party_comes_out(monkeypatch):
    guild, g = _guild()
    g.add_wagon(Wagon())
    _, s = _hunt(guild, g)
    s.go()
    s.state_.ambush_mult = 0.0
    monkeypatch.setattr(wagon_watch, "risk", lambda group, node: 1.0)
    s.start()
    s.done()
    assert not g.wagons and not g.herd


def test_a_guarded_wagon_and_a_hunt_never_started_keep_it(monkeypatch):
    monkeypatch.setattr(wagon_watch, "risk", lambda group, node: 1.0)
    guild, g = _guild()
    g.add_wagon(Wagon())
    _, s = _hunt(guild, g)
    s.go()
    assert s.leave()["screen"] == "map" and g.wagons
    _, s = _hunt(guild, g)
    s.toggle_watch(g.members[0].uid)
    s.go()
    s.state_.ambush_mult = 0.0
    s.start()
    s.done()
    assert g.wagons


def _ox_guild(hour=8):
    guild, g = _guild(node="ox_fields", hour=hour)
    missions.accept(guild, g.members[0], missions.TANNER_HIDES).state = "done"
    missions.accept(guild, g.members[0], missions.TANNER_BIWOLF).state = "done"
    missions.accept(guild, g.members[0], missions.TANNER_OX)
    return guild, g


def test_the_ox_is_tracked_by_daylight_only():
    guild, g = _ox_guild(hour=15)
    _, s = _hunt(guild, g, key="ox_hunt")
    st = s.state()
    left = ox.daylight_hours(guild.clock.hour_of_day)
    assert st["title"] == "The Ox Fields" and not st["setup"]["targets"]
    assert [x["hours"] for x in st["setup"]["shifts"]] == [h for h in ox.TRACK_SHIFT_HOURS if h <= left]
    guild2, g2 = _ox_guild(hour=23)
    _, dark = _hunt(guild2, g2, key="ox_hunt")
    assert dark.state()["setup"]["why"]
    with pytest.raises(ValueError):
        dark.start()


def test_a_found_trail_is_the_players_chase_and_his_fall_closes_the_job(monkeypatch):
    guild, g = _ox_guild()
    game, s = _hunt(guild, g, key="ox_hunt")
    monkeypatch.setattr(ox.random, "randint", lambda a, b: 20)
    st = s.start()
    assert st["phase"] == "ambush" and st["ambush"]["title"] == "The trail is fresh!"
    s.fight()
    assert game.session.battle.aggressor == "player"
    _end(game)
    assert s.phase == "done" and missions.pending_ox(guild) is None
    assert "Aurochs, the immortal ox, is dead." in s.map.notices


def test_a_member_with_a_pick_goes_to_the_talents_and_back():
    guild, g = _guild()
    game, s = _hunt(guild, g)
    with pytest.raises(ValueError):
        s.talents(g.members[0].uid)
    u = g.members[0]
    u.combat_xp = 10
    assert s.talents(u.uid) == {"screen": "talents"}
    assert isinstance(game.session, TalentSession)
    assert game.session.back()["screen"] == "hunt" and game.session is s


def test_an_order_that_falls_due_on_the_clock_opens_the_hunt():
    guild, g = _guild()
    game = Game(MapSession(guild))
    g.order = orders.interactive("hunt")
    game.session._advance()
    assert game.session._land()["screen"] == "hunt"
    assert isinstance(game.session, HuntSession)


def test_the_server_routes_the_hunt_verbs(saves):
    guild, _ = _guild()
    persist.save_game("w1", guild)
    srv = serve(Game.from_save("w1"))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"

    def post(verb, body):
        req = urllib.request.Request(url + verb, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    try:
        gid = json.loads(urllib.request.urlopen(url + "/api/map/state").read())["groups"][0]["gid"]
        assert post("/api/map/act", {"gid": gid, "key": "hunt"}) == {"screen": "hunt"}
        assert post("/api/hunt/hours", {"hours": 4})["setup"]["shifts"][0]["on"]
        assert post("/api/hunt/leave", {})["screen"] == "map"
    finally:
        srv.shutdown()
