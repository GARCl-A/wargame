"""RULES.md stays true: what it names in backticks exists, and a constant's quoted value is the live one."""

import importlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES = (ROOT / "RULES.md").read_text(encoding="utf-8")
SKIP_DIRS = {".git", "saves", "node_modules", "__pycache__", ".venv", "venv", "scratch"}


def _tokens():
    for number, line in enumerate(RULES.splitlines(), 1):
        for token in re.findall(r"`([^`\n]+)`", line):
            yield number, token.strip()


def _sources():
    """{path: text} of every module of gartok/ (the game; the Editor is another package)."""
    return {p: p.read_text(encoding="utf-8") for p in (ROOT / "gartok").rglob("*.py")}


SOURCES = _sources()
ALL_SOURCE = "\n".join(SOURCES.values())


def _module_source(stem):
    """`stem.py`, its mixins `stem_*.py` and, for a package, every file in it; None for a non-module."""
    found = [text for p, text in SOURCES.items()
             if p.parent == ROOT / "gartok" and (p.stem == stem or p.stem.startswith(stem + "_"))
             or p.parent == ROOT / "gartok" / stem]
    return "\n".join(found) or None


def _has_word(text, word):
    return re.search(rf"\b{re.escape(word)}\b", text) is not None


def test_every_file_rules_names_exists():
    have = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*")
            if not SKIP_DIRS.intersection(p.relative_to(ROOT).parts)
            and (p.relative_to(ROOT).parts[0] != "editor" or ROOT.name == "editor")]
    have += [path for path in (p.relative_to(ROOT).as_posix() for p in (ROOT / "editor").rglob("*"))
             if f"`{path}`" in RULES]
    ghosts = sorted({f"line {n}: {t}" for n, t in _tokens()
                     if re.fullmatch(r"[\w/.-]+\.(py|json|md)", t)
                     and not any(path == t or path.endswith("/" + t) for path in have)})
    assert not ghosts, f"RULES.md names files that do not exist: {ghosts}"


def test_every_module_attribute_rules_names_exists():
    ghosts = []
    for number, token in _tokens():
        match = re.fullmatch(r"([a-z_][a-z0-9_]*)\.([A-Za-z_]\w*)(?:\.\w+)*(?:\(.*\))?", token)
        if not match:
            continue
        module, attribute = match.groups()
        if attribute in ("py", "json", "md"):
            continue
        source = _module_source(module)
        if source is not None and not _has_word(source, attribute):
            ghosts.append(f"line {number}: {token}")
    assert not ghosts, f"RULES.md names a module attribute that is gone: {ghosts}"


def test_every_class_and_constant_rules_names_exists():
    ghosts = []
    for number, token in _tokens():
        bare = re.sub(r"\(.*\)$", "", token)
        parts = bare.split(".")
        for part in parts:
            if re.fullmatch(r"[A-Z][A-Z0-9_]{3,}", part) or re.fullmatch(r"[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+", part):
                if not _has_word(ALL_SOURCE, part) and not _has_word(_editor_source(), part):
                    ghosts.append(f"line {number}: {token}")
                break
        else:
            match = re.fullmatch(r"([A-Z][A-Za-z]+)\.([A-Za-z_]\w*)", bare)
            if match and (not re.search(rf"class {match.group(1)}\b", ALL_SOURCE)
                          or not _has_word(ALL_SOURCE, match.group(2))):
                ghosts.append(f"line {number}: {token}")
    assert not ghosts, f"RULES.md names a class or constant that is gone: {sorted(set(ghosts))}"


_EDITOR = []


def _editor_source():
    if not _EDITOR:
        _EDITOR.append("\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "editor").rglob("*.py")))
    return _EDITOR[0]


def test_a_constant_quoted_with_its_value_still_has_it():
    pair = re.compile(r"`(?:(\w+)\.)?([A-Z][A-Z0-9_]{3,})(?: = ([\d.,]+))?`"
                      r"(?:\s*[(=,]\s*\**\$?\**([\d][\d,]*(?:\.\d+)?))?")
    drift = []
    for number, line in enumerate(RULES.splitlines(), 1):
        for prefix, name, inline, after in pair.findall(line):
            said = inline or after
            if not said:
                continue
            module = _defining_module(prefix, name)
            if module is None:
                continue
            value = getattr(importlib.import_module(f"gartok.{module}"), name)
            if isinstance(value, (int, float)) and float(said.replace(",", "")) != float(value):
                drift.append(f"line {number}: {name} is {value}, RULES.md says {said}")
    assert not drift, f"RULES.md quotes a constant that changed: {drift}"


def _defining_module(prefix, name):
    for path, text in SOURCES.items():
        if path.parent != ROOT / "gartok":
            continue
        if prefix and path.stem != prefix:
            continue
        if re.search(rf"^{name}\s*=", text, re.M):
            return path.stem
    return None
