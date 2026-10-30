"""The combat log, the per-team controllers and the combat lab (combat_log.py, combat_lab.py,
battle_screen controllers, scripts/combat_analysis.py, scripts/combat_pairs.py)."""

import os
import random
import pytest
from gartok import ai, combat_lab, combat_log, encounters, recorder
from gartok.battle import Battle
from gartok.clock import Clock
from gartok.guild import Guild
from gartok.scenario import ErmosScenario, FlagScenario
import combat_analysis
import combat_pairs

HUMAN_AI = {"player": "human", "enemy": "ai"}

def _fight(seed=3, level=2, size=3, scenario=None):
    random.seed(seed)
    squad = [encounters.build_enemy(level) for _ in range(size)]
    foes = [encounters.build_enemy(level) for _ in range(size)]
    return Battle(squad, foes, scenario=scenario or ErmosScenario())

def _play(battle, limit=400):
    for _ in range(limit):
        if battle.winner is not None:
            break
        ai.take_turn(battle, battle.active)

def _recorded(tmp_path, controllers=HUMAN_AI, **kw):
    battle = _fight(**kw)
    log = combat_log.CombatLog(str(tmp_path / "fight.jsonl"), {"fight": "test"}, controllers)
    battle.record_to(log)
    return battle, log

def _lab_log(tmp_path, name, controllers, seed=5):
    battle, meta = combat_lab.build("scrapper", 0, 3, seed=seed)
    log = combat_log.CombatLog(str(tmp_path / name), meta, controllers)
    battle.record_to(log)
    _play(battle)
    log.end(battle)
    return battle


def test_a_whole_fight_is_written_and_closed(tmp_path):
    battle, log = _recorded(tmp_path)
    _play(battle)
    log.end(battle)
    rows = combat_log.load(log.path)
    assert rows[0]["e"] == "start" and rows[-1]["e"] == "end"
    assert rows[-1]["winner"] == battle.winner
    assert rows[0]["controllers"] == HUMAN_AI and rows[0]["meta"] == {"fight": "test"}
    assert [r["n"] for r in rows if r["e"] == "act"] == list(range(1, len(rows) - 1))


def test_the_start_row_holds_the_board_and_every_unit(tmp_path):
    battle, log = _recorded(tmp_path)
    start = combat_log.load(log.path)[0]
    assert start["board"]["cols"] == battle.board.cols
    assert sorted(map(tuple, start["board"]["walls"])) == sorted(battle.board.walls)
    assert len(start["units"]) == len(battle.units)
    assert start["units"][0]["char"]["race"] and start["units"][0]["team"] == "player"
    assert len(start["state"]["units"]) == len(battle.units)


def test_the_file_alone_rebuilds_the_fight_state_for_state(tmp_path):
    battle, log = _recorded(tmp_path)
    _play(battle)
    log.end(battle)
    frames = combat_log.frames(combat_log.load(log.path))
    last = frames[-1]["units"]
    for unit, seen in zip(battle.units, last):
        assert (seen["hp"], seen["status"], (seen["x"], seen["y"])) == (unit.hp, unit.status, tuple(unit.pos))
        assert seen["name"] == unit.name and seen["team"] == unit.team
    assert frames[-1]["round"] == battle.round_no


def test_each_decision_is_one_row_even_when_an_action_calls_another(tmp_path):
    battle, log = _recorded(tmp_path)
    calls = []
    orig = log.record

    def spy(*a, **kw):
        calls.append(a[1])
        return orig(*a, **kw)

    log.record = spy
    _play(battle)
    rows = [r for r in combat_log.load(log.path) if r["e"] == "act"]
    assert len(rows) == len(calls)


def test_rows_say_who_decided_and_only_a_person_gets_the_ais_guess(tmp_path):
    battle, log = _recorded(tmp_path)
    _play(battle)
    acts = [r for r in combat_log.load(log.path) if r["e"] == "act"]
    assert {r["by"] for r in acts} == {"human", "ai"}
    for r in acts:
        assert (r["team"] == "player") == (r["by"] == "human")
        assert (r["ai"] is not None) == (r["by"] == "human")


