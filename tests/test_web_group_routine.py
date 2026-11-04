"""The BANDS tab's routine side: a group is given a copy from the Book, adjusts it, stops, continues, takes it off."""

import pytest

from gartok import persist, recorder, routine_book
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
    guild.reputation["arena"] = routine_book.FAME_PER_SLOT
    guild.routine_pages.append(routine_book.Page("Walker", (r.Rest(8),), "rest a while"))
    session = GuildSession(MapSession(guild, persist.new_world_id()), tab="bands")
    yield session, guild
    recorder.detach()


def test_a_band_without_a_routine_offers_the_pages_and_the_seats(sheet):
    session, _ = sheet
    st = session.state()["bands"]
    assert st["routine"] is None and st["equip"] == {"pages": [[0, "Walker"]], "seats": [0, 1]}
    assert st["chips"][0]["mark"] is None


def test_equipping_shows_the_copy_running_and_marks_the_chip(sheet):
    session, guild = sheet
    st = session.equip(0)["bands"]
    assert st["view"] == "routine" and st["routine"]["name"] == "Walker" and st["routine"]["running"]
    assert st["chips"][0]["mark"] == ["Routine", "good"]
    assert guild.groups[0].order is not None


def test_adjusting_the_copy_leaves_the_page_alone(sheet):
    session, guild = sheet
    session.equip(0)
    out = session.routine_save(r.dump((r.Rest(2),)))["bands"]["routine"]
    assert out["blocks"] == r.dump((r.Rest(2),)) and guild.routine_pages[0].blocks == (r.Rest(8),)
    with pytest.raises(ValueError, match="unknown place"):
        session.routine_save(r.dump((r.Travel("nowhere"),)))


def test_a_stopped_routine_continues_and_a_running_one_refuses(sheet):
    session, guild = sheet
    session.equip(0)
    with pytest.raises(ValueError, match="no stopped routine"):
        session.continue_routine()
    r.interrupt(guild.groups[0], "no coins")
    guild.groups[0].order = None
    st = session.state()["bands"]
    assert st["routine"]["paused"] == "no coins" and st["chips"][0]["mark"] == ["Stopped", "bad"]
    assert session.continue_routine()["bands"]["routine"]["running"]


def test_taking_off_frees_the_seat_and_saving_back_adds_a_page(sheet):
    session, guild = sheet
    session.equip(0)
    session.save_back()
    assert [p.name for p in guild.routine_pages] == ["Walker", "Walker 2"]
    out = session.take_off()["bands"]
    assert out["routine"] is None and out["view"] == "packs" and out["equip"]["seats"] == [0, 1]
    with pytest.raises(ValueError, match="has no routine"):
        session.take_off()


def test_equipping_is_refused_without_a_seat_or_a_page(sheet):
    session, guild = sheet
    with pytest.raises(ValueError, match="no such routine"):
        session.equip(4)
    guild.reputation["arena"] = 0
    with pytest.raises(ValueError, match="no free automation slot"):
        session.equip(0)


def test_the_routine_view_has_its_own_tutorial_card(sheet):
    session, _ = sheet
    assert session.tutorial_key() == "group"
    session.show_view("routine")
    assert session.tutorial_key() == "guild.band_routine"
    with pytest.raises(ValueError, match="no such view"):
        session.show_view("x")
