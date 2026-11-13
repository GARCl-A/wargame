"""The local HTTP server between the core and the web client: the client's files, the game's art,
and a JSON API over the screen being played. Standard library only.

    GET  /api/screen              -> which screen is open (the client's router reads it first)
    GET  /api/sounds              -> the sound cues
    POST /api/bye                 -> the page is going (closed, or reloaded on another screen)
    POST /api/client_error        -> a script error of the page, written to the fault log
    GET  /api/tutorial            -> the open screen's tutorial card; POST .../dismiss, .../reopen
    GET  /api/settings/export     -> the playtest zip (saves, combat logs, build), while Settings is open
    *    /api/<screen>/<verb>     -> that screen's session (`session.Session`)
    *    /api/lab/fights, /new    -> the combat lab, when the game was opened on one
"""

import hashlib
import json
import mimetypes
import os
import re
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .. import (
    checks,
    combat_lab,
    fault_log,
    i18n,
    persist,
    playtest_export,
    recorder,
    settings,
    sound,
    tutorial,
)
from ..combat_log import CombatLog
from .battle_session import BattleSession
from .guild_session import GuildSession
from .map_session import MapSession
from .session import ASSETS
from .title_session import TitleSession

CLIENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "client")
ART = ("portraits", "icons", "sounds", "music")    # the asset folders the client may read
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
        self.world = None             # the save the open screens play on
        self.faults = 0               # faults in a row
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
        m = session if hasattr(session, "world_id") else getattr(session, "map", None)
        if getattr(m, "world_id", None) is not None:
            self.world = m.world_id
        if session.screen == "title":
            self.world = None

    def recover(self):
        """After a fault: back on the last save of the world being played, or the title when there is none to
        trust (a second fault in a row, or a save that does not load). False when nothing was reloaded (a lab
        fight, the title, the draft): the screen stays as it is."""
        self.faults += 1
        if self.world is None:
            return False
        try:
            if self.faults >= 2:
                raise LookupError
            self.load(self.world)
        except Exception:  # noqa: BLE001 -- a save that does not load is the title's job, whatever broke it
            self.open(TitleSession(i18n.t("server.fault_title")))
        return True

    @classmethod
    def fight(cls, fight="fortress", level=2, squad=4, seed=None, players=1, log_root=None):
        lab = Lab(log_root)
        return cls(lab.fight(fight, level, squad, seed, players), lab)

    @classmethod
    def from_save(cls, world, screen="map"):
        game = cls(SCREENS[screen](_load(world), world))
        if screen == "map":
            game.session.land_due()
        return game

    @classmethod
    def title(cls, notice=None):
        return cls(TitleSession(notice))

    def load(self, world, save_id=persist.CURRENT):
        """The map on a save of `world`, as `App._continue_game`: a snapshot becomes the live state."""
        guild = _load(world, save_id)
        if save_id != persist.CURRENT:
            persist.save_game(world, guild)
        session = MapSession(guild, world)
        self.open(session)
        session.land_due()

    def new_fight(self, fight, level, squad, seed=None, players=1):
        self.open(self.lab.fight(fight, level, squad, seed, players))
        return {"steps": self.session.snapshot()}


def _load(world, save_id=persist.CURRENT):
    guild = persist.load_game(world, save_id)
    if settings.get("record_play") == "ON":
        recorder.attach(persist.world_dir(world), guild)
    return guild


def tutorial_header(session):
    """`key` and whether its card is up (`key|1`), or empty when the screen has none."""
    key, state = session.tutorial_key(), session.tutorials()
    if key is None or state is None or not state.enabled:
        return ""
    return f"{key}|{int(state.should_show(key))}"


