# Backlog — everything still open

The one place for open work. It folds the playtest review (2026-10-05), the wagon and
camp to-do list and the later playtest notes. What is already built is in the code, its
tests and the git log; the long-range AI plan is
[campaign_ai_roadmap.md](campaign_ai_roadmap.md).

Sizes are estimates; claims about what the code already has were checked on 2026-10-12 (after cart currency pooling, fallen ally loot recovery, lackeys rename, wagon guard work XP, map roster group money, dynamic node tabs, draft rename & layout, rest accordion budgeting, lumber yard hub gathering tab, gathering tutorial, dynamic work XP recipes, keepers in game, field campfire cooking, CTF defender positioning, Carriage display on WatchScreen, Snake Antidote recipe, work tree CHA root, vehicle container in group screen, Roast Meat & Fruit Compote cooking recipes, classic start screen, and check_backlog audit). When an item is done, delete
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

# Suggested order (updated 2026-10-12 after wiki compendium & mentorship)

Goal read: a sandbox open-world guild manager; the run ends only on a wipe. Balance and
sim work is ahead of the content it balances, so the order favours content verticals and
the seams they need.

1. **Ledger Hold military frontier supply runs & hub unlock** (transport supplies from Ledger Hold to First Outpost under high ambush risk; requires minimum cargo capacity and travel speed).
2. **Weapon traits registry and 2-AP actions** (immutable keyword model in `weapon_traits.py`, followed by unique 2-AP weapon actions).
3. **Sim planner / offers integration** (`scripts/economy_offers.py` -> policy planner) to settle the day-30 milestone verdict against recorded runs.
4. **Magic as the vertical progression** (built on the *node that unlocks* mechanic once Ledger Hold / library maps land).

---

# Ready to do

## Small

- **Economy report prints a FAIL on the day-30 milestone.** `scripts/economy_report.py --quick`
  (re-run 2026-10-10, after the vocations: unchanged): the `balanced` policy reaches the milestone
  in 0% of guilds (need 50%), cost from $423. It is the known gap with the recorded runs (11-14
  days by hand), so it settles with *Feed the recorded runs* and the planner, not by tuning
  prices. **Decided 2026-10-10:** recalibrate the sim until it matches the recorded runs (both
  ~60-day saves reached day 30 easily), starting with the offers list (built). The run exits 1 on a failed verdict, but no test or gate reads it.
