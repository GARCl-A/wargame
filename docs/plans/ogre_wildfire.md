# The Ogre's Wildfire — plan

**Built 2026-10-15**, as planned below except where *As built* says otherwise. The rules now live in
RULES.md (*Secret nodes*, *Fire on the board*, *Push*, *Magic*); this file keeps the decisions.

**Designed 2026-10-15 (author interview).** The Nature Coven's third mission and one of
the game's endgame fights for now. It brings in one system the game will reuse: **ethereal nodes**,
nodes that appear for one event and then vanish.

Marked **(default)** = picked by me while writing the plan; the author may veto it.

## The story

An Ogre leads a goblin band into the Wilds to burn a clearing and build a fortress there. The
fortress is not the Wilds' problem. The problem is that they have no idea how to do it, so they
keep setting GIGANTIC wildfires. The Nature Coven asks the guild to stop the fires and deal with
the Ogre, by teaching or by force.

## 1. The mission

- A `MissionTemplate` on the Nature Grove's JOBS tab, 1 reputation through a deed like the other
  school missions. **Deadline: 14 days** from acceptance.
- **Done = the big focus is resolved** (the Ogre convinced or beaten, see 4). The small foci
  still left keep burning on their own clock; resolving them is the reward for doing it well.
- **Reward:** a level-1 Nature spell scroll (an `ItemType.SCROLL` with a `spell_id`): a **water spell
  that deals damage and pushes the target away** (author 2026-10-15): **1d6 + INT** damage, and a hit pushes the
  target **1 square**; range = the thrown range of the smallest thrown weapon, the Dagger:
  **6 squares**. It is built with this mission and counts as Nature's own level-1 spell for *Tier 1 spells per school* (Magic Arc item 4), AI included.

## 2. Ethereal nodes and the map

The moment the mission is accepted, four nodes appear:

```
The Wilds -- Focus 1, Focus 2, Focus 3, Great Focus   (1 h each)
Great Focus -- Focus 1, Focus 2, Focus 3              (1 h each)
```

- **Ethereal node:** created at runtime, owned by the guild (saved with it), removed when its
  event ends. Today `world.NODES` is a fixed list and "hidden" only means not revealed yet, so this
  is new: runtime nodes and edges in the guild's save, merged into the world graph and the layout.
- **A small focus burns after 7 days** unresolved: its node vanishes and **two new foci** appear,
  each linked to the nodes the parent was linked to (The Wilds and the Great Focus), **1 h farther**
  (2 h). Each new focus has its own 7 days.
- **Day 14:** every focus still active counts as burned and vanishes, with no further spawn. The
  event ends cleanly. Worst case: 3 + 6 small foci + the Great Focus = 10 burned.
