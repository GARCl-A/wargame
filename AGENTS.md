# GARTOK Tactical — agent context

Python turn-based squad wargame rebuilding a lost tabletop RPG from its character generator.
Sandbox guild manager — no win condition, no campaign end screen. Run ends only on a full wipe.
The game is the web client (`python main.py`); pygame survives only as the Editor
(`python main.py --editor`) and as screens the web still holds headless.

**Source of truth:** `RULES.md` = design prose (combat, world systems); `REFERENCE.md` = generated
catalog data (`python -m gartok.reference`, never edited by hand). When the two disagree,
`REFERENCE.md` wins. **Where code lives:** `README.md` → *Structure* (one line per module) and
*How to add a system*. This file is loaded on every request: keep it to rules, and put a new
module's description in the README, not here.

## Conventions

- **All text is English** — UI, combat log, data model, code, docs.
- **Commits** are Portuguese, present tense, no accented characters. No `Co-Authored-By:`
  trailer. Always run the `pre-commit` skill first.
- **Comments** default to none. Keep only a comment that explains a non-obvious *why*.
- **Tests:** `python -m pytest tests/ -n auto -m "not balance"` — the hard gate (~30 s). `-m balance`
  holds the sims' design numbers: run it with `scripts/economy_report.py` after touching wages,
  prices or loot. A test that is not about a roll builds its characters from
  `tests.helpers.standard_unit`, never a rolled `Unit(...)`. `sim_test.py` is a secondary check
  for combat/AI changes. Tiers and what is left: `docs/plans/test_suite.md`.
- **pygame is abandoned.** Never update, rewire or add a pygame screen; when a screen's rules move
  out, delete the screen and its tests in the same commit. Rules and what is left:
  `docs/plans/web_frontend.md`. New UI is the web client (`gartok/web/client/`: `shell.js`,
  `kit.js` for pieces two screens share, one folder per screen); the Editor's pygame UI follows
  `gartok/ui/README.md`.
- Work and commit straight on `main`; no feature branches unless the user asks for one.
  A teammate works on `main` in parallel, so `git pull` before committing.

## Design premises (durable)

- **Every unit is its own individual.** The group is a container, the unit is the atom. A shared
  activity resolves per-person.
- **World-first.** Rules exist as world things first; if they talk to combat, better.
- **Disposable early squad.** Early mortality is very high; starters are meant to be lost.
- **No guild treasury.** Money lives on the character as `Copper Coin` ($1) and `Gold Coin` ($100)
  items in the pack (they weigh, split and move like any item; 200 coins = 1 kg). `Unit.money` is
  their sum; paying spends copper first, then breaks gold and returns change. Gold only comes
  from the bank exchange (`economy.buy_gold` / `sell_gold`, $1 fee per coin each way); loot,
  wages and rewards are copper.
- **Vision is per-character.** The map is always dark; on your turn you see what the active unit
  sees. The drawing never shows what the rules hide: the web board is sent only as the side
  knows it, and `ai.py` reads a foe only through `intel.known_fields`.
- **Adventure out-earns day labour.** Lumber is only a survival floor (16 h = cheapest meal + $1);
  the arena and the wilds pay more. No fatigue, so the Yard pays ~50% over that floor: accepted
  (2026-10-22), hunger is the one upkeep. Re-run `scripts/economy_report.py` after touching
  wages, purses, prices or loot; `scripts/economy_offers.py` lists what a guild can take up today.

## Load-bearing rules (the code and its tests rely on them)

- **One concern per module.** A place's rules live in a class with no pygame (`trade.Counter`,
  `work_desk.WorkDesk`, `vault.BankVault`, `job_board.Board`, ...) and its web tab
  (`web/*_tab.py`) only draws it; a screen's server half is a `web/session.py` session.
- **Unit vs Combatant.** `unit.py` is the persistent character (mixins `unit_*.py`);
  `combatant.py` is that unit inside one battle. Persistent state goes on `Unit`, saved via
  `persist`.
- **Saves:** `persist.SAVE_VERSION`, no migration. A new *optional* field needs no bump: add its
  neutral value to `unit.SAVE_DEFAULTS` / `persist.PAYLOAD_DEFAULTS`. A battle or hunt in
  progress is never saved.
- **Registries, not branches:** actions are `Action` subclasses in `actions/` (+ `PANEL_ACTIONS`),
  racial abilities `abilities.py`, conditions `conditions.py`, weapon traits `weapon_traits.py`
  (`ItemDef.has_trait()`), talents `talents.py`, items `items.py` (single source), node services
  `node_functions.py` (each order kind has its tab in `web/hub_session.HUB_KINDS`), forced events
  `forced.EVENTS`.
- **Tests fail on a missing entry:** every item needs an `item_icon.ICONS` entry; every race,
  occupation and node a glyph (`art_files.RACE_ICON`, `OCCUPATION_ICON`, `map_view.NODE_ICON`);
  every base material a source (`sources.py`); `REFERENCE.md` must match the registries.
- **Combat log:** every `Action.execute`, end of turn and flag/trap goes through
  `CombatLog.record`, human or AI, so a fight rebuilds from its JSONL alone.
- **Groups:** a `Group` with a `pending` forced fight has `order = None` but is `locked`: no split,
  merge, leader swap or kit change until it resolves.
- A recipe's level is derived (`craft_level.py`), never set by hand.

## Feature implementation rules

Whenever a new mechanic or action is added to the game, you MUST always:
1. **Implement end-to-end**: backend, core logic and UI. 100% playable, no loose ends.
2. **AI support**: the AI knows how to use and react to the new mechanic in combat.
3. **Automated tests**: happy path, edge cases and AI behaviour.
4. **Tutorial card** for a new screen or tab: a `tutorial_key()` on its session and a
   `tutorial.<id>` block in `locales/en.json` (recipe in `README.md`).

## Deep context

History of a feature built up to 2026-10-20 or a past design decision (including what was tried
and rejected): the `project-context` skill (`.agents/skills/project-context/`), one reference per
initiative — read only what you need. Frozen since 2026-10-28; for anything later, the code,
`docs/plans/` and `git log` are the record.
