---
name: gartok-groups-refactor
description: "GARTOK's Guild->Groups->Units refactor: the guild splits into physical Groups (own position+squad), moving to a tick/orders map loop instead of one token"
metadata: 
  node_type: memory
  type: project
  originSessionId: 53128f45-592b-4d33-907c-09b481f03c91
  modified: 2026-09-13T17:04:21.716Z
---

Started 2026-09-11, mid-implementation (this memory tracks the plan + design
calls; check code state before trusting phase-completion claims). Part of
[[gartok-tactical-project]]; this is the *destrava* item the project x-ray
flagged — the seam for the whole [[gartok-open-world-vision]] (specialised
groups, base-building chains) to exist at all. Plan file (if still present):
`C:\Users\lucas\.claude\plans\bubbly-napping-tiger.md`.

## The user's frame (verbatim design constraints, durable)

> A GUILDA contém GRUPOS que contêm UNIDADES. Quem anda no mapa são os GRUPOS.

- **A group is a physical unit** — everyone in it is always at the same place.
- **A unit is always in exactly one group**, even if solo (a "solo group" is
  valid — this is what makes `arena_lone_wolf` meaningful again, see below).
- **Physically co-located groups can be merged** (⇒ splitting must also exist —
  merging only means anything if you can peel a group apart first).
- **Shared state stays guild-level**: bank chest, faction reputation/deeds, the
  taverna pool, the campaign clock, `battles_won`. **Groups own position + squad
  composition.** The Guild becomes "the shared stuff + the full member list."
- **Time model = tick / orders** (chosen over a single instant-travel clock and
  over per-group clocks): issue an order to each group (Travel/Work/Hunt/Market/
  Bank/Recruit/Arena/Idle), hit ADVANCE, the world jumps to the **soonest order
  completion** across all groups, runs upkeep over that span, then resolves
  every group whose order came due. Auto orders (Travel/Work/Idle) resolve
  silently; interactive ones (Battle, Market, Bank, Taverna, Hunt) hand control
  to their existing screen, played one at a time from a queue. Idle groups still
  eat during upkeep.

## Phasing (each independently mergeable — logic before pixels)

1. **Data model + persistence** (behaviour-identical, one group covering the
   whole roster) — `gartok/group.py` (`Group`: `gid, members, node, name,
   order`); `Guild.groups` list; `Guild.roster`/`Guild.node` become **Phase-1
   shims** (properties over the single group — ambiguous once >1 group exists,
   removed in Phase 3); the 3 real roster-mutation sites
   (`guild._daily_upkeep` casualties, `campaign.absorb_battle` permadeath,
   `recruit.enlist`) became `guild.remove_members`/`guild.add_member`/
   `guild.group_of`; **hunger/food-sharing scoped to the group** (see
   [[gartok-food-sharing]] — `_shared_larder` now pools only the eater's own
   group). Save format v6→v7: `"groups": [{gid,name,node,members}]` replaces
   flat `"roster"`/`"node"`; `load_game` falls back to one group for a save with
   no `"groups"` key (no other migration).
2. **Orders + the event-driven advance engine** (headless) — `gartok/orders.py`
   (`Order(kind, dest, hours_left, interactive)`); `campaign.advance(guild) ->
   TickResult(events, pending, wiped)` — jumps `dt` to the soonest
   `hours_left`, calls `guild.pass_time(dt)`, decrements every order, resolves
   auto kinds inline, queues interactive kinds in `pending`.
