---
name: gartok-recruit-capacity
description: "GARTOK recruitment chaining: each member can only sponsor recruit_capacity people (BASE + Charisma mod), guild leader adds racial_level -- the real answer to guild population growth"
metadata:
  node_type: memory
  type: project
  originSessionId: 96b5d0c5-17d5-4c3c-a1ac-f9ff46b17627
  modified: 2026-09-11T22:42:07.052Z
---

Designed and implemented 2026-09-11, part of [[gartok-tactical-project]].
Directly follows up on [[gartok-leadership]]'s open problem ("this caps group
SIZE, not group COUNT / total roster") and activates the `recruited_by` field
that [[gartok-open-world-vision]] flagged as inert since `recruit.py` existed.

## The idea (user's framing)

"Cada personagem só pode ter X subordinados (sendo X o valor máximo de pessoas
que ele poderia recrutar). O líder da guilda tem um buff FORTE: soma seu
próprio nível a esse valor. Os personagens incapazes de recrutar ficam na
folha da guilda e são os limitadores de quantidade."

## Math validated before building (worth re-deriving if this gets retuned)

This is a branching process, not a flat cap — whether the roster's growth
self-limits depends on the *mean* capacity per recruit, not on "some members
can't recruit." Since `mod_charisma` is roughly symmetric around 0 but
capacity floors at 0 (can't recruit negative people), the mean offspring count
per node is pulled **above** zero, not landing at it — so this mechanic alone,
in isolation, doesn't guarantee the tree dies out. In practice it doesn't need
to: the **weekly taverna pool already hard-throttles supply**
(`TAVERNA_SIZE=3` every `REFRESH_DAYS=7`, see `recruit.py`) — recruit capacity
isn't the thing stopping infinite growth, it's the thing deciding **who within
the guild is allowed to spend the guild's limited weekly recruits**. That's
exactly what the user wanted (low-Charisma members become permanent "floor,"
the guild leader becomes structurally load-bearing for continued growth), so
the mechanic is validated for that purpose, not as a population-growth-rate
control (the taverna pool already does that job).

**This does NOT solve [[gartok-leadership]]'s original open problem** (900
solo groups) — that's about group *count*, this is about total roster *size*.
Orthogonal levers, both legitimate, not a replacement for each other.

## As built (`gartok/recruit.py`, `gartok/taverna_screen.py`)

- `BASE_RECRUIT_CAPACITY = 1`. `recruit_capacity(guild, unit)` = base +
  `unit.mod_charisma`, floored at 0; `+ unit.racial_level` if `unit is
  guild.leader` (mirrors `Group.capacity`'s `BASE_CAPACITY + leader's CHA mod`
  shape one level up). `recruit_slots_used(guild, unit)` counts live
  `guild.roster` members whose `recruited_by == unit.uid`; `slots_free` is the
  difference.
- **Leader death handling ("libera", the user's explicit call over the
  alternative "gasto pra sempre"):** no special-case code needed — capacity
  and used-count are computed live over `guild.roster` each time, so a dead
  recruiter's bookkeeping simply stops existing with them. A descendant's own
  `recruited_by` pointing at a dead uid is inert, never a standing penalty —
  verified by `test_a_dead_recruiters_line_keeps_working` (the chain still
  extends through a dead recruiter's own recruits).
- Gated at the screen layer, same pattern as `barred` (not inside `convince`,
  which only knows the two units, not guild state): `TavernaScreen._eligible`
  drops sponsors with `slots_free <= 0`; `_pitch` blocks with a notice;
  `_draw_party_card` shows a `FULL` badge and a live "`N` slot(s) free" line.
- Tests: 5 new in `tests/test_recruitment.py` (base+CHA capacity, floors at 0,
  leader racial_level bonus, slots deplete/block, death doesn't cripple a
  descendant's own chain). 358 pass (was 353), sim byte-identical (never
  touches combat).
- RULES.md's Leadership section corrected: the cohesion/`Group.overextension`
  paragraph had claimed to be "the answer to what stops the guild from being
  100,000 characters" — that was the [[gartok-leadership]] open problem's own
  unresolved claim, now replaced with this mechanic as the real answer; the
  old paragraph is reworded to say what cohesion actually caps (one group's
  comfortable size, not the roster).

## Growth-curve sim (2026-09-11, throwaway script, not committed)

User asked "em quantas semanas a guilda atinge o máximo, se é que atinge" —
ran a standalone sim (draft 3 units the real way, then play the taverna every
week like an eager player: try every eligible sponsor on every pool candidate,
strongest pitch first, until success or nobody left with a free slot). 300
independent drafted guilds, up to 200 simulated weeks.

- **A) Pure recruiting (guild does nothing else, so the leader's `racial_level`
  stays 0 the whole run):** 187/300 (62%) hit an absolute, permanent 0-capacity
  ceiling — median **19 weeks** (~4.5 months in-game), min 1 (an unlucky draft
  can be maxed out in its very first tavern visit), max 194. Final roster size
  at the ceiling: median 11, max 22. The other 113/300 never fully zero out —
  they keep finding rare compatible (shared-language, low-alignment-distance)
  pitches for a long tail, but growth in practice stalls early too (median
  "last week anyone was actually recruited" across all 300 = week 60, pulled
  up by that slow tail, not typical).
- **B) Leader also adventures (+2 combat/work XP a week, a made-up pace, not
  calibrated to real play speed):** nobody hit a hard 0-capacity wall in 200
  weeks. Median final size **19** (max 24), growth continuing out past week
  150 in the median case. Makes sense: `racial_level` itself caps around week
  ~21 (work, 6 levels) / ~53 (combat, 7 levels) at this XP rate, so even an
  adventuring leader's bonus tops out eventually — the long tail past that is
  the same rare-lucky-pitch mechanism as scenario A, just from a bigger base.

**Answer to "does it reach a max": yes, reliably, for a guild that only
recruits — typically within a season or two of game-time, capping at a modest
roster (~11 people). A guild that keeps its leader active elsewhere pushes the
ceiling roughly 2x higher and much later, but still tops out once the leader's
level caps.** `BASE_RECRUIT_CAPACITY = 1` reads as reasonable off this data —
low enough to bite fast, not so low the guild never leaves single digits.

## Open / not done

- No UI surfaces `recruit_capacity`/`slots_free` outside the taverna screen
  (e.g. `guild_screen`'s roster list doesn't show it) — not asked for yet.
- `BASE_RECRUIT_CAPACITY = 1` is a first guess, untuned by play — same "retune
  freely" status as `BASE_CAPACITY`, `progression` thresholds, etc.
- Not committed as of this writing — pending [[commit-workflow]] (`/pre-commit`
  review first).
