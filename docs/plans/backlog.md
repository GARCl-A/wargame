# Backlog — everything still open

The one place for open work. It folds the playtest review (2026-10-05), the wagon and
camp to-do list and the later playtest notes. What is already built is in the code, its
tests and the git log; the long-range AI plan is
[campaign_ai_roadmap.md](campaign_ai_roadmap.md).

Sizes are estimates, not checked against the code. When an item is done, delete
it here and, if it changed a design premise, record it in `AGENTS.md` or the doc that owns it.

Three parts:

- **Ready to do** — the task is defined enough to start. Sorted by size: small (a sitting),
  large (a system: UI, AI and tests), epic (its own arc).
- **Needs more information** — a design question, a repro or another system has to land
  before the task can be sized.
- **Starting items waiting on another system** — not a question: a list of items whose
  system does not exist yet.

---

# Suggested order (project review, 2026-10-09)

Goal read: a sandbox open-world guild manager; the run ends only on a wipe. Balance and
sim work is ahead of the content it balances, so the order favours content verticals and
the seams they need.

1. Mine + Legendary Ox + Tanner missions + Signal Horn recipe (first craft -> mission -> item loop).
2. Vocations in the draft (decided, table below).
3. AI combat recording (`recorder.py` combat event); the economy is calibrated against a
   player the AI does not match yet.
4. Docs refresh (Small, below) can go in any sitting. The *Architecture debt* section lists
   what to pay on the way.

Magic comes after the *node that unlocks* mechanic; it is the next big content gap.

---

# Ready to do

## Small

- **README and RULES describe an older game.** They sell "tactical squad + factions"; the code
  is an open-world guild manager. The README barely mentions wagons and animals, the Claim,
  the bank, the Medic, vocations or the economy sim. Refresh both to today's game (RULES
  stays prose, `REFERENCE.md` stays generated).
- **Economy report prints a FAIL on the day-30 milestone.** `scripts/economy_report.py --quick`
  (2026-10-09): the `balanced` policy reaches the milestone in 0% of guilds (need 50%), cost
  from $423. It is the known gap with the recorded runs (11-14 days by hand), so it settles
  with *Feed the recorded runs* and the planner, not by tuning prices. The run exited 0, so
  this does not break a gate.
- **Starting tools with no job: Bucket, Scissors, Pliers.** Scissors and Pliers wait on a
  recipe that lists them in `tools`, the Chisel on the Horn, the Shovel on the Mine and Chains on *Prisoners*.
  The Bucket (Peasant) has no planned system at all: give it one (water, milking, camp) or
  swap the Peasant's item, since the rule is that every starting item is useful.

## Architecture debt

Past choices that now fight the direction. Each has the cost of fixing it; pay one when the
feature that needs it is next, not before. Debts already written as part of a feature are
pointed to, not repeated.

- **Weapon traits are ad-hoc fields.** `ItemDef.finesse` / `thrown` plus hand-written `if`s in
  the description builder; every new weapon is a new `if`. Blocks the 2-AP action per weapon.
  **Cost: medium** (a registry like `abilities.py`). Detail under *Weapons that are really
  different*.
- **Big screen files.** `app.py` (1180 lines, 102 `def`s) is the wiring hub; `map_screen.py`,
  `market_screen.py` and `battle_screen.py` run 800-950. Not critical. When one takes a new node
  or tab, split by concern instead of growing it. **Cost: low per split.**
- **Saves have no migration (on purpose).** Fine while the author is the only player. Before
  any outside playtest decide: keep "an older shape does not load" with a clear message, or add
  a version bridge. **Cost: low (message) to medium (bridge).**

## Large

- **Signal Horn chain (the item is built, it cannot be obtained).** The Signal Horn (artifact
  slot) is not sold: only crafted, and the recipe is rare. Final shape: **Leather + Rope + a
  Chisel (tool, not consumed) + the Legendary Ox's horn**. Pieces, in order:
  1. **The recipe lists the Chisel** in `tools=(...)` (the mechanism is built: `CraftingRecipe.tools`).
  2. **The Legendary Ox:** a unique creature, its loot is a new `Legendary Horn` item. It is the
     target of the last mission of the chain, so it is placed by the mission, not random.
  3. **Mission chain from the Tanner** (2-3 missions on the hub's board, reputation-gated) whose
     reward is learning the recipe; the last one points at the ox.
  4. The recipe in `items.CRAFTING_RECIPES` (`craft_level.py` derives the level), then re-run
     `scripts/economy_report.py` (a new craft-for-sale line). Needs tests, tutorial and RULES line.
- **Mine (new node, like the Lumber Yard).** A work node plus a shop, mechanically close to the
  Lumber Yard. It is a normal node on the map, not a hidden one. **Stone Brick, Iron Ore (new
  item) and Coal are sold only there**: they leave `MARKET_STOCK`, so the Claim oven will need a
  trip to the Mine. Work order pays in the Mine's goods or wage like the yard does.
  - **To set while building:** the distance from Ankareth (suggestion: about 3 h, farther than the
    Farm), the wage and pay, whether it needs a Pickaxe (`CraftingRecipe.tools`: a tool in any
    group pack), whether the work carries a per-hour risk. Re-run `scripts/economy_report.py`.
  - Iron Bar stays with the Smith's chain; Iron Ore feeds it later. Needs the node, shop, UI,
    sim support and tests.
- **Weapons that are really different (two tracks, both to build).**
  1. **Named weapon traits.** `ItemDef` carries ad-hoc fields (`finesse: bool`, `thrown: int`)
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
  - **To define while building:** which field sits behind which success margin, how the
    check scales with the target's level, whether knowledge outlasts the fight (a creature
    met before). Needs the action, AI support and tests.
