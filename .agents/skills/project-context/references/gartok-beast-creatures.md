---
name: gartok-beast-creatures
description: "Wolf/beast kind, EncounterTable, per-species loot drops, and the long-term procedural-creature-generator goal (2026-09-12)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8cab88d5-9ffe-4d20-946c-2966fd0befa8
  modified: 2026-09-12T20:10:00.404Z
---

First non-humanoid `Unit.race["kind"]` shipped 2026-09-12: **Wolf**
(`data.BEASTS`/`data.BEAST_POOL`), enemy-only, never rolled as a player race.
A beast skips the occupation system entirely (`Unit._apply_beast`: no weapon,
no job item -- fights unarmed, its bite is the racial ability's
`melee_damage` bonus) but still rides the existing level/HD/talent scaffold
(`encounters.build_enemy(mean_level, race_pool=...)`), so scaling a beast to
an encounter's level needed zero new code.

**Where a new hand-authored creature costs what**: one row in `data.BEASTS`
(stats, ability id, `drop_item`/`drop_chance`) is the whole cost if it reuses
an existing ability. A genuinely new mechanical effect still needs a block in
`abilities.py` (same cost a new *humanoid* race's ability would have -- not
beast-specific). Loot is fully data-driven per species now (`drop_item`/
`drop_chance` live on the race dict, read generically by `loot.field_loot`) --
this was NOT true at first ship (a global `BEAST_DROP_ITEM`/`_CHANCE` pair in
loot.py would have made every beast drop the same "1sqm Hide"); fixed same
session before a second creature could hit the bug.

`encounters.EncounterTable`/`EncounterEntry` (see `encounters.WILDS_TABLE`)
picks a *pool* by weight, independent of headcount/level weights -- Wilds
rolls 70% wolf pack / 30% old-style humanoid bandit gang. Adding a new
locality's own mix = a new `EncounterEntry` tuple, not new logic.

**Explicit long-term direction from the user (2026-09-12)**: hand-author
creatures/content now, for the initial campaign's sense of craft -- but the
real goal is flexible procedural generators/builders that grow the world over
time for high replayability and make adding new creatures trivial. Current
system supports exactly ONE fixed ability per creature (curated, like player
races) -- there is no trait-combination generator (e.g. "roll 2-3 random
traits from a pool" for a monster). Building that needs a different authoring
shape (a list of trait ids per creature, not one ability id) and was
deliberately deferred -- a decision to make carefully before building, not
mid-implementation. Keep this in mind before hardcoding assumptions
elsewhere that a creature has exactly one ability slot.
