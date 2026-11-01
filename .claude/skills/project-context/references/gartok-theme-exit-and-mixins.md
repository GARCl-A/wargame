---
name: gartok-theme-exit-and-mixins
description: Oct 2026 refactor arc on main: unit.py/guild.py split into mixins, theme.py deleted (gartok/ui is the only presentation layer), board palette in ui/board_style, banner in ui/banner
metadata:
  type: project
---

Done 2026-10-04 on `main`, ~8 commits ending at `c902c66`.

- **Mixin split.** `Unit` = `HungerMixin, LevelingMixin, EditMixin, DerivationMixin, LoadoutMixin` (`unit_hunger/levels/edit/derive/loadout.py`); `Guild` = `HoldingsMixin, WildsClaimMixin, UpkeepMixin, LaborMixin` (`guild_holdings/claim/upkeep/labor.py`). Public API unchanged; `unit.py`/`guild.py` re-export the helpers callers import. Tests that monkeypatch module names must patch the *new* module (e.g. `roll` lives in `unit_loadout`).
- **theme.py is gone**, with `LegacyFonts` and `test_theme_budget.py`. Board colours/layout/`BoardView` -> `ui/board_style.py`; banner colour -> `ui/banner.py`; `Stack`, `box`, `pips` -> `ui/primitives.py`; `hp_tooltip` -> `ui/sheet_card.py`. Every screen now takes the `tokens.fonts()` dict (`app.ui_fonts`); ctor params are still *named* `fonts`/`self.fonts`.
- **Static check kept:** `tests/test_static.py` runs ruff F821 over the package (a missing import only explodes on a rarely drawn path).
- `battle_screen`, `char_editor_screen`, `map_editor_screen` got a reskin only (same layout); a real battle HUD redesign is expected later.

**Why:** the user wanted the `ui/` kit to be the sole presentation source and the two 1300-line modules split before more features inflate them.

**How to apply:** supersedes the theme.py description in [[gartok-ui-redesign]]; completes [[gartok-ui-component-migration]]. Scope `ruff --fix` to specific files (a broad run once rewrote unrelated test files).
