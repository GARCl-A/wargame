# Backlog — everything still open

The one place for open work. It folds the playtest review (2026-10-05), the wagon and
camp to-do list and the later playtest notes. What is already built is in the code, its
tests and the git log; the long-range AI plan is
[campaign_ai_roadmap.md](campaign_ai_roadmap.md).

Sizes are estimates, not checked against the code. When an item is done, delete
it here and, if it changed a design premise, record it in `AGENTS.md` or the doc that owns it.

Two parts:

- **Ready to do** — the task is defined enough to start. Sorted by size: small (a sitting),
  medium (a feature touching a few modules), large (a system: UI, AI and tests), epic (its
  own arc).
- **Needs more information** — a design question, a repro or another system has to land
  before the task can be sized.

---

# Ready to do

## Medium

- **Signal Horn** (new item, not a starting item: too strong). A combat action that warns
  allies, for example extra movement or drawing attention. Talks to the Alarm Trap and the
  Alert talent. Needs the action, AI support and tests.

## Large

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
- **Crafting tools.** Crafting consumes everything today. Let a recipe also require a tool
  that is not consumed (a cart needs wood, nails and a saw). Gives Chisel, Scissors, Shovel
  and the Goldsmith's Pliers a job (and jewellery crafting, when it exists). Shapes the
  future wagon recipe.
- **Prisoners.** Non-lethal attacks that knock a unit out even in lethal zones, then
  capture it. Chains are what holds the captive. Needs the AI to know it too.
