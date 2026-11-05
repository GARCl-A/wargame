"""Minimal i18n: dotted-key string catalogs loaded from `locales/<lang>.json`.

A catalog is authored as nested JSON (groups related strings the way the rest
of the game's data lives -- see `npc_lib.py`/`map_lib.py` for the same
"git-tracked JSON at the repo root" idiom) and flattened at load time into
dotted keys ("tutorial.map.title") for lookup. `t()` falls back current
language -> `en` -> the key itself, so a missing string shows up on screen as
its own key instead of crashing or rendering blank -- a gap is obvious the
moment you look at the screen.

Plan, phases and decisions: docs/plans/translation_pt_br.md. Beyond `t()` the
module offers `plural()` (a `one`/`other` pair) and `name()` (the shown name of a
catalog thing, which falls back to its id, so the id never depends on the text).
"""

import json
import os
import string

LOCALES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "locales")
DEFAULT_LANG = "en"
LANGUAGES = {"en": "English", "pt-br": "Português (Brasil)"}    # each written in its own language

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
    if code not in LANGUAGES:
        raise ValueError(f"no language called {code}")
    _lang = code


def language():
    return _lang


def has(key):
    """Whether `key` resolves to a real authored value (current language, or
    the `en` fallback) -- lets a caller tell "no such string" apart from a
    string that happens to look like its own key, which comparing `t(key)`
    against the key itself cannot."""
    return key in _catalog(_lang) or key in _catalog(DEFAULT_LANG)


def t(key, **fmt):
    """A string, or a list of strings (paragraphs) for keys authored as a JSON
    array -- callers that expect prose (e.g. `primitives.wrap`) already take a
    list of lines, so a multi-paragraph value needs no special-casing."""
    value = _catalog(_lang).get(key)
    if value is None and _lang != DEFAULT_LANG:
        value = _catalog(DEFAULT_LANG).get(key)
    if value is None:
        return key
    if isinstance(value, list):
        return [v.format(**fmt) if fmt else v for v in value]
    return value.format(**fmt) if fmt else value


def sentence(text):
    """`text` opening a sentence: its first letter in capitals, the rest as written."""
    return text[:1].upper() + text[1:]


def count(noun, n):
    """`n` of a counted thing: `count.<noun>.one` / `.other` in the catalog ("3 days")."""
    return plural(f"count.{noun}", n)


def plural(key, n, **fmt):
    """`key.one` when `n == 1`, else `key.other`; `{n}` is always a placeholder. Portuguese reads 0 as
    plural ("0 dias") like English, so the two forms are all either language needs."""
    return t(f"{key}.{'one' if n == 1 else 'other'}", n=n, **fmt)


def plural_key(key, n):
    """The key of the form `n` takes: for a log line, whose text is made by `battle.log(key, **params)`."""
    return f"{key}.{'one' if n == 1 else 'other'}"


def _lookup(key):
    value = _catalog(_lang).get(key)
    if value is None and _lang != DEFAULT_LANG:
        value = _catalog(DEFAULT_LANG).get(key)
    return value


def name(kind, ident):
    """The shown name of a catalog thing (`name.<kind>.<id>`), or `ident` itself when no one wrote it. An
    entry is a string, or `{"name": ..., "gender": "m" | "f"}` when an article depends on it (the loader
    flattens that into `...<id>.name` and `...<id>.gender`)."""
    key = f"name.{kind}.{ident}"
    for lang in dict.fromkeys((_lang, DEFAULT_LANG)):
        cat = _catalog(lang)
        value = cat.get(key, cat.get(f"{key}.name"))
        if value is not None:
            return value
    return ident


def desc(kind, ident, **fmt):
    """The description of a catalog thing (`desc.<kind>.<id>`), `""` when no one wrote it."""
    key = f"desc.{kind}.{ident}"
    return t(key, **fmt) if has(key) else ""


def gender(kind, ident):
    """`"m"` or `"f"` of a catalog name (`"m"` when the entry carries none)."""
    return _lookup(f"name.{kind}.{ident}.gender") or "m"


def placeholders(text):
    """The `{name}` fields a string or a list of strings uses."""
    lines = text if isinstance(text, list) else [text]
    return {f for line in lines for _, f, _, _ in string.Formatter().parse(line) if f}


def group(prefix):
    """Every string under `prefix.` in the current language, `en` filling the gaps, keyed without the
    prefix: the text the browser client asks for once, before it draws a screen."""
    cut = len(prefix) + 1
    out = {}
    for lang in dict.fromkeys((DEFAULT_LANG, _lang)):
        out.update({k[cut:]: v for k, v in _catalog(lang).items() if k.startswith(prefix + ".")})
    return out


def catalog(lang):
    """The flattened catalog of `lang` (a copy), for the parity tests and the audit."""
    return dict(_catalog(lang))


class Ref:
    """A catalog thing named inside a message (`Ref("ability", "halfling_luck", "Halfling Luck")`): it is
    stored by kind and id and shown at render time with `name()`, so the same line reads in any
    language; `default` (the registry's own name) shows when no one wrote a catalog name yet."""

    def __init__(self, kind, ident, default=None, lower=False):
        self.kind, self.ident, self.default, self.lower = kind, ident, default, lower

    def __str__(self):
        shown = name(self.kind, self.ident)
        shown = self.default if shown == self.ident and self.default else shown
        return shown.lower() if self.lower else shown

    def article(self):
        return gender(self.kind, self.ident)


class Msg:
    """A message kept as its key and parameters instead of its text: the combat log stores these so a
    fight reads in any language. A parameter may be a `Ref` or another `Msg`."""

    def __init__(self, key, **params):
        self.key, self.params = key, params

    def __str__(self):
        return t(self.key, **{k: str(v) if isinstance(v, (Msg, Ref)) else v for k, v in self.params.items()})

    def to_json(self):
        return {"k": self.key, "p": {k: _param_json(v) for k, v in self.params.items()}}


def _param_json(v):
    if isinstance(v, Msg):
        return v.to_json()
    if isinstance(v, Ref):
        return {"ref": [v.kind, v.ident, v.default, v.lower]}
    return v


def from_json(data):
    """The text of a stored `Msg.to_json()` (or a plain string) in the current language."""
    if isinstance(data, str):
        return data

    def param(v):
        if isinstance(v, dict) and "k" in v:
            return from_json(v)
        if isinstance(v, dict) and "ref" in v:
            return str(Ref(*v["ref"]))
        return v
    return t(data["k"], **{k: param(v) for k, v in data.get("p", {}).items()})


class Text:
    """A class attribute whose value is the catalog string `<prefix>.<owner.id>.<field>` in the current
    language, read on every access (`""` when the owner has none)."""

    def __init__(self, prefix, field, **fmt):
        self.key, self.fmt = (prefix, field), fmt

    def __get__(self, obj, owner):
        key = f"{self.key[0]}.{owner.id}.{self.key[1]}"
        return t(key, **self.fmt) if has(key) else ""