def test_the_ais_walking_is_a_row_like_a_persons(tmp_path):
    battle, log = _recorded(tmp_path)
    _play(battle)
    acts = [r for r in combat_log.load(log.path) if r["e"] == "act"]
    assert any(r["by"] == "ai" and r["action"] == "move" for r in acts)


def test_the_ais_guess_changes_nothing_and_is_what_it_then_really_does(tmp_path):
    battle, log = _recorded(tmp_path, controllers={"player": "human", "enemy": "human"})
    for _ in range(12):
        actor = battle.active
        idx = battle.units.index(actor)
        hp = [(u.hp, u.pos, u.ap) for u in battle.units]
        state = random.getstate()
        guess = combat_log.ai_choice(battle, actor)
        assert random.getstate() == state
        assert [(u.hp, u.pos, u.ap) for u in battle.units] == hp
        seen = len(combat_log.load(log.path))
        ai.take_turn(battle, actor)
        first = next(r for r in combat_log.load(log.path)[seen:] if r["actor"] == idx)
        assert guess == {"action": first["action"], "target": first["target"], "kw": first["kw"]}
        if battle.winner:
            break


def test_options_list_the_cells_and_targets_the_unit_could_use():
    from tests.helpers import _melee_battle
    battle, attacker, defender = _melee_battle()
    opts = combat_log.legal_options(battle, attacker)
    assert opts["move"] and all(len(c) == 2 for c in opts["move"])
    assert "end_turn" not in opts and "error" not in opts
    assert opts["attack"] == [battle.units.index(defender)]


def test_planting_the_flag_is_a_decision_and_the_flags_are_in_the_world(tmp_path):
    random.seed(4)
    squad = [encounters.build_enemy(1) for _ in range(3)]
    foes = [encounters.build_enemy(1) for _ in range(3)]
    battle = Battle(squad, foes, scenario=FlagScenario())
    log = combat_log.CombatLog(str(tmp_path / "ctf.jsonl"), {}, HUMAN_AI)
    battle.record_to(log)
    assert battle.awaiting_flag
    battle.plant_flag((2, 3))
    rows = combat_log.load(log.path)
    plant = rows[1]
    assert plant["action"] == "plant_flag" and plant["target"] == {"cell": [2, 3]}
    assert plant["state"]["world"]["flags"]["player"] == [2, 3]
    assert plant["state"]["world"]["flags"]["enemy"]


def test_skipping_the_trap_setup_is_a_logged_decision(tmp_path):
    random.seed(4)
    squad = [encounters.build_enemy(1) for _ in range(2)]
    foes = [encounters.build_enemy(1) for _ in range(2)]
    battle = Battle(squad, foes)
    trapper = battle.player_units[0]
    trapper.inventory.append("Bear Trap")
    battle.trap_setup_queue = [trapper]
    log = combat_log.CombatLog(str(tmp_path / "traps.jsonl"), {}, HUMAN_AI)
    battle.record_to(log)

    battle.skip_traps()
    skip = combat_log.load(log.path)[1]
    assert skip["action"] == "skip_traps" and skip["target"] is None
    assert battle.awaiting_trap is None and "Bear Trap" in trapper.inventory


def test_a_unit_who_joins_mid_fight_arrives_with_its_static_data(tmp_path):
    battle, log = _recorded(tmp_path)
    before = len(battle.units)
    joiner = encounters.build_enemy(1)
    battle.reinforce(joiner, [(battle.board.cols - 1, 0), (battle.board.cols - 2, 0)])
    _play(battle, limit=3)
    rows = combat_log.load(log.path)
    new = [r for r in rows if r.get("new_units")]
    assert new and new[0]["new_units"][0]["i"] == before
    assert len(combat_log.frames(rows)[-1]["units"]) == before + 1


def test_a_battle_with_no_sink_runs_as_before():
    battle = _fight()
    assert battle.sink is None
    _play(battle)
    assert battle.winner is not None


