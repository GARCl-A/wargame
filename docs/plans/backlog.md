# Backlog — everything still open

The one place for open work. It folds the playtest review (2026-10-05), the wagon and
camp to-do list and the later playtest notes. What is already built is in the code, its
tests and the git log; the long-range AI plan is
[campaign_ai_roadmap.md](campaign_ai_roadmap.md).

Sizes are estimates; claims about what the code already has were checked on 2026-10-18. When an item is done, delete
it here and, if it changed a design premise, record it in `AGENTS.md` or the doc that owns it.

Parts:

- **Ready to do** — the task is defined enough to start. Sorted by size: small (a sitting),
  *Playtest notes* (raw, to be sized as they are picked up), *Architecture debt* (past choices to
  pay when a feature needs them), large (a system: UI, AI and tests), *Art* (made by hand) and epic (its own arc).
- **Needs more information** — a design question, a repro or another system has to land
  before the task can be sized.
- **Starting items waiting on another system** — not a question: a list of items whose
  system does not exist yet.

The *Suggested order* below comes first.

---

# Suggested order (updated 2026-10-17)

Goal read: a sandbox open-world guild manager; the run ends only on a wipe. Balance and
sim work is ahead of the content it balances, so the order favours content verticals and
the seams they need. **The magic arc is the whole focus until it closes** (author, 2026-10-15).

1. **Magic Arc, to the end** (*Ready to do -> Medium*): the six school missions are built (2026-10-16: the
   dialogue before initiative, [dialogue.md](dialogue.md), and Blood's third, the Dragon's Clutch,
   [dragon_lair.md](dragon_lair.md)); the keepers, the initiation and each school's own level-0 / level-1
   spells are built (2026-10-17). The talk before the arena's first boss fights is built (2026-10-18,
   `boss_talk_screen.py`). **Next:** a few choices in the magic tree for Nature and Faith (*Medium -> Magic Arc*). The frontier supply run walks since
   2026-10-18 (RULES.md *Ledger Hold*).
   How a player gets the new scrolls is deferred past the arc (author 2026-10-17: scrolls are never sold).
   The racial rule is settled (2026-10-16: a pick every 5 racial levels, no authored NPC pins its level, a
   test holds it; the level curves have no top since the same day); the Ogre stays racial 10 with a fixed
   level-6 escort (2026-10-17).
2. **Playtest on the current build, then feed it and the Caravana run to the AI and the sim** (*Large*): starts once the
   magic arc closes (author 2026-10-17); the walked supply run is in; the rite and the tier 0/1 spells are in. The AI work it waited on is done (2026-10-16);
   what the AI still lacks is a short list (*Teach the AI the newer actions*), and the weapon actions' cases are
   tuned from this playtest.
3. **Blood's fourth mission** (the robbed dragon strikes back): only after every test scheduled after the
   magic arc (author 2026-10-17: the playtest and the tuning it feeds).
4. **Production chain between groups** (*Large*, after magic).
5. **Talent trees as long as the levels** (*Large*, after magic).
6. **Archaeology at Ancient Ruins** (Shovel tool, discovery rolls, artifact recovery; after magic).
7. **Cooking and temporary meal buffs** (after magic).
8. **Sim planner / offers integration** (`scripts/economy_offers.py` -> policy planner), once item 2's data is in.

---

# Ready to do

## Small

- **Economy report prints a FAIL on the day-30 milestone.** `scripts/economy_report.py --quick`
  (re-run 2026-10-10, after the vocations: unchanged): the `balanced` policy reaches the milestone
  in 0% of guilds (need 50%), cost from $423. It is the known gap with the recorded runs (11-14
  days by hand), so it settles with *Feed the recorded runs* and the planner, not by tuning
  prices. **Decided 2026-10-10:** recalibrate the sim until it matches the recorded runs (both
  ~60-day saves reached day 30 easily), starting with the offers list (built). The run exits 1 on a failed verdict, but no test or gate reads it.
- **Enemy info: tune the read (built 2026-10-11, `intel.py`).** The thresholds are a first guess (`intel.BASE_DC` 8,
  bands at margin 0 / +5 / +10, `RACE_DISCOUNT` 2, `ASSESS_BONUS` 4): tune them on the next playtest, with
  `vocation_report.py` for the Scholars' +2. The AI's search with nobody in sight (the aggressor sweeps waypoints,
  the defender groups up) may want smarter play around doors and terrain.
- **Mine leftovers:** In the economy simulation (`scripts/economy_report.py`), the `crafter` policy still skips recipes that need Coal, and no policy builds the Claim oven, so those two trips stay unpriced in the automated report.
- **UI polish leftovers (found 2026-10-13 by rendering the screens at 1000x640 to 1920x1080).** Map labels
  (`map_panel.place_labels`: a name sits where it overlaps no other name or mark) and the Wilds' trees (`MapCamera.autofit`
  takes `radii`, half a region's radius around each node) were fixed 2026-10-13. Left: (1) The draft cards' attribute row
  (`ui/draft_panel`) is tight between groups ("+0 CON"). (2) In a window below about 1100 px the map frames at its zoom
  floor (`MapCamera.autofit`, 440 in `map_panel.draw_map`) and overflows instead of fitting.
- **Map names on a crowded map (found 2026-10-15).** The layout no longer squeezes a growing map into the
  unit box: it grows past 1 and the camera pans (`world.compute_layout`, `_spread` keeps every pair of nodes
  0.09 apart, so icons never stack). Names are the next limit: at the camera's zoom floor 0.09 is about 40 px,
  narrower than a name, so a dense region (tried with 60 extra nodes) piles labels even where icons are clear.
  Options when the map gets there: names only past a zoom level or on hover, or a wider spacing.
