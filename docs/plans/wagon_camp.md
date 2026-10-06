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
- Saves: `SAVE_VERSION` 19, old `wagon` / `animals` keys and unhitched saves still load.

**Scale premise.** The game is meant to get big (guilds with many groups, many
animals, several wagons). These subsystems must be shaped for that now, not
patched later. Prefer the general model even when the first version only
exercises a small part of it.

## Design constraints to keep

- **Storage must trade capacity for something.** Personal pack: free, goes to
  combat. Chest: static and safe. House: static and safe, has the oven. Wagon:
  mobile, lost with the group, needs animals that eat, and sets the trip's pace.
  Pack animals sit between pack and wagon. Travel speed exists now, so revisit the numbers.
- **Tack decides an animal's role** (Pack Saddle carries, Harness pulls, a riding
  saddle later). The wagon is a box; transport (capacity, speed) is derived.
- Animals do not fight yet, but they have full creature sheets. **Wagons never enter a
  battle map**: when combat starts, passengers get off and fight like anyone else.

## Still to build

### 4. Parking, breaking and repair
- A wagon is never left in the open (the Old Road). It **stays only where a group
  could garrison**: the house, the Claim.
- With a garrison in a safe place it is safe. With **nobody to defend it** in a
  dangerous place it is an inanimate object: it **loses** any fight that comes. The
  wagon is lost and **everything inside becomes the enemy's loot**, the same as a
  group wiped out in a fight: that loot is gone.
- **The wagon cannot die: it breaks**, the same rule as the Automaton's Inorganic
  Body (0 HP = broken, no death clock). A broken wagon **stays in the group**: it
  does not move, adds nothing to speed and cannot carry cargo. It is repaired like
  an Automaton (Stabilize, INT vs DC 15) but outside of combat.
- **A broken wagon leaves exactly two options:** stop and repair it, or abandon it.
  Travelling with it broken *is* abandoning it, so there is no third way. Before
  abandoning one, its cargo can still be unloaded into packs.
- **An order that leaves a wagon behind** (a hunt, a fight, a garrison elsewhere) is not
  modelled: wagons always travel with the group today. This step decides it: the wagon is
  parked (only where it may stay) or it goes along; parking is what makes leaving it legal.

### 5. Camp and the Farm
- **Campfire** never goes out and uses a single Lumber; cooking has no upkeep. Revisit if
  garrison cooking is too cheap or too fiddly (80 meals for 8 people over 10 days is about
  40 batches). Do it once wagons carry the food, so the numbers are real.
- **The Farm** only holds the stables for now; rework it as the animals and wagons hub
  once parking exists (a wagon waits there too).

### Prices and capacities
The accepted placeholder table (units of 30 kg), all applied; retune from play feel, the
Horse's 480 cp and the mobility premium are the first suspects. Donkey 180, Ox 300, Horse 480,
Cart 150, Carriage 600, Chest 90 cp / 30 kg, House 1440 cp / 600 kg / tax 30 per week, Pack
Saddle 60, Harness 30.

Everything is priced at about 3 cp per kg over 12 weeks (house bare = 6 × 80 kg people + 60
hides = 600 kg; the chest must cost less than the tanner's 200 cp reward for 15 hides). A cart
clears the Shortbow + Quiver (345 cp): Cart 150 + Donkey 180 + Harness 30 = 360. `economy_sim.py`
gives the same report before and after (it never buys these): early squads start with about 27 cp,
so a cart is a mid-game purchase and a house a late one.

### Later: wild animals and mounts (separate arc, keep in mind)
- **Wild Donkey / Ox / Horse** are not rolled anywhere; their racial modifiers (+2 / +3 /
  +5) only matter if one ever is (a Horse at 3d6 +5 could reach 23, so revisit then).
- Riding is a later arc, done after this one. A riding saddle enters `animals.TACK`
  then; the rider and animal pair goes into combat. Nothing is built, but the creature
  abstraction should not make it harder.
