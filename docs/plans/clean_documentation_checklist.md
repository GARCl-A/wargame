# Documentation cleanup checklist

**Update this file whenever we touch the documentation** (add, remove, move, rename or merge a doc).
Tick a box once the file was reviewed and its fate decided (kept, trimmed, merged, deleted).

Snapshot: 2026-11-01, updated after removing `.agents` — 60 `.md` + 2 `LICENSE.txt`, plus the non-text folders at the end.

## Responsibility map (decided 2026-11-01)

Goal: duplication close to zero. Each topic has **one owner**; every other doc holds at most a
one-line rule and a link. When a box below is ticked, apply this map to that file.

**What `AGENTS.md` is for.** It rides on every request, so it holds only what an agent would get
wrong or break without knowing it, that the code does not show, and that applies on any task:
agent behaviour (language, commits, comments, where to work), invariants the tests enforce, and the
code-facing consequence of a design premise. It never holds a module's description, a number, a
dated decision, history or the *why* of a premise.

Test for a premise: *if an agent ignored it, would it write code that breaks an invariant or a test?*
Yes -> one line in `AGENTS.md` (the code-side consequence only) and the prose stays in `RULES.md`.
No (it only makes the design feel off) -> `RULES.md` alone.

| Topic | Owner | Everyone else |
|---|---|---|
| Design premises and their *why* (sandbox, individual, no treasury, adventure vs labour, vision, disposable squad) | `RULES.md` (World systems) | `AGENTS.md`: one line each for the premises that touch code (individual, world-first, no treasury, per-character vision, re-run the economy report); `README.md`: one sentence of pitch |
| Premise of a disposable early squad | `RULES.md` only | not in `AGENTS.md` (no code consequence) |
| Dated economy decisions and numbers (the ~50% yard margin, accepted 2026-10-22) | `docs/plans/economy_sim_v2.md` | `AGENTS.md`: only "re-run `scripts/economy_report.py` after touching wages, purses, prices or loot" |
| Money mechanics (coins, 200 = 1 kg, bank fee, change) | `RULES.md` | `AGENTS.md`: "money is items on the character, no guild pool" |
| pygame only in the Editor, delete the screen with its rules | `docs/web_client.md` | `AGENTS.md`: one rule line + link; `editor/ui/README.md`: its opening line only |
| Test gate, markers, `standard_unit`, tiers | `docs/plans/test_suite.md` | `AGENTS.md`: the gate command + the `standard_unit` rule + link; the exact steps live in `pre-commit` |
| Commit rules (Portuguese, no accents, no `Co-Authored-By` ever, `pre-commit` first, user approval) | `.claude/skills/pre-commit/SKILL.md` | `AGENTS.md`: one line + link; the two `commit-workflow.md` copies are deleted (one was Antigravity-only) |
| Where code lives, how to add a system | `README.md` | `AGENTS.md`: link only |
| Catalog data | `REFERENCE.md` (generated) | link only |
| History and rejected options | `project-context` (frozen), `git log` | `AGENTS.md`: one line |
| Cloud session | works on its own `claude/...` branch; once on `main` it is deleted | already in `AGENTS.md`; no change |

Decisions: no `Co-Authored-By` trailer from anywhere, whatever a harness reminder says (the repo rule
wins). A dated decision is kept only in the doc that owns it, with its date as provenance.

## Root
- [x] `AGENTS.md` — done 2026-11-01 (94 -> 81 lines): opening and *Deep context* shortened, *Tests* and *pygame* are rule + link, premises cut to their code-facing line (disposable squad dropped: it is in `RULES.md` l. 715), dated ~50% decision moved to `economy_sim_v2.md`, owner list added. *Load-bearing rules* and *Feature implementation rules* untouched.
- [ ] `CLAUDE.md`
- [x] `README.md` — done 2026-11-01 (428 -> 256 lines): pitch cut to one paragraph, *Controls* (stale pygame keys) and the *generator / designed / World systems* bullets deleted (`RULES.md` owns them), *Structure* lost its pygame ghosts (`icons`, `artwork`, `battle_fx`, `abandon_screen`, `watch_screen`), `web/`, `scripts/` and `docs/` shrank to a pointer, *How to add* aligned with `SAVE_DEFAULTS` and the `arena_talk` namespace. `tests/test_readme_map.py` now fails on a module missing from the map or a file named that does not exist.
- [ ] `REFERENCE.md`
- [ ] `RULES.md`

## `docs/`
- [ ] `docs/web_client.md`
- [ ] `docs/plans/backlog.md`
- [ ] `docs/plans/campaign_ai_roadmap.md`
- [ ] `docs/plans/economy_sim_v2.md`
- [ ] `docs/plans/test_suite.md`

## Local READMEs
- [ ] `editor/ui/README.md`
- [ ] `gartok/assets/README.md`
- [ ] `gartok/web/client/fonts/README.md`
- [ ] `scripts/portrait_lora/README.md`
- [ ] `recordings/2026-10-08/README.md`
- [ ] `recordings/2026-10-10/README.md`
- [ ] `recordings/2026-10-12/README.md`
- [ ] `recordings/2026-10-19/README.md`

## Licenses
- [ ] `gartok/assets/icons/LICENSE.txt`
- [ ] `gartok/assets/sounds/LICENSE.txt`

## Agent skills and rules

Decided 2026-11-01: **Antigravity is no longer used**, so `.agents/` is gone and the three skills it
held now live in `.claude/skills/`, the only place Claude Code finds them (done, same day).
- [ ] **Local skills (yours):** look at the skills on your own machine (`~/.claude/skills/`) and copy
  the ones the repo needs into `.claude/skills/`, then list each one here. Nothing in the repo
  depends on them being there.
