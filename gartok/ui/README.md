# gartok/ui — how to build a screen

The war-table kit: "steel desk + paper map". Chrome is dark steel, the world is
paper laid on the table, and brass / blood / green are the only things that
glow. Read this before adding or changing anything that draws.

`gartok/theme.py` is the legacy look. Don't add new usage; when you touch a
screen non-trivially, move it onto this kit. `tests/test_theme_budget.py` lists
the modules still on `theme` and fails on a new one; when you finish moving a
module, take it off that list. (`set_pointer` lives in `primitives.py` now.)

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
| `primitives.py` | `panel`, `modal_card`, `draw_card`, `draw_button`, `text` / `caps` / `wrap` / `ellipsize`, `tabs`, `scrollbar`, `draw_tooltip`, `token_badge`, `section`, `header`, `footer_bar` |
| `camera.py` | `MapCamera`: pan / zoom around a screen-space centre |
| `map_panel.py` | the MAP zone: `draw_map`, `draw_minimap`, node glyphs, pawns |
| `command_bar.py` | the COMMAND zone: clock, alerts, headline stats |
| `roster_panel.py` | the ROSTER zone: one card per group, events timeline |
| `inspector_panel.py` | the INSPECTOR zone: selected band, status, available orders |
| `quest_panel.py` | active-mission cards with deadline and progress |
| `guild_roster.py` | the guild roster: filter pills, band accordions, member cards with status pills |
| `member_panel.py` | the guild member sheet, one `draw_*` per block (vitals, weapon, load, tracks, roles) |
| `reputation_panel.py` | faction cards (deeds, unlocks) in as many columns as fit |
| `combat_card.py` | unit cards for recruit / squad lists and party rows |
| `sheet_card.py` | the character sheet at three densities |
| `loadout_panel.py` | bag / cargo / shop pieces (rail, column, container, send menu) |
| `mission_offer_screen.py` | base class for city NPC screens with one active job |

## Adding to the kit

New component: one module, one zone. Write it against rules 5 and 6, give it a
docstring that says what the data dicts contain (the existing panels are the
template), and add a row above. If two screens would draw the same thing, it
belongs here, not in either screen.
