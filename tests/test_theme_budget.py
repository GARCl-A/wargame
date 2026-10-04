"""`gartok/theme.py` is the legacy ramp -- `gartok/ui/` is where screens are
built now (see `gartok/ui/README.md`).

This pins the modules still importing `theme` so the list can only shrink: a
new import fails here, and a module that finishes its migration must be taken
off `STILL_ON_THEME` (the second test), so the budget never goes stale.
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parent.parent / "gartok"

# Why each still imports theme -- migrate the "screen" ones first:
STILL_ON_THEME = {
    # the board renderer's palette (floor, walls, highlights, token colours):
    # no `ui/` equivalent yet -- needs a board-palette home before theme can go
    "battle_screen.py", "battle_fx.py", "lighting.py",
    # the player/banner colour is runtime state `theme.set_player_color` mutates
    "app.py", "draft_screen.py", "ui/primitives.py", "ui/combat_card.py",
    # screens/panels still drawn with theme's spacing ramp, panel() and text()
    "screen.py", "sheet_panel.py", "tutorial_card.py",
    "char_editor_screen.py", "map_editor_screen.py",
}


def _imports_theme(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[-1] == "theme":
                return True
            if any(a.name == "theme" for a in node.names):
                return True
        elif isinstance(node, ast.Import):
            if any(a.name.split(".")[-1] == "theme" for a in node.names):
                return True
    return False


def _importers():
    return {p.relative_to(PKG).as_posix() for p in PKG.rglob("*.py")
            if p.name != "theme.py" and _imports_theme(p)}


def test_no_new_module_imports_the_legacy_theme():
    new = _importers() - STILL_ON_THEME
    assert not new, f"build on gartok/ui/ instead of theme.py: {sorted(new)}"


def test_the_theme_budget_has_no_stale_entries():
    done = STILL_ON_THEME - _importers()
    assert not done, f"migrated off theme -- remove from STILL_ON_THEME: {sorted(done)}"


def test_no_undefined_names_in_the_package():
    """A name used but never imported only blows up when that code path draws
    (the guard screen shipped once without `caps` imported)."""
    try:
        r = subprocess.run([sys.executable, "-m", "ruff", "check", str(PKG),
                            "--select", "F821", "--no-cache"],
                           capture_output=True, text=True)
    except OSError:
        pytest.skip("ruff unavailable")
    if "No module named ruff" in r.stderr:
        pytest.skip("ruff unavailable")
    assert r.returncode == 0, r.stdout
