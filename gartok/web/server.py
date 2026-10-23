"""The local HTTP server between the core and the web client: the client's files, the game's art,
and a small JSON API over one `BattleSession`. Standard library only."""

import json
import mimetypes
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .. import combat_lab, settings, sound
from ..combat_log import CombatLog
from .battle_session import ASSETS, BattleSession

CLIENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "client")
ART = ("portraits", "icons", "sounds")    # the asset folders the client may read


class Game:
    """The fight being played, behind one lock: the API's requests never interleave. With a
    `log_root` every fight is written there as the combat lab writes its own (`combat_log`)."""

    def __init__(self, fight="fortress", level=2, squad=4, seed=None, players=1, log_root=None):
        self.lock = threading.Lock()
        self.log_root = log_root
        self.new(fight, level, squad, seed, players)

    def new(self, fight, level, squad, seed=None, players=1):
        battle, meta = combat_lab.build(fight, int(level), int(squad), seed)
        controllers = {"player": "human", "enemy": "human" if int(players) == 2 else "ai"}
        meta.update(name=combat_lab.FIGHTS[fight].name, players=int(players), volume=settings.get("volume"))
        if self.log_root is not None:
            name = combat_lab.default_name(fight, controllers)
            battle.record_to(CombatLog(combat_lab.log_path(name, root=self.log_root),
                                       {"source": "lab", "name": name, **meta}, controllers))
        self.session = BattleSession(battle, meta, controllers)


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

        def _file(self, path):
            if path is None:
                self._send(b"not found", "text/plain", 404)
                return
            ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
            with open(path, "rb") as fh:
                self._send(fh.read(), ctype)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")

        def do_GET(self):
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            parts = url.path.strip("/").split("/", 1)
            if url.path in ("/", "/index.html"):
                return self._file(os.path.join(CLIENT, "index.html"))
            if parts[0] == "client" and len(parts) == 2:
                return self._file(_inside(CLIENT, parts[1]))
            if parts[0] == "assets" and len(parts) == 2 and parts[1].split("/", 1)[0] in ART:
                return self._file(_inside(ASSETS, parts[1]))
            with game.lock:
                s = game.session
                if url.path == "/api/state":
                    return self._json(s.state(q.get("inspect")))
                if url.path == "/api/route":
                    return self._json(s.route((int(q["x"]), int(q["y"]))))
                if url.path == "/api/aim":
                    return self._json(s.aim(q.get("action", "")))
                if url.path == "/api/sounds":
                    return self._json({"cues": {cue: [f"/assets/sounds/{f}" for f in files]
                                                for cue, files in sound.CUES.items()},
                                       "level": sound.LEVEL})
                if url.path == "/api/fights":
                    return self._json([{"id": f.id, "name": f.name, "note": f.note, "squad": f.squad}
                                       for f in combat_lab.FIGHTS.values()])
            self._send(b"not found", "text/plain", 404)

        def do_POST(self):
            path, body = urlparse(self.path).path, self._body()
            with game.lock:
                s = game.session
                inspect = body.get("inspect")
                try:
                    if path == "/api/act":
                        steps = s.act(body.get("action", ""), body.get("target"), body.get("cell"), inspect,
                                      body.get("elevation"))
                    elif path == "/api/advance":
                        steps = s.advance(inspect)
                    elif path == "/api/talk":
                        steps = s.answer(body.get("verb"), body.get("speaker"), bool(body.get("go_on")), inspect)
                    elif path == "/api/seat":
                        steps = s.take_seat(inspect)
                    elif path == "/api/new":
                        game.new(body.get("fight", "fortress"), body.get("level", 2), body.get("squad", 4),
                                 body.get("seed"), body.get("players", 1))
                        steps = game.session.snapshot()
                    else:
                        return self._send(b"not found", "text/plain", 404)
                except ValueError as e:
                    return self._json({"error": str(e)}, 409)
                return self._json({"steps": steps})

    return Handler


def serve(game, port=0):
    """A server bound to localhost (port 0: a free one), not yet serving."""
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(game))
