"""Asking around (`investigation.py`): the Charisma roll, the clue count and its multipliers, the places that
know nothing, the hour it costs through the hub, and the save."""

import pytest

from gartok import data, investigation, missions, orders, persist
from gartok.clock import SECONDS_PER_DAY
from gartok.group import Group
from gartok.guild import Guild
from gartok.web.hub_session import HubSession
from gartok.web.map_session import MapSession
from tests.helpers import standard_unit

T = missions.FARMER_DAUGHTER
JOB = T.id


@pytest.fixture(autouse=True)
def live(monkeypatch):
    monkeypatch.setattr(missions, "FARMER_QUEST_LIVE", True)


def _guild(node="faith_cathedral"):
    u = standard_unit()
    guild = Guild([u])
    guild.groups = [Group([u], node)]
    guild.clock.seconds = 29 * SECONDS_PER_DAY
    guild.revealed.add("faith_cathedral")
    guild.missions.append(missions.Mission(JOB, u.uid, guild.clock.day, guild.clock.day + 20))
    return guild, guild.groups[0]


def _roll(monkeypatch, nat):
    monkeypatch.setattr(data, "d20", lambda: nat)


def test_a_good_roll_finds_the_clue_and_marks_the_place(monkeypatch):
    guild, g = _guild()
    _roll(monkeypatch, 20)
    lines = investigation.ask(guild, g, JOB)
    assert investigation.answer(JOB, "faith_cathedral") in lines
    assert investigation.clues(guild, JOB) == 1 and investigation.asked(guild, JOB, "faith_cathedral")


def test_a_bad_roll_costs_the_hour_and_can_be_tried_again(monkeypatch):
    guild, g = _guild()
    _roll(monkeypatch, 1)
    investigation.ask(guild, g, JOB)
    assert investigation.clues(guild, JOB) == 0 and not investigation.asked(guild, JOB, "faith_cathedral")
    _roll(monkeypatch, 20)
    investigation.ask(guild, g, JOB)
    assert investigation.clues(guild, JOB) == 1


def test_a_place_with_nothing_to_tell_says_so_when_the_roll_passes(monkeypatch):
    guild, g = _guild("farm")
    _roll(monkeypatch, 15)
    assert investigation.ask(guild, g, JOB) == [investigation.answer(JOB, "farm")]
    (c,) = guild.table
    assert c.nat == 15 and c.dc == investigation.GATHER_DC and c.ok
    assert investigation.asked(guild, JOB, "farm")


def test_a_place_with_nothing_to_tell_needs_the_roll_to_learn_it(monkeypatch):
    guild, g = _guild("farm")
    _roll(monkeypatch, 1)
    lines = investigation.ask(guild, g, JOB)
    assert lines != [investigation.answer(JOB, "farm")] and not investigation.asked(guild, JOB, "farm")
    assert not guild.table[0].ok


def test_every_job_falls_back_to_nobody_knows_at_a_place_without_clues(monkeypatch):
    guild, g = _guild("city")
    _roll(monkeypatch, 20)
    assert investigation.ask(guild, g, missions.TANNER_HIDES.id)[0] == investigation.answer("anything", "city")


def test_a_place_asked_twice_is_not_rolled_again(monkeypatch):
    guild, g = _guild()
    _roll(monkeypatch, 20)
    investigation.ask(guild, g, JOB)
    monkeypatch.setattr(data, "d20", lambda: pytest.fail("rolled"))
    investigation.ask(guild, g, JOB)
    assert investigation.clues(guild, JOB) == 1


def test_clues_add_up_and_each_reader_brings_its_multiplier(monkeypatch):
    guild, g = _guild()
    _roll(monkeypatch, 20)
    investigation.ask(guild, g, JOB)
    g.node = "ledger_hold"
    investigation.ask(guild, g, JOB)
    assert investigation.clues(guild, JOB) == 2
    assert investigation.bonus(guild, JOB, 2) == 4 and investigation.bonus(guild, JOB, 1) == 2
    assert investigation.bonus(guild, "other", 2) == 0


def test_a_clue_lifts_the_next_roll(monkeypatch):
    guild, g = _guild()
    guild.investigation[JOB] = {"clues": 9, "asked": []}
    _roll(monkeypatch, 1)
    investigation.ask(guild, g, JOB)
    assert investigation.asked(guild, JOB, "faith_cathedral")


def test_the_best_talker_rolls():
    u1, u2 = standard_unit(), standard_unit()
    u1.charisma, u2.charisma = 8, 18
    u1._derive_combat()
    u2._derive_combat()
    assert investigation.speaker(Group([u1, u2], "city")) is u2


def test_the_save_keeps_the_clues_and_an_old_save_has_none(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    guild, _ = _guild()
    guild.investigation[JOB] = {"clues": 2, "asked": ["faith_cathedral", "ledger_hold"]}
    world_id = persist.new_world_id()
    persist.save_game(world_id, guild)
    assert persist.load_game(world_id).investigation == guild.investigation
    assert persist.PAYLOAD_DEFAULTS["investigation"] == {}


def test_the_order_remembers_the_job_it_asks_about():
    from gartok import stints
    order = stints.order("ask_around", 1, subject=JOB)
    back = persist.order_from_dict(persist.order_to_dict(order))
    assert back.subject == JOB and stints.is_stint(back)


def _hub(guild):
    return HubSession(MapSession(guild), guild.groups[0], orders.Order("shrine"))


def test_the_jobs_tab_lists_every_job_out_whatever_its_board(monkeypatch):
    guild, g = _guild()
    st = _hub(guild).board.state()
    assert [a["id"] for a in st["asks"]] == [JOB] and not st["asks"][0]["done"]


def test_asking_around_through_the_hub_spends_the_hour_and_answers(monkeypatch):
    guild, g = _guild()
    _roll(monkeypatch, 20)
    hub = _hub(guild)
    before = guild.clock.seconds
    st = hub.ask_around(JOB)
    assert guild.clock.seconds - before == 3600
    assert st["tab"] == "jobs" and st["jobs"]["asks"][0]["done"]
    assert investigation.answer(JOB, "faith_cathedral") in st["jobs"]["asks"][0]["answer"]
    assert investigation.answer(JOB, "faith_cathedral") in st["jobs"]["notice"]


def test_a_place_already_asked_costs_no_hour(monkeypatch):
    guild, g = _guild()
    guild.investigation[JOB] = {"clues": 1, "asked": ["faith_cathedral"]}
    hub = _hub(guild)
    before = guild.clock.seconds
    hub.ask_around(JOB)
    assert guild.clock.seconds == before


def test_one_cannot_ask_about_a_job_not_out():
    guild, g = _guild()
    guild.missions.clear()
    with pytest.raises(ValueError):
        _hub(guild).ask_around(JOB)


def test_the_hour_asked_reaches_the_web_answer_as_a_die(monkeypatch):
    from gartok.web import server
    guild, g = _guild()
    _roll(monkeypatch, 14)
    hub = _hub(guild)
    hub.ask_around(JOB)
    (record,) = server._table(hub)
    assert record["nat"] == 14 and record["dc"] == str(investigation.GATHER_DC)
