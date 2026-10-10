"""The combat log, the per-team controllers and the combat lab (combat_log.py, combat_lab.py,
battle_screen controllers, scripts/combat_analysis.py, scripts/combat_pairs.py)."""

import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from gartok import ai, combat_lab, combat_log, encounters, recorder, vision
from gartok.battle import Battle
from gartok.battle_screen import BattleScreen
from gartok.clock import Clock
from gartok.combat_lab_screen import CombatLabScreen
from gartok.editor_menu_screen import EditorMenuScreen
from gartok.guild import Guild
from gartok.scenario import ErmosScenario, FlagScenario
from gartok.ui.tokens import fonts as ui_fonts

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
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


# ---- the log ------------------------------------------------------------- #

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


# ---- controllers --------------------------------------------------------- #

def _screen(controllers=None, scenario=None):
    pygame.init()
    battle = _fight(scenario=scenario)
    screen = BattleScreen(ui_fonts(), battle, on_battle_end=lambda b: None, controllers=controllers)
    return screen, battle


def test_the_default_is_a_person_for_the_guild_against_the_ai():
    screen, battle = _screen()
    team = battle.active.team
    assert screen._is_player_turn() is (team == "player")
    assert screen.me == "player" and screen.foe == "enemy"


def test_a_person_can_play_the_opposing_side_and_sees_through_its_eyes():
    screen, battle = _screen({"player": "ai", "enemy": "human"})
    while battle.active.team != "enemy":
        battle.end_turn()
    assert screen._is_player_turn()
    assert screen.me == "enemy" and screen.foe == "player"
    assert vision.observers(battle, False, screen.me) == [battle.active]
    screen.draw(pygame.Surface((1280, 800)))


def test_an_ai_side_is_driven_by_the_screens_update():
    screen, battle = _screen({"player": "ai", "enemy": "ai"})
    before = (battle.round_no, battle.turn_idx)
    for _ in range(8):
        screen.update(1000)
    assert (battle.round_no, battle.turn_idx) != before
    assert not screen._is_player_turn()


def test_two_people_get_a_hand_over_card_between_their_turns():
    screen, battle = _screen({"player": "human", "enemy": "human"})
    surf = pygame.Surface((1280, 800))
    screen.update(1)
    assert screen._handoff is None or screen._handoff == battle.active.team
    while screen._handoff is None:
        battle.end_turn()
        screen.update(1)
        if battle.winner:
            pytest.skip("the fight ended first")
    waiting = screen._handoff
    assert not screen._is_player_turn()
    screen.draw(surf)
    screen._click((10, 10))
    assert screen._handoff is None and screen._seat == waiting and screen._is_player_turn()


def test_an_ai_guild_plants_its_own_flag_in_capture_the_flag():
    screen, battle = _screen({"player": "ai", "enemy": "human"}, scenario=FlagScenario())
    assert battle.awaiting_flag
    screen.update(1)
    assert battle.flags["player"] is not None and battle.flags["player"][0] < battle.board.cols // 2


def test_the_log_is_closed_when_the_screen_sees_the_end(tmp_path):
    screen, battle = _screen({"player": "ai", "enemy": "ai"})
    log = combat_log.CombatLog(str(tmp_path / "x.jsonl"), {}, {"player": "ai", "enemy": "ai"})
    battle.record_to(log)
    _play(battle)
    screen.update(1)
    assert log.closed and combat_log.load(log.path)[-1]["e"] == "end"


# ---- the lab ------------------------------------------------------------- #

@pytest.mark.parametrize("fight_id", list(combat_lab.FIGHTS))
def test_every_benchmark_fight_builds_at_any_level(fight_id):
    fight = combat_lab.FIGHTS[fight_id]
    battle, meta = combat_lab.build(fight_id, 3, fight.squad, seed=11)
    assert len(battle.player_units) == fight.squad and battle.enemy_units
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


def _lab():
    pygame.init()
    started = []
    screen = CombatLabScreen(ui_fonts(), started.append, lambda: None)
    screen.draw(pygame.Surface((1280, 800)))
    return screen, started


def test_the_lab_form_picks_the_fight_the_size_and_who_plays():
    screen, started = _lab()
    rect = next(r for r, f in screen.hits["fights"] if f == "boss")
    screen._click(rect.center)
    assert screen.fight == "boss" and screen.squad == 6
    screen.draw(pygame.Surface((1280, 800)))
    screen._click(screen.hits["level"][1].center)
    screen._click(screen.hits["level"][1].center)
    screen._click(screen.hits["squad"][0].center)
    assert screen.level == 2 and screen.squad == 5
    screen._click(screen.hits["p2"].center)
    screen._click(screen.hits["start"].center)
    assert started == [{"fight": "boss", "level": 2, "squad": 5,
                        "controllers": {"player": "human", "enemy": "human"},
                        "name": "boss-human-vs-human"}]