def _tutorial(session, verb, post):
    key, state = session.tutorial_key(), session.tutorials()
    if key is None or state is None:
        raise ValueError(i18n.t("server.this_screen_has_no_tutorial"))
    if not post and verb is None:
        return {"key": key, **tutorial.card(key, session.tutorial_rows(key), session.tutorial_spot(key), session.tutorial_wiki(key))}
    if post and verb == "dismiss":
        first = key not in state.seen
        state.dismiss(key)
        return session.tutorial_closed(key, first) or {}
    if post and verb == "wiki":
        ref = session.tutorial_wiki(key)
        if ref is None:
            raise ValueError(i18n.t("server.this_screen_has_no_tutorial"))
        state.dismiss(key)
        return session.open_wiki(ref)
    if post and verb == "reopen":
        state.reopen(key)
        return {"key": key, **tutorial.card(key, session.tutorial_rows(key), session.tutorial_spot(key), session.tutorial_wiki(key))}
    return None


_ETAGS = {}      # path -> ((mtime, size), etag): a file is hashed again only when it changed


def _etag(path):
    st = os.stat(path)
    stamp = (st.st_mtime_ns, st.st_size)
    hit = _ETAGS.get(path)
    if hit is None or hit[0] != stamp:
        with open(path, "rb") as fh:
            hit = _ETAGS[path] = (stamp, '"' + hashlib.sha1(fh.read()).hexdigest()[:20] + '"')
    return hit[1]


def _inside(root, rel):
    path = os.path.normpath(os.path.join(root, rel))
    return path if path.startswith(os.path.normpath(root) + os.sep) and os.path.isfile(path) else None


def _table(session):
    """The checks the player's last order rolled outside a fight, as `dice.js` throws them (`checks.drain`)."""
    owner = session if hasattr(session, "guild") else getattr(session, "map", None)
    guild = getattr(owner, "guild", None)
    return checks.drain(guild) if guild is not None and getattr(guild, "table", None) else []


