---
name: gartok-doc-generator
description: "GARTOK: REFERENCE.md is generated from the registries (gartok/reference.py); RULES.md holds only prose; tests split into tests/ by domain; world.Bout, _pick_party, ruins node dropped"
metadata: 
  node_type: memory
  type: project
  modified: 2026-09-10T15:34:34.671Z
  originSessionId: 4ca1ac23-7c1e-4f7b-882f-63ea5778141a
---

Structural cleanup + a teammate's arena feature, committed together as `b6cefaa`
(2026-09-10, off `d53454e`). Part of [[gartok-tactical-project]]. Driven by the
project x-ray. The two were entangled at the file level (both touched
`world.py`/`app.py`/`factions.py`/`campaign.py`) with a cross-dep
(`REFERENCE.md` <-> `factions.py`), so one commit, not the two that were planned.

**The teammate's "The Games"** (in `b6cefaa`): the arena's 2nd stage, unlocked by
`arena_dethrone`. `arena.brawl_bout()` (3v3, `stage2=True`) + `ctf_bout()`
(`ctf=True`, a `scenario.FlagScenario` -- the FIRST real consumer of the
`Scenario.win_check` seam: win by reaching the other side's flag, no wipe).
Opponents scaled level 1..6 (`encounters.ARENA_LEVEL_WEIGHTS`, `arena.stage2_pack`).
`Battle` gains `flags`/`is_ctf`/`_assign_flag_runners`/`check_objective`;
`combatant.ctf_runner`; `ai._ctf_goal` routes the fastest half of the enemies at
the player's flag; `battle_screen` plants the flag + hides the enemy's until
seen. Three deeds behind `arena_dethrone` (`arena_bloodsport`,
`arena_flag_runner`, `arena_untouchable` = CTF win with `outcome.player_kos == 0`)
-- worth 3 rep, which now brings the Iron cage (rep 5) into reach. See
[[gartok-factions-reputation]].

## Docs: generated catalog + hand-written prose

- **`gartok/reference.py`** — `build()` walks the registries (`data.RACES`/
  `OCCUPATIONS`/`WEAPONS`/`ARMOR`, `abilities.ABILITIES`, `talents.TREE`,
  `factions`, `world.ARENA_TIERS`, `progression`, `economy.PRICES`) and emits
  **`REFERENCE.md`** at repo root — the game's data dictionary. English, straight
  from the `name`/`effect`/`blurb` strings already in the code. `python -m
  gartok.reference` rewrites it; `--check` exits 1 if stale.
- **Drift guard:** `tests/test_reference.py::test_reference_doc_is_regenerated_from_the_registries`
  asserts `reference.is_current()`. Add an ability/weapon/talent → regenerate and
  commit `REFERENCE.md` or CI fails. Plus two structural tests (every race
  ability / occupation weapon / talent `requires` resolves).
- **`GARTOK-regras.md` → `RULES.md`** (English). Prose only: the d20 combat
  rules, falling/death, Z-axis, vision, world systems, §9 "what the generator
  lost", the design premises. The catalog tables were replaced with pointers to
  `REFERENCE.md`. The 🟢 recovered / 🟡 designed framing kept.
- `README.md` rewritten in English, brought up to date (tavern, lumber yard,
  wilds, factions, champion title, editors, progression, Z-axis, `tests/`).
- 6 code docstrings that said `GARTOK-regras.md` now say `RULES.md`. Nothing
  pt-BR left in the repo — see [[player-text-english]].

## Tests split by domain

`test_gartok.py` (one ~2950-line file, hand-rolled runner) → **`tests/`
package**, one file per domain (`test_combat.py`, `test_world.py`,
`test_campaign.py`, `test_progression.py`, `test_zaxis.py`, …, 18 files + 208
tests). Shared fixtures in **`tests/helpers.py`** (`_unit`, `_combatant`,
`_recruit`, `_melee_battle`, `_FixedRNG`, `_person`; also re-exports the game
modules via `from tests.helpers import *`). Empty root `conftest.py` +
`tests/__init__.py`. Runner is now **`python -m pytest tests/`** (the
`if __name__ == "__main__"` runner is gone).

**Audit done 2026-09-10:** misfiled tests moved (new `tests/test_work.py` for the
lumber yard; arena-torch-scatter → `test_world.py`), pt-BR names renamed
(`test_besteiro`→`test_crossbowman`, `test_madeireira`→`test_lumber_yard`), the
two `test_map_library_round_trips_*` merged, dead `hp_before` line removed.
**+7 coverage tests**: initiative-keys-off-WIS (the balance change had none), 3
AI tests (`_recover_weapon`, reload-before-closing, chaotic/lawful `_should_flee`
branching), title-defense *win* path, and the keep-hunting accrual across an
ambush-split hunt (`test_hunt`).

**Fragility fix (`helpers.fixed_d20`):** the `random.seed(N)  # first d20 = 13`
pattern (fragile to any RNG-consuming change upstream) is replaced by a
`with fixed_d20(value):` context manager that patches `d20` in `actions`,
`battle` and `data` at once, so a test asserts on the check *outcome*. Applied to
every death-save / stabilize / first-aid / climb / push / jump test; the old
`_d20` class in `test_zaxis` is gone. `recruit.convince` tests already used
`_FixedRNG` (roll injection via the `rng=` param) — left as is. Remaining
`random.seed` calls are the legit "reproducible generation" or "loop until it
converges" patterns.

## Small refactors (same session)

- **`world.Bout`** — a frozen dataclass replaced the arena-offer dict.
  `ARENA_TIERS` is now `[Bout(...)]`; `arena.champion_bout()` / `defense_bout()`
  return `Bout`. Fields: `name, entry, purse, enemies, rep=None, champion=False,
  defense=False, map_slug=None` (was `"map"`). Consumers use attribute access
  (`offer.entry`, `.champion`, `.map_slug`) instead of `["x"]` / `.get("x")` —
  `app._start_battle`, `campaign.absorb_battle`, `factions` deed checks,
  `squad_screen`, `guild_screen`. Motivated by the arena getting more bout types
  (user: "a arena ainda vai ser bastante expandida"). See
  [[gartok-factions-reputation]].
- **`app._pick_party(node, title, label, then)`** — collapsed the 4 identical
  `SquadScreen`-as-party-picker wrappers (`_open_market`/`_open_work`/
  `_open_hunt`/`_open_recruit`). The arena squad picker (`_open_squad`) stays
  separate — it has stake tiers and a squad-capped pick.
- **The `ruins` node was removed** from `world.py` (node + 2 edges). It was just
  "lethal ArenaScenario, level-0 enemies", no identity, and the arena grew its
  own. User: "não estou fazendo nada lá, pode tirar" — reimplement later if it
  earns a scenario + faction.

## Talent-tree dead-pick question (from the x-ray) — a non-issue today

`Unit.choose_talent` already allows cross-root picks (only checks track /
not-taken / picks>0 / `requires`). Combat: 7 reachable levels vs 9 nodes; work:
6 vs 6. No dead picks at current numbers — the risk is only future
`progression.py` tuning outpacing node count. Worth a `max reachable level per
track <= node count` invariant test if tier 3 is ever added.
