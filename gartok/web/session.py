"""What every screen's server half is: it turns the domain into plain data and applies what the
person does, as `ui/` turns it into dicts for pygame today.

    GET  /api/<screen>/<verb>?query  -> Session.GET[verb](session, query)
    POST /api/<screen>/<verb> {body} -> Session.POST[verb](session, body)

A verb answers JSON; a `ValueError` is a refusal (409). Every session has a `state` verb, the
whole screen as its side knows it.
"""

import os
from typing import ClassVar

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def asset_url(path):
    return "/assets/" + os.path.relpath(path, ASSETS).replace(os.sep, "/") if path else None


class Session:
    screen = ""
    GET: ClassVar[dict] = {}
    POST: ClassVar[dict] = {}

    def state(self):
        raise NotImplementedError

    def verb(self, name, post):
        """The handler of `name`, or None when this screen has no such verb."""
        return (self.POST if post else self.GET).get(name)
