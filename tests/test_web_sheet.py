"""A member's sheet as a modal, opened from any screen that shows them: the `sheet` verb every session answers
(`Session.sheet`, `web/sheet_view.py`) and the shell's `Sheet` that draws it."""

import json
import os
import re
import threading
import urllib.error
import urllib.request

import pytest

from gartok import persist, recorder
from gartok.animals import HARNESS, Animal
from gartok.group import Group
from gartok.guild import Guild
from gartok.web.map_session import MapSession
from gartok.web.server import Game, serve
from tests.helpers import standard_unit

CLIENT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gartok", "web", "client")


@pytest.fixture
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    yield tmp_path
    recorder.detach()


def _guild(node="market"):
    a, b = [standard_unit() for _ in range(2)], [standard_unit()]
    for u in (*a, *b):
        u.give_to_pack("Potato", 4)
    ox = Animal("Ox", tack=HARNESS)
    return Guild(None, groups=[Group(a, node=node, leader=a[0], herd=[ox]), Group(b, node="tavern", leader=b[0])],
                 name="Ink Hands")


def _open(guild, key):
    game = Game(MapSession(guild))
    assert game.session.act(guild.groups[0].gid, key)["screen"]
    return game


def test_the_guild_sheet_opens_anyone_of_the_guild_and_an_animal(saves):
    guild = _guild()
    game = _open(guild, "guild")
    other = guild.groups[1].members[0]
    u = game.session.sheet(other.uid)
    assert u["name"] == other.name and u["band"] == guild.groups[1].display_name
    assert {"attrs", "stats", "weapon", "kit", "tracks", "talents", "record"} <= set(u)
    assert "roles" not in u                                  # the modal reads, it acts on nothing
    ox = guild.groups[0].herd[0]
    assert game.session.sheet(ox.uid)["beast"]


def test_a_hub_opens_its_bands_people_and_no_one_else(saves):
    guild = _guild()
    game = _open(guild, "market")
    me = guild.groups[0].members[1]
    assert game.session.screen == "hub" and game.session.sheet(me.uid)["name"] == me.name
    with pytest.raises(ValueError):
        game.session.sheet(guild.groups[1].members[0].uid)  # another band is in another place


def test_the_draft_opens_a_candidate_of_the_pool_before_any_guild(saves):
    game = Game.title()
    game.session.new_guild()
    d = game.session
    assert d.sheet_units() == []
    d.choose_vocation(d.state()["vocations"][0]["id"])
    d.next()
    card = d.state()["pool"][0]
    u = d.sheet(card["uid"])
    assert u["name"] == card["name"] and u["band"] is None and u["stamps"] == []
    assert u["where"] == "Not yet sworn in"


def test_the_sheet_verb_is_routed_on_every_screen(saves):
    guild = _guild()
    srv = serve(_open(guild, "market"))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        me = guild.groups[0].members[0]
        with urllib.request.urlopen(f"{base}/api/hub/sheet?uid={me.uid}") as r:
            assert json.loads(r.read())["uid"] == me.uid
        with pytest.raises(urllib.error.HTTPError) as no:
            urllib.request.urlopen(f"{base}/api/hub/sheet?uid=nobody")
        assert no.value.code == 409
    finally:
        srv.shutdown()
        srv.server_close()


def _client(path):
    with open(os.path.join(CLIENT, path), encoding="utf-8") as f:
        return f.read()


def test_the_shell_draws_the_book_and_the_screens_mark_their_portraits():
    shell = _client("shell.js")
    assert "const Sheet" in shell and "/sheet?uid=" in shell
    for path in ("screens/guild/bands.js", "screens/hub/shop.js", "screens/draft/draft.js"):
        assert "data-sheet=" in _client(path), path
    guild = _client("screens/guild/guild.js")
    assert "Sheet.pages(" in guild and "function memberPages" not in guild


def test_a_long_name_on_the_guild_sheet_shows_whole_on_hover_and_the_book_shrinks_its_heading():
    cells = re.compile(r'<(h1|h3|div class="nm")[^>]*>\$\{esc\([umpa]\.name\)\}')
    for path in ("shell.js", "screens/guild/guild.js", "screens/guild/bands.js"):
        for m in cells.finditer(_client(path)):
            assert "title=" in m.group(0), f"{path}: {m.group(0)}"
    assert '<b title="${esc(c.name)}"><em class="bn">' in _client("screens/guild/bands.js")
    shell, css = _client("shell.js"), _client("shell.css")
    assert "nameSize(u.name)" in shell and ".book .who h1.xlong" in css
