"""Minimal i18n: dotted-key string catalogs loaded from `locales/<lang>.json`.

A catalog is authored as nested JSON (groups related strings the way the rest
of the game's data lives -- see `npc_lib.py`/`map_lib.py` for the same
"git-tracked JSON at the repo root" idiom) and flattened at load time into
dotted keys ("tutorial.map.title") for lookup. `t()` falls back current
language -> `en` -> the key itself, so a missing string shows up on screen as
its own key instead of crashing or rendering blank -- a gap is obvious the
moment you look at the screen.

Only the tutorial (`tutorial.py`) reads this today; nothing else in the game
has been converted, on purpose -- this module is the framework, not a
translation pass.
"""

import json
import os

LOCALES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "locales")
DEFAULT_LANG = "en"

_cache = {}          # lang -> flattened {dotted key: str | list[str]}
_lang = DEFAULT_LANG


def _flatten(node, prefix=""):
    out = {}
    for k, v in node.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = v
    return out


def _catalog(lang):
    if lang not in _cache:
        path = os.path.join(LOCALES_DIR, f"{lang}.json")
        try:
            with open(path, encoding="utf-8") as fh:
                _cache[lang] = _flatten(json.load(fh))
        except FileNotFoundError:
            _cache[lang] = {}
    return _cache[lang]


def set_language(code):
    global _lang
    _lang = code


def language():
    return _lang


def available_languages():
    if not os.path.isdir(LOCALES_DIR):
        return []
    return sorted(f[:-len(".json")] for f in os.listdir(LOCALES_DIR) if f.endswith(".json"))


def has(key):
    """Whether `key` resolves to a real authored value (current language, or
    the `en` fallback) -- lets a caller tell "no such string" apart from a
    string that happens to look like its own key, which comparing `t(key)`
    against the key itself cannot."""
    return key in _catalog(_lang) or key in _catalog(DEFAULT_LANG)


def t(key, **fmt):
    """A string, or a list of strings (paragraphs) for keys authored as a JSON
    array -- callers that expect prose (e.g. `theme.wrap_lines`) already take a
    list of lines, so a multi-paragraph value needs no special-casing."""
    value = _catalog(_lang).get(key)
    if value is None and _lang != DEFAULT_LANG:
        value = _catalog(DEFAULT_LANG).get(key)
    if value is None:
        return key
    if isinstance(value, list):
        return [v.format(**fmt) if fmt else v for v in value]
    return value.format(**fmt) if fmt else value
