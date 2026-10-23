import pygame
import pytest

from gartok import persist, settings
from gartok.app import App
from gartok.settings_screen import SettingsScreen
from gartok.start_screen import StartScreen
from gartok.ui.tokens import T
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

    # Switch tabs and verify drawing works on each
    recipes_rect = next(r for tid, r in screen.tab_buttons if tid == "recipes")
    screen._click(recipes_rect.center)
    assert screen.tab == "recipes"
    screen.draw(surf)

    talents_rect = next(r for tid, r in screen.tab_buttons if tid == "talents")
    screen._click(talents_rect.center)
    assert screen.tab == "talents"
    screen.draw(surf)

    beasts_rect = next(r for tid, r in screen.tab_buttons if tid == "beasts")
    screen._click(beasts_rect.center)
    assert screen.tab == "beasts"
    screen.draw(surf)

    rules_rect = next(r for tid, r in screen.tab_buttons if tid == "rules")
    screen._click(rules_rect.center)
    assert screen.tab == "rules"
    screen.draw(surf)

    # Search filter keydown and redraw
    event = pygame.event.Event(pygame.KEYDOWN, unicode="a", key=pygame.K_a)
    screen.handle_event(event)
    assert screen.search_query == "a"
    screen.draw(surf)

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


def test_the_world_row_carries_the_banner_vocation_and_faces(tmp_path, monkeypatch):
    from gartok.guild import Guild
    from gartok.unit import Unit
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    from gartok.group import Group
    units = [Unit("Fighter") for _ in range(3)]
    for i, u in enumerate(units):
        u.name = f"M{i}"
    g = Guild(None, groups=[Group(units, node="city")])
    g.vocation, g.banner_color, g.banner_icon = "caravan", (10, 20, 30), "wolf-head"
    persist.save_game("w1", g)
    row = persist.list_worlds()[0]
    assert (row["vocation"], tuple(row["banner_color"]), row["banner_icon"]) == ("caravan", (10, 20, 30),
                                                                               "wolf-head")
    assert [f["name"] for f in row["faces"]] == ["M0", "M1", "M2"]
    assert all(f["race"] == u.race["name"] for f, u in zip(row["faces"], units))


def _start(monkeypatch, worlds, size):
    monkeypatch.setattr(persist, "list_worlds", lambda: worlds)
    got = []
    screen = StartScreen(ui_fonts(), lambda: got.append("continue"), *[lambda: None] * 6)
    screen.draw(pygame.Surface(size))
    return screen, got


WORLD = {"world": "w", "name": "The Iron Ravens", "day": 5, "squad": ["A", "B"], "battles_won": 3,
         "saved_at": 1700000000, "vocation": "wilds", "banner_color": [200, 60, 50], "banner_icon": "wolf-head",
         "faces": [{"name": "A", "race": "Orc", "portrait": 1}, {"name": "B", "race": "Elf", "portrait": 2}]}


def test_clicking_the_last_guild_continues_it(monkeypatch):
    screen, got = _start(monkeypatch, [WORLD], (1920, 1080))
    assert screen.campaign_rect is not None
    screen._click(screen.campaign_rect.center)
    assert got == ["continue"]


def test_with_no_guild_new_game_is_the_primary_and_there_is_no_card(monkeypatch):
    screen, _ = _start(monkeypatch, [], (1920, 1080))
    assert screen.campaign_rect is None
    assert screen._menu()[1]["key"] == "new" and screen._menu()[1]["primary"]


def test_the_menu_fits_every_window(monkeypatch):
    for size in ((1024, 640), (1280, 720), (1920, 1080), (2560, 1440)):
        screen, _ = _start(monkeypatch, [WORLD], size)
        assert all(r.bottom <= size[1] - T.S * 6 for _, r, _ in screen.buttons), size
        assert len({r.y for _, r, _ in screen.buttons}) == len(screen.buttons)
