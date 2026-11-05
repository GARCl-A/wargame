"""The settings, as pygame's `SettingsScreen`: one row per `settings.SPEC` entry with its choices,
and, with a guild open, its tutorial cards (on or off, and shown again). Opened from the title or
the map's menu; BACK returns there."""

from typing import ClassVar

from .. import i18n, settings
from ..version import GAME_VERSION, build_hash
from .session import Session


def _shown(key, value):
    if key.endswith("_ms"):
        return f"{value} ms"
    if key == "volume":
        return f"{value}%" if value else i18n.t("ui.settings.value.off")
    if key == "language":
        return i18n.LANGUAGES[value]
    return i18n.t(f"ui.settings.value.{str(value).lower()}")


class SettingsSession(Session):
    screen = "settings"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {
        "set": lambda s, b: s.set(b["key"], b["value"]),
        "tutorial": lambda s, b: s.toggle_tutorial(),
        "reset_tutorial": lambda s, b: s.reset_tutorial(),
        "back": lambda s, b: s.back_to(),
    }

    def __init__(self, back, back_label=None, guild=None, save=None):
        self.back_to = back
        self.back_label = back_label or i18n.t("ui.title.back")
        self.guild = guild
        self.save = save or (lambda: None)
        self.reset_note = False

    def set(self, key, value):
        if key not in settings.SPEC:
            raise ValueError(i18n.t("ui.settings.unknown", name=key))
        choices = settings.SPEC[key][1]
        if value not in choices:
            raise ValueError(i18n.t("ui.settings.cannot_be", label=i18n.t(f"ui.settings.row.{key}.label"), value=value))
        while settings.get(key) != value:
            settings.cycle(key)
        if key == "language":
            settings.apply_language()
        return self.state()

    def _tutorial(self):
        if self.guild is None:
            raise ValueError(i18n.t("ui.settings.no_guild_tutorial"))
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
        rows = [{"key": k, "label": i18n.t(f"ui.settings.row.{k}.label"),
                 "note": i18n.t(f"ui.settings.row.{k}.note"), "value": settings.get(k),
                 "choices": [{"value": v, "label": _shown(k, v)} for v in choices]}
                for k, (_, choices, _) in settings.SPEC.items()]
        tut = None
        if self.guild is not None:
            tut = {"enabled": self.guild.tutorial.enabled, "reset": self.reset_note}
        return {"rows": rows, "tutorial": tut, "guild": self.guild.name if self.guild else None,
                "version": f"GARTOK v{GAME_VERSION} · {build_hash()}", "volume": settings.get("volume"), "back": self.back_label}
