"""README.md's code map stays true: every module is in it, and every file it names exists."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
SKIP_DIRS = {".git", "saves", "node_modules", "__pycache__", ".venv", "venv", "scratch"}


def _tracked_basenames():
    names = set()
    for path in ROOT.rglob("*.py"):
        if not SKIP_DIRS.intersection(path.relative_to(ROOT).parts):
            names.add(path.name)
    return names


def test_every_module_of_gartok_is_in_the_readme_map():
    missing = [p.name for p in sorted((ROOT / "gartok").glob("*.py"))
               if p.name not in ("__init__.py", "__main__.py")
               and not re.search(rf"(?<![\w/.]){re.escape(p.name)}", README)]
    assert not missing, f"add to README's Structure: {missing}"


def test_every_package_of_gartok_is_in_the_readme_map():
    missing = [p.name for p in sorted((ROOT / "gartok").iterdir())
               if p.is_dir() and (p / "__init__.py").exists()
               and not re.search(rf"^\s+{p.name}/", README, re.M)]
    assert not missing, f"add to README's Structure: {missing}"


def test_every_file_the_readme_names_exists():
    have = _tracked_basenames()
    named = set(re.findall(r"(?<![\w.])([A-Za-z_][\w]*\.py)\b", README))
    ghosts = sorted(n for n in named if n not in have)
    assert not ghosts, f"README names files that do not exist: {ghosts}"
