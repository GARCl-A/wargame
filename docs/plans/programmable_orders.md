# Programmable orders

The author's next arc (decided 2026-11-03): automation of the world around the expedition. The backlog
holds nothing of it any more: everything open on this subject is here, and the author works through this
file until it is done. Three parts, in this order:

1. **Before programmable orders** — what is built first, because the orders stand on it.
2. **Current content** — everything the backlog said on the subject, moved here unchanged in meaning.
3. **To do** — the arc itself.

When an item is done, delete it here (the record is the git log) and, if it changed a design premise,
record it in `AGENTS.md` or the doc that owns it.

---

# 1. Before programmable orders

Nothing is open here any more. Left for later, they come up with the work (author 2026-11-03): the tests the pygame campaign's cut lost
(everyone jailed, no save mid-battle, two due screens in turn, the REST row, a trip cancelled; backlog,
*Medium*), which cover the interruption and the resume the loop depends on.

---

# 2. Current content

Everything the backlog held on the subject.

## Intent (author 2026-10-31)

Macro management through automation, **optional**. The main group is played by hand; the secondary groups
run routines (collect wood, buy vials, craft healing potions and stock the guild inventory; study a spell
for two months) and the player collects when back from the expedition. A player who likes clicking can still
do 80 clicks a day. The player never runs two adventures at once: automation is for the world around the
expedition. It is why the game has several groups (without it they feel slow, as in RimWorld). The author
knows it may push some players away and goes ahead: the game is first for them. The tester's view: it only
attracts, it turns micro into macro.

Johann's session (2026-10-31): automation (secondary groups on routines) is the author's answer to the macro
load and was well received. His view on groups: up to 8 units is fine, more groups slow it unless there is
automation. Whether switching between groups is pleasant was not clear in the record: ask again.

## The entries that want a composed order

Several entries want a composed or automated order and today each names its own shape:

- **Programmable order chains for a group** (older raw notes, 2026-10-12 / 2026-10-21), e.g. gather Lumber at
  the Yard -> sell Lumber and buy food -> gather again. Large; ties to `orders.py` and the sim's planner.
- **The Battlefield beyond the Faith mission.** For now its only use is the Faith Order's errands, and it
  stays that way (author 2026-10-17). Later it becomes one more place of Ledger Hold work and missions: what
  an open skirmish pays, how often the front has a fight. The supply run's walked order with an ambush
  part-way (`Guild.supply_leg`, `Order.owed`) is the shape to reuse. Ledger Hold would then have two jobs,
  the supply run and the front itself (author 2026-10-30): the player enlists as reinforcement, is paid to
  arrive and to fight in the skirmish already under way, and the job is to win it. That is not a walked
  order with an ambush: the battle is the job, so it needs its own order kind.
- **The production chain's gather-sell-buy loop** (backlog, *Large -> Production chain between groups*):
  the carpenter buys wood from the lumberjack and iron from the smith, the smith buys ore and coal from the
  mine; endless day labour at the Yard should flood wood prices. Not part of this arc: the proof of concept
  runs at fixed prices.
- **The stints in `stints.py`** (hours a band spends on a screen are an order, run through
  `MapSession.spend`).
- **The campaign AI** ([campaign_ai_roadmap.md](campaign_ai_roadmap.md)): its planner enumerates and prices
  offers; the spec has to know the model of an order so the two do not grow apart.

## Decided with the author (2026-11-01)

- An *order* is a list of steps and conditionals the player builds and assigns to a group, which then runs
  under it.
- Goods change hands between inventories of two groups only at the same node. B stays parked at the Yard and
  only C walks.
- A hand-over takes everything by default, with an optional condition ("wait for X Lumber").
- The profit stays with C (nothing forbids a step that returns coins to B).
- Hunger ("low on food") and an ambush both drop the group out of automatic mode to manual.
- A step that cannot run (no coins, no stock, blocked route) stops the order and warns the player.
- Constraint to keep: only `campaign.advance` moves the clock.

## The proof of concept (author 2026-11-01): the acceptance scenario of the spec

If the plan's design cannot run it, the design is wrong. Three groups:

- **A** — played by hand, hunting in the Wilds.
- **B** — automated, gathering Lumber at the Lumber Yard into the group's own inventory.
- **C** — an automated trader that takes B's Lumber, walks to the farm, sells it, buys potatoes, walks back
  to B, hands the potatoes over, takes the new Lumber, and repeats.

