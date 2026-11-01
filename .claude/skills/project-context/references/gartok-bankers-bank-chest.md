---
name: gartok-bankers-bank-chest
description: "GARTOK faction #2 The Bankers (deed-less for now) + the guild's first shared property: a rented bank strongbox (weight-capped storage) at the City"
metadata: 
  node_type: memory
  type: project
  originSessionId: fec0287b-b105-4e05-9338-c732e7791746
  modified: 2026-09-10T23:02:46.919Z
---

Added Sep 2026. Part of [[gartok-tactical-project]], extends
[[gartok-factions-reputation]]. User's frame: the Bankers "vendem qualidade de
vida"; lending + debt collection is their real trade but **deferred** — this first
cut is only the strongbox. Also the guild's first *bem imóvel* (shared property).

## The Bankers (`gartok/factions.py`)

`Faction("bankers", "The Bankers", ...)` — registered now, **no deeds**. Shows in
the REPUTATIONS tab with a "None yet — this faction's standing doesn't move." line
(`guild_screen._draw_reputacoes` now guards empty `DEEDS_BY_FACTION`).
`reference.py._factions` prints "_No deeds yet_" for a deed-less faction (drift
test enforced). No reputation mechanic at all — renting the chest is a flat fee,
not gated.

## The bank strongbox

- **Guild state** (`gartok/guild.py`): `bank_capacity` kg (0 = not rented),
  `bank_items` list[str]. `bank_unlocked` prop, `bank_load` prop (sums
  `data.item_weight`), `rent_bank_chest()` sets capacity (caller pays first).
  Persisted (`persist.py`, SAVE_VERSION 5→6).
- **Economy** (`economy.py`): `BANK_CHEST_PRICE = 50`, `BANK_CHEST_CAPACITY = 10`.
  One tier — `bank_capacity` is shaped for a later bigger box (raise the value).
- **World**: `world.Node` got a `bank=False` flag (parallel to `work`); the `city`
  node has `bank=True`. `map_screen` shows "VISIT THE BANK" for `here.bank` →
  `app._open_bank` → `_pick_party` (market-style party picker) →
  `_open_bank_vault` → `BankScreen`.
- **`gartok/bank_screen.py`** (new): `DragSelectMixin` + custom move logic (not
  `LoadoutMoveMixin` — the chest isn't a Unit). Left = chest panel (locked: RENT
  button paid from the party's pooled purse, richest-first via `_leave` split like
  market `_checkout`; unlocked: capacity bar + stashed rows). Right = party member
  cards showing **pack only**. `sel` is `("bank", idx)` or `(member, idx)`,
  single-select. Deposit caps on `bank_load + weight <= bank_capacity`; withdraw
  and hand-over cap on the taker's `carry_max`. Gear in the chest is only
  reachable from the City.
- **v1 limit**: only pack items move (spares); wielding/wearing stays on the gear
  screen. Noted in the module docstring.

`MapScreen.__init__` gained an `on_bank` param (8th callback) — `test_screens.py`
and any `MapScreen(...)` call site need the extra arg. Tests: `tests/test_bank.py`.

Prose: RULES.md "Reputation and factions" → "Faction #2 — The Bankers".
