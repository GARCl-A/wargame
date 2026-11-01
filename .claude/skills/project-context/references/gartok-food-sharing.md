---
name: gartok-food-sharing
description: GARTOK food sharing — per-unit share_food toggle pools rations within a physical Group (scoped there since the 2026-09-11 refactor) so only strong members need to haul food
metadata: 
  node_type: memory
  type: project
  originSessionId: ab5f00c0-6ada-44c6-9a13-6dab9ebc6d68
  modified: 2026-09-13T16:58:11.022Z
---

Added 2026-09-08. Part of [[gartok-tactical-project]]. Food used to be strictly
per-character (each ate only from their own pack), which forced every weak
recruit to carry their own rations even when a strong member could haul for the
group.

**Now:** `Unit.share_food` (bool, default True, persisted, toggle on the guild
screen member panel). At every meal — daily upkeep and `do_maintenance` — each
unit eats from its own pack first (a full first pass over the roster), then any
still-hungry unit draws from `Guild._shared_larder(u)`: the packs of roster-mates
with `share_food` on. Two passes so nobody loses their own meal to a hungry mate
earlier in roster order. `Unit._take_ration(larder)` does the own-pack-then-
larder search; `consume_daily_food` / `eat_now` take an optional `larder`.

**Scoped to `Group` as of the Guild→Groups→Units refactor (2026-09-11,
[[gartok-groups-refactor]]).** `_shared_larder(eater)` now looks up
`guild.group_of(eater)` and pools only that group's members — a mate in a
different physical `Group` is out of reach, matching the real-world logic (you
can't hand someone food you aren't standing next to). With the single starting
group this is behaviourally identical to the old whole-roster pooling (Phase 1
of the refactor was required to be byte-identical); it only diverges once a
second group exists. `RULES.md` §Hunger updated to say "group-mate", not
"guild-mate".

**Why:** a squad is separate individuals with different roles; the strong carrier
being the group's food mule is the natural early-game division of labour, and the
toggle lets the player opt a hoarder out. This was the first system to hit the
"what is a group" question that the full Group refactor later answered.
