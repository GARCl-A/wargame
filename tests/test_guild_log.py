"""The guild's log (guild_log.py): what is kept, in what order, what the limit does, and the lines the
clock writes where they are born."""

import json
from collections import Counter

import pytest

from gartok import campaign, guild_log, orders, persist, settings
from gartok.clock import SECONDS_PER_DAY, SECONDS_PER_HOUR
from gartok.group import Group
from gartok.guild import Guild
from gartok.guild_log import GuildLog
from tests.helpers import standard_unit


@pytest.fixture(autouse=True)
def _tmp_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PATH", str(tmp_path / "settings.json"))
    settings.reload()
    yield
    settings.reload()


def _guild(*nodes, food=6):
    groups = []
    for node in nodes:
        unit = standard_unit()
        unit.give_to_pack("Potato", food)
        groups.append(Group([unit], node=node, leader=unit))
    return Guild(None, groups=groups, name="Ink Hands")


def _lines(guild, kind=None):
    return [r for r in guild.log.tail(10_000) if kind is None or r["kind"] == kind]


# ---------------------------------------------------------------- the log itself
def test_lines_are_kept_in_the_order_of_their_second_a_late_write_slots_in():
    log = GuildLog(cap=50)
    log.record(["third"], 3 * SECONDS_PER_HOUR, "day")
    log.record(["first"], SECONDS_PER_HOUR, "day")
    log.record(["also third"], 3 * SECONDS_PER_HOUR, "day")
    assert [r["text"] for r in log.tail(10)] == ["first", "third", "also third"]


def test_a_row_says_its_day_and_hour_off_the_clock_second():
    log = GuildLog(cap=50)
    log.record(["x"], 2 * SECONDS_PER_DAY + 5 * SECONDS_PER_HOUR + 7 * 60, "food", "The Founders")
    (row,) = log.tail(1)
    assert (row["day"], row["at"], row["band"], row["kind"]) == (3, "05:07", "The Founders", "food")


def test_a_failure_is_marked_bad_and_an_ordinary_line_is_not():
    log = GuildLog(cap=50)
    log.record(["Ribit worked 8 h (+$2 each).", "Morkaelrax did not eat today: Hungry.",
                "Ribit: the pickaxe broke, no haul."], 0, "work")
    assert [r["tone"] for r in log.tail(3)] == ["", "bad", "bad"]


def test_a_full_log_forgets_its_oldest_line_and_asks_only_until_answered():
    log = GuildLog(cap=10)
    for i in range(9):
        log.record([f"line {i}"], i, "day")
    assert log.near_full and not log.full and not log.prompt
    log.record(["line 9"], 9, "day")
    assert log.full and log.prompt
    log.record(["line 10"], 10, "day")
    assert len(log.entries) == 10 and log.tail(10)[0]["text"] == "line 1"
    log.muted = True
    assert log.full and not log.prompt


def test_search_narrows_by_word_kind_and_band_and_the_guild_own_lines_are_dash():
    log = GuildLog(cap=50)
    log.record(["Ribit dug 4 Iron Ore."], 1, "work", "The Miners")
    log.record(["Morkaelrax ate."], 2, "food", "The Founders")
    log.record(["Tax is due."], 3, "guild")
    assert log.search("ore")[1] == 1
    assert log.search("iron ORE")[0][0]["band"] == "The Miners"
    assert [r["text"] for r in log.search(kind="food")[0]] == ["Morkaelrax ate."]
    assert [r["text"] for r in log.search(band="The Founders")[0]] == ["Morkaelrax ate."]
    assert [r["text"] for r in log.search(band="-")[0]] == ["Tax is due."]
    assert log.search("miners")[1] == 1                      # the band's name is searched too
    assert log.search("nothing like this")[1] == 0


def test_the_default_limit_is_the_players_setting():
    assert GuildLog().limit == settings.SPEC["log_lines"][2]
    settings.step_up("log_lines")
    assert GuildLog().limit == settings.get("log_lines") > settings.SPEC["log_lines"][2]


