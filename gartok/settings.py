"""Player preferences: one small JSON beside the saves, shared by every guild.

`SPEC` is the whole catalog (key -> label, allowed values, default); the pause
menu builds one row per entry, so a new preference is one line here plus the
code that reads it with `get`.
"""

import json
import os

from . import persist

PATH = os.path.join(os.path.dirname(persist.SAVE_DIR), "settings.json")

SPEC = {
    "chord_ms": ("ARROW CHORD", (0, 20, 40, 70, 100), 40),
}

_values = None


def _load():
    global _values
    _values = {k: default for k, (_, _, default) in SPEC.items()}
    try:
        with open(PATH, encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return
    if isinstance(saved, dict):
        for k, (_, choices, _) in SPEC.items():
            if saved.get(k) in choices:
                _values[k] = saved[k]


def get(key):
    if _values is None:
        _load()
    return _values[key]


def cycle(key):
    """Step `key` to its next allowed value, wrapping, and save it."""
    choices = SPEC[key][1]
    nxt = choices[(choices.index(get(key)) + 1) % len(choices)]
    _values[key] = nxt
    try:
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(_values, f, indent=2)
    except OSError:
        pass
    return nxt


def label(key):
    name, _, _ = SPEC[key]
    value = get(key)
    return f"{name}: {value} MS" if key.endswith("_ms") else f"{name}: {value}"


def reload():
    global _values
    _values = None
