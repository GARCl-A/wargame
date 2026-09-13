---
name: gartok-factions-reputation
description: "GARTOK factions + deeds: reputation is per-faction and moves ONLY by completing one-shot achievements (deeds), no per-win grind"
metadata: 
  node_type: memory
  type: project
  originSessionId: e213b717-d560-44b0-8ce6-2d957c9322b2
  modified: 2026-09-11T00:06:56.115Z
---

Added Sep 2026, committed (`fb067cc` + follow-ups). Part of
[[gartok-tactical-project]]. This is **the objective system** — the user's frame:
"cada achievement é sobre reputação com facções; você faz uma mecânica funcionar
em game e ganha reputação."

## The model (`gartok/factions.py`, registry like `talents.py` / `abilities.py`)

- **`Faction(id, name, blurb)`** — an organisation, **not a node**. It may hold
  ground across several nodes. First and only one today: `arena` = "The Pits".
- **`Deed(id, faction, name, blurb, rep, check, requires=None)`** — a **one-shot
  achievement**. `check(guild, node, outcome) -> bool`; when it first passes, the
  id is banked in `guild.deeds_done` forever and `rep` points go to the faction.
  Deeds are **independent / any order** — `requires` only when order must be
  forced (unused so far). Hand-grown, node by node, like the talent trees.
- **`settle(guild, node, outcome)`** — checks every open deed, banks the passers
  (fixpoint loop for `requires` chains), returns the newly completed deeds. Deed
  checks read `node`, `outcome.arena_tier` (the staked `arena_offer` dict, or
  None) and `outcome.squad_size` -- both set on `BattleOutcome` before `settle`.

**Reputation moves ONLY through deeds — there is NO per-win grind** (explicit
design call). Repeatable reputation missions are a *later* thing.

**The Pits' deeds** (+1 rep each, independent / any order, can clear several at
once). `arena_tier` is now a `world.Bout` dataclass (attribute access, not
`.get()`) after a Sep-2026 refactor.

*Stage 1 (`rep` 0→3, opens Bronze):*
1. `arena_first_blood` "First Blood" — win any staked arena bout.
2. `arena_lone_wolf` "Lone Wolf" — win the entry tier (`arena_tier.rep == 0`)
   with `squad_size == 1`. A solo entry-pit win clears #1 and #2 together.
3. `arena_dethrone` "Dethrone the Champions" — beat the champion team.
   `app._open_squad` appends `arena.champion_bout()` (`champion=True` +
   `map_slug="the-pit"`) while the deed is open. See [[gartok-arena-champion-title]].

*Stage 2 — the Games (`rep` 3→6, brings Iron cage into reach), all
`requires="arena_dethrone"`:* built Sep 2026, `gartok/arena.py` +
`gartok/scenario.py`. Once `arena_dethrone` is banked, `_open_squad` drops the
champion bout and appends `arena.brawl_bout()` + `arena.ctf_bout()` (both
`stage2=True`, entry 30 / purse 130 / 3 enemies, opponents from
`arena.stage2_pack` → `encounters.ARENA_LEVEL_WEIGHTS` level 1..6, 1 common).
4. `arena_bloodsport` "Bloodsport" — win any stage-2 bout (`arena_tier.stage2`).
5. `arena_flag_runner` "Flag Runner" — win the CTF bout (`arena_tier.ctf`).
6. `arena_untouchable` "Untouchable" — win the CTF bout with `outcome.player_kos == 0`
   (`player_kos` = `sum(c.kills for c in battle.player_units)`, new on `BattleOutcome`).
   A flawless CTF win banks all three in one `settle` pass.

**Capture the Flag** (`scenario.FlagScenario`, extends `ArenaScenario`,
`is_ctf=True`): `battle.flags = {"player": None, "enemy": None}`; enemy flag
auto-placed in the right half during `build`, player plants theirs in the left
half via `battle_screen` (`awaiting_flag` gates AI turns). `win_check` returns a
team the instant a living unit stands on the *other* side's flag — first real
consumer of the `Scenario.win_check` seam. Non-lethal, so a forced winner never
wipes. `battle.check_objective()` lets the screen end it mid-turn.
**Flag-seeking AI**: `Battle._assign_flag_runners` tags ceil(half) of the enemy
side (fastest first) `ctf_runner=True`; `ai._ctf_goal` + a branch in `take_turn`
sends them at the player's flag (rest hold and fight), so a CTF can be lost too.
The runner steps ONTO the flag cell via `reachable`/`path_to` (not
`path_step_toward`, which stops *adjacent* to a unit) — a downed body lying on a
flag never blocks the cell (`occupied()` excludes the downed). The **enemy flag is
fog-gated** in `battle_screen._draw_flags` (`pos not in self._visible`) — you have
to find it; your own flag always shows.

## Wiring

