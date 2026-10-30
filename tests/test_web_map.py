"""The campaign map in the browser: its orders, its clock and the screens it opens, through the same
session the server routes to."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from gartok import justice, orders, persist, recorder, world
from gartok.animals import Animal
from gartok.group import CAUTIOUS, Group
from gartok.guild import Guild
from gartok.unit import Unit
from gartok.wagon import Wagon
from gartok.web.hub_session import HubSession
from gartok.web.map_session import MapSession
from gartok.web.server import Game, serve
from tests.helpers import standard_unit


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


def _broken_cart(guild):
    g = guild.groups[0]
    cart, ox = Wagon("Cart"), Animal("Ox")
    cart.give_to_pack("Lumber", 3)
    g.add_wagon(cart)
    g.herd.append(ox)
    cart.hp = 0
    return g, cart, ox


def test_a_broken_wagon_is_left_behind_only_after_the_card_says_what_goes_with_it():
    guild = _guild("lumber_yard", "lumber_yard")
    s = _game(guild).session
    g, cart, ox = _broken_cart(guild)
    p = s.preview(g.gid, "market")
    assert "why" not in p and p["path"]
    (w,) = p["leave"]["wagons"]
    assert w["name"] == "Cart" and w["items"] == 3 and w["kg"] == round(cart.stash.load, 1)
    assert w["cargo"] == ["3 Lumber"] and p["leave"]["animals"] == [ox.name]
    with pytest.raises(ValueError, match="leave it behind"):
        s.travel(g.gid, "market")
    assert g.order is None and cart in g.wagons
    st = s.travel(g.gid, "market", leave=True)
    assert g.wagons == [] and ox in g.herd and ox.hitch is None
    assert g.order.kind == "travel" and g.order.final_dest == "market"
    assert any("leaves its broken cart behind" in n for n in st["notices"])


def test_a_sound_wagon_is_never_left_and_its_team_is_not_named_as_walking():
    guild = _guild("lumber_yard", "lumber_yard")
    s = _game(guild).session
    g, _, ox = _broken_cart(guild)
    sound, horse = Wagon("Cart"), Animal("Horse")
    horse.tack = "Harness"
    g.add_wagon(sound)
    g.herd.append(horse)
    assert g.hitch(horse, sound)
    assert s.preview(g.gid, "market")["leave"]["animals"] == [ox.name]
    s.travel(g.gid, "market", leave=True)
    assert g.wagons == [sound] and horse.hitch == sound.uid


def test_with_no_road_the_wagon_is_kept(monkeypatch):
    guild = _guild("lumber_yard", "lumber_yard")
    s = _game(guild).session
    g, cart, _ = _broken_cart(guild)
    monkeypatch.setattr(world, "route", lambda a, b: ([], float("inf")))
    with pytest.raises(ValueError, match="no road"):
        s.travel(g.gid, "market", leave=True)
    assert cart in g.wagons


def test_entering_a_place_opens_its_screen_and_coming_back_changes_nothing(saves):
    guild = _guild("city")
    game = _game(guild)
    m = game.session
    g = guild.groups[0]
    t0 = guild.clock.seconds
    assert m.act(g.gid, "bank") == {"screen": "hub"}
    assert isinstance(game.session, HubSession)
    assert game.session.state()["tab"] == "vault" and g.node == "city"
    st = game.session.map.back()
    assert st["screen"] == "map" and game.session is m and guild.clock.seconds == t0


def test_an_order_whose_screen_falls_due_on_the_clock_opens_it():
    guild = _guild("city")
    game = _game(guild)
    g = guild.groups[0]
    g.order = orders.interactive("bank")
    game.session._advance()
    st = game.session._land()
    assert st == {"screen": "hub"} and game.session.order.kind == "bank"
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
        assert post("/api/map/act", {"gid": gid, "key": "bank"}) == {"screen": "hub"}
        assert json.loads(urllib.request.urlopen(url + "/api/screen").read())["screen"] == "hub"
        with pytest.raises(urllib.error.HTTPError) as e:
            post("/api/map/travel", {"gid": gid, "node": "market"})
        assert e.value.code == 409
        assert post("/api/hub/back", {})["screen"] == "map"
        st = post("/api/map/travel", {"gid": gid, "node": "market"})
        assert st["screen"] == "map" and st["groups"][0]["node"] == "market"
        with pytest.raises(urllib.error.HTTPError) as e:
            post("/api/map/travel", {"gid": gid, "node": "market"})
        assert e.value.code == 409
    finally:
        srv.shutdown()
        srv.server_close()


def _hurt_band(node="country_roads", potatoes=6, hp_lost=8, n=2):
    units = [standard_unit() for _ in range(n)]
    for u in units:
        u.hp = max(1, u.hp_max - hp_lost)
        u.give_to_pack("Potato", potatoes)
    guild = Guild(None, groups=[Group(units, node=node, leader=units[0])], name="Ink Hands")
    return guild, guild.groups[0]


def _rest_rows(guild, g):
    ins = _game(guild).session.state()["groups"][0]["inspector"]
    return {r["key"]: r for r in ins["camp"]["rest"]}


def test_the_rest_rows_count_the_meals_the_hours_cost():
    guild, g = _hurt_band()
    rows = _rest_rows(guild, g)
    assert rows["rest:1"]["sub"] == "no meal" and rows["rest:8"]["sub"] == "no meal"
    full = rows["rest:full"]
    assert full["label"] == "Until full" and full["sub"].endswith("4 meals") and full["tip"] is None


def test_a_rest_the_rations_cannot_carry_to_full_health_stops_at_the_floor_and_says_how_short():
    guild, g = _hurt_band(potatoes=1, hp_lost=30)
    full = _rest_rows(guild, g)["rest:full"]
    assert full["label"] == "To the floor" and full["sub"].endswith("no meal")
    assert full["tip"] == "rations run out 2 days short of full health"
    guild, g = _hurt_band(potatoes=2, hp_lost=40)
    full = _rest_rows(guild, g)["rest:full"]
    assert full["sub"].endswith("2 meals") and full["tip"] == "rations run out 1 day short of full health"


def test_nobody_hurt_has_no_rest_to_the_end():
    guild, g = _hurt_band(hp_lost=0)
    full = _rest_rows(guild, g)["rest:full"]
    assert not full["enabled"] and full["sub"] == "nobody is hurt"


def test_a_trip_cancelled_on_the_road_ends_at_the_next_node_not_the_far_one():
    guild = _guild("city", "city")
    s = _game(guild).session
    a, b = guild.groups
    s.travel(a.gid, "battlefield")
    path, _ = world.route("city", "battlefield")
    assert len(path) > 2
    s.act(a.gid, "cancel_trip")
    b.order = orders.rest(48)
    s._advance()
    assert a.node == path[1] and not a.busy


def test_hours_spent_off_the_map_run_the_other_bands_and_leave_what_falls_due_waiting():
    guild = _guild("city", "market")
    s = _game(guild).session
    a, b = guild.groups
    a.order = orders.rest(8)
    t0 = guild.clock.seconds
    events, dead = s.tick_outside(3, busy=b.members)
    assert guild.clock.seconds - t0 == 3 * 3600 and dead == []
    assert 4.9 < a.order.remaining < 5.1 and not s.pending

    c = guild.groups[0]
    c.order = orders.interactive("bank")
    c.order.remaining = 1
    s.tick_outside(2, busy=b.members)
    assert [(g, o.kind) for g, o in s.pending] == [(c, "bank")]


def test_two_due_screens_open_one_at_a_time_and_the_map_comes_back_after_the_last():
    guild = _guild("city", "market")
    a, b = guild.groups
    a.order, b.order = orders.interactive("bank"), orders.interactive("market")
    game = _game(guild)
    s = game.session
    s.pending = [(a, a.order), (b, b.order)]
    assert s._land() == {"screen": "hub"} and game.session.order.kind == "bank"
    assert s.pending and s.pending[0][1].kind == "market"
    a.order = orders.idle()
    assert s.back() == {"screen": "map", **s.state()} and s.turn["gid"] == b.gid
    assert s.go_on() == {"screen": "hub"} and game.session.order.kind == "market"
    assert not s.pending
    b.order = orders.idle()
    assert s.back()["screen"] == "map"


def test_the_clock_handing_the_screen_to_another_band_puts_up_the_hand_over_card():
    guild = _guild("city", "market")
    a, b = guild.groups
    a.order = orders.interactive("bank")
    b.order = orders.interactive("market")
    game = _game(guild)
    s = game.session
    s.pending = [(a, a.order), (b, b.order)]
    assert s._land() == {"screen": "hub"}                   # nothing was in view yet: no card for the first
    a.order = orders.idle()
    s.back()
    card = s.state()["turn"]
    assert card["name"] == b.display_name and card["node"] == world.node("market").name
    assert card["band"] == "Band 2 of 2 · its turn" and card["action"] == s._activity_label(b.order)
    assert not card["danger"] and card["members"] == [u.name for u in b.members]
    assert s.tutorial_key() == "group_turn"
    assert s.go_on()["screen"] == "hub"
    assert s.state()["turn"] is None and s.tutorial_key() == "map"
    with pytest.raises(ValueError):
        s.go_on()


def test_an_ambushed_band_handed_the_screen_gets_a_danger_card_and_a_lone_band_none():
    guild = _guild("city", "road")
    a, b = guild.groups
    s = _game(guild).session
    s.seen = a.gid
    b.pending = orders.Order("ambush", pack=(standard_unit(),))
    s.focus = b.gid
    s._land()
    card = s.state()["turn"]
    assert card["danger"] and card["action"] == "Ambushed: fight when ready"
    s.go_on()

    solo = _guild("city")
    s = _game(solo).session
    s.seen = solo.groups[0].gid
    s.focus = solo.groups[0].gid
    s._land()
    assert s.state()["turn"] is None


def test_a_guild_with_every_member_jailed_waits_out_the_sentence_and_stands_a_band_up(saves):
    unit = standard_unit()
    unit.crime = 2
    guild = Guild(None, groups=[Group([unit], node="city", leader=unit)], name="Ink Hands")
    justice.jail(guild, unit)
    assert not guild.groups and guild.jailed
    t0 = guild.clock.seconds
    s = _game(guild).session
    (band,) = guild.groups
    assert band.members == [unit] and not guild.jailed and band.node == world.START_NODE
    assert guild.clock.seconds > t0 and not s.wiped
    st = s.state()
    assert [b["gid"] for b in st["groups"]] == [band.gid] and not st["wiped"]


def test_the_landing_after_a_sentence_served_in_play_stands_the_band_up_too(saves):
    a = standard_unit()
    a.crime = 1
    guild = Guild(None, groups=[Group([a], node="city", leader=a)], name="Ink Hands")
    s = _game(guild).session
    justice.jail(guild, a)
    assert not guild.groups
    assert s._land()["screen"] == "map" and len(guild.groups) == 1 and not s.wiped


def _http(srv):
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"

    def post(verb, body=None):
        req = urllib.request.Request(url + verb, data=json.dumps(body or {}).encode(),
                                     headers={"Content-Type": "application/json"})
        return urllib.request.urlopen(req)
    return post


def test_a_save_is_refused_while_a_fight_is_open_and_nothing_is_written(saves):
    guild = _guild("road")
    mute = Unit("Fighter")
    mute.languages = []
    g = guild.groups[0]
    g.pending = orders.Order("ambush", pack=(mute,))
    game = _game(guild, "w1")
    game.session.act(g.gid, "resolve_event")
    assert game.session.screen == "battle"
    before = [x["id"] for x in persist.list_saves("w1")]
    srv = serve(game)
    post = _http(srv)
    try:
        with pytest.raises(urllib.error.HTTPError) as e:
            post("/api/map/save_as", {"name": "mid"})
        assert e.value.code == 409
    finally:
        srv.shutdown()
        srv.server_close()
    assert [x["id"] for x in persist.list_saves("w1")] == before
    assert not any(x["kind"] == "manual" for x in persist.list_saves("w1"))


def test_a_save_is_refused_while_a_hunt_is_open(saves):
    from gartok.web.hunt_session import open_hunt
    guild = _guild("country_roads")
    g = guild.groups[0]
    game = _game(guild, "w1")
    open_hunt(game.session, g, "meat")
    assert game.session.screen == "hunt"
    srv = serve(game)
    post = _http(srv)
    try:
        with pytest.raises(urllib.error.HTTPError) as e:
            post("/api/map/save_as", {"name": "mid"})
        assert e.value.code == 409
    finally:
        srv.shutdown()
        srv.server_close()
    assert not any(x["kind"] == "manual" for x in persist.list_saves("w1"))
