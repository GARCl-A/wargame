"""What every screen's server half is: it turns the domain into plain data and applies what the
person does, as `ui/` turns it into dicts for pygame today.

    GET  /api/<screen>/<verb>?query  -> Session.GET[verb](session, query)
    POST /api/<screen>/<verb> {body} -> Session.POST[verb](session, body)

A verb answers JSON; a `ValueError` is a refusal (409). Every session has a `state` verb, the
whole screen as its side knows it, and a `sheet` verb (`?uid=`): the book of anyone it shows
(`sheet_units`), which the shell opens over the screen.

A screen with a tutorial card names it in `tutorial_key` (its `tutorial.<id>` in `locales/en.json`, read again after
every request, so a tab or a phase can change it); the server sends it in each answer's `X-Tutorial` header
and serves the card itself (`/api/tutorial`).
"""

import os
from typing import ClassVar

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def asset_url(path):
    return "/assets/" + os.path.relpath(path, ASSETS).replace(os.sep, "/") if path else None


class Session:
    screen = ""
    game = None               # the `server.Game` that opened it, to open another screen
    GET: ClassVar[dict] = {}
    POST: ClassVar[dict] = {}

    def state(self):
        raise NotImplementedError

    def tutorial_key(self):
        return None

    def tutorials(self):
        """The `TutorialState` the card is read and dismissed in: the guild's."""
        guild = getattr(self, "guild", None)
        return guild.tutorial if guild is not None else None

    def tutorial_closed(self, key, first):
        """A card was dismissed (`first`: never before); an answer naming another screen moves there."""
        return

    def sheet_units(self):
        """The people and animals this screen shows, whose sheet the shell may open."""
        return []

    def sheet(self, uid):
        from .sheet_view import sheet_of
        u = next((u for u in self.sheet_units() if u.uid == uid), None)
        if u is None:
            raise ValueError("nobody by that id here")
        return sheet_of(u, getattr(self, "guild", None))

    def verb(self, name, post):
        """The handler of `name`, or None when this screen has no such verb."""
        if name == "sheet" and not post:
            return lambda s, q: s.sheet(q.get("uid", ""))
        return (self.POST if post else self.GET).get(name)
