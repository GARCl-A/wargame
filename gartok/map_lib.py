"""The map library: hand-authored battle maps kept outside the campaign saves.

The Editor's scenario creator (`map_editor_screen`) writes them here -- one JSON
file per map under `maps/` at the repo root, versioned in git. Authored content,
like `world.py` and the NPC library (`npc_lib`): a map laid out in the editor can
ship with the game.

A file is a flat dict -- the grid size, the wall / torch / player+enemy cells
(each a sorted `[x, y]` pair), `deploy_npc` as `[x, y, slug]` triples pinning a
named library character to a cell, and the two lighting flags -- plus a
`map_slug` (the file's stem, the stable id). `scenario.CustomScenario` +
`npc_units` turn one back into a playable battle. Nothing wires a world node to a
custom map yet -- that, like `use NPC x`, comes later.
"""

import json
import os
import re

from .board import COLS, ROWS
from .npc_lib import load_npc, slugify

MAP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "maps")

_CELL_KEYS = ("walls", "torches", "deploy_player", "deploy_enemy", "deploy_npc",
              "elevation", "ropes")


def new_map(name="Untitled"):
    """A blank map dict: full grid, nothing on it, indoor and dark."""
    d = {"name": name, "cols": COLS, "rows": ROWS,
         "ambient_light": False, "outdoor": False}
    for key in _CELL_KEYS:
        d[key] = []
    return d


def map_path(slug):
    return os.path.join(MAP_DIR, f"{slug}.json")


def save_map(data, slug=None):
    """Write `data` to `maps/<slug>.json` (slug defaults to the name). Cell lists
    are sorted so the file diffs cleanly. Returns the slug used. Atomic."""
    os.makedirs(MAP_DIR, exist_ok=True)
    slug = slug or slugify(data.get("name"))
    payload = {"name": data.get("name") or "Untitled",
               "cols": data.get("cols", COLS), "rows": data.get("rows", ROWS),
               "ambient_light": bool(data.get("ambient_light")),
               "outdoor": bool(data.get("outdoor")),
               "map_slug": slug}
    for key in _CELL_KEYS:
        payload[key] = sorted([list(c) for c in data.get(key, [])])
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    text = re.sub(r"\[\s+(-?\d+),\s+(-?\d+)\s+\]", r"[\1, \2]", text)          # [x, y]
    text = re.sub(r"\[\s+(-?\d+),\s+(-?\d+),\s+(-?\d+)\s+\]",
                  r"[\1, \2, \3]", text)                                        # [x, y, z]
    text = re.sub(r'\[\s+(-?\d+),\s+(-?\d+),\s+("(?:[^"\\]|\\.)*")\s+\]',
                  r"[\1, \2, \3]", text)                                        # [x, y, "slug"]
    tmp = map_path(slug) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, map_path(slug))
    return slug


def load_map(slug):
    """-> the map dict from `maps/<slug>.json` (raises if the file is gone)."""
    with open(map_path(slug), encoding="utf-8") as fh:
        return json.load(fh)


def delete_map(slug):
    try:
        os.remove(map_path(slug))
    except FileNotFoundError:
        pass


def npc_units(data):
    """The named NPCs a map places -- loaded from the library, each tagged with
    the cell it was dropped on (`unit.map_cell`) so `scenario.CustomScenario`
    stands it there. Missing library files are skipped. The caller hands these to
    `Battle` as (part of) the enemy side."""
    out = []
    for entry in data.get("deploy_npc", []):
        if len(entry) < 3:
            continue
        x, y, slug = entry[0], entry[1], entry[2]
        try:
            u = load_npc(slug)
        except OSError:
            continue
        u.map_cell = (x, y)
        out.append(u)
    return out


def list_maps():
    """One summary dict per file for the library list, sorted by name:
    `{slug, name, walls, outdoor}`. Skips anything that will not parse."""
    out = []
    try:
        names = os.listdir(MAP_DIR)
    except FileNotFoundError:
        return out
    for fn in names:
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(MAP_DIR, fn), encoding="utf-8") as fh:
                d = json.load(fh)
            out.append({"slug": fn[:-5], "name": d.get("name", fn[:-5]),
                        "walls": len(d.get("walls", [])),
                        "outdoor": bool(d.get("outdoor"))})
        except (json.JSONDecodeError, OSError):
            continue
    return sorted(out, key=lambda r: r["name"].lower())
