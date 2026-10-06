# Wagon, animals and travel — what is left

The original problem: a Claim garrison needs 10 days of food and a group of 6–8
cannot carry that much. Cooking and jerky (house oven, Claim campfire), the
group's animals and wagon, tack, The Farm, the storage rebalance and herd capacity
(`Group.herd_capacity` = `HERD_BASE` 3 + the leader's Wisdom modifier; each animal
costs its species' `herd_weight`, 1 for now, minimum capacity 1; it gates buying at
the Farm and merging, and an overgrown herd gets a 7-day notice (`Group.herd_notice`,
`cohesion._herds`) before an untacked animal strays, leaving its tack and load with the
leader, one more every 7 days until it fits) are built;
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
- A wagon seats people by **weight, not seat count**. A passenger is cargo: the
  wagon carries the person **and everything they carry**. A character with a
  sword and ten meals is, to the wagon, one load of body weight + sword + meals.
  The pack stays on the passenger (it is still theirs and they can still eat
  from it); the wagon's cargo room, its passengers and its draft limit are one
  budget.
- **Boarding is automatic when everyone fits.** When not everyone fits, it loads
  the group from the slowest to the fastest until the weight limit is reached;
  whoever is left walks. The group's speed is then the slowest of the walkers and
  the draft animals (the passengers' own speed drops out).
- **Body weight and the typical pack scale with size**, multiplied together, from a
  Medium at 60 kg body + 20 kg pack. A person with gear:

  | Size | Body | Pack | Person + gear |
  |---|---|---|---|
  | Tiny | 15 | 5 | 20 |
  | Small | 30 | 10 | 40 |
  | Medium | 60 | 20 | **80** |
  | Large | 120 | 40 | 160 |
  | Huge | 240 | 80 | 320 |

  So a Small takes half the room of a Medium in the cart, a Large takes two. Needs a
  `kg` per size next to `data.SIZES`. Note `SIZES["carry"]` today does not match (Small
  carries as a Medium, 1.0); the pack column here is only the sizing heuristic for
  vehicles, not a carry rule.

### Animals and wagons are a kind of creature, bought straight into the group
- A wagon and an animal are **a kind of unit**, like a character: a sheet with HP,
  speed, carry, pack, equipment slots. Characters are one kind; animals another;
  wagons another. Buying one **adds it to the group**, it is not an item that goes
  to a pack. The Farm stays a plain shop: no candidate pool, no pitch roll.
- Shared abstraction for splitting, merging, speed, HP, feeding and the gear
  screen, instead of `Wagon` and `Animal` each duck-typing a pack owner.
- **Where they live:** not in `Group.members`. Animals go in their own list
  (`Group.herd`), wagons in `Group.wagons`. A wagon does not count for leadership;
  an animal counts only against herd capacity.

### Vehicle types
- **Every capacity is a multiple of 30 kg**, the unit of the chest (15 hides). It is
  the heuristic that keeps the numbers organised: capacities, and the prices that
  follow from them, are counted in units of 30.
- The first wagon is a **cart**: two wheels and one animal. Its job is to carry **two
  people with their packs** (2 x 80 = 160 kg, so 180 kg with a little room). A **Donkey
  cannot pull two people**: a cart behind a Donkey carries **90 kg** (one person and
  a pack), behind an Ox **180 kg**, behind a Horse **120 kg**. Most of what it costs
  is the animal.
- Above it come **carriages** for four to six people (6 x 80 = 480 kg, so **540 kg**):
  bigger, much more expensive, pulled by several animals (three Oxen draw 540 kg).
- So `Wagon` becomes a **type** (cart, carriage, later more), each with its own cargo
  box, hitch slots, price and hit dice. What an animal draws is a number that comes
  from its sheet (below): **the net load it can pull**, with the vehicle's own weight
  left out of the sum. Cargo room = min(the box, what the harnessed animals draw).
  Room is weight only: no separate cap on people.

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

### Combat
- **Wagons never enter a battle map** for now. When combat starts, passengers get
  off and fight like anyone else; the wagon is not part of the fight.

### Parking wagons
- A wagon is never left in the open (the Old Road). It **stays only where a group
  could garrison**: the house, the Claim.
- With a garrison in a safe place it is safe. With **nobody to defend it** in a
  dangerous place it is an inanimate object: it **loses** any fight that comes. The
  wagon is lost and **everything inside becomes the enemy's loot**, the same as a
  group wiped out in a fight: that loot is gone.

### HP and stats
- **The animal is an animal: a full creature sheet**, with attributes including
  Constitution, hit dice, speed, carry, size. Animals get **races**, the same way
  the wolf and the giant spider are races in the beast table of `data.py`: Donkey,
  Ox and Horse for now, nothing more. The `animals.SPECIES` table goes away in
  favour of those rows. They do not fight yet, but they have the numbers.
- **Strength sets what an animal can carry**, with the same formula characters use
  (`Unit._derive_carry`): a Large animal already doubles it. A character is 3d6 plus
  the racial modifier, and the largest racial STR modifier in the game today is +2
  (the wolf, the Orc, the Goliath). Animals stay in that range: **a +4 or +6 would
  give a Donkey STR 22 and an Ox STR 24 on a good roll**, which is absurd.
- **The wolf is the reference.** Wolf: Medium, STR +2, hit die d8, 10.5 m. It carries
  about 19 kg and staggers at 41. The **Donkey is the wolf scaled to Large with the same
  +2**: a Large animal doubles it, so it carries ~38 kg and draws ~82. After rounding
  to the nearest 30, that is exactly the target (back **30**, draw **90**) with **no
  multiplier**.
- **Two numbers per animal**, both rounded to the nearest 30 kg: the **back load**
  (`carry_normal`, with a Pack Saddle) and the **draw** (`carry_max`, what it pulls on a
  cart). The one multiplier is a passive racial ability, **Beast of Burden**, added to
  the carry formula next to the precedent `Ability.carry_size`. **Only the Ox has it.**
  The Donkey and the Horse have **no trait for now**.
- **Shop animals have fixed attributes, they are not rolled.** A unit rolls 3d6, but a
  cart's capacity cannot depend on a lucky Donkey (its draw would range from 34 to 130
  kg). A bought animal gets the race's fixed score, which is why the strength can sit
  above the game's usual +2 without being absurd:

  | Race | HD | Speed | Size | STR (fixed) | Trait | Back load | Draw (net) |
  |---|---|---|---|---|---|---|---|
  | Wolf (reference) | d8 | 10.5 m | Medium | 3d6 +2 | none | 19 | 41 |
  | Donkey | d8 | 6 m | Large | 13 | none | 38 -> **30** | 82 -> **90** |
  | Ox | d10 | 6 m | Large | 14 | Beast of Burden x2 | 92 -> **90** | 188 -> **180** |
  | Horse | d8 | 12 m | Large | 16 | none | 54 -> **60** | 106 -> **120** |

  The Ox is stronger than the Donkey by the trait, not by a huge STR. The Horse is the
  basic mount (a strong person in heavy armor, ~100 kg net), which without a trait needs
  STR 16 to draw 120; STR 15 would draw only 90. In the beast table the racial modifiers
  that give these scores on an average roll are Donkey +2, Ox +3, Horse +5; they only
  matter if a wild one is ever rolled (a Horse at 3d6 +5 could reach 23, so revisit then).
  Today's `SPECIES` speeds (Donkey 7.5) change to match; CON and the other attributes
  follow the wolf and spider rows.
