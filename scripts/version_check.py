"""Keep `docs/versions.csv` honest. Run by `build_exe.bat` (with --build) and the pre-commit skill.

Errors (exit 1): GAME_VERSION or SAVE_VERSION differs from the last row of the table.
Warning: HEAD moved past the last row's hash; fill a new row and say whether saves break.
--build also bakes the short HEAD hash into gartok/build_info.py (gitignored) for the exe."""

import csv
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gartok.persist import SAVE_VERSION  # noqa: E402
from gartok.version import GAME_VERSION  # noqa: E402


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=ROOT).stdout.strip()


def check(rows, head, dirty):
    """-> (errors, warnings)"""
    errors, warnings = [], []
    if not rows:
        return ["docs/versions.csv has no rows"], warnings
    last = rows[-1]
    if last["version"] != GAME_VERSION:
        errors.append(f"GAME_VERSION is {GAME_VERSION} but the last row is {last['version']}: "
                      f"add a row (or fix the constant)")
    if str(SAVE_VERSION) != last["save_version"]:
        errors.append(f"SAVE_VERSION moved ({last['save_version']} -> {SAVE_VERSION}): saves break. "
                      f"Bump GAME_VERSION and add a row with breaks_save=yes")
    if head and head != last["hash"]:
        n = git("rev-list", "--count", f"{last['hash']}..HEAD") or "?"
        warnings.append(f"{n} commit(s) since v{last['version']} ({last['hash'][:7]}): add a row to "
                        f"docs/versions.csv and check whether saves break")
    if dirty:
        warnings.append("the working tree has uncommitted changes; the build will not match its hash")
    return errors, warnings


def main(argv):
    with open(os.path.join(ROOT, "docs", "versions.csv"), encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    head = git("rev-parse", "HEAD")
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
