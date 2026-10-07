# Backlog — everything still open

The one place for open work. It folds the playtest review (2026-10-05), the wagon and
camp to-do list and the later playtest notes. What is already built is in the code, its
tests and the git log; the long-range AI plan is
[campaign_ai_roadmap.md](campaign_ai_roadmap.md).

Ease and impact are estimates, not checked against the code. When an item is done, delete
it here and, if it changed a design premise, record it in `AGENTS.md` or the doc that owns it.

## Medium

- **Medic, quick treatment (B1).** A tab in the Apothecary hub: the answer to rest healing
  being slow (1 HP per 8 h at CON mod 0). A hospital that treats with healing potions and
  antidotes at a discount, priced as the *expected* potions and antidotes needed to leave
  cured, at catalogue price x 0.7 (a constant in `economy.py`). It is a transaction: pick
  the patients from the party present, pay, and the clock advances for the whole group.
  - HP: always up to max, 1 h. Cost = `ceil((hp_max - hp) / 3.5)` Minor Healing Potions.
  - Sickness: 8 h, cost = one First Aid Kit charge (price / charges).
  - Poison: assume every Antidote save passes; stacks fall about 2 a day (natural + dose),
    so N stacks take 24 h x `ceil((N - 1) / 2)` (at least 1 h) and `ceil(N / 2)` doses.
    Only treatments up to 24 h belong here; longer ones are B2.
- **Medic, hospital stay (B2).** After B1. A treatment of 24 h or more admits the patient:
  they split off into a new Group on a new order kind (saved with the groups), locked like
  any group with an order. With no free group slot the whole group waits with them instead.
  On discharge the patient is a loose group and the player merges by hand.
- **Economy sim catch-up.** `scripts/economy_sim.py` models a trader against its own
  `Vendor` class, so it never sees what changed the economy in the game: the market's
  finite cash (`Guild.market_cash`: $100 to start, +$25/day up to $500), coins as items
  (`$`, gold, the bank exchange), the Medic and upkeep that now drain money (house tax,
  garrison, wagon wear, animal feed, group rest), and a squad pooling one market instead
  of a lone trader. First decide what question it answers (can one character earn a
  living? can a guild?), then have it drive the real `Guild`, market and daily upkeep
  instead of a parallel model. Until then a change to wages, purses or loot is checked by
  hand.
- **Combat info modal.** Hide part of it by default and rework it: it carries information
  that should not be there and lacks some that would help. Define what goes in and out first.

## Larger

- **Specialised shops.** Split the single general market into shops (forge, tanner, market,
  like the library already is) with different stock, which creates arbitrage. The market's
  finite cash is built (`Guild.market_cash`, keyed by node id), so each shop gets its own.
- **Found-the-guild screen.** Scope is vague; define what is wrong first.

## Starting items

Each occupation starts with one item (`data.OCCUPATIONS`) and about half the recruits got
one with no use at all. Rule: every occupation's item is useful and **unique to it**, as
an occupation is only a weapon and an item. Items that already work: Meat, Potato, Quiver,
1L Beer, 1sqm Hide, Iron Bar, Lumber, 1kg Coal, First Aid Kit, Lantern, Scroll, Dictionary.
The rest each need a mechanic, or a swap to an item that has one:

- **Duplicates to split.** Hunter and Mercenary both carry Rope; Merchant and Messenger
  both carry Sack; Jailer (Iron Shackles) and Slave (Chains) are the same thing. Each pair
  needs different items, simple or cheap is fine.
- **Goldsmith's Scales.** Swap for a jeweller's tool, to sit ready for jewellery crafting.
- **Crafting tools.** Crafting consumes everything today. Let a recipe also require a tool
  that is not consumed (a cart needs wood, nails and a saw). Gives Chisel, Scissors, Shovel,
  the Goldsmith's tool and the Hunter/Mercenary fix a job. Shapes the future wagon recipe.
- **Prisoners.** Non-lethal attacks that knock a unit out even in lethal zones, then
  capture it. Chains are what holds the captive. Needs the AI to know it too.
- **Claim construction: oven.** Built at the Claim with time and Stone Brick; like the
  campfire but always lit. First thing to build there, and the start of a general
  build-at-the-Claim system.
- **Animals in combat.** The Shepherd's Sheep only stands still on the board today.
  Controllable and AI-driven animals share the *Riding and mounts* arc below.
- **Inventory containers.** Decide whether the inventory should be split into containers
  at all. If yes, Sack gets its role; if not, Merchant and Messenger need other items.
- **Cloak.** Equipped in the armour slot, +1 to the guard test (`justice.guard_test`) for
  a character with crime. No effect on a clean record.
- **Map.** Finds treasures and secret zones. Waits for those systems.
- **Compass.** Avoids getting lost on very long trips through unknown paths. Waits for a
  getting-lost system.
- **Deck of Cards.** A card minigame at the tavern, among others. Its own arc.
- **Musical Instrument.** A "perform" work at the tavern, next to the lumber yard.
- **Holy Symbol.** Required, together with everything else, to start in faith magic.

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

- **Riding and mounts** (separate arc). A riding saddle enters `animals.TACK`; the rider and
  animal pair goes into combat. The creature abstraction should not make it harder.
