# Web client guide: how to build a screen

The game is a web client over a Python core: `python main.py` serves it and opens it in a browser window.
Read this before you add or change a screen. It is a standing guide (the rules, the look, the layouts that
hold); open work is in [plans/backlog.md](../plans/backlog.md), and how each step was built is in
`git log -p --follow -- docs/web_ui/web_client.md`.

The Editor (`python -m editor`) is the one pygame program left; leave it alone (see *Port the Editor* in the backlog).

## Rules

### No pygame in the game

- No new pygame screen, and no pygame change for a new feature. `gartok/` never imports pygame or `editor`
  (a test checks it).
- When a screen's rules move out of a pygame screen, delete the screen, its `*_draw` mixin and the tests that
  only test it in the same commit. A test that checked a rule through a screen moves onto the core module or
  the web session, only if nothing else covers the rule.

### A screen is a session, a client folder and a rules module

- **Rules** live in a core module with no pygame (a *desk*: `trade.Counter`, `workbench.Bench`,
  `guild_sheet.GuildSheet`, `dialogue.Talk`, `spoils.Spoils` ...). A test loads it with pygame blocked.
- **The server half** is a `web/session.Session`: a `screen` id, `state`, its verbs, `tutorial_key()` (and `tutorial_rows(key)` for a card's registry-drawn rows) and
  `sheet_units` (who its `sheet` verb may open). It holds the desk; it never borrows a method off a screen.
  The server routes `/api/<screen>/<verb>` to the open session and refuses another screen's verbs.
- **The client half** is `client/screens/<id>/`, with its files named in `SCREENS` in `shell.js`. A
  screen's scripts declare top-level names, so two scripts of one page must not share one (a test checks
  it).
- **Shared pieces are not copied.** The shell (`shell.js`) holds the helpers and the `Sheet` modal (the
  member's book, opened by any portrait marked `data-sheet`); what two screens draw is in `kit.js` /
  `kit.css`, one function each on plain data. Read their headers for the list. A piece a second screen
  needs moves there; a screen never keeps its own copy (a test checks the helpers).
- **Every hover is the game's tooltip** (`Tip` in `kit.js`), never the browser's `title` (a test checks it):
  `${tip(text)}` on the element, `tip(text, "item")` for an item's name over its lines,
  `tip(text, "sum")` for a breakdown (a title, `label: value` rows, `= total`).
- **The click is the shell's** (`Sound` in `shell.js`): it plays on whatever the styles mark clickable (a
  `pointer` or `zoom-in` cursor; `.off` and the open tab go back to `default`) and on a drag let go over a
  marked drop target, and an answer that is not ok plays the error cue. So a clickable element needs its
  cursor, `data-silent` keeps one quiet, and a screen plays only the cue its answer picks (`coins` when the
  purse moved, `level_up`), never `click`.
- **A new screen has a tutorial card:** recipe in `README.md`, *New tutorial card*.
- **A screen opens whole.** `#screen` is veiled until `settle()` in `shell.js` finds nothing left to wait for
  (answers in, fonts loaded, `<img>`s and CSS pictures decoded, capped at 2.5 s), then fades in; the tutorial
  card waits for `Shell.ready` and enters after it. A screen needs nothing for this, but a late `fetch` it fires
  outside `api()` is not waited for.

### How a screen is checked

- **Screenshots at milestones**, only when the step is about the look: headless Edge at 1920x1080 on a copy
  of a real late-game save; clicks and drags driven over the DevTools protocol when they matter.
- **A new family of screens gets a mockup first**, one HTML page at 1920x1080 with its PNG in
  `references/<family>_mockup/`, approved by the author before any code. Its other screens follow without
  one. Add the family to the table in *The mockups* (a test fails otherwise).

### Art direction

- **The table.** The game looks like the RPG's own material (an engraved bestiary, a map inked by hand,
  character sheets) laid on a dark wooden table.
- **Paper is for what you read, leather is for what you act on.** The board, the bestiary, a shelf, a
  charter are paper; panels of people and packs, the purse and the buttons are dark leather and brass. A
  dragged ware is a paper slip. End Turn and a screen's main action are a wax seal.
- **Colour is state:** blue your side, blood red the foe, brass the focus (the active unit, the chosen
  action), cool verdigris for idle edges, labels and plates.
- **Fog of war** (approved 2026-10-30, `battle_mockup/fog_b.png`): never seen is the dark table, empty
  (a margin note or sound rings for what is only heard); seen before is a pale paper survey with the walls
  inked; in sight is the real floor, warm where lit and cool and dim where not.
- **Type:** running text is `--read` (EB Garamond Medium, never italic) at 16px or more; IM Fell English is a voice (a keeper's
  line, a dialogue, a flavour line), never under 17px; Cinzel is for names and labels. The map sheet's
  lettering is the chart's hand, drawn on the canvas.
- **The art is not drawn in code.** Code composes images (textures, frames, portraits) and draws only state
  (health, ranges, highlights): `pygame.draw` art is why the game looked like programmer art.
- **How the art is made.** Gemini is the preferred generator: its results are the best. It is anchored on the
  four engraved portraits in [references/](references/) (Gnoll 10, Grippli 13, Kenku 4, Ogre 0), 2D
  engraving only: no isometric, 3D or pixel art. The portrait LoRA (`/gen-portrait`) is the fallback, and
  its results are weaker: the LoRA portraits in the game are provisional, candidates to be replaced. An
  agent does not generate art: it lists what is missing under Art in [plans/backlog.md](../plans/backlog.md)
  and asks the author. Save each Gemini prompt that works, with its reference images, in
  `docs/art/<name>_options/`.
- **No tile sheets.** A floor is one seamless texture across the cell lines, tinted per place in code, in a
  lower value band than the tokens (cream tokens vanished on a cream floor). Files go in
  `gartok/web/client/img/`.

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

Each folder under [references/](references/) is the approved look of a family, one frame per `?state=`
(a mockup page may hold more frames than the table names):

| Folder | Family |
|---|---|
| `battle_mockup/` | the board |
| `menu_mockup/` | the title: the menu beside the last guild's charter on its map |
| `market_mockup/` | a shop: the keeper, the shelf, the packs |
| `map_mockup/` | the campaign map |
| `sheets_mockup/` | the guild's sheet: members, bands, the guild, reputations |
| `dialogue_mockup/` | the talk before a fight |
| `report_mockup/` | after a fight: the fallen, the report, a level-up, the field, the purse |
| `talents_mockup/` | the talent tree: THE MAP and THE BRANCH |
| `draft_mockup/` | a new guild: vocation, pool, commission, charter |

## Known limits

Accepted, written down so nobody chases them:

- The fog and light layer is redrawn on every step; a wall the side never saw can stand between a light it
  sees and a cell in sight, which then reads a little brighter (no information leaks).
