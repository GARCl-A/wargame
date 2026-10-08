---
name: gartok-economy-lore-tutorial
description: Oct 2026 arc on main -- the world premise (adventuring beats day labour), the economy numbers tuned to it, and the modal tutorial system that teaches the game; commits 769c8c6, 92ecec4, 811ef12
metadata:
  type: project
---

Done 2026-10-04 on `main`, three commits (`769c8c6` economy, `92ecec4` tutorial, `811ef12` hub purse fix).

## The premise (from the user's voice memos)

Gartok is generic medieval fantasy. Economically, delving into ruins, catacombs and
wild forests for creatures, artefacts and magic items pays far better than honest
work, so everyone who can hold a weapon is out there (One Piece's Age of Pirates).
Guilds are the standard way to organise and the big ones grow into company-like
entities; the player is founding one with a little coin and three recruits. This is
the copy of the `draft.intro` card and the yardstick for every number below.

## Economy checked against it

A headless sim (level-0 squad of 3, AI on both sides) found the premise did NOT
hold: lumber paid 2.25-3 cp/h, hunting ~2 cp/h at ~0.37 deaths/h, and the arena
Scrapper paid -4.9 cp per bout at the AI's 50% win rate but +5/h for a player who
wins every time (one bout per hour: battle time is seconds, only `APPROACH_HOURS = 1`
counts, and nothing caps repeats). Tuned to:

| Source | Now | Per hour, team of 3 |
|---|---|---|
| Lumber, foreman's axe | 1 cp per 4 h block (4 cp / 16 h = cheapest meal, a 3 cp Potato, +1) | 0.75 |
| Lumber, own axe | 4/3 of that, floored (`LUMBER_AXE_RATIO`, 5 cp / 16 h) | 0.94 |
| Arena Scrapper | entry 3 each, purse 11 (win +2, loss -9, break-even 82%) | +2.0 at 100% wins |
| Wilds hunt | wolf drops Hide at 100% (was 75%) | ~3 loot+meat at 100% ambush wins, deaths otherwise |

The scale is: hunt with good tactics (3.5-4.4) > perfect Scrapper (2.0) > lumber
(~0.8-0.9). Two-hides-per-wolf was rejected as silly.

**Not touched on purpose:** the Games bouts. Brawl is entry 30 each / purse 130
(break-even 69%, enemies level 1-6) and is now the richest faucet; the user wants to
play it and feel the progression before tuning. Arena level-0 XP only goes to
level-0 characters, which already limits the Scrapper farm.

## Tutorial system

- **Every card is modal** (`ui/intro_card.py`, drawn by `tutorial_card.draw`): dimmed
  screen, serif paragraphs, optional brass `suggestion` line, one button (`Got it`,
  `draft.intro` says `Begin`). The old small corner card, `tutorial_anchor` and
  `footer_anchor` are gone; `?` badge still reopens the current card.
- **Debounce** lives in `App._tutorial_swallow`: while a card is up every click and
  key is swallowed (click or Enter/Space dismisses; Esc still opens pause); after a
  dismissal clicks are swallowed for `TUTORIAL_DEBOUNCE_MS` (300) and the dismissing
  press's mouse-up is eaten, so closing a card never presses what is under it.
- **Per new save**: each `_new_game` gets a fresh `TutorialState`, so every card shows
  the first time; it saves with the guild. Existing saves see the new ids on first visit.
- **`draft.intro`** is chosen in `DraftScreen.tutorial_key` (needs the state, hence
  `DraftScreen(tutorial=...)`), only while no pick is made.
- **Map**: `MapScreen` returns `"map"` again; the COMMAND bar's own `?` button is the
  reopen badge (`_help_rect`). Before this the card was registered and never shown.
- **Hubs** (`bank_hub`, `library_hub`, `apothecary_hub`) delegate `tutorial_key` to the
  active tab; before this the `bank` and `library` cards never showed. Their tabs sit
  40 px left of the right edge for the badge, and the inner screens' purse text is
  pushed left by `header_reserve` (a class attribute on `StashScreen`/`MarketScreen`).
- Ids: draft.intro/pick/identity, map, guild.members/overview/reputations, squad,
  battle, loot, reward, market, taverna, hunt, bank, gear, level, library, group,
  missions (all `MissionOfferScreen`), trust, ledger, craft (forge/scriptorium/
  apothecary), property, claim, guard, prison. `test_no_registered_card_is_orphaned`
  fails if an id is registered but no screen returns it.
- Copy rule: every claim in a card was checked against the code, constants or RULES.md;
  copy is where the map's old "pick a group on the right" bug hid (the list is on the left).

**Why:** the user wanted the lore as the first interaction and tutorials that actually
teach how to play (hunger, the clock, permadeath, first steps) and how to use each screen.

**How to apply:** a new screen needs a `tutorial_key()` and a `tutorial.<id>` block in
`locales/en.json`; keep the badge clear of the screen's own top-right controls. Re-run
`scripts/economy_report.py` (see [[gartok-economy-sim-v2]]) after any change to
`LUMBER_WAGE`, arena purses or loot values; the numbers above are the 2026-10 reference.
Related: [[gartok-open-world-vision]], [[gartok-balance-sim]], [[gartok-wilds-hunting]].

## Left open
- Brawl / Games economy (see above).
- No cards for `RepossessionScreen`, `alert`, `adelio_prompt` (decision modals that explain themselves).
- No reusable "build any screen with a real guild" test fixture; each visual audit is a one-off script.
