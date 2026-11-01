"""Keep `docs/versions.csv` honest. Run by `build_exe.bat` (with --build) and the pre-commit skill.

Errors (exit 1): GAME_VERSION or SAVE_VERSION differs from the last row of the table.
Warning: only the dirty tree (commits past the last row are normal while the version is unchanged).
--release appends the row for the current GAME_VERSION itself (date, HEAD, save format, breaks_save).
--build also bakes the short HEAD hash into gartok/build_info.py (gitignored) for the exe."""

import csv
import datetime
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gartok.persist import SAVE_VERSION  # noqa: E402
from gartok.version import GAME_VERSION  # noqa: E402


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=ROOT).stdout.strip()


def check(rows, head, dirty):  # head kept for callers; commits past the last row are not a problem
    """-> (errors, warnings)"""
    errors, warnings = [], []
    if not rows:
        return ["docs/versions.csv has no rows"], warnings
    last = rows[-1]
    if last["version"] != GAME_VERSION:
        errors.append(f"GAME_VERSION is {GAME_VERSION} but the last row is {last['version']}: "
                      f"run scripts/version_check.py --release (or fix the constant)")
    if str(SAVE_VERSION) != last["save_version"]:
        errors.append(f"SAVE_VERSION moved ({last['save_version']} -> {SAVE_VERSION}): saves break. "
                      f"Bump GAME_VERSION and run scripts/version_check.py --release")
    if dirty:
        warnings.append("the working tree has uncommitted changes; the build will not match its hash")
    return errors, warnings


def release_row(rows, head):
    """The row for the current GAME_VERSION, or None when the table already has it."""
    if rows and rows[-1]["version"] == GAME_VERSION:
        return None
    breaks = bool(rows) and rows[-1]["save_version"] != str(SAVE_VERSION)
    return {"version": GAME_VERSION, "date": datetime.date.today().isoformat(), "hash": head,
            "save_version": str(SAVE_VERSION), "breaks_save": "yes" if breaks else "no", "path": ""}


def main(argv):
    with open(os.path.join(ROOT, "docs", "versions.csv"), encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    head = git("rev-parse", "HEAD")
    if "--release" in argv:
        row = release_row(rows, head)
        if row is None:
            print(f"v{GAME_VERSION} is already in docs/versions.csv: bump GAME_VERSION first")
            return 1
        with open(os.path.join(ROOT, "docs", "versions.csv"), "a", encoding="utf-8", newline="") as fh:
            csv.DictWriter(fh, list(row), lineterminator="\n").writerow(row)
        print(f"Added v{GAME_VERSION} ({head[:7]}, breaks_save={row['breaks_save']}); commit docs/versions.csv")
        return 0
    errors, warnings = check(rows, head, bool(git("status", "--porcelain")))
    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    if errors:
        return 1
    if "--build" in argv:
        with open(os.path.join(ROOT, "gartok", "build_info.py"), "w", encoding="utf-8") as fh:
            fh.write(f'BUILD_HASH = "{head[:7] or "unknown"}"\n')
        print(f"Build {GAME_VERSION} ({head[:7]})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