- **Prisoners.** (Not started; decide whether it lands before the specialised shops.) Non-lethal attacks that knock a unit out even in lethal zones, then
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
  - **Way in: record the player's combat, as was done for the economy.** First list every
    action the AI can take (`actions/`) and what `ai.py` does with each. Then the player plays
    fights by hand: AI vs AI with the player taking over one side's unit (the wolf, different
    races and levels), and the recorder logs each decision (state, options, pick). From those
    rows, derive a policy the way `play_analysis.py` derived the `human` economy profile:
    thresholds and priorities (when to focus fire, when to retreat, when to go for the flag),
    then feed them to `ai.py` and measure against the benchmark win rates above.
  - Needs: a combat event in `recorder.py`, a way to hand a unit to the player in an AI fight,
    and an analysis script for the combat rows.
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
  the user), and it must include an ambush on the Old Road, which neither run touched. Then compare
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
- **The Mine on the solo task.** `orders.solo` / `solo.py` carry the hospital stay and the craft
  (a member splits off, or the whole group waits; merge back by hand). The Mine is one more
  `task` there: a branch in `solo.finish` and an issue function like `solo.craft`.
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
    *and* a work node) and Market already exist. Rough split: Smith = weapons, shields,
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
- **Fill the short portrait pools.** Beasts have 4 each (Wolf, Giant Spider, Donkey, Ox,
  Horse) and the Skeleton 4; the Wolf is the only beast the Wilds rolls, so take it to 8 or
  more first. Goblin has 7, Kenku 8 and Goliath 8 against 12 for Human, Elf, Gnome, Halfling
  and Orc.
- **Map node icons.** The 13 nodes share three kinds of glyph (`map_screen.KIND_ICON`). Give
  Ankareth, Arena, Market, Tavern, Prison, Library, Farm, Ancient Ruins and the Claim a mark of
  their own. The map works as it is, so this is polish.
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
  - **New mechanic to build first (decided: a general one): a node that unlocks.** A node
    carries a reveal condition (an item in the pack, a deed, a reputation) and appears in the
    world when it holds. The map is the first user. Nothing does that today. The Mine does *not*
    use it: it is a plain node.
  - **To define:** the exact reputation gate and the intermediate mission; the three
    factions as nodes with their own deeds (see `factions.py`); how each school's study
    differs (`magic.py`); whether the three are exclusive. Holy Symbol (below) belongs to
    the faith school.

- **Found-the-guild charter** (`draft_screen.py`). Founding the guild should be the
  heaviest choice of the run: squad members die, the guild does not, and the player *is*
  the guild. What is left waits for design.
  - **Vocation (decided):** the guild picks one of 6 at founding. Each is a list of **6 races**
    and a **fixed guild perk** (no talent tree; the perk may become a tree's root later).
    - **Pool rule:** the 9-card pool always holds at least one card of each of the vocation's 6
      races; the other 3 come from the normal draw (natural race weights, all 18 races). A
      commission token re-rolls only the clicked card, from the natural race table and outside
      the vocation. Every race is in at least one vocation.
    - **The 6 (first cut, names and lists can change):**

      | Vocation | Races | Perk |
      |---|---|---|
      | Warband | Orc, Hobgoblin, Goblin, Goliath, Gnoll, Lizardfolk | +1 Mental Defense in the daily cohesion roll only (5% fewer walk-outs); the defense penalty of overextension is unchanged |
      | Delvers | Dwarf, Kobold, Gnome, Automaton, Goblin, Goliath | more yield from gathering work (which orders count and how much: to set) |
      | Wilds | Centaur, Elf, Treefolk, Grippli, Gnoll, Sprite | lower chance of a road ambush (with a floor, not immunity; to set) |
      | Mystics | Kobold, Gnome, Elf, Sprite, Kenku, Human | faster spell study (dormant until the magic line exists) |
      | Caravan | Human, Halfling, Dwarf, Kenku, Automaton, Centaur | faster travel on the world map (check how it stacks with wagons and animals) |
      | Marsh | Grippli, Lizardfolk, Treefolk, Halfling, Kobold, Kenku | one extra day before hunger starts (`unit_hunger.hunger_level`, `unfed_days` minus 1) |

    - **To set while building:** the numbers of Delvers, Wilds, Mystics and Caravan (measure
      them with `scripts/economy_report.py`), and that the perk is the guild's (every member), not
      only the members of the listed races. Needs the vocation registry, pool rule in
      `draft_screen.py`, perk hooks, save field and tests (including the pool guarantee and each perk).
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
