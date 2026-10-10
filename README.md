# GARTOK Tactical

An open-world **guild manager** with turn-based tactical combat, based on the
**GARTOK RPG**, rebuilt from the character generator at
[Gerenciador-Gartok](https://github.com/GARCl-A/Gerenciador-Gartok).
It is a sandbox: there is no win condition and no end screen. The run ends only
when the whole guild is wiped out.

Every unit is a randomly generated GARTOK character (race + occupation + 3d6)
and its own individual: the group is a container, the unit is the atom.

**Draft:** the game opens on a pool of nine rolled characters; you keep three.
Those three are your **guild**: name it, pick its banner (colour + emblem —
cosmetic, recolours every unit token from then on), then choose who leads it.
Early mortality is very high on purpose — the starters are meant to be lost.

**Campaign:** the guild is one or more **groups** on the world map, each a
physical unit of members standing on their own node. Give a group an order
(travel, work, or head into a battle / market / tavern / the wilds); once no
group is left idle, the clock runs on its own (`campaign.advance`), resolving
travel and work silently and handing you the rest to actually play. For a
battle you pick a **squad** (1–3 members), drop onto a grid, and win by
putting the enemy team down. Time only passes while the clock is running or on
a group resting (day/night, hunger); death is permanent; a total wipe ends
the run. Each guild is a **world** of its own (a save folder: the current state,
an automatic snapshot before every fight, and named manual saves).

There is no money pool: coins are items in a character's pack. Adventure
out-earns day labour — the lumber yard is only a survival floor — so the risk pays.
What the guild builds is **standing and property**: reputation with factions
(earned by one-shot `deeds` and paid missions — the arena, the Bankers, the
Library, the Tanner), a house in the City or a fenced Claim in the Wilds, wagons
and animals, and a growing set of groups run in parallel.

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
| Pick a character (draft) | click up to three of the nine cards (click again to put one back), then **CONTINUE** |
| Replace a candidate (draft) | **COMMISSION** (top right) → choose archetypes → click the card to replace |
| Walk (1 point) | click a green cell — the path to the cursor is drawn; the walked trail this turn is marked |
| Attack (1 point) | click an enemy with a red outline |
| Throw / Demoralize / Stabilize / First Aid / Pick Up / Defend / Flee / Climb / Push / Jump / Drop In | panel buttons (the aimed ones ask for a target click) |
| Toggle character ↔ squad vision | `L` |
| Inspect a sheet | click any unit |
| End turn | `Space` (defends first when it can) or the button |
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
- **Economy**: money lives on the character as `Copper Coin` ($1) and `Gold Coin`
  ($100) items in the pack (they weigh and split like any item); gold only exists
  through the bank's exchange. A market with haggling by language + Charisma +
  alignment and finite stock per shop; the arena's staked non-lethal bouts; field
  loot; the lumber yard's and the Mine's day-labour wages (the Mine pays $1 more per block and
  sells the stone, ore and coal); the Forge turns learned recipes and
  materials into gear and battlefield traps (`crafting_screen.py`). The numbers are
  kept honest by an economy sim (`scripts/economy_report.py`).
- **Bank**: a rented strongbox at the City, the gold exchange and the Bankers'
  trust mission (`bank_screen.py`, `economy.buy_gold`/`sell_gold`).
- **Medic**: a quick treatment at the Apothecary that mends HP, sickness and poison
  for the potions it would take at a discount; a long one is a hospital stay on a
  `solo` order (`medic.py`, `solo.py`).
- **Wagons and animals**: a group keeps livestock (Donkey, Ox, Horse) and wagons
  (cart, carriage) that carry cargo and passengers by weight, eat, wear down on the
  road and are lost with the group (`wagon.py`, `animals.py`, `stables_screen.py`,
  `garage_screen.py`).
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
  node_functions.py what a node can offer (shop, bank, forge...): order kind + map button, one entry each
  shop.py           a shop's own till and finite shelf, one per node that offers `shop`
  clock.py          the campaign clock (seconds), day/night
  guild.py          the guild = shared state (reputation, taverna pool, leadership, fame slots) + every group;
                    guild_upkeep / guild_holdings / guild_claim / guild_labor hold its behaviour
  holdings.py       Stash (weight-capped storage) and CityProperty (house, tax, squat, oven) and Garage (parked wagons and animals)
  creature.py       shared base of animals and wagons (HP, load, pack-owner calls)
  animals.py        livestock races (Donkey, Ox, Horse) kept in Group.herd, tack decides the role
  wagon.py          a Group's wagons (cart 1 HD, carriage 3 HD) and the draft animals hitched to them (passengers and cargo by weight, feeding); the road wears 1 HP per 100 distance, 0 HP breaks one (repaired for Lumber, or left behind via abandon_screen.py); bought at stables_screen.py
  group.py          Group = a physical subset of the guild: its own node + squad + order;
                    fame buys group slots (`BASE_SLOTS`, `group_slots`)
  cohesion.py       the daily sweep over overextended groups: the weakest member may walk
                    (7-day notice, loot by alignment)
  solo.py           solo tasks (hospital stay, craft): one member busy apart from the group on a `solo` order
  medic.py          the Medic's quick treatment (HP, sickness, poison at the Apothecary) and the hospital stay past 24 h; medic_screen.py is its tab
  orders.py         what a group is doing (travel/work/interactive) and how long it takes
  factions.py       factions and their deeds (one-shot achievements that grant reputation)
  missions.py       paid, deadlined jobs from a named giver (the Tanner, the Bankers'
                    trust chest) -- distinct from a Deed: has a reward and can fail
  arena.py          the Champion of the Pit title: dethrone, defend, the 15/7-day cycle
  campaign.py       folds a battle result back into the guild (permadeath, loot, deeds);
                    also the tick engine (`advance`) that plays orders out
  economy.py        prices, market stock, haggling (language + Charisma + alignment)
  constants.py      tuning knobs shared by economy/justice/campaign (bail, patrols, taxes)
  chest.py          a generic locked pack item (d20+DEX vs DC), opened via group_screen
  justice.py        crime per character, City jurisdiction, the guard's catch/patrol/prison
  recruit.py        the recruitment contest, the weekly tavern pool, and the prison's
                    bail-and-pitch alternative
  vocations.py      the founding trade (six races + one guild perk), read by travel, hunt, work, food and cohesion
  hunt.py           a live wilds hunt: hours, ambush risk, the meat payout
  ox.py             the tanner's last job: the Country Roads search, tracking Aurochs by daylight
  ox_fields.py      the Ox Fields battle: terrain, the herd's call, win on the beast's fall
  persist.py        save slots (JSON); only the roster + campaign meta hit disk
  settings.py       player preferences (settings.json), listed in the pause menu
  combat_log.py     one JSONL per fight, enough to rebuild it: every decision, its options, what the AI would have done
  combat_lab.py     the benchmark fights set up outside a campaign (Editor menu: COMBAT LAB), either side a person or the AI
  recorder.py       opt-in play log (play.jsonl beside the saves) the economy sim learns from
  npc_lib.py        the NPC library (git-tracked npcs/*.json, outside the saves)
  map_lib.py        the map library (git-tracked maps/*.json) + npc_units

  # onboarding + translation (i18n.py is project-wide; tutorial is its first consumer)
  i18n.py           dotted-key string catalogs (locales/*.json), language fallback
  tutorial.py       the tutorial's ids + TutorialState (seen/enabled, pygame-free)

  # screens (Screen base: handle_event / update(dt) / draw(surface), reads self.mouse)
  # every screen draws straight to the real window and lays out from screen.get_size()
  screen.py         the screens' base class (click dispatch -> self._click)
  menu_screen.py / combat_lab_screen.py / vocation_screen.py / draft_screen.py / map_screen.py / guild_screen.py / group_screen.py
  squad_screen.py / battle_screen.py / loot_screen.py / reward_screen.py
  market_screen.py / taverna_screen.py / prison_screen.py / hunt_screen.py / level_screen.py
  bank_screen.py / bank_view_screen.py / tanner_screen.py / trust_screen.py / ledger_screen.py / crafting_screen.py
  city_property_screen.py / garage_screen.py / abandon_screen.py / watch_screen.py / wilds_claim_screen.py / justice_screen.py
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
                    add random talent picks and a per-talent ranking), economy_activities.py
                    (what each activity pays in copper and XP, and the floor check),
                    economy_guild.py (a whole guild living days under a policy, with the
                    race / occupation ranking and the restock sweep), economy_exploits.py
                    (money-from-nothing loops, recipe barriers, dominance), economy_report.py
                    (all of them in one report, with verdicts), ai_usage.py (which actions the combat AI takes, and
                    what losing each costs it), unit_stats.py (creation-stat spread), crafting_cost.py,
                    vocation_report.py (each vocation perk's value as a share of the guild's daily wage,
                    combat_analysis.py (reads the combat logs: action mix, how often a person matched the AI, a replay)
                    item_icon_preview.py (contact sheet of the code-drawn item silhouettes, ui/item_icons.py)
                    combat_pairs.py (the AI replays the squads a person played, lab or campaign logs: its win rate before and after an ai.py change)
                    archive_combat_logs.py (copies each world's campaign combat logs from saves/ into combat_lab/campaign/, which git tracks)
                    gen_portrait.py (medallion portraits from a local Stable Diffusion + the style LoRA, driven by
                    the /gen-portrait skill; portrait_lora/ has the setup and the Colab notebook that trains the LoRA)
docs/plans/         backlog.md (all open work), economy_sim_v2.md (the sim and its findings),
                    campaign_ai_roadmap.md (the long-range AI plan)
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
- **New place on the map**: a `Node` in `world.NODES` listing its `functions` + edges in
  `world.EDGES` (cost in hours). Offering something already built is only the id in the list.
  A new kind of service is one `NodeFunction` in `node_functions.FUNCTIONS` (order kind, button
  label) plus its opener in `app.App._FUNCTION_OPENERS`; a forced fight's aftermath is one line in
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
