---
name: gartok-name-generator
description: "gartok/names.py: procedural personal names for every generated Unit (recruits + random enemies + arena challengers); private RNG so it never perturbs seeded tests"
metadata: 
  node_type: memory
  type: project
  originSessionId: 5f693763-6865-4ba0-813c-f7b47f36ec5b
  modified: 2026-09-09T13:53:03.807Z
---

`gartok/names.py` — `random_name()` strings 2-4 of `SYLLABLES` (60 entries) and
capitalises. Promoted out of `arena.py` (was `_SYLLABLES` / `_random_name`) on
2026-09-09 when recruits and random enemies started needing names too.

- `Unit.__init__` calls `names.random_name()` whenever `name is None`, so every
  `Unit("player")` recruit (taverna pool) and `Unit("enemy")` gets a real name
  instead of the old `"Race Occupation"` label. `arena.build_challenger` no longer
  sets a name explicitly — the bare `Unit("enemy")` already has one.
- `_auto_name` still means "procedurally generated nobody" (scenario deploy zones
  key off it via `CustomScenario._is_npc`); it no longer implies the name tracks
  race/occupation. `_after_edit` stopped rewriting the name; `set_name("")` now
  hands out a fresh `random_name()` instead of the `Race Occupation` label.
- Module holds a private `_rng = random.Random()` and `random_name(rng=_rng)`, so
  minting names does NOT consume the global `random` stream that seeded tests
  rely on. Pass an explicit `rng` if deterministic names are ever needed.

Part of [[gartok-tactical-project]]. Related: [[gartok-arena-champion-title]]
(challengers), [[gartok-character-creator]] (authored NPCs keep their own names).
