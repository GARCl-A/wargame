"""Publish the last built version as a GitHub release. Run by `release.bat`, after `build_exe.bat`
and after its version bump is committed and pushed.

Reads the last row of `docs/versions.csv`, refuses when the tree is dirty, HEAD is not on
origin/main, HEAD or the exe in dist/ carries code the row does not, or the tag already exists.
Prints the notes (the commit subjects since the previous row) and asks before it creates the tag
`v<version>` on HEAD and uploads dist/GARTOK.exe with `gh`. --dry-run stops after the notes, --yes skips the question."""

import csv
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.version_check import CSV_PATH, RELEASE_FILES, code_changed_since, git

EXE = os.path.join(ROOT, "dist", "GARTOK.exe")
BUILD_INFO = os.path.join(ROOT, "gartok", "build_info.py")


def changes(prev_hash, last_hash):
    """Subjects of the commits in the release, oldest first, without the version bookkeeping ones."""
    out = git("log", "--reverse", "--no-merges", "--name-only", "--format=%x00%s", f"{prev_hash}..{last_hash}")
    subjects = []
    for block in out.split("\x00")[1:]:
        subject, *files = [ln for ln in block.splitlines() if ln.strip()]
        if not files or any(f not in RELEASE_FILES for f in files):
            subjects.append(subject)
    return subjects


def notes(row, subjects):
    lines = []
    if row["breaks_save"] == "yes":
        lines += ["**Esta versão não abre os saves das anteriores.**", ""]
    lines += ["## Mudanças", ""]
    lines += [f"- {s}" for s in subjects] or ["- Sem mudanças de jogo."]
    lines += ["", "## Como jogar", "",
              ("Baixe o `GARTOK.exe` abaixo e execute. O executável não é assinado: se o Windows mostrar "
               "o aviso do SmartScreen, clique em *Mais informações* e depois em *Executar assim mesmo*.")]
    return "\n".join(lines) + "\n"


def built_hash():
    try:
        with open(BUILD_INFO, encoding="utf-8") as fh:
            return fh.read().split('"')[1]
    except (OSError, IndexError):
        return ""


def problems(row, head, tag):
    """Why this release cannot go out now, as sentences. Empty when it can."""
    found = []
    if not os.path.exists(EXE):
        found.append("dist/GARTOK.exe does not exist: run build_exe.bat")
    built = built_hash()
    if not built:
        found.append("gartok/build_info.py is missing: run build_exe.bat")
    elif code_changed_since(row["hash"], git("rev-parse", built) or built):
        found.append(f"the exe was built from {built}, which is not v{row['version']}: run build_exe.bat")
    if git("status", "--porcelain"):
        found.append("the working tree has uncommitted changes: commit the version bump first")
    if code_changed_since(row["hash"], head):
        found.append(f"HEAD has code newer than v{row['version']}: run build_exe.bat to release it")
    subprocess.run(["git", "fetch", "--quiet", "--tags", "origin"], cwd=ROOT, check=False)
    if subprocess.run(["git", "merge-base", "--is-ancestor", head, "origin/main"], cwd=ROOT, check=False).returncode:
        found.append("HEAD is not on origin/main: push first")
    if git("tag", "--list", tag):
        found.append(f"the tag {tag} already exists: this version is already released")
    return found


def main(argv):
    with open(CSV_PATH, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    row = rows[-1]
    tag = f"v{row['version']}"
    head = git("rev-parse", "HEAD")
    found = problems(row, head, tag)
    for p in found:
        print(f"ERROR: {p}")
    text = notes(row, changes(rows[-2]["hash"], row["hash"]) if len(rows) > 1 else [])
    print(f"\n=== GARTOK {row['version']} ({tag} on {head[:7]}) ===\n")
    print(text)
    if found:
        return 1
    if "--dry-run" in argv:
        return 0
    if "--yes" not in argv and input(f"Publish {tag} on GitHub? [y/N] ").strip().lower() != "y":
        print("Not published.")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        notes_path = os.path.join(tmp, "notes.md")
        with open(notes_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return subprocess.run(["gh", "release", "create", tag, EXE, "--title", f"GARTOK {row['version']}",
                               "--notes-file", notes_path, "--target", head], cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
