# The Dragon-Blooded Snake — plan

**Built 2026-10-15**, as planned below except where *As built* says otherwise. The rules now live
in RULES.md; this file keeps the decisions.

The first magic mission after the Codex, built whole before the other faction missions are
designed (author, 2026-10-15). It brings in four systems the game will reuse: a dungeon of its
own, the magic talent track, capturing a downed foe, and non-lethal damage.

Marked **(default)** = picked by me while writing the plan; the author may veto it.

## The story

An ordinary snake with dragon blood in it lairs in a nest near the Lumber Yard. *Blood* is
**bloodline**: magic you are born with (child of a dragon, an angel, a demon). Two schools want it:

- **The Blood Cult** wants the **corpse**, to read the bloodline in an autopsy.
- **The Nature Coven** wants it **alive**, to learn whether a curse corrupted it and to treat it.

One beast, two outcomes: the first delivery closes the other, and the closed one shows as
**failed** (the Codex deliveries get the same treatment).

## 1. Missions and the failed state

- Two `MissionTemplate`s, `blood_snake` (goal: the *Snake Dragon Corpse* item) and
  `nature_snake` (goal: the captured Snake Dragon in the group, see 4), on the Blood Sanctuary's
  and the Nature Grove's JOBS tabs once the sanctuaries are revealed. No deadline, no pay,
  1 reputation each through a deed (`blood_snake` / `nature_snake`), exclusive like the Codex.
- **Failed exclusives.** When one of an exclusive set is done, the others are recorded as
  failed (deed and mission), listed as such on the Guild tab's deeds and the missions ledger.
  Applies to the three Codex deliveries too.

## 2. The nest (dungeon)

- A hidden node, **Serpent's Nest**, one edge off the Lumber Yard. With either snake mission
  out, a group at the Lumber Yard can search for it: 2 h, Wisdom DC 10, the same shape as the Ox's
  Country Roads search **(default)**.
- `world.Node.dungeon = True`: one dark map (no ambient light), **5 chambers** joined by
  corridors, in the `AncientRuinsScenario` mould. Chambers 1-4 hold packs of snakes (`SNAKE_POOL`,
  a Giant Spider at most) **(default)**; chamber 5 is the lair, with shallow and deep water, and
  the Snake Dragon in it.
- The fight is won the moment the Snake Dragon is down for good (dead or captured), whatever is
  still standing (`Scenario.win_check`, like the Ox Fields).

## 3. The Snake Dragon

- An authored NPC (`npcs/snake_dragon.json`, portrait `portraits/snake_dragon/0.png`), **level 8**,
  stats honestly rolled (the boss rule). Its race is the existing **Snake** (`data.BEASTS`, Small,
  `serpentine`): an ordinary snake, and everything dragon about it comes from its magic talents
  (Bloodline → Dragon → Dragon Breath). Its one racial pick at level 8 is **Serpent Growth**
  (Small to Medium), already in `talents.py`.
- **Dragon Breath** (an `Action`): costs 2 AP; a cone 1-3-5 cells deep 3 in the facing
  direction; **one attack roll** against every unit in the cone, **allies included**; 2d6 damage on
  each hit. The AI breathes only with **at least 3 units in the cone**.
- When killed it drops the *Snake Dragon Corpse* (`loot.UNIQUE_DROPS`, as Aurochs drops his hide).

## 4. Capture

- **Capture** (an `Action`, 1 AP): an adjacent downed enemy (`dying` or `stable`) and a **Rope or
  Chains** in the actor's inventory. The rope or chains is used up **(default)**. The target becomes
  `captured`: out of the fight, never takes a coup de grace, skips the end-of-battle death save.
- **Anything can be captured, all the same way.** After the battle every captive joins the group
  as a **captured unit**: a `Unit` in `Group.captives`, not a member, not in battles, not fed.
  It **counts toward the herd limit** (`Group.herd_capacity`, 1 each **(default)**) and walks with
  the group (its speed counts in the group's pace **(default)**). It **dies 7 days** after capture;
  the Snake Dragon's body then becomes the *Snake Dragon Corpse* item in the leader's pack.
- The *Snake Dragon Corpse* rots in **3 days** (`lifespan=3`, spoils to nothing usable).
- Saved with the group. Shown on the group screen (a captives row with days left) and the map's
  group card. Leaving a captive behind is a release button on the group screen **(default)**.
- The AI on the player's side (autowin, the sim, `combat_pairs`) captures when the Nature mission
  is accepted and the target is the Snake Dragon; the enemy side never captures.

## 5. Non-lethal toggle

- Per character, in the battle panel, default lethal; applies to every attack (melee, ranged,
  spells, Dragon Breath).
- Non-lethal: −1 to hit; a foe brought to 0 HP drops `stable` instead of `dying`; a hit on a
  downed body does not tick its death clock.
- The player-side AI switches it on in the same case as Capture (the Nature mission is accepted and
  the target is capturable).

## 6. The magic track

- A **fourth talent track**, `magic`, beside combat, work and racial. Its XP is **magic XP**:
  a last hit dealt with a spell (the combat XP rule's amount goes to magic instead of combat)
  and finishing the study of a spell (`spell level + 1` marks **(default)**). Later magic
  activities add more. The thresholds are combat's **(default)**. Magic levels feed the racial
  track like the other two **(default)**.
- One root per school, **Initiated**, granted (not picked) when the unit holds that school in
  `magic_sources`; a school's branch opens only under its own Initiated root.
- The Blood root opens **Bloodline → Dragon → Dragon Breath**. *Dragon* gives +1 AC (scales)
  **(default)**; *Dragon Breath* grants the action above.
- For the player the track becomes reachable with initiation (Magic Slice 2). Now it ships so the
  Snake Dragon can carry it, and so a Kobold (born `blood`) already sees the Blood root.
  *As built 2026-10-17:* initiation is the rite at each sanctuary (`rite.py`), which grants the school
  and its Initiated root.

## Build order

Each step lands with its UI, AI and tests, and is committed on its own:

1. Magic track (XP, levels, picks, the Blood branch) and the Dragon Breath action + AI.
2. Non-lethal toggle + AI.
3. Capture, captured units in the group (save, herd limit, 7-day death, UI) + AI.
4. The Snake Dragon NPC, the nest dungeon and its discovery.
5. The two missions, the exclusive failed state (Codex included), RULES / REFERENCE / tutorial.

## As built (differences and choices made while building)

- The fight cannot stop the moment the last foe falls if someone still has to tie a captive up, so a
  won lethal fight runs **one more round** (*BIND THE FALLEN*) while a fallen foe lies unbound and
  someone standing holds a Rope or Chains.
- A foe left fallen and unbound after a won lethal fight is finished off: the Snake Dragon then drops
  its body in the loot even if it ended knocked out.
- A captured foe drops no unique item and no species material (it is alive).
- **Rope** is now sold at the Market (8, 2 a day) and **Chains** at the Smithy (3, 0.5 a day): without
  them only a Mercenary or a Jailer could ever take the Snake Dragon alive. Rope being freely
  buyable dropped the Alarm Trap recipe's derived level from 2 to 1 (`craft_level.py`).
- The two snake jobs require the Library's Codex job done (what reveals the sanctuaries).
- Once either snake job is delivered, the nest is re-entered without its Snake Dragon.
- Dragon Breath's attack bonus is the breather's Constitution modifier.
- The level screen sizes its four columns by each tree's breadth (combat and work are wide, racial
  and magic narrow).
