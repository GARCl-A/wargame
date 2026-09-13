---
name: gartok-missions-and-tanner
description: "missions.py (paid, deadlined jobs, distinct from factions.Deed) + the tanner NPC at the City + finite market stock, first shipped 2026-09-12"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8cab88d5-9ffe-4d20-946c-2966fd0befa8
  modified: 2026-09-12T20:09:44.665Z
---

Built and merged (pending commit as of 2026-09-12): a **Mission** system distinct
from [[gartok-factions-reputation]]'s `Deed` -- a Deed is silent/passive/no
giver/no deadline, banks reputation only. A `Mission` (`gartok/missions.py`) has
an explicit giver, a concrete goal/qty, a copper reward, and a real deadline
(`deadline_day`), and can fail.

**Scoped to a Unit, not a Group.** First implementation scoped to `Group.gid`
and the user (correctly) called it a bad plan: `Group` is reshuffled
constantly by splits/merges (see [[gartok-groups-refactor]]), so a mission
pinned to one `Group` object strands the moment that exact group stops
existing. Fixed: `Mission.unit_uid` names who accepted it (the group's
**leader** signs, matching the market-haggling "who speaks for the group"
convention); `progress`/`turn_in` resolve `guild.group_of(unit)` fresh every
call, so the job travels with its signer into whatever group they're
currently in and pays whoever's with them *now*, not at acceptance time. This
is the same pattern `Guild._shared_larder` already uses for food-sharing.
**General lesson**: any player-facing commitment that outlives one screen
visit should hang off a `Unit`, never a `Group` -- Group is a physical,
disposable container, Unit is the stable identity.

First mission: `missions.TANNER_HIDES` -- the City's tanner NPC
(`tanner_screen.py`, "TALK TO THE TANNER" button next to the bank) wants 15x
`"1sqm Hide"` (an item name that already existed in `data.py` as the Tanner
*occupation*'s starting item -- reused for consistency), pays 200 copper, 5
in-game days to deliver. Only one instance of a given mission template can be
active guild-wide at a time (`missions.offers_at`); expires automatically via
`Guild._daily_upkeep` -> `missions.expire_overdue`.

**Finite market stock**, built alongside so the hide couldn't just be bought
instead of hunted: `economy.STOCK` names items with a live, finite count
(`Guild.market_stock`, persisted) -- absent = unlimited (every pre-existing
item, no rebalancing). `1sqm Hide` starts at 0 (never buyable except from a
player's own resale); `Leather Jerkin`/`Studded Leather` start at 3 each
(early armor now feels earned). Buying decrements, selling increments -- no
restock timer, the market only ever has what's actually been sold to it.

See [[gartok-wilds-hunting]] and [[gartok-beast-creatures]] for the other half
of this loop (hides only drop from beasts killed in the Wilds, not from hours
hunted like meat).
