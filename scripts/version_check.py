"""Keep `docs/versions.csv` honest. Run by `build_exe.bat` (with --build) and the pre-commit skill.

Errors (exit 1): GAME_VERSION or SAVE_VERSION differs from the last row of the table.
--build releases by itself when code changed since the last row: it writes a save with the last
released code (a git worktree), tries to load it with this code, bumps SAVE_VERSION when it no
longer loads, bumps GAME_VERSION (minor when saves break, else patch) and appends the row.
Then it bakes the short HEAD hash into gartok/build_info.py (gitignored) for the exe.
Commit the files it touched (versions.csv, version.py, persist.py)."""

import csv
import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gartok import persist  # noqa: E402
from gartok.persist import SAVE_VERSION  # noqa: E402
from gartok.version import GAME_VERSION  # noqa: E402

CSV_PATH = os.path.join(ROOT, "docs", "versions.csv")
VERSION_PY = os.path.join(ROOT, "gartok", "version.py")
PERSIST_PY = os.path.join(ROOT, "gartok", "persist.py")
RELEASE_FILES = {"docs/versions.csv", "gartok/version.py", "gartok/persist.py"}
FIELDS = ["version", "date", "hash", "save_version", "breaks_save", "path"]

PROBE = """
import sys
from gartok import persist
from gartok.guild import Guild
from gartok.unit import Unit
persist.SAVE_DIR = sys.argv[1]
persist.save_game("probe", Guild([Unit("player") for _ in range(3)], node="wilds"))
"""


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=ROOT).stdout.strip()


def check(rows, dirty_files):
    """-> (errors, warnings)"""
    errors, warnings = [], []
    if not rows:
        return ["docs/versions.csv has no rows"], warnings
    last = rows[-1]
    if last["version"] != GAME_VERSION:
        errors.append(f"GAME_VERSION is {GAME_VERSION} but the last row is {last['version']}: "
                      f"build with --build to release it (or fix the constant)")
    if str(SAVE_VERSION) != last["save_version"]:
        errors.append(f"SAVE_VERSION moved ({last['save_version']} -> {SAVE_VERSION}) but the last row "
                      f"is v{last['version']}: build with --build to release it")
    stray = [f for f in dirty_files if f not in RELEASE_FILES]
    if stray:
        warnings.append("the working tree has uncommitted changes; the build will not match its hash")
    return errors, warnings


def next_version(version, breaks):
    major, minor, patch = (int(p) for p in version.split("."))
    return f"{major}.{minor + 1}.0" if breaks else f"{major}.{minor}.{patch + 1}"


def code_changed_since(last_hash, head):
    """False when the commits since `last_hash` only touch the release bookkeeping itself."""
    if not last_hash or last_hash == head:
        return False
    for path in git("diff", "--name-only", f"{last_hash}..{head}").splitlines():
        if path not in RELEASE_FILES:
            return True
        if path == "gartok/persist.py":
            lines = git("diff", "-U0", f"{last_hash}..{head}", "--", path).splitlines()
            if any(ln[:1] in "+-" and not ln.startswith(("+++", "---")) and "SAVE_VERSION =" not in ln
                   for ln in lines):
                return True
    return False


def saves_break(last_hash):
    """Write a save with the code of `last_hash`, load it with this code. -> (breaks, reason)"""
    tmp = tempfile.mkdtemp(prefix="gartok_probe_")
    tree = os.path.join(tmp, "tree")
    saves = os.path.join(tmp, "saves")
    try:
        if subprocess.run(["git", "worktree", "add", "--detach", tree, last_hash], cwd=ROOT,
                          capture_output=True).returncode:
            return True, f"could not check out {last_hash[:7]}"
        out = subprocess.run([sys.executable, "-c", PROBE, saves], cwd=tree, capture_output=True, text=True)
        if out.returncode:
            return True, f"the last release could not write a probe save: {out.stderr.strip()[-200:]}"
        persist.SAVE_DIR = saves
        try:
            persist.load_game("probe")
        except Exception as exc:   # any failure to read the old save is a break
            return True, f"{type(exc).__name__}: {str(exc)[:200]}"
        finally:
            persist.SAVE_DIR = os.path.join(ROOT, "saves")
        return False, "the last release's save loads"
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", tree], cwd=ROOT, capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)


def sub_in(path, pattern, repl):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    text, n = re.subn(pattern, repl, text, count=1, flags=re.M)
    assert n == 1, f"{pattern} not found in {path}"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def release(rows, head):
    """Bump what must be bumped and append the row. -> the new row."""
    last = rows[-1]
    breaks, reason = saves_break(last["hash"])
    save_version = int(last["save_version"])
    if breaks:
        save_version += 1
        sub_in(PERSIST_PY, r"^SAVE_VERSION = \d+", f"SAVE_VERSION = {save_version}")
    version = next_version(last["version"], breaks)
    sub_in(VERSION_PY, r'^GAME_VERSION = "[^"]*"', f'GAME_VERSION = "{version}"')
    row = {"version": version, "date": datetime.date.today().isoformat(), "hash": head,
           "save_version": str(save_version), "breaks_save": "yes" if breaks else "no", "path": ""}
    with open(CSV_PATH, "a", encoding="utf-8", newline="") as fh:
        csv.DictWriter(fh, FIELDS, lineterminator="\n").writerow(row)
    print(f"Released v{version} ({head[:7]}): saves {'BREAK' if breaks else 'still load'} ({reason})")
    return row


def main(argv):
    with open(CSV_PATH, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    head = git("rev-parse", "HEAD")
    building = "--build" in argv
    if building and rows and code_changed_since(rows[-1]["hash"], head):
        release(rows, head)
        print("Commit docs/versions.csv, gartok/version.py and gartok/persist.py (when it changed).")
        rows = None
    dirty = [ln.split(None, 1)[1] for ln in git("status", "--porcelain").splitlines()]
    errors, warnings = ([], check(rows, dirty)[1]) if rows is None else check(rows, dirty)
    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    if errors:
        return 1
    return _finish(head) if building else 0


def _finish(head):
    with open(os.path.join(ROOT, "gartok", "build_info.py"), "w", encoding="utf-8") as fh:
        fh.write(f'BUILD_HASH = "{head[:7] or "unknown"}"\n')
    print(f"Build ({head[:7]})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
