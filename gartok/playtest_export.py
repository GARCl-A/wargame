"""The playtest export: the save folder (saves, combat-log JSONLs, the play recorder's file) as one
zip, with a `playtest.json` that names the build, so the author reads what a tester did."""

import io
import json
import os
import time
import zipfile

from . import persist
from .version import GAME_VERSION, build_hash

INFO = "playtest.json"


def filename():
    return f"gartok-playtest-v{GAME_VERSION}-{time.strftime('%Y%m%d-%H%M%S')}.zip"


def build():
    """The zip's bytes: `playtest.json` (game_version, save_version, build, exported_at) and every file
    under the save folder, kept at its path inside it."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        info = {"game_version": GAME_VERSION, "save_version": persist.SAVE_VERSION, "build": build_hash(),
                "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        z.writestr(INFO, json.dumps(info, indent=2))
        for folder, _dirs, files in os.walk(persist.SAVE_DIR):
            for name in sorted(files):
                path = os.path.join(folder, name)
                z.write(path, os.path.join("saves", os.path.relpath(path, persist.SAVE_DIR)))
    return buf.getvalue()
