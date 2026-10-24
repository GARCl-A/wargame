# Web front-end: keep the Python core, replace the pygame presentation

**Status:** the battle spike is built and the author's verdict (2026-10-23) is go: better
than pygame already, but with a lot left to fix in colour, fluidity and light. Steps 1
to 3, 5 and 7 are done; step 4 (the art) is done as far as it got, so the next step is 6.

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

## Art direction

- **The table.** The game looks like the RPG's physical material (an engraved bestiary,
  a map inked by hand, character sheets) laid on a dark wooden table. The target is
  [references/battle_mockup/](references/battle_mockup/) (`battle.html`,
  `battle_mockup.png`). The same language off the board:
  [menu_mockup/](references/menu_mockup/) (the title screen: the menu beside the last
  guild's charter, laid on the map it has walked) and
  [market_mockup/](references/market_mockup/) (a shop: the keeper and the deal, the
  shelf as a ledger page, the shoppers' packs, a ware in hand). Each folder is one HTML
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
- **`gartok/web/map_session.py`** + `screens/map/` is the map as step 7 left it: the
  guild, the day and where each band stands, enough to prove the router.
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
- For step 6: torchlight still multiplies each lit cell toward warm brown, which turns
  the dungeon's grey back to brown round a torch; the remembered wash runs a canvas
  `filter` over the whole world on every state, the first thing to cache if a big
  board stutters. At the fit zoom the trees lose their leaf detail.

### 6. Battle: light — todo

Today the light is one flat level per cell, blurred. It reads as blocky, flat in
daylight, and too weak in the dark.

- The server also sends the light sources the side can see (torches, fire, lit units)
  and the walls around them.
- The client draws a visibility polygon from each source, cut by the walls, with a warm
  radial falloff. Darkness gets weight indoors; daylight gets a direction (a soft shadow
  on each wall).
- The rule stays in Python: the client paints light only inside the cells
  `visible_cells` allows.

**Done when:** the author approves the dungeon and the Necromancer fight at night. The
battle is then finished.

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

### 8. Map — todo

1. A mockup at 1920x1080 in `references/map_mockup/`, in the menu mockup's language
   (the map inked by hand), approved by the author before any code.
2. The screen on the shared base, on a real save: groups, orders, travel, the
   inspector, entering a node.

**Done when:** a pygame session's map loop (move a group, issue each order kind, advance
time, open a node) works in the browser, pygame's `map_screen.py` checked as the list.

### 9. Hubs, then the rest — todo

- **Hubs:** one tabbed frame (the `TabbedHubScreen` equivalent) with the shop as its
  first tab, following [market_mockup/](references/market_mockup/). Two things it
  leaves open: past about 12 rows (or 6 shoppers, or wagons and animals shopping along)
  the pack columns scroll sideways, as `ui/hscroll.ColumnScroll` does; the Smithy's
  weapons tab (damage, hands, size) is not yet tried in the 660px shelf. The other
  tabs (work, gathering, medic, jobs, initiation) then reuse the frame.
- **The rest, by family:** each family not yet mocked gets one mockup before its first
  screen (the guild and group sheets, the dialogues, the report after a fight); its
  other screens follow without one. The title screen follows the menu mockup.

**Done when:** every `*_screen.py` that the campaign can reach has a web screen.

### 10. The swap — todo

The campaign hook is the seam between `app_battle` and `BattleScreen`: the campaign
hands the web session a battle and settles it through `campaign.absorb_battle` as
today. A window cannot mix pygame and the browser, so the swap is one move once the
whole loop (title, map, hub, battle, report, map) runs in the browser:

- the web front-end becomes `python -m gartok`;
- pygame and `ui/` are retired;
- `AGENTS.md` (the `ui/` rules) and `gartok/ui/README.md` are rewritten for the new layer.

**Done when:** a new guild plays its first ten days with no pygame window.
