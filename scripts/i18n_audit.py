"""Counts the literal English sentences left in `gartok/`: the number the translation (docs/plans/translation_pt_br.md)
drives to zero.

A sentence is a string constant, or an f-string, with a space and a letter in it that is not a docstring, a dict key,
a comparison operand, or an argument of an `assert`/`raise` of a bare invariant. It is a heuristic: it finds where to look,
not what to translate. `python scripts/i18n_audit.py [--top N] [--module NAME]`.
"""

import argparse
import ast
import functools
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "gartok"
SKIP_MODULES = {"i18n.py"}
EDITOR_ONLY = {"ATTRIBUTE_HELP", "DERIVED_HELP"}    # tables only the Editor reads (it is being redone, out of scope)
ID_STRINGS = {"Any Dictionary", "Dictionary of ", "Snake Dragon", "Treefolk Recruit"}    # a mission's goal: an item or beast id
# positional args that are catalog ids, not shown text: a node's default name (`name.node.<id>` wins), a keeper's race and role
ID_ARGS = {"Node": (1,), "Vendor": (1, 2)}
WORDS = re.compile(r"[A-Za-z]{2,}[:,.]?\s+[A-Za-z]{2,}|[A-Za-z]{2,}[:,.]?\s+\{|\}[:,.]?\s+[A-Za-z]{2,}")


@functools.cache
def _ids():
    """Strings that are the id of a catalog thing, not a sentence: an item or race called by its English name
    (the name is the key, `i18n.name` shows it), an alignment, a size."""
    import sys
    sys.path.insert(0, str(ROOT))
    from gartok import data, items
    return set(items.all_items()) | set(data.ALL_RACE_NAMES) | {a for _, a in data.ALIGNMENTS} | set(data.SIZE_ORDER)


def _docstrings(tree):
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _callee(call):
    """The name a call is made under: `Node` for `Node(...)` and `world.Node(...)`."""
    f = call.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None


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
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in EDITOR_ONLY for t in node.targets):
            ids.update(id(n) for n in ast.walk(node.value))
        elif isinstance(node, ast.Assert) and node.msg is not None:
            ids.update(id(n) for n in ast.walk(node.msg))
        elif isinstance(node, ast.Call) and _callee(node) in ID_ARGS:
            ids.update(id(node.args[i]) for i in ID_ARGS[_callee(node)] if i < len(node.args)
                       and isinstance(node.args[i], ast.Constant))
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
                and id(node) not in inside and node.value not in _ids() | ID_STRINGS and WORDS.search(node.value)):
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
