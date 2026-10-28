"""The title screen in the browser: the menu beside the last guild played, the guilds kept and one
guild's saves; CONTINUE and LOAD open the map on that save, and the map's MENU comes back to it."""

import json
import threading
import urllib.request

import pytest

from gartok import persist, recorder, world
from gartok.group import Group
from gartok.guild import Guild
from gartok.web.map_session import MapSession
from gartok.web.server import Game, serve
from gartok.web.title_session import TitleSession
from tests.helpers import standard_unit


@pytest.fixture
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    yield tmp_path
    recorder.detach()


def _guild(name, *nodes, members=2):
    groups = []
    for node in nodes:
        units = [standard_unit() for _ in range(members)]
        groups.append(Group(units, node=node, leader=units[0]))
    return Guild(None, groups=groups, name=name, vocation="caravan")


def _save(world_id, guild, at):
    """The live save of `world_id`, stamped `at` (the guilds are listed newest first)."""
    persist.save_game(world_id, guild)
    path = persist.save_path(world_id)
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    payload["saved_at"] = at
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)


def _last_manual(world_id):
    return next(s["id"] for s in persist.list_saves(world_id) if s["kind"] == "manual")


def _title():
    return Game.title().session


def test_with_no_guild_the_title_invites_one_and_cannot_continue(saves):
    st = _title().state()
    menu = {m["key"]: m for m in st["menu"] if m}
    assert not menu["continue"]["enabled"] and not menu["load"]["enabled"] and menu["quit"]["enabled"]
    assert st["charter"] is None and st["map"] is None and st["invite"]
    with pytest.raises(ValueError, match="no guild to continue"):
        _title().load(None)


def test_the_last_guild_played_is_the_charter_and_its_known_world_the_map(saves):
    old = _guild("Old Hands", "city")
    _save("old", old, 1000)
    last = _guild("Ink Hands", "lumber_yard", "market", members=3)
    last.roster[0].hp = 1
    _save("ink", last, 2000)
    st = _title().state()
    menu = {m["key"]: m for m in st["menu"] if m}
    assert menu["continue"]["enabled"] and menu["continue"]["hint"].startswith("Ink Hands · day")
    assert menu["load"]["hint"] == "2 guilds"
    c = st["charter"]
    assert c["world"] == "ink" and c["name"] == "Ink Hands" and c["vocation"] == "Caravan" and c["motto"]
    assert {k: v for v, k in c["ledger"]} == {"Day": last.clock.day, "Members": 6, "Wins": 0, "Bands": 2}
    assert [f["name"] for f in c["faces"]] == [u.name for u in last.roster[:4]] and c["more"] == 2
    assert c["faces"][0]["hurt"] and not c["faces"][1]["hurt"]
    assert c["where"]["place"] in ("Lumber Yard", "Market") and c["where"]["rest"] == "1 other band abroad"
    m = st["map"]
    assert {n["id"] for n in m["nodes"]} == {n.id for n in world.known(last)}
    assert sorted(g["at"] for g in m["groups"]) == ["lumber_yard", "market"]
    assert m["meta"]["name"] == "Ink Hands"


def test_continue_opens_the_map_on_the_live_save(saves):
    _save("ink", _guild("Ink Hands", "lumber_yard"), 2000)
    title = _title()
    assert title.load("ink") == {"screen": "map"}
    s = title.game.session
    assert isinstance(s, MapSession) and s.world_id == "ink" and s.guild.name == "Ink Hands"


def test_the_guilds_kept_newest_first_with_their_saves(saves):
    _save("old", _guild("Old Hands", "city"), 1000)
    _save("ink", _guild("Ink Hands", "lumber_yard"), 2000)
    title = _title()
    st = title.page("guilds")
    assert [w["name"] for w in st["guilds"]] == ["Ink Hands", "Old Hands"]
    row = st["guilds"][1]
    assert row["world"] == "old" and row["members"] == 2 and row["saves"] == 1 and len(row["faces"]) == 2
    assert row["color"] and row["emblem"]
    with pytest.raises(ValueError, match="no such guild"):
        title.page("saves", "nowhere")
    assert title.page("home")["charter"]["world"] == "ink"


