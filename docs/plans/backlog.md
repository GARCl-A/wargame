# Backlog — everything still open

The one place for open work. It folds the playtest review (2026-10-05), the wagon and
camp to-do list and the later playtest notes. What is already built is in the code, its
tests and the git log; the long-range AI plan is
[campaign_ai_roadmap.md](campaign_ai_roadmap.md).

Ease and impact are estimates, not checked against the code. When an item is done, delete
it here and, if it changed a design premise, record it in `AGENTS.md` or the doc that owns it.

## Medium

- **Medic / rest until full.** Camps of 8 h are tedious. Either a medic NPC that speeds
  healing, or a "rest until full" button that costs X days and X food, shown up front. Rest
  healing is deterministic, so the cost is computable.
- **Combat info modal.** Hide part of it by default and rework it: it carries information
  that should not be there and lacks some that would help. Define what goes in and out first.
- **Split stack in the Market and Stash menus.** The ⋮ menu moves a whole stack there; a
  partial move (30 of 200 coins) still means splitting on the Gear or Group screen first.
  `SplitStackMixin` already does it for those two; the Market uses `sel`, not `selected`.

## Larger

- **Market cash and specialised shops.** The market needs a finite purse so items cannot be
  sold forever. That implies splitting the single general market into shops (forge, tanner,
  market, like the library already is) with different stock, which creates arbitrage.
- **Bank currency exchange.** 100 copper to 1 gold; relevant now that coins weigh (200 coins
  = 1 kg). Coins are items and move like any other, so this is a stack-for-stack swap at the
  bank, plus a Gold Coin item.
- **Found-the-guild screen.** Scope is vague; define what is wrong first.
- **Use for the characters' starting items.**

## Big / structural

- **Auto battler with priority programming** (Siralim Ultimate style). Its own arc and
  branch: UI, AI and tests.

## Wagons, animals and camp

Nothing here blocks anything; each item waits for a reason to build it. Constraints to keep
while building them:

- The game is meant to get big (many groups, animals and wagons): shape these systems for
  that now and prefer the general model over a patch for the small case.
- Storage trades capacity for something: pack is free and goes to combat; chest and house
  are static and safe; a wagon is mobile, lost with the group, needs animals that eat and
  sets the trip's pace; pack animals sit between pack and wagon.
- Tack decides an animal's role (Pack Saddle carries, Harness pulls, a riding saddle later);
  the wagon is a box and transport is derived.
- Wagons never enter a battle map: when combat starts, passengers get off and fight.

- **Broken wagons.** A wagon cannot die: at 0 HP it breaks (the Automaton's Inorganic Body
  rule). It stays in the group, does not move, adds nothing to speed and carries no cargo.
  Repaired like an Automaton (Stabilize, INT vs DC 15) out of combat, costing Lumber and
  crafting time, or abandoned (travelling with it broken is abandoning it); cargo can be
  unloaded into packs first. Needs something that damages wagons first: wear in travel, or a
  wagon on a battle map.
- **Garrison leader and size.** Who leads a garrison and how large it may be (the leader
  decides the herd and the group size there).
- **Garage tuning.** The house garage's flat 690 cp per tier and the Claim garage's flight
  chance stay as they are until play shows what they should do.
- **Price retune from play.** The Horse's 480 cp and the mobility premium are the first
  suspects.
- **Wild Donkey / Ox / Horse.** Not rolled anywhere; their racial modifiers (+2 / +3 / +5)
  only matter if one ever is (a Horse at 3d6 +5 could reach 23, so revisit then).
- **Riding and mounts** (separate arc). A riding saddle enters `animals.TACK`; the rider and
  animal pair goes into combat. The creature abstraction should not make it harder.

## Loose ends from finished work

- Gear, Group, Market and Stash share the ⋮ menu through `packbox.ItemMenuMixin`; a fifth
  screen with pack rows should use it rather than grow its own popup.
