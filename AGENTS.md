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
- Work and commit straight on `main`; no feature branches unless the user asks for one.
  A teammate works on `main` in parallel, so `git pull` before committing.

## Design premises (durable)

- **Every unit is its own individual.** The group is a container, the unit is
  the atom. A shared activity resolves per-person.
- **World-first.** Rules exist as world things first; if they talk to combat,
  better. Systems land bit by bit.
- **Disposable early squad.** Early mortality is very high; starters are meant
  to be lost.
- **No guild treasury.** Money lives on the character -- as `Copper Coin` ($1) and `Gold Coin` ($100) items in the pack (they weigh, split and move like any item). `Unit.money` is their sum in `$`; paying spends copper first, then breaks gold and returns change. Gold only exists through the bank exchange (`economy.buy_gold` / `sell_gold`, $1 fee per coin each way); loot, wages and rewards are copper.
- **Vision is per-character.** The map is always dark; on your turn you see
  what the active unit sees.
- **Adventure out-earns day labour.** In Gartok the risk pays: lumber is only a
  survival floor (16 h = cheapest meal + $1), the arena and the wilds pay
  more. Re-run `scripts/economy_report.py` (verdicts, exploits, what each activity pays,
  a guild living 30 days, the ranking; its parts are `economy_activities.py`,
  `economy_talents.py` (each work talent priced on its own), `economy_guild.py` and `economy_exploits.py`) after touching wages, purses, prices or loot.
  `scripts/economy_offers.py` lists what a guild can take up today (bouts, missions, kit, tools),
  each priced in copper and days, from the same tables.

## Architecture — one concern per module