- **Enemy info: loose ends of the first version (built 2026-10-11).** (1) The thresholds are a first
  guess (`intel.BASE_DC` 8, bands at margin 0 / +5 / +10, `RACE_DISCOUNT` 2, `ASSESS_BONUS` 4): play
  and tune, and size the Scholars' +2 with `vocation_report.py` (the perk is live now, not yet priced).
  (2) With nobody in sight an *attacker* searches and a *defender* groups up (built 2026-10-11,
  `Battle.aggressor`, RULES.md). Left: the search is a coarse waypoint sweep (it ignores doors and
  cover), a defender only groups and never sets a line or a trap, the arena has no role, and
  `ai._skitter` (the Aurochs' run from the hunters in the Ox Fields) keeps measuring every foe: it
  is a beast's nose, not a player's.
  (3) The AI only assesses when it is
  cornered and out of reach (`ai._try_assess`): a policy for when a point is worth it (before a duel,
  against a boss) is open. (4) The foe card is tall once the HARD band opens and squeezes the action
  list at 720p: let it scroll or fold. (5) Allies' bars stay exact; whether the Guild screen's party
  rows or the Wilds rows should ever show a foe is moot, but the hunt and ambush screens show foes
  only on the board. (6) `combat_pairs.py` seeds the dice before the rebuild (the turn order was
  loose before); re-baselined 2026-10-11, see *Combat AI* step 5.
- **Mine leftovers (built 2026-10-09).** (1) *Iron Ore* is smelted into *Iron Bar* at the Blacksmith forge (`2x Iron Ore + 1kg Coal -> 1x Iron Bar`, built 2026-10-12). (2) The sim now has the `miner` and `miner_short` policies (stock up, walk past the Old Road,
  work 6 or 2 shifts, walk back). Result at level 0: with the AI's own fights 75-95% of the
  guilds are wiped on the road; with a player winning 80% (the report's setting then; it is 0.95 since 2026-10-10) `miner` earns
  $166 a member by day 30 against the yard's $67, reaches the day-30 milestone in 70% of guilds
  (every other policy: 0-20%) and loses 30% of them. A 2-shift stay is worse than the yard.
  So the $1 premium pays only for a long stay, and the Mine is the best way to the
  milestone. **Decided 2026-10-09: keep it** (the risk and the time are what it pays for); re-judge
  after a playtest, and if it is too strong a lower premium or a longer road is the lever, not a bigger one. The crafter policy
  still skips recipes that need Coal and no policy builds the Claim oven, so those two trips stay
  unpriced.

## Playtest notes 2026-10-12

Raw notes from a playtest, grouped; split each into a sized item as it is picked up. Guiding
rule from the notes: **fewest possible buttons on the map**: a node has one "Enter" button and
its functions are tabs inside.

**Map and node entry**
- **Travel graph is hard to read.** Decided 2026-10-12: algorithmic auto-layout rework avoiding edge crossings and treating highly connected nodes as central hubs.
- **Group swap with 2 groups feels odd.**
- **Start screen (built 2026-10-12):** classic main menu screen ("Continue", "Load Game", "New Game", "Editor", "Settings", "Wiki") replacing direct boot into the saves list in `menu_screen.py`.

**Layout overlaps (component rule; Market shelf, Bank quantity box, Load cards, Draft leader row attributes, Rest accordion budgeting and Tavern hub tabs fixed 2026-10-12)**
- **Carry-weight display differs between screens** (Tannery vs normal Market), and the *Carrier*
  talent: investigated 2026-10-12 -- both Tannery and Market share the exact same `MarketScreen` and `LoadoutMixin`. The perceived weight variance was due to temporary attribute drops from hunger/sickness altering the base carry threshold, and `_carry_relief` dynamically scaling only with non-weapon, non-consumable pack cargo as designed.

**Draft, leveling and talents**
- **Leveling templates:** player-made, editable autopick of talents, so the same clicks are not
  repeated every level.
- **Level up during a Wilds hunt:** attach the level-up modal to the unit's card in the hunt.
- **Craft sub-tree in work track (built 2026-10-12):** +1 INT root (`Clever`) with `Crafter` (+1 crafting progress) and `Linguist` (+2 language study rolls) at tier 2, and `Apothecary` / `Blacksmith` at tier 3.
- **No activity gives work XP past work level 4.** Nothing lets a character climb from work 4
  onward (`Signal Horn` is level 4, the current recipe ceiling). Decided 2026-10-12: XP past level 4 will come from
  (1) higher-tier, complex crafting recipes, (2) Ledger Hold military enlistment / border skirmishes work shifts, and
  (3) archaeology at Ancient Ruins. Built 2026-10-12: `progression.eligible_work_activities` dynamically inspects registered recipes up to level 4+.
- **In-game dynamic wiki / compendium (built 2026-10-12):** A searchable in-game encyclopedia screen generated dynamically
  from the game's data catalogs (`items`, `abilities`, `talents`, `recipes`, `data.BEASTS`, node functions and
  combat rules), accessible from StartScreen and from PauseScreen during active gameplay (Esc/back restores the exact paused scene state).
- **Perk to reduce armour weight.**
- **Craft talent:** converts Lumber into arrows daily, by a percentage.
- **Target equipment:** per unit, how it should be equipped; on entering a shop with an upgrade
  available it swaps by itself.

**Pack, cart and coins** (coins at the shops, bank, medic, stables, garage, licence, study rent and Claim now
read the cart and animals too, 2026-10-12: `Creature` has pack calls and `money`, `Group.money` / `Group.stores`;
a Dictionary at the tavern and Lumber at the Claim read stores too; guarding the wagon counts as level 1 work, 2026-10-12)
- **Locked stackable (e.g. Salt):** the distribution should fill the inventory with the lock first,
  within its load limit.
- **Cannot lock items in the cart.**
- **Cargo screen:** search by item name.

**Auto orders**
- **Programmable order chains for a group**, e.g. gather Lumber at the Yard -> sell Lumber and
  buy food -> gather again. Large; ties to `orders.py` and the sim's planner.

**Factions, nodes and world**
- **Bankers' trust test (resolved 2026-10-12):** Investigated and fixed: `TrustScreen` modal accept/leave buttons visually overlay the `ledger_hold` node position on the underlying map screen at standard resolutions; rapid double-clicks on modal close were passing mouse events directly to `MapScreen`, triggering an accidental travel order to Ledger Hold. Fixed by adding a 250ms click debounce window (`SCENE_DEBOUNCE_MS`) when transitioning to the map.
- **Ledger Hold as a guards faction hub (mentorship quest built 2026-10-12):** Ledger Hold is its own distinct faction.
  After completing the Bankers' trust test, visiting Ledger Hold offers a mission from Commander Varkas to mentor a designated level 0 Treefolk recruit (added to guild roster; tracked by unique `recruit_uid`; designated portrait `treefolk_recruit.png`; base attributes before racial modifiers: 13, 11, 12, 10, 10, 11). Once `racial_level >= 2`, turning the recruit in strips all gear and pack items back to the group, awards $230 reward and banks faction deeds. General Treefolk portrait pool expanded to 20 portraits (0..19). Decided 2026-10-12: first military work shift is "frontier supply run" (transporting resources from Ledger Hold to First Outpost under high ambush risk, requiring minimum cargo capacity and travel speed).
- **Iron Bar smelting (built 2026-10-12):** 2x Iron Ore + 1kg Coal at the Blacksmith forge produces 1x Iron Bar (`CRAFTING_RECIPES`, `CraftingStation.FORGE`).
- **Ancient Ruins as an archaeological site:** start "archaeology" work there (deferred to after the magic arc).
  Decided 2026-10-12: complex system requiring tools (Shovel/Pick), multi-step iterations and costs to unearth artifacts, money and lost lore.
- **The Claim:** let the player build their own farm to stock food.

**Combat and AI** (allies recover worn armor, off-hands and artifacts on won battle loot screen, 2026-10-12;
henchmen renamed to Lackeys, 2026-10-12; CTF AI defender holding home flag square built 2026-10-12;
Ribbit Brothers defeated deed, post-battle recruit prompt on tavern screen and arena cameo built 2026-10-12)

**Balance question**
- **Which stats matter.** Playtest feel: CON > STR > DEX > CHA > INT > WIS in importance. Negative STR/CON is very punishing
  (armour is hard to wear, healing is slow); low CHA caps guild growth; the mental stats hurt little.
  Decided 2026-10-12: keep current stat severity for now; revisit attribute weighting and severity after the magic arc lands.

---

## Architecture debt

Past choices that now fight the direction. Each has the cost of fixing it; pay one when the
feature that needs it is next, not before. Debts already written as part of a feature are
pointed to, not repeated.

- **Weapon traits are ad-hoc fields.** `ItemDef.finesse` / `thrown` plus hand-written `if`s in
  the description builder; every new weapon is a new `if`. Blocks the 2-AP action per weapon.
  **Cost: medium** (a registry like `abilities.py`). Detail under *Weapons that are really
  different*.
- **Big screen files.** `app.py` (about 1200 lines, 107 `def`s) is the wiring hub; `map_screen.py`,
  `market_screen.py` and `battle_screen.py` run about 900-1100 (the last two are past 1000). Not critical. When one takes a new node
  or tab, split by concern instead of growing it. **Cost: low per split.**
- **Saves have no migration (on purpose).** Fine while the author is the only player. Before
  any outside playtest decide: keep "an older shape does not load" with a clear message, or add
  a version bridge. **Cost: low (message) to medium (bridge).**

## Large

- **Talent trees are shorter than the level cap (to be authored by hand, no rush).** The XP
  tables now run to level 15 (2026-10), but the trees do not: combat has 14 nodes and work 10
  (each level grants one pick), so combat 15 wastes a pick and work levels 11-15 grant picks with
  nothing to spend them on. The racial track (picks from racial level 5) is worse: its 27 nodes
  are split across races, so most races have almost none of their own and a high racial level
  buys hit dice only (the Aurochs has zero). Goal: **at least 30 combat and 30 work talents**,
  and enough racial nodes per race for its picks. Nothing built; the author will design them.
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
- **Weapons that are really different (two tracks, both to build).**
  1. **Named weapon traits (decided 2026-10-12: immutable model, central keyword registry mirroring `abilities.py`).** `ItemDef` carries
     ad-hoc fields (`finesse: bool`, `thrown: int`)
     and each trait's rule text is a hand-written `if` in the description builder. Model them as
     an immutable registry of named keywords (Finesse, Thrown, Entangle...) like `abilities.py`, so a new
     weapon is declared by listing traits and the code, UI text and `REFERENCE.md` read from one
     place.
  2. **A 2-AP action per weapon kind.** Every weapon keeps the basic attack; each kind also gets
     its own two-point action. A trait may grant an action.
  - **First step:** audit the weapon catalog for what any two share (die, hands, range, trait)
    and what makes each unique; the audit decides the traits and the actions. Needs AI and tests.
- **Prisoners.** (Not started; decided 2026-10-09: lands after the specialised shops.) Non-lethal attacks that knock a unit out even in lethal zones, then
  capture it. Chains are what holds the captive. Needs the AI to know it too.
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

- **Art for content already in this backlog.** The Cart and Carriage (`wagon.Vehicle`). Both `carriage.png` and `cart.png` installed in `portraits/npc/` and wired into vehicle displays (2026-10-12). Keepers resolved:
  (1) The Medic is Pimbletwig himself, sharing the Apothecary's keeper art.
  (2) Stables at the Farm are run by Edric Ashvale himself (`farmer.png`), no new keeper needed.
  (3) Arena Master: Goliath pit master Thok'Gar (`portraits/npc/arena_master.png`) wired in `world.NODES`.
- **Snake Dragon (future creature).** `portraits/snake_dragon/0.png` exists. Decided 2026-10-12: reserved for one of the magic questlines following the Library's codex / trust sequence; deferred to when the post-library magic quests are built.
- **Fill the short portrait pools.** Updated 2026-10-12: Wolf reached 8, Skeleton reached 9,
  Ox reached 7, Sheep pool created (4), Goliath reached 10, and Goblin reached 12.
  Remaining short: Snake (3), Giant Spider (4), Donkey (4), Horse (4), Kenku (8), Centaur (12).
- **Map node icons.** The 19 nodes share three kinds of glyph (`map_screen.KIND_ICON`; the Lumber Yard and the Mine
  share the work glyph, and the Smithy, Tannery and Apothecary the `town` house). Give Ankareth, Arena, Market, Tavern, Prison, Library, Farm, Ancient
  Ruins, the Claim, the Mine, the Smithy, the Tannery and the Apothecary a mark of their own. The map works as it is, so this is polish.
- **Occupation icons.** `icons/body` and `icons/hat` are staged and nothing loads them. If
  the character sheet is to show the vocation, pick a consistent icon per occupation (18 or
  more). Depends on the sheet calling it.
- **Battle-board objects.** Dropped weapon, torch and the neutral corpse (`ground.py`) are
  drawn procedurally. Lowest priority.

## Epic

- **Riding and mounts.** A riding saddle enters `animals.TACK`; the rider and animal pair
  goes into combat. Controllable and AI-driven animals in combat (today the Shepherd's
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

- **Magic as the vertical progression.** The biggest content gap (only the library tome quest
  exists). Blocked on the *node that unlocks* mechanic below. Follows the library's tome quest. Chain:
  1. After the tome quest, at reputation 3 with the Library, they hand over a **map** that
     unlocks a new place.
  2. An intermediate mission to earn their trust in the guild.
  3. Then the Library sends the codex to one of the **three magic factions** (Blood mages,
     Nature mages, Faith mages), where the magic line proper begins.
  - **New mechanic to build first (decided: a general one): a node that unlocks.** Every node
    is revealed or not, and an event flips it (reading a map, completing a deed, reaching a
    reputation). The map is the first user. Nothing does that today. The Mine does *not*
    use it: it is a plain node. **Open:** whether the flip happens once and stays (recommended);
    Reading the map does not consume it (decided). The revealed set lives in the guild's save (decided; a new optional field `revealed`, a list of node ids, neutral value `[]` in `persist.PAYLOAD_DEFAULTS`).
  - **To define:** the exact reputation gate and the intermediate mission; the three
    factions as nodes with their own deeds (see `factions.py`); how each school's study
    differs (`magic.py`); the three schools are **not exclusive** (decided 2026-10-09: anyone may study any; the barrier is study cost). Holy Symbol (below) belongs to
    the faith school.

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

- **Magic sources (for the magic arc, decided 2026-10-10).** `Unit.magic_source` holds one source.
  Make it a set: a unit already initiated who takes another school's initiation (Kenku or Skeleton
  *Faith Initiate*) trains in it too, as the schools are not exclusive. Touches `can_study_spell`,
  the save, the char editor, `sheet_card` and the tavern screen. Today it is invisible, since
  Kenku, Skeleton and Sprite start with no source. Share Magic stays battle-only on purpose.
  Sprite's *Nature Initiate* gives no free spell when already initiated, unlike Faith Initiate;
  equalise if it ever matters.

- **Better food (not started; direction 2026-10-09: buffs for eating good food, which leads to a
  recipe book).** Food only quells hunger today and the Potato does that at the
  lowest price, so nothing else is worth buying. Add dishes that are better and dearer and spoil
  fast (a bonus for the meal, a short `lifespan`), so what rots matters and a larder is a choice.
  Marsh's slower rot (see the charter) is priced low until this lands. **Decided 2026-10-10 & 2026-10-12:**
  cooking is an ordinary craft activity, and eating the dish gives a temporary buff that moves
  one number for 24 h (HP, an attribute, advantage on a named kind of action...). Only the most recent meal
  buff is active by default, but the data model on `Unit` stores an active buff list to support future talents that
  allow multiple buffs simultaneously. Specific upcoming recipes built 2026-10-12: (1) Jerky (2 Meat + 1 Salt); (2) Roast Meat (pure Meat + campfire, quick cooked meat); (3) Fruit Compote (introduces new base item `Sugar`; Sugar + Vial + Fruit -> long-lasting Fruit Compote, preventing gathered fruit from spoiling in 24 h). Decided 2026-10-12: neither of these two new recipes grant temporary stat buffs; their purpose is food preservation (extending lifespan of raw gathered meat and fruit). Cooking recipes take priority over jewelry crafting. Open: future premium dishes that grant temporary buff stats per dish, and the cost to the economy sim
  (`cheapest_food_price` stops being the one price of a meal).

---

# Starting items waiting on another system

Each occupation starts with one item (`data.OCCUPATIONS`). Rule: every occupation's item
is useful and **unique to it**, as an occupation is only a weapon and an item. Items that
already work: Meat, Potato, Quiver, 1L Beer, 1sqm Hide, Iron Bar, Lumber, 1kg Coal, Stone Brick
(the Claim oven's material), First
Aid Kit, Lantern, Scroll, Dictionary, Salt, Ink, Rope, Bear Trap. The Merchant starts with a Semi-precious Gemstone (a store of value), and Rotten Food is the Slave's on purpose (eating it makes you sick). These wait
for a system that does not exist yet:

- **Scissors** (Barber). For shearing sheep once player husbandry/farms land (Claim/property).
- **Pliers** (Goldsmith). High-yield, long-duration jewelry crafting recipes (generating substantial money and craftable artifacts).
- **Shovel** (Grave Robber). Archaeology at Ancient Ruins.
- **Chisel** (Sculptor). Carving the Legendary Horn (`Signal Horn`, built) and artistic stonework.
- **Map.** Finds treasures and secret zones. Waits for those systems.
- **Compass.** Avoids getting lost on very long trips through unknown paths. Waits for a
  getting-lost system.
- **Deck of Cards.** A card minigame at the tavern, among others. Its own arc.
- **Holy Symbol.** Required, together with everything else, to start in faith magic.
