"""Counts the literal English sentences left in `gartok/`: the number the translation (docs/plans/translation_pt_br.md)
drives to zero.

A sentence is a string constant, or an f-string, with a space and a letter in it that is not a docstring, a dict key,
a comparison operand, or an argument of an `assert`/`raise` of a bare invariant. It is a heuristic: it finds where to look,
not what to translate. `python scripts/i18n_audit.py [--top N] [--module NAME]`.
"""

import argparse
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "gartok"
SKIP_MODULES = {"i18n.py"}
WORDS = re.compile(r"[A-Za-z]{2,}\s+[A-Za-z]{2,}")


def _docstrings(tree):
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _excluded(tree):
    """ids of constants that are not shown text: dict keys, comparison operands, subscripts, `assert` messages."""
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            ids.update(id(k) for k in node.keys if k is not None)
        elif isinstance(node, ast.Compare):
            ids.update(id(n) for n in [node.left, *node.comparators])
            for n in [node.left, *node.comparators]:
                if isinstance(n, (ast.Tuple, ast.List, ast.Set)):
                    ids.update(id(e) for e in n.elts)
        elif isinstance(node, ast.Subscript):
            ids.add(id(node.slice))
        elif isinstance(node, ast.Assert) and node.msg is not None:
            ids.update(id(n) for n in ast.walk(node.msg))
    return ids


def sentences(path):
    """[(line, text)] of the literal sentences in one module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = _docstrings(tree) | _excluded(tree)
    out, inside = [], set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            inside.update(id(v) for v in node.values)
            text = "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values)
            if id(node) not in skip and WORDS.search(text):
                out.append((node.lineno, text))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip
                and id(node) not in inside and WORDS.search(node.value)):
            out.append((node.lineno, node.value))
    return sorted(out)


def audit():
    """{module path relative to gartok: [(line, text)]} for every module that still holds some."""
    found = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.name in SKIP_MODULES:
            continue
        hits = sentences(path)
        if hits:
            found[path.relative_to(PACKAGE).as_posix()] = hits
    return found


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=25, help="how many modules to list")
    p.add_argument("--module", help="print the sentences of one module (a path under gartok/)")
    args = p.parse_args()
    found = audit()
    if args.module:
        for line, text in found.get(args.module, []):
            print(f"{line:5}  {text[:110]!r}")
        return
    ranked = sorted(found.items(), key=lambda kv: -len(kv[1]))
    for mod, hits in ranked[:args.top]:
        print(f"{len(hits):5}  {mod}")
    print(f"{sum(map(len, found.values())):5}  total in {len(found)} modules")


if __name__ == "__main__":
    main()