- [x] `.agents/rules/commit-workflow.md`, `.agents/hooks.json`, `.agents/scripts/lint_touched_file.py` — deleted (Antigravity only; "wait for approval" lives in `pre-commit` step 9, Claude's hook in `.claude/settings.json`)
- [x] `scripts/lint_touched_file.py` — Antigravity branches cut, message in English
- [x] `.claude/settings.json` — kept (the ruff PostToolUse hook), status message in English
- [x] `.claude/skills/check_backlog/SKILL.md` — the real file now (the pointer is gone)
- [ ] `.claude/skills/pre-commit/SKILL.md` — moved, Antigravity paragraph cut; still to review its content against the map (it owns the commit rules and the exact test steps)
- [ ] `.claude/skills/project-context/SKILL.md` — moved, commit-workflow row and empty *Workflow* section gone; its fate goes with the references below
- [ ] `.claude/skills/gen-portrait/SKILL.md` — review

## `project-context` references (38 files)
All under `.claude/skills/project-context/references/`:
- [x] `commit-workflow.md` — deleted, with its index row and the `[[commit-workflow]]` mention in `gartok-recruit-capacity.md`
- [ ] `player-text-english.md`
- [ ] `gartok-arena-champion-title.md`
- [ ] `gartok-arena-ribbit-brothers-boss.md`
- [ ] `gartok-autowin.md`
- [ ] `gartok-balance-sim.md`
- [ ] `gartok-bankers-bank-chest.md`
- [ ] `gartok-beast-creatures.md`
- [ ] `gartok-character-creator.md`
- [ ] `gartok-crafting-traps.md`
- [ ] `gartok-doc-generator.md`
- [ ] `gartok-economy-lore-tutorial.md`
- [ ] `gartok-economy-sim-v2.md`
- [ ] `gartok-enemy-kit-by-level.md`
- [ ] `gartok-factions-reputation.md`
- [ ] `gartok-food-sharing.md`
- [ ] `gartok-groups-refactor.md`
- [ ] `gartok-guild-group-screens-split.md`
- [ ] `gartok-guild-hub-redesign.md`
- [ ] `gartok-high-identity-races.md`
- [ ] `gartok-item-system.md`
- [ ] `gartok-leadership.md`
- [ ] `gartok-map-editor.md`
- [ ] `gartok-map-size-water.md`
- [ ] `gartok-mission-confianca-progress.md`
- [ ] `gartok-missions-and-tanner.md`
- [ ] `gartok-name-generator.md`
- [ ] `gartok-open-world-vision.md`
- [ ] `gartok-portrait-generation.md`
- [ ] `gartok-portraits-and-treefolk.md`
- [ ] `gartok-property-two-paths.md`
- [ ] `gartok-recruit-capacity.md`
- [ ] `gartok-tactical-project.md`
- [ ] `gartok-talent-trees.md`
- [ ] `gartok-theme-exit-and-mixins.md`
- [ ] `gartok-time-scarcity.md`
- [ ] `gartok-ui-redesign.md`
- [ ] `gartok-wilds-hunting.md`
- [ ] `gartok-z-axis.md`

## Non-text documentation (folder exploration)

### `docs/plans/references/` — HTML mockups (168 files in subfolders + 4 loose PNGs)
Loose images in the folder root:
- [ ] `docs/plans/references/gnoll_10.png`
- [ ] `docs/plans/references/grippli_13.png`
- [ ] `docs/plans/references/kenku_4.png`
- [ ] `docs/plans/references/ogre_0.png`

Each mockup is a standalone page (`*.html` + `icons.js`, often `data.js`) with its screenshots and an `img/` folder of portraits/sprites:
- [ ] `battle_mockup/` — 14 files + 10 in `img/` (`battle.html`, `fog.html`, `pit.html`, `pit_maps.html`, `stack.html`, `play_battle.bat`)
- [ ] `dialogue_mockup/` — 7 files + 18 in `img/` (`dialogue.html`)
- [ ] `draft_mockup/` — 8 files + 27 in `img/` (`draft.html`)
- [ ] `map_mockup/` — 6 files + 9 in `img/` (`map.html`)
- [ ] `market_mockup/` — 3 files + 5 in `img/` (`market.html`)
- [ ] `menu_mockup/` — 3 files + 4 in `img/` (`menu.html`)
- [ ] `report_mockup/` — 8 files + 9 in `img/` (`report.html`)
- [ ] `sheets_mockup/` — 7 files + 9 in `img/` (`sheets.html`)
- [ ] `talents_mockup/` — 15 files + 6 in `img/` (`talents.html`, `big.js`)

### `docs/art/` — art candidates (images only, no text)
- [ ] `elf_options/` — 6 PNGs (3 options, 200 px and 512 px)
- [ ] `hobgoblin_options/` — 6 PNGs (3 options, 200 px and 512 px)
- [ ] `npc_options/` — 20 PNGs (10 NPCs, 200 px and 512 px)
- [ ] `snake_dragon/` — 2 PNGs
- [ ] `snake_options/` — 6 PNGs (cascavel, cornuda, mamba)
- [ ] `sprite_options/` — 6 PNGs (monocle, vaultkey, goldcoin)
- [ ] `treefolk_options/` — 4 loose comparison sheets (PNG/JPG), plus:
  - [ ] `cropped/` — 16 PNGs (8 medallions + 8 raw)
  - [ ] `cropped_v2/` — 8 PNGs
  - [ ] `military/` — 8 PNGs (recruit variants)
- [ ] `wagon_options/` — 2 sheets (JPG), plus:
  - [ ] `cropped/` — 6 PNGs (cart and wagon, raw and medallion)
