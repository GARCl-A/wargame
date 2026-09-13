---
name: gartok-ui-redesign
description: "GARTOK Tactical's presentation layer — theme.py design system, fully procedural rendering, the screen contract"
metadata: 
  node_type: memory
  type: project
  originSessionId: e8c74a1e-914a-469b-9b88-6880aab3a82b
  modified: 2026-09-08T22:25:48.530Z
---

The presentation layer of GARTOK Tactical ([[gartok-tactical-project]]) was
rebuilt off the MVP look in Sep 2026 and now runs on a design system.

## Current state

- **`theme.py` is the design system** — one source of truth for looks:
  - `SP` spacing scale `(4,8,12,16,24,32)` → `SP1..SP6`. Never hard-code a gap.
  - surface ramp `SURFACE_0..4` + semantic colour roles (`INK`/`INK_DIM`/
    `INK_FAINT`, `ACCENT`, `DANGER`, `OK`, `WARN`, `INFO`, `PLAYER_C`/`ENEMY_C`/
    `NEUTRAL_C`). Old names kept as aliases.
  - `Fonts`: a weighted sans (title/heading/label/body/body_sm/body_bd) + a
    monospace (num_lg/num/mono/mono_sm) for numbers, dice and the log. Built once
    after `pygame.init()`.
  - layout constants (`TILE=48`, `MARGIN`, grid/panel/log rects, `WIN_W/WIN_H`).
  - helpers/widgets: `text()`, `tracked()`, `wrap_lines()`, `blit_block()`,
    `Stack`, `panel()`, `chip()`, `section()`, `pips()`, `token_badge()`.
- **Rendering is procedural with one exception** (Sep 2026): `artwork.py` loads
  the game-icons.net SVGs under `assets/icons/{body,hat,head}/`, rasterises each
  once at the size asked, tints it, and caches by `(category, name, px, colour)`.
  `theme.token_badge` (and the battle board / initiative tokens) now draw the
  unit's **race silhouette** — `artwork.RACE_ICON` maps race name → `head/*.svg`
  — with the board letter as fallback. `body/` + `hat/` are staged, unused.
  Assets reorganised: `assets/icons/` (loaded) vs `assets/dungeon/` (the
  orphaned tileset; `tileset.py` still orphaned). Icon categories under
  `assets/icons/`: `head/` (race tokens, loaded), `body/` + `hat/` (staged),
  and `action/` + `gui/` (game-icons.net "action" + "gui" packs, added Sep 2026,
  flattened from the nested `<pack>.svg/icons/ffffff/transparent/1x1/<author>/`
  download layout — used by talent-node icons on the level screen).
  `Unit.attack_bonus` →
  `(mod, attr)` base to-hit, shown on the guild weapon row + reused by
  `sheet_panel._to_hit`.
  The battle board is a two-tone checker + raised-stone walls
  with per-corner rounding; torches are drawn glows; `lighting.LightRenderer`
  paints the darkness layer with radial light holes. The world map
  (`map_screen`) is a cached terrain fill + carved roads + vector node glyphs +
  a gold guild marker + tooltip.
- **`app.py`: every scene is now `native`** (migrated Sep 2026 — the whole
  roster of screens carries `native = True`). The loop does
  `scene.mouse = pygame.mouse.get_pos()` (raw), dispatches raw events, and each
  frame just `window.fill(BG); scene.draw(window)`. The fixed-canvas +
  `smoothscale` letterbox path is **gone** (`_to_canvas` / `_present` /
  `_blit_scene` / `self.canvas` deleted). Nothing blurs on maximise now.
  Every screen's `draw` reads `W, H = screen.get_size()` (or `screen.get_width()`)
  and reflows; helper methods that need the size take `screen` and read it too.
  **`battle_screen` is the deliberate non-reflow case**: it keeps the fixed
  `TILE=48` composition, renders to `self._canvas` (`WIN_W×WIN_H`), and blits it
  **centred, unscaled** in the window — crisp, letterboxed with `BG`. Its
  `handle_event` / `draw` translate mouse by `self._offset` to canvas space.
  `WIN_W/WIN_H` (theme.py) are now just the opening window size + that canvas.
- **Screen contract**: `screen.Screen` is the base class — it folds `self.mouse`,
  the left-click → `self._click(pos)` dispatch and a no-op `update`. Every screen
  subclasses it and adds `draw(surface)` + its own `_click` (10 screens now,
`taverna_screen` added Sep 2026 for recruitment — candidate cards + party-member
picker, modelled on market/reward); the battle screen
  also overrides `handle_event` (keyboard) and `update` (AI timer). Shared game
  widget so far: `theme.token_badge` (the round unit token). The back/menu
  footer and the card grid are still per-screen — extract a widget when a third
  screen needs the exact same shape, not before.
