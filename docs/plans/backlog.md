# Backlog — everything still open

The one place for open work. It folds the playtest review (2026-10-05), the wagon and
camp to-do list and the later playtest notes. What is already built is in the code, its
tests and the git log; the long-range AI plan is
[campaign_ai_roadmap.md](campaign_ai_roadmap.md).

Sizes are estimates; claims about what the code already has were checked on 2026-10-11 (after the info modal and the AI's flanking). When an item is done, delete
it here and, if it changed a design premise, record it in `AGENTS.md` or the doc that owns it.

Parts:

- **Ready to do** — the task is defined enough to start. Sorted by size: small (a sitting),
  *Architecture debt* (past choices to pay when a feature needs them), large (a system: UI,
  AI and tests), *Art* (made by hand) and epic (its own arc).
- **Needs more information** — a design question, a repro or another system has to land
  before the task can be sized.
- **Starting items waiting on another system** — not a question: a list of items whose
  system does not exist yet.

The *Suggested order* below comes first.

---

# Suggested order (project review, 2026-10-09; updated 2026-10-11 after the info modal and the AI tactics)

Goal read: a sandbox open-world guild manager; the run ends only on a wipe. Balance and
sim work is ahead of the content it balances, so the order favours content verticals and
the seams they need.

1. **Item properties** (design first), which reads the sources gathering created (built 2026-10-11),
   then the specialised shops and finite stock.
2. The sim's planner (*Sim policies that find the opportunities themselves*), now that the offers
   list exists (`scripts/economy_offers.py`), to settle the day-30 verdict against the recorded runs.
3. The AI's first tactics are built (2026-10-11, `intel.py`, RULES.md; flanking helped, focus fire,
   holding and demoralizing first did not, see *Combat AI*). The arena duels it loses (Defend the Title,
   the day-6 Scrapper) look like stat gaps more than decisions: leave them.
4. The *Architecture debt* section lists what to pay on the way.

Magic comes after the *node that unlocks* mechanic; it is the next big content gap.

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
- **Starting tools with no job: Scissors, Pliers.** Scissors and Pliers wait on a recipe that
  lists them in `tools`, the Chisel on the Horn and Chains on *Prisoners*. The Shovel has no job either: the Mine
  works with the Pick, which the Miner already starts with.
