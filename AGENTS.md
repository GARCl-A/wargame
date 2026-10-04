# GARTOK Tactical — agent context

Python / pygame-ce turn-based squad wargame rebuilding a lost tabletop RPG from
its character generator. Sandbox guild manager — no win condition, no campaign
end screen. Run ends only on a full wipe.

**Source of truth:** `RULES.md` = design prose (combat, world systems);
`REFERENCE.md` = generated catalog data (`python -m gartok.reference`).
When the two disagree, `REFERENCE.md` wins.

## Conventions

- **All text is English** — UI, combat log, data model, code, docs. Nothing
  pt-BR remains in the repo.
- **Commits** are Portuguese, present tense, no accented characters. No
  `Co-Authored-By:` trailer. Always run the `pre-commit` skill first.
- **Comments** default to none. Keep only a comment that explains a non-obvious
  *why*. Cut anything that restates what the code already says.
- **Tests:** `python -m pytest tests/` — the hard gate. `sim_test.py` is a
  secondary check for combat/AI changes.
- A teammate works on `main` in parallel — branch for anything non-trivial.

## Design premises (durable)

- **Every unit is its own individual.** The group is a container, the unit is
  the atom. A shared activity resolves per-person.
- **World-first.** Rules exist as world things first; if they talk to combat,
  better. Systems land bit by bit.
- **Disposable early squad.** Early mortality is very high; starters are meant
  to be lost.
- **No guild treasury.** Money lives on the character.
- **Vision is per-character.** The map is always dark; on your turn you see
  what the active unit sees.

## Architecture — one concern per module

| Module | Role |
|---|---|
| `unit.py` | persistent character: init, save/load, generation; the rest is mixins — `unit_hunger.py` (meals), `unit_levels.py` (XP tracks, talents), `unit_edit.py` (draft/sandbox setters), `unit_derive.py` (HP/AC/speed + breakdowns), `unit_loadout.py` (hands, armor, pack, stack helpers) |
| `combatant.py` | a Unit *inside one battle* (HP, AP, status, conditions) |
| `battle.py` | board + units + turn flow; wraps each Unit in a Combatant |
| `actions.py` | every combat action is an `Action` subclass |
| `abilities.py` | `Ability` frozen-dataclass registry (passives + hooks) |
| `talents.py` | talent-tree registry mirroring abilities.py |
| `conditions.py` | `Condition` subclasses (Defending, Demoralized) |
| `board.py` | grid geometry, walls, LOS, pathfinding (pure, no battle state) |
| `vision.py` | free fns over battle: light, can_see, visible_cells |
| `ground.py` | GroundObject (weapon, torch) + Creature (neutral body) |
| `scenario.py` | deployment, board setup; the seam for objectives / maps |
| `ai.py` | heuristic over actions.py; alignment tempers behaviour |
| `world.py` | Node graph, edges in hours, route Dijkstra |
| `orders.py` | Order dataclass; AUTO / INTERACTIVE / garrison / forced kinds |
| `campaign.py` | tick engine (`advance`), battle absorption, forced fights |
| `guild.py` | Guild state: groups, roster, leadership, fame slots; owns `bank` + `house`. Behaviour lives in mixins — `guild_upkeep.py` (clock, meals, daily sweep), `guild_holdings.py` (bank, property, debt, garrison), `guild_claim.py` (Wilds claim), `guild_labor.py` (work/crafting shifts) |
| `holdings.py` | what the guild owns: `Stash` (weight-capped storage), `CityProperty` (house, tax, squat) |
| `group.py` | Group = physical subset of the guild (members, node, order) |
| `economy.py` | prices, stock, haggling, garrison/property constants |
| `persist.py` | JSON save/load, SAVE_VERSION, tolerates missing keys |
| `factions.py` | factions + one-shot deeds → reputation |
| `items.py` | single source of truth for all items (ItemDef, ItemInstance, catalog, recipes) |
| `app.py` | pygame shell: scene loop, screen wiring |
| `recruit.py` | recruitment contest (CHA vs CHA, shared language gate) |
| `archetypes.py` | recruit archetype catalog + candidate generation |
| `missions.py` | paid, deadlined jobs from a named giver (has a reward, can fail) |
| `justice.py` | crime per character, City jurisdiction, patrols, prison |
| `arena.py` | Champion of the Pit title and its defense cycle |
| `magic.py` | spell registry + study-difficulty math (casting is in actions.py) |
| `encounters.py` | enemy packs scaled to a target mean level |
| `progression.py` | XP curves + combat-XP rule |
| `autowin.py` | auto-resolve a battle via Monte Carlo estimate |
| `ui/` | war-table component kit; see `ui/README.md` |

Screens follow `screen.Screen` base; `native = True` means full-window layout.
Every `*_screen.py` is one screen; `*_hub_screen.py` wraps a city NPC's shop,
crafting and mission board in tabs. The full module list is in `README.md`.

## UI conventions

**Before any UI work, read `gartok/ui/README.md`** — the design rules
(palette, colour semantics, 8px grid, fonts) and the component catalog.

- **`gartok/ui/` is the single source of truth for screen presentation.**
  Every new screen or non-trivial screen change builds on that component set:
  data-driven `draw_x(surf, F, rect, ...data, mpos)` functions that take plain
  dicts/tuples, never real domain objects (`Group`, `Node`, `Unit`) — the
  screen itself adapts its model into that shape, the component stays
  reusable across screens.
- **`theme.py` is legacy** — the app's original bespoke ramp (`widgets.py` has
  been fully eliminated). Don't add new usage. When a screen gets touched
  non-trivially, migrate it onto `gartok/ui/` instead of extending the old system.
  Buttons, layouts and modals are on `gartok/ui/`; the board's palette and
  camera are `ui/board_style.py`, the banner colour is `ui/banner.py`, and what
  still imports `theme` is five screens/panels that draw their chrome with its
  `panel()`/`text()`/surface ramp. `tests/test_theme_budget.py` lists them (`STILL_ON_THEME`) and
  fails on a new importer — and on an entry that migrated, so take it off the list.
- A `ui/` component never reads module globals or hardcodes screen
  coordinates/fixed pixel widths for panel sizing — it takes its rect/data as
  parameters and sizes/lays out relative to those (proportional-with-clamp
  for anything window-size-dependent, like `map_panel.draw_minimap` already
  does), so the same component holds up at any window size.

## Deep context

For detailed history of any feature or past design decision, use the
`project-context` skill (`.agents/skills/project-context/`). It indexes every
memory from the project's development and has the full files as references —
read only what you need.

## Feature Implementation Rules

Whenever a new mechanic or action is added to the game, you MUST always:
1. **Implement end-to-end**: Backend, core logic, and User Interface (UI). Features must be 100% playable with no loose ends.
2. **AI Support**: Ensure the AI knows how to use and react to the new mechanic during combat.
3. **Automated Tests**: Write tests covering the happy path, edge cases, and AI behavior.