@pytest.mark.parametrize("fight_id", list(combat_lab.FIGHTS))
def test_every_benchmark_fight_builds_at_any_level(fight_id):
    fight = combat_lab.FIGHTS[fight_id]
    battle, meta = combat_lab.build(fight_id, 3, fight.squad, seed=11)
    assert len([u for u in battle.player_units if not u.ai_ally]) == fight.squad and battle.enemy_units
    assert meta == {"fight": fight_id, "level": 3, "squad": fight.squad, "seed": 11}


def test_the_same_seed_builds_the_same_fight():
    a, _ = combat_lab.build("wilds", 2, 3, seed=7)
    b, _ = combat_lab.build("wilds", 2, 3, seed=7)
    assert [u.hp_max for u in a.units] == [u.hp_max for u in b.units]
    assert [u.race["name"] for u in a.units] == [u.race["name"] for u in b.units]


def test_the_ribbit_brothers_is_six_a_side_by_default():
    assert combat_lab.FIGHTS["boss"].squad == 6 and combat_lab.FIGHTS["scrapper"].squad == 3


def test_log_paths_are_dated_and_a_taken_name_gets_a_number(tmp_path):
    first = combat_lab.log_path("Scrapper: Me vs AI!", today="2026-10-10", root=str(tmp_path))
    assert first == os.path.join(str(tmp_path), "2026-10-10", "scrapper-me-vs-ai.jsonl")
    os.makedirs(os.path.dirname(first))
    open(first, "w").close()
    second = combat_lab.log_path("Scrapper: Me vs AI!", today="2026-10-10", root=str(tmp_path))
    assert second.endswith("scrapper-me-vs-ai-2.jsonl")


def test_the_default_name_says_who_played():
    assert combat_lab.default_name("ctf", {"player": "human", "enemy": "ai"}) == "ctf-human-vs-ai"
    assert combat_lab.default_name("ctf", {"player": "human", "enemy": "human"}) == "ctf-human-vs-human"


def test_a_campaign_fight_logs_into_the_world_folder_only_while_recording(tmp_path):
    from gartok.group import Group
    assert recorder.combat_log_path("d012-wilds-hunt") is None                 # the recorder is off
    guild = Guild(None, groups=[Group([encounters.build_enemy(1)], node="wilds")], clock=Clock(86400 * 11))
    assert recorder.attach(str(tmp_path / "world"), guild)
    try:
        path = recorder.combat_log_path("d012-wilds-hunt")
        assert path == os.path.join(str(tmp_path / "world"), "combat_logs", "d012-wilds-hunt.jsonl")
        os.makedirs(os.path.dirname(path))
        open(path, "w").close()
        assert recorder.combat_log_path("d012-wilds-hunt").endswith("d012-wilds-hunt-2.jsonl")
    finally:
        recorder.detach()


def test_the_combat_log_path_is_none_while_detached():
    recorder.detach()
    assert recorder.combat_log_path("anything") is None


def test_the_analysis_summarises_and_replays_a_log(tmp_path):
    battle, log = _recorded(tmp_path)
    _play(battle)
    log.end(battle)
    lines = combat_analysis.summary(log.path)
    text = "\n".join(lines)
    assert "player: human, enemy: ai" in text and "won by" in text and "AI's action" in text
    replay = combat_analysis.show(log.path)
    assert replay and replay[0].startswith("r ")
    assert combat_analysis.find_logs([str(tmp_path)]) == [log.path]


def test_the_agreement_counts_where_a_person_parts_from_the_ai():
    rows = [{"e": "act", "by": "human", "action": "attack", "target": {"unit": 4},
             "ai": {"action": "attack", "target": {"unit": 4}}},
            {"e": "act", "by": "human", "action": "defend", "target": None,
             "ai": {"action": "attack", "target": {"unit": 4}}},
            {"e": "act", "by": "human", "action": "attack", "target": {"unit": 5},
             "ai": {"action": "attack", "target": {"unit": 4}}},
            {"e": "act", "by": "ai", "action": "attack", "target": None, "ai": None}]
    total, same_action, same_all, split = combat_analysis.agreement(rows)
    assert (total, same_action, same_all) == (3, 2, 1)
    assert split == {("defend", "attack"): 1}


