"""The combat log, the per-team controllers and the combat lab (combat_log.py, combat_lab.py,
battle_screen controllers, scripts/combat_analysis.py, scripts/combat_pairs.py)."""

import os
import random
import pygame
import pytest
from gartok import ai, combat_lab, combat_log, encounters, vision
from gartok.battle import Battle
from editor.battle_screen import BattleScreen
from editor.combat_lab_screen import CombatLabScreen
from editor.editor_menu_screen import EditorMenuScreen
from gartok.scenario import ErmosScenario, FlagScenario
from editor.ui.tokens import fonts as ui_fonts

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

def _screen(controllers=None, scenario=None):
    pygame.init()
    battle = _fight(scenario=scenario)
    screen = BattleScreen(ui_fonts(), battle, on_battle_end=lambda b: None, controllers=controllers)
    return screen, battle

def _lab():
    pygame.init()
    started = []
    screen = CombatLabScreen(ui_fonts(), started.append, lambda: None)
    screen.draw(pygame.Surface((1280, 800)))
    return screen, started


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
    from editor.editor_app import EditorApp
    monkeypatch.setattr(combat_lab, "ROOT", str(tmp_path))
    app = EditorApp.__new__(EditorApp)
    app.ui_fonts = ui_fonts()
    app._start_lab_fight({"fight": "scrapper", "level": 1, "squad": 3,
                          "controllers": {"player": "human", "enemy": "ai"}, "name": "first try"})
    assert isinstance(app.scene, BattleScreen)
    log = app.scene.battle.sink
    assert os.path.dirname(os.path.dirname(log.path)) == str(tmp_path) and log.path.endswith("first-try.jsonl")
    start = combat_log.load(log.path)[0]
    assert start["meta"]["source"] == "lab" and start["meta"]["fight"] == "scrapper"
    assert start["controllers"] == {"player": "human", "enemy": "ai"}


def test_the_lab_has_a_tutorial_card_with_copy():
    from gartok import i18n
    from gartok.tutorial import TUTORIALS
    assert "combat_lab" in TUTORIALS and i18n.has("tutorial.combat_lab.title")
    assert CombatLabScreen(ui_fonts(), lambda s: None, lambda: None).tutorial_key() == "combat_lab"
