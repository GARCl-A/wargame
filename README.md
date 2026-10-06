# GARTOK Tactical

A turn-based tactical wargame based on the **GARTOK RPG**, rebuilt from the
character generator at
[Gerenciador-Gartok](https://github.com/GARCl-A/Gerenciador-Gartok).

Every unit is a randomly generated GARTOK character (race + occupation + 3d6).

**Draft:** the game opens on a selection screen — three characters are rolled,
you keep one, three times. Those three are your **guild**: name it, pick its
banner (colour + emblem — cosmetic, recolours every unit token from then on),
then choose who leads it.

**Campaign:** the guild is one or more **groups** on the world map, each a
physical unit of members standing on their own node. Give a group an order
(travel, work, or head into a battle / market / tavern / the wilds); once no
group is left idle, the clock runs on its own (`campaign.advance`), resolving
travel and work silently and handing you the rest to actually play. For a
battle you pick a **squad** (1–3 members), drop onto a grid, and win by
putting the enemy team down. Time only passes while the clock is running or on
a MAINTENANCE stop (day/night, hunger); death is permanent; a total wipe ends
the run. Saved by slot.

Progress toward the game's goal is **reputation with factions**, earned by
pulling off a faction's signature challenges (`deeds`) — the arena (The Pits) is
the first, with its staked bouts, its champion title, and a three-deed
sub-campaign.

## Run

```
pip install -r requirements.txt
python main.py
```

Dev tools (pytest, ruff) live apart from the game's own requirements:
`pip install -r requirements-dev.txt`.

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
- **Actions** (`gartok/actions/`): Walk, Attack, Defend, Throw, Pick Up,
  Demoralize, Stabilize, First Aid, Flee, plus the Z-axis moves Climb / Push /
  Jump / Drop In.
- **Falling / stabilizing / death** (dying → stable | dead), permadeath.
- **Temporary conditions** — Defending, Demoralized (`gartok/conditions.py`).
- **The mechanical effect of the racial abilities** (`gartok/abilities.py`).
- **Vision and light**, walls, ground objects, torches; **a per-cell Z axis**
  (pits, fall damage); **water** — shallow (difficult terrain) and deep (Swim,
  hold your breath or drown).
- **Ammo** (crossbow + quiver, reload) and **improvised weapon**; **flanking**
  and Pack Tactics.
- **1 cell = 1.5 m**.

World systems, outside combat:

- **Campaign**: the guild's members are split across **groups**, each its own
  token that can travel/work/act independently; a tick/orders engine
  (`gartok/orders.py`, `campaign.advance`) advances the shared clock + day/night
  to the next order due; permadeath and save-by-slot (`world.py`, `clock.py`,
  `guild.py`, `group.py`, `persist.py`).
- **Identity**: the guild's name and banner (colour + emblem), picked at the
  draft — cosmetic, recolours every unit token for the run
  (`ui.banner.set_player_color`, `Guild.banner_color`/`banner_icon`).
- **Leadership**: the guild has one leader ("who am I", chosen at the draft);
  every group has its own (who speaks for it, freely swappable); a group's
  leader caps how many members it can hold before cohesion costs Mental
  Defense (`Group.leader`/`capacity`, `Guild.leader`).
- **Hunger**: one meal a day, a shared larder; without food, growing penalties
  up to death.
- **Progression**: no classes — each XP track (combat, work) has its own level
  and its own talent tree (`progression.py`, `talents.py`, `level_screen.py`).
- **Magic**: a first foothold, not a full system yet — three spells gated by a
  racial magic source, cast in battle (`actions.CastSpellAction`, `ai.py`),
  learned by studying at the taverna over several in-game days (`magic.py`).
- **Economy**: copper on the character (no treasury); a market with haggling by
  language + Charisma + alignment; the arena's staked non-lethal bouts; field
  loot; the lumber yard's day-labour wage; the Forge turns learned recipes and
  materials into gear and battlefield traps (`crafting_screen.py`).
- **Recruitment**: a tavern pool refreshed weekly (no money, a Charisma-vs-
  Charisma pitch) or the prison's bail-and-pitch alternative (pay first, then
  pitch); each member can only sponsor so many people (Charisma-gated), the
  guild leader's own level adding a strong bonus on top (`recruit.py`).
- **Factions & reputation**: one-shot deeds earn per-faction standing
  (`factions.py`); the arena's champion title lives in `arena.py`. Paid,
  deadlined **missions** from a named giver (the Tanner, the Bankers) are a
  separate, failable track alongside the silent deeds (`missions.py`).
- **Base-building**: two paths to guild property, both playable start to
  finish — a taxed house bought from the Bankers in the City, or a Wilds
  claim fenced and garrisoned by hand through a scout/clear/fence/sweep/
  sustain campaign, contestable by raids and seizure once established
  (`city_property_screen.py`, `wilds_claim_screen.py`).
- **Crime & justice**: a personal rap sheet that can get a character caught by
  the City guard at a jurisdiction node — accept prison time, fight the
  patrol, or flee; the Old Road carries its own ambush risk regardless of
  crime (`justice.py`).
