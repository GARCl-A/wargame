---
name: gartok-z-axis
description: "The board's third dimension: per-cell elevation, pits, fall damage, and the Climb/Push/Jump/Drop-in actions"
metadata: 
  node_type: memory
  type: project
  originSessionId: a64e2688-1ff7-42da-8793-4f9e087dc17b
  modified: 2026-09-09T13:48:26.335Z
---

Built 2026-09-09, committed `64c6602`. Motivated by the arena bossfight
(`maps/the-pit.json`, now the champion-bout map — see
[[gartok-arena-champion-title]]); the hole ended up as scenery, the bout is still
"down the whole team". The board gained a **Z axis**: `board.elevation = {(x,y): z}` (int,
only non-zero cells stored), `board.elevation_at(pos)`. Negative = a **pit**;
positive is reserved for future rises. `board.surface_dc(cell)` = 10 if the cell
is in `board.ropes` else 15 (`CLIMB_DC_ROPE`/`CLIMB_DC_STONE` in `board.py`).

**Pathfinding never changes level.** `_dijkstra`/`reachable`/`path_to`/
`path_step_toward` took a `vertical=False` param; a non-vertical walk skips any
neighbour whose `elevation_at` differs from the *start* cell. `vertical=True` is
passed for `unit.can_move_vertically` (= `ability.flies or ability.climb_speed`)
— a flier routes in and out of pits as normal movement.

**Fall damage** — `Battle.apply_fall(unit, drop, log)`: `max(0, drop-1)` d6 (first
level free). Fliers take none.

**Four new actions in `actions.py`** (all cost 1; registered in `PANEL_ACTIONS`;
CLIMB/DROP are in `battle_screen`'s `contextual` tuple — only shown at a pit edge.
PUSH and JUMP are general moves, always on the panel, greyed when unusable):
- **`Push`** (`PUSH`, aimed at an enemy ≤1 away, |Δz|≤1): `d20+FOR` vs
  `PUSH_DC_BASE(10) + target.mod_constitution`. Success shoves the target 1 cell
  straight back; a wall/body behind stops it; a lower cell behind → they fall.
- **`Climb`** (`CLIMB`, aimed at an adjacent cell of different z): `d20+FOR` vs
  `board.surface_dc`. `combatant.auto_climb(dc)` (`dc <= ability.auto_climb_dc`)
  skips the roll — the Lizardfolk's Climber (`auto_climb_dc=25`). Slip = wasted AP.
- **`DropIn`** (`DROP`, "Drop in", adjacent lower cell): no check, take the fall.
- **`Jump`** (`JUMP`, aimed cell): `d20+FOR`, clears `roll//JUMP_DIVISOR(5)` cells
  (≤ speed) in a Bresenham line toward the aim, over any pit; wall/body ends it
  short; lands lower → falls. Roll happens in `execute` (hidden).

**Melee & Z**: `Attack.can` blocks melee (`attack_range<=1`) when `|Δz| > 1`
(deeper than a one-level lip). Ranged/Throw/Demoralize unaffected.

**Ability changes** (`abilities.py`): `flight` (Sprite) lost `speed=2` +
`ac_natural=1`, now just `flies=True` (3D move + no fall damage). `climber`
(Lizardfolk) lost `speed=1`, now `auto_climb_dc=25`. New `Ability` fields:
`flies`, `climb_speed` (unused seam), `auto_climb_dc`.

**UI**: `battle_screen._click` routes `aim_action.target == "cell"` to execute
against the clicked tile. Pits drawn as sunken dark cells with the depth number;
ropes as a tan vertical line. Editor: see [[gartok-map-editor]].

**AI**: `ai._step_over_elevation(battle, unit, target)` — when the unit can't
walk any nearer (`path_step_toward` returns its own cell), it Climbs/Drops onto
the adjacent cell scoring best by `(grid_distance to target, |Δz to target|)`,
acting only if that beats standing still. A slipped climb still counts (spent the
attempt). Called from `take_turn` right before the cornered-DEFEND fallback.

**Also fixed here (was a pre-existing bug, not pit-specific):**
`board.path_step_toward` used to explore only the `budget` disc, so a unit at a
dead end against a wall would just DEFEND forever instead of taking the long way
around. It now plans the route over the **whole board** (full Dijkstra, ~192
cells, negligible) and only caps the *walk* at `budget`. `sim_test.py` went from
9/200 stalling seeds (on `main`!) to **0**; pit trenches, pools and the-pit-style
maps all resolve. This changes the RNG stream, so the old "byte-identical sim"
guarantee in [[gartok-tactical-project]] no longer holds.

**Known limit**: footprint>1 uniform-elevation isn't enforced in `fits`
(bossfight is all Medium footprint 1).
