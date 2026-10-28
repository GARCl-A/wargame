# Web front-end: keep the Python core, replace the pygame presentation

**Status:** the battle spike is built and the author's verdict (2026-10-23) is go: better
than pygame already, but with a lot left to fix in colour, fluidity and light. Steps 1
to 3 and 5 to 9 are done; step 4 (the art) is done as far as it got. Step 10 is under way:
every campaign fight (forced, the Claim's, the arena, the hunt, the searches' finds, the errands') is played
in the browser from the map to the report; the title screen and the draft are next, then the swap.

## Decisions so far

| Date | Decision | Why |
|---|---|---|
| 2026-10-23 | The art is not drawn in code. Code composes images (textures, frames, portraits) and draws only state (health, ranges, highlights). | `pygame.draw` art always reads as programmer art. That, more than any single screen, is why the game looked ugly. |
| 2026-10-23 | Gemini makes the art, not the local SD + LoRA. | The author's best images came from Gemini. |
| 2026-10-23 | The style anchor is the four engraved portraits in [references/](references/): Gnoll 10, Grippli 13, Kenku 4, Ogre 0. | Sepia engraving on parchment is nearly one colour, so AI output stays consistent with it. It also tells the game's story: this is the lost RPG's own material. |
| 2026-10-23 | No tile sheets. The floor is one seamless texture that crosses the cell lines, and code tints it. | The first 4x4 tile sheet was rejected: each tile was a picture of its own, and side by side they did not fit together. |
| 2026-10-23 | The floor sits in a lower value band than the tokens. | Cream tokens vanished on a cream floor. |
| 2026-10-23 | Keep 2D engraving. Isometric, 3D and pixel art are out. | Isometric means many angles per unit, which is where AI is least consistent. 3D is months of art for one person. AI is bad at true pixel art, and the 400 portraits would be lost. |
| 2026-10-23 | Keep the Python core and replace pygame with an HTML/CSS/Canvas client. Option 2 of 3. | The rules, sim, AI and tests are the game's value. Presentation is pygame's weakest side: the mockup took an afternoon in HTML. The `ui/` contract (plain dicts in) is already the API. |
| 2026-10-23 | The transport is a stdlib HTTP server and the window is Edge or Chrome in `--app` mode; shipping is pywebview or Tauri, decided at the end. | No new dependency for the spike. pywebview's `pythonnet` is unverified on Python 3.14. |
| 2026-10-23 | The server filters fog, sight and intel; the client never gets what the side does not know. | The client is untrusted. It is also the same rule `ai.py` lives by (`intel.known_fields`). |
| 2026-10-23 | Fonts (Cinzel, EB Garamond, IM Fell English) ship in `gartok/web/client/fonts/`. | They must not be fetched at runtime. |
| 2026-10-23 | The style holds off the board: the title screen and a shop were mocked in it, and the author approved both. | The battle alone did not prove the direction for the rest of the game; the menu and the market are its two most different screens. |
| 2026-10-23 | A shop shows every shopper's whole kit as a readable list, one column per pack: worn slots and pack rows, each with icon, name, quantity and weight. The keeper is a strip across the top, not a column. | The first market mockup shrank the packs to rows of icon tiles beside a tall keeper page, and the author lost sight of the inventory, which is what the screen is for. |
| 2026-10-28 | The talent tree is a graph laid out from `requires` alone, in two views behind one toggle: THE MAP (radial round the character, with a camera) and THE BRANCH (an outline and the talent's neighbourhood). | The trees will reach about 100 talents each, wider and deeper, and may not keep six attribute families; a fixed page holds 30 to 35. A 100-node load test fitted top-down and left-to-right at 15% and radial at 29%; the outline holds any size. |
| 2026-10-24 | The map mockup is approved, with four changes from pygame's map: the minimap goes (the known world fits; zoom, pan and FIT stay); hovering a place shows a paper slip with the walk's hours and arrival and the way there in red ink; Split and Merge open inside the picked band's card instead of behind a gear; the REST choices and the travel stance are always shown, as segmented rows. | The whole known world fits one sheet at 1920x1080, so the minimap only duplicated it; pygame never said how long a walk takes before it was ordered; the gear and the REST drop-down hid what a band can do. |

## Art direction

- **The table.** The game looks like the RPG's physical material (an engraved bestiary,
  a map inked by hand, character sheets) laid on a dark wooden table. The target is
  [references/battle_mockup/](references/battle_mockup/) (`battle.html`,
  `battle_mockup.png`). The same language off the board:
  [menu_mockup/](references/menu_mockup/) (the title screen: the menu beside the last
  guild's charter, laid on the map it has walked) and
  [market_mockup/](references/market_mockup/) (a shop: the keeper and the deal, the
  shelf as a ledger page, the shoppers' packs, a ware in hand) and
  [map_mockup/](references/map_mockup/) (the campaign map: the sheet inked by hand
  between the bands and the inspector; `map.html?state=split` and `?state=merge` are its
  two other frames, `map_split.png` and `map_merge.png`) and
  [sheets_mockup/](references/sheets_mockup/) (the guild's sheet: a member's character
  sheet as an open book, a band's packs, the charter, the reputations; one frame per
  `sheets.html?state=`) and [dialogue_mockup/](references/dialogue_mockup/) (the talk
  before a fight: the foe's page, the answers as cards, who speaks; one frame per
  `dialogue.html?state=`) and [report_mockup/](references/report_mockup/) (after a fight:
  the fallen, the report with its blows in ink, the level-up, the field, the arena's
  purse; one frame per `report.html?state=`) and [talents_mockup/](references/talents_mockup/) (the talent
  tree: the member and the four tracks on leather, the tree on paper, the talent in hand; one frame per
  `talents.html?state=`). Each folder is one HTML
  page at 1920x1080 with its PNG, its portraits and the game-icons.net glyphs it uses;
  the item glyphs there stand in for art not made yet.
- **Paper is for what you read, leather is for what you act on.** The board, the
  bestiary, the shelf and the guild's charter are paper; the unit panel, the packs, the
  purse and the buttons are dark leather and brass. A dragged ware is a paper slip.
- **Rock** is ink hatching that fades away from the rooms. Walls are masonry, trees or
  boulders by place.
- **Fog of war** reads the way a map would:
  - never seen is blank paper, with a margin note or sound rings for what is only heard;
  - seen before is a sepia wash;
  - in sight is lit.
- **UI materials** are leather, paper and brass, with a wax seal for End Turn.
- **Colour is still state:** blue is your side, blood red is the foe, brass is focus.

## Architecture (as built)

- **Core:** `gartok/*`. The spike changed it in two places, both refactors that the
  pygame screen uses too:
  - `actions.panel`: the action bar's entries, enabled state and hotkeys;
  - `artwork.portrait_path`: a portrait's file, split from loading it.
- **The shell** (step 7): `gartok/web/session.py` is what every screen's server half is (a
  `Session` with a `screen` id, a `state`, and its verbs in `GET` / `POST`); the server
  routes `/api/<screen>/<verb>` to the open session and refuses another screen's verbs
  (409). `/api/screen` says which one is open; `/api/lab/...` is the combat lab's (fights,
  a new one), there only when the game was opened on a lab fight. On the client,
  `index.html` + `shell.js` + `shell.css` are the shell: the helpers (`$`, `api`, `esc`,
  `face`, `Sound`), the stage scaled to the window, the palette, and the materials
  (`.paper`, `.kicker`, `.leather`, `.ghost-btn`, `.btn`, `.brass-btn`, `.seal`, `.medal`,
  the `.it` item row). Each screen is `client/screens/<id>/`: `screen.html` and the files
  `SCREENS` in `shell.js` names. A screen's scripts declare top-level names, so it opens
  once per page load; moving to another screen reloads the page on it.
- **`gartok/web/battle_session.py`** runs one fight: the turn flow `BattleScreen` runs,
  and the board as the side knows it, as JSON (`state`, `act`, `advance`, `route`,
  `aim`). `act` and `advance` return *steps*, one per decision: a `_StepTap` sits in
  front of `battle.sink` (the combat log's seam, which it passes through) and cuts a
  step after each recorded action, with the walks (cut to what the side sees), the
  events and the state after it. Sight and light are cached between steps while the
  observers, the lights and the walls stay the same.
- **The camera** (`screens/battle/board.js`): the board is painted once per state into a world canvas
  at a fixed cell size (capped by a pixel budget); zoom and pan only crop and scale it.
  The wheel zooms round the cursor, a drag pans, the arrows pan, `+`/`-` zoom, `C`
  centres the active unit; zoomed in, the camera follows whoever walks or acts.
- **`gartok/web/server.py`** is the JSON API over the open session, plus the client's
  files and the game's art.
- **`gartok/web/client/screens/battle/`** is the fight: `board.js` paints the board and
  `battle.js` handles input, tokens, panels and effects.
- **`gartok/web/map_session.py`** + `screens/map/` (`sheet.js` the sheet and its camera,
  `map.js` the rest) is the campaign map (step 8). Every order it opens has a screen (the away
  card that stood in for the rest is gone since 10e); a kind with none is a `ValueError`. A session
  holds its `game` (`Game.open`), so a verb can open another screen; its answer names the screen
  open and the client reloads on it.
- **`gartok/web/hub_session.py`** + `screens/hub/` (`hub.js` the frame, `shop.js` the shop tab) is a
  place's hub (step 9): the tabs pygame's hub shows for the same order, the keeper, the way back.
  `shop_tab.py` drives a headless `MarketScreen` (or `LibraryScreen`), as the map borrows pygame's
  reads. Item glyphs are game-icons.net SVGs in `assets/icons/item/`, one per `item_icon` kind
  (`item_icon.glyph`).
- **`gartok/web/jobs_tab.py`** + `screens/hub/jobs.js` are a giver's jobs board (9d), on pygame's own
  `MissionOfferScreen` held headless.
- **`gartok/web/craft_tab.py`** + `screens/hub/craft.js` are a workbench (9e: the forge, the carpentry,
  the Apothecary's craft, the Library's writing desk), on pygame's own `CraftingScreen` held headless.
- **`gartok/web/stable_tab.py`** + `screens/hub/stables.js` are the Farm's STABLES and the Carpenter's WAGONS
  (9f), on pygame's own `StablesScreen` / `WagonYardScreen` rules, borrowed as `medic_tab` borrows the Medic's.
- **`gartok/web/tavern_tab.py`** + `screens/hub/tavern.js` are the Tavern's RECRUIT, STUDY and PERFORM (9g), on pygame's
  own `TavernaScreen` held headless; the City Prison's THE CELLS (9i) is the same tab on `PrisonScreen`.
- **`gartok/web/initiation_tab.py`** + `screens/hub/initiation.js` are a sanctuary's INITIATION (9h), on pygame's own
  `InitiationScreen` held headless.
- **`gartok/web/vault_tab.py`** + `screens/hub/vault.js` are a stash: the Bank's VAULT (9j) on pygame's own
  `BankScreen` held headless, and the City house's THE HOUSE (9k) on `CityPropertyScreen`; the Bankers' JOBS beside the
  vault is `jobs_tab` on `TrustScreen`.
- **`gartok/web/garage_tab.py`** + `Stables.garage` in `screens/hub/stables.js` are the house's GARAGE (9k), on pygame's
  own `GarageScreen` held headless; the house's KITCHEN is `craft_tab` at the `cooking` station.
- **`gartok/web/claim_tab.py`** + `screens/hub/claim.js` are the Wilds Claim's THE CLAIM (9l), on pygame's own
  `WildsClaimScreen` held headless; its KITCHEN is `craft_tab` at `cooking` and its GARAGE `garage_tab` with `claim=True`.
- **`gartok/web/ledger_tab.py`** + `screens/hub/ledger.js` are Ledger Hold's THE DESK (9m), on pygame's own
  `LedgerScreen` held headless: its panels are data (`LedgerScreen.panels`) that both draw.
- **`gartok/web/guild_session.py`** + `screens/guild/` (`guild.js` the frame, members, charter and reputations,
  `bands.js` the band's packs) is the guild's sheet (9n), on pygame's own `GuildScreen` and `GroupScreen` held headless.
- **`gartok/web/dialogue_session.py`** + `screens/talk/` are the talk before a fight (9o), on pygame's own
  `DialogueScreen` held headless.
- **`gartok/web/report_session.py`** + `screens/report/` are the screens after a fight (9p): the fallen, the report, each
  level-up, the field (pygame's own `LootScreen` held headless) or the arena's purse, then the map.
- **`gartok/web/work_tab.py`** + `screens/hub/labor.js` are a work node's Work and Gathering
  tabs (9b): `WorkTab` / `GatherTab` borrow `WorkScreen`'s and `GatherScreen`'s reads; the
  verbs that run the clock (`work`, `gather`, `licence`) are `HubSession`'s, which holds the map.
- **Launch:** `python -m gartok.web --fight <lab fight>`, `python -m gartok.web --save
  <world>` (a guild's folder under `saves/`; `--screen` picks the screen), or double-click
  [references/battle_mockup/play_battle.bat](references/battle_mockup/play_battle.bat) and pick a fight.
- **Tests:** `tests/test_web.py`.

## Spike result (2026-10-23)

- **Cost:** about 520 lines of Python and about 1,040 of client code, against about
  2,500 for the pygame battle screen.
- **Latency:** five lab fights were played end to end through the API with no errors.

  | Fight | Median | Worst |
  |---|---|---|
  | Wilds | 7 ms | 15 ms |
  | Dungeon | 13 ms | 30 ms |
  | Fortress | 12 ms | 46 ms |
  | Necromancer (48x30 board, three sides) | 218 ms | 485 ms |

- **Look:** it reaches the mockup's direction on live data. The author's verdict:
  better, but a lot to improve in colour, fluidity and light.

## How to continue

"Seguir com plano de ui" means: take the first step below not marked done whose inputs
exist, do only that step, meet its **Done when**,
commit, then mark it done here and note anything it changed for the steps after it. One step per session. Start from this file, not from
exploring the code.

Two rules hold for every step:

- **Tests first, screenshots at milestones.** A step's rules are tested in pytest
  through the API (`tests/test_web.py`). A screenshot (1920x1080) is taken only when the
  step is about the look.
- **pygame is frozen.** It stays the shipping front-end until step 10, and nothing in a
  step may break it. A new feature meanwhile gets a working pygame screen, with no
  polish.

## Next steps, in order

The order puts the steps with a clear test first and the ones tuned by eye last. Light
and colour wait for the art, because tuning them before the textures exist is work
that the real art throws away.

### 1. Battle: fluidity — done (2026-10-23)

- Each decision of a turn is a step (see Architecture). The client plays them in order:
  the token walks its path cell by cell (110 ms a cell), then the board after the step,
  then its numbers and callouts, with 260 ms between steps.
- An AI turn that shows the side nothing plays with no pause, so a big fight's unseen
  turns do not drag.
- Tests: the steps of AI turns add up to the same fight as plain `take_turn`; a foe's
  walk never shows a cell the side does not know; the player's move walks its path.
- Not done: the fog and light layer is still redrawn on every step. It costs about 5 ms
  in the browser, so it was left.

### 2. Battle: speed on big boards — done (2026-10-23)

`vision.visible_cells` and `lighting.cell_levels` walked every light source for every
cell. Now each source lights its own reach once (`vision.lit_cells`), the line of sight
is tried only where light or dark range allows, and the session caches sight between
steps. The output is identical (a test checks it cell by cell against `can_see`).

| Necromancer, 300 requests | Median | Worst |
|---|---|---|
| Spike | 218 ms | 485 ms |
| With steps, before the fix | 237 ms | 688 ms |
| Now | 27 ms | 159 ms |

The worst requests are about half `ai.take_turn` itself (path fields on a 48x30 board,
about 85 ms for one turn), which pygame pays too. The client spends that time inside
the 480 ms pause before the turn, so nobody sees it. If it ever shows, the next cost is
`battle._pf_field` / `board._dijkstra`.

### 3. Battle: parity with pygame — done (2026-10-23)

- Zoom and pan (with step 1).
- **A question put to a person stops the fight until it is answered.** The state
  carries `setup` (the flag, a trapper's trap: the cells it may go on, Skip traps),
  `talk` (a patrol's challenge, played as `DialogueScreen` plays it: speaker, verbs
  with their check and odds, the line it got, Go on) and `handoff`. `advance` never
  answers them for the person.
- **Two players at one screen.** `BattleSession` takes controllers per side, as
  `BattleScreen` does. Between two people's turns the board hides behind a hand-over
  card (`take_seat`). Pick it in New fight, or with `--players 2`.
- **The Floating Disk** offers its heights per cell in `aim`. The rule moved to
  `FloatingDiskAction.heights`, which pygame now reads too. Light Globe and the disk
  now mark their reach while aiming, which they never did, in pygame either.
- **Crit banner and sound.** Each step says what it sounded like (heard even when
  unseen, as `BattleFX` plays it). The client plays `sound.py`'s own cues from
  `/api/sounds` at the settings volume.
- **Combat log.** Every fight from `python -m gartok.web` is logged to
  `combat_lab/<date>/` as the pygame lab logs its own (`--no-log` to skip it).
- **Withdraw**, missing before, is a button once the scenario allows it.
- **The action bar.** Delay sits apart, beside the seal. Spells fold into one plate
  that opens a list. Past the width, the row scrolls sideways, with arrows and the
  wheel. The unit card shows the level (racial, the one the bestiary shows of a foe),
  and each side has its own colour (squad, ally, foe, third side).
- Tests: every lab fight plays to its end through the session with every human choice
  answered through the API; the challenge, the flag, the hand-over, the disk's height,
  the sounds and the log each have their own.
- Left as is: with seed 7, the Ribbit Brothers' capture the flag stalls AI against AI
  (two survivors, one sitting on its own flag). That is the AI, not the web; it is in
  the backlog.

### 4. Art for the board — done as far as it got (2026-10-23)

Anchored on the reference portraits: a wall sheet, UI frames (9-slice), and outdoor
floors (earth, grass, sand). Files go in `gartok/web/client/img/`. As built: rock, grass and
sand floors, three trees, one boulder and the UI materials (paper, leather, brass button,
wax seal, portrait frame). Gemini ran out before earth, cobbles, the wall and two more
boulders; they stay unchecked under Art in [backlog.md](backlog.md). Steps 5 and 6 work
with what is in and keep today's drawing where a file is missing.

**Done when:** the files are in the repo. Steps 5 and 6 need them.

### 5. Battle: colour — done (2026-10-23)

Floor, walls, blank paper and remembered ground sat in nearly the same beige, and the
UI was warm on warm. As built (`screens/battle/board.js`, the tables at its top):

- **One value scale:** never-seen paper is the lightest, the floor mid, walls dark, the
  tokens the strongest contrast.
- **Each place tints one texture** (`FLOORS`): a `color` blend gives the place's hue and
  keeps the engraving's values, a multiply sinks it into the floor's band. Cave is cool
  rock, the dungeon's flagstones neutral grey, the arena warm sand, grass green-grey.
  Earth borrows the sand, darker, and cobbles the flagstones, smaller, until their art
  exists. Broad soft-light patches hide the tile's repeat.
- **Walls** (`WALL`): trees and boulders are the art, turned at random and tinted the
  same way into the dark band; masonry is drawn, dark (its art is still missing).
- **Remembered ground** is the board itself washed to sepia, darker, and hatched; it
  was a beige multiply barely apart from the paper.
- **The chrome** gets a cool verdigris accent (`--verdigris` in `shell.css`) on idle
  edges, labels, plates and the initiative chain, on a charcoal table. Brass stays
  the focus: the active unit, the chosen action.
- Left open: at the fit zoom the trees lose their leaf detail. (The torchlight that
  turned the grey back to brown and the remembered wash's cost were step 6's.)

### 6. Battle: light — done (2026-10-24)

The light was one flat level per cell, blurred: blocky, flat in daylight, too weak in
the dark. As built:

- **The server** sends `lights`, the sources the side sees (torch, fire, a lit unit) with
  their reach, and `daylight`. The per-cell levels leave those sources out
  (`lighting.cell_levels(..., sources)`), so a light out of sight is only a glow on the
  cells and never shows where it stands. The walls are the ones the side already knows.
- **The client** (`board.js`) casts each light as a polygon from its cell's middle,
  stopped by the known walls (only their exposed faces turned to the light), filled with
  a warm falloff; overlapping lights keep the brightest, as the rules do. What the
  levels leave (the eyes' own sight, a far glow) is cool and dim, so the dark has
  weight. Light paints only the cells in sight and never past the board.
- **By day** a sun stands up and to the left: each known wall or tree throws a soft
  shadow down and right.
- **Flicker:** the pools brighten and dim a little, about 15 times a second, drawn over
  the last paint (each pool's polygon is kept) instead of painting the board again; off
  by day and under `prefers-reduced-motion`.
- **Cost**, measured in Edge with the GPU, forcing the canvas to finish (a bare redraw
  of the sheet is about 14 ms of that): a state's paint went from about 50 ms to about
  30 ms once the blurs ran on the small cell grid, the remembered wash was cached per
  board and the world-sized canvases were reused; forty torches add about 12 ms; a
  flicker frame costs about what a bare redraw does.
- Left as is: a wall the side never saw can stand between a light it sees and a cell in
  sight; that cell then reads a little brighter than the rules have it. No information
  leaks (the cell is in sight); it is rare.

The battle is finished.

### 7. The shared base — done (2026-10-23)

- As built: see **The shell** under Architecture. The battle moved onto it with no change
  in look (a screenshot of the same fight before and after matches but for the portraits,
  which are drawn at random), and `--save <world>` opens the map screen on a save.
- Tests: the router names the open screen and refuses another screen's verbs; every file
  the shell's manifest names is served; a save opens the map through the router.
- For step 8: fill `MapSession.state` and `screens/map/`. The session is built from a
  loaded `Guild` (`Game.from_save`); nothing yet saves it back, which the map's orders
  will need (`persist.save_game`, as `App` does after each tick). Moving between screens
  (map → hub → battle) is a page reload on the screen the server opened; a verb that
  changes screen sets `game.session` and the client reloads.

The plan as written before it was built:

Before the second screen, so each screen after it is a small adapter and not a rewrite.

- **Server:** the `state` / `act` pattern of `battle_session` becomes generic: one
  session class per screen that turns the domain into JSON (as `ui/` turns it into
  dicts today) and applies its actions. The server routes by screen and can open any
  screen on a save: `python -m gartok.web --save <world> --screen <id>`.
- **Client:** a shell with a screen router, the CSS tokens (the mockups' palette and
  the fonts), and the materials as components: paper panel, leather panel, brass
  button, wax seal, item row, portrait frame.
- The battle moves onto it with no change in look.

**Done when:** the battle runs on the shell, and an empty second screen opens from a
save through the same router.

### 8. Map — done (2026-10-24)

1. A mockup at 1920x1080 in `references/map_mockup/`, in the menu mockup's language
   (the map inked by hand), approved by the author before any code. Done: built on the
   day-70 save `35d38388`; the decisions it took are in the table above. Not drawn, but
   decided: the seal is the CTA (`_footer_cta`), live red with "Fight" on an ambush and
   "Advance 24 h" once every band is garrisoned; a busy band's inspector shows its stop
   (Stop at, Stop resting, Recall from garrison) where the camp section is.
2. The screen on the shared base, on a real save: groups, orders, travel, the
   inspector, entering a node.

**Done when:** a pygame session's map loop (move a group, issue each order kind, advance
time, open a node) works in the browser, pygame's `map_screen.py` checked as the list.

As built:

- **The server** (`MapSession`) reads the map as pygame does: it mixes in
  `MapInspectorMixin` and borrows three `MapScreen` reads (`_order_status`, `_mates_for`,
  `_rest_plans`), so a node's buttons, the searches, the Wildfire and the REST rows stay
  one source. Step 10 moves them here when pygame goes. The state is the whole map for
  the side: the known nodes and roads, every band with its way ahead (each stop and when
  it gets there), its inspector and camp, the hours ahead, the seal. `preview` is the
  slip over a place (the path, its hours, the arrival).
- **The clock** runs as `App._advance` runs it: an order that leaves no band idle runs it
  to the next band gone idle or the next screen due; the seal passes 24 h once every band
  holds a post. A screen that falls due opens `AwaySession`; back from it, the next one
  due opens, then the map. Every order saves the world (`persist.save_game`, as `App`
  does), and `record_play` attaches the recorder as `App` does.
- **A forced fight** (ambush, guard, raid) stops its band on the map, as pygame's ambush
  does: no order, split or merge, and the seal turns red and opens it. The fight itself
  waits for step 10 (the web battle in the campaign): the away card says so, and the band
  keeps its fight due in the save, where pygame picks it up.
- **The client** follows the mockup: the sheet painted once, the land, roads and ways
  inked through the camera; places and pawns are HTML over it, each label set where it
  does not hit another place; the slip and the red ink on hover; Split and Merge in the
  picked band's card; stance and REST as segmented rows. The news of a run of the clock
  (meals, arrivals, deaths, level-ups) is a paper slip over the sheet.
- Tests: `tests/test_web_map.py` (travel, the clock waiting on an idle band, rest,
  search, stance, the stops, a busy band, entering a place, a screen due on the clock,
  split and merge, a fight due, the 24 h seal, the routing and the save).
- **Not in the browser yet**, each a pygame screen the away card stands in for until step
  9 or 10: the hand-over card between bands (the map just moves to the band, with the
  news slip); level-ups and memorials (a line in the news); the starved's belongings
  (pygame's loot screen; the browser does not offer them, so they are lost); the auto-win
  of an ambush; the Wildfire talk; leaving a broken wagon (travel is refused with a note);
  the camp kitchen; the guild and group sheets; the map's tutorial card.

### 9. Hubs, then the rest — done (2026-10-28)

- **Hubs:** one tabbed frame (the `TabbedHubScreen` equivalent) with the shop as its
  first tab, following [market_mockup/](references/market_mockup/). The other tabs (work,
  gathering, medic, jobs, initiation) then reuse the frame.
- **The rest, by family:** each family not yet mocked gets one mockup before its first
  screen (the guild and group sheets, the dialogues, the report after a fight); its
  other screens follow without one. The title screen follows the menu mockup.

**Done when:** every `*_screen.py` that the campaign can reach has a web screen.

**9a. The hub frame and the shop tab — done (2026-10-24).** As built:

- **The server** (`HubSession`): an order whose kind has a hub in pygame (market, forge,
  carpenter, apothecary, tanner, library, the Farm's stables, a sanctuary) opens it from the
  map, on the tab pygame opens first. The tabs are `hub_session.HUBS` (the hubs with their own
  class) or the node's own list as `TabbedHubScreen.for_node` builds it. A tab not drawn yet
  is a note inside the frame; the bank, the tavern's recruits, the property, the Claim and the
  rest still open the away card. Back lands on the map and saves.
- **The shop** (`ShopTab`): pygame's own trades on a headless `MarketScreen`: buy into a pack,
  onto a worn slot or shared out by room; hand items over, whole or part of a stack; sell (the
  till refuses what it cannot pay); lock, mark for auto-sell and sell the marked; distribute
  the load. Every verb answers the whole hub.
- **The client** follows the mockup: the keeper's strip with the deal (who speaks, you pay,
  they pay) and the till; the shelf on paper with its categories, stock pips and steppers; one
  leather column per pack (wagons and animals too) that scroll sideways past four; the sell
  plate and the purse with each pack's share. Drag a ware or an item where it goes, or click
  it and click where; Shift picks several; right-click an item for its menu. A Large weapon is
  its own row (pygame folds it into a size toggle).
- **Item glyphs:** 59 game-icons.net SVGs (CC BY 3.0, `assets/icons/LICENSE.txt`) in
  `assets/icons/item/`, one per `item_icon` kind; a test fails for a kind with no file.
- Tests: `tests/test_web_hub.py` (tabs and keeper, buy into a pack / by room / onto a hand,
  refusals, hand over part of a stack, sell and the till's limit, lock and auto-sell, back and
  the save, the routing). The drags, clicks and menu were also driven in headless Edge over
  the DevTools protocol on a copy of the day-70 save.
- **Next (9b):** the other tabs, one per session, in the order a guild meets them: work and
  gathering (the Lumber Yard), the Medic, the jobs boards, the forge and carpentry, the
  stables and wagon yard, the tavern's tabs, initiation. The mockup's open question is
  settled: a weapons shelf (damage, hands, range) reads in the 660px shelf. Left as is: an
  item's tooltip is the browser's own `title`.

**9b. Work and Gathering (the Lumber Yard, the Mine) — done (2026-10-27).** As built:

- **The layout** every tab after it can follow: the hub's cards are the tab's `hub_cards()`
  (`{label, value, tone}`, drawn by `labor.js`'s `cards`), the people or the thing you buy on
  leather at the left (660px, where the shelf sits), the ledger of choices on paper at the right.
- **Work:** the crew with each one's tool (own or the foreman's), wage and note; the four
  shifts. A shift runs the clock as `App._work_shift` does: the tab stays up with what the
  shift paid when its end is all that stopped the clock; another band idle (before or during
  the shift), a screen or a fight due, or a death lands on the map with the shift still running.
  `MapSession._advance` now answers `(idle gids, the dead)` for that.
- **Gathering:** the licence (status, the band's purse, buy) and the drop table; the shifts
  with haul, wage and ambush odds, live only with the licence. A gathering shift goes back to
  the map and the clock runs there, as pygame's does.
- Tests: `tests/test_web_hub.py` (the crew and shifts, a paid shift's pay and clock, a shift
  that lands on the map, the licence bought and refused, a gathering shift). The clicks were
  driven in headless Edge on a copy of the day-70 save.
- **Next (9c):** the Medic (the Apothecary's MEDIC tab), then the jobs boards.

**9c. The Medic — done (2026-10-27).** As built:

- **The server** (`MedicTab`) borrows `MedicScreen`'s reads and its pick rule (`_toggle`: visits
  combine, a hospital stay is picked alone) and `_treat`, now methods pygame calls too. The pick lives
  on the server (`patient`), so both front-ends hold one rule.
- **The layout** is 9b's: the ward on leather (each patient with an ailment chip per part, the price
  and hours, a red chip for a stay; the healthy ones in a line under it), the bill on paper (the picked
  ones itemised, the total, who waits, Treat or Admit), the last visit's lines under it.
- **The clock:** a visit passes its hours as pygame's does (`medic.treat` -> `guild.pass_time`) and
  the tab stays up; a stay that splits the patient off stays up too; a stay the whole band waits out
  (no free slot, or a lone patient) is an order, and the band goes back to the map where the clock runs.
- Tests: `tests/test_web_hub.py` (the ward and the bill, the pick rule, a visit paid and cured, a
  bill the band cannot pay, a stay split off, a stay the band waits). The two states were looked at in
  headless Edge at 1920x1080.
- **Next (9d):** the jobs boards (the Apothecary's, the Tanner's, the Library's, the sanctuaries').

**9d. The jobs boards — done (2026-10-27).** As built:

- **The server** (`JobsTab`) holds the giver's own pygame board headless (`TannerScreen`,
  `ApothecaryMissionScreen`, `LibraryMissionScreen`, `ShrineMissionScreen`, picked by the node's function as
  `TabbedHubScreen.for_node` picks it), as `ShopTab` holds a `MarketScreen`: the board, the terms, the labels
  and the notices are pygame's. Accepting and handing over moved out of `MissionOfferScreen._click` into
  `accept` / `turn_in`, which pygame calls too. A sanctuary's dragon-egg sale is its `footer_action`.
- **The layout** is 9b's: on leather who signs (the leader; the job travels with them) and what the packs
  already carry toward each job the band can take or hand over; on paper the board, one row per job (glyph,
  name, tags, blurb, terms, button). A job whose goal is a fight (the Battlefield, the Necromancer, the
  Wildfire) keeps its button off: the fight is met on the map.
- Tests: `tests/test_web_hub.py` (the board, the signer and the carried goods; accepting; handing over and
  the pay; refusals; a sanctuary's egg sale). The open and the taken board were looked at in headless Edge at
  1920x1080 on a copy of the day-70 save.
- **Next (9e):** the forge and carpentry (the workbench), then the stables and the wagon yard.

**9e. The workbenches — done (2026-10-27).** As built:

- **The server** (`CraftTab`) holds pygame's `CraftingScreen` headless at the station of the node's function
  (the Smithy's forge, the Carpenter, the Apothecary, the Library's scriptorium): one tab class for every
  `craft`, `forge` and `carpenter` tab key. The hour sets (`WAIT_HOURS`, `ALONE_HOURS`) and the rule that
  keeps a crafter from going alone (`alone_blocker`) moved out of pygame's draw into names both front-ends use.
- **The layout** is 9b's: the crafters on leather (click to pick; each with d20 + INT and the batch under way)
  and the last stint's lines under them; on paper the picked crafter's recipes, one row each (glyph, level,
  work XP, yield, what it uses with what the band holds, the tools, the progress bar of a batch under way) with
  the two rows of hours: the group waits (1 / 4 / 8 h) or the crafter goes alone (4 / 8 / 16 h), or why not.
- **The clock:** a stint the group waits is rolled now and passes its hours as pygame's does
  (`Guild.crafting_shift`) and the tab stays up with its lines; alone is `solo.craft` (a solo task with its own
  group slot) and the band goes back to the map, as pygame's does. The Claim kitchen (station `cooking`) is not
  a hub tab: it waits for the Claim's screen.
- Tests: `tests/test_web_hub.py` (the crafters and the recipes with what they use, a stint the group waits, a
  stint alone and its refusal with no slot, each bench at its own station). Looked at in headless Edge at 1920x1080.
- **Next (9f):** the stables and the wagon yard (the Farm's STABLES, the Carpenter's WAGONS).

**9f. The stables and the wagon yard — done (2026-10-27).** As built:

- **The server** (`StableTab`, `WagonTab`) borrows `StablesScreen`'s and `WagonYardScreen`'s rules (the pooled purse
  paid richest first, the herd limit, the tack fitted once, the resale to the leader, nothing sold while it carries
  cargo). Buying and selling a wagon moved out of `WagonYardScreen._click` into `_buy_wagon` / `_sell_wagon`, which
  pygame calls too; a loaded wagon now says why it will not sell, in both. A purchase resyncs the shop tab, where
  animals and wagons shop as packs.
- **The layout** is 9b's: what the band keeps on leather (each animal with its portrait, tack, job, hunger and the
  tack it can still take; each wagon with what pulls it, its cargo, HP and meals aboard) with its Sell; on paper what
  is for sale, with why a row is off (the herd full, the purse short). Wagons use game-icons.net's `old-wagon`
  (`assets/icons/item/old-wagon.svg`).
- The Farm's subtitle printed its languages as a Python tuple; it reads "Ankarin or Sylvan" now.
- Tests: `tests/test_web_hub.py` (the Farm's tabs and the offers, buying an animal and the shop seeing it, a full herd
  and a short purse, tack and a sale back only unloaded, the wagon yard's buy and sell). Both tabs were looked at in
  headless Edge at 1920x1080; the clicks were not driven, the verbs are tested through the session.
- **Next (9g):** the tavern's tabs (Recruit, Study, Perform), then initiation.

**9g. The Tavern — done (2026-10-27).** As built:

- **The server** (`TavernTab`) holds pygame's `TavernaScreen` headless, one object for the three tabs as pygame's hub
  shares one screen: the pool, the pitch and its bars, the study targets and the show are its. Picking a stranger, renting
  and cancelling the rooms, setting and stopping a study target moved out of `TavernaScreen.handle_event` into
  `_pick_candidate`, `_rent_study`, `_cancel_study`, `_set_target`, `_stop_study`, which pygame calls too; `_perform`
  answers the show's lines. The map's ENTER THE TAVERN (order `recruit`) and the garrisoned band's `visit_tavern` open it
  on RECRUIT, beside the Food & Drink shop.
- **The layout** is 9b's. RECRUIT: the strangers on leather (status, archetype chips with their tooltips); on paper the
  picked one's dossier (HP, AC, speed, attack, kit glyphs, the racial ability), the last pitch's two rolls with every
  modifier, who makes the pitch (each one's odds or why not) and the button. STUDY: the rent on leather with Rent or
  Cancel; on paper each member's target and progress, Set target opening the scrolls and dictionaries the band carries in
  place (pygame's modal). PERFORM: the players on leather (click to seat; who has no instrument is dimmed); on paper the
  rules, the show's length as a segmented row, Play and the last show's lines.
- **The clock:** a show passes its hours here (`Guild.perform_shift`) and the tab stays up with what it paid; a death
  that empties the band lands on the map. Renting the rooms puts the band on its garrison post and stays.
- Tests: `tests/test_web_hub.py` (the tabs and the dossier, a pitch won and saved, a pitch lost and the bar, the study
  target and the rooms, a show and its seats, entering from a study post). The three tabs were looked at in headless
  Edge at 1920x1080 on a copy of the day-70 save.
- Left as is: `test_buying_into_a_pack_pays_from_the_purse_into_the_till...` fails about one run in five, before this
  step too (a random ware); it is not the tavern's.
- **Next (9h):** initiation (a sanctuary's INITIATION tab), then the prison's cells.

**9h. The initiation — done (2026-10-27).** As built:

- **The server** (`InitiationTab`) holds pygame's `InitiationScreen` headless: the school's terms, the blockers (no standing,
  no Holy Symbol, a tested blood with no magic, a band with an order in flight), the status line and the begin are its.
  Picking and beginning moved out of `InitiationScreen._click` into `_pick` / `_begin`, which pygame calls too.
- **The layout** is 9b's: the band on leather (click who stays; a chip for where each one stands, initiated or the stage
  and its points, or the reason the school will not take them, dimmed); on paper the terms as a ledger, the picked one's
  bar and status (points and days left) and BEGIN or RESUME THE RITE, the sanctuary's lines under it.
- **The clock:** a novice split off into a group of their own leaves the tab up; a band that boards whole (a lone
  member, or no free group slot) goes back to the map, where the clock runs.
- Tests: `tests/test_web_hub.py` (the terms and the pick, a school with no standing, the Faith's symbol, a novice split
  off, a band that boards whole). Looked at in headless Edge at 1920x1080 on a copy of the day-70 save.
- **Next (9i):** the prison's cells (`PrisonScreen` is the Tavern's RECRUIT with a bail, so it can reuse `TavernTab`).

**9i. The prison's cells — done (2026-10-27).** As built:

- **The server:** the order `prison` opens a hub with one tab, THE CELLS (`hub_session.HUBS["prison"]`), and the
  keeper is the warden. `TavernTab(prison=True)` holds pygame's `PrisonScreen` headless, so the weekly pool, the bail
  (`recruit.bail_cost`, paid richest first before the roll), the +2 it buys and the bar after a lost pitch are its; the
  tavern's verbs (`candidate`, `recruiter`, `convince`) serve it as they are.
- **The layout** is the Tavern's RECRUIT: each prisoner's bail beside their tongues, a bail line in the dossier (gold
  when the band can pay it, red when not), the button "Pay the $N bail and convince" or "Cannot afford", and the cells'
  own rule in the footer.
- Tests: `tests/test_web_hub.py` (the cells and the warden, each bail, a bail paid and the prisoner signed with the
  objective, a lost pitch that keeps the coin, a purse too short). Looked at in headless Edge at 1920x1080 on a copy of
  the day-70 save.
- **Next (9j):** the bank (`bank_screen.py`, the City's VISIT THE BANK), the first of the holdings: the strongbox, then
  the house and the Claim.

**9j. The Bank — done (2026-10-27).** As built:

- **The server:** the order `bank` opens a hub with VAULT and JOBS (`hub_session.HUBS["bank"]`), the keeper Elysia.
  `VaultTab` holds pygame's `BankScreen` headless: the chest's weight cap, the hard load limit on what comes out, the
  slots, the services (rent the strongbox, buy the house: refused when off, as pygame's button is) and the purse are its.
  The gold exchange moved out of `BankScreen._exchange_click` into `_exchange`, which pygame calls too. JOBS is `JobsTab`
  on `TrustScreen` (the Test of Trust), added to `jobs_tab.BOARDS` as `trust`.
- **The layout** is the shop's: the strongbox on paper where the shelf sits (each stack with its weight, how many are
  held and a Take stepper, the chest's load as a bar that shows what a pick would add), one leather column per pack, the
  Bankers' services on the sell plate (or, once rented and with no house to buy, the exchange's rates), the purse with
  Distribute and Done. Drag onto the chest to stow, out of it onto a pack or a worn slot; click and click; Shift picks
  several; right-click for the menu (where to send it; on a coin stack, mint or melt gold).
- The shop's pointer handlers answered on every tab of the hub (a Done elsewhere would have gone back twice); they now
  answer only on the shop.
- Tests: `tests/test_web_hub.py` (the tabs and keeper, the rent and a short purse, part of a stack in and out, the chest
  and a pack that will not hold it, a weapon from the chest into a hand, minting and melting, the Test of Trust). The
  map's away-card tests now use the property. Looked at in headless Edge at 1920x1080 on a copy of the day-70 save, and
  a drag in, a click out, the menu, a mint and Done were driven over the DevTools protocol.
- **Next (9k):** the house (`city_property_screen.py`, VISIT THE PROPERTY): the stash, the tax, the oven and its
  kitchen, the garage; `RepossessionScreen` before it when the tax is too far behind.

**9k. The City house — done (2026-10-27).** As built:

- **The server:** the order `property` opens a hub whose tabs follow the house (`hub_session._house_tabs`): THE HOUSE
  always, KITCHEN once it has an oven, GARAGE once it is owned, so buying the house or the oven adds its tab at once.
  pygame's COOK and GARAGE services are tabs here (the screen is built without `on_cook` / `on_garage`).
- **The house** is `VaultTab` on `CityPropertyScreen`: the stash, the tax and debt cards, buying the house, the oven and
  paying the debt are pygame's. `VaultTab` takes the screen class; the gold exchange and Distribute stay the bank's only
  (`exchanges`, `CAN_DISTRIBUTE`), and `vault.js` reads the stash's owner, title and copy off the state.
- **The kitchen** is `CraftTab` at the `cooking` station (`craft_tab.STATIONS["kitchen"]`).
- **The garage** (`GarageTab`) holds `GarageScreen` headless and calls its own click by index from a uid: the bays, the
  herd limit, the pooled purse, parking and taking out, and the repair, whose hour runs through `HubSession._tick` (as
  `App._tick_outside_map`: the other bands keep in step, what falls due waits for the map). On leather what is parked; on
  paper the next bay and what the band has with it.
- **Repossession:** with the tax too far behind, the hub shows the Bankers' notice in place of the tabs (no tabs, every
  tab verb refused); return (the debt) or squat, both back to the map with pygame's notice.
- The map's away-card tests now use the Test of Trust. `test_the_faith_rite_asks_for_a_holy_symbol` failed when a random
  Priest carried his own Holy Symbol; the test takes them away first.
- Tests: `tests/test_web_hub.py` (the house before and after it is bought, stowing with no gold exchange, the oven and a
  stint of Jerky, the debt, the garage's bays, parking and taking out, a repair and its hour, both answers to the notice).
  The three tabs and the notice were looked at in headless Edge at 1920x1080.
- **Next (9l):** the Wilds Claim (`wilds_claim_screen.py`, the Claim's own screen: its stages and their fights, the
  kitchen at the `cooking` station, the Claim's garage with `GarageTab(claim=True)`).

**9l. The Wilds Claim — done (2026-10-27).** As built:

- **The server:** the map's THE WILDS CLAIM (order `claim`) opens a hub whose tabs follow the claim
  (`hub_session._claim_tabs`, beside `_house_tabs` in `DYNAMIC`): THE CLAIM always, KITCHEN once the hearth can cook
  (a fire or the oven), GARAGE once the garrison opens it. `ClaimTab` holds pygame's `WildsClaimScreen` headless and
  calls its own methods, so scouting, the fences' Lumber, the garrison and its job, the campfire's WIS roll, the oven and
  the banked Lumber stay one source; a verb the stage does not offer is refused. The kitchen is `craft_tab`'s
  `kitchen`; the garage is `GarageTab(claim=True)`: no bays, no limit, the bolt chance while nobody holds it.
- **The clock:** scouting, the fences and the hearth pass their hours here (`guild.pass_time`, as pygame's do) and the
  tab stays up with what came of it; garrisoning is an order, so the band goes back to the map. The two fights (CLEAR,
  SWEEP) are campaign fights: the away card says so (`AwaySession` with `fight=True` and no order) and nothing changes
  until step 10.
- **The layout** is 9b's: the band on leather (a chip for the Lumber and Stone Brick each carries); on paper the six
  stages as a track (done, in hand, to come, seized), the stage's lines, its progress (the fences' Lumber, the days left
  and who holds it, the banked Lumber), its buttons and the hearth's two builds.
- The hub frame's fallback glyph (a place with no keeper) was painted in the medallion's own gradient and never showed;
  it is dark now.
- The test guild's Fighters now carry no Lumber or Stone Brick (a random kit could, and failed the garage's mend test
  about one run in eight). `test_the_house_stows_and_gives_back_but_mints_no_gold` still fails about one run in twenty
  (a random kit); it was left.
- Tests: `tests/test_web_hub.py` (the claim's hub and scouting, the fights on the away card, the fences, the garrison
  and its garage, the fire, the kitchen and the oven, the established and the seized claim, the claim garage). Looked at
  in headless Edge at 1920x1080.
- **Next (9m):** the places left behind the away card: Ledger Hold (`ledger_screen.py`: the Bankers' chest exchange,
  Commander Varkas, the supply runs), the Library's study desk, the map's campfire cooking (`craft_tab` at `cooking`);
  then the first family that needs a mockup, the guild and group sheets.

**9m. Ledger Hold and the campfire — done (2026-10-27).** As built:

- **Ledger Hold:** the order `ledger` opens a hub with one tab, THE DESK (`hub_session.HUBS["ledger"]`), the keeper
  Commander Varkas. `LedgerScreen` lost its per-panel draws: `panels()` returns the desk's panels as data (the chest
  while someone carries it, the mentorship and the supply run once the Bankers vouch, else the gatehouse) and `_act`
  is what its buttons do; pygame draws the panels from that and `LedgerTab` sends them. A button the desk does not offer,
  or offers greyed out, is refused. The supply run is an order: the band goes back to the map, where the clock runs.
- **The layout:** the band on leather (a chip on whoever carries the chest or the letter); on paper the panels side by
  side, each with its facts, its button and the ambush warning under the supply run.
- **The campfire:** the map's campfire (lit, or lit first) opens a hub with one tab, CAMPFIRE: `craft_tab`'s `kitchen`
  at the `cooking` station, with no keeper (the band's own fire). Back lands on the map.
- **The Library's study:** pygame's STUDY tab (`TabbedHubScreen.for_node`) is the Library's shop a second time, and the
  map only ever opens the Library's own hub (shop, write, jobs); the browser's node tabs drop it.
- Tests: `tests/test_web_hub.py` (the desk and the gate, the chest for a letter, the mentorship accepted and delivered
  once trained, the supply run refused short of cargo and sent off, the campfire's kitchen, the Library's tabs). Looked
  at in headless Edge at 1920x1080.
- **Next (9n):** the first family that needs a mockup: the guild and group sheets (`guild_screen.py`, `group_screen.py`:
  the map's Gear & quests and the guild's tabs), one mockup first, then the screens. What still opens the away card
  after that: the wildfire's talk, the campaign fights (step 10), `trust` (the City's Test of Trust as its own order).

**9n. The guild and group sheets — done (2026-10-27).** The mockup came first:
[references/sheets_mockup/](references/sheets_mockup/) `sheets.html` (built on the day-70 save `35d38388`; `data.js`
is the save read through `GuildScreen`'s own adapters) has four frames, one per `?state=`:

- `members` (`sheets_mockup.png`): the roster on leather (filters, each band and its herd, HP, badges); the member's
  sheet as an open book on paper, the RPG's own character sheet: the engraved plate, attributes and fight boxes, the
  weapon, the kit, the race's gift on the left page; the three careers, the talents and the record on the right; on
  leather beside it what can be done for them: the talent tree, the roles (guild leader, group leader, rations, pack
  load) and the way to the band's gear.
- `guild` (`sheets_guild.png`): the charter on paper (banner, founding trade, fame and the band slots as wax seals,
  standing per faction, the bands, the notices); the holdings on leather, each with its stamp.
- `reputations` (`sheets_reputations.png`): the objectives as a checklist page; each faction a paper card with its
  rep as a wax seal, its deeds ticked in red ink and its unlocks.
- `bands` (`sheets_bands.png`): one band at a time. A chip per band across the top (its faces, where, what it does,
  how full; the picked one carries the rename pencil), then the band's load, rations and pace and its two actions;
  one leather column per member as the shop's; on the right the wagon (hull, the hitched animal, the cargo) above the
  band's jobs in hand and its captives. The item menu (drop, split, lock, send to whom with the room each has) is a
  paper slip, and only the picked band's packs are on the table.

Decided with the author (2026-10-27):

- **One sheet, four tabs: Members, Bands, The Guild, Reputations.** pygame's separate Manage Gear screen
  (`group_screen.py`) becomes the Bands tab. An item moves only between people in one place, and one place is one
  band, so the tab shows one band at a time: no trade can cross bands, and the rule shows on the table instead of as
  a refusal. The map's Gear & quests opens the sheet on Bands with that band picked; the member sheet's button and
  the charter's band table go there too. A band with a fight due shows read-only (`Group.locked`).
- **A member is hungry from the first hunger level**, when the attributes already drop; pygame waited for the second
  (`guild_screen._needs_attention`, `hunger_level >= 2`), a bug to fix with the screen.

As built:

- **The server** (`GuildSession`, screen `guild`): the map's Guild button opens it on MEMBERS, Gear & quests on BANDS
  with that band picked. It holds pygame's `GuildScreen` headless for the roster, the sheet, the roles, the charter
  and the reputations, and one `GroupScreen` per picked band for the kit: the moves (`_give_many`, onto a worn slot, an
  animal's tack, a wagon's room, an animal onto a wagon to hitch it), the item menu (`_menu_rows` / `_menu_run`: drop,
  open a chest, drink, study, hand to whom), the split, the lock, the band's buttons (distribute, treat sickness and
  poison, ride, hitch, repair, release). A band with a fight due answers every kit verb with pygame's refusal. A repair's
  hour runs through `MapSession.tick_outside` (moved there from `HubSession._tick`, which now calls it). The campfire
  opens the hub's kitchen as the map's does.
- **The talent tree** is still pygame's: its button opens the away card, which now takes a `resume` and comes back to
  the sheet instead of the map.
- **The layout** follows the mockup: the roster on leather (filters, a fold per band, badges), the sheet as an open
  book (plate, attributes, the fight boxes with each breakdown as its tooltip, the weapon, the kit, the race; the
  careers, the talents, the record), the roles beside it; one band's chips, load, rations and pace, one column per
  member and animal, the wagons with their hull, hitched animals and cargo, the jobs in hand and the captives; the
  charter with fame, the band slots as wax seals, standing, the bands (a row opens that band), the notices; the
  holdings, the strongbox's contents behind Look inside; the objectives and one card per known faction.
- **Hungry from the first level:** `guild_screen._needs_attention` and the HUNGRY badge now read `hunger_level >= 1`,
  in pygame too.
- Left out: pygame's CARGO view (every stack of the band in one sorted table) and the mockup's "road ahead" card;
  an item's tooltip is the browser's own `title`. A band's tab has no tutorial card yet (no web screen has one).
- Tests: `tests/test_web_guild.py` (the two ways in, the roster and the sheet, hunger at the first level and the
  alerts filter, the fold and the idle filter, a role and its refusal, the talent tree's away card and its way back,
  moves within a band and onto a hand, no move across bands, the item menu, split and lock, the read-only band, the
  wagon's room and the hitch, rename and release, the charter and the strongbox, the reputations, back and the save).
  The four tabs were looked at in headless Edge at 1920x1080 on a copy of the day-70 save, and a drag between packs,
  the item menu, a member picked in the roster and a role were driven over the DevTools protocol.
- **Next (9o):** the dialogues (`dialogue_screen.py`: the talk before a fight), the next family that needs a mockup;
  then the report after a fight. What still opens the away card: the talent tree, the wildfire's talk, the campaign
  fights (step 10), `trust`.

**9o. The dialogues — done (2026-10-27).** The mockup came first:
[references/dialogue_mockup/](references/dialogue_mockup/) `dialogue.html` (built on the day-70 save `35d38388`;
`data.js` is a real `Ambush`, `Patrol` and `BossTalk` read through `DialogueScreen._data()`, with every member's
options) has four frames, one per `?state=`. Read left to right: they speak, you answer, who answers.

- `ambush` (`dialogue_mockup.png`): the leader on paper as a bestiary page (the engraved plate, race and trade, the
  tongues they speak, their line in large type, the rest of the pack below), and why the checks moved (the
  `Ambush.edge` the squad's look gives, which pygame never shows). In the middle, one paper card per verb: what a
  pass does in green ink and a miss in red, the odds, the check, and the d20's twenty faces with the ones that pass
  inked ("8 or more on the die"); the bribe's price against the band's purses; Attack as "roll initiative". On
  leather, the band: CHA, INT and tongues, the one shared with the leader underlined; a member with no shared tongue
  is dimmed ("no Goblin"); a click picks who answers.
- `result` (`dialogue_roll.png`): the card played, then a slip with the d20 drawn, the sum against the DC, a stamp
  (SEEN THROUGH / IT HOLDS), what happened, and "how the fight opens" read off the `Opening` (caught off guard,
  they come on shaken, they get the jump), then the result's one button.
- `guard` (`dialogue_guard.png`): the same table for the City's patrol; the wanted member carries the crime.
- `boss` (`dialogue_boss.png`): no verbs; the middle is the order of speakers (who speaks now, who waits) and GO ON.

As built:

- **The server** (`DialogueSession`, screen `talk`): it holds pygame's `DialogueScreen` headless (who speaks, the
  verbs, the result) and answers `speaker`, `choose` and `go_on`. Three talks open it: `forced_talk` (the map's Fight
  on a band with a fight due, when the pack has a speaker: the guard and the ambushes, as `App._open_dialogue`),
  `wildfire_talk` (the map's TALK at a focus, as `MapScreen._wildfire_talk`) and `boss_talk` (an arena boss's lines;
  nothing opens it yet, the bout is step 10's). A pack with nobody who speaks goes straight to the fight's away card.
- **How each talk ends:** a fight goes to the away card with the roll kept on the order (`Order.parley`, saved the
  moment it is rolled), so Fight again opens the talk on its result and never rolls anew; peace settles the order
  (`forced.settle_talk`), surrender jails the wanted, Run falls back (a re-catch is the band's next fight), and the clock
  runs on from the map; the Wildfire's fight is the map's ATTACK THE CAMP (or STORM THE FORTRESS), its last lesson puts
  the fire out.
- **The roll** is read off the result's line (`d20(n) +m = t vs DC d`), never re-rolled; the stamp follows the die
  (an Intimidate that lands still fights, with them shaken), and the answer played is kept as it read before the roll.
- **The layout** follows the mockup's four frames; the d20 tumbles when it is thrown, not on a reload.
- Left out: a tutorial card (no web screen has one yet).
- Tests: `tests/test_web_talk.py` (the map's Fight opens the talk, the language gate, a bribe, an empty purse, a failed
  bluff kept on the order and in the save, Intimidate's two openings, a pack that cannot talk, the guard's wanted, the
  cells, Run, no second Run, the Wildfire's two checks and its miss, a boss's lines, the roll read off the line). The
  ambush, the roll, the guard and the boss were looked at in headless Edge at 1920x1080 on a copy of the day-70 save.
- **Next (9p):** the report after a fight (`aftermath.py`'s memorials, report, level-ups, loot), the next family that
  needs a mockup. What still opens the away card: the talent tree, the campaign fights (step 10), `trust`.

**9p. The report after a fight — done (2026-10-28).** The mockup came first:
[references/report_mockup/](references/report_mockup/) `report.html` is built on the day-70 save `35d38388`: band 1
against a five-strong ambush on the Old Road, played AI against AI until a seed gave a win with deaths, a level-up and
loot (seed 30 under `PYTHONHASHSEED=0`; the fight is not the same across processes otherwise). `data.js` is that
outcome read through pygame's own `ReportScreen.data()`, `LevelUpScreen.data()`, `memorial_screen.card()` and the
loot pool; the purse is `arena.brawl_bout()` with the same survivors. Five frames, one per `?state=`, in the order
`app_battle` plays them; a strip at the top right names where each frame sits in that chain:

- `memorial` (`report_memorial.png`): the fight's dead lie together, one mourning card each (the portrait in grey,
  days with the guild, "one of the founders" for a day-1 member, who put them down with their medal, the line of the
  fall, and that their kit lies on the field).
- `report` (`report_mockup.png`): VICTORY stamped on a muster roll; the band on the left (status, combat XP before
  and after, takedowns, a LEVEL mark), the pack on the right, and every takedown drawn between them in ink (blue the
  band's, dashed red the pack's). On leather: what follows, in order, and each survivor's HP after the fight.
- `level` (`report_level.png`): the plate with a wax seal of the new level, the gains as a ledger (struck before,
  after, the delta), the bar to the next level, the talent pick that waits.
- `loot` (`report_loot.png`): the shop's layout: the field's stacks on paper by kind, one leather column per survivor
  (HP, load against the hard limit, worn slots, pack); a dragged Brigandine refused on the column that cannot carry it,
  with why; Take what fits and Leave the rest on leather.
- `purse` (`report_purse.png`): the purse against the stake (staked, won, net) and one card per fighter, Give on each.

The author approved its proposals (2026-10-28): the dead on one page, not one card per death; the blows as lines with
the pack listed beside the band; HP after the fight and the chain of screens on the report. Unchanged rules: the purse
lands whole on one fighter, the loot's ceiling is each one's hard load limit, whatever stays on the field is lost.

As built:

- **The server** (`ReportSession`, screen `report`) takes the battle and `campaign.absorb_battle`'s outcome and lays out
  the chain as `app_battle._battle_end` plays it: the fallen (when any), the report, one page per level-up, then the
  arena's purse or the field (only with loot and survivors), then `then()` (the map by default). A full wipe shows only
  the fallen. Verbs: `next`, `talents` (the away card, which comes back to the same level-up), `take`, `auto`, `give`.
- **The field** is pygame's own `LootScreen` held headless: `take` sets its picks (a field stack with a quantity, a pack
  row, a worn slot) and calls `_give_many` onto a member's pack or slot, or back onto the field; a load past the hard
  limit is refused with why (`refused`), shown on that column; what each member took this page is marked new and
  summed in the footer. Take what fits is `_auto_pick`.
- **The purse** lands as `RewardScreen` lands it, once, and the save is written; Continue waits for it.
- `aftermath.LevelUp.headline` (which track the card is about) moved out of `LevelUpScreen`, which reads it now.
- **What opens it:** nothing yet. The campaign fight is step 10's; it hands this session the battle and the outcome
  (and the arena's offer for the purse). The Adelio and Ribbit recruit prompts are not drawn: they open the Tavern's
  RECRUIT, which is built.
- Left out: a tutorial card (no web screen has one yet).
- Tests: `tests/test_web_report.py` (the chain in order, a quiet win, a full wipe, the killer on the fallen page, the
  report's band, pack, blows and HP, a foe left stable, the level-up's ledger and pick, the talents round trip, the
  field's kinds, part of a stack, a refusal with why, a worn slot and back to the field, Take what fits, what is left
  is lost, the purse instead of the field, once only). All five pages were looked at in headless Edge at 1920x1080
  on a copy of the day-70 save, on an Old Road ambush played AI against AI.
- **Next:** what still opens the away card is the talent tree, `trust` and the campaign fights. The talent tree is the
  last screen family of step 9 that the campaign reaches; step 10 follows it.

**9q. The talent tree — done (2026-10-28).** The mockup came first:
[references/talents_mockup/](references/talents_mockup/) `talents.html` is built on the day-70 save `35d38388`: Ylhel
after the report's fight (combat 2, one pick). `data.js` is the real trees read through `talents.TREE` /
`racial_tree`, each node's state off `Unit.holds_talent` / `offerable`, and for an open node the sheet before and
after the pick (`choose_talent` on a copy). `big.js` is the load test: a made-up combat tree of 100 talents (8 roots,
8 tiers, 40 leaves, 6 with two requirements). Frames, one per `?state=`:

- `combat` (`talents_mockup.png`), `locked`, `racial`, `magic`: the first layout, one track per paper page with the
  trees in attribute families. Kept as the record of what a fixed page holds (about 30).
- `big_down`, `big_zoom`, `big_right`: the 100 top-down and left-to-right with a camera; discarded (15% at FIT).
- `big_radial` (THE MAP) and `big_focus` (THE BRANCH), with the toggle between them; `&real=1` puts today's 30
  real talents in them (`talents_real_radial.png`, `talents_real_focus.png`); `&sel=<id>` picks the talent in hand.

Decided with the author (2026-10-28):

- **Two views, one toggle.** THE MAP is the default: the portrait at the centre, the roots on the first ring, each
  tier one ring out; a camera as the map's (wheel, drag, FIT); at FIT the names of what is held and what can be taken
  stay (a name that hits another hides until zoomed), the rest wait for the zoom. THE BRANCH: every talent as an
  outline open along the picked branch (a closed branch shows held/total and how many are open), and round the
  talent in hand what it needs above, its siblings, what it opens below. The view last used is remembered.
- **The layout reads only `requires`**, so the tree may grow wider, deeper or lose its families; a second
  requirement is a red dotted line.
- **Click picks, TAKE confirms** (pygame takes on click; a pick is for good). The card shows what moves on the sheet
  (STR 8 → 9, and when the modifier does not move), the branch, and what the talent opens.
- **On leather:** the member, the four tracks with their picks, CAN TAKE NOW (every open talent; a click takes it in
  hand), the band's faces with their waiting picks.

As built:

- **The server** (`TalentSession`, screen `talents`) holds the member, the track on the page and the talent in hand.
  Each node's state: taken, open (a pick can take it), waiting (it could, with a pick), locked (what it needs is not
  held), granted (a school's root). The talent in hand carries its status, the branch above it, what it opens, and for
  an open one the sheet's numbers that move (`delta`): read off a deep copy with the talent added and the sheet
  derived again, not through `choose_talent`, which would write a pick to the play log. Verbs: `look` (another member
  of the band, another track, a talent in hand), `take` (`Unit.choose_talent`; a refusal says why: needs X first, no
  pick, no school yet, the next racial pick's level), `back`. The save is written on each pick.
- **What opens it:** the member's sheet (`GuildSession.talents`, back to the sheet) and a level-up's Pick talents
  (`ReportSession.talents`, back to the same level-up, with the report's chain and Talents marked now). It lands on
  the first track with a pick waiting, the talent in hand its first open one.
- **The client** follows THE MAP and THE BRANCH. The rings are leaf columns round the portrait, the depth off
  `requires`; zoomed out, a name that hits another hides (the talent in hand first, then what can be taken); the
  camera is kept while the same member's same tree is shown. The view last used is in `localStorage`. TAKE (or Enter)
  spends the pick, Escape goes back. There is no second requirement in the data yet, so no red dotted line is drawn.
- Left out: a tutorial card (no web screen has one yet).
- Tests: `tests/test_web_talents.py` (the sheet opens it on the track with a pick, open / locked / waiting, the delta
  without touching the member, the branch and what it opens, a pick that opens what hangs from it and lands in the
  save, each refusal with why, CAN TAKE NOW across tracks, the racial track's next pick, the magic tree with no
  school, back, the routing); the level-up's round trip in `tests/test_web_report.py`, the sheet's in
  `tests/test_web_guild.py`. THE MAP, a zoom, THE BRANCH, a locked talent, a pick taken, the magic and the racial
  trees were looked at in headless Edge at 1920x1080 on a copy of the day-70 save, driven over the DevTools protocol.
- **Next:** what still opens the away card is `trust` (the City's Test of Trust as its own order) and the campaign
  fights. `trust` is the last screen of step 9 the campaign reaches; step 10 follows it.

**9r. The Test of Trust — done (2026-10-28).** No mockup: it is the Bankers' board the bank's JOBS tab already draws.
A `trust` order (pygame's `App._open_trust_offer`, `TrustScreen` alone) opens a hub with that one tab
(`hub_session.HUBS["trust"]`), Elysia in the header. Tests: `tests/test_web_hub.py` (the one tab, the keeper, the
job taken, back to the map); the map's tests of the away card now enter the arena, which still opens it.

- **Step 9 is closed.** What opens the away card now is only the campaign fights (the arena, the hunt, the
  searches' finds, the Ruins, the Nest, the Lair, the skirmish, the Wildfire's fights, the forced fights after
  their talk). They are step 10's seam: `app_battle` hands the battle to `BattleSession` and settles it through
  `campaign.absorb_battle`, then `ReportSession` plays the aftermath.

### 10. The swap — in progress

Too big for one session, so it is cut as step 9 was: first the campaign's fights, family by family,
then the title and the draft, then the swap itself.

**10a. The forced fights and the Claim's — done (2026-10-28).** `campaign_fight.py` is the seam
`app_battle` was: `forced_fight` builds the fight as `App._start_forced_battle` does (after the talk with
its `Opening`, or straight from the map's seal when nobody in the pack speaks), `claim_fight` the
Claim's CLEAR and SWEEP as `_start_claim_battle`; `_enter` saves the snapshot before it, writes the
play log's combat log, binds the bestiary and opens `BattleSession` with a `then`. A campaign fight's
state says `campaign` and its header is the place and the event (`meta.sub`); once it is over the end
card's Go on posts `done`, which settles it: `campaign.absorb_battle`, the `fight` row of the play log,
`group.pending` cleared and `forced.resolve` (or the Claim's stage), the save, then `ReportSession`,
whose chain ends on the map through the clock (`_to_map`), or on the wiped map. The away card now
only stands for the fights still left; it lost its forced-fight forms. A window closed mid-fight
leaves the fight due on the map, as in pygame.

- Left out: the map's auto-resolve (`autowin_ambush`, pygame's Monte Carlo) has no button in the
  browser yet.
- Tests: `tests/test_web_campaign_fight.py` (the seal with nobody to talk to opens the board, the
  snapshot, `done` refused before the end, the report and back to the map with the fight gone from
  the save; a whole fight played by the AI on both sides through the session; a talk lost into a
  fight keeps its opening; the Claim's fight won moves the stage; a lab fight has nothing after it);
  the old away-card tests in `test_web_map.py`, `test_web_talk.py`, `test_web_hub.py` now land on the
  board. The end card and the report after it were looked at in headless Edge at 1920x1080.
- **Next (10b):** the arena (`_start_battle` with a `Bout`: the entry fee, a boss's lines, the purse
  on the report, Adelio's and the Ribbit Brothers' recruit offers, the title defense). Then the hunt
  (its ambushes and the ox chase), the searches' finds (the Ruins, the Nest, the Lair), the errands'
  fights (the battlefield, the necromancer, the Wildfire's camp and fortress), then the title screen
  and the draft, then the swap below.

**10b. The arena — done (2026-10-28).** `arena_session.py` (screen `arena`) is pygame's `SquadScreen` in arena
mode as `App._open_arena` opens it: the bouts in the arena's story (the Scrapper and the champion, then the Games
and the Ribbit Brothers until they fall), who fights (a band that fits the bout is picked whole, a smaller bout
trims the overflow, a member collapsed from hunger cannot be picked) and the stake (a head, out of the whole band's
purses, richest first). STAKE AND FIGHT builds the bout through `matchup.build`; the guild's first bout against a
boss opens the boss's lines first (`dialogue_session.boss_talk`, `guild.boss_talks_seen`). The bout is a campaign
fight: `campaign_fight._enter` takes the picked `squad`, the `offer` (to `absorb_battle` and the report's purse)
and `after`, where the report ends. Settled, it marks `obj_arena_bout`; a title note with no purse goes to the
map's notices. Won against Adelio (not yet in the roster) or the Ribbit Brothers, the report ends on the offer to
recruit them (`AdelioPromptScreen`, `RibbitPromptScreen`), whose yes opens the Tavern's RECRUIT with them as the
only strangers (`hub_session.HUBS["pit_recruit"]`, `HubSession(candidates=...)`, `TavernTab(candidates=...)`).
A due title defense goes straight to the board, the champion alone, not to the death, as
`App._start_title_defense`, but only when the champion stands in the band that entered (pygame takes them from
anywhere); otherwise the bouts say who must come and by when.

- The client follows the talk's frame: the pit master and the bouts on paper, the band's cards on leather, the
  stake's ledger and the seal at its foot; the offer is a paper card. No mockup: it is the squad picker the other
  screens already drew in parts (the band's cards, the keeper, the seal).
- Left out: a tutorial card (no web screen has one yet).
- Tests: `tests/test_web_arena.py` (the bouts by the guild's deeds, the band picked whole and the stake a head, the
  cap, the trim and the unfit, a stake the band cannot pay, a Scrapper won to the purse and the map with the
  snapshot and the objective, a bout lost with no purse, the champion's lines once, his fall and the offer into
  RECRUIT with Adelio alone, the offer turned down, the defense with the champion here and elsewhere, the routing);
  the map's and the hub's away-card tests now enter the hunt. The bouts (the Pit, the Games with the Ribbit
  Brothers picked) and the offer were looked at in headless Edge at 1920x1080 on a copy of the day-70 save.
- **Next (10c):** the hunt (`app_hunt`: the Wilds' hunt for meat with its ambushes, the Biwolf, the ox chase), then
  the searches' finds (the Ruins, the Nest, the Lair), the errands' fights (the battlefield, the necromancer, the
  Wildfire's camp and fortress), then the title screen and the draft, then the swap below.

**10c. The hunt — done (2026-10-28).** `hunt_session.py` (screen `hunt`) is pygame's `HuntScreen` and `TrackScreen`
as `app_hunt` plays them, for the Wilds' `hunt` and the Ox Fields' `ox_hunt`: a band with a wagon first says who
minds it (`watch_screen`: someone must go in, one guard keeps it safe), then the quarry (meat or forage) and the
shift (the ox's shifts only as long as the daylight left), each stretch on the clock through
`MapSession.tick_outside` (the other bands keep in step, what falls due waits for the map), an ambush (the wolves,
the Ogre's goblins, the Biwolf after dark with the meat) or the ox's trail fought as a campaign fight
(`campaign_fight._enter` with the party as `squad` and an `after` that comes back to the hunt), won with hours left
to KEEP HUNTING or HEAD BACK, then the haul banked (`hunt.grant_haul`) and the wagon rolled for on the way out. A
member with a talent pick opens the talent tree and comes back to the hunt.

- One change from pygame: a hunt left before any hour was spent does not roll for the wagon (pygame rolls it even
  then). Like pygame, a hunt is never saved: a window closed mid-hunt drops it.
- Left out: the auto-resolve of an ambush (pygame's AUTO-WIN, its Monte Carlo); a tutorial card.
- The client is the arena's frame: the choices and the news on paper, the party on leather, a green seal to set out
  and a red one to fight. No mockup.
- Tests: `tests/test_web_hunt.py` (the quarry and the shift, a quiet shift banks the meat and returns to the map, an
  ambush to the board with the snapshot and back to the interlude, heading back, a lost ambush, the wagon's watch, an
  unguarded wagon lost and a guarded one kept, the ox by daylight only, the ox's chase is the player's and his fall
  closes the job, the talents and back, an order due on the clock, the routing); the away-card tests now enter the
  Ancient Ruins. The watch, the setup, the ambush and the haul were looked at in headless Edge at 1920x1080.
- **Next (10d):** the searches' finds (the Ancient Ruins, the Serpent's Nest, the Dragon's Lair: each its own
  scenario behind the wagon's watch), then the errands' fights (the battlefield, the necromancer, the Wildfire's
  camp and fortress), then the title screen and the draft, then the swap below.

**10d. The searches' finds — done (2026-10-28).** `campaign_fight.delve` is `App._enter_ancient_ruins`,
`_enter_nest` and `_enter_lair`: the Ancient Ruins, the Serpent's Nest and the Dragon's Lair (`DELVES`: the seal's
label, the header, what waits inside, the scenario), in the dark, lethal, the squad the aggressor; the Nest wants the
Snake Dragon alive while the Nature Coven's job is out; ruins with nothing left say so on the map. A band with a wagon
first opens `watch_session.py` (screen `watch`), pygame's `WatchScreen`: who goes in, who minds it, GO IN hands the
party to the place; the fight's settle rolls for a wagon left unguarded (`wagon_watch.leave_outside`). The hunt's
watch now reads the same `watch_state` / `toggle`. The Lair's patrol challenges and the withdraw were already the
battle session's.

- The client is the hunt's watch page on its own screen (`watch.css` imports `hunt.css`, with a darker ground).
- Left out: a tutorial card.
- Tests: `tests/test_web_delve.py` (each place straight in with no wagon, in the dark with the snapshot; the watch
  and the guards out of the fight; back changes nothing; an unguarded wagon lost and a guarded one kept; the Ruins
  remember and once empty lie silent; the Nest's dragon wanted alive; a wipe; the routing); the away-card tests now
  enter the skirmish. The watch was looked at in headless Edge at 1920x1080.
- **Next (10e):** the errands' fights (the skirmish: the battlefield and the necromancer; the Wildfire's camp and
  fortress), each behind the same `WatchSession`; then the title screen and the draft, then the swap below.

**10e. The errands' fights — done (2026-10-28).** `campaign_fight.errand` is `App._enter_skirmish` and
`_enter_wildfire_fight`: `skirmish` at the Battlefield is the Faith Order's Mercy at the Front (four Ledger Hold
soldiers at the band's side, played by the AI) or, once that errand is out, the necromancer's night (three sides);
`camp_fight` is a Wildfire camp, `ogre_fight` the Great Focus or the hostile fortress left standing. Each goes behind
the same `WatchSession` (`_watched`, which `delve` uses too) and is settled as `_battle_end` does: the errand
(`settle_battlefield` with the soldiers lost, `settle_necromancer` on his fall, with the deed's notice) or
`wildfire.settle_fight`; a band with nothing to fight there is back on the map. With that, every order the campaign
reaches has a browser screen: `AwaySession` and `screens/away/` are gone, and `MapSession._enter` raises on a kind
it cannot play (`hub_session.opens_hub` went with it: no node has a stable without a shop).

- The client is unchanged: the watch and the board already drew all of it (the allies and a third side came with the
  lab fights).
- Left out: a tutorial card.
- Tests: `tests/test_web_errand.py` (every activity kind of `App._ACTIVITY_OPENERS` has a screen; the skirmish with
  the soldiers and the snapshot; every soldier home is the deed, one lost fails it even on a win; the necromancer's
  night and his fall; no errand, back on the map; the wagon's watch; a camp, a cleared camp, a camp lost; the Great
  Focus and the standing fortress); the map's away-card tests now open the Bank, and a missed Wildfire talk lands on
  the board (`test_web_talk.py`).
- **Next (10f):** the title screen and the draft (`start_screen`, the draft and `vocation_screen`, the saves
  browser), so a new guild starts in the browser; then the swap below.

**10z. The swap.** The campaign hook is the seam between `app_battle` and `BattleScreen`: the campaign
hands the web session a battle and settles it through `campaign.absorb_battle` as
today. A window cannot mix pygame and the browser, so the swap is one move once the
whole loop (title, map, hub, battle, report, map) runs in the browser:

- the web front-end becomes `python -m gartok`;
- pygame and `ui/` are retired;
- `AGENTS.md` (the `ui/` rules) and `gartok/ui/README.md` are rewritten for the new layer.

**Done when:** a new guild plays its first ten days with no pygame window.
