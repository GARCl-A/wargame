---
name: gartok-arena-ribbit-brothers-boss
description: "GARTOK arena Games capstone: the Ribbit Brothers (3 authored Grippli + 3 goons, CTF on an authored map); the design rules behind it -- expected player level, arena squad caps, honest NPC stats (implemented in gartok/arena.py, matchup.py, scenario.py)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2a6a9a70-10ce-42b5-bde1-95af8b72d5a6
  modified: 2026-09-11T01:27:33.463Z
---

Designed AND implemented Sep 10 2026, committed (`ded5da7`). Part of
[[gartok-tactical-project]]; capstone of the arena's second stage (the Games),
which sits behind [[gartok-arena-champion-title]] (`arena_dethrone`). Builds on
[[gartok-talent-trees]] (racial hit dice = `1 + racial_level`) and
[[gartok-map-editor]] (`maps/capture-the-flag-the-gamers.json`, authored by the
user, `deploy_npc` positions are the user's own placement).

## The design rules (agreed with the user, apply to future arena content too)

- **Expected player level entering the Games = mean level 3** (combat XP
  doubles at battle end, so this is reachable through normal arena/Wilds grind
  by the time `arena_dethrone` is banked). A boss team is *expected level + 1*;
  ordinary scaled goons sit *at* expected level.
- **Arena squad cap = opponent count, per bout** (`world.Bout.squad_max` /
  `.player_cap`, default 0 = "match `enemies`"). Every staked tier and Games
  bout already satisfies this without setting `squad_max`; only the boss bout
  needs it explicit (`squad_max=6`, since `enemies=3` there only counts the
  goons, not the 3 authored brothers). Side effect the user hasn't ruled on:
  Rookie pit now forces a 1v1, which makes the `arena_lone_wolf` deed free --
  flagged, not resolved.
- **Authored NPC stats must be honestly rolled, not hand-picked-to-feel-strong.**
  A "proxy" (`encounters.build_enemy`) rolls a real 3d6 array per attribute,
  average total ~63. The first draft of the three brothers hand-picked totals
  (68-73) without saying so -- the user caught it ("vc provavelmente roubou").
  Fixed by actually rolling 3d6 x6 and assigning the dice to the stat that fits
  the role (legitimate array-assignment, not inflation): Ribit 63 (average
  roll), Bufo 75, Peep 77 (both genuinely lucky rolls, left as rolled). Same
  discipline should apply to any future authored NPC.
- **HP for an authored NPC comes from the baked `level_hp_rolls`, not a
  hand-set `hp_override` that happens to look plausible.** First draft set
  Bufo's HP to 58 (near max-possible-rolls for his 5 HD) via `hp_override` --
  caught by the user doing the arithmetic themselves. All three NPCs now carry
  `hp_override: null`; HP is whatever their baked dice + Con + talents produce.
- **A symmetric CTF map needs no favoritism mechanic.** An earlier pass gave
  the boss team `enemy_defends_flag` (never race back) plus a rigged deep flag,
  reasoning from a *first* frog placement that was accidentally mid-map (an
  unfair footrace). The user placed the brothers properly at the map's own back
  line (symmetric to the player's), which made the special-casing pointless --
  reverted in full. Lesson: check terrain/placement symmetry before reaching
  for an asymmetric rule. Verified programmatically (`walls`/`water`/`elevation`
  invariant under `x -> cols-1-x`) and by a controls-for-position mirror battle
  (frogs vs frogs, symmetric deploy zones) landing at ~50/50 over 150 runs.

## As built

- `gartok/world.py` -- `Bout.squad_max` (0 = match `enemies`) and the
  `player_cap` property; `SquadScreen.max_pick` (`squad_screen.py`) is now a
  property that tracks the selected offer's `player_cap`, trimming the pick on
  a tier switch. The offer-tile "N opponent(s)" line was reading `off.enemies`
  (wrong for the boss, which only counts goons there) -- switched to
  `off.player_cap`.
- `gartok/arena.py` -- `boss_bout()`: `Games: The Ribbit Brothers`, entry 40,
  purse 450, `enemies=3` (goons only, `BOSS_GOON_LEVEL=3`), `stage2=True,
  ctf=True, boss=True, map_slug="capture-the-flag-the-gamers", squad_max=6`.
  Offered alongside `brawl_bout()`/`ctf_bout()` once `arena_dethrone` is done
  (`app._open_squad`).
- `gartok/matchup.py` -- `offer.boss` branch: enemies =
  `map_lib.npc_units(map_lib.load_map(offer.map_slug))` (the 3 brothers, placed
  by the map's `deploy_npc`) + `offer.enemies` goons at `offer.level`; scenario
  = `CustomFlagScenario` when `offer.ctf and offer.map_slug`.
- `gartok/scenario.py` -- `_FlagObjective` mixin (pulled out of the old
  `FlagScenario`): `is_ctf`, `build` (calls `auto_place_enemy_flag` after
  `super().build`), `auto_place_enemy_flag`, `win_check`. `FlagScenario(_FlagObjective,
  ArenaScenario)` and the new `CustomFlagScenario(_FlagObjective,
  CustomScenario)` both just inherit `build` from the mixin -- no per-class
  override, cooperative MRO resolves `super()` to the right terrain parent.
- `gartok/factions.py` -- deed `arena_ribbit_brothers` ("The Ribbit Brothers"),
  requires `arena_dethrone`, checks `_arena_tier(e).boss`. A clean boss win
  banks it alongside `arena_bloodsport`/`arena_flag_runner`/`arena_untouchable`
  in one go (all four key off the same win, by design -- the capstone sweeps
  the Games' deed sheet).
- `npcs/ribit.json` (rewritten), `bufo.json`, `peep.json` (new) -- all Grippli,
  combat level 6 / work level 2 / racial level 4 (5 HD), `tongue` racial talent.
  Ribit: Dagger + Dagger (tongue), agile/deadeye/fleet/alert/iron_will/quick_wits,
  Leather Jerkin, HP 31. Bufo: Broadsword + Shortspear (tongue),
  strong/sure_strike/heavy_hand/tough/hardy/bulwark, Chainmail, HP 38 (the
  tank). Peep: Light Crossbow + Dagger (tongue), agile/deadeye/long_reach/
  fleet/alert/quick_wits, Leather Jerkin, HP 23 (Amphibious sniper, sits in the
  map's deep water).
- `maps/capture-the-flag-the-gamers.json` -- name fixed (was missing a closing
  paren), `deploy_npc` pins the brothers at the map's own back line
  (`[17,8,"peep"], [18,14,"ribit"], [20,8,"bufo"]` -- the user's own placement,
  not mine).
- Tests: `test_arena_games.py`, `test_matchup.py`, `test_campaign.py` (updated
  for the new squad-cap reality on `Iron cage` instead of `Rookie pit`).
  277 pass.

## Open / not resolved

- **Balance is unvalidated against a real player.** AI-sim proxy (crude,
  uncoordinated, random talents) loses to the boss team consistently even
  after the HP/attribute fixes -- expected, since the proxy has none of a
  human's advantages (gear choices, first aid, focus fire, smart flag timing),
  but nobody has actually played the fight yet.
- **Rookie pit forcing a 1v1** (see squad-cap rule above) trivializes
  `arena_lone_wolf`. Needs a decision: bump Rookie to 2 opponents, rework the
  deed, or accept it.
