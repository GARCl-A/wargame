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
  button; dropping on a full wagon swaps); cargo room = min(box, what its animals draw). Merge gives both wagons; `Guild.split_group(...,
  wagons=, herd=)` hands wagons and animals over (the map's split card lists them).
- Herd capacity: `Group.herd_capacity` = `HERD_BASE` 3 + the leader's Wisdom modifier;
  gates buying, merging and splitting; an overgrown herd gets a 7-day notice
  (`cohesion._herds`) before an untacked animal strays.
- Saves: `SAVE_VERSION` 19, old `wagon` / `animals` keys and unhitched saves still load.

**Scale premise.** The game is meant to get big (guilds with many groups, many
animals, several wagons). These subsystems must be shaped for that now, not
patched later. Prefer the general model even when the first version only
exercises a small part of it.

## Design constraints to keep

- **Storage must trade capacity for something.** Personal pack: free, goes to
  combat. Chest: static and safe. House: static and safe, has the oven. Wagon:
  mobile, lost with the group, needs animals that eat, and (below) slows the trip.
  Pack animals sit between pack and wagon. Revisit the numbers once travel speed exists.
- **Tack decides an animal's role** (Pack Saddle carries, Harness pulls, a riding
  saddle later). The wagon is a box; transport (capacity, speed) is derived.
- Animals do not fight yet, but they have full creature sheets. **Wagons never enter a
  battle map**: when combat starts, passengers get off and fight like anyone else.

## Still to build

### 3. Travel time from distance and speed
- Edges stop being hours and become **distance**. One unit = what a person
  walking at 9 m covers in an hour, so today's numbers carry over unchanged.
- The group has a **speed**; time = distance × 9 / speed (in meters per move).
- **Group speed = the slowest of everyone travelling**, using each character's
  real combat speed (`Unit.speed`: race, armor drag, load, hunger). Animals that
  travel with the group are counted too, harnessed or not. No exceptions: a
  group of armored dwarves is slow, and the answer is a mount or a wagon.
- Anyone riding in a wagon is not walking, so their own speed drops out; the
  wagon moves at its draft animals' speed (`Wagon.speed`, the slowest hitched animal).
- Slice it: **3a** `Group.speed` only (slowest of members and animals), shown on the
  group screen, no route or clock change; **3b** edges become distance, travel time uses
  `Group.speed`, re-run `scripts/economy_sim.py` and the balance sim (every route and
  wage-per-hour changes).

### 4. Passengers, by weight
- A wagon seats people by **weight, not seat count**. A passenger is cargo: the
  wagon carries the person **and everything they carry**. The pack stays on the
  passenger (it is still theirs and they can still eat from it); the wagon's cargo
  room, its passengers and its draft limit are one budget.
- **Boarding is automatic when everyone fits.** When not everyone fits, it loads
  the group from the slowest to the fastest until the weight limit is reached;
  whoever is left walks. The group's speed is then the slowest of the walkers and
  the draft animals (the passengers' own speed drops out).
- **Body weight and the typical pack scale with size**, multiplied together, from a
  Medium at 60 kg body + 20 kg pack:

  | Size | Body | Pack | Person + gear |
  |---|---|---|---|
  | Tiny | 15 | 5 | 20 |
  | Small | 30 | 10 | 40 |
  | Medium | 60 | 20 | **80** |
  | Large | 120 | 40 | 160 |
  | Huge | 240 | 80 | 320 |

  Needs a `kg` per size next to `data.SIZES`. Note `SIZES["carry"]` today does not match
  (Small carries as a Medium, 1.0); the pack column is only the sizing heuristic for
  vehicles, not a carry rule.

### 5. Parking, breaking and repair
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

### Prices and capacities not applied yet
The accepted placeholder table (units of 30 kg; retune from play feel, the Horse's 480 cp
and the mobility premium are the first suspects). Applied: Donkey 180, Ox 300, Horse 480,
Cart 150, Carriage 600. **Still the old numbers:**

| Item | Today | Target |
|---|---|---|
| Chest | 100 cp, 30 kg | **90 cp**, 30 kg |
| House | 1000 cp, 200 kg, tax 40/wk | **1440 cp, 600 kg**, tax 30/wk |
| Pack Saddle | 40 cp | **60 cp** (Harness is already 30) |

How the targets are derived: the chest is anchored on the tanner's 200 cp reward (15 hides
= 30 kg must cost less); everything is priced at about 3 cp per kg over 12 weeks (house
bare = 6 × 80 kg people + 60 hides = 600 kg). A cart must clear the Shortbow + Quiver
(345 cp): Cart 150 + Donkey 180 + Harness 30 = 360. Pack Saddle 60 keeps a pack animal
well above the chest's cost per kg. After applying, **re-run `scripts/economy_sim.py`**:
early squads start with about 27 cp, so a cart is a mid-game purchase and a house a late
one. The house should out-hold the biggest carriage (6 people + gear) and cost more than
1000 cp.

### Mounts (separate arc, keep in mind)
- Riding is a later arc, done after this one. A riding saddle enters `animals.TACK`
  then; the rider and animal pair goes into combat. Nothing is built, but the creature
  abstraction should not make it harder.

## Not built (loose ends)

- **The Farm** only holds the stables for now; to be reworked.
- **Campfire** never goes out and uses a single Lumber; cooking has no upkeep.
  Revisit if garrison cooking is too cheap or too fiddly (80 meals for 8 people
  over 10 days is about 40 batches).
- **Distribute load** ignores animals and the wagons.
- **A group's order that leaves a wagon behind** is not modelled; wagons always
  travel with the group today.
- A herd also goes over capacity when the leader changes (swap, death), not only on a
  merge.
- **Wild Donkey / Ox / Horse** are not rolled anywhere; their racial modifiers (+2 / +3 /
  +5) only matter if one ever is (a Horse at 3d6 +5 could reach 23, so revisit then).
