"""The faults of a play session: every exception a request did not expect and every script error the
browser reported, one JSON object per line in the save folder, so the playtest export carries them."""

import json
import os
import time

from . import persist
from .version import GAME_VERSION, build_hash

NAME = "errors.jsonl"
MAX_BYTES = 1_000_000      # past this nothing is appended: a fault per frame must not fill the disk
MAX_TEXT = 8000            # a message or a trace longer than this is cut


def path():
    return os.path.join(persist.SAVE_DIR, NAME)


def record(source, where, error, trace="", screen=""):
    """Append one fault; never raises (a full disk or a read-only folder must not turn a fault into a
    second one). `source` is "server" or "client", `where` the verb path or the script's file:line."""
    try:
        os.makedirs(persist.SAVE_DIR, exist_ok=True)
        target = path()
        if os.path.exists(target) and os.path.getsize(target) >= MAX_BYTES:
            return
        line = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "game_version": GAME_VERSION, "build": build_hash(),
                "source": source, "screen": screen, "where": str(where)[:MAX_TEXT],
                "error": str(error)[:MAX_TEXT], "trace": str(trace)[:MAX_TEXT]}
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    except (OSError, ValueError, TypeError):
        pass
