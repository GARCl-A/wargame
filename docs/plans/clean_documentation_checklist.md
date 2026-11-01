# Documentation cleanup checklist

**Update this file whenever we touch the documentation** (add, remove, move, rename or merge a doc).
Tick a box once the file was reviewed and its fate decided (kept, trimmed, merged, deleted).

Snapshot: 2026-11-01 — 63 `.md` + 2 `LICENSE.txt`, plus the non-text folders at the end.

## Root
- [ ] `AGENTS.md`
- [ ] `CLAUDE.md`
- [ ] `README.md`
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
- [ ] `.agents/rules/commit-workflow.md`
- [ ] `.agents/skills/check_backlog/SKILL.md`
- [ ] `.agents/skills/pre-commit/SKILL.md`
- [ ] `.agents/skills/project-context/SKILL.md`
- [ ] `.claude/skills/check_backlog/SKILL.md`
- [ ] `.claude/skills/gen-portrait/SKILL.md`

## `project-context` references (39 files)
All under `.agents/skills/project-context/references/`:
- [ ] `commit-workflow.md`
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