3. **Map UI** — one token per group, group selection, issuing orders (replaces
   `map_screen`'s instant `guild.node = target.id`), a split/merge control
   (`guild.split_group`/`merge_groups`, merge gated on same node), the ADVANCE
   button, and `app` draining `TickResult.pending` as a queue of existing
   activity screens (SquadScreen/MarketScreen/BankScreen/TavernaScreen/
   HuntScreen — all already take a plain member list, not the whole guild, so
   they scope onto a group with no internal change).

**Status as of 2026-09-11: Phases 1 and 2 done, not committed.**

Phase 1 (`gartok/group.py`, `guild.py`, `campaign.py`, `recruit.py`,
`persist.py` v7 + fallback, RULES.md hunger prose). 277→284 tests green.

Phase 2 (`gartok/orders.py` new; `campaign.TickResult`/`campaign.advance`):
`Order(kind, eta, remaining, dest, hours)`; `AUTO_KINDS={travel,work}`,
`INTERACTIVE_KINDS={arena,market,bank,recruit,hunt}` (named to match `app`'s
existing `_open_*` openers 1:1, so Phase 3 just calls them). `orders.travel`
raises `ValueError` for an unreachable destination (checked, since the graph is
fully connected today so this can't happen through normal play — only
exercised by a deliberately bogus node id in tests). `orders.work` bakes in
Brisk Hands' clock-speedup (`Guild.work_speedup`, pulled out of `work_shift`)
so the order's ETA is the real clock cost while `order.hours` stays the nominal
shift length pay/XP is based on. **Key fix to get right**: `guild.work_shift`
(the old instant/single-call path, still used by the legacy `WorkScreen`) calls
`pass_time` itself; the tick's `advance()` must NOT call it again when a work
order resolves (`dt` already advanced the shared clock once for the whole
guild) — split into `Guild._pay_shift` (pay+XP only, no clock advance) reused
by both paths. `advance()` jumps `dt = min(remaining across active orders)`,
runs `guild.pass_time(dt)` once, then resolves every order that hit 0: travel
moves `group.node` + fires the existing `factions.settle(Event("travel", ...))`
seam verbatim (same message format as the old `map_screen._go`); work calls
`_pay_shift`; everything else queues into `TickResult.pending` as
`(group, order)` for the caller to play. A mid-tick wipe (upkeep starves the
last group empty) short-circuits before the resolution loop
(`TickResult(wiped=True)`, `pending` stays empty) — verified by test.
`remove_members` (Phase 1) also now prunes any group it empties out entirely,
so a dead group doesn't linger as a ghost token. 292 tests green (8 new in
`test_orders.py`), `sim_test.py` still byte-identical (battles untouched by any
of this). No UI wired to any of it yet.

**Phase 3 (map UI) done 2026-09-11, not committed.** `map_screen.py` rewritten:
`self.selected` is the group every click acts on; a GROUPS list (side panel)
switches it; clicking a node issues `orders.travel` on the selected group
instead of moving instantly; per-node actions (arena/market/bank/recruit/hunt)
issue `orders.interactive(kind)`; a WORK node shows an inline 4/8/12/16h chip
row that issues `orders.work` directly (no screen). SPLIT (peel members into a
new co-located group) and MERGE (fold a co-located idle group in) are new
`Guild` methods (`split_group`/`merge_groups`) with their own small UI mode.
ADVANCE calls `on_advance()` (-> `app._advance`, `dt=None`); MAINTENANCE calls
`on_advance(dt=1)` -- **both go through the same `campaign.advance`**, so an
order in flight can't drift out of sync with the clock (this is why
`campaign.advance` grew the `dt=` override, and why `Guild.do_maintenance`'s
"eat now" tail got pulled out into `Guild.eat_now_pass()`, reusable standalone).
Map markers show a "+N" badge for other groups sharing a node (selection stays
list-driven, not click-the-map, to keep hit-testing simple).

`app.py`: `_pick_party`/`_open_squad`/`_open_market`/`_open_bank`/`_open_work`/
`_open_hunt`/`_open_recruit` (the old map-click openers) are gone. New
`_advance(dt=None)` calls `campaign.advance`, stashes `TickResult.pending`, and
`_after_activity()` drains it one screen at a time (skipping any group that
starved out entirely before its turn -- see the bug below), reusing the
existing `_open_market_stalls`/`_open_bank_vault`/`_open_taverna`/
`_open_hunt_ground`/new `_open_arena(group, node)` -- every activity screen's
`on_done`/`on_back` now points at `_after_activity` instead of `_start_map`.
**Market/Bank/Taverna/Hunt no longer need a party-picker at all** -- the
resolving group's own `.members` *is* the party (that's the point of having
split it off); `SquadScreen` survives only for the Arena, where squad size vs.
`player_cap`/stake tier is still a real choice. **`WorkScreen` is deleted** --
work is now a fully silent order, resolved by `campaign.advance` into notices
exactly like travel, never a screen.

**Real bug caught by testing, not by inspection:** `campaign.advance` snapshots
`active = [g for g in guild.groups if g.busy]` *before* running
`guild.pass_time(dt)` -- if a group starves out entirely during that same
tick's upkeep, `remove_members` prunes it from `guild.groups`, but the stale
reference was already captured in `active` and would still get appended to
`TickResult.pending` as "a screen to open" for a group with zero members. Fixed
in `campaign.advance`'s resolution loop (`if g.empty: continue`) and defensively
again in `app._after_activity`. Caught by
`tests/test_map_orders_integration.py::test_a_group_that_starves_out_before_resolution_is_skipped`
(two co-located groups, one fed, one not, same-tick same ETA) -- would have
silently opened e.g. `MarketScreen(..., shoppers=[], ...)` otherwise.

