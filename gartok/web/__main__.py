"""`python -m gartok.web`: serve a combat-lab fight and open it in a browser window.

    python -m gartok.web --fight fortress --level 2 --squad 4 [--seed N] [--no-window]
"""

import argparse
import os
import shutil
import subprocess
import tempfile
import webbrowser

from .. import combat_lab
from .server import Game, serve

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
                      "--no-first-run", "--no-default-browser-check"])


def main():
    p = argparse.ArgumentParser(prog="python -m gartok.web")
    p.add_argument("--fight", default="fortress", choices=sorted(combat_lab.FIGHTS))
    p.add_argument("--level", type=int, default=2)
    p.add_argument("--squad", type=int, default=4)
    p.add_argument("--seed", type=int)
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--no-window", action="store_true")
    args = p.parse_args()
    server = serve(Game(args.fight, args.level, args.squad, args.seed), args.port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"GARTOK web: {url}  (Ctrl+C to stop)")
    if not args.no_window:
        open_window(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