def test_the_lab_steppers_stop_at_their_limits():
    screen, _ = _lab()
    screen._click(screen.hits["level"][0].center)
    assert screen.level == 0
    for _ in range(30):
        screen._click(screen.hits["level"][1].center)
        screen._click(screen.hits["squad"][1].center)
    assert screen.level == combat_lab.MAX_LEVEL and screen.squad == combat_lab.MAX_SQUAD


def test_the_lab_names_the_simulation_by_typing():
    screen, started = _lab()
    screen._click(screen.hits["name"].center)
    assert screen.editing
    for ch in "my run":
        screen.handle_event(pygame.event.Event(pygame.KEYDOWN, key=0, unicode=ch))
    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode=""))
    screen.draw(pygame.Surface((1280, 800)))
    screen._click(screen.hits["start"].center)
    assert started[0]["name"] == "my run"


def test_the_editor_menu_opens_the_lab():
    pygame.init()
    opened = []
    menu = EditorMenuScreen(ui_fonts(), lambda: None, lambda: None, on_combat_lab=lambda: opened.append(1))
    menu.draw(pygame.Surface((1280, 800)))
    rect = next(r for k, r, enabled in menu.cards if k == "combat_lab" and enabled)
    menu._click(rect.center)
    assert opened == [1]


def test_starting_a_lab_fight_opens_a_battle_with_a_log_at_the_chosen_path(tmp_path, monkeypatch):
    from tests.helpers import make_app
    monkeypatch.setattr(combat_lab, "ROOT", str(tmp_path))
    app = make_app(None)
    app.ui_fonts = ui_fonts()
    app._start_lab_fight({"fight": "scrapper", "level": 1, "squad": 3,
                          "controllers": {"player": "human", "enemy": "ai"}, "name": "first try"})
    assert isinstance(app.scene, BattleScreen)
    log = app.scene.battle.sink
    assert os.path.dirname(os.path.dirname(log.path)) == str(tmp_path) and log.path.endswith("first-try.jsonl")
    start = combat_log.load(log.path)[0]
    assert start["meta"]["source"] == "lab" and start["meta"]["fight"] == "scrapper"
    assert start["controllers"] == {"player": "human", "enemy": "ai"}


# ---- the campaign's own fights ------------------------------------------- #

def test_a_campaign_fight_logs_into_the_world_folder_only_while_recording(tmp_path):
    from tests.helpers import make_app, world
    guild = Guild(None, groups=[], clock=Clock(86400 * 11))
    app = make_app(guild)
    battle = _fight()
    node = world.node("wilds")
    app._log_fight(battle, node)
    assert battle.sink is None                                  # the recorder is off

    from gartok.group import Group
    unit = encounters.build_enemy(1)
    guild = Guild(None, groups=[Group([unit], node="wilds")], clock=Clock(86400 * 11))
    app.guild = guild
    assert recorder.attach(str(tmp_path / "world"), guild)
    try:
        app._log_fight(battle, node)
        path = battle.sink.path
        assert path == os.path.join(str(tmp_path / "world"), "combat_logs", "d012-wilds-hunt.jsonl") or \
            os.path.basename(path).startswith("d012-wilds-")
        assert os.path.dirname(path).endswith("combat_logs")
        second = _fight()
        app._log_fight(second, node)
        assert second.sink.path != path
    finally:
        recorder.detach()


def test_the_combat_log_path_is_none_while_detached():
    recorder.detach()
    assert recorder.combat_log_path("anything") is None


# ---- reading it back ----------------------------------------------------- #

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


def _lab_log(tmp_path, name, controllers, seed=5):
    battle, meta = combat_lab.build("scrapper", 0, 3, seed=seed)
    log = combat_log.CombatLog(str(tmp_path / name), meta, controllers)
    battle.record_to(log)
    _play(battle)
    log.end(battle)
    return battle


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
    assert combat_pairs.drift(rows) == []


def test_a_fight_with_an_objective_of_its_own_is_not_rebuilt(tmp_path):
    battle, meta = combat_lab.build("ctf", 2, 3, seed=5)
    log = combat_log.CombatLog(str(tmp_path / "ctf.jsonl"), meta, HUMAN_AI)
    battle.record_to(log)
    log.end(battle)
    with pytest.raises(ValueError):
        combat_log.rebuild(combat_log.load(log.path))


def test_the_pairs_script_gives_the_same_ai_rate_every_run(tmp_path):
    _lab_log(tmp_path, "mine.jsonl", HUMAN_AI)
    rows = combat_log.load(str(tmp_path / "mine.jsonl"))
    first = combat_pairs.ai_win_rate(lambda: combat_log.rebuild(rows), 3)
    assert 0 <= first <= 1
    assert combat_pairs.ai_win_rate(lambda: combat_log.rebuild(rows), 3) == first


def test_the_lab_has_a_tutorial_card_with_copy():
    from gartok import i18n
    from gartok.tutorial import TUTORIALS
    assert "combat_lab" in TUTORIALS and i18n.has("tutorial.combat_lab.title")
    assert CombatLabScreen(ui_fonts(), lambda s: None, lambda: None).tutorial_key() == "combat_lab"
