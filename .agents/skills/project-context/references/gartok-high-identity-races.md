# High-Identity Racial Talents & Daily Framework

**Arc:** Loose Ends Audit & Playtest Prep
**Date:** 2026-09-13

## Goal
Implement a closing pass of design decisions to make races feel deeply distinct (High-Identity) while solving loose ends in progression and state before a playtest.

## What was decided and why

### 1. The 24-Hour Daily Framework (`last_daily_luck_day`)
Instead of tracking arbitrary cooldown ticks or abstract timestamps, we implemented a robust daily framework keyed to the campaign clock (`guild.clock.day`).
- Uses `Unit.can_use_daily()` and `mark_daily_used()` which check against a `last_daily_luck_day` stored in the unit's persistent state.
- **Why?** It ensures abilities that say "once per day" actually respect the sandbox's passage of time (24h), preventing resting abuse and seamlessly functioning both in combat and the world map.

### 2. The Racial Level 5 Gate
- **Rule:** Hit dice (`1d(racial HD) + CON mod`) continue to scale progressively with every racial level starting at L1. However, the **first racial talent pick unlocks only at Racial Level 5** (`earned = max(0, racial_level - 4)`).
- **Why?** To prevent low-level recruits from immediately front-loading their powerful, defining high-identity traits. It turns racial talents into a mid-game reward that signifies a character's mastery of their heritage, rather than a free starter perk.

### 3. The Racial Talents
Three Tier-1 racial talents were introduced to define the races without overlapping with combat or work trees:
- **Leshy (`fruitful`)**: Produces 1 fresh `"Fruit"` every dawn (triggered by `Guild._daily_upkeep`). It leverages the existing shared larder system, allowing the Leshy to nourish the squad or themselves.
- **Human (`cosmopolitan`)**: Reduces alignment distance penalties by 1 step in recruitment and market haggling. Captures the human adaptability in the sandbox's social systems.
- **Halfling (`halfling_luck`)**: Uses the new daily framework to reroll the first failed d20 test every 24 hours. Wired seamlessly into attacks, death saves, lockpicking, and recruitment.

## What NOT to redo
- Do not add arbitrary cooldowns (e.g., "3 turns") to daily abilities. Stick to the `clock.day` system.
- Do not decouple Hit Dice from racial level; they scale together from L1. Only the *talent picks* are gated at L5+.
