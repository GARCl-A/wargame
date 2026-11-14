# Web client guide: how to build a screen

The game is a web client over a Python core: `python main.py` serves it and opens it in a browser window, and the
native client (`shell/`, Electron) shows the same page in a window of its own.
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
- **The server half** is a `web/session.Session`: a `screen` id, `state`, its verbs, `tutorial_key()` (`tutorial_rows(key)` for a card's registry-drawn rows, `tutorial_spot(key)` for the part of the screen it lights) and
  `sheet_units` (who its `sheet` verb may open). It holds the desk; it never borrows a method off a screen.
  The server routes `/api/<screen>/<verb>` to the open session and refuses another screen's verbs.
- **A refusal is a `ValueError`, the rest is a fault.** A verb refuses with `ValueError` (409, shown by the
  screen, or by the shell's toast when the screen has no `catch`). Any other exception is logged to
  `errors.jsonl` in the save folder, answered 500, and the game reloads its last save; the shell shows the
  card. A screen never catches a fault to hide it.
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
  purse moved, `level_up`), never `click`. The cues are decoded once into Web Audio buffers (an `<audio>`
  element reloads its file at every play), and the first press or key resumes the context.
- **The music is `Music` in `music.js`, in the host page.** `/` is `host.html`, which holds the music and the game
  in a frame (`/game`, the page `shell.js` runs in). A screen change reloads the frame, never the host, so a track
  plays through every screen without a cut; the game reaches it through its frame's parent (`enter(screen)` from `api()` the
  moment an answer names another screen, and at boot; `volume`; `poke()` on a press or key, which retries a start the
  browser refused before the first click; the app window and the native client open with the autoplay policy lifted, so only the default-browser fallback waits for a click). Files and timings are in `sound.py` (`MUSIC`, `MUSIC_SILENCE`, `MUSIC_FADE`),
  the volume is its own `music` setting. A radio on every screen but the fight: one of 4 tracks, 30 to 60 seconds of
  quiet, the next; in a fight one of 3 battle tracks at random, chained while the fight lasts. A change between the two
  fades the old one out and the new one in; leaving a fight starts with the quiet. The game opened on `/game` alone is
  silent of music. Closing the window is still the page's `bye` (the host sends it too).
- **Client text is a key:** a sentence a screen's script or HTML shows is `tr("ui.…")` / `data-t` (recipe in
  `README.md`), never a literal; the sentences a session sends are keys of their own (phase 3 of the translation plan).
- **A new screen has a tutorial card:** recipe in `README.md`, *New tutorial card*.
- **What happened goes in the guild's log** (`Guild.log`, `guild_log.py`, shown in the map's right column): a
  rule or a screen that makes a line the player would want to reread (a meal, a haul, a fight, a deed) writes
  it where it is born, with `Guild.log.record(lines, clock_seconds, kind, band)` or, on a screen,
  `MapSession.say(lines, kind, group)`, which also puts the lines in `notices` for the answer that asked.
  A line that only passes through (a tab reading back what its order said, `MapSession.spend`) is not written
  again, and an order's refusal is not a log line: it is the map's `news` toast.
- **Static files are revalidated, the API is never stored.** `/client` and `/assets` answer `no-cache` with an
  ETag (a content hash; a 304 when it matches), so a new build is never shadowed by an old copy and no one
  clears a cache; `/api` answers `no-store`. A test walks every static file for the header.
- **A screen opens whole.** `#screen` is veiled until `settle()` in `shell.js` finds nothing left to wait for
  (answers in, fonts loaded, `<img>`s and CSS pictures decoded, capped at 2.5 s), then fades in; the tutorial
  card waits for `Shell.ready` and enters after it. A screen needs nothing for this, but a late `fetch` it fires
  outside `api()` is not waited for.
  Every `api()` answer also decodes the `/assets/portraits` and `/assets/icons` URLs it names before it returns, so a
  screen that swaps its HTML on a verb (the report's stages) never paints new faces empty on a slow machine.
  `open()` asks for a screen's CSS, `screen.html` and scripts at once (the scripts download together and run in
  the order `SCREENS` lists them): a request that waits on another costs a round trip each, which adds up on a
  slow machine.

### How a screen is checked

- **The layout is measured, not eyed.** `tests/test_layout.py` opens the screen in a headless browser, in each
  language, and fails on a card that must be scrolled and on words cut, past their box, over each other or
  glued to the next (how to cover a screen: `tests/README.md`). A new screen joins its `SCREENS`.
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
- **Fog of war** (`battle_mockup/fog_b.png` of 2026-10-30, the remembered floor dropped on 2026-11-13): the
  brighter, the better known. In sight is the real floor, warm where lit and cool and dim where not; of what
  was seen before only the terrain (walls, pits, water) and the things remembered there stay, dark silhouettes below anything in sight;
  the rest is the dark table, flat and empty (a margin note or sound rings for what is only heard).
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
- **One press for every portrait.** A portrait is installed, then pressed: `python scripts/portrait_press.py`
  levels it to the pool's paper and ink and adds the same grain (a pressed file is marked and skipped, so
  running it over everything is safe). No portrait keeps a colour of its own.