- **Combat AI plays far below a person.** Every economy number depends on how often the
  squad wins, and a person wins far more than `ai.py` does: measured in the economy report
  (layer 1 prints the AI's own win rate beside the skilled ones), the AI wins the Scrapper
  95%, the champion bout 75%, a Games brawl 43%, capture the flag 37%, a Wilds ambush at
  level 3 61% and the Ribbit Brothers 7%. A person wins the Pit's bouts "almost always".
  Goal: AI win rates close to a competent player's on those benchmark fights, so the sim
  (and `autowin`) stop needing a `--skill` knob. Start from what the AI does badly in the
  Games (objective play in capture the flag, focus fire, using the terrain), re-run
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
  wipe is 0% ([finding 20](economy_sim_v2.md)). Settling it needs a third, longer run. Then compare
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
- **Crafting in parallel.** Crafting spends the whole guild's clock today
  (`Guild.crafting_shift`: one crafter at a time, everyone waits). Instead the player
  allocates a character to craft: they split off the group into their own Group on a craft
  order, work at the station while the others do something else, and rejoin by hand (the
  same shape as the Medic's hospital stay, and it competes for the same group slots).
  The economy sim's `crafter` policy then becomes one member crafting while the rest work
  the yard. Needs the order kind, saves, UI and tests.
- **Specialised shops.** Split the single general market into shops, each its own node
  with a walking distance between them, so the player has to go around. The market's
  finite cash is built (`Guild.market_cash`, keyed by node id), so each shop gets its own.
  The production chain (lumberjack -> carpenter, smith) and restocking tied to the world
  are a later arc; this task is the structure with a fixed restock.
  - **Shops:** Smith, Apothecary and Tanner are new nodes outside the city (today `forge`,
    `apothecary` and `tanner` are flags on `city`). The Smith and the Apothecary take their
    crafting with them, as tabs. Farm (today only the stables), Tavern, Lumber Yard (a shop
    *and* a work node) and Market already exist. Rough split: Smith = weapons, shields,
    metal armour, Iron Bar, Coal; Tanner = leather armour, Cloak, Hide, Quiver; Apothecary =
    potions, Vial, First Aid Kit; Farm = raw food and Salt; Tavern = Beer and Jerky (the only
    ready-made food today); Lumber Yard = Lumber; Market = the rest (Torch, Lantern, traps).
  - **Prices and stock:** one base price everywhere. Every item is finite in every shop. A
    shop buys any item at 50% and puts it on its shelf to resell at 100%. Each item has a
    target count per shop and the shop walks back to it a little each day. Since every shop
    resells everything, the targets are what makes each one specialised.
  - The Library joins the same rule (stock target, finite cash, buys anything at 50%) and
    keeps its other tabs.
  - **The till belongs to the shop, not to the node's kind.** `Guild._daily_upkeep` refills
    cash only for nodes with `kind == "market"`, so the Library's till (a `town` with a
    shop tab) never refills and a Tavern (recruiting, work and a shop in one node) would not
    either. A node with several functions needs a `shop` function that owns the till, its
    refill and its stock; the economy sim's route scan reads the same list.
  - **Node distances:** the new nodes need a walking distance from Ankareth, and the
    existing ones (Market and Library 1 h, Farm 2 h) should be reviewed together with them,
    since the distance is the cost of going around between shops.
  - **First step:** define the stock target per item and per shop, and the daily refill
    rate. A first estimate from the economy sim's restock sweep
    ([economy_sim_v2.md](economy_sim_v2.md), finding 6): a shelf of about 10 refilling 3 a
    day keeps a crafting specialist at about 2x a lumberjack's wage; below 4 with 1 a day
    makes crafting for sale pointless. Open: AI and tests.

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

- **The Mine (new node).** A place to dig, and where Stone Brick (the Claim oven's material,
  15 x $10) and the ore side of the Smith's chain (Iron Bar, Coal) come from, instead of only
  the Market. Not sized: it is a node with its own work, risk and loot, and the first node of
  the production chain the specialised shops wait for.
  - **To define:** where it sits and its distance from Ankareth; what it yields and at what
    rate (a work order like the yard, or a Wilds-style activity with ambushes); the risk
    (cave-ins, creatures, the Z axis already has pits); whether it needs a tool (a Pickaxe;
    ties to *Crafting tools*); how its pay compares with the yard and the Wilds (re-run
    `scripts/economy_report.py`); whether it is a Claim-like holding the guild can own.
  - Needs the node, its order or activity, UI, AI/sim support and tests.

- **Weapons that are really different.** Today every weapon of one damage die is the same
  weapon (all d8 melee play alike; the d6 ones differ only by Finesse, as the rapier). Two
  lines, not yet chosen between (they may combine):
  1. **A 2-AP action per weapon.** Every weapon keeps the basic attack; each weapon *kind*
     also gets its own two-point action. Open: which actions, one per weapon or per family,
     how the AI chooses between them.
  2. **Explicit weapon traits.** `ItemDef` carries ad-hoc fields (`finesse: bool`,
     `thrown: int`, `items.py:64`) and each trait's rule text is a hand-written `if` in the
     description builder. Model them as a set of named keywords (Finesse, Thrown, Entangle...)
     so a new weapon is declared by listing traits (a spiked spinning chain: Finesse + Thrown
     + Entangle) and the code, UI text and `REFERENCE.md` read from the one registry. Same
     shape as `abilities.py`.
  - **First step:** audit the weapon catalog for what any two share (die, hands, range,
    trait) and what makes each one unique, then decide whether trait keywords can carry the
    2-AP action too (a trait grants an action). Needs AI and tests.

- **Magic as the vertical progression.** Follows the library's tome quest. Chain:
  1. After the tome quest, at reputation 3 with the Library, they hand over a **map** that
     unlocks a new place.
  2. An intermediate mission to earn their trust in the guild.
  3. Then the Library sends the codex to one of the **three magic factions** (Blood mages,
     Nature mages, Faith mages), where the magic line proper begins.
  - **New mechanic to build first: a node that unlocks maps.** Items or deeds (the map)
    must be able to make a node/map appear in the world. Nothing does that today.
  - **To define:** the exact reputation gate and the intermediate mission; the three
    factions as nodes with their own deeds (see `factions.py`); how each school's study
    differs (`magic.py`); whether the three are exclusive. Holy Symbol (below) belongs to
    the faith school.

- **Found-the-guild charter** (`draft_screen.py`). Founding the guild should be the
  heaviest choice of the run: squad members die, the guild does not, and the player *is*
  the guild. What is left waits for design.
  - **Vocation:** a curated list of 5-8 that biases only the candidate pool, mostly the
    **races and occupations** drawn (age and tendency may follow). It has no effect after the
    draft and never locks the pool. Open: the list and each one's bias.
  - **Oath** (separate from the vocation): *what binds the members together, and how a
    stranger would tell someone belongs to the guild* (a creed, a mark, a code). It cannot be
    broken, but it can be changed. It has a mechanical side in two places: **cohesion**
    (`cohesion.py`, how members stay or leave) and a **combat/world rule** (something the
    guild will or will not do, trading a lock for a bonus). Not economy or per-faction
    reputation. Open: the list, the exact effects, how the guild is recognised in the world
    (does an NPC react to it?), and the cost of changing one.
  - **Presentation (the identity phase of `draft_screen.py` is still off the kit):** a live preview of the guild as choices are made,
    a richer composed banner, and an opening scene: a founding charter that writes itself
    line by line, signed with the banner and the oath, kept as the first entry of the
    guild's chronicle.
  - Open: AI and tests for the vocation bias.

## Starting items waiting on another system

Each occupation starts with one item (`data.OCCUPATIONS`). Rule: every occupation's item
is useful and **unique to it**, as an occupation is only a weapon and an item. Items that
already work: Meat, Potato, Quiver, 1L Beer, 1sqm Hide, Iron Bar, Lumber, 1kg Coal, First
Aid Kit, Lantern, Scroll, Dictionary, Salt, Ink, Rope, Bear Trap. Amethyst is only a store
of value, and Rotten Food is the Slave's on purpose (eating it makes you sick). These wait
for a system that does not exist yet:

- **Map.** Finds treasures and secret zones. Waits for those systems.
- **Compass.** Avoids getting lost on very long trips through unknown paths. Waits for a
  getting-lost system.
- **Deck of Cards.** A card minigame at the tavern, among others. Its own arc.
- **Holy Symbol.** Required, together with everything else, to start in faith magic.
