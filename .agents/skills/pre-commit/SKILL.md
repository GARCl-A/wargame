---
name: pre-commit
description: Review gate before any git commit in this repo — runs the tests, reviews the diff and fixes clear-cut findings itself, drafts a commit message in the project's own style, and waits for explicit approval before committing.
---

Run this before **every** `git commit` in this repo. Never commit without going
through it, and never commit without the user's explicit approval that comes
out the other end — no exceptions, no "this one's obviously fine."

This file is the canonical, self-contained pre-commit process for this repo,
read by both Antigravity (native `.agents/` support) and Claude Code (its
user-level `pre-commit` skill defers to it entirely). Keep it up to date here
first if the process changes.

The user codes iteratively, so the final diff is often the accumulated path
rather than the shape someone would pick starting from scratch. Review it with
that "end of the road" eye: leftover mess is the obvious cost, a solution that
only makes sense historically is the expensive one.

## Steps

1. **See the whole change.** `git status --short` (staged, unstaged, untracked
   — never `-uall`) and `git diff` / `git diff --staged` for everything that
   would land in the commit. Read it; don't skim the file list and assume.
   Read whole files when the diff alone doesn't show how the change fits in.
   State the apparent goal of the change in one line (it goes in the recap, so
   the user can correct a misreading early); if the diff is too ambiguous to
   infer it, ask.

2. **Tests must pass first.** Run `python -m pytest tests/`. A failure stops
   this skill here — report it and fix or ask before going any further. Never
   let a red suite ride into a commit. (`python sim_test.py` is a good second
   check for anything touching combat/AI, but isn't a hard gate the way pytest
   is.)

3. **Check for missing imports and undefined variables (static analysis).**
   Python tests often miss `NameError`s in UI hover states or error paths.
   For every new variable, constant, or function used in the diff, verify it is
   defined in scope or imported at the top of the file.

4. **Review the diff for quality, not just correctness — never skipped, not
   even for a one-line diff.** A green suite proves the code works; it says
   nothing about whether it was the right way to build it. File by file:

   - **Architecture & approach.** Is this the best structural decision
     available, or is there a simpler one that fits how this codebase already
     solves similar problems? Typical smells: a helper or pattern already
     exists and was reimplemented by hand; the fix sits in the wrong layer
     (symptom instead of cause); a special case where the general one would
     cover it (or the reverse: generalised for a single use); a flag or
     indirection that only exists because the first attempt needed it.
     Only raise an alternative when the difference is real and worth the
     rework, and say what it would cost ("swap two lines" vs "redo the method").
   - **Project health & conventions.** Does it leave the codebase easier to
     extend, or add debt — a second way to do something that already had one,
     a pattern that fights the architecture? Check against similar existing
     code and, for `gartok/`, the "How to add a system" recipes in `README.md`
     (a new registry looks like `abilities.py`/`talents.py`, a new screen hook
     like the existing ones, UI built on `gartok/ui/`). A parallel mechanism
     duplicating an existing one is a smell, not a stylistic choice.
   - **State & logic holes.** Hunt for edge cases in persistence and object
     lifecycles. A counter that decrements without ever resetting? A consumable
     dropped without the backup activating? An attribute assumed to exist but
     never enforced? If a pattern was copied, audit it for hidden flaws.
   - **Efficiency.** Anything recomputed every frame that shouldn't be,
     redundant passes over the same data, O(n²) where the file's pattern is O(n).
   - **Comments.** The project default is none. Keep a comment only if it
     answers a "why" the code can't: a constraint, a workaround with its
     reason, a trap for the next editor. Cut narration of the line below,
     decorative headers, comments or docstrings that repeat the name or
     signature, process notes to the author ("now we handle X", "TODO: test"),
     and blocks a rename or an extracted method would make clearer. A
     justified-but-bloated comment gets trimmed to its lean version.
   - **Mess.** Debug prints, commented-out code, unused imports/variables,
     stray manual-test files, hardcoded local paths or credentials, ownerless
     TODOs, duplication the diff introduced. Skip style the linter already
     covers; review only what is in the diff, not pre-existing problems it
     didn't touch.

   **Apply the fixes yourself — don't hand the user a list to approve.** Every
   finding with one clearly right answer gets fixed on the spot, nitpicks
   included: trim a comment or docstring, hoist a long inline expression into
   a variable, drop dead code, rename for convention, add a missing import. The
   user should never have to answer "adjust these?" with "yes, do all of it."

   - After editing, re-run `python -m pytest tests/` (step 2) so the fixes are
     covered by the green suite, and re-read the resulting diff.
   - Ask the user only about what genuinely needs their call: two reasonable
     designs with different trade-offs, a behaviour change beyond the diff's
     intent, or a change that widens scope. Put those in the recap (step 7) as
     explicit questions, each with a recommendation.
   - Things checked and deliberately left alone (e.g. behaviour that matches the
     backlog and has a test) get one line in the recap — not a question.
   - Don't invent findings to fill a category; "nothing here" is a valid result.

