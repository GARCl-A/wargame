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
    assert settings.get("volume") == 75


def test_cycle_wraps_and_persists():
    choices = settings.SPEC["volume"][1]
    seen = [settings.cycle("volume") for _ in choices]
    assert seen[-1] == settings.get("volume") == 75 and set(seen) == set(choices)
    settings.cycle("volume")
    stored = settings.get("volume")
    settings.reload()
    assert settings.get("volume") == stored


def test_the_log_limit_takes_any_number_inside_its_range_and_steps_up_from_there():
    settings.put("log_lines", 3000)
    settings.reload()
    assert settings.get("log_lines") == 3000 and settings.next_choice("log_lines") == 5000
    with pytest.raises(ValueError):
        settings.put("log_lines", 10)
    settings.put("log_lines", 9000)
    assert settings.next_choice("log_lines") is None and settings.step_up("log_lines") == 9000


def test_a_corrupt_or_foreign_value_falls_back_to_the_default():
    with open(settings.PATH, "w", encoding="utf-8") as f:
        f.write('{"volume": 12345}')
    assert settings.get("volume") == 75
    with open(settings.PATH, "w", encoding="utf-8") as f:
        f.write("not json")
    settings.reload()
    assert settings.get("volume") == 75
