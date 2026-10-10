# Backlog — everything still open

The one place for open work. It folds the playtest review (2026-10-05), the wagon and
camp to-do list and the later playtest notes. What is already built is in the code, its
tests and the git log; the long-range AI plan is
[campaign_ai_roadmap.md](campaign_ai_roadmap.md).

Sizes are estimates; claims about what the code already has were checked on 2026-10-10 (after the Combat lab and vocations commits). When an item is done, delete
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

# Suggested order (project review, 2026-10-09)

Goal read: a sandbox open-world guild manager; the run ends only on a wipe. Balance and
sim work is ahead of the content it balances, so the order favours content verticals and
the seams they need.

1. Play the combat recordings (the Combat lab is built) and derive the AI's policy from them;
   the economy is calibrated against a player the AI does not match yet.
2. The *Architecture debt* section lists what to pay on the way.

Magic comes after the *node that unlocks* mechanic; it is the next big content gap.

---

# Ready to do

## Small

- **Economy report prints a FAIL on the day-30 milestone.** `scripts/economy_report.py --quick`
  (re-run 2026-10-10, after the vocations: unchanged): the `balanced` policy reaches the milestone
  in 0% of guilds (need 50%), cost from $423. It is the known gap with the recorded runs (11-14
  days by hand), so it settles with *Feed the recorded runs* and the planner, not by tuning
  prices. The run exits 1 on a failed verdict, but no test or gate reads it.
- **Signal Horn has no line in the economy report.** The chain is built (Tanner missions,
  Aurochs, `items.CRAFTING_RECIPES["Signal Horn"]` with a Chisel); `scripts/economy_report.py`
  still lacks a craft-for-sale line for it. The ox's portrait is under *Art*.
- **Starting tools with no job: Scissors, Pliers.** Scissors and Pliers wait on a recipe that
  lists them in `tools`, the Chisel on the Horn and Chains on *Prisoners*. The Shovel has no job either: the Mine
  works with the Pick, which the Miner already starts with.
- **Mine leftovers (built 2026-10-09).** (1) *Amethyst* was meant as a Mine drop, but a shift only pays the wage: the Mine is work,
  not gathering. **Decided 2026-10-09: wait** until the Mine gets gathering of its own, then the
  Amethyst drops from it (rare enough not to beat the wage; the stone is worth $120). (2) *Iron Ore* has no recipe or
  use until the Smith's chain exists. (3) The sim now has the `miner` and `miner_short` policies (stock up, walk past the Old Road,
  work 6 or 2 shifts, walk back). Result at level 0: with the AI's own fights 75-95% of the
  guilds are wiped on the road; with a player winning 80% (the report's setting) `miner` earns
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
- **Big screen files.** `app.py` (1240 lines, 108 `def`s) is the wiring hub; `map_screen.py`,
  `market_screen.py` and `battle_screen.py` run 865-1024 (`battle_screen.py` is past 1000 since the
  per-team controllers). Not critical. When one takes a new node
  or tab, split by concern instead of growing it. **Cost: low per split.**
- **Saves have no migration (on purpose).** Fine while the author is the only player. Before
  any outside playtest decide: keep "an older shape does not load" with a clear message, or add
  a version bridge. **Cost: low (message) to medium (bridge).**

## Large

- **Talent trees are shorter than the level cap (to be authored by hand, no rush).** The XP
  tables now run to level 15 (2026-10), but the trees do not: combat has 14 nodes and work 10
  (each level grants one pick), so combat 15 wastes a pick and work levels 11-15 grant picks with
  nothing to spend them on. The racial track (picks from racial level 5) is worse: its 26 nodes
  are split across races, so most races have almost none of their own and a high racial level
  buys hit dice only (the Aurochs has zero). Goal: **at least 30 combat and 30 work talents**,
  and enough racial nodes per race for its picks. Nothing built; the author will design them.
- **Item properties: base material, source, rarity (design first, feeds the economy).** Every
  item is craftable except the **base materials**: an item with no recipe is a base material
  (derived, like `craft_level.py`, not set by hand), and each one must **declare its source**:
  gathered at a node (Lumber, Iron Ore), hunted (Meat, Hide) or loot (Amethyst, which is a base
  material, found as a Mine drop, never crafted). A test checks that no item lacks both a
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
- **Intelligence reveals enemy info (combat info modal).** The modal today carries
  information that should not be there and lacks some that would help. Rework it around
  INT as the way to learn about enemies, so INT helps the player decide (and later the AI).
  - **Always visible, no INT:** name, race, weapon in hand, visible conditions, health in
    bands (unhurt / wounded / near death) and anything the active unit can simply see.
  - **Passive:** when a fight starts, each ally rolls an INT check against the enemies they
    face; what it reveals (exact HP, AC, MD, attacks, bonuses, abilities) is stored on the
    enemy and shared by the whole squad.
  - **Action:** an Assess action (AP cost) to dig further into one target.
  - **Scholars perk (decided 2026-10-10, built with this modal):** the Scholars vocation gives the
    whole guild a bonus on the INT roll that reveals enemy info (passive and Assess). Size it at
    about the Kobold's +2 and check it with `vocation_report.py`. Until the modal exists the
    vocation is dormant and the draft shows it as "no effect yet".
  - **To define while building:** which field sits behind which success margin, how the
    check scales with the target's level, whether knowledge outlasts the fight (a creature
    met before). Needs the action, AI support and tests.
