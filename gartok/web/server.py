"""The local HTTP server between the core and the web client: the client's files, the game's art,
and a JSON API over the screen being played. Standard library only.

    GET  /api/screen              -> which screen is open (the client's router reads it first)
    GET  /api/sounds              -> the sound cues
    POST /api/bye                 -> the page is going (closed, or reloaded on another screen)
    *    /api/<screen>/<verb>     -> that screen's session (`session.Session`)
    *    /api/lab/fights, /new    -> the combat lab, when the game was opened on one
"""

import json
import mimetypes
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .. import combat_lab, persist, recorder, settings, sound
from ..combat_log import CombatLog
from .battle_session import BattleSession
from .guild_session import GuildSession
from .map_session import MapSession
from .session import ASSETS
from .title_session import TitleSession

CLIENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "client")
ART = ("portraits", "icons", "sounds")    # the asset folders the client may read
SCREENS = {"map": MapSession, "guild": lambda guild, world: GuildSession(MapSession(guild, world))}
# the screens a save opens; a battle comes from the lab or the campaign


class Lab:
    """The combat lab's fights. With a `log_root` every fight is written there as the pygame lab
    writes its own (`combat_log`)."""

    def __init__(self, log_root=None):
        self.log_root = log_root

    def fight(self, fight="fortress", level=2, squad=4, seed=None, players=1):
        battle, meta = combat_lab.build(fight, int(level), int(squad), seed)
        controllers = {"player": "human", "enemy": "human" if int(players) == 2 else "ai"}
        meta.update(name=combat_lab.FIGHTS[fight].name, players=int(players))
        if self.log_root is not None:
            name = combat_lab.default_name(fight, controllers)
            battle.record_to(CombatLog(combat_lab.log_path(name, root=self.log_root),
                                       {"source": "lab", "name": name, **meta}, controllers))
        return BattleSession(battle, meta, controllers)

    def fights(self):
        return [{"id": f.id, "name": f.name, "note": f.note, "squad": f.squad} for f in combat_lab.FIGHTS.values()]


class Game:
    """The screen being played, behind one lock: the API's requests never interleave."""

    def __init__(self, session, lab=None):
        self.lock = threading.Lock()
        self.lab = lab
        self.quit = lambda: None      # the window's QUIT; `__main__` stops the server with it
        self.gone_at = None           # when the page last said bye with no request since
        self.open(session)

    def closed(self, grace):
        """The page said bye `grace` seconds ago and nothing came after it: the window was closed, not
        reloaded on another screen."""
        return self.gone_at is not None and time.monotonic() - self.gone_at > grace

    def open(self, session):
        """Make `session` the open screen; a verb that changes screen calls this, and the client
        reloads on the screen its answer names."""
        session.game = self
        if getattr(session, "map", None) is not None:      # a screen over the map opens with it
            session.map.game = self
        self.session = session

    @classmethod
    def fight(cls, fight="fortress", level=2, squad=4, seed=None, players=1, log_root=None):
        lab = Lab(log_root)
        return cls(lab.fight(fight, level, squad, seed, players), lab)

    @classmethod
    def from_save(cls, world, screen="map"):
        return cls(SCREENS[screen](_load(world), world))

    @classmethod
    def title(cls, notice=None):
        return cls(TitleSession(notice))

    def load(self, world, save_id=persist.CURRENT):
        """The map on a save of `world`, as `App._continue_game`: a snapshot becomes the live state."""
        guild = _load(world, save_id)
        if save_id != persist.CURRENT:
            persist.save_game(world, guild)
        self.open(MapSession(guild, world))

    def new_fight(self, fight, level, squad, seed=None, players=1):
        self.open(self.lab.fight(fight, level, squad, seed, players))
        return {"steps": self.session.snapshot()}


def _load(world, save_id=persist.CURRENT):
    guild = persist.load_game(world, save_id)
    if settings.get("record_play") == "ON":
        recorder.attach(persist.world_dir(world), guild)
    return guild


def _inside(root, rel):
    path = os.path.normpath(os.path.join(root, rel))
    return path if path.startswith(os.path.normpath(root) + os.sep) and os.path.isfile(path) else None


def make_handler(game):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, body, ctype, status=200):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload, status=200):
            self._send(json.dumps(payload).encode(), "application/json", status)

        def _missing(self):
            self._send(b"not found", "text/plain", 404)

        def _file(self, path):
            if path is None:
                return self._missing()
            ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
            with open(path, "rb") as fh:
                self._send(fh.read(), ctype)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")

        def _api(self, parts, args, post):
            """`parts` past /api/; the lock is held."""
            s = game.session
            if parts == ["bye"] and post:
                game.gone_at = time.monotonic()
                return self._json({})
            if parts == ["screen"] and not post:
                return self._json({"screen": s.screen, "lab": game.lab is not None,
                                   "volume": settings.get("volume")})
            if parts == ["sounds"] and not post:
                return self._json({"cues": {cue: [f"/assets/sounds/{f}" for f in files]
                                            for cue, files in sound.CUES.items()},
                                   "level": sound.LEVEL})
            if len(parts) != 2:
                return self._missing()
            screen, verb = parts
            try:
                if screen == "lab" and game.lab is not None:
                    if verb == "fights" and not post:
                        return self._json(game.lab.fights())
                    if verb == "new" and post:
                        return self._json(game.new_fight(args.get("fight", "fortress"), args.get("level", 2),
                                                         args.get("squad", 4), args.get("seed"),
                                                         args.get("players", 1)))
                    return self._missing()
                if screen != s.screen:
                    return self._json({"error": f"the open screen is {s.screen}"}, 409)
                handler = s.verb(verb, post)
                if handler is None:
                    return self._missing()
                return self._json(handler(s, args))
            except ValueError as e:
                return self._json({"error": str(e)}, 409)

        def do_GET(self):
            game.gone_at = None
            url = urlparse(self.path)
            parts = url.path.strip("/").split("/")
            if url.path in ("/", "/index.html"):
                return self._file(os.path.join(CLIENT, "index.html"))
            if parts[0] == "client" and len(parts) > 1:
                return self._file(_inside(CLIENT, "/".join(parts[1:])))
            if parts[0] == "assets" and len(parts) > 2 and parts[1] in ART:
                return self._file(_inside(ASSETS, "/".join(parts[1:])))
            if parts[0] == "api":
                with game.lock:
                    return self._api(parts[1:], {k: v[0] for k, v in parse_qs(url.query).items()}, False)
            self._missing()

        def do_POST(self):
            game.gone_at = None
            parts = urlparse(self.path).path.strip("/").split("/")
            if parts[0] != "api":
                return self._missing()
            body = self._body()
            with game.lock:
                return self._api(parts[1:], body, True)

    return Handler


def serve(game, port=0):
    """A server bound to localhost (port 0: a free one), not yet serving."""
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(game))