def test_a_limit_only_steps_up_and_stops_at_the_largest():
    top = settings.SPEC["log_lines"][1][-1]
    for _ in range(10):
        settings.step_up("log_lines")
    assert settings.get("log_lines") == top and settings.next_choice("log_lines") is None


def test_export_writes_the_oldest_half_as_text_and_drops_it(tmp_path, monkeypatch):
    monkeypatch.setattr(guild_log, "export_dir", lambda: str(tmp_path / "log-export"))
    log = GuildLog(cap=10)
    for i in range(10):
        log.record([f"line {i}"], i * SECONDS_PER_HOUR, "day", "The Founders" if i % 2 else None)
    log.muted = True
    path = log.export_and_trim("Ink Hands", 1)
    with open(path, encoding="utf-8") as fh:
        text = fh.read().splitlines()
    assert path.endswith("Ink Hands-day1.txt") and len(text) == 5
    assert text[0] == "Day 1 00:00  line 0" and text[1] == "Day 1 01:00  [The Founders] line 1"
    assert next(r["text"] for r in log.tail(10)) == "line 5" and not log.full and not log.muted
    for i in range(10, 15):
        log.record([f"line {i}"], i * SECONDS_PER_HOUR, "day")
    assert log.export_and_trim("Ink Hands", 1).endswith("Ink Hands-day1-2.txt")    # never over a file


def test_discard_drops_the_oldest_half_without_a_file():
    log = GuildLog(cap=10)
    for i in range(10):
        log.record([f"line {i}"], i, "day")
    assert log.discard_oldest() == 5 and len(log.entries) == 5


# ---------------------------------------------------------------- written where it is born
def test_every_crossed_day_writes_its_meals_at_its_own_midnight():
    guild = _guild("lumber_yard")
    guild.pass_time(72)
    food = _lines(guild, "food")
    assert {r["day"] for r in food} == {2, 3, 4}
    assert all(r["at"] == "00:00" for r in food)
    assert [r["day"] for r in food] == sorted(r["day"] for r in food)


def test_a_rest_order_writes_its_healing_under_the_band_and_nothing_twice():
    guild = _guild("lumber_yard")
    g = guild.groups[0]
    g.name = "The Founders"
    unit = g.members[0]
    unit.hp = max(1, unit.hp_max - 3)
    g.order = orders.rest(8)
    campaign.advance(guild)
    heal = [r for r in _lines(guild) if "recovers" in r["text"]]
    assert heal and heal[0]["kind"] == "rest" and heal[0]["band"] == "The Founders"
    texts = [r["text"] for r in _lines(guild)]
    assert max(Counter(texts).values()) == 1


def test_a_paid_shift_is_a_work_line_of_its_band():
    guild = _guild("lumber_yard")
    g = guild.groups[0]
    g.order = orders.work(guild, g, 8)
    campaign.advance(guild)
    work = _lines(guild, "work")
    assert work and all(r["band"] == g.display_name for r in work)


def test_a_jump_with_no_group_order_logs_the_hungry_not_a_group():
    guild = _guild("lumber_yard", food=0)
    guild.pass_time(72)
    assert any("did not eat" in r["text"] and r["tone"] == "bad" and r["band"] is None for r in _lines(guild, "food"))


# ---------------------------------------------------------------- saved with the guild
def test_the_log_comes_back_from_a_save(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    guild = _guild("lumber_yard")
    guild.log.record(["Ribit worked 8 h."], 5 * SECONDS_PER_HOUR, "work", "The Loggers")
    persist.save_game("w", guild)
    again = persist.load_game("w")
    assert again.log.to_list() == guild.log.to_list()


def test_a_save_without_a_log_loads_an_empty_one(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    persist.save_game("w", _guild("lumber_yard"))
    path = persist.save_path("w")
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    del payload["log"]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    assert persist.load_game("w").log.entries == []