- **The wagon has only a hit die**, no Constitution or other attributes. Every vehicle
  is an object and has a **d8**; that settles all wagon types.
- **The wagon cannot die: it breaks**, the same rule as the Automaton's Inorganic
  Body (0 HP = broken, no death clock). A broken wagon **stays in the group**: it
  does not move, adds nothing to speed and cannot carry cargo. It is repaired like
  an Automaton (Stabilize, INT vs DC 15) but outside of combat.
- **A broken wagon leaves exactly two options:** stop and repair it, or abandon it.
  Travelling with it broken *is* abandoning it, so there is no third way. Before abandoning one, its cargo can still be unloaded into packs.

### Mounts (separate arc, keep in mind)
- Riding is a later arc, done after this one. A riding saddle enters
  `animals.TACK` then; the rider and animal pair goes into combat. Nothing is
  built, but the creature abstraction above should not make it harder.

## Storage economics

How the prices are derived, anchored on the one thing the design fixes: the chest.

**The anchor.** The chest exists because the tanner asks for 15 hides and there is
nowhere to keep them. 15 hides (2 kg each) = **30 kg**, the smallest storage unit the
game cares about, and it has to cost **less than the tanner's reward (200 cp)**.
**Unit = 30 kg, and prices are multiples of 30 too.** The chest becomes **90 cp for
30 kg: 3 cp per kg**, paid once (today it is 100). Everything else is priced from
that, over a fixed horizon of 12 weeks:

    cost per kg = (purchase + upkeep per week x 12) / capacity

**The unit of people.** A Medium is 60 kg, a pack 20 kg: **80 kg per person**. The
cart, the carriage and the house are all counted in these, and rounded up to the next
multiple of 30.

**Sanity floors.** A cart must cost more than a bow and arrows (Shortbow 320 + Quiver
25 = 345 cp) and less than a plate armor (950 cp).

Accepted numbers (placeholders to retune from play; upkeep is one ration a day per animal, a
Potato at 3 cp = 21 cp a week; "units" are 30 kg):

