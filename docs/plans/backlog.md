# Backlog — everything still open

The one place for open work. It folds the playtest review (2026-10-05), the wagon and
camp to-do list and the later playtest notes. What is already built is in the code, its
tests and the git log; the long-range AI plan is
[campaign_ai_roadmap.md](campaign_ai_roadmap.md).

Ease and impact are estimates, not checked against the code. When an item is done, delete
it here and, if it changed a design premise, record it in `AGENTS.md` or the doc that owns it.

Two parts:

- **Ready to do** — the task is defined enough to start. Sorted by size: small (a sitting),
  medium (a feature touching a few modules), large (a system: UI, AI and tests), epic (its
  own arc).
- **Needs more information** — a design question, a repro or another system has to land
  before the task can be sized.

---

# Ready to do

## Small

Polish:

- **Tolerant `from_save` for new optional keys.** `Unit.from_save` and `persist.load_game`
  read every key strictly. Add one defaults table next to `unit_to_dict` / `_payload` and
  have `from_save` read `{**DEFAULTS, **data}`, so a new optional field gets a default
  without per-key `.get` noise. `SAVE_VERSION` bumps only when the shape changes (a field
  removed, renamed or with new meaning), not for an added optional field.

## Medium

- **Craft with the group's shared inventory.** Inside a crafting screen the group's packs
  count as one pool for ingredient requirements, so items need not be moved onto one
  character first. A locked item (padlock) can never be used in any craft.
- **Founding draft: 9 pick 3.** `draft_screen.py` offers a pool of 9 candidates and the
  player picks 3, replacing 3 rounds of 1 of 3. The 3 Commission Tokens work as they do
  today: spent to call the archetypes missing from the pool, here rerolling one of the 9.
  Then choose the guild leader from the 3. Independent of vocation and oath. Needs the
  generation, the UI and tests.
- **Founding screen on the `ui/` kit.** The draft screen is off-pattern; rebuild it with the
  `gartok/ui/` components (data-driven `draw_x`, 8px grid, palette) and keep its tutorial
  card. Do it together with the 9-pick-3 draft so the layout is built once.
- **Medic, quick treatment (B1).** A tab in the Apothecary hub: the answer to rest healing
  being slow (1 HP per 8 h at CON mod 0). A hospital that treats with healing potions and
  antidotes at a discount, priced as the *expected* potions and antidotes needed to leave
  cured, at catalogue price x 0.7 (a constant in `economy.py`). It is a transaction: pick
  the patients from the party present, pay, and the clock advances for the whole group.
  - HP: always up to max, 1 h. Cost = `ceil((hp_max - hp) / 3.5)` Minor Healing Potions.
  - Sickness: 8 h, cost = one First Aid Kit charge (price / charges).
  - Poison: assume every Antidote save passes; stacks fall about 2 a day (natural + dose),
    so N stacks take 24 h x `ceil((N - 1) / 2)` (at least 1 h) and `ceil(N / 2)` doses.
    Only treatments up to 24 h belong here; longer ones are B2.
- **Medic, hospital stay (B2).** After B1. A treatment of 24 h or more admits the patient:
  they split off into a new Group on a new order kind (saved with the groups), locked like
  any group with an order. With no free group slot the whole group waits with them instead.
  On discharge the patient is a loose group and the player merges by hand.
- **Claim construction: oven.** Built at the Claim with time and Stone Brick; like the
  campfire but always lit. First thing to build there, and the start of a general
  build-at-the-Claim system.
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
- **Play recorder for the economy sim.** The sim's policies are my guesses at how a person
  plays; the arc ends by recording the real thing. An opt-in setting (`settings.json`) makes
  the game append events to a JSONL file beside the guild's saves, never inside a save:
  - each day: money of every character, combat / work levels, HP, rations in the group;
  - each order given (group, kind, destination, hours) and each market buy or sell (item,
    quantity, price), bank and house purchases, recruiting pitches and their result;
  - each fight's outcome (kind, won, deaths, XP) and each talent picked.
  Then play **three 30-day runs** and use them to: (1) print the same day-by-day table the sim
  prints (activity, levels, net worth); (2) extract the decision thresholds (money held when an
  Axe was bought, days of food when you shopped, level and HP before a bout, the day you left
  the yard); (3) add a `human` policy to `scripts/economy_guild.py` that uses them and compare
  it with `lumber`, `balanced`, `climber`. Three runs show the variation; one would only be a
  story. Open questions before building: where the hooks go (orders are issued from several
  screens, so the cleanest seam may be `campaign.advance` plus the screens' `_buy` / `_sell`),
  and that the sim's fights come from a library, so replayed fights use a 0.9-0.95 skill.
  Needs the setting, the hooks, the analysis script and tests. Findings it should settle are in
  [economy_sim_v2.md](economy_sim_v2.md): the day-30 milestone, the Axe-first order, whether the
  ladder (yard, Scrapper, Games, Wilds) is how people really climb.
- **Crafting in parallel.** Crafting spends the whole guild's clock today
  (`Guild.crafting_shift`: one crafter at a time, everyone waits). Instead the player
  allocates a character to craft: they split off the group into their own Group on a craft
  order, work at the station while the others do something else, and rejoin by hand (the
  same shape as the Medic's hospital stay, B2, and it competes for the same group slots).
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

- **Found-the-guild charter** (`draft_screen.py`). Founding the guild should be the
  heaviest choice of the run: squad members die, the guild does not, and the player *is*
  the guild. The draft (9 pick 3) and the screen fix are in Ready > Medium; what is left
  waits for design.
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
  - **Presentation, after the screen fix:** a live preview of the guild as choices are made,
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