- **Resolved focus:** the node vanishes at once.
- **A group on a node that vanishes** is moved to The Wilds with a message ("the fire took the
  clearing"), no damage. A group travelling to it has its order cancelled and stops where it is
  on the route.

## 3. Small focus

- **Who:** 3 Goblins at the squad's mean level plus 1 **Hobgoblin foreman** one level above.
- **Teach them:** a chain of checks against the foreman (CHA to get a hearing, then INT to teach the
  method), **DC 13** each; the player picks who rolls each one. A failed check turns them
  hostile: the fight starts.
- **Fight, then put it out:** after the fight, an INT check puts the fire out (**DC 13**, **16 hours**). It is a map-level check after the fight, not a board action.
  A failure costs the 16 hours and can be retried while the focus clock runs.

## 4. Great Focus (the Ogre's fortress)

- **The fight is the equivalent of a racial-15 character:** the **Ogre at racial ~10** (authored,
  following the racial rule: a track sum of 20, no `racial_override`) plus **about 5 Goblins and
  Hobgoblins at the squad's level +1**, like the Battlefield's warband. Tune it in the sim until it
  weighs as much as one racial-15 boss.
- **New race: Ogre** (author 2026-10-15), enemy only (never in the draft or recruit pool):
  - mods STR +4, DEX -2, CON +2, INT -2, WIS +2, CHA -2; hit die **d12** (new: today's top is d10); Large.
  - **Ability, Reach:** melee attacks reach 1 square farther (the `melee_reach` seam the Grippli's
    Tongue already uses).
  - **Racial tree** (racial picks come at 5, 10 and 15, so the racial-10 Ogre holds 2: **this Ogre takes
    Giant's Grip and Mighty Shove**; Intimidating Presence is for future Ogres):
    - **Giant's Grip**, shared with the Goliath and generalised to "wield weapons one size above
      yours": Large for a Medium Goliath (unchanged), **Huge** for the Ogre. Huge weapons do not exist:
      add `WeaponSize.HUGE` and a Huge variant per base weapon (die stepped once more than Large).
    - **Intimidating Presence**, shared with the Orc: STR instead of CHA to Demoralize.
    - **Mighty Shove** (new): his Push throws the target **3 squares** back and deals **1d6**; hitting a
      wall on the way deals **1d6 more**. A body in the way (alive or dead, friend or foe) stops the shove there and takes
      that 1d6 too. With the fire on the board, his shove throws people into the flames.
- **Map:** an authored map of a fortress under construction: no roof, only some walls, and daylight.
- **Fire on the board (this fight only):** entering or starting a turn on a burning cell deals
  **2d6 per burning square it occupies** (a Large unit on 4 burning squares takes 8d6); each round one or two neighbouring cells catch fire; fire gives light. The
  AI avoids flames and pushes the player's units into them.
- **Talk to the Ogre:** the same CHA then INT chain at **DC 15**, **-1 for every small focus resolved by
  teaching** (the goblins already told him). A failure starts the fight.
- **Convinced:** he builds it right. The fortress stays as a fixed, friendly node near The Wilds,
  with the Ogre as its `Vendor` (portrait), **no function for now**. What it offers is a later item.

## 5. Consequences

- **Every burned focus: -5% of The Wilds' meat yield, permanently** (10 at worst: -50%; no floor needed).
- **Failure** (day 14 with the Great Focus unresolved): the Great Focus counts as burned and the
  fortress stays as a fixed, **hostile** node near The Wilds:
  - more ambushes, by goblins, while hunting in The Wilds;
  - it can be attacked later (the finished fortress, a harder fight). Winning removes the node
    but does not bring the mission back.

## As built

- **Modules:** `wildfire.py` (the state on `Guild.wildfire`, the clock, the talk chain, the put-out, the
  fights' crews, what it leaves on the Wilds), `fortress_scenario.py` (the fortress fight),
  `world.add_node` / `remove_node` / `clear_runtime` (ethereal nodes; `world.VERSION` tells the map to
  refresh), `npcs/ogre.json` (Grumbold the Builder).
- **The map:** the foci and the Great Focus sit near The Wilds at a free spot (`world.free_spot`, kept
  0.09 from every node). Each focus's inspector shows its clock, the talk chain as one button a member
  with their modifier, ATTACK THE CAMP / STORM THE FORTRESS (node functions `camp_fight` / `ogre_fight`)
  and, once the crew is beaten, PUT OUT THE FIRE (`orders.put_out`, a `work` order with
  `task="put_out"`). A missed talk check issues the fight at once.
- **Talking takes no time;** the two checks are rolled where the group stands. The put-out takes the
  16 hours on the clock like any work order.
- **The small focus fight** is on open ground (`ErmosScenario`), no fire on the board, as planned.
- **The Ogre** rolled 4d6 and dropped the lowest for each attribute (author 2026-10-15), then the
  race's mods and his talents: STR 17, DEX 9, CON 15, INT 12, WIS 18, CHA 8; 98 HP. Combat 10,
  work 10, racial 10 by the rule (no pin), Builder, Giant's Grip and Mighty Shove. Equipped (author
  2026-10-15) with Plate Armor (AC 15, speed 4 squares) and a Huge Club (1d10).
- **The escort** (5 at the Great Focus, 7 at the finished fortress) is fixed at level 6, whatever the
  squad's level (author 2026-10-17, `wildfire.ESCORT_LEVEL`); the Ogre stays racial 10.
- **The hostile fortress** is one node an hour off The Wilds; storming it is the finished walls (one
  gate), the bonfire and 7 escorts at level 6. Winning removes it; the meat stays lost.
- **Mighty Shove and bodies:** a downed body stops the throw (and takes the 1d6); a dead one is off the
  board (the board does not draw the dead), so it does not. A plain Push still lands on a downed body.
- **The AI** steps out of the fire, routes round it, shoves a foe into the flames (anyone) or into a wall
  (Mighty Shove), and casts Water Jet when it beats its hand weapon or throws a foe into the fire.
- **Combat lab:** "Wildfire camp" and "The Ogre's fortress" are benchmark fights.

