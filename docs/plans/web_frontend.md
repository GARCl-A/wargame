# Web front-end: keep the Python core, replace the pygame presentation

**Status (2026-10-29):** the game is in the browser. `python main.py` opens the title; every screen the
campaign reaches (the map, every hub tab, the guild's sheet, the talk, the fights, the report, the talents,
the title, the draft, the settings, the wiki) is a web screen, and `gartok.web.server` loads with pygame
blocked. The pygame campaign is gone; only the Editor (`python main.py --editor`) still opens a pygame window.

What is left is below, under **What is left**. The record of how each step was built (steps 1 to 10,
2026-10-23 to 2026-10-29) is in git: `git log -p -- docs/plans/web_frontend.md`.

## How to continue

"Seguir com plano de ui" means: take the first item under **What is left** whose inputs exist, do only
that item, meet its **Done when**, commit, then delete it from this file (one line in the commit says
what changed for the items after it). One item per session. Start from this file, not from exploring the
code.

## Rules for new work

### pygame is abandoned (since 2026-10-28)

- No new pygame screen, no pygame change for a new feature, no rewiring a pygame screen onto a rule moved
  out of it.
- When a screen's rules move out, the screen, its `*_draw` mixin and the tests that only test it are
  deleted in the same commit. A test that checked a rule through a screen moves onto the core module or
  the web session, only if nothing else covers the rule.

### A screen is a session, a client folder and a rules module

- **Rules** live in a core module with no pygame (a *desk*: `trade.Counter`, `workbench.Bench`,
  `guild_sheet.GuildSheet`, `dialogue.Talk`, `spoils.Spoils` ...). A test loads it with pygame blocked.
- **The server half** is a `web/session.Session`: a `screen` id, `state`, its verbs, `tutorial_key()` and
  `sheet_units` (who its `sheet` verb may open). It holds the desk; it never borrows a method off a screen.
  The server routes `/api/<screen>/<verb>` to the open session and refuses another screen's verbs. A verb
  that changes screen sets `game.session`; the client reloads on it.
- **The client half** is `client/screens/<id>/`, with its files named in `SCREENS` in `shell.js`. A
  screen's scripts declare top-level names, so two scripts of one page must not share one (a test checks
  it). Shared pieces live in the shell: `$`, `api`, `esc`, `face`, `Sound`, `Tutorial`, `Sheet` (the
  member's book as a modal, opened by any portrait marked `data-sheet`); what two screens draw is in
  `kit.js` / `kit.css`, one function each on plain data (`Kit.item`, `Kit.column`, `Kit.purse`, `Kit.stepper`,
  `ico`, `money`, `plural`, `kg`, `stagePoint`, `popAt`, `dropMarker`). A piece a second screen needs moves
  there; a screen never keeps its own copy (a test checks the helpers).
- **Every hover is the game's tooltip** (`Tip` in `kit.js`), never the browser's `title` (a test checks it):
  `${tip(text)}` on the element, `tip(text, "item")` for an item's name over its lines,
  `tip(text, "sum")` for a breakdown (a title, `label: value` rows, `= total`).
- **The server filters** fog, sight and intel: the client never gets what the side does not know (the
  rule `ai.py` lives by, `intel.known_fields`).
- **A new screen has a tutorial card:** `tutorial_key()` plus a `tutorial.<id>` block in
  `locales/en.json`. The shell puts the `?` at the end of the screen's `#top`.

### How a step is checked

- **Tests first**, in pytest through the API (`tests/test_web_*.py`).
- **Screenshots at milestones**, only when the step is about the look: headless Edge at 1920x1080 on a copy
  of a real save (the day-70 save `35d38388` is the usual one); clicks and drags driven over the DevTools
  protocol when they matter.
- **A new family of screens gets a mockup first**, one HTML page at 1920x1080 with its PNG in
  `references/<family>_mockup/`, approved by the author before any code. Its other screens follow without
  one.

### Art direction

- **The table.** The game looks like the RPG's own material (an engraved bestiary, a map inked by hand,
  character sheets) laid on a dark wooden table.