- **No tile sheets.** A floor is one seamless texture across the cell lines, tinted per place in code, in a
  lower value band than the tokens (cream tokens vanished on a cream floor). Files go in
  `gartok/web/client/img/`.

### Marks on the board

- **A condition is a gem on the token's rim** (the table in web/condition_marks.py: icon + class ctl/hurt/mind/boon, control
  first; up to four, the last slot counts the rest) and a pip on its initiative coin. Things lying on a cell and
  bodies stacked under a fighter are two brass medallions with a count. **Hover opens only from a gem or a
  medallion, never from the token** (attacking always hovers the target): a gem opens the ledger (what each
  condition is and does), the items medallion the list, the bodies medallion the same list read-only. A click
  pins the ledger or the items list; a click on the bodies medallion opens the pile card, where the player picks
  who to stabilize or attack, and Pick up keeps its own pick list. Draw opens a card too (`#draw`): one row per drawable item in the
  pack, the blocked ones with their reason, then the stows, each showing what the hands hold afterwards.

### The dice

- **Every d20 the player may watch is a `rolls` record** (`Battle.rolled`, drained in `battle_session._events`
  and cut to what the side sees; the actor's id is null when the actor is not seen). `client/dice.js` +
  `dice.css` draw it: `Dice.roll(tray, rolls, {short, onStop, onVerdict})` throws the d20 onto the chronicle's
  tray (`#tray`, a wooden rim and a felt floor at the foot of the chronicle), turns it, stops it on the natural,
  and tints it green (hit), gold (natural 20), red (miss) or dark red (natural 1); on a hit the damage dice
  (`damage.each`, one die per die rolled) turn after it. The number over whoever acted (`17 +3 = 20` and the
  difficulty chip) is `battle.js:playRolls`, through `onStop` / `onVerdict`.
- **The difficulty chip** is a small shield with the number and its label, or, for a difficulty the side has not
  read (`dc == "?"`), a wax seal with the `uncertainty` glyph.
- **Timeline of a step** (`playSteps`): walk, the dice (awaited), then the board state and its floats; the HP bar and
  the damage number never come before the die stops. The player's own acts roll in full (about 0.55 s on a miss,
  0.85 s on a hit); what the player did not choose (a foe, a save) is the short throw, about 0.22 s. A click or a
  key snaps the dice to their result. The timing constants sit at the top of `dice.js`.
- **Dice outside combat** (`checks.py`): a rule that rolls on the player's own order (the tavern's pitch, a lock picked from the pack) puts a `Check` on `guild.table`; `server._json` drains it into the answer's `checks` field and `api()` in `shell.js` hands it to `Dice.table`, a small tray that slides in over whatever screen is open. Routines (an hour of scouting, ask-around, a repair) put nothing. The talk screen's d20 is the same `Dice` die (`Dice.spin`).
- **The decisive modifier is named** (`_decisive` in `actions/base.py`, `decisive` on the roll record): when a hit lands only because of one modifier, or a miss only because of one penalty, the number over the actor gets a small line ("Flank +2 made it") and the chronicle line a thicker edge. Never on a nat 20 or nat 1, never for a foe whose defence is unread (`dc "?"`), never when the roll had room to spare.
- **A thrown die is heard** (`dice` in `sound.py`, one of `die-throw-1..3` drawn, played by `Dice` when a die is thrown onto a tray, in a fight and out of one; silent when the `Dice` setting is off).
- **A blow moves the token** (`blow` in `battle.js`, at the verdict of a melee roll): the attacker lunges a third of a cell, a hit knocks the target back and flashes it, a critical shakes the sheet once; a fighter that drops tips over (`renderTokens`). They use the `translate` property so the tilt of a fallen token is left alone, and `prefers-reduced-motion` skips them.
- **The `Dice` setting** (`full` / `quick` / `off`, `Shell.dice`) and `prefers-reduced-motion` make the dice
  stopped and the wait none.

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
| `routines_mockup/` | the Book of routines and a group's routine: block editor, running, stopped |

## Known limits

Accepted, written down so nobody chases them:

- The fog and light layer is redrawn on every step; a wall the side never saw can stand between a light it
  sees and a cell in sight, which then reads a little brighter (no information leaks).
