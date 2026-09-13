---
name: gartok-arena-champion-title
description: "GARTOK 'Champion of the Pit': per-character title from dethroning Adelio, arena-only Demoralize perks, 15/7-day title-defense cycle (implemented in gartok/arena.py)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 384b62b6-698b-44f6-bcb4-2f3d84fec5d2
  modified: 2026-09-11T22:19:39.525Z
---

Designed AND implemented Sep 8 2026, committed (`fb067cc`). Part
of [[gartok-tactical-project]]; builds on [[gartok-factions-reputation]] (the
`arena_dethrone` deed) and [[gartok-character-creator]] (`npc_lib`, the Adelio
NPC file at `npcs/adelio-small-knife.json`).

**Sep 2026 follow-up:** the champion bout is now fought on the hand-authored
`maps/the-pit.json` (with the sunken hole from [[gartok-z-axis]]) —
`arena.champion_bout()` carries `map="the-pit"` / `arena.CHAMPION_MAP` and
`app._start_battle` builds `CustomScenario(map_lib.load_map(...))` when an offer
has a `map`. Adelio (`load_champion()`, no `map_cell`) deploys to the map's
`deploy_npc` cell (14, 7) via `CustomScenario._is_npc`; `npc_units` is NOT called,
so no second Adelio. Win condition unchanged — down the whole team; the pit is
scenery, nothing about it is mandatory. First real consumer of the map editor's
output. See [[gartok-map-editor]].

## As built

- `gartok/arena.py` — new module: `champion_bout()` / `defense_bout()` offer
  dicts, `champion_of` / `defense_due` / `defense_deadline` / `sync` (lazy
  forfeit), `build_challenger(mean_level)` (both tracks to that level + random
  valid talents), `load_champion()` (Adelio, tagged `arena_role="champion"`,
  `arena_title=True`), `cameo_enemy()` (5%).
- `Unit`: `bio` (str) + `arena_title` (bool) fields, `set_bio`; round-trip in
  `persist.unit_to_dict` / `from_save`. SAVE_VERSION 3 → 4.
- `Guild.arena_challenge_day` (int day / None), persisted.
- `Combatant.downed_by` set in `credit_kill` (covers the non-lethal KO path).
- `Battle(..., arena=False)` flag; `app._start_battle` passes `arena=node.arena`.
- `actions.Demoralize`: `_can_provoke(battle, actor, target)` now also true for a
  titled actor in the arena; +1 `[circumstance]` on the roll when language shared;
  target MD +1 when the target is the titled champion in the arena.
- `campaign.absorb_battle`: `_claim_champion_title` (finisher via `downed_by` →
  squad member) and `_settle_title_defense`; sets `outcome.arena_title_event`.
- `app`: `_start_title_defense` (bypasses SquadScreen, straight to a 1v1),
  champion bout appended to arena offers while `arena_dethrone` open, cameo swap
  in normal bouts, `_map_notices` buffer, `arena.sync` in `_start_map`.
- `RewardScreen(note=...)`, `MapScreen` shows a WARN line + "DEFEND YOUR TITLE"
  button when `defense_due`.
- `char_editor_screen`: BIO edit row (`_MAX_BIO=240`).
- Tests: 6 new in `test_gartok.py` ("arena: the Champion of the Pit title"),
  plus title/bio fields added to `test_save_slot_file_round_trip`. 174 pass.

## Lore

The Pits (`arena` faction) is a **fighters' guild** whose HQ *is* the arena. Adelio
Small-Knife — Halfling ex-thief from the village, joined recently — is champion of
the lowest tier, "the best of the worst." The champion bout is Adelio **+ 2 random
level-0 capangas** (`Unit("enemy")`). Winning it is the 3rd arena deed
`arena_dethrone` ("Dethrone the Champion").

## The title is a per-CHARACTER thing, not the guild's

- Goes to **whoever lands the KO on Adelio** (arena is non-lethal → the blow that
  zeroes his HP). Needs a new engine seam: record the downing combatant so
  `campaign.absorb_battle` can map it back to the roster `Unit`.
- Stored on the `Unit` (round-tripped in `persist.unit_to_dict`; shows in the
  player save and, while Adelio holds it, in his npc json).
- **Messy KO → title stays VACANT, no second chance** (bonuses lost for the run):
  - downed by a capanga's friendly fire → nobody claims (Adelio's side loses anyway);
  - "pet lands the KO → pet becomes champion" is what the user *wants* but the
    engine has no pet-combat (`Creature` = passive blocker, `ground.py`): park it
    behind a future combat-pets feature, leave a comment-hook only.
- Deed + reputation still land regardless of who/what got the last hit.

## What the title does — ONLY inside the arena

Needs `Battle` to learn it's an arena fight (pass `arena=node.arena`; today it
only gets `lethal`). Then in `actions.Demoralize`:
- holder may Demoralize **any** target, no shared language required;
- if the holder **does** share a language: **+1** to the roll (so knowing the
  tongue beats the free pass — intended);
- holder gets **+1 Mental Defense** vs Demoralize.
No passive income (user rejected it).

## Title defense — 15/7 day cycle

- Every 15 days (`clock.day`) a formal challenge is issued; champion has **7 days**
  to be at the arena node and fight a **1v1**. No per-day hook today → check lazily
  in `app._start_map` (like `recruit.refresh_pool` on tavern visit). Persist
  `title_challenge_day` (or None).
- Miss the window OR lose the 1v1 → **title lost, permanent for the run** (deed
  stays banked, only the arena bonuses go).
- Challenger = `Unit("enemy")` with `set_track_level("combat", M)` +
  `set_track_level("work", M)` where `M = champion.mean_level + 1` (so it scales
  each cycle), **plus random talent picks that respect tree prerequisites**
  (`set_track_level` alone gives HD but no talents).
- Fiction: stronger adventurers keep arriving; to fight the higher rings they need
  reputation, so eventually a strong one challenges the pit champion to ascend.

## Adelio after being dethroned

Becomes a "recurring NPC" — for now that means **5% chance per normal arena bout**
that one enemy slot is `npc_lib.load_npc("adelio-small-knife")` instead of a rolled
`Unit("enemy")`. He **stays level 0 forever** ("best of the worst").

## Correction (2026-09-11): the title is a GUILD-level thing, not a per-group one

The project x-ray flagged "champion title defense still triggers guild-wide
regardless of which group's arena order triggered it" as architecture debt to
fix under the new [[gartok-groups-refactor]] Group model. **User's correction:
this is correct behaviour, not a bug** — "o título de campeão é realmente algo
na guild." The title belongs to the guild as a whole (which unit currently
carries it is bookkeeping, not scope) — do not suggest scoping title-defense
per `Group`.

**General premise, applies to titles as a category, not just this one:** "os
títulos só estarão disponíveis na primeira vez que um feito for realizado por
save" — a title is claimable only by whoever *first* completes the triggering
feat in a given save; that exclusivity is definitional to what a "title" is in
this game, not a one-off rule for Champion of the Pit. Any future title should
carry the same first-clear-only premise.

## Build order (agreed)

- **Leva 1**: `bio` field on units + Adelio's bio (+ char-editor text field); the
  champion-challenge bout (fixed "Challenge the Champion" button at the arena while
  `arena_dethrone` is open; builds Adelio + 2 filler; offer carries `champion=True`);
  KO-attribution seam; title as a persisted `Unit` flag (SAVE_VERSION → 4);
  RewardScreen line.
- **Leva 2**: the arena-only Demoralize/MD effects; the 15/7-day defense cycle +
  scaled challenger; Adelio's 5% cameo.
