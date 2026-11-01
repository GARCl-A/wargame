---
name: gartok-map-size-water
description: "GARTOK: Board carries cols/rows (was fixed 16x12); water terrain (shallow=difficult, deep=Swim+breath); Amphibious reworked; battle view = full-window + zoom/scroll camera"
metadata:
  type: project
---

Branch `feat/map-size-and-water` (off `b6cefaa`), 2026-09-10, **2 commits**:
`319daeb` (engine + editor + docs) and `40f8180` (battle-view camera). Not merged
/ not pushed. Part of [[gartok-tactical-project]]; layers on [[gartok-z-axis]] and
[[gartok-map-editor]].

## Configurable board size

`board.COLS, ROWS = 16, 12` are now just **defaults**. `Board(cols=, rows=)`
stores `self.cols/self.rows`; the neighbour tables are built + cached per size
(`board._neighbors_for(cols, rows)` → `(neigh, neigh_d)`; `Board._neigh/_neigh_d`).
`Board.neighbors(pos)` / `Board.fits(pos, fp, blocked)` are instance methods now
(sized to the map); the free `neighbors()`/`fits()` keep a `cols=COLS` default for
callers with no board. Ripple: `vision.visible_cells`, `lighting`, `scenario`
(`_spawn_cells`/`_place(…, board)`/`_scatter_torches`/`own_half(team, cols)`/
`FlagScenario`), `actions.Flee._at_edge`, `ai`, all read `battle.board.cols/rows`.
`map_lib` persists `cols`/`rows` (already did); `CustomScenario` threads them.
Procedural fights (`ArenaScenario`/`ErmosScenario`) stay 16×12.

## Water terrain (on top of the Z axis)

`board.water` (set of cells, map key `"water"` = `[x,y]` list). Derived in
`Board.refresh_terrain()` (called from `__init__`; also after in-place edits —
the editor preview, tests):
- **shallow water** = water at `elevation >= 0` → `board.difficult` (general
  "+1 to enter" set; folded into `_dijkstra` step cost and `Board.path_cost`,
  which `Battle.move_unit` now uses instead of `route_cost`).
- **deep water** = water over a pit (`elevation < 0`) → `board.deep_water`.
  `Battle._impassable_water(unit)` adds it to the pathfinder `blocked` set for
  anyone not flying. `board.is_deep_water(pos)`.

**Swim** (`actions.Swim`, `SWIM_DIVISOR=5`) — cloned from Jump: `d20+STR` crosses
`result//5` cells toward the aim, capped at `speed//2`, water cells only, stops at
wall/body/edge. In `PANEL_ACTIONS` + `battle_screen` `contextual` tuple (shown
only at a water edge). AI: `ai._step_over_terrain` (was `_step_over_elevation`)
tries CLIMB/DROP/**SWIM**.

**Breath / drowning** — `Battle._apply_submersion(unit)` at the top of a
submerged unit's turn (called after `start_turn` in `_roll_initiative` +
`_advance_turn`): holds `data.BREATH_BASE(4) + CON mod` rounds, then escalating
`n d6` each turn (`combatant.rounds_submerged`; reset on surfacing).
`Battle.apply_fall` skips damage for a landing in deep water (water breaks it).

**Amphibious (Grippli)** reworked: was `speed=1`, now
`Ability.water_breathing=True` → `combatant.water_breathing` → never drowns.
REFERENCE.md regenerated.

## Battle view: full-window + camera (`theme.py` + `battle_screen.py` + `lighting.py`)

`BattleScreen` was the last screen still rendering to a fixed `WIN_W×WIN_H`
`_canvas` blitted centred (the huge letterbox the user hated). Now: draws
straight to the window, `theme.battle_layout(size)` docks panel right / log
bottom / board viewport fills the rest, and **`theme.BoardView`** (a pan/zoom
camera) owns all board↔pixel math: `fit(rect)` picks a tile size in
`[MIN_TILE, MAX_TILE]=[18,56]` to fit the whole board (small maps get big tiles,
filling the reclaimed margin), wheel zooms around the cursor, right/middle-drag
pans, and `update` re-centres on the active unit when it goes off-screen for a
board bigger than the view. `lighting.LightRenderer.draw(…, view)` builds a
viewport-sized darkness surface. `theme.GRID_*`/`TILE`/`WIN_*` consts kept (app
still opens at `WIN_W×WIN_H`, tests import them).

## Editor (`map_editor_screen.py`)

`self.cols/self.rows` per map; **WIDTH/HEIGHT steppers** in SETTINGS (8..48,
`_clamp_to_grid` drops out-of-bounds cells on shrink). New **WATER** drag tool
(blue): floods a flat cell = puddle, a pit cell = deep water (coexists with the
pit like a rope). `_preview_board()` helper feeds `_sealed`/`_sync_dark`.

## Tests

`tests/test_water.py` (12), plus size-aware + difficult-terrain cases in
`test_board.py` and a size/water round-trip in `test_editor.py`. `sim_test.py`
unchanged (avg 5.165, 0 stalls — water isn't in the procedural sim).

## REFERENCE.md annotations

4 hand annotations ("(change to X when this becomes a mechanic)") appeared in
`REFERENCE.md` mid-session (someone editing the shared checkout). `REFERENCE.md`
is generated and drift-tested — no preserve mechanism. Resolution: the 4 notes
moved to a new **"Placeholder effects"** subsection in `RULES.md` §7 (Strong
Stomach → eat spoiled food, Primal Blood → 1 spell, Keen Hearing → perception,
Ancestral Blood → learn spells); `REFERENCE.md` stays generated-clean.