| Storage | Capacity | Purchase | Upkeep/wk | cp per kg (12 wk) |
|---|---|---|---|---|
| Chest | 30 kg (1) | 90 | none | 3.0 |
| House, bare | **600 kg (20)** = 6 x 80 + 60 hides (120 kg) | **1440** | 30 tax | 3.0 |
| Cart + Donkey | 90 kg (3) | 150 cart + 180 Donkey + 30 harness = 360 | 21 | 6.8 |
| Cart + Ox | 180 kg (6) | 150 + 300 Ox + 30 = 480 | 21 | 4.1 |
| Cart + Horse | 120 kg (4) | 150 + 480 Horse + 30 = 660 | 21 | 7.6 |
| Carriage + 3 Oxen | 540 kg (18) | 600 + 900 + 90 = 1590 | 63 | 4.3 |

Reading it: the house is priced to the chest's band (1440 + 12 weeks of tax = 1800 for
600 kg, exactly 3 cp per kg), so it is worth buying exactly when you would otherwise
buy chests. The mobile options sit above that band because the animal's food never
stops. The Donkey cart (360 cp) clears the bow-and-arrow floor (345 cp) by a little.
Every purchase price above is a multiple of 30, the tax is 30, and the house moves from
20 to 600 kg.

**Does the chain hold together?** Yes, with one caveat about where each number comes from:
- Chest: set by the tanner's reward (90 cp < 200). House: derived from the chest's cost
  per kg. Both are chained.
- Cart: the 150 cp cart and the 30 cp Harness are chosen; the Donkey (180) is what makes
  the cart total clear the bow-and-arrow floor (360 >= 345). Animal price per kg of draw:
  Donkey 2.0 (180/90), Ox 1.7 (300/180), so a bigger animal is cheaper per kg, as it
  should be.
- **Horse: 480 = 2.0 cp per kg of draw x 120 kg x 2 for speed** (12 m, twice the
  others). It is the only price with a premium and it is justified by speed and by being
  the future mount, not by capacity. It is not strange, but nothing else in the chain
  checks it, so it is the first to move if mounts turn out cheaper or dearer than
  carts.
- The **mobility premium** (cost per kg over the chest's 3.0) is not chosen, it comes out:
  Ox cart 1.4x, carriage 1.4x, Donkey cart 2.3x, Horse cart 2.5x. If you prefer to pick it
  (for example "mobile storage costs 1.5x the chest"), the prices are backed out from it.
- **The pack saddle and the Donkey.** The Pack Saddle has to leave a Donkey-as-cargo-
  animal worth less than a chest. It carries 30 kg on its back, one chest unit, and costs
  180 + the saddle, with 252 cp of food over 12 weeks. At a **60 cp saddle** that is
  (180 + 60 + 252) / 30 = **16.4 cp per kg**, 5.5 times the chest's 3.0; its purchase
  alone (240 cp) is 2.7 chests. Any saddle price keeps it above the chest (even a free one
  gives 14.4), so the condition does not bind; **60 cp** is chosen because it is about
  five hides of leather (12 cp each) and the Harness's 30 cp is about two and a half.
  The Ox on its back (90 kg) is (300 + 60 + 252) / 90 = 6.8, 2.3 chests. The Donkey earns
  its keep pulling a cart, not as a pack animal.
- **Tack prices are multiples of 30:** Harness 30, **Pack Saddle 60** (it is 40 today).

These change numbers that exist today: chest 100 -> 90 cp, house 1000 -> 1440 cp and
200 -> 600 kg, tax 40 -> 30 a week. Re-run `scripts/economy_sim.py` once they land:
early squads start with about 27 cp, so a cart is a mid-game purchase and a house a
late one.

## Suggested build order

1. **Creature abstraction** (animal and wagon as a kind of unit, stats, bought into
   `Group.herd` / `Group.wagons`): everything else sits on it.
2. **Vehicle types and several wagons**: cart / carriage, `Group.wagons`, the Harness link, split and merge.
3. **Travel from distance and speed**, with animals counted in the slowest.
4. **Passengers by weight**, with the numbers above and body weight by size.
5. **Parking wagons** at the house and Claim, and wagon breaking and repair.

## Open questions

None for now. The prices and capacities in the storage table are **accepted as
placeholders**: they stay as they are and get retuned from playtest feel if the
balance turns out wrong (the Horse's 480 cp and the mobility premium are the
first suspects).

## Loose ends

- **Splitting animals** is not built: a split never takes animals, so today a herd only
  goes over capacity when the leader changes (swap, death).

- **The Farm** only holds the stables for now; to be reworked.
- **Campfire** never goes out and uses a single Lumber; cooking has no upkeep.
  Revisit if garrison cooking is too cheap or too fiddly (80 meals for 8 people
  over 10 days is about 40 batches).
- **Distribute load** ignores animals and the wagon.
- **A group's order that leaves a wagon behind** is not modelled; wagons always
  travel with the group today.
