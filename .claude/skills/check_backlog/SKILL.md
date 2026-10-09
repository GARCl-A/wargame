---
name: check_backlog
description: Tech-lead / PM review of the backlog against the last 5 commits — audits whether `docs/plans/backlog.md` (and the docs it points to) reflect what shipped, ranks the Ready-to-do items by impact, separates what still needs a design decision from what needs a scope answer, and ends with an ordered action plan. Use when the user types /check_backlog or asks "o que fazer agora", "revisa o backlog", "o backlog está em dia?".
---

Act as the user's tech lead / product manager. Reply in Portuguese. Read-only:
do not edit files unless the user asks afterwards.

## Inputs

- `git log -5 --stat --format='--- %h %s%n%b'` — the last 5 commits, with bodies.
- `docs/plans/backlog.md` — the one place for open work (parts: *Ready to do*
  by size, *Needs more information*).
- Docs the backlog or the commits point to (`docs/plans/economy_sim_v2.md`,
  `campaign_ai_roadmap.md`, `AGENTS.md` module table, `README.md`).

## Steps

1. **Sync audit.** For each of the 5 commits, check that what it delivered is
   reflected in the backlog and the docs:
   - items it finished were deleted from the backlog (the backlog's own rule);
   - items it created or changed were added or reworded;
   - claims in open items still hold — **verify against the code**, don't trust
     the prose (`grep` for the flag, the function, the file the item names);
   - docs that describe a thing as "not built" / "a switch" / "B1" that now
     exists.
   Run `python -m pytest tests/ -q` as the sanity gate and report the result.
   List each divergence with file and line, and say what should change.

2. **Execution priority.** From *Ready to do*, list the highest immediate-impact
   items, ordered, each with one line of why (what it unblocks, how cheap it is,
   what depends on it). Say which Large items should *not* start yet and why.

3. **Refinement.** For the open items that need work before they can be built,
   split them in two lists:
   - **Design decisions** (architecture / system shape): what must be decided,
     the options, and a recommendation.
   - **Unanswered business / scope questions**: what the user has to answer.
   Point out items that share a mechanism (e.g. two features that need the same
   new order kind) so the decision is made once.

4. **Action plan.** An ordered list of what the user should focus on now,
   starting with the cheap doc fixes from step 1. Close by offering to apply
   those doc fixes.

## Format

Four sections matching the steps, short bullets, file references as markdown
links. Facts you checked are stated plainly; anything you did not verify is
marked as such.
