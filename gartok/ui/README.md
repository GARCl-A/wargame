# gartok/ui — how to build a screen

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
   proportional-with-clamp, the way `map_panel.draw_minimap` does.
7. **Reuse before you draw.** Buttons, panels, modals, tabs, tooltips and
   scrollbars already exist in `primitives.py`. A second button style is a bug.

## Components

| Module | What it is |
|---|---|
| `tokens.py` | `T` palette / spacing / font sizes, `fonts()`, `mix()` |
| `primitives.py` | `panel`, `box`, `modal_card`, `draw_card`, `draw_button`, `text` / `caps` / `wrap` / `ellipsize`, `tabs`, `scrollbar`, `draw_tooltip`, `token_badge`, `section`, `header`, `footer_bar`, `Stack` (vertical cursor), `pips` |
| `banner.py` | the guild's banner colour (`BANNER_COLORS`, `player_color()`, `set_player_color`) -- the one run-wide presentation state |
| `board_style.py` | the battle board's palette, `battle_layout`, `BoardView` (pan/zoom camera) |
| `camera.py` | `MapCamera`: pan / zoom around a screen-space centre |
| `map_panel.py` | the MAP zone: `draw_map`, `draw_minimap`, node glyphs, pawns |
| `command_bar.py` | the COMMAND zone: clock, alerts, headline stats |
| `roster_panel.py` | the ROSTER zone: one card per group, events timeline |
| `inspector_panel.py` | the INSPECTOR zone: selected band, status, available orders |
| `quest_panel.py` | active-mission cards with deadline and progress |
| `guild_roster.py` | the guild roster: filter pills, band accordions, member cards with status pills |
| `member_panel.py` | the guild member sheet, one `draw_*` per block (vitals, weapon, load, tracks, roles) |
| `guild_panel.py` | the guild overview: fame, group slots, each group's task and warnings, holdings |
| `reputation_panel.py` | faction cards (deeds, unlocks) in as many columns as fit |
| `combat_card.py` | unit cards for recruit / squad lists and party rows |
| `sheet_card.py` | the character sheet at three densities |
| `draft_panel.py` | the founding draft: pool candidate card, squad rail, commission modal |
| `loadout_panel.py` | bag / cargo / shop pieces (rail, column, container, send menu) |
| `market_panel.py` | the market's vendor shelf: category tabs, stock list and drag ghost |
| `intro_card.py` | the centred, veiled card (title, paragraphs, optional brass note, one button) used by every tutorial card |
| `board_render.py` | the battle board: terrain, props, unit tokens/bodies, flags and tactical overlay |
| `battle_panel.py` | the battle screen chrome: initiative strip, side panel cards/actions, and log well |
| `mission_offer_screen.py` | base class for city NPC screens with one active job |

## Adding to the kit

New component: one module, one zone. Write it against rules 5 and 6, give it a
docstring that says what the data dicts contain (the existing panels are the
template), and add a row above. If two screens would draw the same thing, it
belongs here, not in either screen.