- `Guild`: `reputation = {faction_id: int}` + `deeds_done = []` **replaced**
  `arena_reputation: int`. `guild.arena_reputation` is now a `@property` →
  `reputation.get("arena", 0)`, so `world.arena_offers` / `map_screen` / tests
  are untouched. Save v3 (`persist`): `reputation` + `deeds_done` dicts/lists;
  old `arena_reputation` key dropped (no migration — runs start fresh).
- `campaign.absorb_battle(guild, squad, battle, node=None, arena_offer=None)` —
  gained `node`; dropped the `guild.arena_reputation += 1` line; builds one
  `BattleOutcome`, sets `arena_reward`/`loot_pool`, then
  `outcome.deeds_earned = factions.settle(...)`. Skipped on a full wipe.
- **`settle` generalized off the battle (Sep 2026, this session).**
  `settle(guild, node, outcome)` → **`settle(guild, event)`**; `Deed.check` is
  `(guild, event) -> bool` (was `(g, node, out)`). New **`factions.Event(kind,
  node=None, outcome=None)`** frozen dataclass — `kind` in {"battle","travel",
  "market","hunt","recruit",…}, battle events carry the `BattleOutcome`. Arena
  deeds now start with `event.kind == "battle"` via `_arena_win(event)` /
  `_arena_tier(event)` helpers. `campaign` passes `Event("battle", node=, outcome=)`.
  **2nd live call site: `map_screen._go`** fires `Event("travel", node=target)`
  on arrival and appends any earned deed to `self.notices` — no travel deed
  exists yet, the seam is just live. A market/hunt/hire trigger is now a
  one-line `factions.settle(guild, factions.Event("<kind>", node=…))` at that
  flow. Test: `test_campaign.py::test_settle_takes_any_event_and_arena_deeds_ignore_non_battle_ones`.
  265→266 tests, sim byte-unchanged.
- `app`: stashes `self._battle_node` in `_start_battle`, passes it in
  `_battle_end`; `RewardScreen(..., deeds=outcome.deeds_earned)` shows a green
  "DEED · First Blood  +1 reputation with The Pits" banner. Non-arena deeds would
  surface on `LootScreen` later (not wired — no such deeds yet). A travel deed
  surfaces in `map_screen.notices` (already wired).
- **`gartok/matchup.py` (Sep 2026)** — `build(node, offer, *, squad_size, guild)
  -> (enemies, scenario)`. Pulled the enemy-list + scenario-choice branching out
  of `app._start_battle` / `_start_title_defense` (champion / cameo / stage2 /
  defense / ctf / map_slug / plain), which was accreting a branch per bout type.
  `app` now just: charge the stake, `matchup.build(...)`, `Battle(...)`. New bout
  type = edit `matchup._enemies` / `_scenario`, not `app`. Tests: `test_matchup.py`.
- `guild_screen` REPUTATIONS tab (`_draw_reputacoes`) rebuilt: per-faction score,
  deeds done (filled dot, OK colour) / open, then the arena tier-unlock list.

## Arena tiers now gate on hand-written deeds

`world.ARENA_TIERS` = Rookie pit → Silver arena, needs rep **0/3/5/10**. Stage-1
deeds = 3 rep (opens Bronze); stage-2 Games deeds = another 3 rep (**opens Iron
cage**, rep 5). Silver arena (10) still sits past reachable rep. User's frame:
"não é um gerador procedural, essa arena funciona assim, essas são as regras dela."

**Tiers now scale (Sep 2026, this session, `matchup.py`).** `world.Bout` gained
`level: int = 0`; `ARENA_TIERS` levels = **0 / 1 / 2 / 3** (Rookie→Silver).
Opponents built via `encounters.build_enemy(offer.level)` (was bare level-0
`Unit("enemy")`). The Games still use `arena.stage2_pack` (level 1–6); the
champion goons are `build_enemy(0)` ≈ the old bare enemy. `reference.py`
`_arena_tiers` gained an "Opponent level" column (REFERENCE.md regenerated).

## Open next

Arena stages 1 & 2 are both built (6 deeds, brawl + CTF + champion bout). Still
open: `ARENA_TIERS` spawning through `encounters` (scale the rep ladder too);
flag-runner AI is basic (fastest-half rush, no coordinated defense). Also:
repeatable rep missions. (`settle` is now event-shaped with a travel call site —
done this session; a market/hunt/hire trigger is a one-liner when a deed needs it.)

**Faction #2 = The Bankers** (Sep 2026), but **deed-less** — see
[[gartok-bankers-bank-chest]]. Registered in `factions.py` with no deeds; its
"content" is the rented bank strongbox (guild storage), not a reputation track.
`guild_screen` + `reference.py` now handle a faction with an empty deed list. A
real deed-driven faction #2 (e.g. `wilds`) is still open.