- **Prisoners.** (Not started; decided 2026-10-09: lands after the specialised shops.) Non-lethal attacks that knock a unit out even in lethal zones, then
  capture it. Chains are what holds the captive. Needs the AI to know it too.
- **Combat AI plays far below a person.** Every economy number depends on how often the
  squad wins, and a person wins far more than `ai.py` does: measured in the economy report
  (layer 1 prints the AI's own win rate beside the skilled ones), the AI wins the Scrapper
  95%, the champion bout 75%, a Games brawl 43%, capture the flag 37%, a Wilds ambush at
  level 3 61% and the Ribbit Brothers 7%. A person wins the Pit's bouts "almost always".
  Goal: AI win rates close to a competent player's on those benchmark fights, so the sim
  (and `autowin`) stop needing a `--skill` knob. **Benchmark scenarios (decided):** Scrapper,
  Games brawl, champion, capture the flag, Ribbit Brothers, dungeon and ambush (wolves and
  bandits); the player's recorded fights on these train the policy. Start from what the AI
  does badly in the Games (objective play in capture the flag, focus fire, using the terrain), re-run
  `scripts/economy_activities.py` as the gauge. Needs AI changes, tests and `sim_test.py`.
  - **Way in: record the player's combat, as was done for the economy.** The recorder is built
    (2026-10-10): `combat_log.py` writes one JSONL file per fight with the whole fight, every
    decision with its legal options and what `ai.py` would have done, and each state after it;
    a controller per team (human or AI) drives `BattleScreen`; the Combat lab (Editor menu,
    `combat_lab.py`) sets up Scrapper, champion, brawl, capture the flag, Ribbit Brothers, Wilds
    and Old Road ambushes and the Ancient Ruins and logs into `combat_lab/<date>/<name>.jsonl`;
    campaign fights log into `saves/<world>/combat_logs/` while `record_play` is ON;
    `scripts/combat_analysis.py` reads them (action mix, how often a person matched the AI, a
    replay). What is left, in order:
    1. **Play the fights** (the user, in the Combat lab; the 12 human-against-AI
       tries of 2026-10-10 were thrown away: the AI's walking was not in the log, fixed since,
       and they were played at levels off this list). A first target, 10 fights each,
       human (player 1) against the AI, at the level the economy expects of that fight:
       Scrapper at level 0, champion at 0-1, brawl and capture the flag at 1-3, Wilds and Old
       Road ambushes at 3, Ancient Ruins at 2-3, Ribbit Brothers at 3. Play to win, as you
       would in the campaign: the win rate comes out of the same logs and is the number to
       compare with the AI's benchmark rates. Then **two Ribbit Brothers fights human against
       human** (one decision list per side). The tainted 2026-10-10 try was dropped; one clean
       `boss-human-vs-human.jsonl` is in, one is still to play. The brothers changed on
       2026-10-10 (Peep and Ribit swap the Tongue for Webbed Feet, so no Lash).
    2. **Derive the policy** from the rows the way `play_analysis.py` derived the `human` economy
       profile: thresholds and priorities (when to focus fire, when to retreat, when to go for
       the flag). A new script over `combat_log.frames`.
    3. **Feed it to `ai.py`** and measure against the benchmark win rates above. The gauge is
       `scripts/combat_pairs.py` (the AI replays each logged squad, same dice before and after a change,
       plus `--fresh` for unseen squads). Baseline at level 0, Scrapper: the AI wins 59% of the 10 logged
       squads (the person 7 of 10) and 56% of unseen ones, not the 95% the report prints. Leads from the
       10 Scrapper logs: the person holds position where the AI walks up (19 of 278 decisions) and
       focuses fire more (89% against 77%); tried and dropped: Defend with a spare point (no change, the
       AI already ends only 5% of its turns with a point left, a person 23%).
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
  wipe is 0% ([finding 20](economy_sim_v2.md)). Settling it needs a third run (to be played by
  the user, after the vocations land), and it must include an ambush on the Old Road, which neither run touched. Then compare
  `human` with `lumber`, `balanced`, `climber`. Findings it should settle are in
  [economy_sim_v2.md](economy_sim_v2.md): the day-30 milestone, the Axe-first order, whether the
  ladder (yard, Scrapper, Games, Wilds) is how people really climb. What the runs show: the
  milestone gear (Axe each, Studded Leather or better each, strongbox) in 11-14 days against the
  sim's 49-80; the starting kit sold on day 0 to buy Axes (the sim never sells starting items);
  the Champion beaten on day 6 at combat 0 and day 12 at ~0.3; the library Dictionary mission
  turned in on day 11 (Paper + Ink bought, $250 paid). Known gaps: the other shops (Smith,
  Apothecary, Tanner) do not log purchases yet; HP before a fight is the squad's at the
  battle's start.
- **Sim policies that find the opportunities themselves.** Every policy in `economy_guild.py` is
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
art is game-icons.net SVG silhouettes. Each task below is its own sitting of art-making;
the ones that also need code say so. Order is the suggested priority.

- **Item icons (the biggest gap).** `items.py` has no icon field and the pack, market, stash
  and loot screens are text only. **Decide first** the style (medallion or silhouette). Then
  by category: one-handed weapon, two-handed weapon, bow/crossbow, light/medium/heavy armor,
  shield, potion, food, material (leather, wood, iron, stone), tool, Copper Coin, Gold Coin.
  After that the key items: Signal Horn, Chisel, Pickaxe, Holy Symbol, Legendary Horn. Needs
  the `ItemDef` field, a `ui/` component for the icon and tests.
- **Art for content already in this backlog.** The Legendary Ox (its own portrait, not the
  common Ox's), the Mine, Smith, Apothecary and Tanner nodes, the Tanner and Smith as
  mission givers with a face, and the Cart and Carriage (`wagon.Vehicle`; `watch_screen.py`
  is text only today).
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
    Reading the map does not consume it (decided). The revealed set lives in the guild's save (decided; a new optional field, so its neutral value goes in `persist.PAYLOAD_DEFAULTS`).
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
  - **Scholars wait for the info modal.** Its perk is dormant (`vocations.INFO_BONUS`, see
    *Intelligence reveals enemy info*).
  - **Oath (deferred, not scheduled)** (separate from the vocation): *what binds the members
    together, and how a stranger would tell someone belongs to the guild* (a creed, a mark, a code). It cannot be
    broken, but it can be changed. It has a mechanical side in two places: **cohesion**
    (`cohesion.py`, how members stay or leave) and a **combat/world rule** (something the
    guild will or will not do, trading a lock for a bonus). Not economy or per-faction
    reputation. Open: the list, the exact effects, how the guild is recognised in the world
    (does an NPC react to it?), and the cost of changing one.
  - **Presentation (the identity phase of `draft_screen.py` is still off the kit):** a live preview of the guild as choices are made,
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
  Marsh's slower rot (see the charter) is priced low until this lands. Open: what a good meal
  gives (HP, a buff, morale), the recipes and who cooks (`Crafter`, the Claim oven), and the
  cost to the economy sim (`cheapest_food_price` stops being the one price of a meal).

---

# Starting items waiting on another system

Each occupation starts with one item (`data.OCCUPATIONS`). Rule: every occupation's item
is useful and **unique to it**, as an occupation is only a weapon and an item. Items that
already work: Meat, Potato, Quiver, 1L Beer, 1sqm Hide, Iron Bar, Lumber, 1kg Coal, Stone Brick
(the Claim oven's material), First
Aid Kit, Lantern, Scroll, Dictionary, Salt, Ink, Rope, Bear Trap. Amethyst is only a store
of value, and Rotten Food is the Slave's on purpose (eating it makes you sick). These wait
for a system that does not exist yet:

- **Map.** Finds treasures and secret zones. Waits for those systems.
- **Compass.** Avoids getting lost on very long trips through unknown paths. Waits for a
  getting-lost system.
- **Deck of Cards.** A card minigame at the tavern, among others. Its own arc.
- **Holy Symbol.** Required, together with everything else, to start in faith magic.
