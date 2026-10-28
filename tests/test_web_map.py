"""The campaign map in the browser: its orders, its clock and the screens it opens, through the same
session the server routes to."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from gartok import orders, persist, recorder, world
from gartok.group import CAUTIOUS, Group
from gartok.guild import Guild
from gartok.unit import Unit
from gartok.web.away_session import AwaySession
from gartok.web.map_session import MapSession
from gartok.web.server import Game, serve


def _guild(*nodes):
    groups = []
    for node in nodes:
        units = [Unit("Fighter") for _ in range(2)]
        for u in units:
            u.give_to_pack("Potato", 6)
        groups.append(Group(units, node=node, leader=units[0]))
    return Guild(None, groups=groups, name="Ink Hands")


@pytest.fixture
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    yield tmp_path
    recorder.detach()


def _game(guild, world_id=None):
    return Game(MapSession(guild, world_id))


def test_the_state_holds_the_known_world_the_bands_and_what_the_picked_one_can_do():
    guild = _guild("lumber_yard")
    st = _game(guild).session.state()
    known = {n.id for n in world.known(guild)}
    assert {n["id"] for n in st["nodes"]} == known
    assert all(a in known and b in known for a, b, _ in st["edges"])
    (band,) = st["groups"]
    assert band["idle"] and band["chip"] == "No orders" and band["members"][0]["lead"]
    ins = band["inspector"]
    assert ins["place"]["name"] == "Lumber Yard" and ins["place"]["stats"][0]["label"] == "A 16 h shift"
    assert any(b["t"] == "button" and b["key"] == "market" for b in ins["blocks"])
    assert [r["key"] for r in ins["camp"]["rest"]] == ["rest:1", "rest:8", "rest:full"]
    assert st["cta"]["key"] == "cycle_idle" and not st["cta"]["enabled"]


def test_the_slip_over_a_place_gives_the_walk_the_order_takes():
    guild = _guild("lumber_yard")
    game = _game(guild)
    g = guild.groups[0]
    p = game.session.preview(g.gid, "market")
    assert p["path"][0] == "lumber_yard" and p["path"][-1] == "market" and p["via"] == ["Ankareth"]
    o = orders.travel(g, "market")
    legs = [o.eta, *(world.hours(next(w for v, w in world.neighbors(a) if v == b), g.speed)
                     for a, b in zip([o.dest, *o.path], o.path))]
    assert p["hours"] == round(sum(legs), 1)
    assert game.session.preview(g.gid, "lumber_yard")["why"]


def test_a_lone_band_sent_on_walks_there_and_the_clock_runs_to_its_arrival(saves):
    guild = _guild("lumber_yard")
    persist.save_game("w", guild)
    game = _game(guild, "w")
    g = guild.groups[0]
    hours = game.session.preview(g.gid, "market")["hours"]
    t0 = guild.clock.seconds
    st = game.session.travel(g.gid, "market")
    assert st["screen"] == "map" and g.node == "market" and not g.busy
    assert abs((guild.clock.seconds - t0) / 3600 - hours) < .1
    assert persist.load_game("w").groups[0].node == "market"


def test_with_another_band_idle_the_clock_waits_for_its_order():
    guild = _guild("city", "city")
    game = _game(guild)
    a, b = guild.groups
    t0 = guild.clock.seconds
    game.session.travel(a.gid, "market")
    assert a.busy and guild.clock.seconds == t0
    st = game.session.act(b.gid, "rest:1")
    assert guild.clock.seconds > t0 and st["focus"] is not None


def test_rest_search_stance_and_the_stops_issue_their_orders():
    guild = _guild("country_roads")
    s = _game(guild).session
    g = guild.groups[0]
    t0 = guild.clock.seconds
    s.act(g.gid, "rest:8")
    assert guild.clock.seconds - t0 == 8 * 3600 and not g.busy
    s.act(g.gid, CAUTIOUS)
    assert g.stance == CAUTIOUS
    t1 = guild.clock.seconds
    s.act(g.gid, "scout_fields")
    assert guild.clock.seconds > t1 and not g.busy

    guild = _guild("city", "city")
    s = _game(guild).session
    a, b = guild.groups
    s.travel(a.gid, "battlefield")
    assert a.order.path
    s.act(a.gid, "cancel_trip")
    assert a.order.path == ()
    b.order = orders.rest(8)
    s.act(b.gid, "stop_rest")
    assert not b.busy


def test_a_busy_band_refuses_a_new_order():
    guild = _guild("city", "city")
    s = _game(guild).session
    a = guild.groups[0]
    s.travel(a.gid, "market")
    with pytest.raises(ValueError):
        s.travel(a.gid, "arena")
    with pytest.raises(ValueError):
        s.act(a.gid, "rest:1")


def test_entering_a_place_opens_its_screen_and_coming_back_changes_nothing(saves):
    guild = _guild("city")
    game = _game(guild)
    m = game.session
    g = guild.groups[0]
    t0 = guild.clock.seconds
    assert m.act(g.gid, "skirmish") == {"screen": "away"}
    assert isinstance(game.session, AwaySession)
    assert game.session.state()["title"] and g.node == "city"
    st = game.session.map.back()
    assert st["screen"] == "map" and game.session is m and guild.clock.seconds == t0


def test_an_order_whose_screen_falls_due_on_the_clock_opens_it():
    guild = _guild("city")
    game = _game(guild)
    g = guild.groups[0]
    g.order = orders.interactive("skirmish")
    game.session._advance()
    st = game.session._land()
    assert st == {"screen": "away"} and game.session.order.kind == "skirmish"
    assert game.session.map.back()["screen"] == "map"


def test_split_and_merge_shuffle_the_bands_where_they_stand():
    guild = _guild("city")
    s = _game(guild).session
    g = guild.groups[0]
    leaving = g.members[1]
    st = s.split(g.gid, [leaving.uid])
    assert len(guild.groups) == 2 and st["focus"] == guild.groups[1].gid
    assert guild.groups[1].members == [leaving]
    (mate,) = next(b for b in st["groups"] if b["gid"] == g.gid)["mates"]
    s.merge(g.gid, mate["gid"])
    assert len(guild.groups) == 1 and leaving in g.members


def test_a_fight_due_stops_the_band_and_the_seal_opens_it_without_settling_it():
    guild = _guild("road", "city")
    a = guild.groups[0]
    mute = Unit("Fighter")
    mute.languages = []                     # nobody to talk to: the seal goes straight to the fight
    a.pending = orders.Order("ambush", pack=(mute,))
    game = _game(guild)
    s = game.session
    st = s.state()
    assert st["focus"] == a.gid and st["cta"]["key"] == "resolve_event" and st["cta"]["gid"] == a.gid
    band = next(x for x in st["groups"] if x["gid"] == a.gid)
    assert band["blocked"] and band["inspector"]["camp"] is None
    with pytest.raises(ValueError):
        s.travel(a.gid, "city")
    with pytest.raises(ValueError):
        s.advance_world()
    assert s.act(a.gid, "resolve_event") == {"screen": "battle"}
    assert game.session.state()["campaign"]
    game.open(s)
    assert a.fight_due


def test_every_band_at_its_post_lets_the_seal_pass_a_whole_day():
    guild = _guild("city")
    g = guild.groups[0]
    g.order = orders.garrison("guard")
    s = _game(guild).session
    assert s.state()["cta"]["key"] == "advance_world"
    t0 = guild.clock.seconds
    s.advance_world()
    assert guild.clock.seconds - t0 == 24 * 3600


def test_the_server_routes_the_map_verbs_and_answers_with_the_screen_open(saves):
    guild = _guild("city")
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
        assert post("/api/map/act", {"gid": gid, "key": "skirmish"}) == {"screen": "away"}
        assert json.loads(urllib.request.urlopen(url + "/api/screen").read())["screen"] == "away"
        with pytest.raises(urllib.error.HTTPError) as e:
            post("/api/map/travel", {"gid": gid, "node": "market"})
        assert e.value.code == 409
        assert post("/api/away/back", {})["screen"] == "map"
        st = post("/api/map/travel", {"gid": gid, "node": "market"})
        assert st["screen"] == "map" and st["groups"][0]["node"] == "market"
        with pytest.raises(urllib.error.HTTPError) as e:
            post("/api/map/travel", {"gid": gid, "node": "market"})
        assert e.value.code == 409
    finally:
        srv.shutdown()
        srv.server_close()
