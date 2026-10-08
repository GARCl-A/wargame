"""The play recorder (gartok/recorder.py) and its analysis (scripts/play_analysis.py): the log
a person's play leaves, the thresholds read off it, and the `human` policy that plays by them."""

import json
import os
import sys

import pytest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
sys.path.insert(0, SCRIPTS)

import economy_guild as sim_mod
import play_analysis as pa

from gartok import campaign, economy, orders, recorder, settings
from gartok.clock import SECONDS_PER_DAY
from gartok.guild import Guild
from gartok.unit import Unit

_LIBRARY = sim_mod.FightLibrary(samples=6)


@pytest.fixture(autouse=True)
def _detached():
    recorder.detach()
    yield
    recorder.detach()


def _rows(tmp_path):
    with open(tmp_path / recorder.FILE, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def _lumber_run(tmp_path, days=4):
    sim = sim_mod.Sim(sim_mod.Lumber(), seed=1, library=_LIBRARY)
    recorder.attach(str(tmp_path), sim.guild)
    while sim.elapsed < days:
        sim.policy.step(sim)
    return sim


def test_setting_is_off_by_default():
    assert settings.SPEC["record_play"][2] == "OFF"


def test_nothing_is_written_while_detached(tmp_path):
    recorder.emit("buy", item="Axe")
    recorder.day_tick(Guild([Unit("player")], node="city"))
    assert not os.listdir(tmp_path)
    assert not recorder.attached()


def test_a_played_guild_leaves_session_day_order_and_buy_rows(tmp_path):
    _lumber_run(tmp_path)
    rows = _rows(tmp_path)
    kinds = {r["e"] for r in rows}
    assert {"session", "day", "order", "buy"} <= kinds
    assert rows[0]["e"] == "session"
    assert all("money" in r and "food_days" in r for r in rows)
    days = [r["day"] for r in rows if r["e"] == "day"]
    assert days == sorted(set(days))
    assert all(len(r["roster"]) == 3 for r in rows if r["e"] == "day")


def test_a_route_is_one_order_not_one_per_leg(tmp_path):
    guild = Guild([Unit("player")], node="city")
    recorder.attach(str(tmp_path), guild)
    group = guild.groups[0]
    group.order = orders.travel(group, "lumber_yard")
    campaign.advance(guild)
    walked = [r for r in _rows(tmp_path) if r["e"] == "order"]
    assert len(walked) == 1 and walked[0]["kind"] == "travel"
    assert walked[0]["dest"] == "lumber_yard"
    campaign.advance(guild)
    assert len([r for r in _rows(tmp_path) if r["e"] == "order"]) == 1


def test_loading_an_earlier_save_drops_the_replayed_rows(tmp_path):
    path = tmp_path / "play.jsonl"
    rows = [{"e": "session", "t": 0}, {"e": "day", "t": 100, "day": 2, "roster": [], "rations": 0},
            {"e": "day", "t": 200, "day": 3, "roster": [], "rations": 0},
            {"e": "session", "t": 150}, {"e": "day", "t": 300, "day": 4, "roster": [], "rations": 0}]
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    kept = pa.load(str(path))
    assert [r["t"] for r in kept] == [0, 100, 150, 300]


def test_day_table_reports_money_and_what_the_guild_did(tmp_path):
    _lumber_run(tmp_path)
    table = pa.day_table(pa.load(str(tmp_path / recorder.FILE)))
    assert table and all(t["alive"] == 3 for t in table)
    assert any(t["activity"] in ("work", "rest") for t in table)
    assert "money" in pa.table_report(table, "lumber")


def _buy(t, item, qty, price, money, food_days, members=3):
    return {"e": "buy", "t": t, "item": item, "qty": qty, "price": price, "money": money,
            "food_days": food_days, "members": members}


def test_thresholds_read_the_axe_the_food_trip_and_the_fights():
    h = 3600
    rows = [
        _buy(1 * h, "Axe", 1, 35, 100, 4.0),
        _buy(50 * h, "Potato", 6, 3, 50, 3.0),
        _buy(50 * h + 60, "Potato", 6, 3, 40, 5.0),
        {"e": "order", "t": 30 * SECONDS_PER_DAY, "kind": "arena", "hours": 1},
        {"e": "fight", "t": 30 * SECONDS_PER_DAY, "kind": "Scrapper", "won": True,
         "hp_frac": 0.8, "money_before": 90, "members_before": 3, "level_before": 0},
        {"e": "fight", "t": 31 * SECONDS_PER_DAY, "kind": "Scrapper", "won": False,
         "hp_frac": 0.6, "money_before": 150, "members_before": 3, "level_before": 1},
        {"e": "fight", "t": 32 * SECONDS_PER_DAY, "kind": "ambush", "won": True},
    ]
    got = pa.thresholds(rows)
    assert got["axe_cash_per_member"] == pytest.approx((100 + 35) / 3, abs=0.01)
    assert got["axe_food_days"] == 4.0
    assert got["food_target_days"] == 5.0
    assert got["food_low_days"] == 1.0
    assert got["bout_min_hp"] == 0.6
    assert got["bout_cash_per_member"] == 40.0
    assert got["bout_win_rate"] == 0.5
    assert got["yard_leave_day"] == 31


def test_profile_is_the_median_of_the_runs():
    runs = [[_buy(0, "Axe", 1, 35, 65, 3.0)], [_buy(0, "Axe", 1, 35, 165, 3.0)],
            [_buy(0, "Axe", 1, 35, 265, 3.0)]]
    merged = pa.profile(runs)
    assert merged["runs"] == 3
    assert merged["axe_cash_per_member"] == pytest.approx((165 + 35) / 3, abs=0.01)


def test_a_run_that_never_hunted_has_no_hunt_threshold():
    assert "hunt_min_hp" not in pa.thresholds([_buy(0, "Axe", 1, 35, 65, 3.0)])


def test_the_human_policy_plays_by_the_profile(tmp_path):
    prof = tmp_path / "profile.json"
    prof.write_text(json.dumps({"yard_leave_day": 3, "axe_cash_per_member": 20,
                                "food_low_days": 1.5, "food_target_days": 4}), encoding="utf-8")
    sim_mod.Human.load(str(prof))
    try:
        res = sim_mod.run_guild("human", days=6, seed=2, library=_LIBRARY, marks=(6,))
    finally:
        sim_mod.Human.profile = {}
    assert not res.crashed
    assert res.money[6] >= 0


def test_missions_and_crafts_are_logged(tmp_path):
    from gartok import missions
    guild = Guild([Unit("player")], node="city")
    recorder.attach(str(tmp_path), guild)
    template = next(iter(missions.TEMPLATES.values())) if hasattr(missions, "TEMPLATES") else None
    assert template is not None
    missions.accept(guild, guild.roster[0], template)
    for item in ("Meat", "Meat", "Salt"):
        guild.roster[0].give_to_pack(item)
    guild.crafting_shift(guild.roster[0], "Jerky", 1)
    got = {r["e"]: r for r in _rows(tmp_path)}
    assert got["mission"]["what"] == "accept" and got["mission"]["id"] == template.id
    assert got["craft"]["recipe"] == "Jerky"


def test_the_rush_policy_follows_the_recorded_line():
    sim = sim_mod.Sim(sim_mod.Rush(), seed=6, library=_LIBRARY, skill=0.95, horizon=30)
    while sim.elapsed < 30 and not sim.policy.dictionary_done:
        sim.policy.step(sim)
    assert sim.champion_beaten and sim.policy.dictionary_done
    assert sim.guild.missions[0].state == "done"
    assert all(economy.lumber_level(u) > 0 for u in sim.members)
