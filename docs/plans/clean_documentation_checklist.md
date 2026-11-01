# Documentation cleanup checklist

**Update this file whenever we touch the documentation** (add, remove, move, rename or merge a doc).
Tick a box once the file was reviewed and its fate decided (kept, trimmed, merged, deleted).

Snapshot: 2026-11-01, updated after removing `.agents` — 57 `.md` + 2 `LICENSE.txt`, plus the non-text folders at the end.

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
| Dated economy decisions and numbers (the ~50% yard margin, accepted 2026-10-22) | `docs/economy_sim.md` | `AGENTS.md`: only "re-run `scripts/economy_report.py` after touching wages, purses, prices or loot" |
| Money mechanics (coins, 200 = 1 kg, bank fee, change) | `RULES.md` | `AGENTS.md`: "money is items on the character, no guild pool" |
| pygame only in the Editor, delete the screen with its rules | `docs/web_ui/web_client.md` | `AGENTS.md`: one rule line + link; `editor/ui/README.md`: its opening line only |
| Test gate, markers, `standard_unit`, tiers | `tests/README.md` | `AGENTS.md`: the gate command + the `standard_unit` rule + link; the exact steps live in `pre-commit` |
| Commit rules (Portuguese, no accents, no `Co-Authored-By` ever, `pre-commit` first, user approval) | `.claude/skills/pre-commit/SKILL.md` | `AGENTS.md`: one line + link; the two `commit-workflow.md` copies are deleted (one was Antigravity-only) |
| Where code lives, how to add a system | `README.md` | `AGENTS.md`: link only |
| Open work | `docs/plans/backlog.md` (tasks) | a big item points to its plan in `docs/plans/` (`loyalty.md`, `campaign_ai_roadmap.md`); a doc of something already built is not a plan and lives outside `docs/plans/` |
| Catalog data | `REFERENCE.md` (generated) | link only |
| History and rejected options | `project-context` (frozen), `git log` | `AGENTS.md`: one line |
| Cloud session | works on its own `claude/...` branch; once on `main` it is deleted | already in `AGENTS.md`; no change |

Decisions: no `Co-Authored-By` trailer from anywhere, whatever a harness reminder says (the repo rule
wins). A dated decision is kept only in the doc that owns it, with its date as provenance.

## Root
- [x] `AGENTS.md` — done 2026-11-01 (94 -> 81 lines): opening and *Deep context* shortened, *Tests* and *pygame* are rule + link, premises cut to their code-facing line (disposable squad dropped: it is in `RULES.md` l. 715), dated ~50% decision moved to `economy_sim_v2.md`, owner list added. *Load-bearing rules* and *Feature implementation rules* untouched.
- [x] `CLAUDE.md` - points towards `AGENTS.md`.
- [x] `README.md` — done 2026-11-01 (428 -> 256 lines): pitch cut to one paragraph, *Controls* (stale pygame keys) and the *generator / designed / World systems* bullets deleted (`RULES.md` owns them), *Structure* lost its pygame ghosts (`icons`, `artwork`, `battle_fx`, `abandon_screen`, `watch_screen`), `web/`, `scripts/` and `docs/` shrank to a pointer, *How to add* aligned with `SAVE_DEFAULTS` and the `arena_talk` namespace. `tests/test_readme_map.py` now fails on a module missing from the map or a file named that does not exist.
- [x] `REFERENCE.md` — done 2026-11-01 (729 -> 656 lines, generated): it is the **design catalog for developers and agents, spoilers included** (the player's view is the in-game wiki, which must show only what the guild has discovered: backlog, *Medium*). `Items` no longer repeats weapons/armor/shields and groups the dictionaries and scrolls, with prices; new *Creatures* section and `Held by` / `d100` columns; `Requires` shows names, the racial track is grouped by race; prose numbers come from the constants. `tests/test_reference.py` pins all of it (derived prose, every registry entry present, no ids, no repeated tables, doc pointers resolve); the two data-integrity tests moved to `tests/test_data_catalog.py`. Still for `RULES.md`: its deed table, throw ranges and loose constants duplicate this file.
- [x] `RULES.md` — done 2026-11-01 (2127 -> 1948 lines): what `REFERENCE.md` already generates is a pointer now (vocation table, archetype list, size table, creature stats, racial-ability effects, weapon-action list, Pits/Bankers/Library deeds, XP curves, kit budget, talent nodes, throw ranges); the code-map paragraph is gone (`README.md` owns it); the premises (world-first, disposable squad) moved into the one *World systems* list that `AGENTS.md` points to. Stale text fixed: "only the Dagger throws / the Light Crossbow is the one ranged weapon", the yard's "$0.75/h", "food: Meat, Potato" and "food for sale at the market", the pygame ghosts (`ui.banner`, `ui/foe_panel.py`, `App._work_shift`, `RepossessionScreen`, the Gear screen's right-click "study" row, `Guild.ox_fields_discovered`). `tests/test_rules_doc.py` fails on a named file, module attribute, class or constant that no longer exists, and on a quoted constant value that drifted. Spells now have a generated `## Spells` in `REFERENCE.md` (each spell action carries its `desc`, with range and dice read off its constants; *Magic* keeps only the rules, where the scrolls come from and how the AI casts); the quest sections cite the module constants behind their rosters, levels and DCs (`necromancer.SOLDIERS = 4`), so the test validates them (68 quoted values). Left open: `wiki_rules.py` is a hand-written, player-facing copy of part of the combat prose.

