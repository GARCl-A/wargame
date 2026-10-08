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

Bugs:

- **Delay is unlimited.** A unit can delay indefinitely; allow one delay per round.
- **Tavern performance gives wrong work XP.** Performing at the tavern does not seem to
  grant work XP correctly (the stage and the level multiplier landed in `6298cba`); check
  the amount against the work-XP rule.

Polish:

- **"Until full" shows the wrong thing.** The rest preview says "3 meals each"; it should
  show the total food cost.
- **Who is "riding".** The group screen shows how many are riding in a wagon but not who;
  list them.
- **Recruit blocked reason.** When a character cannot recruit, lead with the most
  important reason: 0 recruitment slots available.
- **Musical Instrument for sale.** Add it to the market stock.
- **Wagon in the Market's inventory.** The wagon should show up as an inventory in the
  Market, like the other containers.
- **Arena bets use the group purse.** Betting should combine the whole group's money, not
  only the fighters'.

## Medium

- **Craft with the group's shared inventory.** Inside a crafting screen the group's packs
  count as one pool for ingredient requirements, so items need not be moved onto one
  character first. A locked item (padlock) can never be used in any craft.
- **Animal sheet in the Guild.** Show the Ox (any `Animal`) with a character-sheet card
  like a unit's.
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

- **Crafting tools.** Crafting consumes everything today. Let a recipe also require a tool
  that is not consumed (a cart needs wood, nails and a saw). Gives Chisel, Scissors, Shovel
  and the Goldsmith's Pliers a job (and jewellery crafting, when it exists). Shapes the
  future wagon recipe.
- **Prisoners.** Non-lethal attacks that knock a unit out even in lethal zones, then
  capture it. Chains are what holds the captive. Needs the AI to know it too.
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
  - **Node distances:** the new nodes need a walking distance from Ankareth, and the
    existing ones (Market and Library 1 h, Farm 2 h) should be reviewed together with them,
    since the distance is the cost of going around between shops.
  - **First step:** define the stock target per item and per shop, and the daily refill
    rate. Open: AI and tests.

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

- **Strip legacy-save compatibility code.** The game is still in testing and no save needs
  to survive a format change, so code that only keeps old saves loading is dead weight.
  Find it and cut it: the tuple and string branches of `Guild._rot_food` /
  `_age_food_name` and `unit_hunger.take_ration` (food aged by renaming, `"Potato (2d)"`),
  the "tolerates missing keys" defaults and the `pack_from_raw` flat-list shapes, the
  `from_save` shape-polymorphism, `SAVE_VERSION` upgrade steps, and the tests that only
  cover those. Settle first which part stays on purpose (a tolerant `from_save` for new
  optional keys is cheap) and update the `persist.py` / `AGENTS.md` notes that promise
  compatibility.
- **Combat info modal.** Hide part of it by default and rework it: it carries information
  that should not be there and lacks some that would help. Define what goes in and out first.
- **Economy sim catch-up.** `scripts/economy_sim.py` models a trader against its own
  `Vendor` class, so it never sees what changed the economy in the game: the market's
  finite cash (`Guild.market_cash`: $100 to start, +$25/day up to $500), coins as items
  (`$`, gold, the bank exchange), the Medic and upkeep that now drain money (house tax,
  garrison, wagon wear, animal feed, group rest), and a squad pooling one market instead
  of a lone trader. First decide what question it answers (can one character earn a
  living? can a guild?), then have it drive the real `Guild`, market and daily upkeep
  instead of a parallel model. Until then a change to wages, purses or loot is checked by
  hand.
- **Found-the-guild screen** (`draft_screen.py`). Founding the guild should be the
  heaviest choice of the run: squad members die, the guild does not, and the player *is*
  the guild. Today it is a colour, an icon and a leader pick, and the screen looks
  off-pattern. Redesign in two phases around a founding charter (epic once defined):
  - **Before the picks:** pick a *vocation* from a curated list of 5-8. It biases the
    candidates' race, age, occupation and tendency; it never locks the pool. Pick the
    *oath* (separate from the vocation): a short list, each with a mechanical effect,
    built on `cohesion.py` and `factions.py`. An oath cannot be broken, but it can be
    changed. Name and banner may also go here.
  - **Draft:** a pool of 9 candidates, pick 3 (replaces 3 rounds of 1 of 3). The 3
    Commission Tokens stay, now spent to reroll one of the 9 before choosing.
  - **After the picks:** choose the guild leader.
  - **Presentation:** a richer composed banner (more shapes, colours and patterns), a
    live preview of the guild as choices are made, and an opening scene: a founding
    charter that writes itself line by line as the player decides, signed at the end
    with the banner and the oath, and kept as the first entry of the guild's chronicle.
  - Open: the vocation list and each one's bias; the oath list, effects and the cost of
    changing one; whether Commission Tokens still shape archetypes or only reroll; AI
    and tests for the new generation bias.
- **Inventory containers.** Decide whether the inventory should be split into containers
  at all. Sack and Iron Shackles were removed from the catalogue; bring a container back
  when this is decided.

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