## Medium

- **Magic Arc — what is left.** Built: the six school missions, the keepers and the initiation (`rite.py`), each
  school's level-0 / level-1 spells with their AI. RULES.md *Secret nodes*, *Magic* (with *Initiation*), *Capture*,
  *Dragon Breath*, *Fire on the board*; plans and as-built notes in [snake_dragon.md](snake_dragon.md),
  [ogre_wildfire.md](ogre_wildfire.md), [necromancer.md](necromancer.md), [dragon_lair.md](dragon_lair.md),
  [dialogue.md](dialogue.md). Premises that stay: initiation belongs to the character; a school takes 2 reputation
  with its faction (a threshold, not spent); exclusivity is intended and the guild's choices may close a school
  (accepted 2026-10-16); the third missions are the endgame bosses, each worth a racial-15 character, so they are
  authored NPCs (generated enemies stop at `constants.ENEMY_COMBAT_CAP` / `ENEMY_WORK_CAP`); Faith consumes a Holy
  Symbol (uncommon, $80 since 2026-10-18; from the Priest's birth or a Priest's loot; shops buy it, none stocks it); Blood is bloodline (new branches follow
  Bloodline -> Dragon -> Dragon Breath) and Blood magic costs no hit points. Left:
  1. *To close the arc:* choices in the magic tree for Nature and Faith (author 2026-10-18). Today the tree has 5 nodes: Blood's chain (Bloodline -> Dragon ->
     Dragon Breath) and the granted roots `nature_initiated` / `faith_initiated`, which do nothing on their own, so a
     Nature or Faith caster has nothing to pick. The author reviews the tree and how it is managed; at least a few
     picks per school.
  2. *Scrolls (deferred past the arc, author 2026-10-17):* scrolls are never sold; how a player gets Hex, Spare the
     Dying, Healing Touch, Invisibility and Raise Dead is designed later (`items.py` has no scroll for the last two).
     Today Grasping Roots comes as the Scribe's starting Scroll and with the `nature_magic` race (Gnome).
  3. *The sim does not initiate anyone:* no policy boards a member, the same multi-day investment step the Claim oven
     lacks (*Mine leftovers*); both land with the planner.
  4. *Blood's fourth mission* (the robbed dragon keeps attacking): not designed; not before every test scheduled
     after the arc (author 2026-10-17).
  5. *Open-ended:* the Blood bloodlines are dragon (built), angel and demon (author 2026-10-18); more magic XP sources (today a magic kill and a
     finished study, `progression.py`, on combat's curve as a placeholder).
  6. *Tuning, after a playtest:* the Battlefield's sides (4 soldiers at -2, 6 raiders at +1, the 6 potions); the Snake Dragon's numbers (level 8, Dragon Breath 2d6, the nest's packs), the 7-day
     captive and the 3-day corpse are first picks. **After the racial rule (2026-10-16):** the Ribbit Brothers went
     from work 2 to 4 to earn their one racial talent at racial 5, so they are mean 5 (the arena rule was boss = +1
     over an expected level 3, i.e. 4) with one more hit die each (Bufo 38 -> 44 HP, Peep 23 -> 27, Ribit 31 -> 37);
     the Ancient Archivist lost Deft Bones (3 talents at racial 10, which earns 2); the Aurochs carries work 13
     instead of a pin (same 13 HD). Re-check those fights in the lab. **The Ogre's Wildfire:** the Ogre is 4d6-drop-lowest (STR 17,
     98 HP), in Plate Armor (AC 15, speed 4) with a Huge Club; his escort is 5 at level 6 (7 at the hostile fortress).
     AI against AI in the lab (`combat_lab` "fortress", squad at mean 6): the squad wins 2/30 with four, 4/30 with
     six. Play it in the lab first (an AI squad plays far below a person), then tune the fire (2d6 a cell, 1-2 cells a
     round), the camp's crew (3 Goblins + a Hobgoblin a level over), the DCs (13 / 15, -1 a taught focus), the
     put-out (16 h, DC 13) and the meat loss (5% a burned focus, for good). **The Necromancer at the Front:** the field
     (48 x 30, night), the sides (4 soldiers at -2, 8 raiders and 4 Zombies at +1, 6 bodies), the necromancer (racial 15,
     96 HP, a raise a turn, reach 6) and Investigate's search (3 cells, WIS vs 10 + INT); AI against AI the squad loses at level 3
     and 6 (`combat_lab` "necromancer"). **The Dragon's Clutch:** the noise (stir 6, wake 14, the sounds' worth, the
     14-cell hearing), the patrols (two of three, sight 6, a torch each), the dragon (racial 20, 227 HP, AC 15, a
     Huge body the tunnel keeps out), the hoard and the egg prices ($400 at the Market, $1200 at a keeper); AI
     against AI at level 3 the squad gets out with an egg in 4 of 20 (`combat_lab` "lair"). **The dialogue
     before initiative** ([dialogue.md](dialogue.md)): every number is a first pick (`dialogue.BASE_DC` 10 +
     the leader's WIS, a bribe of $3 a foe per level + 1 and $10 a crime point for a patrol, Persuade's ±3 by
     alignment, Intimidate's ±4 and the rout at +5, the +5 initiative a failed Intimidate gives, +2 a bluff
     told in a Challenge).

## Playtest notes 2026-10-12

