---
name: release
description: Ships a new version of the game end to end — tests, build of the exe, version bump commit, push and the GitHub release with its notes. Use when the user types /release or says "lançar release", "lança a release", "solta uma versão", "publica a versão", "faz a release".
---

The user asking for a release is the approval to build, to commit the version bump, to push `main`
and to publish on GitHub. It is not approval to commit anything else: other work goes through the
`pre-commit` skill as always.

Run from the repo root. Stop at the first step that fails, say which one and show its output; never
work around a refusal of `scripts/release.py` or `scripts/version_check.py`.

## Steps

1. **Clean tree.** `git status --porcelain` must be empty. If it is not, stop and list the files:
   the user decides whether they go in (through `pre-commit`) or wait. Do not stash, do not commit them.

2. **Up to date.** `git pull --rebase`. On a conflict, `git rebase --abort`, stop and ask.

3. **Tests.** `python -m pytest tests/ -n auto -m "not balance"`. A failure ends the release.

4. **Build.** `cmd /c ".\build_exe.bat < NUL"` (the `< NUL` answers the script's `pause`; without
   the `.\` cmd does not find the script here), with a 10 minute timeout. It must end with `Done!`
   and leave a fresh `dist/GARTOK.exe`; the line `Released v<version>` says a new version was cut,
   and whether saves break.
   When the output has no `Released` line, no code changed since the last version: go on, step 6
   refuses by itself if that version is already published.

5. **Bump commit.** When the build touched `docs/versions.csv`, `gartok/version.py` or
   `gartok/persist.py`, check that `git status --porcelain` lists nothing else, then commit exactly
   those files as `Versao <version>` (no attribution line) and `git push`.
   Any other dirty file here is a bug of the build: stop and report it.

6. **Publish.** `python scripts/release.py --yes`. It prints the notes, creates the tag
   `v<version>` on HEAD and uploads the exe. On `ERROR:` lines, report them as they are.

7. **Report**, in Portuguese: the version, whether it breaks saves, the release URL that `gh`
   printed, and the notes' list of changes.
