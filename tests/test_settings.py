"""Player preferences (settings.py) and what reads them."""

import pytest
from gartok import settings

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
