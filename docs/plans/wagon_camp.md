# Wagons, animals and camp — to do

The original problem (a Claim garrison needs 10 days of food and a group of 6–8 cannot carry
that much) is solved: everything under **Built** is done. Only the **To do** list at the end is open.
Read the code for how it works; tests in `test_wagon.py`, `test_stables.py`, `test_garage.py`,
`test_claim_garage.py`, `test_wagon_watch.py`, `test_cooking.py`, `test_crafting.py`.

## Built

- Cooking and jerky (house oven, bought once; Claim campfire). Jerky: 2 Meat + Salt -> 2 Jerky, 20 days.
  A cooking shift is a batch: it rolls once an hour, starts the next batch from the same pack with the
  leftover progress, and ends early when the materials run out (`Guild.crafting_shift`); the clock and
  the work XP count only the hours worked. The campfire costs one Lumber, one hour and a WIS check to
  light, burns free while a garrison stands at the claim and goes out in the daily sweep the day nobody
  does (`_campfire_tick`). The Farm is not the player's: it only sells animals, wagons and tack.
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
- Parking (4): a wagon is with the group, in a garage or left outside; wagons never enter a battle map.
  - The house garage (`holdings.Garage` on `CityProperty.garage`, `garage_screen.py`, bought by the bay at
    `economy.GARAGE_PRICE` 690 cp, flat): one wagon and one animal per tier; `Guild.park_wagon` /
    `park_animal` / `take_wagon` / `take_animal`. The cargo stays in the wagon, parked animals eat
    daily from the house stash and the parked wagons' cargo (`animals.feed_herd`) and do not count
    against `herd_capacity`; losing the house loses the garage.
  - The Claim garage (`Guild.claim_garage`, `guild_claim.py`): open from the day the garrison opens
    (SUSTAINING) with no limit. A garrisoned claim is safe and a raid is a normal fight. With
    nobody garrisoned there is one silent roll a day, the flightiest animal's chance (a wagon with no
    animal never loses), and a hit clears everything. A seized claim keeps what was parked. Parked
    food feeds the garrison and animals eat from the garrison's food; parked food rots like any other.
  - A wagon left outside (`wagon_watch.py`, `watch_screen.py`): entering the Ancient Ruins or hunting
    in the Wilds opens the squad selector, where any one member minding the wagon makes it safe.
    Unguarded, one roll when the party is back out: `Node.wagon_risk` (Ruins 35%, Wilds 0) plus the
    flightiest animal's `flight` (Donkey 5%, Horse 10%, Ox 15%); a hit loses wagons, cargo and herd,
    with no notice. The Arena, Library, Prison and Market have no risk.
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

## Prices and capacities (applied)
Donkey 180, Ox 300, Horse 480, Cart 150, Carriage 600, Chest 90 cp / 30 kg, House 1440 cp /
600 kg / tax 30 per week, Pack Saddle 60, Harness 30: about 3 cp per kg over 12 weeks, units of
30 kg. A cart (with a Donkey and Harness, 360 cp) clears the Shortbow + Quiver (345 cp); early
squads start with about 27 cp, so a cart is a mid-game buy and a house a late one. Retune from
play feel; the Horse's 480 cp and the mobility premium are the first suspects.

## To do

Nothing here blocks anything; each item waits for a reason to build it.

- [ ] **Broken wagons.** A wagon cannot die: at 0 HP it breaks (the Automaton's Inorganic Body rule).
  It stays in the group, does not move, adds nothing to speed and carries no cargo. Repaired like an
  Automaton (Stabilize, INT vs DC 15) out of combat, costing Lumber and crafting time, or abandoned
  (travelling with it broken is abandoning it); cargo can be unloaded into packs first. Needs
  something that damages wagons first: wear in travel, or a wagon on a battle map.
- [ ] **Garrison leader and size.** Who leads a garrison and how large it may be (the leader decides
  the herd and the group size there).
- [ ] **Garage tuning.** The house garage's flat 690 cp per tier and the Claim garage's flight chance
  stay as they are until play shows what they should do.
- [ ] **Price retune from play.** The Horse's 480 cp and the mobility premium are the first suspects.
- [ ] **Wild Donkey / Ox / Horse.** Not rolled anywhere; their racial modifiers (+2 / +3 / +5) only
  matter if one ever is (a Horse at 3d6 +5 could reach 23, so revisit then).
- [ ] **Riding and mounts** (separate arc). A riding saddle enters `animals.TACK`; the rider and animal
  pair goes into combat. The creature abstraction should not make it harder.