- **Paper is for what you read, leather is for what you act on.** The board, the bestiary, a shelf, a
  charter are paper; panels of people and packs, the purse and the buttons are dark leather and brass. A
  dragged ware is a paper slip. End Turn and a screen's main action are a wax seal.
- **Colour is state:** blue your side, blood red the foe, brass the focus (the active unit, the chosen
  action), cool verdigris for idle edges, labels and plates.
- **Fog of war** reads as a map would: never seen is blank paper (a margin note or sound rings for what is
  only heard), seen before is a sepia wash, in sight is lit.
- **Type:** running text is `--read` (EB Garamond) at 16px or more; IM Fell English is a voice (a keeper's
  line, a dialogue, a flavour line), never under 17px; Cinzel is for names and labels. The map sheet's
  lettering is the chart's hand, drawn on the canvas.
- **The art is not drawn in code.** Code composes images (textures, frames, portraits) and draws only state
  (health, ranges, highlights): `pygame.draw` art is why the game looked like programmer art.
- **Gemini makes the art**, anchored on the four engraved portraits in [references/](references/) (Gnoll 10,
  Grippli 13, Kenku 4, Ogre 0). 2D engraving only: no isometric, 3D or pixel art.
- **No tile sheets.** A floor is one seamless texture across the cell lines, tinted per place in code, in a
  lower value band than the tokens (cream tokens vanished on a cream floor). Files go in
  `gartok/web/client/img/`; what is still missing is under Art in [backlog.md](backlog.md).
- **Item glyphs** are game-icons.net SVGs (CC BY 3.0) in `assets/icons/item/`, one per `item_icon` kind; a
  test fails for a kind with no file.
- **Fonts** ship in `gartok/web/client/fonts/`, never fetched at runtime.

### Layouts that hold

