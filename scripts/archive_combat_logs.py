"""Copy every world's campaign combat logs into `combat_lab/campaign/`, which git tracks (saves/ does not).

    python scripts/archive_combat_logs.py            # copy what is new, say what was added
    python scripts/archive_combat_logs.py --dry-run

One folder per guild, `<guild name>-<world id>/`, one file per fight (`d045-arena-defend-the-title.jsonl`:
the day it was fought, then the fight). A log already archived is left alone; a world whose logs
are gone from `saves/` keeps its folder. `combat_analysis.py` and `combat_pairs.py` take the folder as is:

    python scripts/combat_analysis.py combat_lab/campaign
"""

import argparse
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVES = os.path.join(ROOT, "saves")
ARCHIVE = os.path.join(ROOT, "combat_lab", "campaign")


def guild_name(world_dir):
    try:
        with open(os.path.join(world_dir, "current.json"), encoding="utf-8") as f:
            return json.load(f).get("name") or "guild"
    except (OSError, ValueError):
        return "guild"


def folder_for(world_id, world_dir):
    name = re.sub(r"[^A-Za-z0-9]+", "-", guild_name(world_dir)).strip("-") or "guild"
    return f"{name}-{world_id}"


def archive(dry_run=False):
    """Returns `{folder: [files copied]}`."""
    added = {}
    if not os.path.isdir(SAVES):
        return added
    for world_id in sorted(os.listdir(SAVES)):
        world_dir = os.path.join(SAVES, world_id)
        logs = os.path.join(world_dir, "combat_logs")
        if not os.path.isdir(logs):
            continue
        folder = folder_for(world_id, world_dir)
        for fname in sorted(os.listdir(logs)):
            if not fname.endswith(".jsonl"):
                continue
            dest = os.path.join(ARCHIVE, folder, fname)
            if os.path.exists(dest):
                continue
            added.setdefault(folder, []).append(fname)
            if not dry_run:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(os.path.join(logs, fname), dest)
    return added


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="list what would be copied, copy nothing")
    args = ap.parse_args(argv)
    added = archive(args.dry_run)
    verb = "would add" if args.dry_run else "added"
    for folder, files in added.items():
        print(f"{folder}: {verb} {len(files)}")
    if not added:
        print("nothing new")
    return 0


if __name__ == "__main__":
    sys.exit(main())
