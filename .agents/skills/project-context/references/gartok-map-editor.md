---
name: gartok-map-editor
description: "The scenario creator (map_editor_screen), the map_lib library and scenario.CustomScenario"
metadata: 
  node_type: memory
  type: project
  originSessionId: 45c7830a-6903-4ec9-98b3-830c95028a3d
  modified: 2026-09-09T13:48:19.554Z
---

The Editor hub's second door, built 2026-09-08 (`EditorMenuScreen` on_scenario →
`app._open_map_editor`). Mirrors the character creator (see
[[gartok-character-creator]]) — a sandbox, git-tracked authored content.

**`map_editor_screen.MapEditorScreen`** (native): paint the 16×12 board
directly. **No RNG anywhere** (user was explicit) — a fresh board is empty, every
cell is hand-placed, whatever is on it is the map. Tools = wall / torch /
player-start / enemy-start / npc-start / erase; left-drag paints, right-drag
erases (`handle_event` owns the drag, `_apply` keeps a cell in one layer at
most). CLEAR wipes. SETTINGS = name + `ambient_light` + `outdoor` toggles
(ambient click is a no-op while outdoor, which forces light on; `_to_dict` drops
the inert flag). A live `_sealed()` BFS warns when walls cut the two sides apart.
Left = the grid, right column = tools/settings/library list.

**NPC START is special — not a drag.** Click a cell → a modal (`_draw_picker`,
`self.picking` = the cell) lists `npc_lib.list_npcs()`; pick one and that slug is
pinned to the cell (`self.npc_at` = `{(x,y): slug}`, saved as `deploy_npc`
`[x, y, slug]` triples). The cell shows the NPC's name initial; right-click
clears it; empty library → a WARN notice. This is how you place Adelio.

**Light preview** on the grid: a dark map dims every floor cell no torch reaches
(`_sync_dark` — `TORCH_RADIUS` + `Board.los_clear`, cached on a
`(walls, torches)` signature, recomputed only on a paint). Painted walls / zones
/ torches draw crisp *on top* of the veil — the dimming is only on the empty
floor, so you never lose sight of what you placed.

**Pit / rope tools (added 2026-09-09, see [[gartok-z-axis]]).** `PIT` is a
drag tool that digs holes at the panel's adjustable `pit_depth` (`self.elev =
{(x,y): -depth}`, exclusive with wall/torch/zone layers). `ROPE` is a
click-to-toggle (not a drag, like NPC): only lands on a cell that already has a
pit, drops the climb DC there 15→10. CLEAR wipes both. `_sealed()` still counts
walls only (pits are passable via Climb).

**`map_lib.py`** — one JSON per map under `maps/` at repo root, git-tracked
(like `npcs/` / `npc_lib`). Flat dict: `name`, `cols`/`rows`, `walls`/`torches`/
`deploy_player`/`deploy_enemy` (sorted `[x,y]`), `deploy_npc` (`[x, y, slug]`),
`elevation` (`[x, y, z]`, z<0 = pit), `ropes` (`[x,y]`),
`ambient_light`, `outdoor`, `map_slug`; cells regex-compacted one per line on
write (a 3-int `[x, y, z]` regex was added alongside the `[x,y]` / `[x,y,"slug"]` ones). `_CELL_KEYS` drives `new_map` + the save loop. `new_map` / `save_map` /
`load_map` / `delete_map` / `list_maps`, plus **`npc_units(data)`** → the
`deploy_npc` characters loaded from the library, each tagged `unit.map_cell =
(x,y)`; the caller hands them to `Battle` as (part of) the enemy side. Ships with
`maps/collapsed-hall.json`.

**`scenario.CustomScenario(data)`** — turns a saved map dict into a playable
battle. `Board(walls=...)` (new param: skips generation, takes cells as-is),
fixed torches, and the painted deploy zones. Deployment: `Scenario._deploy` was
refactored to `_deploy_cells(u)` (ordered candidate list, first fit wins) +
`_place`; base shuffles the edge columns, `CustomScenario` overrides
`_deploy_cells`: a unit tagged `map_cell` (from `npc_units`) → that exact cell
first; else `_is_npc(u)` (`arena_role`, or `_auto_name` False) → npc zone then
enemy; a plain `Unit("enemy")` → enemy then npc; player → player zone; edge
columns as the tail fallback. Lit map → no torch scatter; dark with none placed
stays dark.

**First consumer wired (Sep 2026):** the arena title bout. `arena.champion_bout()`
carries `map="the-pit"`; `app._start_battle` builds `CustomScenario(map_lib.load_map(
offer["map"]))` when an offer has a `map` key, else `node.scenario()` as before.
`maps/the-pit.json` (Z-axis pit) is now live in the game. A **plain world node**
pointing at a custom map still isn't a thing — that + `use NPC x` come later.
