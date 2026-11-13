"""`python -m gartok.web` (and `python -m gartok`, `python main.py`): serve the game and open it in a
browser window; the server stops when the window is closed.

    python -m gartok.web                     the title screen: continue or load a guild
    python -m gartok.web --fight fortress --level 2 --squad 4 [--seed N] [--players 2] [--no-log] [--no-window]
    python -m gartok.web --save <world> [--screen map]
    python -m gartok.web --shell             under the native client (`shell/`): no window of its own; the
                                             server stops when its stdin closes (the client is gone) or on QUIT

Under `--shell` the first line on stdout, `GARTOK web: http://127.0.0.1:<port>/`, is how the client finds the
port; the player's files go where `GARTOK_DATA_DIR` says (`persist.data_dir`).

A lab fight is logged to `combat_lab/<date>/` as the pygame lab logs its own, unless `--no-log`.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser

from .. import combat_lab, settings
from .server import SCREENS, Game, serve

_BROWSERS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
)


def open_window(url):
    """The page in a chromeless app window (Edge or Chrome), else the default browser."""
    exe = (shutil.which("msedge") or shutil.which("chrome")
           or next((p for p in _BROWSERS if os.path.isfile(p)), None))
    if exe is None:
        webbrowser.open(url)
        return
    profile = os.path.join(tempfile.gettempdir(), "gartok-web-profile")
    subprocess.Popen([exe, f"--app={url}", f"--user-data-dir={profile}", "--window-size=1920,1080",
                      "--no-first-run", "--no-default-browser-check", "--disable-features=Translate",
                      "--autoplay-policy=no-user-gesture-required"])      # the title has music before any click


CLOSE_GRACE = 5      # seconds between the page's bye and the stop: a reload onto another screen is back by then


def _stop_when_closed(game, stop):
    while not game.closed(CLOSE_GRACE):
        time.sleep(1)
    stop()


def _stop_on_eof(stream, stop):
    """Stop when `stream` ends: the native client holds the server's stdin open, so its end means the client
    is gone, closed or killed."""
    try:
        stream.read()
    except (OSError, ValueError):
        pass
    stop()


def main():
    p = argparse.ArgumentParser(prog="python -m gartok")
    p.add_argument("--fight", choices=sorted(combat_lab.FIGHTS), help="a combat-lab fight instead of the title")
    p.add_argument("--level", type=int, default=2)
    p.add_argument("--squad", type=int, default=4)
    p.add_argument("--seed", type=int)
    p.add_argument("--players", type=int, choices=(1, 2), default=1, help="2: both sides at one screen")
    p.add_argument("--no-log", action="store_true")
    p.add_argument("--save", metavar="WORLD", help="open a saved guild (its folder under saves/) instead of a lab fight")
    p.add_argument("--screen", default="map", choices=sorted(SCREENS), help="the screen --save opens")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--no-window", action="store_true")
    p.add_argument("--shell", action="store_true", help="run under the native client: no window, stop when stdin closes")
    args = p.parse_args()
    settings.apply_language()
    if args.save:
        game = Game.from_save(args.save, args.screen)
    elif args.fight is None:
        game = Game.title()
    else:
        game = Game.fight(args.fight, args.level, args.squad, args.seed, args.players,
                          None if args.no_log else combat_lab.ROOT)
    server = serve(game, args.port)
    game.quit = lambda: threading.Thread(target=server.shutdown, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"GARTOK web: {url}  (Ctrl+C to stop)", flush=True)      # flushed: a pipe buffers it, and the client waits for it
    if args.shell:
        if sys.stdin is not None:
            threading.Thread(target=_stop_on_eof, args=(sys.stdin, game.quit), daemon=True).start()
    elif not args.no_window:
        open_window(url)
        threading.Thread(target=_stop_when_closed, args=(game, game.quit), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    if args.shell:
        # the thread reading stdin is still blocked: leaving it for the interpreter's shutdown can abort the exit code
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)


if __name__ == "__main__":
    main()
