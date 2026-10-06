# Wagon, animals and travel — what is left

The original problem: a Claim garrison needs 10 days of food and a group of 6–8
cannot carry that much. Built so far (read the code for how it works; tests in
`test_wagon.py`, `test_stables.py`, `test_cooking.py`):

- Cooking and jerky (house oven, Claim campfire).
- Animals as creatures: `creature.Creature` base; Donkey / Ox / Horse are `data.BEASTS`
  rows (`data.LIVESTOCK`, outside `BEAST_POOL`) with fixed attributes, loads from Strength
  rounded to 30 kg, Beast of Burden on the Ox; kept in `Group.herd`, bought at the Farm
  (`stables_screen.py`), tack (Pack Saddle / Harness) decides the role.
- Wagons: `wagon.VEHICLES` (Cart 180 kg / 1 animal / 150 cp, Carriage 540 kg / 3 animals /
  600 cp), d8 hit die, several per group in `Group.wagons`. A Harness animal is hitched to
  one wagon (`Animal.hitch`, `Group.hitch` (`swap=True`) / `hitch_idle` / `next_hitch`;
  drag the animal's header onto the wagon's on the gear screen, or the stables' HITCH
  button; dropping on a full wagon swaps); budget = min(box, what its animals draw). Merge gives both wagons; `Guild.split_group(...,
  wagons=, herd=)` hands wagons and animals over (the map's split card lists them).
- Herd capacity: `Group.herd_capacity` = `HERD_BASE` 3 + the leader's Wisdom modifier;
  gates buying, merging and splitting; an overgrown herd gets a 7-day notice
  (`cohesion._herds`) before an untacked animal strays.
- Travel: `world.EDGES` are distances (one unit = an hour of a 9 m walker); a leg takes
  `world.hours(distance, Group.speed)`, `Group.speed` being the slowest member (combat speed,
  armor and load included) or animal, shown on the gear screen. The economy and balance sims
  never travel, so they were not affected.
- Load: `Group.distribute_load` fills the pack animals and the wagons too (those with room;
  coins stay on people). A herd over `herd_capacity` after a leader change (swap through
  `Guild.set_group_leader`, or death) starts its 7-day notice at once (`cohesion.herd_notices`).
- Passengers, by weight: `Group.boarding()` seats the members in the wagons, slowest first, each
  counting as `data.SIZES[size]["kg"]` plus everything they carry, against `Wagon.budget` (the box
  or what its animals draw) less the cargo already aboard; `Wagon.capacity` is what the passengers
  leave for cargo, so people and cargo share one budget. Whoever does not fit walks; riders drop
  out of `Group.speed`, the animals' pace stands in. The gear screen's wagon column says how many ride.
- The house garage (4a): `holdings.Garage` on `CityProperty.garage`, bought by the bay at
  `economy.GARAGE_PRICE` (690 cp, flat) from `garage_screen.py` (the GARAGE button on the house screen).
  `Guild.park_wagon` / `park_animal` / `take_wagon` / `take_animal`; the cargo stays in the wagon, parked
  animals eat daily from the house stash and the parked wagons' cargo (`animals.feed_herd`, shared with
  `Group.feed_animals`) and do not count against `herd_capacity`; losing the house loses the garage.
- The wagon left outside (4b): a group with a wagon entering the Ancient Ruins or hunting in the Wilds
  opens `watch_screen.WatchScreen` (the squad selector, with its tutorial card): click a member to leave
  them minding the wagon; they stay in the group, only the others delve or hunt. Unguarded, `app` rolls
  once when the party is back out (`wagon_watch.leave_outside`): `Node.wagon_risk` (Ruins
  `ROAD_AMBUSH_CHANCE`, Wilds 0) plus the flightiest animal's `flight` (`data.BEASTS`: Donkey 5%, Horse 10%,
  Ox 15%); a hit loses wagons, cargo and herd, with no notice. Guarded is always safe for now. Nothing new
  is persisted, so no save bump.
- Saves: `SAVE_VERSION` 21, old `wagon` / `animals` keys and unhitched saves still load.

**Scale premise.** The game is meant to get big (guilds with many groups, many
animals, several wagons). These subsystems must be shaped for that now, not
patched later. Prefer the general model even when the first version only
exercises a small part of it.

## Design constraints to keep

- **Storage must trade capacity for something.** Personal pack: free, goes to
  combat. Chest: static and safe. House: static and safe, has the oven. Wagon:
  mobile, lost with the group, needs animals that eat, and sets the trip's pace.
  Pack animals sit between pack and wagon.
- **Tack decides an animal's role** (Pack Saddle carries, Harness pulls, a riding
  saddle later). The wagon is a box; transport (capacity, speed) is derived.
- Animals do not fight yet, but they have full creature sheets. **Wagons never enter a
  battle map**: when combat starts, passengers get off and fight like anyone else.

## Still to build

### 4. Parking (the garage) and the wagon left outside
4a (the house garage), 4b (the wagon left outside) and 4c (the Claim garage) are built. The full design:

A wagon is in one of three states: **with the group** (travels, same risk as the group),
**in a garage** or **left outside**. Wagons never enter a battle map.

