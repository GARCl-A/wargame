"""Player preferences: one small JSON beside the saves, shared by every guild.

`SPEC` is the whole catalog (key -> label, allowed values, default); the pause
menu builds one row per entry, so a new preference is one line here plus the
code that reads it with `get`.
"""

import json
import os

from . import i18n, persist

PATH = os.path.join(os.path.dirname(persist.SAVE_DIR), "settings.json")

SPEC = {
    "record_play": ("settings.name.record_play", ("OFF", "ON"), "OFF"),
    "volume": ("settings.name.volume", (0, 25, 50, 75, 100), 75),
    "music": ("settings.name.music", (0, 25, 50, 75, 100), 50),
    "log_lines": ("settings.name.log_lines", (500, 1000, 2000, 5000), 2000),
    "language": ("settings.name.language", tuple(i18n.LANGUAGES), i18n.DEFAULT_LANG),
    "dice": ("settings.name.dice", ("full", "quick", "off"), "full"),
}

# A value the player types, within bounds; the choices of such an entry are the steps the map's "raise the limit" climbs.
RANGES = {"log_lines": (200, 50000)}

PERCENT = ("volume", "music")

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
            if saved.get(k) in choices or in_range(k, saved.get(k)):
                _values[k] = saved[k]


def in_range(key, value):
    lo, hi = RANGES.get(key, (1, 0))
    return isinstance(value, int) and not isinstance(value, bool) and lo <= value <= hi


def get(key):
    if _values is None:
        _load()
    return _values[key]


def put(key, value):
    """Keep `value` for `key` (one of its choices, or inside its range) and save it."""
    if value not in SPEC[key][1] and not in_range(key, value):
        raise ValueError(f"{key} cannot be {value}")
    if _values is None:
        _load()
    _values[key] = value
    try:
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(_values, f, indent=2)
    except OSError:
        pass
    return value


def cycle(key):
    """Step `key` to its next allowed value, wrapping, and save it."""
    choices = SPEC[key][1]
    return put(key, next_choice(key) or choices[0])


def next_choice(key):
    """The next larger allowed value of `key`, or None when it is on the last."""
    choices = SPEC[key][1]
    if key in RANGES:
        return next((c for c in choices if c > get(key)), None)
    at = choices.index(get(key))
    return choices[at + 1] if at + 1 < len(choices) else None


def step_up(key):
    """`cycle`, but without wrapping round: a limit only ever goes up from here."""
    if next_choice(key) is not None:
        cycle(key)
    return get(key)


def label(key):
    name = i18n.t(SPEC[key][0])
    value = get(key)
    if key in PERCENT:
        return f"{name}: {value}%" if value else i18n.t("settings.off", name=name)
    return f"{name}: {value}"


def apply_language():
    """Point `i18n` at the saved language; the boot and the settings screen call it."""
    i18n.set_language(get("language"))


def reload():
    global _values
    _values = None
