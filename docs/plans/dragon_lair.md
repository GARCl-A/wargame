# The Dragon's Clutch — plan

**Built 2026-10-16**, as planned below except where *As built* says otherwise; the rules now live in
RULES.md (*The Dragon's Clutch* under *Secret nodes*, *Dragonfire* under *Magic*). **Designed 2026-10-16 (author interview, first pass).** The Blood Cult's third mission, and the last of
the six school missions. A dragon sleeps in a lair under the Mine; the guild goes in to take its eggs.
It brings in three things: **levels past 15** (the dragon is level 20), a **heist** (a sleeper that
wakes by noise, not by sight alone) and **eggs** as cargo worth a lot in the right hands.

Marked **(default)** = picked by me while writing the plan; the author may veto it. **Open** = still
to decide.

## The story

The Ancient Codex names a dragon's lair under the Mine, and whoever carried the Codex out of the
ruins read it on the way. The Cult wants its eggs: the bloodline itself, unhatched. Flavour, not a
gate: the Snake Dragon had dragon blood because it swallowed an egg from this lair.

## 1. The mission

- A `MissionTemplate` on the Blood Sanctuary's JOBS tab, 1 reputation through a deed. **Open to all**
  (not exclusive), so Blood's reachability is safe whatever happened to the Codex and the Snake.
- **Offered once the Ancient Codex is recovered (author 2026-10-16)**, whichever school it went to
  (`requires=LIBRARY_ANCIENT_CODEX.id`, like the other school missions).
- **No deadline (default):** the dragon is not going anywhere.
- **Done = one Dragon Egg delivered to the Blood Sanctuary.** More eggs are the guild's to sell (see 5).
- **Reward:** +1 Blood Cult, the eggs past the first, the hoard the squad carried out, and Blood's
  **level-1 spell scroll** on the Dragon branch (Bloodline -> Dragon) **(default)**, like Water Jet for
  the Wildfire. Blood still needs its level 0 and level 1 (Magic Arc item 4); this pays one of them.

## 2. Levels past 15

The dragon is **level 20, for real (author 2026-10-16)**. The level tables become formulas with no top
(see *Infinite levels* below), so this needs no special case: the NPC's tracks just sum past 30.

- **Killing it is possible (author).** Under the combat-XP rule a level-3 who lands the last hit earns
  `(20 - 3) + 1 = 18`, doubled at the end of the battle: 36 XP. **No cap (author 2026-10-16):** the
  dragon is the jackpot.
- **The Dragon is a new race (author 2026-10-16)**, a beast in `data.BEASTS` with its own hit die and
  size. Its stats are honest rolls, like every authored NPC. **Open:** hit die, size (one cell or
  more), its racial talents, the breath's damage.

## 3. Finding the lair

- A hidden node off the Mine, **The Dragon's Lair (default name)**, revealed by a search at the Mine
  while the job is out, like the Serpent's Nest (`serpent_nest.search`). The hook: Nikkit's miners broke
  into a gallery too hot to work, and nobody goes down.

## 4. The board: a heist

- **A dark, hot lair of chambers (default)**: the way in, the kobolds' warren, the hoard and the egg
  chamber beside the dragon.
- **Kobolds awake on patrol (default):** draconic-blooded, they serve the dragon. They can raise the
  alarm (`alarm_triggered`, already built). Talking to them: see *The patrol's challenge* below.
- **Noise, the new seam.** Today a sleeper wakes on a foe in sight within `awareness_radius`, or on an
  alarm (`ai.take_turn`). The dragon instead has **stages: asleep -> stirring -> awake**. Running, heavy
  armour, a fight, and grabbing coin fill a meter; moving slowly and a DEX check against its WIS keep
  it down. **Open:** the numbers.
- **The hoard:** coin on the floor, picked up as real `Copper Coin` / `Gold Coin` in the pack (200 coins
  = 1 kg). Every handful is noise: the greed trap.
- **Awake:** the dragon fights. Its breath sets cells alight with `Battle.fire` (built for the Wildfire);
  the lair burns and closes up as the fight goes on.
- **Won** when the squad leaves by the way in with at least one egg (`withdraw`), or the dragon falls.

## 5. The eggs

- **Dragon Egg**, heavy **(default: 8 kg)**. It does not break and does not spoil (author 2026-10-16).
  The more eggs, the more pay and the slower the carrier.
- **Sold anywhere, paid best by the schools (author 2026-10-16):** the Market buys it at its normal
  price; the three sanctuaries pay much more **(default: each sanctuary buys Dragon Eggs, a sell row on
  its tab)**. **Open:** the two prices.
- Hatching is a future idea (author), not in this mission.

## 6. The patrol's challenge

**Author 2026-10-16:** talking belongs in a general **dialogue before initiative**, not in new combat
actions. The patrol's challenge below becomes the first use of that tool (its design is pending); the
beats stay: contact opens the dialogue, a Draconic speaker unlocks Bluff / Bribe, an egg in sight
closes it.

The point is a choice under pressure, not a free pass for having a Kobold.

- **A patrol that spots the squad does not ring the alarm at once: it challenges** ("Who walks in the
  master's halls?"). The squad has **one round** before the alarm, whoever is in it.
- **Without a Draconic speaker** the only answer is to **silence them**: drop the whole patrol before
  its next turn. No alarm, but the fight is noise on the dragon's meter.
- **With a Draconic speaker** (any unit that speaks it; a Kobold is born with it), a new action,
  **Parley**, offers two more answers:
  - **Bluff** ("we are the new shift", "tribute for the master"): CHA vs 10 + the patrol leader's WIS,
    **+2 for every bluff already told** in the lair (they talk to each other). Success: the patrol goes
    back to its round and leaves the squad be. Failure: the alarm, now.
  - **Bribe:** kobolds love what shines. A sure thing, paid in coin from the pack, so the hoard's coin
    (picked up at the cost of noise) can buy the guards with the dragon's own gold.
- **The eggs change everything:** a patrol that sees someone carrying an egg does not parley ("the
  master's eggs!"); it is the alarm or silence. Talk gets you in; the way out is stealth or steel.
- **AI:** the kobolds' side chooses challenge then alarm; the squad's AI (lab, `combat_pairs`) uses
  Parley when it has a speaker and no egg in sight, bribing when it can pay, otherwise silencing.

## 7. Later: the dragon's revenge (Blood's fourth, author 2026-10-16)

Not in this mission. A dragon that was robbed notices, and keeps attacking. Written as its own Blood
mission later (backlog).

## Infinite levels

Nothing stops the tables having no top: the curves are already closed formulas.

| Track | Today (cumulative, levels 1-15) | Formula for level n |
|---|---|---|
| Combat (and magic) | 3, 10, 21, 36, ... 465 | `2n² + n` |
| Work | 2, 6, 12, 20, ... 240 | `n(n + 1)` |
| Racial (sum of tracks) | 2, 4, 6, ... 30 | `2n` |

What changes with them:
- `progression.Curve.level` works out the level from the formula instead of counting a list;
  `to_next` and `next_racial_pick` lose their "top of the table" case; racial picks at every 5 go on.
- The editor's stepper (`unit_edit`) and the lab (`combat_lab.MAX_LEVEL`) still need a top, only as a
  UI limit (**default:** 30).
- `reference.py` prints the formula and the first levels instead of the full list.
- **Talent trees are finite.** A pick past the last node of a tree waits unspent: that is item 5 of
  the backlog's order (*Talent trees to the level cap*), not a blocker.
- Generated enemies keep their caps (combat 7 / work 6) when scaled to the squad (`clamp_level`); only authored NPCs go past 15.

## As built (2026-10-16)

- **Infinite levels** went in first (`progression.Curve`); the editors stop at `LEVEL_UI_CAP` (30).
- **The dragon:** Kharzuul the Ember-Old, `npcs/dragon.json`. A new beast race **Dragon** (Huge, d12, mods
  +5/+0/+4/+2/+2/+2, darkvision, Draconic), kept out of every rolled pack (`data.AUTHORED_BEASTS`). Racial 20 =
  combat 20 + work 19 + magic 2 (Dragon, Dragon Breath) + Dragonfire; its honest rolls (15, 14, 9, 9, 7, 6)
  arranged body first; natural armour 5; 227 HP, AC 15. Its four racial picks wait unspent: no racial talent
  belongs to the race yet. A hand-drawn head (`icons/head/dragon-head.svg`) is its glyph and the lair's.
- **Its breath burns** in the lair (`Scenario.breath_burns`), and the fire spreads a cell a round once it is up.
- **The board** has every way between the warren, the hoard, the clutch and the hall 3 cells wide so the dragon
  can follow; the tunnel to the way in is 2 wide, so it cannot: the last stretch is breath-only.
- **The patrol's challenge** is `dialogue.Challenge` (Bluff, Bribe, Attack; Bribe needs Draconic there,
  `Encounter.worded`); `Battle.talk_handler` hands it to the battle screen, which shows the dialogue over the
  board while the fight waits; with nobody playing the squad, `dialogue.ai_play` answers.
- **Scenario hooks** `on_turn_start` / `on_turn_end` / `on_pick_up` are the base `Scenario`'s now (no-ops).
- **The squad's AI** plays the heist (`ai._heist`): an egg, at a creep while the dragon sleeps, then the way out.
- **Egg prices:** $400 (the Market pays its usual half); a keeper pays $1200 (`lair.SHRINE_EGG_PRICE`), the
  Cult only once its own egg is in. The egg is a `GEM`-type item, 8 kg.
- **Reward:** `MissionTemplate.reward_item` (new) hands the Scroll of Dragonfire to the delivering group.
