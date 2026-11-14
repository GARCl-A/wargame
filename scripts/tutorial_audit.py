"""Every tutorial card and hint, as the player meets it: size, where it fires, whether it can be read again.

Docs: docs/plans/onboarding_audit.md. One row per card: its words, the code that shows it, whether the screen's
`?` badge reopens it (a hint cannot be reopened once seen), the wiki entry its button opens and whether that
entry exists, the digits typed into its text (a rule's number should be a placeholder) and placeholders left
unfilled when the card is drawn.

    python scripts/tutorial_audit.py
"""

from __future__ import annotations

import importlib
import inspect
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gartok import actions, hints, tutorial, wiki_rules

LOCALE = os.path.join(ROOT, "locales", "en.json")
WEB = os.path.join(ROOT, "gartok", "web")
CARD_KEYS = ("title", "body", "button", "suggestion")
DIGIT = re.compile(r"(?<![{\w])\d[\d.,]*%?(?![^{]*})")


def _cards(node, prefix=""):
    found = {}
    for k, v in node.items():
        if isinstance(v, dict):
            if "title" in v and "body" in v:
                found[prefix + k] = v
            found.update(_cards(v, prefix + k + "."))
    return found


def _texts(card):
    """The card's own strings: body, suggestion and the rows it keeps in the locale (not a nested card)."""
    out = []
    for k, v in card.items():
        if k in ("title", "button"):
            continue
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, list):
            out += [s for s in v if isinstance(s, str)]
        elif isinstance(v, dict) and not ("title" in v and "body" in v):
            out += _texts(v)
    return out


def _sources():
    """The code that chooses a card: every session's `tutorial_key`, and the hub's tab-to-card map."""
    found = {}
    for name in sorted(os.listdir(WEB)):
        if not name.endswith(".py"):
            continue
        module = importlib.import_module(f"gartok.web.{name[:-3]}")
        for cls in vars(module).values():
            if inspect.isclass(cls) and cls.__module__ == module.__name__ and "tutorial_key" in vars(cls):
                found[f"{name[:-3]}.{cls.__name__}"] = inspect.getsource(cls.tutorial_key)
        if name == "hub_session.py":
            found["hub_session.TUTORIAL"] = repr(module.TUTORIAL)
    return found


def _fired_by(key, sources):
    """The session whose `tutorial_key` returns the card, or the hints function that fires it; "never" when none does."""
    if key in hints.IDS:
        const = next(n for n in ("STUDY", "ROAD", "READING", "FALLEN", "DUNGEON", "PLACE", "FLANK", "WILDS") if getattr(hints, n) == key)
        where = [f.__name__ for f in (hints.on_map, hints.in_battle) if f"{const} not in seen" in inspect.getsource(f)]
        return f"hints.{where[0]}" if where else "hints"
    quoted = re.compile(rf"""["']{re.escape(key)}["']""")
    hits = [name for name, src in sources.items() if quoted.search(src)]
    if not hits and key.startswith("guild."):
        hits = [name for name, src in sources.items() if 'f"guild.{self.tab}"' in src]
    return ", ".join(hits) if hits else "never"


def _wiki(key):
    ref = hints.wiki_ref(key) if key in hints.IDS else None
    if ref is None:
        return "-", ""
    chapter, entry = ref.split(":", 1)
    if chapter == "rules":
        ok = entry in [t for t, _ in wiki_rules.sections()]
    elif chapter == "actions":
        ok = entry in [a.id for a in actions.PANEL_ACTIONS]
    else:
        ok = False
    return ref, "" if ok else "MISSING"


def _unfilled(key):
    drawn = tutorial.card(key)
    strings = [drawn["title"], *drawn["body"], drawn["suggestion"] or ""]
    return sorted({m for s in strings for m in re.findall(r"\{\w+\}", s)})


def rows():
    with open(LOCALE, encoding="utf-8") as fh:
        cards = _cards(json.load(fh)["tutorial"])
    listed = list(tutorial.TUTORIALS)
    keys = listed + sorted(set(cards) - set(listed))
    sources = _sources()
    out = []
    for key in keys:
        texts = _texts(cards[key])
        ref, missing = _wiki(key)
        out.append({
            "card": key,
            "kind": "hint" if key in hints.IDS else "screen",
            "words": sum(len(t.split()) for t in texts),
            "fired by": _fired_by(key, sources),
            "? reopens": "no" if key in hints.IDS else "yes",
            "wiki": f"{ref} {missing}".strip(),
            "digits typed": " ".join(sorted({d for t in texts for d in DIGIT.findall(t)})),
            "unfilled": " ".join(_unfilled(key)),
            "listed": "" if key in listed else "not in TUTORIALS",
        })
    return out


def report():
    table = rows()
    cols = list(table[0])
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in table]
    hint_rows = [r for r in table if r["kind"] == "hint"]
    summary = (f"{len(table)} cards, {sum(r['words'] for r in table)} words; "
               f"{len(hint_rows)} hints that cannot be reopened, {sum(1 for r in hint_rows if r['wiki'] == '-')} of them with no wiki entry; "
               f"{sum(1 for r in table if r['fired by'] == 'never')} never shown; "
               f"{sum(1 for r in table if r['digits typed'])} cards with digits typed in; "
               f"{sum(1 for r in table if r['unfilled'])} with a placeholder left unfilled")
    lines += ["", summary]
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