- **Editors**: sandbox character and map creators (`char_editor_screen.py`,
  `map_editor_screen.py`) writing git-tracked content to `npcs/` and `maps/`. The
  map editor sets the grid size and paints walls / pits / water / torches / zones.
- **Onboarding**: a modal, once-per-slot tutorial (`tutorial.py`/`tutorial_card.py`)
  teaching how to play and how to use each screen (draft, map with the clock and
  hunger, each guild-screen tab, group gear, squad, battle, loot, reward, market,
  taverna, the wilds, the bank, paid jobs, the forge, the house, the claim, the
  guard, the prison, progression) — the first time a screen (or tab, or draft phase) matters, a
  centred card over a dimmed screen explains it, some pointing at where to look
  next, dismissed with a click or Enter/Space (input is swallowed while it is up
  and just after, so closing it never presses what lies beneath) and reopenable
  from its `?` badge; per-slot, toggled and reset
  from the pause menu. Its copy is the first thing routed through `i18n.py`, a
  small dotted-key catalog reader (`locales/en.json`) meant to grow into the
  game's general translation layer, not a tutorial-only shim.

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
  actions/          combat actions (cost, target, can/execute): base, combat, movement, support, spells;
                    the PANEL_ACTIONS registry lives in __init__.py
  board.py          grid, walls, elevation, pathfinding (Dijkstra), line of sight
  vision.py         light + what each character sees (screen vision)
  ground.py         ground objects (GroundObject) and neutral creatures (Creature)
  scenario.py       builds a battle's map: terrain, deployment, torches; win_check seam
  encounters.py     enemy packs scaled to a target mean level
  matchup.py        (node, arena Bout) -> the opponents + the scenario for one fight
  unit.py           Unit = the persistent character (init, save/load, generation), built from mixins:
                    unit_hunger / unit_levels / unit_edit / unit_derive / unit_loadout
  combatant.py      Combatant = a Unit inside one battle (HP/AP/pos/conditions/hands)
  battle.py         battle state (wraps each unit in a Combatant), initiative, death
  ai.py             enemy squad AI (over actions/); alignment tempers the edges
  items.py          every item in the game: ItemDef/ItemInstance, catalog, recipes
  archetypes.py     recruit archetype catalog, candidate generation, commission constraints
  names.py          procedural personal names for every generated Unit
  autowin.py        auto-resolve a battle: background Monte Carlo estimate
  loot.py           gathers the field loot after a lethal win
  progression.py    XP curves + the combat-XP rule (pure data, no gartok imports)
  talents.py        the talent trees: one per XP track, Effect(channel, amount, stat)
  magic.py          spell registry (level, sources) + study-difficulty math -- casting
                    lives in actions/spells.py CastSpellAction, learned via the taverna's
                    "study" garrison job (guild.py), AI use in ai.py

  # world + campaign
  world.py          the map graph: nodes, edges (distance), route (Dijkstra), Bout (arena offers)
  clock.py          the campaign clock (seconds), day/night
  guild.py          the guild = shared state (reputation, taverna pool, leadership, fame slots) + every group;
                    guild_upkeep / guild_holdings / guild_claim / guild_labor hold its behaviour
  holdings.py       Stash (weight-capped storage) and CityProperty (house, tax, squat, oven) and Garage (parked wagons and animals)
  creature.py       shared base of animals and wagons (HP, load, pack-owner calls)
  animals.py        livestock races (Donkey, Ox, Horse) kept in Group.herd, tack decides the role
  wagon.py          a Group's wagons (cart, carriage) and the draft animals hitched to them (passengers and cargo by weight, feeding); bought at stables_screen.py
  group.py          Group = a physical subset of the guild: its own node + squad + order;
                    fame buys group slots (`BASE_SLOTS`, `group_slots`)
  cohesion.py       the daily sweep over overextended groups: the weakest member may walk
                    (7-day notice, loot by alignment)
  orders.py         what a group is doing (travel/work/interactive) and how long it takes
  factions.py       factions and their deeds (one-shot achievements that grant reputation)
  missions.py       paid, deadlined jobs from a named giver (the Tanner, the Bankers'
                    trust chest) -- distinct from a Deed: has a reward and can fail
  arena.py          the Champion of the Pit title: dethrone, defend, the 15/7-day cycle
  campaign.py       folds a battle result back into the guild (permadeath, loot, deeds);
                    also the tick engine (`advance`) that plays orders out
  economy.py        prices, market stock, haggling (language + Charisma + alignment)
  constants.py      tuning knobs shared by economy/justice/campaign (bail, patrols, taxes)
  chest.py          a generic locked pack item (d20+DEX vs DC), opened via gear_screen
  justice.py        crime per character, City jurisdiction, the guard's catch/patrol/prison
  recruit.py        the recruitment contest, the weekly tavern pool, and the prison's
                    bail-and-pitch alternative
  hunt.py           a live wilds hunt: hours, ambush risk, the meat payout
  persist.py        save slots (JSON); only the roster + campaign meta hit disk
  npc_lib.py        the NPC library (git-tracked npcs/*.json, outside the saves)
  map_lib.py        the map library (git-tracked maps/*.json) + npc_units

  # onboarding + translation (i18n.py is project-wide; tutorial is its first consumer)
  i18n.py           dotted-key string catalogs (locales/*.json), language fallback
  tutorial.py       the tutorial's ids + TutorialState (seen/enabled, pygame-free)

  # screens (Screen base: handle_event / update(dt) / draw(surface), reads self.mouse)
  # every screen draws straight to the real window and lays out from screen.get_size()
  screen.py         the screens' base class (click dispatch -> self._click)
  menu_screen.py / draft_screen.py / map_screen.py / guild_screen.py / group_screen.py
  gear_screen.py / squad_screen.py / battle_screen.py / loot_screen.py / reward_screen.py
  market_screen.py / taverna_screen.py / prison_screen.py / hunt_screen.py / level_screen.py
  bank_screen.py / bank_view_screen.py / tanner_screen.py / trust_screen.py / ledger_screen.py / crafting_screen.py
  city_property_screen.py / garage_screen.py / watch_screen.py / wilds_claim_screen.py / justice_screen.py
  alert_screen.py / adelio_prompt_screen.py
  bank_hub_screen.py / library_hub_screen.py / apothecary_hub_screen.py (tabbed hubs
  wrapping a shop/strongbox, crafting and a mission board)
  library_screen.py / library_mission_screen.py / apothecary_mission_screen.py
  pause_screen.py / editor_menu_screen.py / char_editor_screen.py / map_editor_screen.py

  # shared presentation
  ui/               the war-table component kit -- the source of truth for screen
                    presentation (rules + catalog in ui/README.md)
  icons.py          vector action icons (pygame.draw) -- no asset file
  artwork.py        loads/tints/caches the SVGs under assets/icons/ and the race
                    portraits under assets/portraits/
  lighting.py       LightRenderer: the darkness layer + radial light holes
  battle_fx.py      combat juice: floating numbers, hit/lunge reactions
  dragselect.py     shared press/drag/drop plumbing for the item screens
  packbox.py        shared drag bookkeeping for the gear and group screens
  stash_screen.py   shared body of the bank / city-property screens (move gear party <-> Stash)
  sheet_panel.py    the full drawn character sheet (guild-screen modal)
  tutorial_card.py  draws the current screen's tutorial card + its `?` badge

  app.py            the pygame shell: resizable window, loop, screen switching,
                    the campaign <-> battle loop
main.py             entry point
tests/              the rule tests, one file per domain (run: python -m pytest tests/)
sim_test.py         headless simulation (200 AI-vs-AI battles)
scripts/            balance_sim.py (race / occupation / combo rankings; --level / --racial
                    add random talent picks and a per-talent ranking), economy_sim.py
                    (net copper by race / occupation / talent; modes bleed, production,
                    work, arbitrage), ai_usage.py (which actions the combat AI takes, and
                    what losing each costs it), unit_stats.py (creation-stat spread), crafting_cost.py
docs/plans/         design plans not yet built (campaign AI roadmap)
```

> Rendering is procedural, with two asset-backed exceptions: `artwork.py` loads
> the SVG silhouettes under `gartok/assets/icons/` (game-icons.net) and the race
> medallion portraits under `gartok/assets/portraits/`.

### How to add a system

- **New action** (e.g. Grapple): an `Action` class in the fitting `actions/` module and an entry
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
  non-elimination objective goes through `Scenario.win_check` (capture-the-flag
  `_FlagObjective` and `AncientRuinsScenario` already override it).
- **New place on the map**: a `Node` in `world.NODES` + edges in `world.EDGES`
  (cost in hours). An order's `kind` becomes its screen through one line in
  `app.App._ACTIVITY_OPENERS`; a forced fight's aftermath is one line in
  `_FORCED_FIGHT_RESOLVERS`.
- **New world system** (outside combat): the routine that passes time in
  `guild.pass_time` / `_daily_upkeep`; the battle result that returns to the
  roster in `campaign.absorb_battle`.
- **New faction or deed** (objective / reputation): a `Faction` or a `Deed` in
  `factions.py`. `Deed.check(guild, event)` runs in `factions.settle(guild,
  Event(kind, ...))`, which already fires after a battle (`campaign.absorb_battle`),
  arriving on a node, a market buy/sell and a mission turn-in. A new trigger
  (hunt, work shift, crafting, recruit, study) is one more `settle` call at
  that event, plus a field on `Event` if the check needs one.
- **New light source**: `vision.unit_light` / `ground_light`.
- **New tutorial card** (a screen or a tab/phase of one): an id in
  `tutorial.TUTORIALS`, a `title`/`body`/optional `suggestion` block under
  `tutorial.<id>` in `locales/en.json`, and a `tutorial_key()` override on the
  screen (and `tutorial_badge_rect()` if the default top-right `?` would
  collide with something clickable). `app.py`'s draw/input hooks pick it up for
  free — see `screen.py`'s two defaults for the contract.
- **New translated string anywhere else**: a key under its own namespace in
  `locales/en.json`, read with `i18n.t(key)` — `tutorial.*` is the only
  namespace actually converted so far; the rest of the game's text is still
  literal, on purpose (this is the framework, not a translation pass).
