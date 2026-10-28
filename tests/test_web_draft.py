"""A new guild in the browser: the vocation, the pool of nine with the commission tokens, the charter;
FOUND opens the map on the guild just saved, and the title lists it."""

import json
import threading
import urllib.request

import pytest

from gartok import persist, recorder, vocations
from gartok.archetypes import ARCHETYPES
from gartok.guild import BANNER_COLORS
from gartok.web.server import Game, serve


@pytest.fixture
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    yield tmp_path
    recorder.detach()


def _draft(vocation=None):
    game = Game.title()
    assert game.session.new_guild() == {"screen": "draft"}
    d = game.session
    if vocation:
        d.choose_vocation(vocation)
        d.next()
    return d


def _squad(d, *indices):
    for i in indices:
        d.pick(i)
    return d.state()


def test_new_guild_opens_the_draft_and_its_first_back_returns_to_the_title(saves):
    game = Game.title()
    menu = {m["key"]: m for m in game.session.state()["menu"] if m}
    assert menu["new"]["enabled"]
    game.session.new_guild()
    st = game.session.state()
    assert st["step"] == "vocation" and st["vocation"] is None
    assert [v["id"] for v in st["vocations"]] == list(vocations.VOCATIONS)
    assert [s["state"] for s in st["steps"]] == ["now", "later", "later"]
    assert game.session.back() == {"screen": "title"} and game.session.screen == "title"


def test_the_vocation_must_be_picked_and_brings_one_of_each_of_its_races(saves):
    d = _draft()
    with pytest.raises(ValueError, match="pick a vocation"):
        d.next()
    with pytest.raises(ValueError, match="no vocation"):
        d.choose_vocation("pirates")
    st = d.choose_vocation(vocations.CARAVAN)
    assert st["vocation"]["name"] == "Caravan" and st["vocation"]["icon"]
    assert [v["id"] for v in st["vocations"] if v["chosen"]] == [vocations.CARAVAN]
    st = d.next()
    assert st["step"] == "pick" and len(st["pool"]) == 9 and st["tokens"] == 3 and st["squad"] == []
    races = [c["race"] for c in st["pool"]]
    assert all(r in races for r in vocations.get(vocations.CARAVAN).races)
    assert st["steps"][0] == {"label": "Vocation", "sub": "Caravan", "state": "done"}


def test_a_pick_toggles_and_the_squad_is_three(saves):
    d = _draft(vocations.WARBAND)
    with pytest.raises(ValueError, match="pick 3"):
        d.next()
    st = _squad(d, 4, 0, 7)
    assert st["squad"] == [4, 0, 7] and st["pool"][4]["picked"]
    with pytest.raises(ValueError, match="let one go"):
        d.pick(2)
    st = d.pick(0)
    assert st["squad"] == [4, 7] and not st["pool"][0]["picked"]
    with pytest.raises(ValueError, match="no such candidate"):
        d.pick(9)


def test_a_commission_spends_its_tokens_on_the_card_it_replaces(saves):
    d = _draft(vocations.CARAVAN)
    _squad(d, 0, 1)
    with pytest.raises(ValueError, match="at least one"):
        d.commission([])
    with pytest.raises(ValueError, match="no archetype"):
        d.commission(["LUCKY"])
    with pytest.raises(ValueError, match="3 tokens left"):
        d.commission(list(ARCHETYPES)[:4])
    st = d.commission(["LEADER", "WISE"])
    assert st["pending"] == ["LEADER", "WISE"] and st["tokens"] == 3
    old = d.draft.pool[1]
    st = d.pick(1)
    assert d.draft.pool[1] is not old and st["pending"] == [] and st["tokens"] == 1
    card = st["pool"][1]
    assert card["commissioned"] and not card["picked"] and st["squad"] == [0]
    starred = [t["label"] for t in card["tags"] if t["commissioned"]]
    assert set(starred) <= {"LEADER", "WISE"} and card["tags"][: len(starred)] == [t for t in card["tags"] if t["commissioned"]]
    with pytest.raises(ValueError, match="1 token left"):
        d.commission(["STRONG", "TOUGH"])
    d.commission(["STRONG"])
    assert d.cancel()["pending"] == [] and d.state()["tokens"] == 1


