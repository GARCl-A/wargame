"""Fault capture: an exception a request did not expect is written to errors.jsonl, answered 500 and the game
goes back to its last save; a refusal stays a 409."""

import io
import json
import threading
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pytest

from gartok import fault_log, i18n, persist, playtest_export, recorder, settings
from gartok.group import Group
from gartok.guild import Guild
from gartok.web.battle_session import BattleSession
from gartok.web.map_session import MapSession
from gartok.web.server import Game, serve
from tests.helpers import standard_unit


@pytest.fixture
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path / "saves"))
    monkeypatch.setattr(settings, "PATH", str(tmp_path / "settings.json"))
    settings.reload()
    yield tmp_path
    settings.reload()
    recorder.detach()


def _map():
    units = [standard_unit() for _ in range(2)]
    guild = Guild(None, groups=[Group(units, node="lumber_yard", leader=units[0])], name="Ink Hands",
                  vocation="caravan")
    persist.save_game("ink", guild)
    return Game(MapSession(guild, "ink"))


def _up(game):
    srv = serve(game)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


@pytest.fixture
def run():
    servers = []

    def start(game):
        srv, url = _up(game)
        servers.append(srv)
        return url
    yield start
    for srv in servers:
        srv.shutdown()
        srv.server_close()


def _ask(url, body=None, raw=None):
    req = urllib.request.Request(url, data=raw if raw is not None else (None if body is None else json.dumps(body).encode()),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _lines():
    p = Path(fault_log.path())
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def _boom(monkeypatch, cls, verb="boom", post=False):
    monkeypatch.setitem(cls.POST if post else cls.GET, verb, lambda s, q: 1 / 0)


def test_a_verb_that_raises_answers_500_and_is_logged(saves, run, monkeypatch):
    _boom(monkeypatch, BattleSession)
    url = run(Game.fight("fortress", 2, 4, seed=3))
    code, body = _ask(url + "/api/battle/boom")
    assert code == 500 and body["fault"] is True and body["error"] == i18n.t("server.fault")
    (line,) = _lines()
    assert line["source"] == "server" and line["where"] == "GET battle/boom" and line["screen"] == "battle"
    assert "ZeroDivisionError" in line["trace"] and line["game_version"]


def test_a_refusal_stays_409_and_writes_no_log(saves, run, monkeypatch):
    def refuse(s, q):
        raise ValueError("no")
    monkeypatch.setitem(BattleSession.GET, "nope", refuse)
    url = run(Game.fight("fortress", 2, 4, seed=3))
    assert _ask(url + "/api/battle/nope") == (409, {"error": "no"})
    assert not Path(fault_log.path()).exists()


def test_a_lab_fight_keeps_its_session_after_a_fault(saves, run, monkeypatch):
    _boom(monkeypatch, BattleSession)
    game = Game.fight("fortress", 2, 4, seed=3)
    session = game.session
    url = run(game)
    code, body = _ask(url + "/api/battle/boom")
    assert code == 500 and body["reload"] is False and game.session is session
    assert _ask(url + "/api/battle/state")[0] == 200


def test_a_game_on_a_save_goes_back_to_it(saves, run, monkeypatch):
    def break_then_raise(s, q):
        s.guild.name = "Broken"
        raise RuntimeError("half done")
    monkeypatch.setitem(MapSession.GET, "boom", break_then_raise)
    game = _map()
    before = game.session
    url = run(game)
    code, body = _ask(url + "/api/map/boom")
    assert code == 500 and body["reload"] is True
    assert isinstance(game.session, MapSession) and game.session is not before
    assert game.session.guild.name == "Ink Hands"


def test_two_faults_in_a_row_open_the_title(saves, run, monkeypatch):
    _boom(monkeypatch, MapSession, "state")
    game = _map()
    url = run(game)
    assert _ask(url + "/api/map/state")[0] == 500
    assert _ask(url + "/api/map/state")[0] == 500
    assert _ask(url + "/api/screen")[1]["screen"] == "title" and game.world is None


def test_a_good_answer_between_two_faults_resets_the_count(saves, run, monkeypatch):
    _boom(monkeypatch, MapSession)
    game = _map()
    url = run(game)
    assert _ask(url + "/api/map/boom")[0] == 500
    assert _ask(url + "/api/screen")[1]["screen"] == "map"
    assert _ask(url + "/api/map/boom")[0] == 500
    assert _ask(url + "/api/screen")[1]["screen"] == "map"


def test_a_client_error_is_logged_cut_and_does_not_reset_the_count(saves, run):
    game = Game.fight("fortress", 2, 4, seed=3)
    game.faults = 1
    url = run(game)
    assert _ask(url + "/api/client_error", {"where": "x.js:3", "error": "e" * 100_000, "trace": "t"})[0] == 200
    (line,) = _lines()
    assert line["source"] == "client" and line["where"] == "x.js:3" and len(line["error"]) == fault_log.MAX_TEXT
    assert game.faults == 1


def test_past_the_cap_nothing_is_appended(saves, monkeypatch):
    monkeypatch.setattr(fault_log, "MAX_BYTES", 200)
    for _ in range(20):
        fault_log.record("client", "a.js:1", "boom")
    assert 0 < Path(fault_log.path()).stat().st_size < 200 + 600


def test_record_does_not_raise_when_the_folder_cannot_be_written(saves, monkeypatch):
    blocker = saves / "file"
    blocker.write_text("x")
    monkeypatch.setattr(persist, "SAVE_DIR", str(blocker / "saves"))
    fault_log.record("server", "GET x", "boom")


def test_a_body_that_is_not_json_answers_with_a_json_body(saves, run):
    url = run(Game.fight("fortress", 2, 4, seed=3))
    code, body = _ask(url + "/api/battle/state", raw=b"{nope")
    assert code in (409, 500) and "error" in body


def test_the_export_carries_the_log(saves, run, monkeypatch):
    _boom(monkeypatch, BattleSession)
    url = run(Game.fight("fortress", 2, 4, seed=3))
    _ask(url + "/api/battle/boom")
    names = zipfile.ZipFile(io.BytesIO(playtest_export.build())).namelist()
    assert "saves/errors.jsonl" in names


def test_the_shell_listens_and_reports_through_fetch():
    js = (Path(__file__).resolve().parent.parent / "gartok" / "web" / "client" / "shell.js").read_text(encoding="utf-8")
    assert 'addEventListener("error"' in js and 'addEventListener("unhandledrejection"' in js
    report = js[js.index("function report("):js.index("function script(")]
    assert "/api/client_error" in report and "fetch(" in report and "api(" not in report