@pytest.mark.slow
def test_the_pairs_script_replays_only_logged_fights_a_person_played_against_the_ai(tmp_path):
    battle = _lab_log(tmp_path, "mine.jsonl", HUMAN_AI)
    _lab_log(tmp_path, "two.jsonl", {"player": "human", "enemy": "human"})
    found, skipped = combat_pairs.played([str(tmp_path)])
    assert [(n, w) for n, _r, w in found] == [("mine.jsonl", battle.winner == "player")]
    assert skipped == 0
    assert combat_pairs.played([str(tmp_path)], fight="brawl") == ([], 0)


def test_a_log_rebuilds_into_the_same_squads_on_the_same_cells(tmp_path):
    _lab_log(tmp_path, "mine.jsonl", HUMAN_AI)
    rows = combat_log.load(str(tmp_path / "mine.jsonl"))
    rebuilt = combat_log.rebuild(rows)
    assert [(u.name, u.team, u.hp_max, u.ac, u.speed, u.weapon_name) for u in rebuilt.units] ==         [(s["name"], s["team"], s["hp_max"], s["ac"], s["speed"], s["weapon"]) for s in rows[0]["units"]]
    assert [tuple(u.pos) for u in rebuilt.units] == [tuple(v[:2]) for v in rows[0]["state"]["units"]]
    assert rebuilt.board.walls == {tuple(w) for w in rows[0]["board"]["walls"]}
    assert rebuilt.scenario.floor == rows[0]["board"]["floor"]
    assert combat_pairs.drift(rows) == []


def test_a_flag_fight_rebuilds_with_both_flags_where_the_log_planted_them(tmp_path):
    battle, meta = combat_lab.build("ctf", 2, 3, seed=5)
    log = combat_log.CombatLog(str(tmp_path / "ctf.jsonl"), meta, HUMAN_AI)
    battle.record_to(log)
    log.end(battle)
    with pytest.raises(ValueError):                         # the player's flag never went down
        combat_log.rebuild(combat_log.load(log.path))
    battle, meta = combat_lab.build("ctf", 2, 3, seed=5)
    log = combat_log.CombatLog(str(tmp_path / "planted.jsonl"), meta, HUMAN_AI)
    battle.record_to(log)
    battle.plant_flag(next(c for c in ((x, y) for x in range(4) for y in range(battle.board.rows))
                           if battle.can_plant_flag(c)))
    log.end(battle)
    rebuilt = combat_log.rebuild(combat_log.load(log.path))
    assert rebuilt.is_ctf and rebuilt.flags == battle.flags
    assert sum(u.ctf_runner for u in rebuilt.player_units) == sum(u.ctf_runner for u in rebuilt.enemy_units) == 1


def test_the_pairs_script_gives_the_same_ai_rate_every_run(tmp_path):
    _lab_log(tmp_path, "mine.jsonl", HUMAN_AI)
    rows = combat_log.load(str(tmp_path / "mine.jsonl"))
    first = combat_pairs.ai_win_rate(lambda: combat_log.rebuild(rows), 3)
    assert 0 <= first[0] <= 1 and first[1] >= 0
    assert combat_pairs.ai_win_rate(lambda: combat_log.rebuild(rows), 3) == first


def test_a_threshold_set_for_the_player_s_side_holds_only_on_its_turns():
    seen = []
    real, flee_hp = ai.take_turn, ai.FLEE_HP
    ai.take_turn = lambda battle, unit: seen.append((unit.team, ai.FLEE_HP))
    try:
        turn = combat_pairs._turn({"FLEE_HP": 0.05})
        battle, _ = combat_lab.build("scrapper", 0, 1, seed=5)
        turn(battle, battle.player_units[0])
        turn(battle, battle.enemy_units[0])
    finally:
        ai.take_turn = real
    assert seen == [("player", 0.05), ("enemy", flee_hp)] and ai.FLEE_HP == flee_hp