def make_handler(game):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, body, ctype, status=200, headers=(), cache="no-store"):
            self.send_response(status)
            for k, v in headers:
                self.send_header(k, v)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload, status=200):
            """The answer, with the tutorial card of the screen open once it has run."""
            if isinstance(payload, dict) and (rolled := _table(game.session)):
                payload = {**payload, "checks": rolled}
            self._send(json.dumps(payload).encode(), "application/json", status,
                       (("X-Tutorial", tutorial_header(game.session)),))

        def _missing(self):
            self._send(b"not found", "text/plain", 404)

        def _file(self, path):
            if path is None:
                return self._missing()
            ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
            tag = _etag(path)
            if tag in (t.strip() for t in self.headers.get("If-None-Match", "").split(",")):
                self.send_response(304)
                self.send_header("ETag", tag)
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                return
            with open(path, "rb") as fh:
                body = fh.read()
            span = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", "").strip())
            if span and (span[1] or span[2]):
                # a browser asks an <audio> for byte ranges to seek and stream (Safari plays nothing without them)
                size = len(body)
                first, last = ((size - int(span[2]), size - 1) if not span[1]
                               else (int(span[1]), min(int(span[2] or size - 1), size - 1)))
                if first > last or first >= size:
                    return self._send(b"", ctype, 416, (("Content-Range", f"bytes */{size}"),))
                return self._send(body[first:last + 1], ctype, 206,
                                  (("ETag", tag), ("Accept-Ranges", "bytes"),
                                   ("Content-Range", f"bytes {first}-{last}/{size}")), cache="no-cache")
            self._send(body, ctype, headers=(("ETag", tag), ("Accept-Ranges", "bytes")), cache="no-cache")

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")

        def _api(self, parts, args, post):
            """`parts` past /api/; the lock is held."""
            s = game.session
            if parts == ["bye"] and post:
                game.gone_at = time.monotonic()
                return self._json({})
            if parts == ["client_error"] and post:
                fault_log.record("client", args.get("where", ""), args.get("error", ""), args.get("trace", ""), s.screen)
                return self._json({})
            if parts == ["screen"] and not post:
                return self._json({"screen": s.screen, "lab": game.lab is not None,
                                   "volume": settings.get("volume"), "music": settings.get("music"),
                                   "dice": settings.get("dice")})
            if parts == ["locale"] and not post:
                return self._json({"lang": i18n.language(), "text": i18n.group("ui"), "names": i18n.group("name")})
            if parts == ["sounds"] and not post:
                return self._json({"cues": {cue: [f"/assets/sounds/{f}" for f in files]
                                            for cue, files in sound.CUES.items()},
                                   "level": sound.LEVEL,
                                   "music": {"tracks": {mode: [f"/assets/music/{f}" for f in files]
                                                        for mode, files in sound.MUSIC.items()},
                                             "silence": sound.MUSIC_SILENCE, "fade": sound.MUSIC_FADE,
                                             "level": sound.MUSIC_LEVEL}})
            if parts[0] == "tutorial" and len(parts) <= 2:
                try:
                    answer = _tutorial(s, parts[1] if len(parts) == 2 else None, post)
                except ValueError as e:
                    return self._json({"error": str(e)}, 409)
                return self._missing() if answer is None else self._json(answer)
            if parts == ["settings", "export"] and not post and s.screen == "settings":
                return self._send(playtest_export.build(), "application/zip",
                                  headers=(("Content-Disposition",
                                            f'attachment; filename="{playtest_export.filename()}"'),))
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
                    return self._json({"error": i18n.t("server.open_screen_is", screen=s.screen)}, 409)
                handler = s.verb(verb, post)
                if handler is None:
                    return self._missing()
                return self._json(handler(s, args))
            except ValueError as e:
                return self._json({"error": str(e)}, 409)

        def _guarded(self, parts, args, post):
            """`_api`, with anything it did not expect written down and answered: a refusal is a ValueError
            (409, inside `_api`); the rest is a fault (500) and the game goes back to its last save."""
            try:
                if callable(args):
                    try:
                        args = args()
                    except ValueError as e:      # a body that is not JSON
                        return self._json({"error": str(e)}, 409)
                self._api(parts, args, post)
                if parts != ["client_error"]:
                    game.faults = 0
            except ConnectionError:
                pass                                  # the page left before the answer: not a fault
            except Exception as e:  # noqa: BLE001 -- the fault is written down and answered, never re-raised
                self._fault(parts, post, e)

        def _fault(self, parts, post, e):
            screen = getattr(game.session, "screen", "")
            fault_log.record("server", ("POST " if post else "GET ") + "/".join(parts),
                             f"{type(e).__name__}: {e}", traceback.format_exc(), screen)
            reload = game.recover()
            body = json.dumps({"error": i18n.t("server.fault"), "fault": True, "reload": reload}).encode()
            try:
                self._send(body, "application/json", 500)
            except OSError:
                pass

        def do_GET(self):
            game.gone_at = None
            url = urlparse(self.path)
            parts = url.path.strip("/").split("/")
            if url.path in ("/", "/index.html"):
                return self._file(os.path.join(CLIENT, "host.html"))     # holds the music; the game is its frame
            if url.path == "/game":
                return self._file(os.path.join(CLIENT, "index.html"))
            if parts[0] == "client" and len(parts) > 1:
                return self._file(_inside(CLIENT, "/".join(parts[1:])))
            if parts[0] == "assets" and len(parts) > 2 and parts[1] in ART:
                return self._file(_inside(ASSETS, "/".join(parts[1:])))
            if parts[0] == "api":
                with game.lock:
                    return self._guarded(parts[1:], {k: v[0] for k, v in parse_qs(url.query).items()}, False)
            self._missing()

        def do_POST(self):
            game.gone_at = None
            parts = urlparse(self.path).path.strip("/").split("/")
            if parts[0] != "api":
                return self._missing()
            with game.lock:
                return self._guarded(parts[1:], self._body, True)

    return Handler


def serve(game, port=0):
    """A server bound to localhost (port 0: a free one), not yet serving."""
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(game))