- **A hub tab:** the hub's cards from the tab's `hub_cards()`; the people or the thing you act on on leather
  at the left (660px, where the shop's shelf sits); the ledger of choices on paper at the right.
- **A shop or stash** shows every shopper's whole kit as a readable list, one leather column per pack
  (worn slots and pack rows, each with icon, name, quantity and weight; past four, the columns scroll
  sideways); the keeper is a strip across the top, not a column. Drag where it goes, or click and click;
  Shift picks several; right-click for the item's menu.
- **One band at a time** where items move: an item moves only between people in one place, so the screen
  shows one band and the rule shows on the table instead of as a refusal.
- **A pick that is for good** is click to pick, a button to confirm (the talent tree's TAKE).

### The mockups

Each folder under [references/](references/) is the approved look of a family, one frame per `?state=`:

| Folder | Family |
|---|---|
| `battle_mockup/` | the board |
| `menu_mockup/` | the title: the menu beside the last guild's charter on its map |
| `market_mockup/` | a shop: the keeper, the shelf, the packs |
| `map_mockup/` | the campaign map (`?state=split`, `merge`) |
| `sheets_mockup/` | the guild's sheet: members, bands, the guild, reputations |
| `dialogue_mockup/` | the talk before a fight |
| `report_mockup/` | after a fight: the fallen, the report, a level-up, the field, the purse |
| `talents_mockup/` | the talent tree: THE MAP and THE BRANCH |
| `draft_mockup/` | a new guild: vocation, pool, commission, charter |

## What is left

In order. The board items are tuned by eye, so each takes a mockup first.

### 1. The reading face is still too thin

On the REPUTATIONS tab a deed's name ("Buy Food") reads easily, its line ("Everyone eats...") takes an
effort though it is legible: EB Garamond at 16px is too light on the dark table. Try a heavier weight
(EB Garamond Medium or SemiBold ship as files), a little more size or a lighter ink on paper, compared
side by side on the reputations tab and one hub tab.

**Done when:** the author picks one from the screenshots and `--read` changes everywhere.

### 2. What else only pygame had: port or drop

Each needs the author's call (port, or drop and delete what is left of it):

- **The hand-over card between groups** (`group_turn`): today the map just moves to the next band with the
  news slip. Its tutorial card is still registered in `tutorial.py` and `locales/en.json`.
- **The vault read from the map** (pygame showed the strongbox's contents without going to the Bank).
- **The auto-win of an ambush or a hunt** (`autowin.py`, a Monte Carlo estimate; no button in the
  browser).

**Done when:** each is in the browser with its tests, or deleted from the code and its tutorial copy.

### 3. The tests the pygame cut lost

No web test covers these yet: the clock run while a screen is open (`MapSession.tick_outside`); a guild with
every member jailed waiting out the sentence on the map; the save refused mid-battle or mid-hunt; two due
screens draining one at a time; the REST row's wording (how many meals, the days of rations still short); a
trip cancelled to the next node.

**Done when:** each has a test through the web sessions.

### 4. The board, by eye

- **The fog.** Seen before (grey), never seen (paper) and seen but unlit (dark) stack into too many layers:
  it is hard to tell what is dark, what is fog and what is unknown (the playtests of 2026-10-21 and
  2026-10-28 both said it). Reopens the board's colour and light (`screens/battle/board.js`).
- **A pit reads as a pit, and how deep** (`board.py` elevation).
- **The bands walk on the map** from node to node along the edge, as tokens walk on the board.
- **A body and a fighter in one cell** (playtest 2026-10-30). A fighter may stand on a body (dying,
  stable or dead), and today the two tokens overlap so neither reads. Both must show, and what lies
  underneath must be readable: options for the mockup, e.g. the body drawn as a small fallen token or a
  mark on the floor under a standing token, a corner badge counting what is underneath, the cell's
  hover listing the stack.
- **The initiative shows each one's state** (playtest 2026-10-30): the green bar under a portrait
  does not say whether the fighter is dead, down and dying, or down and stable, and it must be obvious
  at a glance (the portrait greyed or struck, a mark per state).

**Done when:** a mockup of each is approved, then built and looked at at 1920x1080.

### 5. The Editor

The character creator, the map editor and the combat lab's menu are pygame (`editor_app`,
`editor_menu_screen`, `char_editor_screen`, `map_editor_screen`, `combat_lab_screen`, and `battle_screen` +
`battle_draw` for the lab's fights). The author's call: port them to the browser (the lab's fights already
run there: `python -m gartok.web --fight <lab fight>`), or keep the Editor as a pygame tool apart from the
game.

**Done when:** decided, and if ported, each Editor screen is a web screen and its pygame screen is deleted.

### 6. The retirement

Still importing pygame outside the Editor: `artwork.py` (tints and caches glyphs for pygame), `battle_fx.py`,
`icons.py`, `screen.py`, `text_field.py`, `sound.py` (inside `enable()` only), and the 16 modules of `ui/`.
They go with the last screen that reads them. Then `AGENTS.md` (the UI conventions, the `ui/` rows of the
module table, the pygame rule) and `gartok/ui/README.md` are rewritten for the web layer.

**Done when:** no module of the game imports pygame (or, if the Editor stays pygame, none outside it).

### Loose ends

Small, take them when passing by:

- The map's blocks still carry pygame's layout hints (`gap_before`, `height`); the web ignores them. They
  go with pygame.
- Not ported from pygame's guild sheet: the CARGO view (every stack of a band in one sorted table). The
  sheets mockup's "road ahead" card was never built.
- The talent tree draws a second requirement as a red dotted line, but no talent has one yet: check it the
  day one exists.
- At the battle's fit zoom the trees lose their leaf detail.
- A hunt is never saved: a window closed mid-hunt drops it (as pygame did).
- Shipping: the PyInstaller build (`build_exe.bat`, `GARTOK.spec`) carries `gartok/web/client` but was never
  run; pywebview or Tauri is decided at the end (pywebview's `pythonnet` is unverified on Python 3.14).
- Accepted, written down so nobody chases them: the fog and light layer is redrawn on every step (about
  5 ms); a wall the side never saw can stand between a light it sees and a cell in sight, which then reads a
  little brighter (no information leaks). If big boards ever feel slow, the next cost is `ai.take_turn`'s
  path fields (`battle._pf_field` / `board._dijkstra`).
