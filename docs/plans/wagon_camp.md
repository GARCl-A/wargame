# Wagon, animals and travel — what is left

The original problem: a Claim garrison needs 10 days of food and a group of 6–8
cannot carry that much. Cooking and jerky (house oven, Claim campfire), the
group's animals and wagon, tack, The Farm and the storage rebalance are built;
read the code for how they work (`animals.py`, `wagon.py`, `stables_screen.py`,
`Group.animals` / `Group.wagon`; tests in `test_wagon.py`, `test_stables.py`,
`test_cooking.py`). This file tracks what is not done.

**Scale premise.** The game is meant to get big (guilds with many groups, many
animals, several wagons). These subsystems must be shaped for that now, not
patched later. Prefer the general model even when the first version only
exercises a small part of it.

## Design constraints to keep

- **Storage must trade capacity for something.** Personal pack: free, goes to
  combat. Chest: 100 cp, 30 kg, static and safe. House: 1000 cp + tax, 200 kg,
  static and safe, has the oven. Wagon: mobile, lost with the group, needs animals
  that eat, and (below) slows the trip. Pack animals sit between pack and wagon.
  Revisit the numbers once travel speed exists.
- **Tack decides an animal's role** (Pack Saddle carries, Harness pulls, a riding
  saddle later). The wagon is a box; transport (capacity, speed) is derived.

## Decided, not built

### Travel time from distance and speed
- Edges stop being hours and become **distance**. One unit = what a person
  walking at 9 m covers in an hour, so today's numbers carry over unchanged.
- The group has a **speed**; time = distance × 9 / speed (in meters per move).
- **Group speed = the slowest of everyone travelling**, using each character's
  real combat speed (`Unit.speed`: race, armor drag, load, hunger). Animals that
  travel with the group are counted too, harnessed or not. No exceptions: a
  group of armored dwarves is slow, and the answer is a mount or a wagon.
- Anyone riding in a wagon is not walking, so their own speed drops out; the
  wagon moves at its draft animals' speed (`Wagon.speed`, the slowest harnessed
  animal).
- Re-run `scripts/economy_sim.py` and the balance sim afterwards: every route and
  wage-per-hour changes.

### Passengers, by weight
- A wagon seats people by **weight, not seat count**. A passenger occupies cargo
  room equal to their **body weight plus everything they carry**. So the wagon's
  cargo room, its passengers and its draft limit are one budget.
- Needs a body weight per character, derived from size (a kg per size class).
- Riding is automatic when everyone fits? Not decided; see open questions.

### Animals and wagons are a kind of creature, recruited
- A wagon and an animal are **a kind of unit**, like a character: a sheet with HP,
  speed, carry, pack, equipment slots. Characters are one kind; animals another;
  wagons another. Buying one is closer to **recruiting** it than to buying an
  item, and the same goes for a donkey, an ox, a horse.
- This is the shared abstraction that splitting, merging, speed, HP, feeding and
  the gear screen should all sit on, instead of `Wagon` and `Animal` each
  duck-typing a pack owner.

### Herd capacity
- A group can only control so many animals, like it can only lead so many people
  (`Group.capacity`, Charisma). Add a **herd capacity**, tied to **Wisdom**. It
  replaces the flat `animals.MAX_ANIMALS` (4). Formula and what each animal costs
  against it (flat, or by size) still to decide.

### Several wagons per group
- A group may have **many wagons** and many animals; no cap other than herd
  capacity (and whatever limits wagons).
- The **Harness links to a specific wagon**: each harnessed animal records which
  wagon it pulls, and `Wagon.draft` counts only its own animals. Unassigned
  harnessed animals pull nothing. The gear screen needs a way to assign (drag the
  animal onto the wagon), and recruiting an animal at the Farm can assign it.
- `Group.wagon` becomes `Group.wagons`; saves must keep loading the single-wagon
  shape.

### Split and merge
- **Merging two groups** that both have wagons just gives the result two wagons.
  The only limit is herd capacity, which also replaces the "no more than 4
  animals" refusal.
- **Splitting** lets the wagon and the animals go to the new group, picked like
  the members are. The default stays "with the original group".

### Parking wagons
- A wagon cannot be left on the road (the Old Road). It **can stay at a node where
  a group could garrison**: the house, the Claim. Needs: what a parked wagon does
  there (holds cargo, feeds the garrison), whether it can stay with nobody beside
  it, and what a raid on the Claim does to it.

### HP and stats
- Wagon and animals **get real stats now**, estimated from the creature sheets we
  already have, even though they do not fight yet. Wagon stats are the harder
  estimate.
- **The wagon cannot die: it breaks**, the same rule as the Automaton's Inorganic
  Body (0 HP = broken, no death clock, repaired with Stabilize, INT vs DC 15).
  A broken wagon stops pulling and waits for repair.

### Mounts (separate arc, keep in mind)
- Riding is a later arc, done after this one. A riding saddle enters
  `animals.TACK` then; the rider and animal pair goes into combat. Nothing is
  built, but the creature abstraction above should not make it harder.

## Suggested build order

1. **Creature abstraction** (animal and wagon as a kind of unit, stats, recruiting
   at the Farm): everything else sits on it.
2. **Several wagons**: `Group.wagons`, Harness link, split and merge rules.
3. **Herd capacity** (Wisdom) replacing `MAX_ANIMALS`.
4. **Travel from distance and speed**, with animals counted in the slowest.
5. **Passengers by weight** (needs body weight by size).
6. **Parking wagons** at the house and Claim, and wagon breaking and repair.

## Open questions

- Body weight per size class (Small / Medium / Large, kg), for passengers.
- Does a passenger's pack stay on them (counting against the wagon's room), or
  does it move into the wagon? Can they eat and fight from there?
- Is riding automatic when everyone fits, or a choice per trip? What if only some
  fit?
- Herd capacity: base value, the Wisdom term, whose Wisdom (the group leader's),
  and whether every animal weighs the same against it.
- The unit abstraction: shared base class or protocol? Do wagons and animals live
  in `Group.members` or in their own lists? What it means for leadership, recruit
  capacity, cohesion, fame slots and which of them enter a battle.
- Recruiting animals and wagons: do they get names and levels? Does the Farm get a
  candidate pool like the tavern, or keep a fixed shelf with prices?
- Where the HP, AC and speed come from (which beast sheets), and for the wagon.
- Breaking and repair: who repairs a wagon, with what, and does a broken wagon
  still hold cargo and passengers?
- A parked wagon with nobody beside it: who guards it, and is it part of a raid?

## Loose ends

- **The Farm** only holds the stables for now; to be reworked.
- **Campfire** never goes out and uses a single Lumber; cooking has no upkeep.
  Revisit if garrison cooking is too cheap or too fiddly (80 meals for 8 people
  over 10 days is about 40 batches).
- **Distribute load** ignores animals and the wagon.
- **A group's order that leaves a wagon behind** is not modelled; wagons always
  travel with the group today.
