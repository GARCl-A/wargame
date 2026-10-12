import pygame
import pytest

from gartok import persist, settings
from gartok.app import App
from gartok.settings_screen import SettingsScreen
from gartok.start_screen import StartScreen
from gartok.ui.tokens import fonts as ui_fonts
from gartok.wiki_screen import WikiScreen


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()


def test_start_screen_renders_and_click_callbacks():
    F = ui_fonts()
    surf = pygame.Surface((1280, 720))
    actions = []

    screen = StartScreen(
        F,
        on_continue=lambda: actions.append("continue"),
        on_new=lambda: actions.append("new"),
        on_load=lambda: actions.append("load"),
        on_editor=lambda: actions.append("editor"),
        on_settings=lambda: actions.append("settings"),
        on_wiki=lambda: actions.append("wiki"),
        on_quit=lambda: actions.append("quit"),
    )

    screen.draw(surf)
    assert len(screen.buttons) == 7

    btn_map = {k: rect for k, rect, _ in screen.buttons}

    # Click new
    screen._click(btn_map["new"].center)
    assert actions == ["new"]

    # Click load
    screen._click(btn_map["load"].center)
    assert actions == ["new", "load"]

    # Click editor
    screen._click(btn_map["editor"].center)
    assert actions == ["new", "load", "editor"]

    # Click settings
    screen._click(btn_map["settings"].center)
    assert actions == ["new", "load", "editor", "settings"]

    # Click wiki
    screen._click(btn_map["wiki"].center)
    assert actions == ["new", "load", "editor", "settings", "wiki"]

    # Click quit
    screen._click(btn_map["quit"].center)
    assert actions == ["new", "load", "editor", "settings", "wiki", "quit"]


def test_start_screen_continue_with_and_without_worlds(monkeypatch, tmp_path):
    F = ui_fonts()
    surf = pygame.Surface((1280, 720))
    actions = []

    # Mock no worlds
    monkeypatch.setattr(persist, "list_worlds", lambda: [])
    screen = StartScreen(
        F,
        on_continue=lambda: actions.append("continue"),
        on_new=lambda: None,
        on_load=lambda: None,
        on_editor=lambda: None,
        on_settings=lambda: None,
        on_wiki=lambda: None,
        on_quit=lambda: None,
    )
    screen.draw(surf)
    btn_map = {k: (rect, en) for k, rect, en in screen.buttons}
    assert btn_map["continue"][1] is False
    screen._click(btn_map["continue"][0].center)
    assert actions == []

    # Mock existing world
    mock_world = [{
        "world": "test_world",
        "name": "The Iron Ravens",
        "day": 5,
        "squad": ["A", "B", "C"],
        "battles_won": 3,
        "saved_at": 1700000000,
    }]
    monkeypatch.setattr(persist, "list_worlds", lambda: mock_world)
    screen_with_world = StartScreen(
        F,
        on_continue=lambda: actions.append("continue"),
        on_new=lambda: None,
        on_load=lambda: None,
        on_editor=lambda: None,
        on_settings=lambda: None,
        on_wiki=lambda: None,
        on_quit=lambda: None,
    )
    screen_with_world.draw(surf)
    btn_map2 = {k: (rect, en) for k, rect, en in screen_with_world.buttons}
    assert btn_map2["continue"][1] is True
    screen_with_world._click(btn_map2["continue"][0].center)
    assert actions == ["continue"]


def test_settings_screen():
    F = ui_fonts()
    surf = pygame.Surface((1280, 720))
    back = []

    screen = SettingsScreen(F, on_back=lambda: back.append(1))
    screen.draw(surf)

    # Click back button
    back_rect = next(r for k, r in screen.buttons if k == "back")
    screen._click(back_rect.center)
    assert back == [1]

    # Test escape
    screen.handle_escape()
    assert back == [1, 1]


def test_wiki_screen_navigation():
    F = ui_fonts()
    surf = pygame.Surface((1280, 720))
    back = []

    screen = WikiScreen(F, on_back=lambda: back.append(1))
    screen.draw(surf)
    assert screen.tab == "items"

    # Switch tabs
    recipes_rect = next(r for tid, r in screen.tab_buttons if tid == "recipes")
    screen._click(recipes_rect.center)
    assert screen.tab == "recipes"

    talents_rect = next(r for tid, r in screen.tab_buttons if tid == "talents")
    screen._click(talents_rect.center)
    assert screen.tab == "talents"

    beasts_rect = next(r for tid, r in screen.tab_buttons if tid == "beasts")
    screen._click(beasts_rect.center)
    assert screen.tab == "beasts"

    rules_rect = next(r for tid, r in screen.tab_buttons if tid == "rules")
    screen._click(rules_rect.center)
    assert screen.tab == "rules"

    # Search filter keydown
    event = pygame.event.Event(pygame.KEYDOWN, unicode="a", key=pygame.K_a)
    screen.handle_event(event)
    assert screen.search_query == "a"

    # Back
    back_rect = next(r for k, r in screen.buttons if k == "back")
    screen._click(back_rect.center)
    assert back == [1]


def test_app_start_screen_integration():
    app = App()
    assert isinstance(app.scene, StartScreen)

    # Open settings from start screen
    app._open_settings()
    assert isinstance(app.scene, SettingsScreen)
    app.scene.handle_escape()
    assert isinstance(app.scene, StartScreen)

    # Open wiki from start screen
    app._open_wiki()
    assert isinstance(app.scene, WikiScreen)
    app.scene.handle_escape()
    assert isinstance(app.scene, StartScreen)

    # Open load game (MenuScreen) from start screen
    app._start_menu()
    from gartok.menu_screen import MenuScreen
    assert isinstance(app.scene, MenuScreen)
    app.scene.handle_escape()
    assert isinstance(app.scene, StartScreen)