def test_an_earlier_save_loaded_becomes_the_live_state_and_the_rest_stay(saves):
    guild = _guild("Ink Hands", "lumber_yard")
    persist.save_game("ink", guild)
    persist.save_game("ink", guild, kind="manual", label="before the road")
    guild.groups[0].node = "market"
    persist.save_game("ink", guild)
    title = _title()
    rows = title.page("saves", "ink")["saves"]["rows"]
    assert {r["kind"] for r in rows} == {"current", "manual"}
    manual = next(r for r in rows if r["kind"] == "manual")
    assert manual["label"] == "before the road" and manual["members"] == 2
    title.load("ink", manual["id"])
    assert title.game.session.guild.groups[0].node == "lumber_yard"
    assert persist.load_game("ink").groups[0].node == "lumber_yard"
    assert len(persist.list_saves("ink")) == 2


def test_a_save_deleted_goes_and_the_live_state_cannot_be(saves):
    guild = _guild("Ink Hands", "lumber_yard")
    persist.save_game("ink", guild)
    persist.save_game("ink", guild, kind="manual", label="keep me")
    title = _title()
    title.page("saves", "ink")
    with pytest.raises(ValueError, match="cannot be deleted"):
        title.delete_save("ink", persist.CURRENT)
    rows = title.delete_save("ink", _last_manual("ink"))["saves"]["rows"]
    assert [r["kind"] for r in rows] == ["current"]


def test_a_guild_deleted_goes_with_every_save(saves):
    _save("old", _guild("Old Hands", "city"), 1000)
    _save("ink", _guild("Ink Hands", "lumber_yard"), 2000)
    title = _title()
    st = title.delete_world("ink")
    assert st["mode"] == "guilds" and [w["world"] for w in st["guilds"]] == ["old"]
    assert title.page("home")["charter"]["world"] == "old"
    assert not (saves / "ink").exists()


def test_a_save_of_another_version_is_shown_but_refused(saves):
    _save("ink", _guild("Ink Hands", "lumber_yard"), 2000)
    path = persist.save_path("ink")
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    payload["save_version"] = -1
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    title = _title()
    st = title.state()
    assert st["charter"]["broken"] and st["map"] is None and st["charter"]["faces"]
    with pytest.raises(ValueError, match="another version"):
        title.load("ink")


def test_the_maps_menu_saves_and_comes_back_to_the_title(saves):
    guild = _guild("Ink Hands", "lumber_yard")
    persist.save_game("ink", guild)
    game = Game(MapSession(guild, "ink"))
    guild.groups[0].node = "market"
    assert game.session.to_title() == {"screen": "title"}
    assert isinstance(game.session, TitleSession) and game.session.notice is None
    assert persist.load_game("ink").groups[0].node == "market"


def test_a_wiped_guild_comes_back_to_the_title_with_the_notice(saves):
    guild = _guild("Ink Hands", "lumber_yard")
    persist.save_game("ink", guild)
    game = Game(MapSession(guild, "ink"))
    game.session.wiped = True
    game.session.to_title()
    assert "wiped out" in game.session.notice


def test_the_router_opens_the_title_and_quit_stops_the_window(saves):
    _save("ink", _guild("Ink Hands", "lumber_yard"), 2000)
    game = Game.title()
    stopped = []
    game.quit = lambda: stopped.append(True)
    srv = serve(game)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        assert json.loads(urllib.request.urlopen(url + "/api/screen").read())["screen"] == "title"
        for f in ("title/screen.html", "title/title.css", "title/title.js", "map/sheet.js"):
            assert urllib.request.urlopen(f"{url}/client/screens/{f}").status == 200
        req = urllib.request.Request(url + "/api/title/continue", b"{}", {"Content-Type": "application/json"})
        assert json.loads(urllib.request.urlopen(req).read()) == {"screen": "map"}
        assert json.loads(urllib.request.urlopen(url + "/api/screen").read())["screen"] == "map"
    finally:
        srv.shutdown()
        srv.server_close()
    title = _title()
    title.game.quit = lambda: stopped.append(True)
    assert title.quit() == {"quit": True} and stopped
