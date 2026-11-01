---
name: gartok-wilds-hunting
description: "GARTOK The Wilds: Hunt activity (meat + ambush risk), encounters.py scaled-enemy core, and the Scenario.win_check seam"
metadata: 
  node_type: memory
  type: project
  originSessionId: d1908594-6fd0-403c-b47d-fe41f3d350f9
  modified: 2026-09-12T20:11:41.866Z
---

Built 2026-09-09 (session after [[gartok-name-generator]]). Closes two of the
three highest-impact gaps from that session's review: enemy scaling (point 3) and
a generic win-condition seam + a new activity shape (point 1). Part of
[[gartok-tactical-project]].

## `gartok/encounters.py` (new) — the scaled-enemy core

- `build_enemy(mean_level, rng=random)` -> a `Unit("enemy")` whose combat/work
  track levels are split **at random** to average to `mean_level` (`_split_tracks`:
  pick `c` in the cap-allowed range, `w = 2*mean - c`, so `(c+w)//2 == mean`
  exactly), then random talent picks respecting `Talent.requires`. The user's
  frame: "nível do inimigo" always means the *mean*; how it splits across
  activities doesn't matter as long as progression rules hold.
- `roll_pack(count_weights, level_weights, rng)` -> list[Unit]: roll a headcount,
  then each member's level independently.
