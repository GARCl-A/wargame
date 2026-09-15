---
name: pre-commit
description: Review gate before any git commit in this repo — checks the diff, runs the test suite, drafts a commit message in the project's own style, and waits for explicit approval before committing.
---

Run this before **every** `git commit` in this repo. Never commit without going
through it, and never commit without the user's explicit approval that comes
out the other end — no exceptions, no "this one's obviously fine."

## Steps

1. **See the whole change.** `git status --short` (staged, unstaged, untracked
   — never `-uall`) and `git diff` / `git diff --staged` for everything that
   would land in the commit. Read it; don't skim the file list and assume.

2. **Tests must pass first.** Run `python -m pytest tests/`. A failure stops
   this skill here — report it and fix or ask before going any further. Never
   let a red suite ride into a commit. (`python sim_test.py` is a good second
   check for anything touching combat/AI, but isn't a hard gate the way pytest
   is.)

   is.)

3. **Check for missing imports and undefined variables (Static Analysis).**
   Python tests often miss `NameError`s in UI hover states or error paths.
   Read the diff carefully: for every new variable, constant, or function used
   in the changes, verify it is either defined in the scope or imported at the
   top of the file. Do not commit code that references undefined variables.

4. **Review the diff for quality, not just correctness — this is not optional
   and not the same thing as "tests pass."** A green suite proves the code
   works; it says nothing about whether it was the right way to build it. Go
   through the actual diff and ask, file by file:

   - **Architecture.** Is this the best structural decision available, or is
     there a simpler one that fits how this codebase already solves similar
     problems? Would someone who knows this repo well build it this way, or
     did it take a shortcut that will need redoing later?
   - **Project health.** Does this leave the codebase easier to extend, or
     does it quietly add debt — a special case, a second way to do something
     that already had one, a pattern that fights the architecture instead of
     joining it?
   - **Follows the project's own conventions.** Check it against similar
     existing code and, for `gartok/`, the "How to add a system" recipes in
     `README.md` — a new registry-like thing should look like `abilities.py`/
     `talents.py`, a new screen hook should look like the existing ones, etc.
     A parallel mechanism that duplicates an existing one is a smell, not a
     stylistic choice.
   - **State & Logic Holes (Blind spots).** Actively hunt for edge cases in
     persistence and object lifecycles. Does a counter decrement without ever
     resetting? If a consumable is dropped, is the backup activated? Are we
     assuming an attribute exists without enforcing it? Do not trust that the
     old code was perfect — if you copy a pattern, audit it for hidden flaws
     before committing.
   - **Efficiency.** Anything recomputed every frame that shouldn't be,
     redundant passes over the same data, an O(n²) shortcut where the
     existing pattern in this file is O(n).
   - **Comments.** This project defaults to none. Cut anything that restates
     what the code already says; keep only a comment that explains a
     non-obvious *why* (a constraint, a workaround, a subtlety a reader would
     otherwise trip on). A bloated docstring that repeats the module below it
     gets trimmed.

   Fix what's clearly wrong before moving on. For a genuine judgment call
   between two reasonable approaches, don't silently pick one — surface it in
   the summary (step 5) instead.

4. **Look for anything that shouldn't ride along.** Common culprits in this
   repo: files under `saves/` (per-machine save slots, not game content),
   `__pycache__`/`.pyc`, stray debug prints, anything that looks like a
   credential or token even in an innocuous-looking file. If `git add` was run
   broadly, re-check `git status` after staging.

5. **Recap decisions and implementation — separate from, and more complete
   than, the commit message.** The commit message (step 6) stays terse and
   in the repo's own compressed style; this recap is for the user, right now,
   in the conversation, so they can approve with the full picture instead of
   reconstructing it from a diff. Two parts, both required:

   - **What was implemented** — the feature-level shape of the change, not a
     file list: what a player/user of it would notice, and what the new
     pieces are underneath (new modules, new registries, what got wired into
     what). If work happened in stages this session, say so.
   - **What was decided, and why** — every point where more than one
     reasonable approach existed and one was picked: architectural choices,
     anything reused from an existing pattern instead of invented fresh,
     anywhere a plan changed mid-work, and everything that came out of step 3
     (both what got fixed and *why that fix specifically*, and anything
     surfaced but deliberately left alone, with the reason). A decision with
     no real alternative isn't worth a line here — this is for the calls
     that could have gone another way.

   This is prose/bullets in the conversation, not a file — don't create a
   decisions log or design-doc artifact for it unless the user asks for one.

6. **Draft the commit message in this repo's own voice**, not a generic one:
   check `git log -3 --format='%B---'` for the current convention before
   writing (`--oneline` alone hides the body). As of this writing that's
   Portuguese, present-tense, no accented characters, a short colon-split
   headline, blank line, then a bulleted body of concrete points (dashes,
   ~72-column wrap, mixes technical and player-facing detail) — e.g.
   `"Recrutamento tem limite: cada personagem so patrocina ate sua capacidade"`
   followed by bullets on `capacity()`, what it gates, what doc it corrects.
   No trailing period on the headline. Match whatever the log actually shows
   at the time, since style can drift.

   **No `Co-Authored-By:` trailer or AI attribution, ever.** The user reviews
   every change and keeps the history free of tooling noise.

7. **Present the summary + drafted message, then stop.** Wait for the user's
   explicit approval in that same conversation. "Looks fine" / "go" / a
   thumbs-up counts; silence, a topic change, or you deciding it's obviously
   fine does not.

8. **Only after approval:** stage exactly the files that belong to this change
   (named explicitly — not a blanket `git add -A`/`-A`-then-hope), commit with
   the approved message, then `git status` to confirm a clean result.

9. **If this commit closes a major arc**, update the project context:
   - Create or update a reference file in
     `.agents/skills/project-context/references/` with the design rationale
     (what was decided and why, what NOT to redo).
   - Update the index table in
     `.agents/skills/project-context/SKILL.md`.
   - If a design premise changed, update `AGENTS.md`.
   Stage these alongside the commit or as a follow-up commit.

## Hard rules

- Never `--no-verify`, never skip or bypass a hook.
- Never `git commit --amend` unless the user asks for it by name.
- Never force-push, never touch `main` history.
- Step 3 (the quality pass) is never skipped for being "too small a change" —
  a one-line diff can still be the wrong one line.
- If the user has already reviewed the diff and says "just commit it," steps
  1–6 still happen (silently is fine) but step 7's approval is satisfied by
  that instruction — don't re-ask once they've already said go.