- **Garage** = stored *inside* a holding, like a garrisoned unit: safe, nothing to roll.
  - **House:** a garage is bought like the oven. The first tier holds **one wagon and one animal**;
    each upgrade adds one more of each. **690 cp per tier** (150 construction, the oven's price,
    plus 3 cp/kg for the 180 kg a Cart with an Ox opens); it is meant to be expensive. The cargo
    stays in the wagon: the garage does not add to the house's 600 kg.
  - **The Claim:** an *open* garage the moment its garrison opens (the 10 days to hold), with no
    limit on wagons or animals. Attacked with defenders: they fight normally. Attacked with
    nobody defending: the wagon is lost. A wagon may be parked there and the garrison emptied,
    but with nobody in it the wagon is alone: **one roll per day**, the flight chance of its
    most flighty animal, and a hit loses everything. The longer it sits alone the worse it gets.
    The wagon should only stay while someone is there.
  - A garaged wagon's food feeds the garrison (the original problem), and garaged animals eat
    from the **whole garage's store** (the house stash; the garrison's food), not only the wagon's.
  - Garaged animals do not count against `Group.herd_capacity`.
- **Left outside**: the group enters a dangerous place and the wagon waits in the node: the Ancient
  Ruins, and a hunt in the Wilds. (Arena, Library, Prison, Market: the wagon waits at the door,
  no risk.)
  - Going in opens the **squad selector**: who enters or hunts, who stays outside minding the
    wagon. **Any one member is a guard**, even a lone level-0. The first time it opens, a tutorial
    card says someone has to mind the wagon.
  - The selector shows the **X% chance of losing the wagon** if nobody stays.
  - **Unguarded**, one roll when the party comes back out: the node's random-encounter chance
    (the Ruins use the Old Road's 35%, `ROAD_AMBUSH_CHANCE`) plus the animal's flight chance
    (Donkey 5%, Horse 10%, Ox 15%). On a hit **everything is gone** (wagon, cargo, animals); the
    game does not say what happened, only that it is no longer there when the party returns.
    The Wilds are not `unsafe`, so a hunt carries only the animal's flight chance.
  - **Guarded**: exposed only to the node's own encounter chance; the Ruins have no random
    encounter for now, so a guarded wagon there is safe.
- The guards are **not split off**: they remain in the same group doing the same activity
  (the incursion, the hunt), only divided between those who go in and those who mind the wagon.
- A parked wagon belongs to its holding (the house garage, the Claim), not to a group: a wagon
  with nobody around has no group to belong to. Taking it out hands it to the group present.
- A broken wagon, repair and abandon are in *Later*: nothing damages a wagon yet.
- Left for later, on purpose: who leads a garrison and how large it may be (the leader decides
  the herd and the group size there); the garage's per-tier price stays flat at 690 cp until
  play shows what it should do; the flight chance is a per-species field in `data.BEASTS` (done in 4b).

Build order: 4a the house garage (done), 4b the guard
selector with its risk percentage and tutorial card (Ruins, Wilds hunt; done), 4c the Claim's open
garage with the daily roll (done: `Guild.claim_garage`, `guild_claim.py`; a seized claim takes what is parked;
parked food rots and feeds the garrison; a wagon with no animal has nothing to bolt, so it never rolls a hit;
the roll is silent like 4b's; `SAVE_VERSION` 21). Each ships with its screen, tests and a `SAVE_VERSION` bump.

### 5. Camp and the Farm
- **Campfire** never goes out and uses a single Lumber; cooking has no upkeep. Revisit if
  garrison cooking is too cheap or too fiddly (80 meals for 8 people over 10 days is about
  40 batches). Do it once wagons carry the food, so the numbers are real.
- **The Farm** only holds the stables for now; rework it as the animals and wagons hub
  once parking exists.

### Prices and capacities (applied)
Donkey 180, Ox 300, Horse 480, Cart 150, Carriage 600, Chest 90 cp / 30 kg, House 1440 cp /
600 kg / tax 30 per week, Pack Saddle 60, Harness 30: about 3 cp per kg over 12 weeks, units of
30 kg. A cart (with a Donkey and Harness, 360 cp) clears the Shortbow + Quiver (345 cp); early
squads start with about 27 cp, so a cart is a mid-game buy and a house a late one. Retune from
play feel; the Horse's 480 cp and the mobility premium are the first suspects.

### Later: broken wagons
- A wagon cannot die: at 0 HP it **breaks** (the Automaton's Inorganic Body rule). It stays in the
  group, does not move, adds nothing to speed and carries no cargo. It is repaired like an
  Automaton (Stabilize, INT vs DC 15) out of combat, costing Lumber and crafting time, or
  abandoned (travelling with it broken *is* abandoning it); cargo can be unloaded into packs first.
- Needs something that damages wagons: a wagon on a battle map or wear in travel. Not built.

### Later: wild animals and mounts (separate arc, keep in mind)
- **Wild Donkey / Ox / Horse** are not rolled anywhere; their racial modifiers (+2 / +3 /
  +5) only matter if one ever is (a Horse at 3d6 +5 could reach 23, so revisit then).
- Riding is a later arc, done after this one. A riding saddle enters `animals.TACK`
  then; the rider and animal pair goes into combat. Nothing is built, but the creature
  abstraction should not make it harder.
