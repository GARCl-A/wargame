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


class _SurvivableLibrary(sim_mod.FightLibrary):
    """The real won fights with the deaths taken out: the test is about the line the policy
    walks, not about the dice of a 6-fight library deciding whether the squad lives to walk it."""

    def pool(self, kind, level, size):
        fights = _LIBRARY.pool(kind, level, size)
        won = [f for f in fights if f.won] or fights
        return [sim_mod.Sample(f.won, f.rounds, [(min(lost, 1), False, xp) for lost, _, xp in f.members],
                               f.loot, f.purse) for f in won]


def test_the_rush_policy_follows_the_recorded_line():
    sim = sim_mod.Sim(sim_mod.Rush(), seed=6, library=_SurvivableLibrary(), skill=0.95, horizon=30)
    for _ in range(500):
        if sim.elapsed >= 30 or sim.policy.dictionary_done:
            break
        sim.policy.step(sim)
    assert sim.champion_beaten and sim.policy.dictionary_done
    assert sim.guild.missions[0].state == "done"
    assert all(economy.lumber_level(u) > 0 for u in sim.members)


def test_a_fall_in_battle_leaves_a_death_row_with_how_it_happened(tmp_path):
    from gartok.battle import Battle
    squad = [Unit("player") for _ in range(2)]
    guild = Guild(list(squad))
    recorder.attach(str(tmp_path), guild)
    battle = Battle(squad, [Unit("enemy")])
    battle.winner = "player"
    victim = battle.player_units[1]
    battle.log("The Wolf bites Victim.")
    battle.log(f"  {victim.name} goes down, dying (4 turns to the death save).")
    battle.log(f"{victim.name}: death save d20(3) -> dies.")
    victim.status = "dead"
    battle.player_units[0].status = "up"

    campaign.absorb_battle(guild, squad, battle)

    row = next(r for r in _rows(tmp_path) if r["e"] == "death")
    assert row["name"] == victim.name and row["cause"] == "combat" and row["how"] == "death_save"
    assert "The Wolf bites Victim." in row["trail"] and "goes down" in row["trail"][-1]
    assert row["foes"] and row["race"] and "combat" in row


def test_a_defeat_is_told_apart_from_a_failed_death_save(tmp_path):
    from gartok.battle import Battle
    squad = [Unit("player")]
    guild = Guild(list(squad) + [Unit("player")])
    recorder.attach(str(tmp_path), guild)
    battle = Battle(squad, [Unit("enemy")])
    battle.winner = "enemy"
    battle.log(f"  {battle.player_units[0].name} goes down, dying (4 turns to the death save).")
    battle.log(f"{battle.player_units[0].name} doesn't survive their wounds after the defeat.")
    battle.player_units[0].status = "dead"

    campaign.absorb_battle(guild, squad, battle)

    row = next(r for r in _rows(tmp_path) if r["e"] == "death")
    assert row["how"] == "defeat"


def test_starving_to_death_leaves_a_death_row(tmp_path):
    u, mate = Unit("player"), Unit("player")
    u.inventory, mate.inventory = [], []
    u.unfed_days = 3
    guild = Guild([u, mate], node="city")
    recorder.attach(str(tmp_path), guild)
    guild.pass_time(24)
    rows = [r for r in _rows(tmp_path) if r["e"] == "death"]
    assert [r["cause"] for r in rows] == ["starvation"] and rows[0]["name"] == u.name


def test_keep_fed_at_low_shops_when_the_larder_is_empty():
    sim = sim_mod.Sim(sim_mod.Lumber(), seed=1, library=_LIBRARY)
    for u in sim.members:
        u.inventory = []
        u.money = 50
    assert sim.food_days == 0
    assert not sim.keep_fed(low=0)                    # "under 0 days" is never true
    assert sim.keep_fed(low=0, at_low=True) and sim.food_days > 0


def test_the_analysis_tells_who_died_and_how(tmp_path):
    rows = [{"e": "death", "t": 2 * SECONDS_PER_DAY, "name": "Ana", "race": "Elf", "occupation": "Smith",
             "combat": 0.3, "work": 1.0, "cause": "combat", "how": "death_save", "round": 5,
             "foes": ["Wolf"], "trail": ["The Wolf bites Ana.", "Ana goes down"], "money": 5, "food_days": 1.0},
            {"e": "death", "t": 4 * SECONDS_PER_DAY, "name": "Bo", "race": "Orc", "occupation": "Slave",
             "combat": 0.0, "work": 0.0, "cause": "starvation", "unfed_days": 3, "money": 0, "food_days": 0.0}]
    out = pa.death_report(rows, "run")
    assert "2 lost" in out and "Ana" in out and "death save in round 5 vs Wolf" in out
    assert "The Wolf bites Ana." in out and "starved after 3 unfed days" in out
    assert "nobody died" in pa.death_report([], "run")


def test_a_death_in_a_sim_fight_names_the_fight(tmp_path):
    sim = sim_mod.Sim(sim_mod.Lumber(), seed=1, library=_LIBRARY)
    recorder.attach(str(tmp_path), sim.guild)
    party = list(sim.members)
    sample = sim_mod.Sample(False, 4, [(0, True, 0), (1, False, 0), (1, False, 0)], [], 0)
    sim.apply(sample, party, kind="wilds")
    rows = [r for r in _rows(tmp_path) if r["e"] == "death"]
    assert len(rows) == 1 and rows[0]["kind"] == "wilds" and rows[0]["won"] is False
