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
| `item_icons.py` | item silhouettes drawn in code (`draw_item_icon`: ~50 kinds, one generator each, a `wagon` for the Stables; `gartok/item_icon.py` maps items and the six vocations to them) |
| `hscroll.py` | `ColumnScroll`: sideways scroll over a row of equal columns (`fit`, `wheel`, `hint`, `click`) |
| `banner.py` | the guild's banner colour (`BANNER_COLORS`, `player_color()`, `set_player_color`) -- the one run-wide presentation state |
| `board_style.py` | the battle board's palette, `battle_layout`, `BoardView` (pan/zoom camera) |
| `camera.py` | `MapCamera`: pan / zoom around a screen-space centre |
| `map_panel.py` | the MAP zone: `draw_map`, `draw_minimap`, node glyphs, pawns, `place_labels` (names that overlap neither each other nor a mark; one with no room waits for the hover, the selected node and where a band stands always show) |
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
| `foe_panel.py` | what a side knows of a foe: its visible traits and the fields Intelligence opened, `?` for the rest |
| `vendor_panel.py` | a shop's keeper in the screen header: the portrait medallion and a name line |
| `hub_frame.py` | the hub screens' frame: `hub_layout`, the keeper header with its cards, the tab row, the footer, `hub_button`; the `hub_*` fonts (bigger, serif small caps for names via `primitives.small_caps`) |
| `hub_body.py` | a hub tab's body in the shop's type: `draw_panel` (serif small-caps title, an aside, the head rule), `draw_person` (portrait, name, a line, chips, a status), `draw_offer` (the shelf's row: icon, name, a line, price, buttons), `draw_chip`, `draw_toggle`, `draw_bar`, `draw_facts` (label / value rows), `draw_section` |
| `shop_shelf.py` | a hub's FOR SALE panel: category chips, the shelf rows with their steppers, the cart / sell / auto-sell footer |
| `hub_party.py` | a party member as a hub card (`member_card`, same contract as `loadout_panel.column`): load bar, the slots two by two, the pack, a drop area |
| `initiation_panel.py` | a sanctuary's initiation: the school's terms, one row per member with where they stand (or why they cannot), the begin / leave footer |
| `party_panel.py` | the figures on a party row (HP, AC, load, rations, work-XP bar) and the party's total load |
| `draft_panel.py` | the founding draft: pool candidate card, squad rail, commission modal; the founding screen (the banner on a shield beside the name, colour and emblem, one card per leader candidate with portrait, recruits and attributes) and `draw_shield` |
| `loadout_panel.py` | bag / cargo / shop pieces (rail, column, container, send menu) |
| `market_panel.py` | the market's drag ghost (the shelf itself is `shop_shelf.py`) |
| `intro_card.py` | the centred, veiled card (title, paragraphs, optional brass note, one button) used by every tutorial card |
| `dialogue_panel.py` | the talk before a fight: the foe's leader and line, who speaks, the answers with their odds (a closed one says why), then the result and its button (with no answers, as an arena boss's line, the speakers go too); one line each when space is short |
| `turn_card.py` | the group hand-over card: band tag, name, node, what is about to open, the crew, one button (blood for a forced fight) |
| `board_render.py` | the battle board: terrain, props (a `corpse` is a grey disc with a cross), unit tokens on a side plate (disc for the squad and allies, diamond for foes; the banner is only a pennant) / bodies, flags and tactical overlay |
| `aftermath_panel.py` | after a fight: the memorial card, the after-action report (squad rows with XP bars, takedowns, deeds), the level-up card with its stamp and climbing numbers |
| `battle_panel.py` | the battle screen chrome: initiative strip, side panel cards/actions, log well, and the crit banner across the board |
| `lab_panel.py` | the combat lab setup screen: benchmark fight list, level/size steppers, controller toggles |
| `medic_panel.py` | the Apothecary's Medic tab: party treatment rows, bill breakdown, quick treat / admit actions |
| `vocation_panel.py` | the founding vocation picker: six vocation cards with race icons and guild perk |
| `mission_offer_screen.py` | base class for NPC job boards: lists every job the giver has (`get_templates`), scrolls when they do not fit |

## Adding to the kit

New component: one module, one zone. Write it against rules 5 and 6, give it a
docstring that says what the data dicts contain (the existing panels are the
template), and add a row above. If two screens would draw the same thing, it
belongs here, not in either screen.