def test_back_keeps_the_pool_while_the_vocation_stays(saves):
    d = _draft(vocations.MARSH)
    _squad(d, 2)
    pool = list(d.draft.pool)
    d.back()
    assert d.next()["squad"] == [2] and d.draft.pool == pool
    d.back()
    d.choose_vocation(vocations.WILDS)
    st = d.next()
    assert st["squad"] == [] and d.draft.pool != pool


def test_the_charter_names_the_guild_its_banner_and_who_leads(saves):
    d = _draft(vocations.SCHOLARS)
    _squad(d, 0, 1, 2)
    st = d.next()
    c = st["charter"]
    assert st["step"] == "charter" and len(c["founders"]) == 3 and not c["can_found"]
    assert [f["name"] for f in c["founders"]] == [u.name for u in d.draft.picks]
    assert all("recruits" in f and f["recruits_why"].startswith("base") for f in c["founders"])
    with pytest.raises(ValueError, match="who leads"):
        d.found()
    c = d.set_name("  The Ashen Lantern of the Long Road  ")["charter"]
    assert c["name"] == "The Ashen Lantern of the"
    c = d.set_color(4)["charter"]
    assert c["color"] == list(BANNER_COLORS[4][1]) and [k["on"] for k in c["colors"]].index(True) == 4
    with pytest.raises(ValueError, match="no emblem"):
        d.set_emblem("smiley")
    c = d.set_emblem("wolf-head")["charter"]
    assert [e["slug"] for e in c["emblems"] if e["on"]] == ["wolf-head"]
    with pytest.raises(ValueError, match="needs a name"):
        d.rename(1, "   ")
    c = d.rename(1, "Ylhel")["charter"]
    assert c["founders"][1]["name"] == "Ylhel"
    c = d.set_leader(2)["charter"]
    assert [f["leader"] for f in c["founders"]] == [False, False, True] and c["can_found"]
    with pytest.raises(ValueError, match="no such founder"):
        d.set_leader(3)
    with pytest.raises(ValueError, match="not on the pick"):
        d.pick(0)


def test_found_saves_the_guild_and_opens_its_map(saves):
    d = _draft(vocations.DELVERS)
    _squad(d, 3, 5, 8)
    d.next()
    d.set_color(2)
    d.set_emblem("snake-bite")
    d.set_leader(1)
    picks, leader = list(d.draft.picks), d.draft.picks[1]
    game = d.game
    assert d.found("Deep Lantern") == {"screen": "map"}
    m = game.session
    g = m.guild
    assert m.screen == "map" and m.world_id
    assert g.name == "Deep Lantern" and g.vocation == vocations.DELVERS and g.leader is leader
    assert tuple(g.banner_color) == BANNER_COLORS[2][1] and g.banner_icon == "snake-bite"
    assert g.roster == picks
    worlds = persist.list_worlds()
    assert [w["name"] for w in worlds] == ["Deep Lantern"] and worlds[0]["world"] == m.world_id
    assert persist.load_game(m.world_id).name == "Deep Lantern"
    title = Game.title().session.state()
    assert title["charter"]["name"] == "Deep Lantern"


def test_an_unnamed_guild_is_the_guild(saves):
    d = _draft(vocations.WARBAND)
    _squad(d, 0, 1, 2)
    d.next()
    d.set_leader(0)
    game = d.game
    d.found("   ")
    assert game.session.guild.name == "The Guild"


def test_the_router_opens_the_draft_from_the_title(saves):
    game = Game.title()
    srv = serve(game)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        req = urllib.request.Request(url + "/api/title/new", b"{}", {"Content-Type": "application/json"})
        assert json.loads(urllib.request.urlopen(req).read()) == {"screen": "draft"}
        assert json.loads(urllib.request.urlopen(url + "/api/screen").read())["screen"] == "draft"
        for f in ("screen.html", "draft.css", "draft.js"):
            assert urllib.request.urlopen(f"{url}/client/screens/draft/{f}").status == 200
        assert json.loads(urllib.request.urlopen(url + "/api/draft/state").read())["step"] == "vocation"
    finally:
        srv.shutdown()
        srv.server_close()
