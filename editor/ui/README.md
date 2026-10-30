# editor/ui — how to build a screen

**pygame is the Editor's alone** (`python -m editor`): this kit is read only by the Editor's
screens and the combat lab's fights. The game is the web client (`gartok/web/client/`); do not add a
pygame screen for it.

The war-table kit: "steel desk + paper map". Chrome is dark steel, the world is
paper laid on the table, and brass / blood / green are the only things that
glow. Read this before adding or changing anything that draws.

Every screen is built on this kit; the old `theme.py` ramp and its `Fonts`
bundle are gone. Screens take the `fonts()` dict as their constructor argument.

## Rules

1. **Colours come from `T` (`tokens.py`).** No new RGB tuples in drawing code.
   If a shade is missing, add it to `T` with a name that says what it is for,
   not what it looks like. Blend with `tokens.mix(a, b, t)`.
2. **Colour is state, not decoration.** Surfaces, lines and neutral text stay
   muted (`STEEL*`, `TX*`, `PAPER*`, `INK*`). `BRASS` = focus / primary,
   `BLOOD` = danger / shortage, `GREEN` = safe / done. A screen that is
   colourful at rest has spent its signal.
3. **Spacing is a multiple of `T.S` (8).** Margins, paddings, gaps and card
   sizes are `T.S * n`. Fixed small offsets (1-2 px borders, glyph nudges) are
   fine.
4. **Type comes from `tokens.fonts()`**, a cached dict (`micro`, `body`,
   `bodyb`, `name`, `head`, `titleb`, `big`, ...). Sizes are the `T.F_*`
   constants. Don't call `pygame.font.SysFont` in a screen.
5. **One concern per component, data in, rects out.** A component is
   `draw_x(surf, F, rect, ...data, mpos)`:
   - `F` is the fonts dict, `rect` is the area it owns, `mpos` drives hover.
   - Data is plain dicts / tuples / lists. Never a `Group`, `Node`, `Unit` or
     any other domain object -- the screen adapts its model into that shape.
   - It returns the hit rects the caller needs for clicks (see
     `draw_roster`, `draw_inspector`).
6. **No module globals, no fixed pixel panel sizes.** Lay out relative to the
   rect you were given. For anything window-size-dependent use
   proportional-with-clamp.
7. **Reuse before you draw.** Buttons, panels, modals, tabs, tooltips and
   scrollbars already exist in `primitives.py`. A second button style is a bug.

## Components

| Module | What it is |
|---|---|
| `tokens.py` | `T` palette / spacing / font sizes, `fonts()`, `mix()` |
| `primitives.py` | `panel`, `box`, `modal_card`, `draw_card`, `draw_button`, `text` / `caps` / `wrap` / `ellipsize` / `with_caret`, `tabs`, `scrollbar`, `draw_tooltip`, `token_badge`, `section`, `header`, `footer_bar`, `Stack` (vertical cursor), `pips` |
| `item_icons.py` | item silhouettes drawn in code (`draw_item_icon`: ~50 kinds, one generator each, a `wagon` for the Stables; `gartok/item_icon.py` maps items and the six vocations to them) |
| `banner.py` | the guild's banner colour (`BANNER_COLORS`, `player_color()`, `set_player_color`) -- the one run-wide presentation state |
| `board_style.py` | the battle board's palette (each place's floor in `FLOOR_STYLES`), `battle_layout`, `BoardView` (pan/zoom camera) |
| `floors.py` | each place's floor (flagstones, Arena sand and stone, grass and trees, packed earth, cobbles, cave rock): the board painted once at `TEX` px a cell, cached, and scaled to the view (`blit_board`); `ground` is the editor's; a scenario names its `floor`, a node or an authored map may override it |
| `inspector_panel.py` | the INSPECTOR zone: selected band, status, available orders |
| `sheet_card.py` | the character sheet at three densities |
| `foe_panel.py` | what a side knows of a foe: its visible traits and the fields Intelligence opened, `?` for the rest |
| `load_meter.py` | what a body carries, the one way every screen shows it: a bar as long as `carry_max` with a tick at `carry_normal`, green / amber (slowed) / blood (full), the figure always `kg / max` |
| `loadout_panel.py` | bag / cargo pieces (rail, column, send menu) |
| `board_render.py` | the battle board: terrain (the floor from `floors.py`, then pits, water, fire, ropes), props (a `corpse` is a grey disc with a cross), unit tokens on a side plate (disc for the squad and allies, diamond for foes; the banner is only a pennant) / bodies, flags and tactical overlay |
| `battle_panel.py` | the battle screen chrome: initiative strip, side panel cards/actions, log well, and the crit banner across the board |
| `lab_panel.py` | the combat lab setup screen: benchmark fight list, level/size steppers, controller toggles |

## Adding to the kit

New component: one module, one zone. Write it against rules 5 and 6, give it a
docstring that says what the data dicts contain (the existing panels are the
template), and add a row above. If two screens would draw the same thing, it
belongs here, not in either screen.
