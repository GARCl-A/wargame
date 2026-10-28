"""The settings, as pygame's `SettingsScreen`: one row per `settings.SPEC` entry with its choices,
and, with a guild open, its tutorial cards (on or off, and shown again). Opened from the title or
the map's menu; BACK returns there."""

from typing import ClassVar

from .. import settings
from .session import Session

NOTES = {
    "chord_ms": "How long the battle waits for a second arrow key to read a diagonal (pygame's keyboard).",
    "record_play": "A day-by-day log of the play beside the saves; it starts with the next guild opened.",
    "volume": "The sounds of the fights, the buttons and the coins.",
}


def _shown(key, value):
    if key.endswith("_ms"):
        return f"{value} ms"
    if key == "volume":
        return f"{value}%" if value else "Off"
    return str(value).title()


class SettingsSession(Session):
    screen = "settings"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {
        "set": lambda s, b: s.set(b["key"], b["value"]),
        "tutorial": lambda s, b: s.toggle_tutorial(),
        "reset_tutorial": lambda s, b: s.reset_tutorial(),
        "back": lambda s, b: s.back_to(),
    }

    def __init__(self, back, back_label="Back", guild=None, save=None):
        self.back_to = back
        self.back_label = back_label
        self.guild = guild
        self.save = save or (lambda: None)
        self.reset_note = False

    def set(self, key, value):
        if key not in settings.SPEC:
            raise ValueError(f"no setting called {key}")
        choices = settings.SPEC[key][1]
        if value not in choices:
            raise ValueError(f"{settings.SPEC[key][0].title()} cannot be {value}")
        while settings.get(key) != value:
            settings.cycle(key)
        return self.state()

    def _tutorial(self):
        if self.guild is None:
            raise ValueError("the tutorials belong to a guild; open one first")
        return self.guild.tutorial

    def toggle_tutorial(self):
        t = self._tutorial()
        t.enabled = not t.enabled
        self.save()
        return self.state()

    def reset_tutorial(self):
        self._tutorial().reset()
        self.save()
        self.reset_note = True
        return self.state()

    def state(self):
        rows = [{"key": k, "label": name.title(), "note": NOTES.get(k, ""), "value": settings.get(k),
                 "choices": [{"value": v, "label": _shown(k, v)} for v in choices]}
                for k, (name, choices, _) in settings.SPEC.items()]
        tut = None
        if self.guild is not None:
            tut = {"enabled": self.guild.tutorial.enabled, "reset": self.reset_note}
        return {"rows": rows, "tutorial": tut, "guild": self.guild.name if self.guild else None,
                "volume": settings.get("volume"), "back": self.back_label}
