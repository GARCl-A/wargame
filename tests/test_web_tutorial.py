"""The tutorial cards in the browser: every answer names the open screen's card in its `X-Tutorial`
header, the card is served by `/api/tutorial` and closed or opened again there, and each screen names
the card its pygame screen does."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from gartok import i18n, persist, recorder, tutorial
from gartok.group import Group
from gartok.guild import Guild
from gartok.web.draft_session import DraftSession
from gartok.web.guild_session import TABS as GUILD_TABS
from gartok.web.guild_session import GuildSession
from gartok.web.hub_session import TUTORIAL as HUB_TUTORIAL
from gartok.web.map_session import MapSession
from gartok.web.report_session import ReportSession
from gartok.web.server import Game, serve
from tests.helpers import standard_unit


@pytest.fixture
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    yield tmp_path
    recorder.detach()


def _guild(node="lumber_yard"):
    units = [standard_unit() for _ in range(2)]
    for u in units:
        u.money = 200
    return Guild(None, groups=[Group(units, node=node, leader=units[0])], name="Ink Hands")


@pytest.fixture
def served(saves):
    guild = _guild()
    game = Game(MapSession(guild))
    srv = serve(game)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", game, guild
    srv.shutdown()
    srv.server_close()


def _call(url, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read()), r.headers.get("X-Tutorial")


# ---------------------------------------------------------------- the server
def test_every_answer_names_the_card_and_the_card_is_the_locales_copy(served):
    url, _game, _guild = served
    _state, header = _call(url + "/api/map/state")
    assert header == "map|1"
    card, _ = _call(url + "/api/tutorial")
    assert card == {"key": "map", **tutorial.card("map")}
    assert card["title"] == i18n.t("tutorial.map.title") and card["body"] == i18n.t("tutorial.map.body")
    assert card["button"] == "See your objectives"


def test_the_maps_first_close_opens_the_objectives_and_a_later_one_stays(served):
    url, game, guild = served
    answer, header = _call(url + "/api/tutorial/dismiss", {})
    assert answer == {"screen": "guild"} and "map" in guild.tutorial.seen
    assert isinstance(game.session, GuildSession) and game.session.tab == "reputations"
    assert header == "guild.reputations|1", "the header names the screen open after the verb"
    _call(url + "/api/guild/back", {})
    _, header = _call(url + "/api/map/state")
    assert header == "map|0"
    card, header = _call(url + "/api/tutorial/reopen", {})
    assert header == "map|1" and card["key"] == "map"
    answer, header = _call(url + "/api/tutorial/dismiss", {})
    assert answer == {} and header == "map|0" and isinstance(game.session, MapSession)


def test_tutorials_switched_off_send_no_card_and_a_screen_with_none_refuses_one(served):
    url, game, guild = served
    guild.tutorial.enabled = False
    assert _call(url + "/api/map/state")[1] == ""
    game.open(Game.title().session)
    assert _call(url + "/api/title/state")[1] == ""
    with pytest.raises(urllib.error.HTTPError) as e:
        _call(url + "/api/tutorial")
    assert e.value.code == 409


def test_a_lab_fight_has_no_card():
    game = Game.fight("wilds", 2, 3, seed=4)
    assert game.session.tutorial_key() is None


# ---------------------------------------------------------------- each screen's card
def _copy(key):
    return i18n.has(f"tutorial.{key}.title") and i18n.has(f"tutorial.{key}.body")


def test_every_card_a_web_screen_names_has_its_copy():
    keys = {*HUB_TUTORIAL.values(), "library", "trust", "map", "group", "squad", "level", "watch", "hunt",
            "ox_hunt", "guard", "dialogue", "battle", "memorial", "report", "level_up", "reward", "loot",
            *(f"guild.{k}" for k in ("members", "overview", "reputations")),
            "draft.intro", "draft.vocation", "draft.pick", "draft.identity"}
    assert [k for k in sorted(keys) if not _copy(k)] == []


def test_a_hubs_card_follows_its_tab(saves):
    guild = _guild()
    game = Game(MapSession(guild))
    assert game.session.act(guild.groups[0].gid, "market") == {"screen": "hub"}
    hub = game.session
    assert hub.tutorial_key() == "market"
    hub.pick_tab("work")
    assert hub.tutorial_key() == "work"
    hub.pick_tab("gather")
    assert hub.tutorial_key() == "gathering"


def test_the_librarys_shop_and_the_trusts_jobs_name_their_own_cards(saves):
    guild = _guild("library")
    game = Game(MapSession(guild))
    game.session.act(guild.groups[0].gid, "library")
    hub = game.session
    assert hub.tutorial_key() == "library"
    hub.pick_tab("jobs")
    assert hub.tutorial_key() == "missions"
    hub.order.kind = "trust"
    assert hub.tutorial_key() == "trust"


def test_the_guild_sheets_card_follows_its_tab(saves):
    s = GuildSession(MapSession(_guild()))
    keys = {}
    for k, _ in GUILD_TABS:
        s.pick_tab(k)
        keys[k] = s.tutorial_key()
    assert keys == {"members": "guild.members", "bands": "group", "guild": "guild.overview",
                    "reputations": "guild.reputations"}


def test_the_draft_welcomes_first_then_names_each_steps_card():
    d = DraftSession()
    assert d.tutorial_key() == "draft.intro"
    d.tutorials().dismiss("draft.intro")
    assert d.tutorial_key() == "draft.vocation"
    d.step = "pick"
    assert d.tutorial_key() == "draft.pick"
    d.step = "charter"
    assert d.tutorial_key() == "draft.identity"


def test_the_reports_card_follows_its_stage():
    s = ReportSession.__new__(ReportSession)
    s.stages = [("memorial", None), ("report", None), ("level", 0), ("purse", None), ("loot", None), ("map", None)]
    seen = []
    for n in range(len(s.stages)):
        s.at_stage = n
        seen.append(s.tutorial_key())
    assert seen == ["memorial", "report", "level_up", "reward", "loot", None]