While the player plays A normally (time passes, A's play is never slowed or interrupted by B and C), the B-C
loop keeps running. Pass criteria: nobody starves, nobody ends stuck, neither activity stops by itself.

It exercises what the spec has to answer: an order that moves goods between two groups (inventory to
inventory, so both must be at the same node), an order that walks a route and trades at each stop, a loop
that resumes after each interruption, food as a need the routine itself must satisfy, and many groups
advancing together on the one clock while one of them is played by hand. Turn it into a test (a headless run
over N game days checking the three criteria) once the design is chosen.

## Related notes kept in the backlog

*Auto battler with priority programming* (*Epic*) is a combat feature of its own, not this arc.

---

# 3. To do

1. **Programmable orders (author 2026-11-03).** Decided in the brainstorm. Built so far: the
   chronological slices of a forced `dt` in `campaign._advance`, and the engine in `routines.py` (`Travel`,
   `Gather`, `Work`, `Rest`, `Wait`, `Take`, `HandOver`, `Trade`, `Repeat`, the conditions, the pause and
   *Continue*, the save). The proof of concept above runs green as `tests/test_routines_poc.py` (24 game
   days, A by hand). Still to build: the `Craft` block, a `Trade` spending limit, the Book of routines
   (slots from reputation, the unlocks), the block editor and its tab with the tutorial card, the
   *Continue* button, and the `Gather` block skipping `orders.work`'s licence check. What is still open is
   listed at the end.

## Spec

**Model.** A *routine* is a layer above `Order`: `Group.routine` holds the blocks and a pointer, and each
time the group's current `Order` resolves the next block emits an ordinary `Order` (`travel`, `work`,
`rest`, `solo`...). `stints.py`, `orders.travel` and the supply run's chained legs are reused as they are;
the routine never owns a countdown of its own. Persistent state on the `Group`, neutral value in the
payload defaults.

**Blocks (the player's vocabulary).**

- Actions: `travel(node)`, `work` / `gather` (for N hours or until full), `trade` (sell X, buy Y, with a
  limit), `rest`, `craft`, `hand_over` ("pass X items to group ABC's inventory"; with no count it takes
  everything) and `take`.
- Food is the routine's own business, never forced: `trade` has "buy food until N days", `take` has "pick
  food until N days" (when the stock is another group's inventory).
- Conditions: `wait until <cond>` is a step. `repeat while / until <cond>` wraps steps (blocks nest, as in
  block programming). A condition is a number compared to a number: items of a kind in a group's
  inventory, coins, HP%, food days. It may read another group, named in one of three ways: by the group's
  own name; "a group at this node doing action X"; or "any other group found at this node". `hand_over`
  and `take` name their other group the same way.
- No `goto`, no free expressions, no variables.

**The clock.** Time moves only until some group is left with no order; a group on a routine is never
without one, so it does not stop the clock. The jump to the soonest completion already does this. Two
consequences the build must honour:

1. When a routine's order resolves, the next block starts at that very instant, on the one clock. A forced
   `dt` (the hunt's stretch while the player plays A) is not one jump of one resolution per group: events
   inside it are settled in chronological order across groups, each step starting where the previous one
   ended. `_advance` today resolves each group once per call; it becomes a loop of sub-jumps. Fed and
   upkeep (`pass_time`) still run per slice, never skipping a day.
2. A cap on blocks that spend no time in one tick (a `hand_over` after a `hand_over`): past it the group
   goes to manual with a log line.

**Hand-over.** Only between two groups at the same node. If the receiving group is not there, wait 1 day;
if still not, the group goes to manual. That wait is a visible fallback on the block, stated in its
editor, and the player may switch it off per block (off: the group goes to manual at once). Two groups after the same stock: whoever got there first.

**Interruptions.** An ambush, hunger or any forced event puts the group in manual and leaves the pointer
on the interrupted block; the player plays it by hand and presses *Continue*. A step that cannot run (no
coins, no stock, blocked route) does the same and warns. Silent failures go to the guild log. A `locked`
group (pending forced fight) is never advanced by its routine.

**The Book of routines (progression, author 2026-11-03).** The player starts with zero automation; the
frame is Final Fantasy XII's gambits. Two separate gates:

- **Automation slots come from reputation**, the same shape as the group slots (`Guild.fame`, RULES.md
  *Fame and group slots*): the more the guild has done, the more groups it can leave on a routine at once.
  A routine runs on as many groups as there are free automation slots.
- **Blocks are mission rewards.** What is unlocked is the block itself: every action (`work`, `gather`,
  `craft`, `rest`, `travel`, `trade`, `hand_over`, `take`) and every condition (items, coins, HP%...) is
  a right the player earns. The routines' theme is its own, apart from the economic gather licence
  (`Guild.has_licence`), which they never read.
- **Places are gated the same way:** a node (the Lumber Yard...) only accepts being put in a routine after
  its mission.
- **First build: everything unlocked.** The gates come later, one by one, as an arc of missions, so the
  routines can be tested whole first.

The player builds with what has been unlocked. The editor is block programming, a linear stack with
nesting for `repeat`.

**Out of scope for the first build.** The campaign AI learning routines (it keeps issuing loose orders,
reading the same block vocabulary so the planner and the spec do not grow apart); the production chain's
dynamic prices (the proof of concept runs at fixed prices); interactive screens (`market`, `forge`...) as
blocks: only silent orders plus `trade` and `craft`.

**Open.**

1. **Which missions unlock which blocks and places**, and the automation slots' own constants (base slots,
   reputation per extra slot). Content, for the arc after the first build.

The Book's tab needs its tutorial card (`tutorial_key()` on its session and a `tutorial.<id>` block in
`locales/en.json`, per `AGENTS.md`): part of the build, not an open question.