| Module | Role |
|---|---|
| `unit.py` / `poisons.py` | persistent character: init, save/load, generation; the rest is mixins — `unit_hunger.py` (meals), `unit_levels.py` (XP tracks, talents), `unit_edit.py` (draft/sandbox setters), `unit_derive.py` (HP/AC/speed + breakdowns), `unit_loadout.py` (hands, armor, artifact slot, pack, stack helpers; `CoinPurse` is the base for `Unit.money` and `Creature`: coins in the pack, 200 coins = 1 kg), `unit_poison.py` (persistent poisons from `poisons.py`: Snake Venom, Spider Venom, Antidote) |
| `artwork.py` | loads, tints and caches the SVG glyphs (`assets/icons/<category>/<name>.svg`) and the portraits; `RACE_ICON`, `OCCUPATION_ICON` and `map_screen.NODE_ICON` name each race's, occupation's and node's glyph (a test fails for one with none); `icons/map/` holds the hand-drawn ones game-icons.net lacks |
| `icons.py` | tiny vector line-art glyphs drawn with `pygame.draw` (no asset files); renders action buttons, status marks, and the 11 weapon action icons |
| `combatant.py` | a Unit *inside one battle* (HP, AP, status, conditions) |
| `battle.py` | board + units + turn flow; wraps each Unit in a Combatant; any number of sides (`others={team: units}`: hostile to all, played by `ai.py`; `foe_units` is everyone off the player's side) and `withdraw` once the scenario allows it |
| `battle_screen.py` / `battle_draw.py` | the fight's screen: input and turn flow / everything it paints (`BattleDrawMixin`) |
| `map_screen.py` / `map_inspector.py` | the map: groups, orders, travel / what the inspector shows at the selected band's node (`MapInspectorMixin`) |
| `market_screen.py` / `market_trade.py` / `market_draw.py`, `group_screen.py` / `group_draw.py`, `taverna_screen.py` / `taverna_draw.py`, `store_column.py` | each screen's state and input / its trades (`MarketTradeMixin`) / everything it paints (`*DrawMixin`); `store_column.py` is the shared wagon/animal store column |
| `actions/` | every combat action is an `Action` subclass; `base` / `combat` / `movement` / `support` / `spells` / `weapon_actions`, registry in `__init__.py` |
| `abilities.py` | `Ability` frozen-dataclass registry (passives + hooks) |
| `talents.py` | talent-tree registry mirroring abilities.py |
| `conditions.py` | `Condition` subclasses (Defending, Demoralized, Invisible, ...) |
| `board.py` | grid geometry, walls, LOS, pathfinding (pure, no battle state) |
| `vision.py` / `fog.py` | free fns over battle: light, can_see, visible_cells / the side's memory of the cells it has seen (`FogMemory`, held by the battle screen, never saved): never seen is black, seen before is dimmed; `lighting.py` lights per cell (`cell_levels`: one flat level per cell in sight, from the torches that reach it along the line of sight), so the drawing never shows what the rules hide |
| `intel.py` / `foe_card.py` | what a side knows of a foe: the opening INT read, its bands, Assess, the guild's `Bestiary`, `known_fields` (the one read the foe card, the log and `ai.py` share); `foe_card` adapts it for `ui/foe_panel.py` |
| `ground.py` | GroundObject (weapon, torch) + Creature (neutral body) |
| `scenario.py` | deployment, board setup; the seam for objectives / maps |
| `ai.py` | heuristic over actions/; alignment tempers behaviour; a 2-point weapon action is taken only when its expected damage beats two plain attacks (`_strike_worth`); reads only `intel.known_fields`; with nobody in sight the side that brought the fight (`Battle.aggressor`) searches and the other groups up |
| `world.py` | Node graph, edges as distance (walking hours), route Dijkstra, `hours(distance, speed)`, algorithmic layout via Kamada-Kawai (`compute_layout`, `apply_layout`: a small map fills the unit box, a big one grows past it and is never squeezed, `_spread` keeps nodes apart); a `Node` offers `functions` (no per-service flags), can be secret (`Node.hidden`, visible only once revealed in `world.known(guild)`) or ethereal (`add_node` / `remove_node`: an event's node, on the map for a while, `VERSION` moves on every change) and may carry a `Vendor` (name, race, role, portrait) per function: `world.vendor(node_id, function)` is the keeper whose face the shop screens show |
| `node_functions.py` | what a node can offer, one `NodeFunction` per id: order kind, map button label, note; `app._FUNCTION_OPENERS` holds each id's screen opener and a test keeps them in step |
| `shop.py` | `Shop` = one node's till and finite shelf (`Guild.shop(node_id)`); every item on it has a target and a daily rate (`economy.SHELVES`, one shelf per node); refilled daily for every node that offers `shop`. The Smithy, Tannery, Apothecary, Farm, Tavern, Market and Carpenter each sell their own part of the town's goods (`economy.TOWN_SHOPS`, `economy.shop_of(item)`) |
| `hub_screen.py` | `TabbedHubScreen` (a node's screens behind one row of tabs, in the frame it owns, `ui/hub_frame.py`: the keeper's header with the active tab's `hub_cards()`, the tab row, the back button; a tab marked `framed` draws only its body on a subsurface, one not yet redrawn keeps its own header and footer under the tab row; `for_node` builds them dynamically for every node with a shop, a lone shop included) and `ShopHubScreen` (the node's shop as the first tab): `forge_hub_screen.py`, `tanner_hub_screen.py`, `apothecary_hub_screen.py` |
| `work_screen.py` / `gather_screen.py` | a work node's (Lumber Yard, Mine) tabs: WORK, the paid shifts with each worker's tool and wage / GATHERING, buy the licence and pick gathering shifts; on the map the node is one ENTER button and a line (`map_inspector._work_line`) |
| `orders.py` | Order dataclass; AUTO (travel / work / rest) / INTERACTIVE / garrison / forced kinds |
| `rest.py` | what a rest order costs and how long "until full" lasts (simulation on copies, keeps a day of rations) |
| `campaign.py` | tick engine (`advance`), battle absorption |
| `forced.py` | forced events (guard, ambushes, raids, seizures): one `ForcedEvent` per order kind in `EVENTS` says where it is caught (on arrival or daily), how the app plays it (`play`: battle / map / talk, `app_forced.FORCED_PLAYERS`) and how it is settled (`resolve`, or `settle_talk` when a dialogue ended it); a new threat is its catch + resolve + one entry |
| `sources.py` | where each base material comes from: a material, food or gem no recipe makes (derived), with its source read off `gather.TABLES` / `data.BEASTS` or declared (`DECLARED`); a test fails for one with none; REFERENCE.md lists them |
| `gather.py` | gathering at the Lumber Yard and the Mine: the drop tables, the licence prices, `roll_haul`, the ambush odds and pack; `Guild.buy_licence` / `gather_shift` / `bank_haul` (in `guild_labor.py`), a `work` order with `gather=True`, and the forced `gather_ambush` fight that `forced.resolve_gather_ambush` settles |
| `guild.py` | Guild state: groups, roster, leadership, fame slots, revealed nodes (`revealed`, `reveal_node`), supply runs tally (`supply_runs_completed`); owns `bank` + `house`. Behaviour lives in mixins — `guild_upkeep.py` (clock, meals, daily sweep), `guild_holdings.py` (bank, property, debt, garrison), `guild_claim.py` (Wilds claim), `guild_labor.py` (work/crafting shifts) |
| `holdings.py` | what the guild owns: `Stash` (weight-capped storage; defined in `stash.py`, re-exported), `CityProperty` (house, tax, squat, oven), `Garage` (wagons and animals kept at the house, or at the Claim with no limit; `garage_screen.py`) |
| `creature.py` / `animals.py` | what a Group keeps besides people: `Creature` is the shared pack owner (HP, load, locked items; it answers the pack calls, `toggle_lock` and `money` like a `Unit`, so shops, the tavern and the Claim read its goods too); `Animal` is a livestock race from `data.BEASTS` (Donkey, Ox, Horse) with fixed attributes, loads from Strength; kept in `Group.herd` |
| `wagon.py` | a Group's wagons (`Group.wagons`; `Vehicle` types Cart / Carriage; `wagon_watch.py` / `watch_screen.py`: the wagon left outside the Ruins or a hunt) + the draft animals hitched to each (`Animal.hitch`, `Group.hitch`): cargo and passengers (by weight) share what those animals draw, eaten from by the group, lost with it (bought at the Carpenter, `stables_screen.WagonYardScreen`; the animals at the Farm, `StablesScreen`). Vehicles are Hit Dice of d8 with no CON; the road wears 1 HP per 100 distance and 0 HP is *broken* (repair: Lumber per HD + 1 h + INT check, `Guild.repair_wagon`; leaving it: `abandon_screen.py`) |
| `group.py` | Group = physical subset of the guild (members, node, order, `pending`); `BASE_SLOTS` / fame → how many groups the guild may run. `pending` is a forced order (ambush, guard, raid) that came due and awaits its fight: `order` is already None (so `advance` ignores the group) but `locked` is true — no split, merge, leader swap or kit change until it resolves. Field campfire (`has_campfire`, `light_campfire`: burns 4 h with Flint and Steel consuming 1 Lumber + 1 Coal for field cooking station; saved via `campfire_node` / `campfire_expires`) |
| `vocations.py` / `vocation_screen.py` | the guild's founding trade, picked once at the draft (`Guild.vocation`): six races (the draft pool holds one of each) and one perk the whole guild has; the perk is read through small functions (`gather_pay`, `travel_mult`, `ambush_mult`, `cohesion_bonus`, `food_pauses`). `Group.stance` (Normal / Cautious) is the travel stance the Wilds perk and Woodland Scout read |
| `cohesion.py` | daily sweep: an overextended group's weakest member may walk (7-day notice, alignment decides the loot) |
| `economy.py` | prices, stock, haggling, garrison/property constants |
| `persist.py` | worlds (one folder per guild): `current.json` + auto snapshots before each fight (last 10) + named manual saves; SAVE_VERSION, no migration: a save of an older shape does not load. A new *optional* field needs no bump: add its neutral value to `unit.SAVE_DEFAULTS` / `persist.PAYLOAD_DEFAULTS`; a key with no default is still required. Saves each group's `order` and `pending` fight (enemy pack included); never a battle or hunt in progress (`App._can_save`) |
| `combat_log.py` / `combat_lab.py` / `combat_lab_screen.py` | one JSONL per fight that rebuilds it from the file alone (`battle.sink`; every `Action.execute`, end of turn and flag/trap goes through `CombatLog.record`, human or AI, with the legal options and what `ai.py` would have done); `BattleScreen` takes a controller per team (human or AI, two humans get a hand-over card); the lab (Editor menu) sets up the benchmark fights and logs to `combat_lab/<date>/<name>.jsonl`, campaign fights to `saves/<world>/combat_logs/` while `record_play` is ON (`saves/` is not in git: `scripts/archive_combat_logs.py` copies them to `combat_lab/campaign/<guild>-<world id>/`, run it after a session); `scripts/combat_analysis.py` reads them; `combat_log.rebuild` puts a logged fight back at its opening (campaign or lab, capture the flag with both flags planted, not the Ruins) and `scripts/combat_pairs.py` has the AI replay the squads a person played (the win rate and the dead to move when `ai.py` changes; `--set NAME=VALUE` weighs an `ai.py` threshold head to head, on the player's side only) |
| `recorder.py` | opt-in play log (`record_play` setting): one JSONL row per day, order, market buy/sell, fight, talent, asset and recruit pitch, in `saves/<world>/play.jsonl`; a no-op while detached. `scripts/play_analysis.py` reads it into the sim's day table and the author's thresholds (what `economy_guild.Balanced` was calibrated on) |
| `battle_fx.py` / `sound.py` | the fight's juice, presentation only: floating numbers, the hit flash, the crit banner and their sounds, read off HP deltas and `battle.fx` / `battle.cue` (crit, miss); what the side cannot see is heard, never shown / one cue name -> a few Kenney variants in `assets/sounds/` (CC0), silent until `App` calls `enable()`; the app also clicks on a button press (hand cursor up) and chinks coins when the guild's money moves |
| `settings.py` / `settings_screen.py` | player preferences in `settings.json` beside the saves (not per guild); one `SPEC` line per option, pause menu and settings screen list them |
| `start_screen.py` / `wiki_screen.py` / `menu_screen.py` / `saves_screen.py` | classic main menu (Continue, New, Load, Editor, Settings, Wiki) and in-game compendium (its RULES tab is `wiki_rules.py`: the rules a player looks up, read off the live constants) -> guild browser -> save snapshots with date and time |
| `factions.py` | factions + one-shot deeds → reputation; a faction is `hidden` until the guild enters one of its `nodes` (`Guild.meet_factions_at`, `factions.known`) |
| `items.py` | single source of truth for all items (ItemDef, ItemInstance, catalog, recipes) |
| `item_icon.py` | what each item looks like: `ICONS` names every catalogue item (kind, material, shape) for `ui/item_icons.py`'s code-drawn silhouettes, rarity is the rim; a test fails for an item with no entry |
| `weapon_traits.py` | `WeaponTrait` frozen-dataclass keyword registry (Finesse, Thrown, crit/action seams) mirroring `abilities.py`; single API is `ItemDef.has_trait()` across combat, UI, and generator |
| `medic.py` | the Medic's quick treatment (Apothecary hub, MEDIC tab): HP / sickness / poison priced as the expected potions and doses at `economy.MEDIC_PRICE_FACTOR`, one clock for the group; past `MEDIC_MAX_HOURS` it is a hospital stay (`admit`: the patient splits off on a `solo` order); the sim prices it from the same constants |
| `solo.py` | a *solo task* (`orders.solo`: kind `solo`, `task` hospital / craft): one member splits off into a group of their own (`Guild.send_alone`, costs a group slot) or the whole group waits; `campaign.advance` calls `solo.finish` when the hours run out and the player merges them back by hand. `solo.craft` rolls the craft at the end, from the crafter's own pack when alone or the group's when it waits; the Forge screen's "Alone" row issues it |
| `rite.py` / `initiation_screen.py` | initiation into a magic school at its hidden sanctuary (INITIATION tab beside JOBS; the keepers are each sanctuary's `shrine` `Vendor`): 2 faction reputation as a threshold, the character boards on a `garrison("rite")` order (alone, or the whole group waits with no free slot), `1d20 + INT` a day toward the school's points (kept per school in `Unit.rite_progress`); Faith consumes a Holy Symbol, Blood first tests `Unit.magic_blood` (rolled at creation, `magic.roll_magic_blood`) for 7 days; board $3 a day only when the pack has no food (`rite.board`); grants the school, no spell |
| `craft_level.py` | a recipe's level, worked out from its difficulty (who may start it, scarce reagents, batch time), never set by hand; it blocks nobody, it is the label and the work-XP multiplier |
| `app.py` | pygame shell: scene loop, screen wiring (its methods are split into mixins: `app_nodes.py` the screens a node opens, `app_forced.py` guard / ambush / raid / Claim fights, `app_hunt.py` the hunt, `app_battle.py` entering and settling a battle); a tick's pending order → its screen via `_ACTIVITY_OPENERS` (built from `_FUNCTION_OPENERS` + arena + `forced.EVENTS`), a forced fight's aftermath via `forced.resolve`; with 2+ groups, a pending screen of a group other than the one in view (`App._focus_gid`), or a map landing on another band, waits behind `group_turn_screen.GroupTurnScreen` (the label: the node button's, `ForcedEvent.label`) |
| `recruit.py` | recruitment contest (CHA vs CHA, shared language gate) |
| `archetypes.py` | recruit archetype catalog + candidate generation |
| `missions.py` / `ledger_screen.py` / `shrine_screen.py` | paid, deadlined jobs from a named giver (has a reward, can fail); a board lists every job its giver has (`MissionOfferScreen.get_templates`, `missions.board`); `shrine_screen` is the JOBS tab of the three hidden sanctuaries (the Codex deliveries, revealed by the Library turn-in); ledger_screen is Ledger Hold's Bankers' chest exchange, Commander Varkas Treefolk mentorship, and frontier supply runs (`orders.supply_run`: a walk to the Frontier Outpost and back, `Guild.supply_leg` rolls each leg's ambush and stops the order part-way in `Order.owed`; 10 deliveries for the military deed) |
| `serpent_nest.py` | the Snake Dragon job: the Lumber Yard search for the hidden Serpent's Nest and its five-chamber dark dungeon (`NestScenario`: sleeping snake packs, the lair pool, win when the Snake Dragon is dead or bound); the Blood Cult wants the body, the Nature Coven the captive (`missions.SNAKE_HUNTS`, exclusive) |
| `lair.py` | the Blood Cult's third errand (`missions.BLOOD_CLUTCH`): the Mine search for the hidden Dragon's Lair and its heist (`LairScenario`): kobold patrols on their rounds that challenge the squad on the board (`contact`, `dialogue.Challenge`, `Battle.talk_handler`, `ai._patrol`), the dragon (`npcs/dragon.json`, racial 20) asleep in stages that noise fills (`hear`, scenario hooks `on_turn_start` / `on_turn_end` / `on_pick_up`), the hoard, the eggs, leaving with one (`can_withdraw`, `ai._heist`); keepers buy eggs (`shrine_screen`) |
| `wildfire.py` / `fortress_scenario.py` | the Nature Coven's third errand (`missions.NATURE_WILDFIRE`, 14 days): the Ogre's goblins set the Wilds on fire; the foci and the Great Focus are ethereal nodes (`Guild.wildfire`, `sync_world` after a load), a focus left 7 days burns and starts two more; talk (CHA then INT, `talk`), fight (`camp_crew` / `ogre_band`) or put the fire out (`orders.put_out`, 16 h); `FortressScenario` is the half-raised fortress with a spreading bonfire (`Battle.fire`), won when the Ogre (`npcs/ogre.json`) falls; what it leaves: `meat_mult`, the hostile fortress's goblins on a hunt, or the friendly fortress's shop (the only shelf of Large weapons, `economy.SHELVES["ogre_fortress"]`) |
| `battlefield.py` | the Faith Order's errand (`missions.FAITH_BATTLEFIELD`): the Battlefield past the Frontier Outpost, two trenches and open ground (`BattlefieldScenario`); four Ledger Hold soldiers fight on the player's side, played by `ai.py` (`Battle(allies=...)`, `Combatant.ai_ally`), against a warband; the errand fails if one soldier dies |
| `necromancer.py` | the Faith Order's second errand (`missions.FAITH_NECROMANCER`): a 48x30 Battlefield at night with three sides (squad + soldiers, a warband, the necromancer's `undead`) and the `fallen` dead of days before; the necromancer (`npcs/necromancer.json`) starts invisible and raises the dead (`actions.RaiseDeadAction`, `InvisibilityAction`, `ai._necromancy`); his fall drops the undead and meets the errand, then the squad may withdraw |
| `captives.py` | a foe bound in battle (`actions.Capture`) kept by a group (`Group.captives`): not a member, counts 1 on the herd limit, walks in the pace, dies 7 days after capture (`daily`), a body worth keeping (`CORPSES`) left with the leader |
| `ox.py` / `ox_fields.py` | the tanner's last job: the Country Roads search, the daylight tracking of Aurochs (`ox.track`, DC climbs per found trail) and the big skittish-beast field (`OxFieldsScenario`: terrain, the herd's call, win on his fall); `ai._skitter` is his flight |
| `justice.py` | crime per character, City jurisdiction, patrols, prison |
| `dialogue.py` / `dialogue_screen.py` | the talk before a fight: an `Encounter` (`Ambush`, `Patrol`, `Challenge`, `WildfireTalk`, `BossTalk`) offers verbs (`VERBS`), `choose` rolls one into a `Result` (peace / fight with an `Opening` for `Battle.open_with` / leave / surrender); `forced.encounter` builds it for the guard and the ambushes, `Order.parley` keeps a rolled one; `ai_choice` is the squad's side |
| `arena.py` / `ribbit_prompt_screen.py` | Champion of the Pit title and its defense cycle; ribbit_prompt_screen handles brothers' post-battle recruit offer; before the guild's first bout against Adelio or the Ribbit Brothers each boss says one line, a `dialogue.BossTalk` with no verbs on the dialogue screen (`arena.boss_talk`, `Guild.boss_talks_seen`, copy in `locales/en.json` under `arena_talk`) |
| `magic.py` | spell registry + study-difficulty math (casting is in actions/spells.py) |
| `encounters.py` | enemy packs scaled to a target mean level (`clamp_level` holds a scaled fight under the enemy caps); `level_weights` makes a table's headcount / level weights from a bell leaning low |
| `outfit.py` | a generated humanoid's kit by racial level: `KIT_BUDGET` (measured by `scripts/wealth_by_level.py`) buys the armour its Dex cap still pays for, a weapon by archetype (Strength one hand + light or two hands, finesse + light, bow + quiver; never the occupation's), then potions, never past the overload; `build_enemy` calls it, and `Battle` calls `light_the_band` so every outfitted band brings a light |
| `progression.py` | XP curves + combat-XP rule |
| `aftermath.py` | what the screens after a fight read, filled by `campaign.absorb_battle`: the report rows and takedowns, each `LevelUp` (numbers before / after), each `Memorial` (in battle or starved, `Unit.joined_day` counts the days); `result_word` is the VICTORY / FLED / DEFEAT both the board and the report show. `app_battle` plays memorials -> report -> level-ups -> loot / purse / map, the state already settled |
| `autowin.py` | auto-resolve a battle via Monte Carlo estimate |
| `tutorial.py` / `tutorial_card.py` | tutorial state + the modal card per screen (`ui/intro_card.py`); copy in `locales/en.json` |
| `objectives.py` | the guild's objectives: 17 small tasks on the Guild Screen's REPUTATIONS tab above the faction deeds, all open from day one, each one teaching a system (food, work, arena, Medic, recruits, licence, jobs, groups, pack animal, wagon, deeds, magic); read off the guild's state, or marked by the screen where it happens; orientation, no coins/fame. The map's first tutorial card closes onto them |
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
- The old `theme.py` ramp is gone; the board's palette and camera are
  `ui/board_style.py`, the banner colour is `ui/banner.py`. Screens take
  the `tokens.fonts()` dict as their constructor argument.
- A `ui/` component never reads module globals or hardcodes screen
  coordinates/fixed pixel widths for panel sizing — it takes its rect/data as
  parameters and sizes/lays out relative to those (proportional-with-clamp
  for anything window-size-dependent, like `map_panel.draw_minimap` already
  does), so the same component holds up at any window size.

A screen with pack rows takes the ⋮ item menu (split stack + quantity prompt)
from `packbox.ItemMenuMixin` — Gear, Group, Market and Stash already do; a new
one reuses it instead of growing its own popup.

A new screen gets a tutorial card too: a `tutorial_key()` on the screen and a
`tutorial.<id>` block in `locales/en.json` that teaches how to use it (see the
recipe in `README.md`).

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
