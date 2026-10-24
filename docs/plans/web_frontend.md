# Web front-end: keep the Python core, replace the pygame presentation

**Status:** the battle spike is built and the author's verdict (2026-10-23) is go: better
than pygame already, but with a lot left to fix in colour, fluidity and light. Steps 1
to 3 and 5 to 8 are done; step 4 (the art) is done as far as it got. Step 9 is under way:
the hub frame and its shop tab are in; the other tabs come next.

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
  two other frames, `map_split.png` and `map_merge.png`). Each folder is one HTML
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
  `map.js` the rest) is the campaign map (step 8). **`away_session.py`** + `screens/away/`
  stands in for every screen the browser does not draw yet: it names where the band went
  and goes back to the map. A session holds its `game` (`Game.open`), so a verb can open
  another screen; its answer names the screen open and the client reloads on it.
- **`gartok/web/hub_session.py`** + `screens/hub/` (`hub.js` the frame, `shop.js` the shop tab) is a
  place's hub (step 9): the tabs pygame's hub shows for the same order, the keeper, the way back.
  `shop_tab.py` drives a headless `MarketScreen` (or `LibraryScreen`), as the map borrows pygame's
  reads. Item glyphs are game-icons.net SVGs in `assets/icons/item/`, one per `item_icon` kind
  (`item_icon.glyph`).
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

### 9. Hubs, then the rest — under way

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

### 10. The swap — todo

The campaign hook is the seam between `app_battle` and `BattleScreen`: the campaign
hands the web session a battle and settles it through `campaign.absorb_battle` as
today. A window cannot mix pygame and the browser, so the swap is one move once the
whole loop (title, map, hub, battle, report, map) runs in the browser:

- the web front-end becomes `python -m gartok`;
- pygame and `ui/` are retired;
- `AGENTS.md` (the `ui/` rules) and `gartok/ui/README.md` are rewritten for the new layer.

**Done when:** a new guild plays its first ten days with no pygame window.
