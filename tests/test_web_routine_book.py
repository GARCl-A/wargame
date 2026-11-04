"""The Routines tab of the guild's sheet: the Book's pages are listed, written, saved and torn through the
session the server routes to."""

import pytest

from gartok import persist, recorder
from gartok import routines as r
from gartok.group import Group
from gartok.guild import Guild
from gartok.web.guild_session import GuildSession
from gartok.web.map_session import MapSession
from tests.helpers import standard_unit


@pytest.fixture
def sheet(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    members = [standard_unit() for _ in range(2)]
    guild = Guild(None, groups=[Group(members, node="city", leader=members[0], name="Gatherers")])
    session = GuildSession(MapSession(guild, persist.new_world_id()), tab="routines")
    yield session, guild
    recorder.detach()


def test_the_tab_lists_the_pages_the_seats_and_what_the_editor_may_name(sheet):
    session, _ = sheet
    state = session.state()["routines"]
    assert state["pages"] == [] and state["seats"] == [0, 0] and state["next"] > 0
    vocab = state["vocab"]
    assert ["farm", "The Farm"] in vocab["nodes"] and "Gatherers" in vocab["groups"]
    assert any("Lumber" in names for _, names in vocab["items"]) and "Minor Healing Potion" in vocab["recipes"]
    assert [t["key"] for t in session.state()["tabs"]][-1] == "routines"


def test_a_page_is_written_filled_in_and_torn(sheet):
    session, guild = sheet
    session.book_new("")
    assert guild.routine_pages[0].name == "New routine 1"
    blocks = r.dump((r.Repeat(r.coins(r.own()) < 500, [r.Travel("farm"), r.Rest(8)]),))
    out = session.book_save(0, "Walker", "to the farm", blocks)
    assert out["routines"]["pages"][0] == {"name": "Walker", "note": "to the farm", "blocks": blocks}
    session.book_new("Second")
    assert session.state()["routines"]["pick"] == 1
    session.book_pick(0)
    assert session.state()["routines"]["pick"] == 0
    session.book_tear(0)
    assert [p.name for p in guild.routine_pages] == ["Second"] and session.state()["routines"]["pick"] == 0


def test_a_refused_page_stays_as_it_was(sheet):
    session, guild = sheet
    session.book_new("A")
    with pytest.raises(ValueError, match="unknown place"):
        session.book_save(0, "A", "", r.dump((r.Travel("nowhere"),)))
    with pytest.raises(ValueError, match="no such routine"):
        session.book_pick(3)
    assert guild.routine_pages[0].blocks == ()


def test_the_pages_are_saved_with_the_game(sheet):
    session, _ = sheet
    session.book_new("Kept")
    assert persist.load_game(session.map.world_id).routine_pages[0].name == "Kept"
