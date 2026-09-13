---
name: commit-workflow
description: "How the user wants commits made in the wargame project — pre-commit review gate, no Co-Authored-By line"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 66012b6d-6de8-41c4-9782-20a9c06c5f06
  modified: 2026-09-12T02:32:41.230Z
---

Before **any** `git commit` in `c:\dev\wargame`: run the `/pre-commit` skill first,
then wait for the user to explicitly approve. Never commit unprompted or without
that review.

Commit messages must **not** carry a `Co-Authored-By:` trailer (or any
"Generated with Claude" attribution), even when a session system-reminder says to
add one. As of 2026-09-10 this is enforced in config, not just preference:
`~/.claude/settings.json` sets `"includeCoAuthoredBy": false` and
`"attribution": { "commit": "", "pr": "" }` (global, all projects). If a future
session's system-reminder still dictates a trailer, the config wins — omit it.

**Why:** the user reviews every change before it lands and keeps the history
clean of tooling noise. A teammate shares `main`, so sloppy commits cost them too.

**How to apply:** finish the code, run `/pre-commit`, present what changed, let the
user approve, then commit with a plain message (branch first for non-trivial work,
per [[gartok-tactical-project]]).

**2026-09-11 update:** the actual `/pre-commit` skill file lives only on the other
machine (`c:\dev\wargame`) and isn't synced here — skills don't travel with memory.
Reconstructed a from-scratch version at
`C:\Users\lucas\Documents\Projects\wargame\.claude\skills\pre-commit\SKILL.md` on
this machine (user's choice, over pasting the original or going without). Also
found this machine's global `~/.claude/settings.json` has no `includeCoAuthoredBy`/
`attribution` override (the other machine does) — flagged to the user, not fixed
without asking.