Validated with a throwaway headless smoke script (real `Fonts()`, real pygame
surfaces, `SDL_VIDEODRIVER=dummy`, deleted after use) driving the actual
`App`/`MapScreen` objects (not mocks) through: split -> travel -> advance ->
work -> pay -> market order -> real `MarketScreen` opens -> drains back to map
-> maintenance (clock +1h exactly) -> bank -> taverna -> merge back to one
group. All 12 steps passed live. Arena and the starved-group skip are covered
by mocked integration tests instead (`test_map_orders_integration.py`), not the
live script.

305 tests green (300 after Phase 1+2), `sim_test.py` byte-identical throughout
all three phases.

## /pre-commit review + fixes (2026-09-11, same session)

Caught one real regression and two smells before committing:
- **Real bug**: `Guild.eat_now_pass()` was extracted from `do_maintenance`
  specifically so the new MAINTENANCE button could reuse it, but nothing ever
  called it -- MAINTENANCE (`campaign.advance(guild, dt=1)`) forced the clock
  but silently dropped "anyone still hungry eats right now." `do_maintenance`
  itself had gone dead in production (only its own test called it). Fixed:
  `campaign.advance` now runs `eat_now_pass` whenever `dt` is explicitly forced
  (that's the actual semantic difference between MAINTENANCE and ADVANCE).
  Regression tests added (`test_forced_dt_also_runs_eat_now_pass_thats_what_makes_it_maintenance`,
  `test_an_unforced_advance_does_not_run_eat_now_pass`).
- `Order.interactive` (`orders.py`) was dead -- `campaign.advance`'s resolution
  loop reimplemented the same auto/interactive split with raw `kind` checks
  instead of reading it. Now wired in (`elif order.interactive:`).
- Three `guild.py` docstrings said "Phase-1 shim" -- session planning jargon
  with no meaning in the code itself. Reworded to "single-group convenience."
- `map_screen._draw_group_actions`'s MERGE button only ever showed one
  co-located idle group (`mates[:1]`, "one row is plenty for now"). Generalized
  to one row per idle co-located group + simplified the layout (dropped the
  two-column split/merge math for stacked full-width rows). Smoke-tested with
  a 3-group-same-node fixture in `test_screens.py`.
- `app._after_activity`'s empty-group skip looked like redundant paranoia next
  to `campaign.advance`'s own guard -- added a comment: it isn't redundant,
  because `HuntScreen` calls `guild.pass_time` directly mid-activity and can
  starve a *different*, still-queued group sitting in `self._pending`.

**Committed as two commits** (`git log --oneline -2`):
1. `5792ed0` -- Rookie pit `enemies=1→3` (`world.py`), split out from the
   refactor since it's an unrelated balance fix that happened to land in the
   same session (world.py's docstring hunk was reconstructed onto the
   pre-refactor file so this commit doesn't carry any Group/orders wording).
2. `bfc6401` -- the whole Guild→Groups→Units + tick/orders + map rewrite
   (19 files, group.py/orders.py new, work_screen.py deleted).

307 tests green, `sim_test.py` byte-identical. **Not pushed** (`git status`:
ahead of origin by 2 commits).

**Known follow-ups, not yet done:**
- The GROUPS list/SPLIT/MERGE UI is functional but plain (compact rows, no
  drag-to-reassign, no rename) -- a polish pass, not a correctness gap.

**Resolved, not a gap:**
- Champion title defense triggers guild-wide regardless of which group's arena
  order triggered it -- flagged here as debt to fix, but the user corrected
  this 2026-09-11: it's correct behaviour by design (see
  [[gartok-arena-champion-title]] "the title is a GUILD-level thing"). Do not
  re-flag this.
- "No one has played this by hand" -- resolved by 2026-09-13, user confirmed
  multi-group split-and-parallel-activities works in real play.

## Also landed this session (separate, small, pre-existing plan item)

`world.ARENA_TIERS` Rookie pit `enemies=1`→`3` (`world.py:114`) — a solo
`arena_lone_wolf` win was trivialized to a forced 1v1 by the boss-fight
squad-cap work (see [[gartok-arena-ribbit-brothers-boss]] "Open / not
resolved"). User's call: "tem que ser NO MINIMO 1x3." `REFERENCE.md`
regenerated. Not committed.

## Open design points resolved during planning (flag if the user wants these changed)

- Multiple interactive orders due at once resolve **sequentially**, not
  simultaneously.
- ADVANCE jumps to the **soonest completion** (discrete-event), not a fixed tick.
- **Idle groups still run daily upkeep** in place.
- Approach-cost hours for interactive orders (market/bank/taverna/arena) — a
  small fixed knob, deferred to Phase 2 implementation.
- Champion title defense becomes an arena order for whichever group holds the
  champion — deferred to Phase 3.
