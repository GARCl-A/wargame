# Auto-Win Simulation & Pre-Battle Resolution

Background Monte Carlo simulation resolving one-sided random ambushes without combat grind.

## Design Rationale

- **Anti-Grind for Forced Encounters:** When high-level parties travel or forage, weak packs can ambush them. Playing out obvious 6v1 stomps slows the game down.
- **Excluded from Arena & Bosses:** Bouts with stakes (Arena purses, champion title defenses, boss fights) are strictly excluded from Auto-Win to prevent passive gold/title cheese.
- **Fair Trade-off:** 
  - **0 Combat XP:** Kills in Auto-Win yield zero combat XP, preserving manual combat incentive for leveling up.
  - **Simulated Damage Persistence:** If enemies deal minor damage on average, that average rounded damage is applied to `unit.hp`.
  - **Normal Loot & World Advancement:** Field loot is gathered via `LootScreen`, clock rounds advance, and guild victory is recorded.

## Eligibility Criteria (Strict)

1. **100% Win Rate:** Squad must win every simulated run.
2. **Zero Casualties:** Every player combatant must finish standing (`status == "up"`, `hp > 0`).
3. **Zero Consumables:** No ammo fired (e.g. crossbow bolts), no potions drunk, no first aid charges spent.
4. **Early Exit:** Any simulated iteration violating these halts immediately and flags the encounter as ineligible.

## Architecture

- `gartok/autowin.py`: Headless battle runner (`simulate_matchup`) and daemon thread manager (`AutoWinEstimator`) with a 1.0s budget and request tokens.
- `gartok/combatant.py`: Initialises `self.hp = min(c.hp_max, max(1, getattr(c, "hp", c.hp_max)))` ensuring persistent damage carries into battle.
- `gartok/map_screen.py`: Displays `AUTO-WIN (100% - NO XP)` in the inspector during road ambushes while keeping the red `AMBUSHED -- FIGHT` CTA for manual play.
- `gartok/hunt_screen.py`: Pauses during wilds ambushes in phase `"ambush"`, offering `FIGHT` and `AUTO-WIN (100% - NO XP)`.
- `gartok/app.py`: `_resolve_ambush_autowin` and `_resolve_hunt_autowin` construct a resolved battle object and route through `_battle_end` for standard loot and notice flow.