- **Mine leftovers (built 2026-10-09).** (1) Gathering at the Mine is built (2026-10-11, see *Gathering: loose ends*); the gems it yields are *semi-precious* and *precious gemstones*. (2) *Iron Ore* has no recipe or
  use until the Smith's chain exists. (3) The sim now has the `miner` and `miner_short` policies (stock up, walk past the Old Road,
  work 6 or 2 shifts, walk back). Result at level 0: with the AI's own fights 75-95% of the
  guilds are wiped on the road; with a player winning 80% (the report's setting then; it is 0.95 since 2026-10-10) `miner` earns
  $166 a member by day 30 against the yard's $67, reaches the day-30 milestone in 70% of guilds
  (every other policy: 0-20%) and loses 30% of them. A 2-shift stay is worse than the yard.
  So the $1 premium pays only for a long stay, and the Mine is the best way to the
  milestone. **Decided 2026-10-09: keep it** (the risk and the time are what it pays for); re-judge
  after a playtest, and if it is too strong a lower premium or a longer road is the lever, not a bigger one. The crafter policy
  still skips recipes that need Coal and no policy builds the Claim oven, so those two trips stay
  unpriced. (4) The Mine has no art or map icon of its own (it uses the
  work glyph), and no tutorial line.

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
  the licence) are in. Left: (1) the numbers are a first cut (Yard Lumber 75 / Fruit 25, Mine Stone 55 /
  Coal 25 / Iron Ore 15 / semi-precious 4 / precious 1, a roll per 8 h, licences $180 and $225, risk 0.5%
  and 1% an hour): play and tune. Sim read over 90 days (20 guilds of 3 at level 0, skill 0.95): median money a member at day 30 / 60 / 90 is
  $51 / 125 / 207 for `lumber` and $30 / 71 / 139 for `gatherer`, and 5 of 20 `gatherer` guilds are wiped by
  the pack (none by `lumber`). **The licence does not pay back in the sim:** with the ambush switched off the
  gatherer still ends at $147, because the +2 copper a shift the table adds is eaten by what the sim makes
  it pay to cash the haul in (a walk to the Market, about 1.2 days a step, and Fruit that rots on the way).
  The Yard has no shop of its own to sell Lumber to. Decide whether the Yard should buy what it yields
  (a till, like the Mine's), or the margin should be wider; `miner` is wiped on the road as before. (2) The sim plays the gathering ambush (`gather:<node>`) as real battles of the node's own pack, but
  with no recorded fights of a person against these packs, the win rate is the AI's or the skill knob's. (3) The
  shift picker shows the drops and the rolls but not the average worth of a shift against the wage.
  (4) **Snakes:** the Yard's packs were meant to include snakes, but there is no snake race (`data.BEASTS`); add one (venom, small, low HD) and put it in `encounters.LUMBER_YARD_TABLE`. (5) The Mine and the Yard have no
  tutorial line of their own beyond the map card, and no art for the Mine. (6) Coal and the gems have no use but to be sold (Coal waits for the Smith's chain); Fruit is
  food, but it rots in a day, so a Yard crew eats it or sells it that evening.
- **Item properties: base material, source, rarity (design first, feeds the economy).** Every
  item is craftable except the **base materials**: an item with no recipe is a base material
  (derived, like `craft_level.py`, not set by hand), and each one must **declare its source**:
  gathered at a node (Lumber, Fruit, Stone Brick, Coal, Iron Ore: built, `gather.TABLES`), hunted (Meat, Hide) or a gem (*semi-precious* and *precious
  gemstones*, gathered at the Mine, never crafted). A test checks that no item lacks both a
  recipe and a source. Rarity then says how scarce each base material is, and the chain
  (source -> recipe -> sale) is what the economy sim and the per-shop stock targets read.
  Do this before *Finite stock and a target per item*.
- **Weapons that are really different (two tracks, both to build).**
  1. **Named weapon traits (decided: a registry like `abilities.py`).** `ItemDef` carries
     ad-hoc fields (`finesse: bool`, `thrown: int`)
     and each trait's rule text is a hand-written `if` in the description builder. Model them as
     a registry of named keywords (Finesse, Thrown, Entangle...) like `abilities.py`, so a new
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
  work without buying food; the map now raises a red banner when the larder is empty or low (`Guild.food_alert`). Then compare
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
- **Finite stock and a target per item, in every shop.** Split from *Specialised shops*: the
  `shop` function (a `Shop` per node, `Guild.shop(node_id)`) landed without changing a rule, so
  most of `MARKET_STOCK` is still infinite and only `economy.STOCK` items are finite, now per
  shop. Make every item finite in every shop, with a target count per shop and item that the
  shelf walks back to a little each day; a shop buys any item at 50% and resells it at 100%.
  First step: the target table and the refill rate (see the numbers in *Specialised shops*).
  Re-run `scripts/economy_report.py`, since this changes the whole economy.
- **Specialised shops.** Split the single general market into shops, each its own node
  with a walking distance between them, so the player has to go around. The market's
  finite cash is built (`Guild.shop(node_id)`, one `Shop` per node offering `shop`), so each shop
  gets its own.
  The production chain (lumberjack -> carpenter, smith) and restocking tied to the world
  are a later arc; this task is the structure with a fixed restock.
  - **Shops:** Smith, Apothecary and Tanner are new nodes outside the city (today `forge`,
    `apothecary` and `tanner` are functions of `city`, with no till of their own). The Smith and the Apothecary take their
    crafting with them, as tabs. Farm (today only the stables), Tavern, Lumber Yard (a shop
    *and* a work node), the Mine (the same, with its own shelf) and Market already exist. Rough split: Smith = weapons, shields,
    metal armour, Iron Bar; Tanner = leather armour, Cloak, Hide, Quiver; Apothecary =
    potions, Vial, First Aid Kit; Farm = raw food and Salt; Tavern = Beer and Jerky (the only
    ready-made food today); Lumber Yard = Lumber; Mine = Stone Brick, Iron Ore and Coal;
    Market = the rest (Torch, Lantern, traps).
  - **Prices and stock:** one base price everywhere. Every item is finite in every shop. A
    shop buys any item at 50% and puts it on its shelf to resell at 100%. Each item has a
    target count per shop and the shop walks back to it a little each day. Since every shop
    resells everything, the targets are what makes each one specialised.
  - The Library joins the same rule (stock target, finite cash, buys anything at 50%) and
    keeps its other tabs.
  - **Node distances:** the new nodes need a walking distance from Ankareth, and the
    existing ones (Market and Library 1 h, Farm 2 h) should be reviewed together with them,
    since the distance is the cost of going around between shops.
  - **First step:** define the stock target per item and per shop, and the daily refill
    rate. A first estimate from the economy sim's restock sweep
    ([economy_sim_v2.md](economy_sim_v2.md), finding 6): a shelf of about 10 refilling 3 a
    day keeps a crafting specialist at about 2x a lumberjack's wage; below 4 with 1 a day
    makes crafting for sale pointless. Open: AI and tests.

## Art (made by hand, not code)

Portraits are engraved medallions in `gartok/assets/portraits/<race>/N.png`; the rest of the
art is game-icons.net SVG silhouettes. Portraits come from the `/gen-portrait` skill (local
Stable Diffusion + a LoRA trained on this pool, `scripts/gen_portrait.py`; about 7 minutes of
GPU a portrait, curated by hand). Each task below is its own sitting of art-making;
the ones that also need code say so. Order is the suggested priority.

- **Art for content already in this backlog.** The Mine, Smith, Apothecary and Tanner nodes
  and the Cart and Carriage (`wagon.Vehicle`; `watch_screen.py` is text only today). The
  shopkeepers' faces are made: `portraits/npc/` holds `merchant.png` (Automaton), `tanner.png`
  (Gnoll), `librarian.png` (Kobold) and `blacksmith.png` (Dwarf). **Built 2026-10-10:** each vendor has a
  name (from `names.py`, fixed per node) and a face in the header of the Market, the Library (shop, craft and
  jobs), the Forge and the Tanner (`world.Vendor`, `ui/vendor_panel.py`), so the player learns to recognise who
  they haggle with. Left: the Apothecary and the Mine have no portrait, and a vendor is not an NPC (no stats,
  no recruiting or robbing them).
- **Fill the short portrait pools.** Beasts have 4 each (Giant Spider, Donkey, Ox, Horse) and
  the Wolf 6; the Skeleton has 6. The Wolf is the only beast the Wilds rolls, so take it to 8
  or more first. Goblin has 7, Kenku 8 and Goliath 8 against 12 for Human, Elf, Gnome, Centaur
  and Orc (Halfling has 14, Grippli 17).
- **Map node icons.** The 14 nodes share three kinds of glyph (`map_screen.KIND_ICON`; the Lumber Yard and the Mine
  share the work glyph). Give Ankareth, Arena, Market, Tavern, Prison, Library, Farm, Ancient
  Ruins, the Claim and the Mine a mark of their own. The map works as it is, so this is polish.
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
  Marsh's slower rot (see the charter) is priced low until this lands. **Decided 2026-10-10:**
  cooking is an ordinary craft activity, and eating the dish gives a temporary buff that moves
  one number for 24 h (HP, an attribute, advantage on a named kind of action...). Open: the
  list of dishes and their buffs, how a buff is stored on the unit (a timed condition, like
  sickness), and the cost to the economy sim (`cheapest_food_price` stops being the one price
  of a meal).

---

# Starting items waiting on another system

Each occupation starts with one item (`data.OCCUPATIONS`). Rule: every occupation's item
is useful and **unique to it**, as an occupation is only a weapon and an item. Items that
already work: Meat, Potato, Quiver, 1L Beer, 1sqm Hide, Iron Bar, Lumber, 1kg Coal, Stone Brick
(the Claim oven's material), First
Aid Kit, Lantern, Scroll, Dictionary, Salt, Ink, Rope, Bear Trap. The Merchant starts with a Semi-precious Gemstone (a store of value; the Amethyst is gone from the game), and Rotten Food is the Slave's on purpose (eating it makes you sick). These wait
for a system that does not exist yet:

- **Map.** Finds treasures and secret zones. Waits for those systems.
- **Compass.** Avoids getting lost on very long trips through unknown paths. Waits for a
  getting-lost system.
- **Deck of Cards.** A card minigame at the tavern, among others. Its own arc.
- **Holy Symbol.** Required, together with everything else, to start in faith magic.
