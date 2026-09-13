---
name: gartok-balance-sim
description: "balance_sim.py: headless AI tournament ranking races / occupations / combos by win rate + Elo; the Sep 2026 baseline findings"
metadata: 
  node_type: memory
  type: project
  originSessionId: 339277fd-69d6-4a08-8637-5d0ffdad5d54
  modified: 2026-09-13T05:03:09.114Z
---

`balance_sim.py` (repo root, next to `sim_test.py`) — a permanent balance
tournament for [[gartok-tactical-project]]. Homogeneous squad vs homogeneous
squad (3 clones of one `(race, occupation)` archetype, fresh 3d6 rolls per
clone), AI both sides, level 0 / no talents. One random sweep feeds race,
occupation and combo rankings at once (a battle is race-vs-race AND
occ-vs-occ AND combo-vs-combo). Elo (multi-K-pass) + win% + Wilson-bounded combo
list + an additive-model interaction check. Multiprocess (`--workers`), stall cap
`GUARD=600` turns → draw. `--scenario ermos|arena|<map-slug>` (any `map_lib` map,
e.g. `the-pit`), `--daylight`. Writes `sim_results/balance-*.{txt,json,csv}`.

    python balance_sim.py                     # default 20k battles, race/occ, ~1 min
    python balance_sim.py --battles 60000     # tight combos too, ~3 min

Per-combo n ≈ battles*2/558; race/occ n ≈ 20x that. At 60k: combo SE ~0.034
(noisy — read combos as a group), race SE ~0.006, occ SE ~0.008 (solid).

## Speed (2026-09-10)

A battle was **103 ms** — 93% of it inside `board._dijkstra`, a full-board
Dijkstra recomputed from scratch ~32×/battle (the AI asks `reachable` /
`path_to` / `path_step_toward` ~3× per unit-turn, nothing cached). The AI
*decisions* cost ~0; it is all pathfinding overhead. Micro-opt of `board.py`
(precomputed `_NEIGHBORS`/`_NEIGHBORS_D` tables, `Board._flat` fast-path skipping
every height check when there are no pits, footprint-1 fast `fits`, inlined
`_step_cost`/corner check in the Dijkstra loop — algorithm unchanged, 205 tests
green) → **29 ms/battle**. Then a **per-turn Dijkstra field cache** in
`battle.py` (`Battle._pf_field` / `self._pf_cache`, cleared in `_advance_turn`;
`board.reachable`/`path_to`/`path_step_toward` take an optional `field=`): the AI
asks for the same full-board scan ~3× per acting unit; 64% hit rate → **~24
ms/battle, 4.3× total**. Behaviour-preserving — verified byte-identical
(winner/rounds/log-len) over 2400 battles across ermos/arena/the-pit incl.
climber+flier. Key = `(start, footprint, diags%2, vertical, frozenset(blocked))`
where `blocked` (walls+creatures+enemy cells) is rebuilt every call, so a stale
hit is impossible; values are int/tuple dicts only (no unit/board refs → GC-safe).
Still open: `--fast-ai` greedy-step (~5× but diverges from real AI); PyPy (~5-8×
free, sim import tree is pygame-clean) but not installed.

The behaviour-preserving speed options are: the board.py micro-opt (done), the
Dijkstra cache (done), and PyPy. Only `--fast-ai` changes battle outcomes.

## Changes applied off the baseline (committed `0bc72d9`, 2026-09-10, on top of the Wilds commit `8bd35a7`)