5. **Keep the docs and the backlog in sync with what this diff changes.**
   Stale docs are what made `/check_backlog` find drift after the fact; close
   it here, in the same commit, instead. The fixes are yours to apply (same
   rule as step 4).

   - **Items the diff finishes or reshapes.** Read `docs/plans/backlog.md`.
     An item the diff completes is deleted (the backlog's own rule); one it
     changes is reworded; a claim that stops being true ("now", "not built",
     a size, a count) is corrected.
   - **Docs that describe what changed.** For each flag, function, constant,
     module or behaviour the diff adds, removes or renames, `grep` the names
     (and the old prose, such as "never heals") across `RULES.md`,
     `README.md`, `AGENTS.md` (the module table), `docs/plans/*.md` and
     `locales/en.json` tutorial copy. Fix every sentence that is now false.
     `REFERENCE.md` is generated: regenerate it, never edit it by hand.
   - **Follow-ups the diff creates.** Debt left on purpose, a split-off task
     or a decision deferred goes into the backlog as an item (size, what
     blocks it), not into a code comment or the recap alone.
   - Say in the recap what was updated and where. "Nothing to sync" is valid,
     but only after the greps were run.

6. **Look for anything that shouldn't ride along.** Common culprits in this
   repo: files under `saves/` (per-machine save slots, not game content),
   `__pycache__`/`.pyc`, stray debug prints, anything that looks like a
   credential or token. Files that don't belong to this change (untracked
   skills, unrelated edits) are never folded in silently: leave them out of
   the commit, mention them in one line and propose a separate commit. If
   `git add` was run broadly, re-check `git status` after staging.

7. **Recap decisions and implementation — separate from, and more complete
   than, the commit message.** The commit message (step 8) stays terse and in
   the repo's own compressed style; this recap is for the user, right now, in
   the conversation, so they can approve with the full picture instead of
   reconstructing it from a diff. Parts, in order:

   - **Apparent goal** — the one line from step 1.
   - **What was implemented** — the feature-level shape of the change, not a
     file list: what a player/user of it would notice, and what the new
     pieces are underneath (new modules, new registries, what got wired into
     what). If work happened in stages this session, say so.
   - **What was decided, and why** — every point where more than one
     reasonable approach existed and one was picked: architectural choices,
     anything reused from an existing pattern instead of invented fresh,
     anywhere a plan changed mid-work, and everything that came out of step 4
     (what got fixed and *why that fix specifically*, and anything surfaced
     but deliberately left alone, with the reason). A decision with no real
     alternative isn't worth a line.
   - **Open questions** — only the genuine calls from step 4, each with your
     recommendation. Omit the section if there are none.

   Concise: a line per point, not a paragraph. This is prose/bullets in the
   conversation, not a file — don't create a decisions log or design-doc
   artifact for it unless the user asks for one.

8. **Draft the commit message in this repo's own voice**, not a generic one:
   check `git log -3 --format='%B---'` for the current convention before
   writing (`--oneline` alone hides the body). As of this writing that's
   Portuguese, present-tense, no accented characters, a short colon-split
   headline, blank line, then a bulleted body of concrete points (dashes,
   ~72-column wrap, mixes technical and player-facing detail) — e.g.
   `"Recrutamento tem limite: cada personagem so patrocina ate sua capacidade"`
   followed by bullets on `capacity()`, what it gates, what doc it corrects.
   The headline states the intent of the change, not the files touched. No
   trailing period on the headline. Match whatever the log actually shows at
   the time, since style can drift. If behaviour and refactoring are mixed in
   one diff, or the bullets don't fit one theme, propose splitting into two
   commits with a message each.

   **No `Co-Authored-By:` trailer or AI attribution, ever.** The user reviews
   every change and keeps the history free of tooling noise.

9. **Present the summary + drafted message, then stop.** Wait for the user's
   explicit approval in that same conversation. "Looks fine" / "go" / a
   thumbs-up counts; silence, a topic change, or you deciding it's obviously
   fine does not.

10. **Only after approval:** `git pull` first (a teammate works on `main` in
   parallel), stage exactly the files that belong to this change (named
   explicitly — not a blanket `git add -A`), commit with the approved message,
   then `git status` to confirm a clean result.

11. **If this commit closes a major arc**, update the project context:
    - Create or update a reference file in
      `.agents/skills/project-context/references/` with the design rationale
      (what was decided and why, what NOT to redo).
    - Update the index table in `.agents/skills/project-context/SKILL.md`.
    - If a design premise changed, update `AGENTS.md`.
    Stage these alongside the commit or as a follow-up commit.

## Hard rules

- Never `--no-verify`, never skip or bypass a hook.
- Never `git commit --amend` unless the user asks for it by name.
- Never force-push, never touch `main` history.
- Step 4 (the quality pass) is never skipped for being "too small a change" —
  a one-line diff can still be the wrong one line.
- If the user has already reviewed the diff and says "just commit it," steps
  1–8 still happen (silently is fine) but step 9's approval is satisfied by
  that instruction — don't re-ask once they've already said go.