- **Battle screen** extras: initiative strip above the grid, turn card with AP
  pips, icon+cost action buttons (`icons.py` — vector glyphs keyed by
  `Action.id`), collapsible inspect, colour-coded log, and a tactical overlay
  (reach / path preview / target rings) drawn **above** the lighting layer.
  Movement records the walked path (`unit.path` / `unit.last_path`); hovering a
  reachable cell previews the route with step cost.
- **`guild_screen`** — rebuilt master-detail (Sep 2026): a left column of
  compact member cards selects `self.member`; a right panel shows that member's
  loadout (stat chips + a carry bar in a left sub-column, MAOS/CORPO/MOCHILA
  slots in a wider right sub-column). Cross-member transfer = drag/drop an item
  onto another member's card (→ their pack); same-member = drop on the detail
  slots. `native = True`. A footer **MANAGE GEAR** button (`on_manage`,
  accent-bordered) opens the gear screen.

- **`gear_screen.py` — Manage Gear** (Sep 2026, `GearScreen(DragSelectMixin,
  LoadoutMoveMixin, Screen)`): the bulk-loadout view the guild screen's
  master-detail was bad at. A top toggle strip picks which roster members show as
  full side-by-side columns (HANDS/OFF/BODY/PACK); `self._cap` = columns that fit
  the window, extras stay selected-but-hidden. The hand/off/armour slots are drop
  zones; **anywhere else on a column drops into that member's pack** (the whole
  column `rect` is registered last as a `"pack"` zone, so the specific slots win
  on a hit; when carrying, the column border lights `INFO`). Drag/click/
  shift-click like the guild screen, **plus right-click an item → a "send to
  <member> / throw away" menu** (`self.menu`; `_open_menu`/`_menu_click`/
  `_draw_menu`, dismissed on any left-down). `native`; `on_back` → guild screen.
  Wired in `app._open_gear`; in the screen smoke test.

- **`dragselect.LoadoutMoveMixin`** (Sep 2026) — the member-loadout move core
  (`_slot_of`/`_item_at`/`_carried_names`/`_take`/`_fits_slot`/`_give_many` over
  a member's hand/offhand/armor/pack) extracted from `guild_screen` when
  `gear_screen` became the third consumer of that shape. Guild + gear mix it in
  (`class X(DragSelectMixin, LoadoutMoveMixin, Screen)`); the market screen
  tracks buy/sell too and keeps its own `_item_at`/`_take`. Also that cleanup:
  `theme.kg()` (weight string, was `_kg` in 4 screens) and `theme.ellipsize()`
  (clip-with-… , was `_fit` in guild+gear).

- **`level_screen` is a node graph** (Sep 2026, was a vertical list): per track,
  the module fn `_tree_layout(track)` places nodes by `requires` (parent = mean
  of children's columns, leaves take slots) into (column, depth) — tier-agnostic,
  deeper trees lay out the same (has a unit test). Each node is an icon tile (`talents.Talent.icon` = `"<cat>/<name>"`
  via `artwork.icon`), tinted by state (taken=OK / open=ACCENT pulse / locked=
  faint), tier badge top-left, check top-right, name below; orthogonal
  connectors under the tiles, coloured by the child's state, emerge below the
  parent's label. Hover pops a detail card (`_hover` → `_draw_tooltip`). Tree
  hangs high in the panel (0.32 bias) — empty room below = "the branch goes on".

- **`sheet_panel.draw_sheet()`** — a full read-only character-sheet modal
  (header, PV/CA/DM/DESLOC/INIC chips, 6 attrs + mods, an ATAQUE block with
  to-hit computed directly, damage, first-aid line, gear/carry/copper,
  languages, full racial ability). Any click closes it. Distinct from the
  text-only `sheet.character_sheet()` (used in the battle inspect panel).
  **`sheet_panel.SheetModalMixin`** (Sep 2026, 3rd consumer rule) folds the
  modal plumbing: `open_sheet(unit)` / `sheet_open` / `close_sheet_on_click()`
  (call first in the screen's click handler) / `draw_sheet_modal(surf, fonts)`
  (call last in `draw`) / `sheet_badge(surf, topright, fonts)` (the small "i"
  disc affordance on a card). Wraps the member in a throwaway `Combatant` (the
  sheet reads to-hit / ammo / hand state). Mixed into `GuildScreen` (opened by
  the detail-header "SHEET" pill), `SquadScreen` and `RewardScreen` (the card
  "i" disc). `guild_screen` was retrofitted onto it (dropped its own
  `self.detail` + `Combatant` import).

**How to apply:** new UI code pulls from `theme.py` — never hard-code gaps,
colours or fonts. Add screen widgets there, not inline. Keep the render path
asset-free.
