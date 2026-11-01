"""docs/web_ui/web_client.md keeps pointing at things that exist: the mockup table matches the folders, the
links resolve, and the desks, client files and session hooks it names are still in the code."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = ROOT / "docs" / "web_ui" / "web_client.md"
DOC = DOC_PATH.read_text(encoding="utf-8")
CLIENT = ROOT / "gartok" / "web" / "client"


def test_the_mockup_table_lists_exactly_the_mockup_folders():
    rows = set(re.findall(r"^\| `(\w+_mockup)/` \|", DOC, re.M))
    folders = {p.name for p in (DOC_PATH.parent / "references").iterdir() if p.is_dir()}
    assert rows == folders, f"table only: {sorted(rows - folders)}; folders only: {sorted(folders - rows)}"


def test_every_link_of_the_guide_resolves():
    broken = [t for t in re.findall(r"\]\(([^)#]+)\)", DOC)
              if not t.startswith("http") and not (DOC_PATH.parent / t).exists()]
    assert not broken, f"links that point nowhere: {broken}"


def test_every_desk_the_guide_names_is_a_class():
    desks = re.findall(r"`([a-z_]+)\.([A-Z]\w+)`", DOC)
    assert desks
    missing = [f"{m}.{c}" for m, c in desks
               if not re.search(rf"^class {c}\b", (ROOT / "gartok" / f"{m}.py").read_text(encoding="utf-8"), re.M)]
    assert not missing, f"desks that no longer exist: {missing}"


def test_the_client_files_and_hooks_the_guide_names_exist():
    for name in re.findall(r"`((?:kit|shell)\.(?:js|css))`", DOC):
        assert (CLIENT / name).exists(), name
    assert "const SCREENS" in (CLIENT / "shell.js").read_text(encoding="utf-8")
    sessions = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "gartok" / "web").glob("*.py"))
    for hook in ("hub_cards", "sheet_units", "tutorial_key"):
        assert f"def {hook}" in sessions, hook
    assert "const Tip" in (CLIENT / "kit.js").read_text(encoding="utf-8")
