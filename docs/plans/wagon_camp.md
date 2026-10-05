# Wagon, animals and travel — what is left

The original problem: a Claim garrison needs 10 days of food and a group of 6–8
cannot carry that much. Cooking and jerky (house oven, Claim campfire), the
group's animals and wagon, tack, The Farm and the storage rebalance are built;
read the code for how they work (`animals.py`, `wagon.py`, `stables_screen.py`,
`Group.animals` / `Group.wagon`; tests in `test_wagon.py`, `test_stables.py`,
`test_cooking.py`). This file only tracks what is not done.

## Design constraints to keep

- **Animal and wagon stay separate.** The animal is its own entity (it may be
  ridden and go to combat later); tack decides its role; the wagon is just a box.
  Transport (capacity, speed) is derived, never stored.
- **Storage must trade capacity for something.** Personal pack: free, goes to
  combat. Chest: 100 cp, 30 kg, static and safe. House: 1000 cp + tax, 200 kg,
  static and safe, has the oven. Wagon: mobile but lost with the group, needs
  animals that eat, and (below) slows the trip. Pack animals sit between pack
  and wagon. Revisit these numbers once travel speed exists.

## Next: speed-based travel (step 3)

- Edges get a **distance** (unit = what one person walking covers); time =
  distance / group speed. Today `world.route` sums fixed hours per edge,
  independent of the group.
- **Group speed = the slowest member.** An animal pulling a wagon does not make
  the walkers faster; if everyone rides the wagon, the draft animals' speed is
  the group's speed (`Wagon.speed` already gives the slowest harnessed animal).
- This is the real cost of a wagon (the Ox moves 6 m, a person 9 m), so it
  rebalances every route and the economy: re-run `scripts/economy_sim.py` and
  the balance sim afterwards.
- Open: can the wagon carry passengers? How many, and do they stop being
  members of the "walking" speed calculation?
- Open: do pack animals (Pack Saddle) set a speed floor for the group too, or
  only draft animals? Today nothing uses animal speed.

## Open design: more than one wagon

Today a group has **at most one wagon**, so the Harness needs no target: every
harnessed animal (up to `HITCH_SLOTS`) pulls the one wagon. The stables only
offer to buy a wagon when the group has none.

To allow several, in this order:
1. `Group.wagons` instead of `Group.wagon`; keep the single-wagon API working
   for saves.
2. A harnessed animal records **which wagon it pulls** (a reference by wagon id),
   and `Wagon.draft` counts only the animals assigned to it. Unassigned
   harnessed animals pull nothing.
3. UI: the gear screen needs a way to assign an animal to a wagon (drag the
   animal onto the wagon column, or a picker on the animal's column); the
   stables assign the animal at purchase.
4. A cap on wagons per group, and what a convoy does to group speed (slowest
   draft team?) and to the animal limit (`animals.MAX_ANIMALS`, now 4).

## Open design: merging and splitting groups with animals / wagons

- **Merge two groups that both have a wagon** is refused today
  (`Guild.merge_groups`). Needs a rule once multiple wagons exist: keep both,
  or ask which one comes along and put the other one's cargo somewhere.
- **Merge that would exceed the animal limit** is refused, with no way to choose
  which animals stay behind.
- **Split**: the wagon and all animals stay with the original group. There is no
  way to hand the wagon or some animals to the new group. Decide whether split
  should let the player pick, and what happens to a wagon left with a group that
  cannot pull it.
- **A wagon or animal left behind** (group leaves a node, order interrupted)
  is not modelled: they always travel with the group.

## Later

- **Riding saddle and mounts.** Add `Riding Saddle` to `animals.TACK` (role
  "mount") only when a mounted unit exists: how a rider and animal are paired,
  that the pair goes into combat, speed while mounted, the animal's HP and
  stats in a fight. No item exists yet on purpose.
- **Animal cards.** Animals are columns in the gear screen with a tack slot; the
  idea of dragging an animal card onto a wagon's slot depends on the multi-wagon
  link above.
- **Wagon and animal HP** are stored but unused: road ambushes, damage, healing
  or resting animals, what a fled combat does to a wagon.
- **The Farm** only holds the stables for now; the user plans to rework it.
- **Campfire** never goes out and uses a single Lumber; cooking has no upkeep.
  Revisit if garrison cooking turns out too cheap or too fiddly (80 meals for 8
  people over 10 days is about 40 batches).
- **Distribute load** ignores animals and the wagon.
