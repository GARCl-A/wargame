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

In this order. Why each one comes first is in italics.

3. **Claim: the lumber licence and the Claim overlap, and nobody knows who gathers (playtest 2026-11-02).**
   The Claim now collides with the Lumberyard licence on lumber collection, and the screen does not say who
   in the Claim is gathering wood or what that takes. Pick one owner of the rule, show per member
   whether they gather and the requirement they lack. Principle (author): every gather activity should have
   the gather tab. *Group B of the proof of concept gathers Lumber: the "gather" step must not be built on
   an ambiguous rule.*

4. **Show food's shelf life and the rations where the decision is made (playtest 2026-11-02, Johann
   2026-10-31).** The supply is a constraint on purpose (*Current content*, and the backlog's *Playtest
   notes -> 2026-10-31*), so the player has to be able to see it: the shelf life in the shop row; each
   food's own expiry in the inventory (today a stack hides the validity of its items); the ration count on
   the craft screen; and the rations a trip or a defence needs in the travel preview, with a warning on
   the first trip. *Hunger drops a group out of automatic mode: the order needs one function that says how
   many rations a stretch takes, and it is the same number the preview and the warning show.*

5. **A log of what happened while the days passed (Johann, 2026-11-01).** Today the lines of a jump
   (meals eaten, food rotted, hunger, purchases) reach the map as one "Since the last order" card (last
   12 lines, click to put it away) and are gone: `MapSession.state` drains `notices`, and the guild
   screen's Notices are the charter's, not a history. Keep a bounded, per-guild list of the day's events
   (saved, or at least kept for the session) with a tab or button to reread it. Size once the card
   decides how much to keep. *The player collects what the automated groups did when back from the
   expedition, and is warned when a step fails: without a history the automation runs blind.*

6. **Ankareth is the town, the node is the bank (author, note outside playtests).** `world.py` names the
   `city` node "Ankareth", but the arena, the market and the smithy are their own nodes: the node is the
   bank. Name the node for what it is, keep "Ankareth" for the region, and replace the circle that marks
   Ankareth's jurisdiction on the map (`MapSheet`, `sheet.js`) with something that does not read as a road.
   Grep the strings and tests that use the name first. *A route step names its nodes: rename before the
   orders are saved with the old name.*

Left for later, they come up with the work (author 2026-11-03): the tests the pygame campaign's cut lost
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

1. **Programmable orders: brainstorm and spec (author 2026-11-01).** Not a build task: first find out
   exactly what the author wants, then write the spec into this file (replacing this item) so the
   implementations are chosen from a real specification. Deliverables:
   1. Brainstorm with the author the use cases: which routines, who runs them, what interrupts them, what
      the player collects and when.
   2. Identify every place that already runs an order (`orders.py`, `stints.py`, `MapSession.spend`, the
      supply run and the hunt) and what they share.
   3. Document the options (a list of ordinary orders run by the one clock, or a new order kind with state)
      with a recommendation. Constraint to keep: only `campaign.advance` moves the clock.
   4. Turn the proof of concept into the acceptance test.
