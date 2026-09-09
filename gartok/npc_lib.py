"""The NPC library: hand-authored characters kept outside the campaign saves.

The Editor's character creator (`char_editor_screen`) writes them here -- one
JSON file per NPC under `npcs/` at the repo root, versioned in git. They are
authored content, like `world.py`, not per-machine save state: a champion team
built in the creator can ship with the game.

A file holds exactly what a save slot's roster entry does (`persist.unit_to_dict`)
plus an `npc_slug` (the file's stem, the stable id), so `Unit.from_save` rebuilds
it with nothing re-rolled. Nothing consumes these yet -- dropping one into a
guild, or fielding three as an arena champion team, comes later.
"""

import json
import os
import re

from .persist import unit_to_dict
from .unit import Unit

NPC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "npcs")


def slugify(name):
    """A filesystem-safe stem from a display name (`"Old Grix"` -> `"old-grix"`)."""
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return s or "npc"


def npc_path(slug):
    return os.path.join(NPC_DIR, f"{slug}.json")


def save_npc(unit, slug=None):
    """Write `unit` to `npcs/<slug>.json` (slug defaults to the name). Returns the
    slug actually used. Atomic: never leaves a half-written file."""
    os.makedirs(NPC_DIR, exist_ok=True)
    slug = slug or slugify(unit.name)
    payload = unit_to_dict(unit)
    payload["npc_slug"] = slug
    tmp = npc_path(slug) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, npc_path(slug))
    return slug


def load_npc(slug):
    """-> Unit rebuilt from `npcs/<slug>.json` (raises if the file is gone)."""
    with open(npc_path(slug), encoding="utf-8") as fh:
        return Unit.from_save(json.load(fh))


def delete_npc(slug):
    try:
        os.remove(npc_path(slug))
    except FileNotFoundError:
        pass


def list_npcs():
    """One summary dict per file for the library list, sorted by name:
    `{slug, name, race, occupation}`. Skips anything that will not parse."""
    out = []
    try:
        names = os.listdir(NPC_DIR)
    except FileNotFoundError:
        return out
    for fn in names:
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(NPC_DIR, fn), encoding="utf-8") as fh:
                d = json.load(fh)
            out.append({"slug": fn[:-5], "name": d.get("name", fn[:-5]),
                        "race": d.get("race", ""), "occupation": d.get("occupation", "")})
        except (json.JSONDecodeError, OSError):
            continue
    return sorted(out, key=lambda r: r["name"].lower())
