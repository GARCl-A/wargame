# Playtest backlog — what is still open

From the 25-item playtest review (2026-10-05). Resolved items are left out:
7 prison like the tavern, 9 HP cur/max, 13 quiver ammo, 15 (no action — mutual
sight stays), 16/17 study split and dictionary, 18 wolf meat, 19 zoom/scroll,
20 arrow-key movement, 21 sentinels racial 5, 22 amethyst price, 23 bank house
purchase, 24 distribute load with coins, and the Claim garrison bug (clock
and re-entry).

Scope notes are from the original review text. Ease/impact are estimates, not
checked against the code.

## Design arc in progress

- **25. Garrison of 10 days at the Claim.** The bug is fixed and the food problem
  has an answer (jerky, campfire, wagon, animals). What remains is in
  [wagon_camp.md](wagon_camp.md): the house and Claim garages, the guard selector
  for the Ruins and the Wilds hunt (design settled, not built), then camp upkeep and
  the Farm hub; broken wagons and mounts come later.

## Medium

- **14. Medic / rest until full.** Camps of 8 h are tedious. Either a medic NPC
  that speeds healing, or a "rest until full" button that costs X days and X
  food, shown up front. Rest healing is deterministic, so the cost is computable.
- **10. Delay action.** Push the unit to the end of the initiative order. Needs
  the action, UI, AI support and tests (see "Feature Implementation Rules").
- **11. Combat info modal.** Hide it by default and rework it: it carries
  information that should not be there and lacks some that would help.
- **12. The 3 dots next to inventory items (Market and Gear).** Question from
  the review: do they do anything today? Check first; remove or give them a job.

## Larger

- **5. Market cash and specialised shops.** The market needs a finite purse so
  items cannot be sold forever. That implies splitting the single general market
  into shops (forge, tanner, market, like the library already is) with different
  stock, which creates arbitrage.
- **6. Bank currency exchange.** 100 copper to 1 gold; relevant now that coins
  weigh (200 coins = 1 kg).
- **2. Found-the-guild screen.** Scope is vague; define what is wrong first.
- **3. Use for the characters' starting items.**
- **4. Hobgoblin and Dwarf share the same racial ability — should they?** A
  design decision before any code.

## Big / structural

- **1. Auto battler with priority programming** (Siralim Ultimate style). Its own
  arc and branch: UI, AI and tests.
- **8. `visible_pack` index refactor.** `[i for i, _ in visible_pack(m)]` is
  repeated in Market and Stash. The panel could take the real index in the pack
  tuple so screens stop translating. It touches `loadout_panel`, which Gear and
  Group also use; about 20 minutes.

## Loose ends from finished work

- `recruit.pitch_block_reason` has no production caller (tests only). The
  taverna's `_eligible` does not check `guild.can_absorb`, which that function
  does — either a forgotten rule (recruiting into a full group) or dead logic.
- Arrow-key chords add 70 ms of input latency (`battle_screen.CHORD_MS`).
- Prison selection went from 2 clicks to 3 steps; Esc leaves the prison.
