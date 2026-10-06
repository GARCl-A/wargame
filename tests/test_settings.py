"""Player preferences (settings.py) and what reads them."""

import os

import pygame
import pytest

from gartok import settings
from tests.test_battle_input import _screen

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


@pytest.fixture(autouse=True)
def _tmp_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PATH", str(tmp_path / "settings.json"))
    settings.reload()
    yield
    settings.reload()


def test_defaults_when_there_is_no_file():
    assert settings.get("chord_ms") == 40


def test_cycle_wraps_and_persists():
    choices = settings.SPEC["chord_ms"][1]
    seen = [settings.cycle("chord_ms") for _ in choices]
    assert seen[-1] == settings.get("chord_ms") == 40 and set(seen) == set(choices)
    settings.cycle("chord_ms")
    stored = settings.get("chord_ms")
    settings.reload()
    assert settings.get("chord_ms") == stored


def test_a_corrupt_or_foreign_value_falls_back_to_the_default():
    with open(settings.PATH, "w", encoding="utf-8") as f:
        f.write('{"chord_ms": 12345}')
    assert settings.get("chord_ms") == 40
    with open(settings.PATH, "w", encoding="utf-8") as f:
        f.write("not json")
    settings.reload()
    assert settings.get("chord_ms") == 40


def test_the_chord_window_follows_the_setting():
    scr, _ = _screen()
    scr.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
    assert scr._chord_ms == 40
    while settings.get("chord_ms") != 100:
        settings.cycle("chord_ms")
    scr._chord = set()
    scr.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT))
    assert scr._chord_ms == 100


def test_the_pause_menu_cycles_a_setting():
    from gartok.pause_screen import PauseScreen
    from gartok.ui.tokens import fonts
    pygame.init()
    pause = PauseScreen(fonts(), None, lambda: None, lambda: None, lambda: None)
    pause.draw(pygame.Surface((1280, 720)))
    rect = dict(pause._buttons)["set_chord_ms"]
    pause._click(rect.center)
    assert settings.get("chord_ms") == 70
