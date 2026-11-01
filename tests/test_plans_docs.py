"""The plans, the economy sim doc and tests/README.md keep pointing at things that exist: links resolve, the
files, tests and `module.NAME` references they name are real, and no plan is an orphan the backlog forgot."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLANS = ROOT / "docs" / "plans"
DOCS = [*sorted(p for p in PLANS.glob("*.md") if p.name != "clean_documentation_checklist.md"),
        ROOT / "docs" / "economy_sim.md", ROOT / "tests" / "README.md"]
PROPOSED = {"gartok/version.py"}        # a file an open backlog item says to create
TEXT = {p: p.read_text(encoding="utf-8") for p in DOCS}


def _ids(pattern):
    return [(p.relative_to(ROOT).as_posix(), m) for p, t in TEXT.items() for m in re.findall(pattern, t)]


def test_every_link_resolves():
    broken = [f"{doc}: {t}" for doc, t in _ids(r"\]\(([^)#\s]+)\)")
              if not t.startswith("http") and not (ROOT / doc).parent.joinpath(t).resolve().exists()]
    assert not broken, broken


def test_every_file_they_name_exists():
    named = _ids(r"`((?:gartok|scripts|tests|docs|editor)/[\w./-]+\.(?:py|md|js|json))")
    missing = [f"{doc}: {path}" for doc, path in named
               if path not in PROPOSED and not (ROOT / path).exists()]
    assert not missing, missing


def test_every_test_they_name_exists():
    named = _ids(r"`(test_\w+\.py)::(test_\w+)`")
    missing = [f"{doc}: {f}::{name}" for doc, (f, name) in named
               if f"def {name}" not in (ROOT / "tests" / f).read_text(encoding="utf-8")]
    assert named and not missing, missing


def test_every_module_attribute_they_name_exists():
    missing = []
    for doc, (mod, name) in _ids(r"`([a-z_]+)\.(?!(?:py|md|js|json)\b)([A-Za-z_]\w+)"):
        for folder in ("gartok", "scripts"):
            path = ROOT / folder / f"{mod}.py"
            if path.is_file():
                if not re.search(rf"\b{name}\b", path.read_text(encoding="utf-8")):
                    missing.append(f"{doc}: {mod}.{name}")
                break
    assert not missing, missing


def test_no_plan_is_forgotten_by_the_backlog():
    backlog = (PLANS / "backlog.md").read_text(encoding="utf-8")
    forgotten = [p.name for p in PLANS.glob("*.md")
                 if p.name not in ("backlog.md", "clean_documentation_checklist.md") and p.name not in backlog]
    assert not forgotten, f"plans the backlog does not point to: {forgotten}"


def test_the_sim_scripts_point_at_a_doc_that_exists():
    pointers = [(s.name, d) for s in (ROOT / "scripts").glob("economy_*.py")
                for d in re.findall(r"(docs/[\w/]+\.md)", s.read_text(encoding="utf-8"))]
    assert pointers
    assert not [(s, d) for s, d in pointers if not (ROOT / d).exists()]
