# Web front-end: keep the Python core, replace the pygame presentation

**Status:** the battle spike is built and the author's verdict (2026-10-23) is go: better
than pygame already, but with a lot left to fix in colour, fluidity and light. Next is
the battle polish below; the map waits until the battle is good.

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

## Art direction

- **The table.** The game looks like the RPG's physical material (an engraved bestiary,
  a map inked by hand, character sheets) laid on a dark wooden table. The target is
  [references/battle_mockup/](references/battle_mockup/) (`battle.html`,
  `battle_mockup.png`).
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
- **`gartok/web/battle_session.py`** runs one fight: the turn flow `BattleScreen` runs,
  and the board as the side knows it, as JSON (`state`, `act`, `advance`, `route`,
  `aim`).
- **`gartok/web/server.py`** is the JSON API over the session, plus the client's files
  and the game's art.
- **`gartok/web/client/`** is the screen: `board.js` paints the board and `battle.js`
  handles input, tokens, panels and effects.
- **Launch:** `python -m gartok.web --fight <lab fight>`.
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

## Next steps, in order

### 1. Fluidity

`ai.take_turn` resolves a unit's whole turn in one call, so the client sees only the
result: tokens jump in a straight line and the blow has already landed.

- The session records each step of an AI turn (each move with its path, each action
  with its target) and returns them in order.
- The client animates them one at a time:
  - the token walks the path cell by cell;
  - the strike lands with its number;
  - a short pause between steps.

  The player's own moves walk the path too.
- Redraw only what changed: the static layer is already cached; the fog and light layer
  is redrawn only when sight changes.
- No rule changes. Test: the steps of a turn add up to the same end state.

### 2. Light

Today the light is one flat level per cell, blurred. It still reads as blocky, flat in
daylight, and too weak in the dark.

- The server also sends the light sources the side can see (torches, fire, lit units)
  and the walls around them.
- The client draws real light: a visibility polygon from each source, cut by the walls,
  with a warm radial falloff.
- Darkness gets weight indoors. Daylight gets a direction (a soft shadow on each wall)
  instead of flat paper.
- The rule stays in Python: the client paints light only inside the cells
  `visible_cells` already allows.

### 3. Colour

Floor, walls, blank paper and remembered ground sit in nearly the same beige, and the
UI is warm on warm.

- Fix one value scale and hold every layer to it:
  - unseen paper: light;
  - floor: mid;
  - walls: dark;
  - tokens: the highest contrast.
- Add a cooler accent in the chrome so it does not melt into the board.
- Tint each place's floor from one texture: arena warm, cave cool, grass green-grey.
- Generate the art still missing with Gemini, anchored on the reference portraits:
  - a wall sheet;
  - UI frames (9-slice);
  - outdoor floors (earth, grass, sand).

### 4. Parity with the pygame battle

Each of these exists in pygame and is missing here:

- zoom and pan on big boards;
- the challenge dialogue (`talk_handler`), where the AI answers for now;
- placing your own flag and traps, auto-placed for now;
- the Floating Disk height prompt;
- the two-player hand-over;
- the crit banner and sound;
- the combat-log sink (`battle.record_to`).

### 5. Speed on big boards

Profile the Necromancer fight. The likely costs are `visible_cells` and
`cell_levels` over every cell on every request. Cache them per step instead of per
request.

### 6. Migration

pygame stays the shipping front-end until the web one covers the whole loop: a window
cannot mix the two. The order:

1. battle (steps 1-5)
2. map
3. hub screens
4. the rest

The campaign hook is the seam between `app_battle` and `BattleScreen`: the campaign hands
the web session a battle, and settles it through `campaign.absorb_battle` as today. When
the swap happens, `AGENTS.md` (the `ui/` rules) and `gartok/ui/README.md` are rewritten
for the new layer, and `ui/` is retired.
