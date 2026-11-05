"""The browser client's text: every key its scripts and pages read exists in `ui.*`, and the server serves it."""

import re
from pathlib import Path

from gartok import i18n
from gartok.web import server

CLIENT = Path(server.CLIENT)
KEY = r"([a-z_]+(?:\.[a-z_]+)+)"


def _used():
    keys = set()
    for path in CLIENT.rglob("*"):
        if path.suffix not in (".js", ".html"):
            continue
        text = path.read_text(encoding="utf-8")
        keys |= {(path.name, k) for k in re.findall(rf'\btr\("{KEY}"', text)}
        keys |= {(path.name, k + ".one") for k in re.findall(rf'\btrn\("{KEY}"', text)}
        keys |= {(path.name, f"unit.{w}.one") for w in re.findall(r'\bplural\([^,]+, "(\w+)"\)', text)}
        keys |= {(path.name, k) for k in re.findall(rf'data-t(?:-tip)?="{KEY}"', text)}
    return keys


def test_every_key_the_client_reads_is_in_the_catalog():
    have = i18n.group("ui")
    missing = sorted(f"{f}: {k}" for f, k in _used() if k not in have)
    assert not missing, missing


def test_the_ui_group_is_served_without_its_prefix():
    ui = i18n.group("ui")
    assert ui["settings.title"] == "Settings"
    assert "ui.settings.title" not in ui


def test_the_group_falls_back_to_english_for_a_missing_key(monkeypatch):
    monkeypatch.setitem(i18n._cache, "x", {"ui.a": "só um"})
    monkeypatch.setitem(i18n.LANGUAGES, "x", "X")
    monkeypatch.setattr(i18n, "_lang", "x")
    ui = i18n.group("ui")
    assert ui["a"] == "só um" and ui["settings.title"] == "Settings"
