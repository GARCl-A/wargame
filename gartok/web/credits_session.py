"""The credits: who made the icons and the sounds, read off the `LICENSE.txt` beside each asset folder
so the screen and the file cannot drift. CC BY 3.0 asks that the authors, the licence link and the
source reach the player; this is where they do. Opened from the title; BACK returns there."""

import os
import re
from typing import ClassVar

from .. import i18n
from .session import Session

ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
URL = re.compile(r"https?://[^\s)]+")
PERSON = re.compile(r"^ {4}(?P<name>[^—\n]+?)(?:\s+—\s+(?P<url>https?://\S+))?\s*$")


def _read(folder):
    with open(os.path.join(ASSETS, folder, "LICENSE.txt"), encoding="utf-8") as f:
        return f.read()


def authors(text):
    """The contributors a LICENSE.txt lists: the indented `Name — link` lines."""
    out = []
    for line in text.splitlines():
        m = PERSON.match(line)
        if m and not line.strip().startswith(("License:", "Source:")):
            out.append({"name": m["name"].strip(), "url": m["url"]})
    return out


def _link(label, text, pattern):
    m = re.search(pattern, text)
    return {"label": label, "url": m[1]} if m else None


def sections():
    icons, sounds = _read("icons"), _read("sounds")
    icon_links = [_link("License: CC BY 3.0", icons, r"License:\s+(https?://\S+)"),
                  _link("Source: game-icons.net", icons, r"Source:\s+(https?://\S+)")]
    sound_links = [_link("License: CC0", sounds, r"(http://creativecommons\.org/publicdomain/zero/\S+)"),
                   {"label": "Source: www.kenney.nl", "url": "https://www.kenney.nl"}]
    return [
        {"id": "icons", "heading": i18n.t("credits.icons.heading"), "intro": i18n.t("credits.icons.intro"),
         "people_label": i18n.t("credits.icons.authors"), "people": authors(icons),
         "links": [x for x in icon_links if x]},
        {"id": "sounds", "heading": i18n.t("credits.sounds.heading"), "intro": i18n.t("credits.sounds.intro"),
         "people_label": None, "people": [{"name": "Kenney Vleugels", "url": "https://www.kenney.nl"}],
         "links": [x for x in sound_links if x]},
    ]


class CreditsSession(Session):
    screen = "credits"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {"back": lambda s, b: s.back_to()}

    def __init__(self, back, back_label="Back"):
        self.back_to = back
        self.back_label = back_label

    def state(self):
        return {"title": i18n.t("credits.title"), "kicker": i18n.t("credits.kicker"),
                "sections": sections(), "back": self.back_label}