Per the user's call after reviewing the ability audit:
- **Automaton — Inorganic Body**: dropped the `damage_reduction=1`; keeps only
  "0 HP → BROKEN instead of dying". (Was the #2 race at 71% largely on that DR.)
- **Kenku — Mimic Sounds**: dropped the once/battle +4 feint; keeps only
  `demoralize_ignores_language`. `_mimic_sounds_feint` helper deleted.
- **Leshy — Autotroph**: dropped the 1 HP/turn combat regen; keeps only the
  hunger-rule exemption (`ability.id == "autotroph"` checks in unit/guild).
  `_autotroph` helper deleted.
- **Initiative now keys off Wisdom** (`combatant.initiative_bonus` → `mod_wisdom`),
  was Dexterity. First combat use for WIS.
- **Crossbow reload** (`combatant.crossbow_loaded`, `actions.Reload` = `RELOAD`,
  AI reloads before closing): the crossbow starts the fight EMPTY, each shot
  empties it, Reload (1 AP) chambers one bolt from the quiver. Unloaded = swung
  as an improvised club. Net: 1 shot/turn, and turn 1 is Reload+Shoot.
- `GARTOK-regras.md` ability table + §Iniciativa + the typed-bonus example
  updated to match. `test_gartok.py` fixed + reload tests added (205 green).
- Smoke (1.2k battles, ermos): **Crossbowman 95%→~51%, rank #1→#16** — the reload
  alone neutralises it. Full re-run pending.

## New weapon: Broadsword (Sep 2026, commit `4dd6b5b`)

1d12, 2 hands, 105 cp — the first 2-handed melee weapon, in `MARKET_STOCK`. The
baseline finding "occupation score ≈ weapon damage die" now has a 1d12 rung above
the 1d8 jobs; nobody starts with it, but it's a buyable power spike. Re-run the
sim on `--scenario` with bought gear if that ever matters. Also new: the Grippli
`tongue` slot (a 2nd weapon, +1 reach, per-turn choice) — a real combat factor
for Grippli that the level-0 sim doesn't see (needs the `tongue` racial talent).

## Hit dice moved off `mean_level` (Sep 2026, commit `2521b47`)

Hit dice is now `1 + racial_level` (the new racial track, see
[[gartok-talent-trees]]), not `1 + mean_level`. `RACIAL_XP_THRESHOLDS` was chosen
so `racial_level == old floor((combat+work)/2)` for `encounters.build_enemy`
(where `_split_tracks` makes `combat+work == 2*mean`), so **enemy HD and every
sim baseline below are unchanged**. `mean_level` still exists purely as the
difficulty scalar the sims pass in.

## Baseline findings (2026-09-09, ermos/daylight, 60k battles) — PRE the changes above

- **Combat balance today is almost entirely STR/CON/Hit-Die.** Mental stats
  (INT/WIS/CHA) and non-combat abilities have zero combat purchase, so the
  "caster-shaped" races sit at the bottom with nothing to trade for their
  physical penalties.
- **Crossbowman is the one broken occupation**: ~95% win rate, +475 Elo over
  every other occupation. The only ranged weapon; ranged does no damage-stat
  bonus but never has to close. Disproportionately rescues fragile races
  (Sprite/Kenku Crossbowman ~89-91%). Every other occupation is within ±5% of
  even — 1d8-axe jobs (Mercenary, Woodcutter, Miner, Builder, Blacksmith) ~0.54,
  1d4-dagger jobs (Innkeeper, Craftsman, Cartographer, Physician, Goldsmith,
  Barber) ~0.45. Weapon damage die ≈ the whole occupation signal.
- **Races span 26%–80%.** Strong: Orc (**79.5%**, way out front — +2 STR/+1 DEX/
  +1 CON, ferocity, d10), Automaton (71%, DR1 + inorganic body), Gnoll (69%,
  +2 CON +3hp), Dwarf (65%), Goliath (64.5%), Lizardfolk (60%). Weak: Sprite
  (26%, −2 STR −2 CON, d6, 1d2 unarmed, flight useless offensively), Kenku (28%,
  −3 STR), Halfling (29%), Kobold (34%), Elf (39.5%), Gnome (45%).
- **Dead-weight-in-combat abilities**: flight (Sprite), keen_hearing (Halfling,
  +3 init only), autotroph (Leshy regen), primal_blood (Gnome, 1 reroll),
  amphibious/gallop (just speed). darkvision looks mid in daylight — needs the
  arena/dark pass to value it.
- **No real synergies**: with Crossbowman excluded, every interaction residual is
  <0.10 (≈noise). Combo strength ≈ race score + occupation score, additive.
- **Balance levers**: give INT/WIS/CHA a combat outlet (or accept those races are
  non-combat specialists per the world-first design); nerf the crossbow (ammo
  scarcity, reload cost, AP, or bump melee); compress racial physical spreads or
  give the weak races a real combat ability; consider weapon-die floor for the
  dagger occupations.
- **Occupation score is ~pure weapon damage die**: 1d4 melee 0.455, 1d6 0.499,
  1d8 0.544, 1d8 crossbow 0.95. The starting item barely matters.
- **Race score is ~sorted by STR then CON then HD.** DEX doesn't rescue low-STR
  races (no DEX-to-melee-damage, few finesse weapons). `pack_tactics` is the one
  non-physical ability with real combat value (Goblin STR−1 still 0.47, above
  better-statted Gnome/Grippli/Kobold/Elf). `ferocity` ≈ a free extra attack.
- **Arena/dark pass (45k, seed 2) confirms it**: race ranking near-identical
  (Orc 79.8, Sprite 25.9); darkvision worth only ~+2-3% (Dwarf #4→#3). The
  crossbow break is daylight/open-field-specific — drops to 73% in the dark
  (can't shoot what you can't see), where Dwarf/Hobgoblin Crossbowman lead.

## Deferred idea: reproducible fixed-seed batches (2026-09-13)

From studying an unrelated open-source project (hexcom) that runs its own
headless AI-vs-AI balance batches: instead of one big random sweep, run
`seed = 1..N` (not random draws) per "arm" being compared, so a specific
figure quoted anywhere is exactly re-runnable by anyone later, and two
readings with one dial changed between them are directly comparable (same
maps/rolls, only the changed thing differs).

**Why:** current `balance_sim.py` sweeps are a single random run per invocation
— reproducing an exact cited number (e.g. "Crossbowman 95%") means re-running
and getting a close-but-different value, and A/B comparisons (e.g. reload
before/after) aren't paired on identical rolls.

**How to apply:** only if/when balance work resumes and a paired-comparison or
citable-figure need shows up — explicitly deprioritized by the user on
2026-09-13, not committed to now. If picked up, it's an addition to
`balance_sim.py`'s battle loop (seed the RNG per battle index within an arm),
not a rewrite.

## `economy_sim.py` — the world-first counterpart (2026-09-09)

Same shape as balance_sim: sample `(race, occ)`, run one trader through `--days`
(default 15) in a town of `--vendors` (default 4) with daily-replenishing stock,
aggregate net copper by race / occ / combo. Three `--mode`s: `bleed` (only the
cost of eating), `production` (occupation makes 1× its table item/day and sells
it), `arbitrage` (vendors get a `±--spread` per-item price multiplier — **a sim
assumption, not a live mechanic** — so buy-here-sell-there can profit). Reuses
`economy.deal_mods` / `deal_value` for the real haggle math; caches the per-vendor
deal once (constant per visit). Fast, single-process. Writes `sim_results/economy-*`.

**Finding: racial abilities + attributes generate ~zero economic difference today.**
- `bleed`: every race loses 25–27 cp/15d on food. Only **Leshy = 0** (autotroph
  skips the meal). CHA +1 Kenku loses the *same* 26 as CHA −1.4 Orc.
- `production`: race spread +1..+7 cp/15d = noise (Leshy +43). **Occupation is
  everything** — and it's the *market value of the produced item*: Physician
  (First Aid Kit, base 40) +262, Guard (Lantern) +186, Crossbowman (Quiver) +141;
  ~half the occupations (dagger jobs, cheap items) can't even cover food (−12..−23).
- `arbitrage` only breaks even at **±35%** regional price spread, only pays at
  **±50%** (invented). At ±50%: Human 592 (its **2nd language** lets it haggle at
  ~2× the vendors) > high-CHA races ~570 > Orc 523. ~13% spread, driven by
  language count more than CHA.
- **Why CHA is inert**: `deal = max(0,mod_CHA)·0.04 + align_bonus`, food costs
  3–5 cp so the discount rounds to 0, and it needs a **shared language** with the
  vendor (~1/11 per vendor). The market is a closed sink (buy `base·(1−deal)`,
  sell `base·(0.5+0.4·deal)` — never cross). No money source in the game (arena
  purse, wilds haul, 3cp/4h lumber wage) is race/attribute-sensitive.
- **Balance levers for the commerce niche**: much stronger haggle (flat cp not %,
  or works without shared language at reduced rate); economic roles for WIS/INT/CHA
  (appraisal → better sell price, arbitrage-spotting); daily production scales
  with an attribute; narrow the buy/sell spread (SELL_FACTOR → ~0.8) so trading
  can be a job.
