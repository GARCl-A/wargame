# GARTOK Tactical

A turn-based tactical wargame based on the **GARTOK RPG**, rebuilt from the
character generator at
[Gerenciador-Gartok](https://github.com/GARCl-A/Gerenciador-Gartok).

Every unit is a randomly generated GARTOK character (race + occupation + 3d6).

**Draft:** the game opens on a selection screen — three characters are rolled,
you keep one, three times. Those three are your **guild**.

**Campaign:** the guild roams the world map as a single token. Each place is a
battle, a market, a tavern, the lumber yard, or the wilds. For a battle you pick
a **squad** (1–3 members), drop onto a grid, and win by putting the enemy team
down. Travelling burns the clock (day/night, hunger); death is permanent; a total
wipe ends the run. Saved by slot.

Progress toward the game's goal is **reputation with factions**, earned by
pulling off a faction's signature challenges (`deeds`) — the arena (The Pits) is
the first, with its staked bouts, its champion title, and a three-deed
sub-campaign.

## Run

```
pip install -r requirements.txt
python main.py
```

Tests: `python -m pytest tests/` (rules) and `python sim_test.py`
(200 headless AI-vs-AI battles). `python -m gartok.reference` regenerates
[`REFERENCE.md`](REFERENCE.md).

## Controls

| Action | How |
|---|---|
| Pick a character (draft) | click one of the three cards |
| Edit a candidate (draft) | **EDIT** button (top right) → click "swap" on a card to change race/occupation; **EDITING** again returns to picking |
| Walk (1 point) | click a green cell — the path to the cursor is drawn; the walked trail this turn is marked |
| Attack (1 point) | click an enemy with a red outline |
| Throw / Demoralize / Stabilize / First Aid / Pick Up / Defend / Flee / Climb / Push / Jump / Drop In | panel buttons (the aimed ones ask for a target click) |
| Toggle character ↔ squad vision | `L` |
| Inspect a sheet | click any unit |
| End turn | `Space` or the button |
| Pause / quit | `Esc` |

After a battle, one click returns to the map (or to the loot / reward screens).

Each unit has **2 action points per turn**; every action costs 1 (except End
Turn). Walking moves up to the unit's speed and can be split across clicks.
**Core rule:** bonuses of the same type do not stack (the largest wins); untyped
bonuses and all penalties add.

**Vision is per-character, not per-player:** the map is dark; on your turn you see
only what the active character sees (torches, light items, darkvision). The enemy
squad (red) is a simple AI.

## What came from the generator and what was designed

Ported from the original `.xlsx` sheets (`gartok/data.py`): 3d6 attributes,
18 races with mods and abilities, 31 occupations with a weapon + item, 9
alignments, sizes / speed / carry, the AC / HP / modifier formulas. The full
catalog — every race, occupation, ability, weapon, armor, price, talent and
tunable constant — is generated from the code into [`REFERENCE.md`](REFERENCE.md).

Designed for the wargame (did not exist in the generator), with the full
reconstructed ruleset in [`RULES.md`](RULES.md):

- **d20 combat**: initiative `d20 + WIS mod`; attack `d20 + mods` vs AC; damage =
  weapon die + STR mod (melee); crit on 20, fumble on 1.
- **Action points** (2/turn) and **typed bonuses** (`data.resolve_bonus`).
- **Actions** (`gartok/actions.py`): Walk, Attack, Defend, Throw, Pick Up,
  Demoralize, Stabilize, First Aid, Flee, plus the Z-axis moves Climb / Push /
  Jump / Drop In.
- **Falling / stabilizing / death** (dying → stable | dead), permadeath.
- **Temporary conditions** — Defending, Demoralized (`gartok/conditions.py`).
- **The mechanical effect of the racial abilities** (`gartok/abilities.py`).
- **Vision and light**, walls, ground objects, torches; **a per-cell Z axis**
  (pits, fall damage).
- **Ammo** (crossbow + quiver, reload) and **improvised weapon**; **flanking**
  and Pack Tactics.
- **1 cell = 1.5 m**.

World systems, outside combat:

- **Campaign**: the guild roams the map as one token; a clock + day/night;
  permadeath and save-by-slot (`world.py`, `clock.py`, `guild.py`, `persist.py`).
- **Hunger**: one meal a day, a shared larder; without food, growing penalties
  up to death.
- **Progression**: no classes — each XP track (combat, work) has its own level
  and its own talent tree (`progression.py`, `talents.py`, `level_screen.py`).
- **Economy**: copper on the character (no treasury); a market with haggling by
  language + Charisma + alignment; the arena's staked non-lethal bouts; field
  loot; the lumber yard's day-labour wage.
- **Recruitment**: a tavern pool refreshed weekly; a Charisma-vs-Charisma pitch,
  no money (`recruit.py`).
- **Factions & reputation**: one-shot deeds earn per-faction standing
  (`factions.py`); the arena's champion title lives in `arena.py`.
- **Editors**: sandbox character and map creators (`char_editor_screen.py`,
  `map_editor_screen.py`) writing git-tracked content to `npcs/` and `maps/`.

## Structure

Identifiers are English; so is the domain content (race, occupation, alignment,
size, language, weapon and item names). Only [`RULES.md`](RULES.md) design prose
may lag the code wording.

```
gartok/
  # domain + combat rules
  data.py           GARTOK tables (ported) + weapons/weights/constants (designed),
                    dice, typed bonuses, alignment axes
  reference.py      walks the registries -> REFERENCE.md (the data dictionary)
  abilities.py      racial abilities: each one's numeric passive and/or hook
  conditions.py     a combatant's temporary states (Defending, Demoralized, ...)
  actions.py        combat actions (cost, target, can/execute) + the PANEL_ACTIONS registry
  board.py          grid, walls, elevation, pathfinding (Dijkstra), line of sight
  vision.py         light + what each character sees (screen vision)
  ground.py         ground objects (GroundObject) and neutral creatures (Creature)
  scenario.py       builds a battle's map: terrain, deployment, torches; win_check seam
  encounters.py     enemy packs scaled to a target mean level
  unit.py           Unit = the persistent character (race/occupation/attributes/hunger/loadout/talents)
  combatant.py      Combatant = a Unit inside one battle (HP/AP/pos/conditions/hands)
  battle.py         battle state (wraps each unit in a Combatant), initiative, death
  ai.py             enemy squad AI (over actions.py); alignment tempers the edges
  loot.py           gathers the field loot after a lethal win
  progression.py    XP curves + the combat-XP rule (pure data, no gartok imports)
  talents.py        the talent trees: one per XP track, Effect(channel, amount, stat)

  # world + campaign
  world.py          the map graph: nodes, edges (hours), route (Dijkstra), Bout (arena offers)
  clock.py          the campaign clock (seconds), day/night
  guild.py          the guild = the roster; daily time/hunger, summed gold, per-faction reputation
  factions.py       factions and their deeds (one-shot achievements that grant reputation)
  arena.py          the Champion of the Pit title: dethrone, defend, the 15/7-day cycle
  campaign.py       folds a battle result back into the guild (permadeath, loot, deeds)
  economy.py        prices, market stock, haggling (language + Charisma + alignment)
  recruit.py        the recruitment contest + the weekly tavern pool
  hunt.py           a live wilds hunt: hours, ambush risk, the meat payout
  persist.py        save slots (JSON); only the roster + campaign meta hit disk
  npc_lib.py        the NPC library (git-tracked npcs/*.json, outside the saves)
  map_lib.py        the map library (git-tracked maps/*.json) + npc_units

  # screens (Screen base: handle_event / update(dt) / draw(surface), reads self.mouse)
  # every screen draws straight to the real window and lays out from screen.get_size()
  screen.py         the screens' base class (click dispatch -> self._click)
  menu_screen.py / draft_screen.py / map_screen.py / guild_screen.py / gear_screen.py
  squad_screen.py / battle_screen.py / loot_screen.py / reward_screen.py
  market_screen.py / taverna_screen.py / work_screen.py / hunt_screen.py / level_screen.py
  pause_screen.py / editor_menu_screen.py / char_editor_screen.py / map_editor_screen.py

  # shared presentation
  theme.py          the design system: spacing scale (SP), palette, two font families,
                    widgets (panel, chip, section, pips, Stack, token_badge)
  icons.py          vector action icons (pygame.draw) -- no asset file
  artwork.py        loads/tints/caches the SVGs under assets/icons/ (race silhouettes on the token)
  lighting.py       LightRenderer: the darkness layer + radial light holes
  sheet.py          formats a Unit into text lines (battle-inspect panel)
  sheet_panel.py    the full drawn character sheet (guild-screen modal)

  app.py            the pygame shell: resizable window, loop, screen switching,
                    the campaign <-> battle loop
main.py             entry point
tests/              the rule tests, one file per domain (run: python -m pytest tests/)
sim_test.py         headless simulation (200 AI-vs-AI battles)
balance_sim.py      the balance tournament (race / occupation / combo rankings)
economy_sim.py      the trade counterpart (net copper by race / occupation)
```

> Rendering is procedural, with one exception: `artwork.py` loads the SVGs under
> `gartok/assets/icons/` (game-icons.net) — today only the race silhouettes on
> the unit token and the talent-node icons. `gartok/assets/dungeon/` +
> `tileset.py` are orphaned, kept on disk in case props (barrels, chests) return.

### How to add a system

- **New action** (e.g. Grapple): an `Action` class in `actions.py` and an entry
  in `PANEL_ACTIONS`. The UI and the AI see it for free.
- **New combat state** (e.g. poison, prone, blind): a `Condition` class in
  `conditions.py`; whoever applies it calls `combatant.add_condition(...)`.
- **New racial ability**: an `Ability` in `abilities.py`. If it reuses the
  existing passives and hooks (`hp_max`, `speed`, …, `on_turn_start`,
  `on_attack_miss`, …) that file is the only edit. A brand-new *kind* of hook
  still needs a core call site (`combatant.py` for combat, `unit.py` for
  derivation) — there is no plugin bus.
- **New persistent character state** (e.g. wounds, fatigue): a field on `unit.py`,
  folded into `Unit._derive_combat` if it moves the numbers, saved in
  `persist.unit_to_dict` / `Unit.from_save`. `Combatant` reads it for free.
- **New ground-object type**: a new `kind` on `ground.GroundObject` and the rule
  that reacts to it (consumers ask `obj.kind` / `obj.is_weapon`).
- **New battle scenario** (prebuilt map, deployment zones, lighting): a `Scenario`
  subclass with `build(battle)` in `scenario.py`; point a `world.Node` at it. A
  non-elimination objective goes through `Scenario.win_check` (the seam exists;
  nothing overrides it yet).
- **New place on the map**: a `Node` in `world.NODES` + edges in `world.EDGES`
  (cost in hours). `app` turns the node's `kind` into the activity.
- **New world system** (outside combat): the routine that passes time in
  `guild.pass_time` / `_daily_upkeep`; the battle result that returns to the
  roster in `campaign.absorb_battle`.
- **New faction or deed** (objective / reputation): a `Faction` or a `Deed` in
  `factions.py`. `Deed.check(guild, node, outcome)` runs in `factions.settle`,
  called by `campaign.absorb_battle` — today only post-battle; another trigger
  (post-market, post-travel) needs one more `settle` call at that event.
- **New light source**: `vision.unit_light` / `ground_light`.