Raw notes from a playtest, grouped; split each into a sized item as it is picked up. Guiding
rule from the notes: **fewest possible buttons on the map**: a node has one "Enter" button and
its functions are tabs inside.

**Draft, leveling and talents**
- **Leveling templates:** player-made, editable autopick of talents, so the same clicks are not
  repeated every level.
- **Target equipment:** per unit, how it should be equipped; on entering a shop with an upgrade
  available it swaps by itself.

**Auto orders**
- **Programmable order chains for a group**, e.g. gather Lumber at the Yard -> sell Lumber and
  buy food -> gather again. Large; ties to `orders.py` and the sim's planner.

**Factions, nodes and world**
- **The Battlefield beyond the Faith mission (author 2026-10-15).** For now its only use is the Faith
  Order's errands, and it stays that way (author 2026-10-17). Later it becomes one more place of Ledger
  Hold work and missions: what an open skirmish pays, how often the front has a fight. The supply run's
  walked order with an ambush part-way (`Guild.supply_leg`, `Order.owed`) is the shape to reuse.
- **Gold spent on equipment per level (author 2026-10-15).** A table of how much kit a body of a given
  level should carry (weapon, armour, consumables), for the enemy generators (`encounters.py`, the
  Battlefield's soldiers and warband) and for future balance. Today a generated body carries its
  occupation's weapon and item whatever its level.
- **Ancient Ruins as an archaeological site:** start "archaeology" work there (deferred to after the magic arc).
  Decided 2026-10-12: complex system requiring tools (Shovel/Pick), multi-step iterations and costs to unearth artifacts, money and lost lore.
- **The Claim:** let the player build their own farm to stock food.
- **The Ogre's fortress after the Wildfire** ([ogre_wildfire.md](ogre_wildfire.md)). Convinced, it stays as a
  friendly node with the Ogre as its `Vendor` and **no function** (author 2026-10-17: it stays so; trade with
  him later, once richer trade subsystems exist). Hostile, STORM THE FORTRESS is built (the finished
  walls, 7 escorts; winning removes the node).

**Balance question**
- **Which stats matter.** Playtest feel: CON > STR > DEX > CHA > INT > WIS in importance. Negative STR/CON is very punishing
  (armour is hard to wear, healing is slow); low CHA caps guild growth; the mental stats hurt little.
  Decided 2026-10-12: keep current stat severity for now; revisit attribute weighting and severity after the magic arc lands.

---

## Architecture debt

Past choices that now fight the direction. Each has the cost of fixing it; pay one when the
feature that needs it is next, not before. Debts already written as part of a feature are
pointed to, not repeated.

- **Big screen files.** Split 2026-10-13: `app.py` (680 lines) keeps the loop and the dispatch tables, its methods live in
  `app_nodes.py`, `app_forced.py`, `app_hunt.py` and `app_battle.py`; `battle_screen.py` keeps input and turn flow, the
  painting is `battle_draw.py`. Still about 860-1060: `market_screen.py`, `map_screen.py`, `group_screen.py`,
  `taverna_screen.py`. When one takes a new node or tab, split by concern instead of growing it. **Cost: low per split.**
- **Saves have no migration (on purpose).** Fine while the author is the only player. Decided 2026-10-12: keep the strict premise that "an older shape does not load"; no migration bridge needed for now. **Cost: zero.**

## Large

- **Teach the AI the newer actions: what is left.** Done 2026-10-16 (`tests/test_ai_actions.py`): the 2-point
  weapon actions are scored by expected damage (hit odds against the AC the unit can reckon: the read number,
  else 10 + the armour and shield it sees) against the two plain attacks the same points buy (one shot for a
  crossbow), so each is taken only where it pays (Cleave on two foes, Armor Pierce on heavy armour, Extreme Shot
  past the crossbow's range, Power Shot on the last arrow, Maiming Strike on a flag runner, Parry & Strike when the
  swing barely lands and foes crowd in); Throw with the last point at a foe it may drop, a flag runner, or when it
  cannot get nearer; Jump over a gap it cannot walk; Push also into a pit, a bear trap or out of a flank on itself;
  traps it sees are walked round, stopped short of and disarmed when in the way; a secret wall it is stalled beside
  is opened; a rider never walks off its mount, waits for it (Delay), dismounts beside a foe to strike, and does not
  remount with a foe in reach. Earlier: Dragon Breath, Capture and Non-lethal, fire, Mighty Shove, Water Jet,
  Dragonfire, the necromancer (`ai._necromancy`), Investigate on the unseen, the patrols (`ai._patrol`) and the
  heist (`ai._heist`). **Gauge (`combat_pairs.py combat_lab --trials 40`, 97 logs, the AI on both sides, HEAD
  before -> after):** Scrapper 49 -> 48%, the Pit's Scrapper 55 -> 63%, champion 89 -> 92%, ambushes 85 -> 92%,
  hunts 83 -> 89%, Defend the Title 46 -> 65%, brawl 92 -> 95%; the one-log Claim fights move within noise.
  `sim_test.py`: no stuck seed, 98/102, 5.4 -> 4.8 rounds a fight. After the weapon-action rebalance (same
  day): Scrapper 46%, the Pit's 63%, champion 91%, ambushes 92%, hunts 89%, Defend the Title 62%, brawl 98%,
  within a run's swing of the line above. These are the new numbers to beat.
  Left: (1) a 2-point weapon action cannot follow a walk (two points a turn): the rule, not the AI (Javelin Charge
  is the exception, 1 point after a walk since 2026-10-16); (2) the player's side has no use for Raise Dead or
  Invisibility (no scroll or other source teaches either: `items.py` has scrolls for the other ten spells only);
  (3) the tier 0/1 spells have their AI (2026-10-17, `ai._hex_or_roots`, `_try_healing_touch`), but Grasping
  Roots and Hex are rules of thumb, not scored in `ai._strike_worth`'s expected-damage terms; (4) Dragon Breath's breather does not move to set up a better cone.
- **Weapon actions: tune the favoured cases after a playtest.** Rebalanced 2026-10-16 (author: two plain attacks
  win in general, the 2-point action wins in its favoured case): out of its case an action is one strike; in it
  the strike lands twice over plus a small edge (RULES.md *Weapon actions*, `favoured` on each action, the
  premise held by `test_ai_actions`); Javelin Charge is 1 point after a walk. Left: whether each case comes up
  often enough (Repel Strike's wall, Maiming Strike's helpless foe, Parry & Strike's two foes, whose margin is
  the slimmest), and the old Extreme Shot / Power Shot niches.
- **Playtest on the current build, then feed it and the Caravana run to the AI and the sim.**
  The *Caravana Do Homem Verde* run (world `95ea6648`, 205 days, the longest) is archived but **never analysed**:
  its `play.jsonl` is in `recordings/2026-10-12/` and its 62 fights in `combat_lab/campaign/`, yet the
  `human` profile (`recordings/2026-10-10/human_profile_4runs.json`) and the `combat_pairs.py` baseline
  (72 logs, 2026-10-11) were both made before it. Order: (1) teach the AI the newer actions (above, done 2026-10-16), so
  the enemy is worth feeling; (2) play a fresh run on the current build with `record_play` ON (weapon actions,
  2-AP actions, magic once in); (3) run `play_analysis.py` over the four earlier runs + Caravana + the new
  one into a new profile, and re-baseline `combat_pairs.py` with the new campaign logs; (4) then settle
  *Economy report prints a FAIL* and the planner with that data.
- **Production chain between groups (after the magic arc, author 2026-10-15).** The first place where one
  group's output is another's input, which is the heart of the open-world vision. Lumber feeds a
  carpenter (bows, wagons: the Tanner holds the Shortbow and Light Crossbow until one exists), Coal feeds the
  Smith (Iron Bar is already a forge recipe). Gives Coal and the gems a use and closes `sources.py`'s
  `traded` goods one chain at a time. Needs recipes, a carpenter node or function, the sim's `crafter`
  policy and tests.
- **Talent trees are shorter than the levels (to be authored by hand, after the magic arc).** The XP
  curves have no top since 2026-10-16 (`progression.Curve`), and each level grants one pick: combat has
  15 nodes and work 14 (checked 2026-10-15), so a pick past the last node waits unspent and neither tree
  has room to choose. The racial
  track has 32 nodes split across races (some shared, like Giant's Grip); a race needs only 3 of
  its own (one pick at racial 5, 10 and 15), and most have 1. Goal: **at least 30
  combat and 30 work talents**, and 3+ racial nodes per race. Nothing built; the author will design them.
  The magic track (5 nodes since 2026-10-17) is being reviewed by the author: its size and how it is
  managed are open.
- **Gathering: loose ends (built 2026-10-11, `gather.py`, RULES.md).** The licence, the drop tables,
  the pay rule, the ambush and the sim's `gatherer` policy (and `miner` gathering once it can afford
  the licence) are in. **Retuned 2026-10-11:** a shift rolls `hours / 7` times (a rate, with the leftover as a
  chance of one more), so a full 16 h day sold is worth at least 3 copper more than the best wage (Yard 8 against
  5, Mine 14.3 against 10, `gather.PREMIUM`), and the licences are priced for a 30-day payback at that gain for 3
  workers ($270 and $385). The Snake joined the Yard's packs (Wolf 45 / Snake 30 / Giant Spider 25). Left:
  (1) **the sim says the payback is longer than the table's.** Measured over 90 days (20 guilds of 3 starter workers at level 0, skill 0.95):
  median money a member at day 30 / 60 / 90 is $37 / 107 / 172 for `lumber` and $35 / 65 / 136 for `gatherer`
  (3 of 20 wiped by the pack); with the ambush off the gatherer ends at $137. Why day 50? A starter guild of 3 works day-labour first to pool the $270 licence (reached around day 20-25); once bought, it nets about +$1.70 a day per member over day labour, not +$3: hauls lose value to rotting Fruit (24 h life), bi-daily selling cycles, and haggling. Thus cumulative money only catches up to pure day-labour around day 50. Applies to both Lumber Yard ($270) and Mine ($385; $10 road each way, higher pack risk). **Decided 2026-10-12: keep current licence prices ($270 and $385)**; the payback gap will naturally improve when future food crafting recipes allow processing Fruit into longer-lasting rations/food (preserving haul value without forced rapid resale); the Mine's higher ambush risk on the Old Road is intentional and accepted. (2) The sim plays the gathering ambush (`gather:<node>`) as real battles of the
  node's own pack, but with no recorded fights of a person against these packs, the win rate is the AI's or the
  skill knob's. (3) The shift picker shows the drops and the rolls but not the average worth of a shift against the
  wage. (4) The Mine has no art yet (the Gathering tutorial card was delivered in 2026-10-12 for both Yard and Mine).
  (5) Coal and the gems have no use but to be sold (Coal waits for the Smith's chain); Fruit is food, but it rots in
  a day, so a Yard crew eats it or sells it that evening. (6) **Snake Venom Gland:** Built 2026-10-12: `CRAFTING_RECIPES` is a dictionary of lists mapping each produced item to its recipe variants; the Antidote in the Apothecary has two recipe variants under "Antidote" (one with Spider Venom Gland and one with Snake Venom Gland), both yielding Antidote. Blade poison coating for player/enemy weapons will be a separate craft, scheduled for after the new weapon actions and traits land.
- **Item properties: base material sources (rarities decided 2026-10-11).** Built 2026-10-11
  (`sources.py`, REFERENCE.md *Base materials*): a base material is a material, food or gem no recipe
  makes (derived), and a test fails for one with no source (gathered, dropped, hunted, foraged, quest,
  traded or spoiled; gathered and beast drops are read off `gather.TABLES` / `data.BEASTS`). Left: (1) the
  rule covers only those types, since weapons, armour and the rest have no recipes yet; widen it as recipes
  land (Smith chain). (2) Six goods are declared `traded` (Potato (Farm), Salt, Beer, Vial (Market), Paper, Ink (Library)):
  Iron Bar moved to forge crafting recipe 2026-10-12; the remaining six wait for their production chains (Farm,
  Library). (3) Rarity per base
  material is set (Venom Gland became common; the rest stayed), and each shop's target count already follows
  it (`economy.SHELVES`).
- **Prisoners.** (First slice built 2026-10-15 for the Snake Dragon: the Non-lethal toggle, Capture with a Rope or
  Chains, captives kept by a group for 7 days on the herd limit, `captives.py`; decided that anything captured follows
  that same scheme.) Left: what a captive is *for* beyond a mission (ransom, questioning, recruiting, the prison), the
  enemy side capturing the player's people, and rescuing a captive in battle.
- **Combat AI plays far below a person.** (Reframed 2026-10-10: on the author's own fights the AI
  playing the player's squad wins hunts 96% and ambushes 100%, so it is close to a person there;
  the gap is the arena duels. The author wins 60 of 62 against the AI and the game feels easy, so
  the lever is a smarter enemy built on what it can see (`intel.known_fields`, built), not stronger enemies.
  Wiping is the end of the run, so a person should still win almost everything.) Every economy number depends on how often the
  squad wins, and a person wins far more than `ai.py` does: measured in the economy report
  (layer 1 prints the AI's own win rate beside the skilled ones), the AI wins the Scrapper
  95%, the champion bout 75%, a Games brawl 43%, capture the flag 37%, a Wilds ambush at
  level 3 61% and the Ribbit Brothers 7%. A person wins the Pit's bouts "almost always".
  Goal: AI win rates close to a competent player's on those benchmark fights, so the sim
  (and `autowin`) stop needing a `--skill` knob. **Benchmark scenarios (decided):** Scrapper,
  Games brawl, champion, capture the flag, Ribbit Brothers, dungeon and ambush (wolves and
  bandits); the player's recorded fights on these train the policy. Start from what the AI
  does badly in the Games (objective play in capture the flag, focus fire), re-run
  `scripts/economy_activities.py` as the gauge. Needs AI changes, tests and `sim_test.py`.
  - **Way in: record the player's combat, as was done for the economy.** The recorder is built
    (2026-10-10): `combat_log.py` writes one JSONL file per fight with the whole fight, every
    decision with its legal options and what `ai.py` would have done, and each state after it;
    a controller per team (human or AI) drives `BattleScreen`; the Combat lab (Editor menu,
    `combat_lab.py`) sets up Scrapper, champion, brawl, capture the flag, Ribbit Brothers, Wilds
    and Old Road ambushes and the Ancient Ruins and logs into `combat_lab/<date>/<name>.jsonl`;
    campaign fights log into `saves/<world>/combat_logs/` while `record_play` is ON (git does not track
    `saves/`: run `scripts/archive_combat_logs.py` after playing and commit `combat_lab/campaign/`);
    `scripts/combat_analysis.py` reads them (action mix, how often a person matched the AI, a
    replay). What is left, in order:
    1. **Play the fights** (the user, in the Combat lab). **Scrapper at level 0 is done**: 10 fights,
       human (player 1) against the AI, in `combat_lab/2026-10-10/`. Left, 10 each: champion at 0-1,
       brawl and capture the flag at 1-3, Wilds and Old Road ambushes at 3, Ancient Ruins at 2-3,
       Ribbit Brothers at 3. Play to win, as you would in the campaign: the win rate comes out of the
       same logs and is the number to compare with the AI's benchmark rates. Then **two Ribbit
       Brothers fights human against human** (one decision list per side): one clean
       `boss-human-vs-human.jsonl` is in, one is still to play. The brothers changed on 2026-10-10
       (Peep and Ribit swap the Tongue for Webbed Feet, so no Lash).
    2. **Derive the policy** from the rows the way `play_analysis.py` derived the `human` economy
       profile: thresholds and priorities (when to focus fire, when to retreat, when to go for
       the flag). A new script over `combat_log.frames`.
    3. **Feed it to `ai.py`** and measure against the benchmark win rates above. The gauge is
       `scripts/combat_pairs.py` (the AI replays each logged fight through `combat_log.rebuild`, same dice
       before and after a change; campaign logs work too; `--fresh` plays unseen lab squads). Tried before
       step 5 and dropped or kept for free: Defend with a spare point (no change), an evil unit finishing a
       downed body only when no standing foe is in reach (kept, costs nothing), and waiting one turn
       instead of walking into a foe's reach (no gain on hunts). A fight swings about 8 points between runs.
    4. **Where the AI trails (read of two campaign saves, 2026-10-10).** The person won 60 of 62 fights
       (hunts and ambushes all); the AI replaying those squads wins hunts and ambushes almost as often, so
       **the gap is the arena**: Defend the Title, the Scrapper and the champion. The lost bout (day 45)
       is a 1-on-1 against a 32 HP foe the AI never beats. **Losses do write their `end` row.** Step 5
       studied the duels: they read as stat gaps more than decisions.
    5. **Tactics tried against a baseline (2026-10-11).** A better way to measure a change than the AI on
       both sides (where the two cancel out and a squad pair reads about 50%): the *challenger* plays the
       player's side with the new rule and the old `ai.py` plays the enemy's, same squads, same dice, over the
       72 finished logs x 40 trials. Baseline (the AI on both sides, after the intel and role changes):
       Scrapper 50%, the Pit's Scrapper 74%, champion 85%, hunts 89%, ambushes 93%, Defend the Title 26%.
       **Re-baselined 2026-10-11 with flanking in, `combat_pairs.py combat_lab --trials 40` (72 logs, the dice
       now fixed before the rebuild): Scrapper 49%, the Pit's Scrapper 71%, champion 91%, hunts 90%, ambushes
       93%, Defend the Title 26%.** Use these as the number to beat; a fight swings about 8 points between runs.
       **Kept:** flanking (a melee unit walks to the far side of a foe an ally already holds): 80.7% to 82.1%
       over all logs, every fight type equal or better. **Dropped, no gain or worse (arena subset, 20 logs):**
       focus fire (nearest first became weakest-reachable first with a crowd bonus, 58.6% to 56.9%), holding
       once to let a melee foe close and answering with two attacks (56.6%), demoralizing first (57.2%),
       and stopping an archer at its range (no ranged unit in the logs, identical). The arena duels did not
       move: Defend the Title stays at 26%, the lost bout is a stat gap (a 32 HP foe) and not a decision.
    Known limits of the lab: the opposing flag is always placed at random, an AI-run guild plants
    its own flag and skips its traps, and `ai.py` only knows the objectives of the enemy side.
- **Feed the recorded runs to the economy sim.** Two runs are kept in
  `recordings/2026-10-08/` (14 and 11 days, not 30; a third was judged not worth playing) with
  the `human_profile.json` that `scripts/play_analysis.py` makes from them. Run
  `economy_guild.py --policies human --profile recordings/2026-10-08/human_profile.json`.
  The `food_low_days` of 0 is real, not a recorder bug: the player shops the day the larder is
  empty (Potatoes, 4-5 days at a time), so the policy now shops *at* the threshold, not under
  it (`keep_fed(at_low=True)`). With that, all `human` guilds go hungry at some point, which
  is what the recordings show a person doing. It wipes 30-40% of 20 guilds, and that is the
  threshold, not the player: `hunt_min_level` 0.5 comes from three won hunts, and at 2.0 the
  wipe is 0% ([finding 20](economy_sim_v2.md)). **Analysed 2026-10-10 over four runs** (the two of 2026-10-08 and the 65- and 95-day saves in
  `recordings/2026-10-10/`, which add the Old Road ambushes; profile in
  `recordings/2026-10-10/human_profile_4runs.json`). The person won **68 of 70 fights** (hunts 48/48,
  ambushes 7/7, Scrapper 8/9, champion 4/4, Defend the Title 1/2). Medians: hunt at 0.71 HP and level
  0.36, bout cash $12.7 a member, food target 4.1 days, leave the yard on day 5. Run through the sim
  (`economy_guild.py --policies human --guilds 40`), the `human` guild is wiped in **65% at skill 0.8
  (the report's setting), 42% at 0.9, 30% at 0.95 and 0% at 1.0**, so the wipes are the fight win rate, not
  the thresholds (the hunt HP floor 0.92 to 0.71 alone takes the wipe from 25% to 60% at 0.8). At 1.0 the
  day-30 milestone comes in 28% of guilds, first on day 28, against 11-14 days by hand. **Decided 2026-10-10:** the report's default `--skill` is now 0.95 (it was 0.8; the verdicts did not change at
  0.95, the milestone still fails at 0%), and the sim's findings below were measured at 0.8. The day-96 wipe in the
  Gozatron save (three of five starved with $237 in hand after three days at 0 food) was the player clicking
  work without buying food; the map now raises a red card in the command bar when the larder is empty or low (`Guild.food_alert`). Then compare
  `human` with `lumber`, `balanced`, `climber`. Findings it should settle are in
  [economy_sim_v2.md](economy_sim_v2.md): the day-30 milestone, the Axe-first order, whether the
  ladder (yard, Scrapper, Games, Wilds) is how people really climb. What the runs show: the
  milestone gear (Axe each, Studded Leather or better each, strongbox) in 11-14 days against the
  sim's 49-80; the starting kit sold on day 0 to buy Axes (the sim never sells starting items);
  the Champion beaten on day 6 at combat 0 and day 12 at ~0.3; the library Dictionary mission
  turned in on day 11 (Paper + Ink bought, $250 paid). Known gaps: the other shops (Smith,
  Apothecary, Tanner) do not log purchases yet; HP before a fight is the squad's at the
  battle's start.
- **Sim policies that find the opportunities themselves.** **The offers list is built
  (`scripts/economy_offers.py`, 2026-10-10)**: one-off missions, bouts with their stake, kit worth
  selling and the work tools, each priced in copper and days; what is left is the planner that reads it
  (a hunt or forage mission's hours price one trip only, and a bout's win chance is not in the list). Every policy in `economy_guild.py` is
  a hand-written line (`rush` is the player's own, recorded). The recorded runs found things the
  earlier policies never tried: selling the starting kit on day 0, the Champion at the stake and
  not at combat 2, a one-off mission whose material is a Wilds trip away. Rebuild `maxev` (or a new
  planner) so it enumerates what is on offer (one-off missions and what each needs, bouts whose
  stake is covered, kit worth selling, gear that lifts the yard's wage), prices each in copper and
  days, and picks the order. Success is that it re-discovers the `rush` line unprompted and finds
  any line the recordings missed; `rush` stays as the reference. Then retire the guessed
  policies that it beats. Needs the planner, the offers listing (the missions, bouts and kit
  hooks the policies reach by hand today) and tests.
- **Finite stock and a target per item, in every shop.** Built 2026-10-11 in `economy.SHELVES`
  (item -> target, units a day) and `Shop.refill`: every item on the Market, the Yard, the Mine and the
  Library is finite, opens at its target and walks back a little each day (a slow item accrues a fraction;
  a surplus the player sold walks down; Hide has rate 0). The Smith, Tanner, Apothecary, Farm and
  Tavern shelves are now their own nodes' (*Specialised shops*).
  The report's verdicts did not change (the day-30 milestone still fails). A stray (an item the player sold
  a shop that is not on its shelf) is listed and resold there and stays until bought (the Library lists them on a
  RESALE tab). Left: (1) the Library's Paper 20/5 and Ink 10/2 and the Market's Lumber
  20/6 are my guesses, not from the table; (2) Jerky's $8 (tavern shelf, 10/3) is
  the batch (2 Meat + 1 Salt + 3 = $16) over its 2 units; (3) the sim's food buying now falls back to the next
  cheapest food when the cheapest runs out (a 12-day Claim trip outgrows 30 Potatoes).
- **Tune the specialised shops.** The Smithy, Tannery and Apothecary are nodes (0.5 h from Ankareth, 0.3 h between them), every node has its own shelf and the sim walks the round (2026-10-11; the report's
  verdicts did not change). What is left:
  - **Distances and bents are a first guess.** Re-run on 2026-10-11 (button labels in): verdicts unchanged, 0 exploits; the route scan (9 shops, a 43.6 h tour,
    a cap of $124/day, 10.3x the yard) is a cap and not income, and only the Mine's road makes the tour long, so `world.EDGES` stays until a playtest says the walk is wrong;
    the tongue of each shop follows its keeper's race, the alignments of the Tannery (Chaotic and Neutral),
    Library (Lawful and Evil) and Apothecary (Chaotic and Good) are authored; the Smithy (Lawful and Neutral),
    Tavern (Neutral and Good) and Farm (Lawful and Good) are picks to confirm, and so is the Farm's second
    tongue (Sylvan).
  - **Jerky is on the Tavern shelf** (10/3, $8). The report says it does not sell at a profit; check it
    does not undercut camp cooking (`cooking` tests, the Claim's food).
  - **Old saves** keep their Market stock as strays there (Axe, Potato...): harmless, listed and
    resold; a sweep on load would clean it.
  - **Production chain** (lumberjack -> carpenter, smith) and world-tied restocking are a later arc; the
    tanner holds the Shortbow and Light Crossbow until a carpenter exists.

## Art (made by hand, not code)

Portraits are engraved medallions in `gartok/assets/portraits/<race>/N.png`; the rest of the
art is game-icons.net SVG silhouettes. Portraits come from the `/gen-portrait` skill (local
Stable Diffusion + a LoRA trained on this pool, `scripts/gen_portrait.py`; about 7 minutes of
GPU a portrait, curated by hand). Each task below is its own sitting of art-making;
the ones that also need code say so. Order is the suggested priority.

- **Fill the short portrait pools.** Pools with 12+ portraits are complete (Goblin, Centaur, Kenku, Treefolk, Automaton, Gnoll, Gnome, Elf, Human, Orc, Kobold, Grippli, Halfling, Hobgoblin, Sprite). Remaining short (< 12): Ogre (3), Snake (3), Giant Spider (4), Donkey (4), Horse (4), Sheep (4), Ox (7), Wolf (8), Skeleton (9), Lizardfolk (11), Goliath (10), Dwarf (11), Zombie (3, the former `portraits/undead/`), Dragon (2), Snake Dragon (1).
- **Battle-board objects.** Dropped weapon, torch and the neutral corpse (`ground.py`) are
  drawn procedurally. Lowest priority.

## Epic

- **Riding and mounts.** Riding a Centaur ally is built (Mount / Dismount in `actions/support.py`, the
  `centaur_mount` talent; the AI rider since 2026-10-16). What is left is riding animals: a riding saddle enters
  `animals.TACK`; the rider and animal pair goes into combat. Controllable and AI-driven animals in combat (today the Shepherd's
  Sheep only stands still on the board) belong to this arc. The creature abstraction
  should not make it harder.
- **Auto battler with priority programming** (Siralim Ultimate style). Its own arc and
  branch: UI, AI and tests.

### Constraints for the wagon, animal and camp systems

Nothing there blocks anything; each item waits for a reason to build it. Keep these while
building them:

- The game is meant to get big (many groups, animals and wagons): shape these systems for
  that now and prefer the general model over a patch for the small case.
- Storage trades capacity for something: pack is free and goes to combat; chest and house
  are static and safe; a wagon is mobile, lost with the group, needs animals that eat and
  sets the trip's pace; pack animals sit between pack and wagon.
- Tack decides an animal's role (Pack Saddle carries, Harness pulls, a riding saddle later);
  the wagon is a box and transport is derived.
- Wagons never enter a battle map: when combat starts, passengers get off and fight.

---

# Needs more information

- **Magic as the vertical progression.** The biggest content gap; the arc's work is in *Ready to do -> Medium*.
  The schools are rival factions but not mutually exclusive for a character. Magic comes strictly before
  Archaeology. Still open, beyond that list: tier 2+ spells and any reputation penalty for rivalry.

- **Found-the-guild charter** (`draft_screen.py`, `vocation_screen.py`). Founding the guild should be the
  heaviest choice of the run: squad members die, the guild does not, and the player *is*
  the guild. The vocation is built (`vocations.py`, see RULES.md); what is left:
  - **Measure the Wilds perk.** The sim has the `wary` policy (`cautious` with the group always
    *Cautious*) and `--vocation`; `scripts/vocation_report.py` still does not price the Wilds
    perk. Compare `cautious` and `wary` under `--vocation wilds` at level 3+ (level 0 never
    reaches an ambush) and price the ambushes avoided.
  - **Price the Scholars' perk.** It is live since 2026-10-11 (`vocations.info_bonus`: +2 on the opening
    read and on Assess), and `vocation_report.py` does not price it yet; the perk's value is how much
    sooner a guild reads a foe, so it needs a fight-level measure, not a copper-a-day one.
  - **Oath (deferred, not scheduled)** (separate from the vocation): *what binds the members
    together, and how a stranger would tell someone belongs to the guild* (a creed, a mark, a code). It cannot be
    broken, but it can be changed. It has a mechanical side in two places: **cohesion**
    (`cohesion.py`, how members stay or leave) and a **combat/world rule** (something the
    guild will or will not do, trading a lock for a bonus). Not economy or per-faction
    reputation. Open: the list, the exact effects, how the guild is recognised in the world
    (does an NPC react to it?), and the cost of changing one.
  - **Presentation (the identity form is a `ui/draft_panel` component since 2026-10-10, the vocation screen too):** a live preview of the guild as choices are made,
    a richer composed banner, and an opening scene: a founding charter that writes itself
    line by line, signed with the banner and the oath, kept as the first entry of the
    guild's chronicle.

- **Sprite's *Nature Initiate* gives no free spell when already initiated** (`Unit.magic_sources` is a list without repeats since
  2026-10-13), unlike Faith Initiate; equalise if it ever matters. Share Magic stays battle-only on purpose.

- **Better food (not started; direction 2026-10-09: buffs for eating good food, which leads to a
  recipe book).** Food only quells hunger today and the Potato does that at the
  lowest price, so nothing else is worth buying. Add dishes that are better and dearer and spoil
  fast (a bonus for the meal, a short `lifespan`), so what rots matters and a larder is a choice.
  Marsh's slower rot (see the charter) is priced low until this lands. **Decided 2026-10-10 & 2026-10-12:**
  cooking is an ordinary craft activity, and eating the dish gives a temporary buff that moves
  one number for 24 h (HP, an attribute, advantage on a named kind of action...). Only the most recent meal
  buff is active by default, but the data model on `Unit` stores an active buff list to support future talents that
  allow multiple buffs simultaneously. Specific upcoming recipes built 2026-10-12: (1) Jerky (2 Meat + 1 Salt); (2) Roast Meat (pure Meat + campfire, quick cooked meat); (3) Fruit Compote (introduces new base item `Sugar`; Sugar + Vial + Fruit -> long-lasting Fruit Compote, preventing gathered fruit from spoiling in 24 h). Decided 2026-10-12: neither of these two new recipes grant temporary stat buffs; their purpose is food preservation (extending lifespan of raw gathered meat and fruit). Dishes with temporary stat buffs are explicitly scheduled for AFTER the magic arc. Open: future premium dishes that grant temporary buff stats per dish, and the cost to the economy sim
  (`cheapest_food_price` stops being the one price of a meal).

---

# Starting items waiting on another system

Each occupation starts with one item (`data.OCCUPATIONS`). Rule: every occupation's item
is useful and **unique to it**, as an occupation is only a weapon and an item. Items that
already work: Meat, Potato, Quiver, 1L Beer, 1sqm Hide, Iron Bar, Lumber, 1kg Coal, Stone Brick
(the Claim oven's material), First
Aid Kit, Lantern, Scroll, Dictionary, Salt, Ink, Rope and Chains (Capture), Bear Trap, Chisel (crafting tool for Signal Horn), Holy Symbol (the Faith rite consumes it). The Merchant starts with a Semi-precious Gemstone (a store of value), and Rotten Food is the Slave's on purpose (eating it makes you sick). These wait
for a system that does not exist yet:

- **Scissors** (Barber). For shearing sheep once player husbandry/farms land (Claim/property).
- **Pliers** (Goldsmith). High-yield, long-duration jewelry crafting recipes (generating substantial money and craftable artifacts).
- **Shovel** (Grave Robber). Archaeology at Ancient Ruins (scheduled after Magic arc).
- **Map.** Finds treasures and secret zones. Waits for those systems.
- **Compass.** Avoids getting lost on very long trips through unknown paths. Waits for a
  getting-lost system.
- **Deck of Cards.** A card minigame at the tavern, among others. Its own arc.
