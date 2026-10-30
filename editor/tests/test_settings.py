"""Player preferences (settings.py) and what reads them."""

import pygame
import pytest
from gartok import settings
from editor.tests.test_battle_input import _screen

@pytest.fixture(autouse=True)
def _tmp_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PATH", str(tmp_path / "settings.json"))
    settings.reload()
    yield
    settings.reload()


def test_the_chord_window_follows_the_setting():
    scr, _ = _screen()
    scr.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
    assert scr._chord_ms == 40
    while settings.get("chord_ms") != 100:
        settings.cycle("chord_ms")
    scr._chord = set()
    scr.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT))
    assert scr._chord_ms == 100
