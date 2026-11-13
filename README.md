# GARTOK Tactical

A guild-manager sandbox with turn-based tactical combat, rebuilt from the character generator
([Gerenciador-Gartok](https://github.com/GARCl-A/Gerenciador-Gartok)) of a lost tabletop RPG, GARTOK.
You draft three rolled characters, lead them as groups across a world map, fight, trade and build, and
lose them: death is permanent and the run ends only when the whole guild is wiped out. The game is a web
client over a Python core; pygame survives only in the Editor.

## Run

```
pip install -r requirements.txt      # the game needs nothing but the standard library
python main.py                       # the game, in a browser window (Edge or Chrome in app mode): the way to develop
cd shell && npm ci && npm start      # the game in the native client (Electron, needs Node): the way it ships
pip install -r editor/requirements.txt && python -m editor   # the Editor, a separate pygame program: characters, maps, the combat lab
```

`python -m gartok` is the same as `python main.py`; `python -m gartok.web --help` lists the browser's own
flags. The server stops when the window is closed. `build_exe.bat` builds the native client (Node on PATH) and
leaves `dist/GARTOK-<version>-win64.zip`; `npm start -- --cache-static` runs the client the way the build does.

Dev tools (pytest, pytest-xdist, ruff) live apart: `pip install -r requirements-dev.txt`.

```
python -m pytest tests/ -n auto -m "not balance"   # the gate; the tiers are in tests/README.md
python sim_test.py                                 # 200 headless AI-vs-AI battles
python -m gartok.reference                         # regenerates REFERENCE.md
```

## Where things are written

| Topic | Read |
|---|---|
| The rules and the design premises | [`RULES.md`](RULES.md) |
| The design catalog for developers and agents, spoilers included: races, creatures, weapons, prices, talents, constants (generated) | [`REFERENCE.md`](REFERENCE.md) |
| Rules for an agent working on the repo | [`AGENTS.md`](AGENTS.md) |
| Building a web screen | [`docs/web_ui/web_client.md`](docs/web_ui/web_client.md) |
| Open work | [`docs/plans/backlog.md`](docs/plans/backlog.md) |
| The Editor's UI kit | [`editor/ui/README.md`](editor/ui/README.md) |

Identifiers and domain content are English; only the prose of `RULES.md` may lag the code wording.

## Structure

```
gartok/
  # domain + combat rules
  data.py           GARTOK tables (ported) + weapons/weights/constants (designed),
                    dice, typed bonuses, alignment axes
  reference.py      walks the registries -> REFERENCE.md (the data dictionary)
  abilities.py      racial abilities: each one's numeric passive and/or hook
  conditions.py     a combatant's temporary states (Defending, Demoralized, ...)
  actions/          combat actions (cost, target, can/execute): base, combat, movement, support, spells,
                    weapon_actions; the PANEL_ACTIONS registry lives in __init__.py
  board.py          grid, walls, elevation, pathfinding (Dijkstra), line of sight
  vision.py         light + what each character sees (screen vision)
  fog.py            fog of war: the side's memory of the cells it has seen
  morale.py         a fighter's nerve in a lethal fight: start value, what moves it, Routed at 0 (`settle` is the one hook)
  intel.py          what a side knows of a foe (INT read, Assess, bestiary); foe_card.py adapts it for the card
  ground.py         ground objects (GroundObject) and neutral creatures (Creature)
  scenario.py       builds a battle's map: terrain, deployment, torches; win_check seam
  encounters.py     enemy packs scaled to a target mean level
  starter_kit.py    the random weapon and item a fresh recruit starts with
  outfit.py         a generated enemy's kit bought with its racial level's budget
  matchup.py        (node, arena Bout) -> the opponents + the scenario for one fight
  unit.py           Unit = the persistent character (init, save/load, generation), built from mixins:
                    unit_hunger.py / unit_levels.py / unit_edit.py / unit_derive.py / unit_loadout.py / unit_poison.py
  poisons.py        persistent poisons (Snake Venom, Spider Venom, Gut Rot): levels, saves, Antidote
  combatant.py      Combatant = a Unit inside one battle (HP/AP/pos/conditions/hands)
  battle.py         battle state (wraps each unit in a Combatant), initiative, death
  ai/               enemy squad AI (over actions/); alignment tempers the edges. `turn.take_turn` runs one turn
                    over the rest: common (shared helpers), reckon (hit odds and what a blow, spell or shove
                    is worth), attack (which attack or special move), support (allies, mounts, potions),
                    target (who to fight, searching, flanking), flee (running, delaying, skittish beasts),
                    movement (steps, terrain, traps, picking things up), scripted (capture the flag,
                    patrols, the heist, the necromancer). A threshold lives in the module that uses it
                    (`ai.module_of(name)`); a test patches a function in the module that calls it
  items.py          every item in the game: ItemDef/ItemInstance, catalog, recipes
  item_icon.py      what each item (and each vocation) looks like (kind, material, shape) for the Editor's code-drawn icons (editor/ui/item_icons.py)
  weapon_traits.py  weapon traits registry: immutable keyword model (Finesse, Thrown, crit/action seams) mirroring abilities.py
  natural_weapons.py the body as a weapon: Unarmed and the beasts' Bite/Fangs/Claws, one ItemDef per body size, outside the item registry
  craft_level.py    a recipe's difficulty level, worked out from its requirements, reagents and batch time
  workbench.py      a station's bench (`Bench`: the crafters, their recipes, what the packs lack,
                    a stint waited out or alone)
  archetypes.py     recruit archetype catalog, candidate generation, commission constraints
  names.py          procedural personal names for every generated Unit
  autowin.py        auto-resolve a battle: background Monte Carlo estimate
  loot.py           gathers the field loot after a lethal win
  spoils.py         the field's loot split among the survivors (the report's FIELD)
  aftermath.py      what the screens after a fight read (report rows, takedowns, LevelUp, Memorial,
                    result_word), filled by campaign.absorb_battle
  progression.py    XP curves + the combat-XP rule (pure data, no gartok imports)
  talents.py        the talent trees: one per XP track, Effect(channel, amount, stat)
  magic.py          spell registry (level, sources) + study-difficulty math -- casting
                    lives in actions/spells.py CastSpellAction, learned via the taverna's
                    "study" garrison job (guild.py), AI use in ai/

  # world + campaign
  world.py          the map graph: nodes, edges (distance), route (Dijkstra), Bout (arena offers)
  node_functions.py what a node can offer (shop, bank, forge...): order kind + map button, one entry each
  map_view.py       what the map shows of a band and its node (`MapView`: inspector blocks,
                    the order's status, the REST plans, `NODE_ICON`), read by web/map_session.py
  shop.py           a shop's own till and finite shelf, one per node that offers `shop`
  trade.py          a shop's counter: buying, selling, the purse, the deal, the moves between packs
                    (`Counter`, the Library's `LibraryCounter`); web/shop_tab.py trades through it
  vault.py          a stash's counter: the Bank's strongbox and gold exchange (`BankVault`),
                    the City house's stash, oven and debt (`HouseVault`)
  tavern.py         the Tavern's counter (`Tavern`: the pitch, the study rooms, the stage;
                    `Prison`: the cells, with a bail)
  work_desk.py      a work node's desks (Lumber Yard, Mine): WORK (`WorkDesk`: paid shifts, each
                    worker's tool and wage) and GATHERING (`GatherDesk`: the licence, what a shift is worth)
  stables.py        the Farm's stables and the Carpenter's wagon yard (`Stables`, `WagonYard`:
                    the purse, the herd limit, the tack, the resale)
  ledger.py         Field Command's desk (`LedgerDesk`: the chest, the mentorship, the supply run);
  job_board.py      each giver's jobs board (`Board`, `TannerBoard`, `ShrineBoard`, ...: the offers,
                    the signing, the turn-in and its notice)
  claim_desk.py     the Wilds Claim's work (`ClaimDesk`: scouting, the fences, the garrison, the hearth);
  clock.py          the campaign clock (seconds), day/night
  guild.py          the guild = shared state (reputation, taverna pool, leadership, fame slots) + every group;
                    guild_upkeep.py / guild_holdings.py / guild_claim.py / guild_labor.py hold its behaviour
  guild_log.py      `GuildLog`: what happened while the days passed, kept per guild and saved with it (`Guild.log`,
                    each line written where it is born: the clock's upkeep and orders, a fight, a talk; the map's
                    log panel reads it, the limit is the `log_lines` setting)
  holdings.py       Stash (weight-capped storage, in stash.py) and CityProperty (house, tax, squat, oven) and Garage (parked wagons and animals); GarageDesk is a garage's counter
  creature.py       shared base of animals and wagons (HP, load, pack-owner calls)
  animals.py        livestock races (Donkey, Ox, Horse) kept in Group.herd, tack decides the role
  wagon.py          a Group's wagons (cart 1 HD, carriage 3 HD) and the draft animals hitched to them (passengers and cargo by weight, feeding); the road wears 1 HP per 100 distance, 0 HP breaks one (repaired for Lumber); bought at the Carpenter (stables.WagonYard); wagon_watch.py is the wagon left outside the Ruins or a hunt
  group.py          Group = a physical subset of the guild: its own node + squad + order;
                    fame buys group slots (`BASE_SLOTS`, `group_slots`)
  cohesion.py       the daily sweep over overextended groups: the weakest member may walk
                    (7-day notice, loot by alignment)
  solo.py           solo tasks (hospital stay, craft): one member busy apart from the group on a `solo` order
  stints.py         hours a band spends where it stands (a show, a Medic's visit, the claim's work, a repair):
                    a `work` order with its `task`, settled by `campaign.advance` when the hours are up
  investigation.py  asking around in a place's Jobs tab: an hour of Charisma, one answer per (job, place), the clue count other rolls read
  medic.py          the Medic's quick treatment (HP, sickness, poison at the Apothecary) and the hospital stay past 24 h; `Ward` is its tab
  rite.py           initiation into a magic school at its hidden sanctuary: the reputation door, boarding on a `garrison("rite")` order, the blood test, the board; `Initiation` is its tab
  orders.py         what a group is doing (travel/work/interactive) and how long it takes
  routine_book.py   the Book of routines: the routines the player has written (`Page`, `check`, `equip` / `adjust` / `take_off` / `save_back` for a group's copy) and how many groups may run one (seats from fame, none to start)
  routines.py       the blocks a player gives a group to run under its orders (travel, gather, work, craft, study, repair, rest, wait, take, hand over, store, fetch, trade, repeat); `campaign.advance` asks it for the next order
  rest.py           what a rest order costs in rations and how long "until full" lasts
  factions.py       factions and their deeds (one-shot achievements that grant reputation)
  objectives.py     the guild's 17 small orientation tasks (REPUTATIONS tab), each teaching a system
  missions.py       paid, deadlined jobs from a named giver (the Tanner, the Bankers'
                    trust chest) -- distinct from a Deed: has a reward and can fail
  arena.py          the Champion of the Pit title: dethrone, defend, the 15/7-day cycle
  campaign.py       folds a battle result back into the guild (permadeath, loot, deeds);
                    also the tick engine (`advance`) that plays orders out
  forced.py         forced events (guard, ambushes, raids, seizures): where each is caught,
                    how it is played and settled, one `ForcedEvent` per kind in `EVENTS`
  fight_nature.py   sought / opportunist / determined: what kind of fight each source declares
  economy.py        prices, market stock, haggling (language + Charisma + alignment)
  constants.py      tuning knobs shared by economy/justice/campaign (bail, patrols, taxes)
  checks.py         the d20 a player's order rolls outside a fight (`Check` on `guild.table`, drained into the web answer)
  chest.py          a generic locked pack item (d20+DEX vs DC), opened from the band's item menu
  justice.py        crime per character, City jurisdiction, the guard's catch/patrol/prison
  lair.py           the Dragon's Lair under the Mine: a heist past kobold patrols and a sleeping dragon
  dialogue.py       the talk before a fight: the verbs (persuade, bluff, intimidate, bribe...),
                    the checks, the encounters (ambush, patrol, Wildfire) and the squad's AI
  draw.py           the Draw action's rules: what the two hands hold, what a draw or a stow puts back in the pack
  draft.py          a new guild's draft: the pool of nine, three picks, the commission tokens, the charter
  recruit.py        the recruitment contest, the weekly tavern pool, and the prison's
                    bail-and-pitch alternative
  vocations.py      the founding trade (six races + one guild perk), read by travel, hunt, work, food and cohesion
  hunt.py           a live wilds hunt: hours, ambush risk, the meat payout
  sources.py        where each base material comes from (derived base materials, a source each)
  gather.py         gathering at the Lumber Yard and the Mine: licence, drop tables, haul, ambush
  serpent_nest.py   the Snake Dragon job: the nest search off the Lumber Yard and its dark dungeon
  battlefield.py    the Faith Order's errand: the border skirmish beside Field Command's AI-played soldiers
  necromancer.py    the Faith Order's second errand: three sides at the front and an invisible necromancer raising the dead
  wildfire.py       the Nature Coven's errand: the Ogre's wildfires, ethereal nodes that burn and spread
  fortress_scenario.py  the Ogre's half-raised fortress: walls, a spreading bonfire, won when he falls
  captives.py       foes bound in battle and kept by a group: herd room, 7 days to live
  ox.py             the tanner's last job: the Country Roads search, tracking Aurochs by daylight
  ox_fields.py      the Ox Fields battle: terrain, the herd's call, win on the beast's fall
  cult_site.py      the Demon Cult's hidden site (the Farmer's job): the Country Roads search that finds it, the ritual fight (bar, Final Rite, the Demon's non-lethal ending), the failure's clock and its node, on the map only once found
  demon_lair.py     the Demon's lair at that site, 15 days after a failed rite: the lone lethal fight; its death reopens the Farm
  persist.py        save slots (JSON); only the roster + campaign meta hit disk
  version.py        GAME_VERSION + build hash; docs/versions.csv is the release table, scripts/version_check.py guards it
  update_check.py   start-up check for a newer GitHub release: one anonymous GET in a thread, the title's notice
  playtest_export.py  the Settings "Export playtest data" zip (saves, combat logs, build)
  fault_log.py      every unexpected exception and script error, one JSON line each in saves/errors.jsonl (the playtest zip carries it)
  settings.py       player preferences (settings.json), listed on the settings screen
  combat_log.py     one JSONL per fight, enough to rebuild it: every decision, its options, what the AI would have done
  combat_lab.py     the benchmark fights set up outside a campaign (Editor menu: COMBAT LAB), either side a person or the AI
  recorder.py       opt-in play log (play.jsonl beside the saves) the economy sim learns from
  npc_lib.py        the NPC library (git-tracked npcs/*.json, outside the saves)
  map_lib.py        the map library (git-tracked maps/*.json) + npc_units

  # onboarding + translation (i18n.py is project-wide; tutorial is its first consumer)
  i18n.py           dotted-key string catalogs (locales/*.json): t / plural / name / desc / gender, language fallback
  tutorial.py       the tutorial's ids + TutorialState (seen/enabled)
  hints.py          the one-time rule cards a trigger fires (a studyable item, the road, a second fight, a fallen member, a dungeon walked out of) and the wiki entry each opens

  wiki_rules.py / wiki_races.py / wiki_terms.py (the compendium's RULES / RACES / the traits and actions it links)
  keywords.py       the reserved words of the rules (Brutal, Shove, Dying...): one text each, the KEYWORDS chapter of the wiki; a description says only the word

  # the Editor lives apart, in editor/ (a sibling package): the one pygame program of the repo.
  # gartok/ never imports it or pygame (a test checks it); the Editor reads gartok, and gartok/assets
  editor/           `python -m editor`: editor_app / editor_menu_screen / char_editor_screen /
                    map_editor_screen / combat_lab_screen, battle_screen + battle_draw + battle_fx (the lab's
                    fights), screen (base class), text_field, artwork + icons (pygame art), sound (mixer),
                    ui/ (the war-table component kit; rules + catalog in editor/ui/README.md),
                    tests/ (`python -m pytest editor/ -n auto`), item_icon_preview.py, requirements.txt (pygame-ce)

  # presentation of the game
  web/              the web client (guide: docs/web_ui/web_client.md): server.py (stdlib JSON API routed by
                    screen), session.py (a screen's server half) and one session (or tab) module per
                    screen or hub tab, client/ (the shell + one folder per screen under screens/;
                    dice.js + dice.css, the one die every screen rolls);
                    `python main.py` / `python -m gartok` (the title); `--shell` is how the native client starts it,
                    `python -m gartok.web --fight <lab fight>` or `--save <world>`
  art_files.py      where the art is: portrait_path, BANNER_ICONS, `RACE_ICON` and
                    name each race's glyph (`map_view.NODE_ICON` the nodes')
  sheet.py          a character's sheet as a plain dict (unit_to_ch)
  lighting.py       light per cell (`cell_levels`): one flat level per cell in sight; the web board draws it
  sound.py          sound cues (assets/sounds/, CC0) and music (assets/music/, CC0) the web plays, `volume` and `music` settings; the Editor has its own player
  loadout_move.py   the moves between a member's hands, armour and pack (the band's kit, the vaults)
  guild_sheet.py    the guild's sheet: the roster, a member's sheet and roles, the charter
  band_kit.py       one band's kit: the moves, the tack and the hitch, the item menu, first aid
  store_column.py   a wagon or an animal as one more pack (the web's shop and vault)

main.py             entry point (gartok/__main__.py: the browser)
shell/              the native client: main.js (Electron: starts the server with --shell, shows its page, stops it on exit), run.js (npm start's launcher), package.json
tests/              the rule tests, one file per domain (run: python -m pytest tests/)
sim_test.py         headless simulation (200 AI-vs-AI battles)
scripts/            the sims and tools; each opens with a docstring saying what it reads and prints:
                    balance_sim.py (race / starting weapon rankings), economy_report.py (every economy sim in
                    one report, with verdicts; the other economy_*.py are its parts), economy_offers.py
                    (what a guild can take up today), play_analysis.py (play.jsonl), combat_analysis.py and
                    combat_pairs.py (read the combat logs; the AI replays a person's squads),
                    make_cult_npcs.py (writes the Demon Cult's eight NPCs to npcs/),
                    build_client.py (the server with PyInstaller, the window with Electron, the zip; run by build_exe.bat),
                    release.py (publishes the last built version as a GitHub release; run by release.bat),
                    gen_portrait.py (portraits from the local model, the /gen-portrait skill; portrait_lora/ has the setup),
                    portrait_press.py (levels every portrait to the same paper and ink; run after installing one)
docs/               economy_sim.md (what the economy sim measures), web_ui/ (web_client.md: how to build a web screen; references/: the approved mockups; proposals/: looks not approved yet), plans/ (backlog.md is all the open work; loyalty.md and campaign_ai_roadmap.md are the plans it points to)
```

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
  `persist.unit_to_dict` / `Unit.from_save`. `Combatant` reads it for free. An optional
  field's neutral value goes in `unit.SAVE_DEFAULTS` and needs no `SAVE_VERSION` bump.
- **New ground-object type**: a new `kind` on `ground.GroundObject` and the rule
  that reacts to it (consumers ask `obj.kind` / `obj.is_weapon`).
- **New battle scenario** (prebuilt map, deployment zones, lighting): a `Scenario`
  subclass with `build(battle)` in `scenario.py`; point a `world.Node` at it. A
  non-elimination objective goes through `Scenario.win_check` (capture-the-flag
  `_FlagObjective` and `AncientRuinsScenario` already override it); a place the squad
  must walk out of keeps the field open with `holds_field`, and what a fight changes in
  the world for good goes in `after_battle` (both on `AncientRuinsScenario`).
- **New place on the map**: a `Node` in `world.NODES` listing its `functions` + edges in
  `world.EDGES` (cost in hours). Offering something already built is only the id in the list.
  A new kind of service is one `NodeFunction` in `node_functions.FUNCTIONS` (order kind, button
  label) plus its tab in `web/hub_session.py`.
- **New threat** (a fight the world forces on a group): a catch function (on arrival or daily)
  and a resolve function in `forced.py`, plus one `ForcedEvent` in `forced.EVENTS` with its
  `nature` (`fight_nature`). Any new fight passes its nature to `web/campaign_fight._enter`, and
  takes a row in `RULES.md`, *Where fights come from*.
- **New world system** (outside combat): the routine that passes time in
  `guild.pass_time` / `_daily_upkeep`; the battle result that returns to the
  roster in `campaign.absorb_battle`.
- **New activity that spends hours** (a show, a repair, a piece of building): never a clock jump of
  its own. It is an order: a `Stint` in `stints.STINTS` (its chip and how it settles) issued by the
  place's desk, and the tab runs it with `HubSession._spent` (`MapSession.spend`), so every band's
  order advances with it and the map takes over when another band needs the person.
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
  screen's session (`web/session.py`). What the copy cannot hold (a list drawn from a registry, later a
  picture) is `tutorial_rows(key)` on the session: each row is a stamp, a rule and a text, optionally an `image` (`big`: a 120 px picture, for a diagram) and a `focus` (a selector lit on the screen
  while the pointer is on the row). `tutorial_spot(key)` names the part of the screen the card is about (the battle's action bar), kept
  lit above the veil while the card is up.
- **New rule pop-up** (a one-time card a trigger fires, with a *See in the wiki* button): an id in `hints.IDS` and
  `tutorial.TUTORIALS`, its `tutorial.hint.<name>` copy in `locales/en.json`, the trigger in `hints.on_map` or
  `hints.in_battle` (the map's and the battle's `tutorial_key()` ask there once their own card is read), and the entry
  that holds the rule in `hints.wiki_ref` (a `wiki_rules` section when the rule has none yet). Its `seen` flag is
  `TutorialState.seen`, already saved.
- **New translated string anywhere else**: a key under its own namespace in
  `locales/en.json`, read with `i18n.t(key, **params)` (a sentence is one key with `{placeholders}`, never
  fragments joined; a count is `i18n.plural(key, n)` with `key.one` / `key.other`; the shown name of an item,
  talent... is `i18n.name(kind, id)` from `name.<kind>.<id>`, with `.gender` when an article depends on it; a sentence
  that names a thing takes an `i18n.Ref` and writes `{item}` in `en`, `{item:o}` / `{item:do}` / `{item:no}` / `{item:um}` in `pt-br`
  (the article of its gender), and a line whose adjective agrees has a `key.f` twin the first feminine `Ref` picks; a size variant,
  a scroll, a recipe paper and a dictionary are not written one by one: `items._composed_names` builds them from `name.compose.*` + the plain
  weapon, `name.spell.<id>`, `name.item.<recipe>` and `name.language.<id>`, so a new spell, weapon or recipe paper needs only its own entry).
  A short label the server writes in English as a word ("Purse", "CHA", an archetype) goes through `i18n.lab(text)` (`ui.lab.<lowercase>`,
  cased as the input is; the client has the same `lab()`), never a literal shown raw. `python scripts/i18n_leaks.py` opens the map, guild
  screen and hub tabs in `pt-br` and lists the strings that still read as English.
  The `pt-br` text goes in `locales/pt-br.json` under the same key and the same placeholders (a test checks).
- **A catalog thing's name and description** (a talent, racial ability, weapon trait, faction, spell, poison,
  vocation, archetype): its registry entry carries no text, only the `id`; `name` / `desc` (`effect`, `perk`) are
  properties reading `name.<kind>.<id>` and `desc.<kind>.<id>` (`i18n.name`, `i18n.desc(kind, id, **params)`) on every
  access, so a language change needs no reload of the registry. A new entry adds both keys to `locales/en.json`
  (a test fails on a gap). A thing whose id *is* its English name (an item, a race, an alignment, a size) keeps that
  name as its id and is shown with `i18n.name(kind, name)` (the `Unit.race_label` property for a race; the client's
  `nm(kind, id)` for an item name it draws): never compare, store or post back the shown string. A node keeps its
  English name as the default and `name.node.<id>` overrides it. `tests/test_i18n_catalog.py` plays the first days
  with every shown name altered, and fails when a rule reads a shown name as an id.
  The language is the `language` setting, applied at boot and on the settings screen. Converted so far:
  `tutorial.*`, `arena_talk.*`, `credits.*`, the web client's `ui.*`, the combat actions (`action.*`, `log.*`,
  `fx.*`), every notice, error and label of the rule modules and web sessions/tabs (one key group per module) and the
  catalog text (`name.*`, `desc.*`, `item.*`) and authored content (missions, deeds, objectives, vendors' lines, node blurbs,
  NPC backstories, dialogue, forced events); `python scripts/i18n_audit.py` counts the literal sentences left (terms: `docs/glossary_pt_br.md`).
- **A battle log line**: `battle.log("log.key", actor=unit.name, ...)`, one full sentence per key. The combat log
  keeps key and params, so a fight reads in any language. A catalog thing inside a line is an `i18n.Ref(kind, id,
  default)` (`actions.base.item_ref(name)` for an item), a sentence inside a line an `i18n.Msg`; both resolve when the
  line is rendered. An action's `name` and `desc` are its `action.<id>.name` / `.desc` (`i18n.Text`, no class literal);
  its `label()` and blocked reasons are `action.<id>.label` / `.reason`.
  A line the screen should light gets a kind on the `LogLine` (`battle.log_lines[-1].mark = "read"`, as `intel.observe` does); the battle state sends it in `log_marks` and the client puts it on the line as a CSS class.
- **Text in the web client**: a key under `ui.` in `locales/en.json`; a script reads it with `tr("group.key",
  {name: value})`, a count with `trn("unit.day", n)` (`unit.day.one` / `.other`), a page's fixed label is
  `data-t="group.key"` (`data-t-tip` for a tooltip). The shell fetches `/api/locale` before it draws a screen,
  and a language change reloads the page. `tests/test_web_locale.py` fails on a key the client reads and the
  catalog lacks.
