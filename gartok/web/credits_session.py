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


MUSIC_AUTHORS = [{"name": "RandomMind", "url": "https://opengameart.org/users/randommind"},
                 {"name": "Emma_MA", "url": "https://opengameart.org/users/emmama"},
                 {"name": "Theodore Kerr (Wolfgang_)", "url": "https://opengameart.org/users/wolfgang"}]


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
    icons, sounds, music = _read("icons"), _read("sounds"), _read("music")
    icon_links = [_link(i18n.t("credits_session.license_cc_by"), icons, r"License:\s+(https?://\S+)"),
                  _link(i18n.t("credits_session.source_game_icons_net"), icons, r"Source:\s+(https?://\S+)")]
    sound_links = [_link(i18n.t("credits_session.license_cc"), sounds, r"(http://creativecommons\.org/publicdomain/zero/\S+)"),
                   {"label": i18n.t("credits_session.source_www_kenney_nl"), "url": "https://www.kenney.nl"}]
    music_links = [_link(i18n.t("credits_session.license_cc"), music, r"(http://creativecommons\.org/publicdomain/zero/\S+)"),
                   {"label": "OpenGameArt.org", "url": "https://opengameart.org"}]
    return [
        {"id": "icons", "heading": i18n.t("credits.icons.heading"), "intro": i18n.t("credits.icons.intro"),
         "people_label": i18n.t("credits.icons.authors"), "people": authors(icons),
         "links": [x for x in icon_links if x]},
        {"id": "sounds", "heading": i18n.t("credits.sounds.heading"), "intro": i18n.t("credits.sounds.intro"),
         "people_label": None, "people": [{"name": i18n.t("credits_session.kenney_vleugels"), "url": "https://www.kenney.nl"},
                                          {"name": "StarNinjas", "url": "https://opengameart.org/users/starninjas"}],
         "links": [x for x in sound_links if x]},
        {"id": "music", "heading": i18n.t("credits.music.heading"), "intro": i18n.t("credits.music.intro"),
         "people_label": i18n.t("credits.music.authors"), "people": MUSIC_AUTHORS,
         "links": [x for x in music_links if x]},
    ]


class CreditsSession(Session):
    screen = "credits"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {"back": lambda s, b: s.back_to()}

    def __init__(self, back, back_label=None):
        self.back_to = back
        self.back_label = back_label or i18n.t("ui.title.back")

    def state(self):
        return {"title": i18n.t("credits.title"), "kicker": i18n.t("credits.kicker"),
                "sections": sections(), "back": self.back_label}
