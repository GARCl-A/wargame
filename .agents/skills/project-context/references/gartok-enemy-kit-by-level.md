---
name: gartok-enemy-kit-by-level
description: "Enemy kit by racial level (Oct 2026): the wealth-by-level sim that measured the budget, outfit.py's buying rules (Dex-capped armour, archetype weapons, potions, a light per band) and what the author decided"
metadata:
  node_type: memory
  type: project
  modified: 2026-10-20
---

Closes the Phase 1 backlog item "Gold spent on equipment per level". Before it, a generated enemy
carried its occupation's weapon and item whatever its level: a level-6 bandit fought in street
clothes.

## The budget: `scripts/wealth_by_level.py`

The guild sim (`economy_guild.py`) could not answer "how much has a level-X character earned": none
of its policies climbs (racial 1 after 200 days). So the script follows one *career* over layer 1's
rows (`economy_activities`) plus three of its own: the supply run (real ambush fights), crafting
(one row per recipe level, profit held to the shop's daily `MARKET_CASH_REGEN` split by the group)
and magic by study (Faith rite + every Faith spell; the only source of magic XP it models). Each day
the career takes the in-band activity that moves the racial track fastest, skips what it cannot pay
or what kills more than `--risk` a day, and the group grows like `Group.capacity` (3 + racial // 2).

Findings worth keeping:
- Levels 0-4 come out the same in every career (crafting a potion to work 4, the arena to combat 4).
- Past 4 the supply run is ~96% of the money ($64/day) and the deadliest thing in the game: only a
  statistical survivor reaches 8. Racial 8 needs magic 2 (combat stalls at 8, work at 6), which
  costs ~$5.5k of study: the one big spend of a career.
- The author took the 95%-win, any-risk career as the table: 56 / 67 / 120 / 216 / 344 / 1054 /
  1995 / 2960 / 5741 (`outfit.KIT_BUDGET`).

## The buying rules (`gartok/outfit.py`), as the author shaped them

- Armour first, up to 50%: the most AC **after its Dex cap** (`ac + min(Dex mod, max_dex)`), the
  cheapest of those, never overloaded. The author's call: Dex +3 needs nothing past Studded Leather.
- Weapon by **archetype, never the occupation** (author's rule): STR > DEX -> Strength (half a
  Broadsword, half one-handed non-finesse + light); otherwise half ranged (bow/crossbow + Quiver),
  half one-handed finesse + light. Strength and ranged draw among those >= half the dearest price
  (price is their power: the Shortbow fires twice a turn, the crossbow once); finesse draws evenly
  among all that fit, because no finesse blade dominates (author: Dagger throws, Rapier hits harder).
- Potions with the rest, capped at 3: the catalogue holds no kit past ~$1270, so levels 6-8 look alike
  (author accepted the cap over coins or artifacts).
- Loot stays the current rules (weapon and pack fall, armour only where `strips_the_dead`).
- Only humanoids from `build_enemy`; beasts and authored NPCs keep their own.
- **A light per band** (author asked for both fixes to the "blind at night" problem):
  `light_the_band`, run by `Battle` on every side the player does not play, gives a torch to a free
  hand, else swaps a two-handed fighter to one hand. Level-0 bands are left alone. A band of only
  archers stays dark (left on purpose).

## Do not redo

- The lair keeps "the first kobold of each patrol holds a torch": `lair.build_patrols` strips the
  torch `outfit` gave the others; a test pins it.
- `rest.until_full` crashed when the meal itself mended the last HP (Bloom Fruit): it now refuses
  with "nobody is hurt once they have eaten". The economy report surfaced it.
- Economy report after the change: every verdict passes; the day-30 milestone stays at 52%.
