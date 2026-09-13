---
name: gartok-leadership
description: "GARTOK leadership system (Guild.leader + Group.leader, capacity/overextension) -- implemented, but the guild-size cap it was meant to justify is still open"
metadata: 
  node_type: memory
  type: project
  originSessionId: 96b5d0c5-17d5-4c3c-a1ac-f9ff46b17627
  modified: 2026-09-12T20:10:16.481Z
---

Implemented 2026-09-11 (same session as [[gartok-groups-refactor]]), part of
[[gartok-tactical-project]] and the answer to the "why have separate groups at
all" gap flagged in that session's project x-ray. Built from a voice memo the
user recorded the day before: every group needs a leader ("quem sou eu" at the
draft), leadership justifies Charisma's role, and a leader's capacity should be
what limits guild size ("o que me impede de fazer um grupo de cem mil
personagens? a capacidade dos meus líderes").

## As built (`gartok/group.py`, `gartok/guild.py`, `gartok/unit.py`, `gartok/economy.py`)

- **`Guild.leader`** -- "who am I", chosen as a new draft step after the 3
  squad picks (`DraftScreen` phase "leader"). Run-unique title, not scoped to a
  group. Auto-succeeds by Charisma on death; a deliberate change
  (`Guild.set_leader`) costs the run's **one free swap** (`leader_swaps_used`),
  then only death reshuffles it again.
- **`Group.leader`** -- defaults to highest Charisma member, freely swappable
  any time for any member (`Group.set_leader`, no cost, no limit), auto-succeeds
  by Charisma if the current one stops being a member.
- **Mechanical hooks**: market haggling routes through the group's leader
  (`economy._haggle_fraction`) instead of "whoever has the best Charisma",
  replacing an implicit rule with a real choice. `Group.capacity = 3 +
  leader's Charisma modifier`; past it, `Group.overextension` docks that many
  points of Mental Defense off every member (`Unit._derive_ac` reads
  `unit.group_overextension`, recomputed by `Guild._sync_leadership` after
  every membership change).
- Save v8 (`persist.py`): each group persists its leader's uid, the guild
  persists `leader` + `leader_swaps_used`. Old saves auto-pick a leader on
  load. 14 new tests (`test_leadership.py` + additions to `test_economy.py`/
  `test_persistence.py`), 346 pass.

## Open problem, flagged by the user right after shipping (not yet resolved)

Two complaints, given together, "mas por hora tudo bem" (not blocking, just
recorded):

1. **The Mental Defense penalty is too weak** -- a flat `-N` to one defensive
   stat doesn't read as a real cost yet.
2. **The bigger gap: this caps group SIZE, not group COUNT.** The user's own
   framing: "isso ainda não justificaria o que me impede de ter 900 grupos de
   1 unidade." Since capacity is checked *per group* and a solo group is
   trivially within capacity (1 member ≤ any leader's capacity), a player can
   fully dodge the cohesion cost by never merging past 1 member per group.
   **The leadership system currently answers "why keep one group small," not
   "why not have infinitely many groups."** Those are different questions and
   only the first one is solved.

Not decided: whether the fix is a hard cap (on group size, or on total
groups/roster), a harsher penalty, or something that costs the GUILD leader
(not each group's own leader) for spinning up more groups in the first place --
that last shape would actually engage `Guild.leader` mechanically, which today
does *nothing* but sit there as an identity (no gameplay hook of its own, only
`Group.leader` does work). Related and still unstarted: [[gartok-time-scarcity]]
(time isn't a resource yet, which is why splitting groups has no downside to
weigh against the upside) -- the user thinks the guild-size question and the
time-scarcity question are probably linked, but hasn't worked out how.

**Partial progress (2026-09-11): [[gartok-recruit-capacity]]** gives
`Guild.leader` its first real mechanical hook (their `racial_level` powers
recruitment capacity) and caps total roster growth via a sponsorship tree.
**This resolves population size, not group count** -- it does nothing to stop
900 solo groups once members already exist. Point 2 above is still open.

**Update 2026-09-12: user ran `balance_sim`-style simulations and the group-
count cap "se mostrou razoável"** -- deprioritized, not abandoned. Explicit
call: don't touch this until it actually shows up as a problem in real
gameplay; revisit then. Time-scarcity ([[gartok-time-scarcity]]) is still
independently worth doing (see that memo), just not *because of* this anymore.