## `docs/`
- [x] `docs/web_ui/web_client.md` — done 2026-11-01 (116 -> 109 lines): it is the brief an agent reads before building a screen, so judgment (art direction, layouts) stays unvalidated and only the pointers are tested. Cut what other owners hold (tutorial recipe -> `README.md`, fog filter and hunt-not-saved -> `AGENTS.md`, fonts and glyph licences -> their own files, tests-first, the kit's function list -> the `kit.js` header). *How the art is made* now says Gemini is preferred and the LoRA is the weaker fallback, and that an agent asks for art instead of generating it. `tests/test_web_client_doc.py` pins the mockup table, links, desks, client files and session hooks. Still open in other reviews: `README.md`, `backlog.md` (Art) and the `gen-portrait` skill present the LoRA as the official path, and `backlog.md` repeats the four-portrait anchor.
- [x] `docs/plans/backlog.md` — done 2026-11-01 (682 -> ~585 lines): a task is a few lines and points to its plan. Re-ordered to match its own header (*Before the friends' playtest*, *Ready to do* Small/Medium, *Large and later* = Large/Art/Epic, deprioritised and reflection, playtest notes, *Needs more information*). Deleted what was done or is no longer true: the *Web front-end* status section, the pre-playtest item about splitting the editors' big files (the Editor is frozen), the 2026-10-28 and 2026-10-30 playtest summaries, the fog and hit-sound notes already listed elsewhere. The wagon/animal/camp constraints moved to `RULES.md` (*Animals and wagons*). The 100-line *Loyalty* design talk moved to `loyalty.md` (a one-paragraph item stays). New items from the absorbed docs: *Campaign AI*, *Economy numbers to sign off* (the economy plan's still-live questions), *Test suite: faster tiers*. The Art section no longer presents the LoRA as the official path nor repeats the four-portrait anchor.
- [x] `docs/plans/campaign_ai_roadmap.md` — kept and trimmed (138 -> ~65 lines): it is the plan of the backlog's *Campaign AI* item. Phase 1 is marked done (`scripts/economy_guild.py`), the executive summary, the technology table, the time estimates and the "when you are ready to resume" steps are gone, the four exploit hypotheses are kept and marked as not covered by the detector, and the old backlog item *Sim policies that find the opportunities themselves* is phase 2.
- [x] `docs/plans/economy_sim_v2.md` — it said "everything in this plan is built", so it was not a plan: moved to `docs/economy_sim.md` as a reference (556 -> ~170 lines): tools, roles, targets, how the sim models play, the detector, the modelling choices that still shape the numbers, the limits. Dropped: 20 dated findings, the author's answers and 24 "decisions made without asking" (in git: `git show 1a999bf:docs/plans/economy_sim_v2.md`; the frozen story is the `gartok-economy-sim-v2` reference). The policies that no longer exist (`games`, `claimer`, `grower`, `rush`, `climber`, `human`...) are described as engine, not policy. The questions still open went to the backlog (*Economy numbers to sign off*). The scripts' docstrings point at the new path.
- [x] `docs/plans/test_suite.md` — it described how the suite works, not what to do: moved to `tests/README.md` (75 -> ~45 lines: tiers, the per-test seed, `standard_unit`, the two gotchas, the doc tests). Its "next steps" went to the backlog (the four luck tests inlined, the speed tiers under *Deprioritised*, the `standard_unit` note under *Remove occupations*). The "What was found" history and the timings that drift are gone.
- [x] `docs/plans/loyalty.md` — new, extracted from the backlog (see above).
- [x] `tests/test_plans_docs.py` — new: links, named files, named tests and `module.NAME` references of the plans, `docs/economy_sim.md` and `tests/README.md` must exist; every plan must be named in the backlog; the sim scripts' doc pointer must resolve.

## Local READMEs
`tests/test_local_readmes.py` keeps the assets README true (every icon folder listed, only real files named).
- [x] `editor/ui/README.md` — done 2026-11-01 (66 -> 22 lines). The Editor is frozen (reference for a future port off pygame), so the README is now the look to carry over (colour is state, the 8 px grid, data in / rects out) and the component table is gone (docstrings own it). `inspector_panel.py` was dead but for `draw_role` / `ROLE_MARK`: those moved into `loadout_panel.py`, the module is deleted.
- [x] `gartok/assets/README.md` — done 2026-11-01 (31 -> 21 lines): it described `gartok/artwork.py` and `map_screen.NODE_ICON` (both gone), pointed at `tests/test_icons.py` (lives in `editor/tests/`) and omitted `icons/item/`. Now: tree, who reads the files (`art_files.py`, the web, `editor/artwork.py`), the `map/` drawing rule, how to add an icon. The glyph-per-race/occupation/node rule is in `AGENTS.md`; the cue list is `sound.py`'s.
- [x] `gartok/web/client/fonts/README.md` — kept as is: source, licence and the weight choices; `fonts.css` declares the faces and nothing else says where they come from.
- [x] `scripts/portrait_lora/README.md` — kept, two edits: the hard "230 images" is gone from the command comment and the 230 is now stated as what the shipped LoRA saw (the pool has 350 portraits), and the default `-000006` pick is explained. Owns setup, training and measured times (the `gen-portrait` skill and `gen_portrait.py` point here); the notebook owns the training recipe.
- [x] `recordings/*/README.md` (4 files) — merged into one `recordings/README.md`: the four repeated the recorder blurb and the `saves/` note. Dead pointers dropped (`economy_guild.py --policies human --profile`: the `human` policy was folded into `balanced`; the backlog item *Feed the recorded runs*: no longer in `backlog.md`). Day and fight counts re-read from the `.jsonl` files. The three `human_profile*.json` were deleted (`play_analysis.py` regenerates them).

## Licenses
- [x] `gartok/assets/icons/LICENSE.txt`
- [x] `gartok/assets/sounds/LICENSE.txt`

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

### `docs/web_ui/references/` — HTML mockups
- [x] Four loose PNGs in the folder root (`gnoll_10`, `grippli_13`, `kenku_4`, `ogre_0`): kept, they are the style anchor for generated art (`web_client.md`, Art direction; `backlog.md`, Art).

Kept: `docs/web_ui/web_client.md` ("The mockups") names them the approved look of each family, and five screen
stylesheets plus `guild_session.py` cite them. Each `img/` holds byte-identical copies of `gartok/assets`
art, left because the mockup pages load it by relative path.
- [x] `battle_mockup/` (`play_battle.bat` still works: it launches `python -m gartok.web --fight`)
- [x] `dialogue_mockup/`
- [x] `draft_mockup/`
- [x] `map_mockup/`
- [x] `market_mockup/`
- [x] `menu_mockup/`
- [x] `report_mockup/`
- [x] `sheets_mockup/`
- [x] `talents_mockup/`

### `docs/art/` — art candidates (images only, no text)
- [x] `elf_options/` — 6 PNGs (3 options, 200 px and 512 px)
- [x] `hobgoblin_options/` — 6 PNGs (3 options, 200 px and 512 px)
- [x] `npc_options/` — 20 PNGs (10 NPCs, 200 px and 512 px)
- [x] `snake_dragon/` — 2 PNGs
- [x] `snake_options/` — 6 PNGs (cascavel, cornuda, mamba)
- [x] `sprite_options/` — 6 PNGs (monocle, vaultkey, goldcoin)
- [x] `treefolk_options/` — 4 loose comparison sheets (PNG/JPG), plus:
  - [x] `cropped/` — 16 PNGs (8 medallions + 8 raw)
  - [x] `cropped_v2/` — 8 PNGs
  - [x] `military/` — 8 PNGs (recruit variants)
- [x] `wagon_options/` — 2 sheets (JPG), plus:
  - [x] `cropped/` — 6 PNGs (cart and wagon, raw and medallion)
