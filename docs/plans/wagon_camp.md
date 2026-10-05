# Wagon, speed-based travel, camp cooking and jerky

Agreed design (2026-10-05). **Nothing here is implemented yet.** It exists to
fix one problem: a Claim garrison needs 10 days of food, and a group of 6–8
cannot carry it.

## Design

### Wagon and draft animals
- The wagon belongs to a **Group**, not the guild. Someone buys it.
- It is a card in Manage Gear, built like a character: HP, speed, inventory,
  carry capacity. Its **equipment slot holds the draft animal**.
- The draft animal is its own card. It can be dragged from the left tab into the
  wagon's slot, and the two stay linked.
- **Carry limit** = min(wagon capacity, sum of the draft animals' capacity).
  The wagon and its load both weigh.
- Draft animals **must eat** too.
- **Wagon contents never go into combat.** Group members eat from it as if it
  were a member with `share_food` on.
- **Loss:** if every member of the group dies, the wagon is lost with them. If
  anyone survives the fight (including by fleeing), the wagon is still there.

### Travel speed
- Today `world.route` sums fixed hours per edge, independent of the group.
- Change: each edge gets a **distance**, in units of what a person walking
  covers. Time = distance / group speed.
- **Group speed = the slowest member.** If everyone rides the wagon, it is the
  draft animals' speed.

### Camp cooking
- Cooking is a craft activity, like forge, writing and potions: ingredients plus
  time.
- **At the house:** buy an oven from the Bankers to unlock it.
- **At the Claim:** a "make campfire" button. Needs firewood in the pack; takes
  1 hour and a test. Unlocks cooking there.
- **Jerky** = Meat + Salt, lifespan **20 days** (Meat 2, Potato 7).
- **Salt** is sold in the market only; no loot, no gathering.

## Build order

1. **Salt, jerky and the cooking activity** (house oven, Claim campfire). This
   alone makes the 10-day garrison possible, without a wagon.
   **Status: implemented, uncommitted at the time of writing.** What was built:
   - Items `Salt` (0.5 kg, 3 cp, market stock) and `Jerky` (0.5 kg, 8 cp, 20 days).
   - `CraftingRecipe.yield_qty`; Jerky = Meat + Meat + Salt -> 2 Jerky at the new
     `COOKING` station. `Unit.known_recipes` adds `items.COMMON_RECIPES`, so
     nobody needs to learn it.
   - House: `CityProperty.oven`, bought for `economy.OVEN_PRICE` (150 cp) on the
     house screen, which then offers COOK; lost with the house.
   - Claim: `Guild.wilds_claim_campfire`. After SWEPT, BUILD A CAMPFIRE burns 1
     **Lumber** (reused as firewood, no new item), 1 h, WIS check DC 8 by the best
     member; the fuel is spent even on a failure. Then COOK appears. Stays lit.
   - Both kitchens open `CraftingScreen(station="cooking")` and return to where
     they were opened from. Saves carry `property_city_oven` and
     `wilds_claim_campfire`.
2. **Wagon with capacity only:** group-owned card, draft-animal slot, carry
   limit, eating from it, loss rule. No effect on travel time.
3. **Speed-based travel.** Last, because it rebalances every route and the
   economy (re-run `scripts/economy_sim.py`).

## Open questions
- Does the draft animal's food come from the wagon's cargo, or does it graze?
- Wagon and animal prices, carry capacities, weights, HP and speeds.
- Is wagon-riding an explicit toggle per member, or implied by "everyone fits"?
- How does the wagon show on the map and in saves (persistence shape)?

## Notes for implementation
- Food ageing already exists: `ItemInstance.days_old` vs `ItemDef.lifespan`.
- Garrison jobs live in `economy.GARRISON_JOBS`; cooking at the Claim could be
  a job there or a stage of the Claim screen.
- A new craft activity needs the end-to-end set: logic, UI, AI where it applies,
  tests (`AGENTS.md`, Feature Implementation Rules), and a tutorial card entry.
