"""Is there a newer release on GitHub? One unauthenticated GET at start-up, in a thread, that fails silent:
no network or a slow answer just means no notice. Nothing about the player is sent."""

import json
import re
import threading
import urllib.request

from .version import GAME_VERSION

LATEST_URL = "https://api.github.com/repos/GARCl-A/wargame/releases/latest"
TIMEOUT = 4

_lock = threading.Lock()
_state = {"done": True, "update": None}


def parse(tag):
    """`v0.1.15` -> (0, 1, 15); None when the tag is not a dotted number."""
    m = re.fullmatch(r"v?(\d+(?:\.\d+)*)", (tag or "").strip())
    return tuple(int(p) for p in m.group(1).split(".")) if m else None


def newer(tag, current=GAME_VERSION):
    a, b = parse(tag), parse(current)
    return a is not None and b is not None and a > b


def fetch(opener=urllib.request.urlopen):
    """The release notice `{"version", "url"}` when GitHub's latest is newer than this build, else None."""
    req = urllib.request.Request(LATEST_URL, headers={"Accept": "application/vnd.github+json", "User-Agent": "gartok-update-check"})
    try:
        with opener(req, timeout=TIMEOUT) as res:
            data = json.load(res)
    except (OSError, ValueError):
        return None
    tag = data.get("tag_name") if isinstance(data, dict) else None
    url = data.get("html_url") if isinstance(data, dict) else None
    if not newer(tag) or not isinstance(url, str) or not url.startswith("https://github.com/"):
        return None
    return {"version": tag.lstrip("v"), "url": url}


def start(fetcher=fetch):
    """Check in the background, once; `status()` has the answer when it lands."""
    with _lock:
        _state.update(done=False, update=None)

    def run():
        update = fetcher()
        with _lock:
            _state.update(done=True, update=update)

    threading.Thread(target=run, daemon=True).start()


def status():
    """`{"pending": bool, "update": notice or None}`."""
    with _lock:
        return {"pending": not _state["done"], "update": _state["update"]}