- `weighted_choice(weights_dict, rng)` — thin `rng.choices` wrapper. **Plain
  hand-weighted tables, no gaussian** (user asked how to skew one — the answer was
  don't, a weight dict is more controllable).
- `WILDS_COUNT_WEIGHTS = {1:10,2:20,3:30,4:20,5:7,6:3}` (mode 3, left-lean),
  `WILDS_LEVEL_WEIGHTS = {0:40,1:25,2:18,3:12,4:5}` (0 common, 4 rare). All tuning
  in one place, retune freely like `progression` thresholds.
- **`arena.build_challenger(mean)` is now a 1-line delegate** to `build_enemy`
  (dropped its own duplicated talent loop; `arena.py` no longer imports
  `talents`/`Unit`).

Enemy scaling by locality is the pattern; The Wilds is levels 0..4. **Arena
tiers now scale through `encounters` too** (Sep 2026, via `gartok/matchup.py` —
`world.Bout.level` 0/1/2/3 for Rookie→Silver; see [[gartok-factions-reputation]]).

## `Scenario.win_check` seam (point 1)

`scenario.Scenario.win_check(self, battle) -> "player" | "enemy" | None`, default
`None`. `battle._check_winner` consults it first, every turn, before the standard
all-down rule. A forced `"enemy"` in a `lethal` fight runs `_wipe_side` +
`_resolve_dangling_dying` (finishes the already-downed) but **leaves upright units
alive** — same survival semantics as a flee. Inert today (no scenario overrides
it); it exists for future non-elimination objectives ("survive N rounds", "reach
the cell", "protect X"). The two docstrings that promised this seam are now true.

## The Wilds is an activity node

- `world.py`: the `wilds` node is `kind="wilds"` (was `"battle"`), keeps
  `ErmosScenario` (now the ambush battlefield). New `Node.is_wilds` property.
- `map_screen.py`: `"wilds"` added to `KIND_COLOR/BADGE/NAME` (indexed
  unconditionally — a missing key KeyErrors at draw), a bow `_glyph`, a danger
  aura, a legend row. `_draw_side` has an `elif here.is_wilds:` branch that emits
  an **action menu** (`_wilds_actions()` -> list of `(key, label, note)`; just
  `("hunt", "GO HUNTING", ...)` now — forage/etc. slot in there). `MapScreen`
  gained an `on_hunt` param (breaks the positional ctor — the screen smoke test
  and `app` were updated).

## `gartok/hunt.py` + `gartok/hunt_screen.py` (new)

- `HuntState(party, node, hours_left, hours_hunted=0, fights=0)` — the live hunt,
  carried on **`app._hunt`** (NOT cleared by `_battle_end`) so a screen rebuilt
  after an ambush picks the hunt back up. `.meat` = `hours_hunted // HUNT_MEAT_HOURS`.
- `hunt_stretch(state, rng)` — spends hours one at a time, `rng.random() <
  AMBUSH_CHANCE_PER_HOUR` per hour, stops on the first hit. Returns
  `(elapsed, ambushed)`.
- `grant_meat(state)` — once, at the end: meat round-robin into surviving hunters'
  `_base_inventory`, `work_hours += hours_hunted` + `collect_levels()` each
  (hunting banks the **work** track, like `Guild.work_shift`). Returns summary lines.
- Constants (top of `hunt.py`, tunable): `AMBUSH_CHANCE_PER_HOUR = 0.15`,
  `HUNT_MEAT_HOURS = 2` (1 kg per 2 h), `HUNT_SHIFT_HOURS = (4,8,12,16)`.
- `HuntScreen(fonts, guild, state, phase, on_ambush, on_done)` — phases
  `"setup"` (shift picker + CONFIRM) / `"interlude"` (KEEP HUNTING / HEAD BACK,
  after a won ambush with daylight left) / `"done"` (wrap-up, calls `grant_meat`
  on entry). Calls `guild.pass_time(elapsed)` after each stretch (runs daily meals
  like a shift). Modelled on `work_screen.py`.

## `app.py` flow

`_open_hunt` -> `SquadScreen` party picker -> `_open_hunt_ground` (builds
`self._hunt`, opens `HuntScreen` phase="setup"). `_start_hunt_battle(state, pack)`
-> `Battle(party, pack, scenario=node.scenario(), lethal=node.lethal, arena=False)`.
**`_battle_end`**: if `self._hunt` set — trim party to survivors in roster; won +
survivors + `hours_left > 0` -> `_resume_hunt` (interlude), else `_finish_hunt`
(done); route the terminal LootScreen's `on_done` to whichever. `_end_hunt` clears
`self._hunt` and returns to the map (or `_campaign_over` if the guild emptied).

Ambush fights are **lethal** (wilds node default), so a win yields field loot —
the reward that offsets the risk. A flee keeps the meat gathered so far, everyone
lives (fled != dead, and it funnels to `_finish_hunt`). No `SAVE_VERSION` bump
(meat -> already-persisted `_base_inventory`, hours -> `work_hours`); autosaves on
the map return. A multi-fight hunt is not saved *between* fights.

## Open / deferred (explicit)

- **Combat XP still keys on the victim's *combat*-track level** (`xp_award` in
  `credit_kill`), not its mean level — a work-heavy "mean level 2" enemy pays a
  level-0 hunter only +1. Flagged to the user as a possible `credit_kill` tweak,
  not done.
- Faction #2 / wilds deeds (the `win_check` seam is now ready for a non-battle-win
  deed). A 2nd wilds action (forage) + creature (non-person) encounter tables.
  Meat-on-corpse loot for a hunter who dies mid-hunt (currently forfeits their
  share). (Arena tiers using `encounters` — done Sep 2026, `matchup.py`.)

Tests: 8 new in `test_gartok.py` (encounters mean-level/talents/pack-size,
`win_check` seam, `hunt_stretch`/`grant_meat`), + `HuntScreen` in the native
smoke test. 204 pass. `sim_test.py` byte-identical (hunting isn't exercised).

**Update 2026-09-12**: the "creature (non-person) encounter tables" item above
is done -- see [[gartok-beast-creatures]]. `roll_pack`/`build_enemy` gained a
`race_pool` param and a `roll_encounter`/`EncounterTable` layer on top; the
Wilds now rolls mostly wolves, meat still per-hour, hide now a per-kill drop
(see [[gartok-missions-and-tanner]] for what the hide is *for*).
