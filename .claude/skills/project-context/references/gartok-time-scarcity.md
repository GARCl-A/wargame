---
name: gartok-time-scarcity
description: "GARTOK design idea, first wedge shipped 2026-09-12 (missions.py deadlines): time isn't a scarce resource yet, which is why splitting the guild into groups has no real downside to weigh"
metadata: 
  node_type: memory
  type: project
  originSessionId: 96b5d0c5-17d5-4c3c-a1ac-f9ff46b17627
  modified: 2026-09-12T20:10:37.426Z
---

Raised 2026-09-11 in the same conversation as [[gartok-leadership]], right
after that system shipped. Not started -- no code, no plan, the user
explicitly said they don't know how to do it yet. Recorded so it isn't
re-derived from scratch later.

## The observation

Today, `campaign.advance`'s tick/orders engine ([[gartok-groups-refactor]])
runs the clock for free from the player's perspective: nothing bad happens by
letting time pass, and no order is more urgent than another. Because of that,
**splitting the guild into more groups currently has no downside** -- it can
only ever help (more parallel activities), never cost anything. The user's own
framing: "a partir do momento em que tempo se torna um recurso valioso,
dividir o grupo começa a se justificar" -- until time is scarce, there's no
tension pulling the other way, so the split/merge mechanic ([[gartok-groups-refactor]])
is mechanically sound but currently unmotivated as a *trade-off*.

## The rough shape of "later"

Not designed, just the user's own words on what might eventually make time
scarce, once the guild is large enough to have something to lose:

- the guild being **attacked** (something to defend, on a clock);
- **deadlines** to meet (an offer, a contract, a rival faction's own clock);
- **calamities** bigger than the guild that must be resolved quickly.

All three imply *urgency competing for the same groups* -- originally thought
linked to [[gartok-leadership]]'s group-count open problem, but as of
2026-09-12 the user deprioritized that problem (sim results looked fine) and
wants time-scarcity pursued as its own thing, not because of it.

## First wedge shipped 2026-09-12: [[gartok-missions-and-tanner]]

The user picked **missions with a deadline** as the concrete entry point over
"a defensible base" -- explicitly because a mission reuses `factions.Event`-
adjacent infrastructure and the existing map tick loop, while a base needs a
whole new subsystem (a place, an attacker, a defense resolution) with no
current analogue. `missions.py`'s `Mission.deadline_day` + `Guild._daily_upkeep`
-> `missions.expire_overdue` is the first "this clock can run out and cost you
something" mechanic in the game. Explicit next step named by the user: a
mission with a real reason to rush (or a physical thing to defend) is what
would make idling multiple small groups start to cost something -- not built
yet, this is the seam to extend when that's wanted.

## Relationship to what already exists

- `orders.py` / `campaign.advance` already have the tick infrastructure
  (soonest-order-due scheduling) that a deadline/calamity mechanic would need
  -- it's a consumer of the existing engine, not a new one.
- `Scenario.win_check` (see [[gartok-wilds-hunting]]) is a generic
  non-elimination objective seam already built for CTF -- a "defend the base"
  or "survive N rounds" scenario could reuse it rather than inventing a new
  battle-resolution path.
- No node, faction, or deed currently represents a threat *to* the guild
  (`factions.py` deeds are all things the guild does *to* the world). A
  calamity/attack system would be the first "the world acts on you" content.
