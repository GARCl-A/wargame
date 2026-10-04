# Guild Screen (The Guild Hub) Redesign

## Context & Purpose
`GuildScreen` is the central administrative command and character roster hub of the guild. It is an inspection and progression interface across all recruited company members, supporting multiple bands geographically dispersed across the world map.

## Core Design Principles
1. **No Magic Cloud Chest:** Items exist physically on character bodies or inside local physical storage structures (e.g. City Bank/Strongbox, base garrisons). There is no global cloud inventory.
2. **Geographic Grounding:** Characters belong to physical groups positioned at specific nodes (`@ Tavern`, `@ Iron Mine`, `@ City`). The UI makes this prominent via the hero badge and roster tags, with a `[ VIEW ON MAP ]` camera shortcut.
3. **Band Affiliation is Informational in this Hub:** Band membership transfers only occur physically on the world map via proximity. The Guild Hub organizes members into collapsible accordions by band for readability and inspection, not for arbitrary remote regrouping.
4. **Three-Zone Encumbrance:** Carry capacity follows explicit physical thresholds:
   - `0 to Carry Normal`: Unencumbered (no penalty, green).
   - `Carry Normal to Carry Max`: Overloaded (`-1 SPD`, amber, marked by a physical divider tick).
   - `> Carry Max`: Immobile (unable to march, red).
5. **Contextual Action Rules:**
   - `DISTRIBUTE BAND LOAD`: Enabled only when 2+ members of the same band are present at the exact same physical node. Otherwise disabled with an explanatory tooltip.
   - `OPEN CITY VAULT`: Only rendered and enabled if the selected member is located in the City and the guild has an active strongbox (`bank_capacity > 0`).
6. **Command Appointments over Mobile Toggles:**
   - `Guild Sovereign`: Prestige supreme title with explicit transfer flow.
   - `Band Commander`: Military appointment tied to band capacity (`3 + CHA mod + racial/2`).
   - `Ration Logistics`: Protocol for pooling food with starving comrades.
7. **Progression Duality:**
   - Explicit visibility for Base Labor (Work XP earned in mining, smithing, facility tasks) alongside Combat Career and Racial Maturity.

## What NOT to Redo
- Never add global drag-and-drop gear swapping to `GuildScreen`. Loadouts must be managed on individual packs (`gear_screen.py`) or via tactical physical screens.
- Never add mobile-style toggle switches that imply arbitrary multi-leader configurations.
- Never drop the location tags or load indicators from the roster cards.
