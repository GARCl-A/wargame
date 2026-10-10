---
name: project-context
description: On-demand deep context for the GARTOK project. Read this when you need the design rationale, history, or architecture details behind a specific feature — each reference file covers one completed initiative.
---

This skill holds the full project memory from GARTOK's development. **Do not
read every file** — scan the index below, identify which reference(s) are
relevant to your current task, and read only those.

## Index

Each file in `references/` covers one completed initiative or standing rule.

### Architecture & identity
| File | What it covers |
|---|---|
| `gartok-tactical-project.md` | **Start here for deep architecture.** Module-by-module breakdown, design premises, combat rules summary, recruitment, progression, armor, encumbrance, test suite shape. |
| `gartok-open-world-vision.md` | The north star: megalomaniac open-world guild manager, specialised groups, base-building, interdependent activities. Sandbox, no win condition. |
| `gartok-guild-group-screens-split.md` | `GuildScreen` handles macro state (roster, rep, leadership), `GroupScreen` handles tactical state (gear, inventory drag/drop, quests). |
| `gartok-ui-redesign.md` | (History; theme.py was deleted 2026-10-04.) Presentation layer, 100% procedural rendering, Screen base class contract. |
| `gartok-theme-exit-and-mixins.md` | **Oct 2026 refactor arc.** unit.py/guild.py split into mixins; theme.py deleted, `gartok/ui/` is the only presentation layer (board_style, banner, ui_fonts). |
| `player-text-english.md` | Why everything is English, the sweep that made it so. |
| `gartok-doc-generator.md` | REFERENCE.md generation, repo structure, drift test, RULES.md prose-only rule. |
| `gartok-item-system.md` | **Item System & ItemInstance.** Single source of truth in items.py, ItemDef, rich ItemInstance, UI helpers, and SAVE_VERSION 17. |
| `gartok-portraits-and-treefolk.md` | **Portraits System & Treefolk.** OSR medallion asset pipeline, artwork.portrait loader, Leshy->Treefolk rename/Medium size, deterministic portrait_id. |
| `gartok-portrait-generation.md` | **Portrait generation.** Local Stable Diffusion + self-trained style LoRA behind `/gen-portrait`: the recipe, what was tried and rejected (Civitai LoRAs, DreamShaper, img2img from a portrait), limits. |
| `gartok-economy-lore-tutorial.md` | **Oct 2026 arc.** World premise (adventuring beats day labour), the lumber/arena/hide numbers tuned to it, and the modal tutorial system (debounce, hub delegation, card ids). |
| `gartok-guild-hub-redesign.md` | **The Guild Hub Redesign.** Central command UI, multi-band accordion roster, tactical profile grid, 3-zone encumbrance, and contextual actions. |

### Systems (world / campaign)
| File | What it covers |
|---|---|
| `gartok-groups-refactor.md` | Guild→Groups→Units refactor (2026-09-11). Physical Group owns position+squad, tick/orders map loop, WorkScreen deleted. |
| `gartok-leadership.md` | Guild.leader (draft pick, 1 free swap) + Group.leader (free swap, capacity=3+CHA mod). |
| `gartok-factions-reputation.md` | Objective system: per-faction reputation via one-shot deeds, no per-win grind. |
| `gartok-recruit-capacity.md` | recruit_capacity=BASE+CHA mod caps roster growth; guild leader adds racial_level. |
| `gartok-time-scarcity.md` | First wedge: missions.py deadlines. |
| `gartok-missions-and-tanner.md` | missions.py (deadlined paid jobs), tanner_screen.py, finite market stock. |
| `gartok-beast-creatures.md` | Wolf, first non-humanoid; data.BEASTS data-driven; EncounterTable. |
| `gartok-food-sharing.md` | share_food toggle pools rations within a physical Group. |
| `gartok-property-two-paths.md` | **Base-building (all 4 systems).** City property (Bankers, tax, repossession/squat) + Garrison engine + Wilds claim campaign + Attack/retake. |
| `gartok-mission-confianca-progress.md` | Bankers' trust-mission arc: crime/guard, Old Road ambush, chest, Ankareth/Ledger Hold. |
| `gartok-bankers-bank-chest.md` | Guild's first shared property: a rented strongbox at the City. |

### Combat & mechanics
| File | What it covers |
|---|---|
| `gartok-crafting-traps.md` | Crafting system (recipes, materials, progress rolls), interactive/AI trap placement, and `campaign._carry_forward` state sync for consumed items/thrown weapons. |
| `gartok-talent-trees.md` | General→specialist premise, tier-2 spec, Alert root, Fleet tier-3; racial track; Grippli Tongue. |
| `gartok-high-identity-races.md` | High-identity tier-1 racial talents (Leshy Fruitful, Human Cosmopolitan, Halfling Luck); 24h daily framework (clock.day); Racial Level 5 talent gate. |
| `gartok-z-axis.md` | Per-cell elevation & pits: fall damage, Climb/Push/Jump/Drop-in, flight/climber. |
| `gartok-map-size-water.md` | Board carries cols/rows; water terrain (shallow=difficult, deep=Swim+breath/drown); Amphibious; camera zoom/scroll. |
| `gartok-arena-champion-title.md` | "Champion of the Pit": per-character title, arena-only Demoralize perks, title-defense cycle. |
| `gartok-arena-ribbit-brothers-boss.md` | Games capstone: 3 authored Grippli + 3 goons, CTF on an authored map. |
| `gartok-wilds-hunting.md` | The Wilds activity node: Hunt for meat with per-hour ambush risk; encounters.py scaled-enemy core. |
| `gartok-autowin.md` | **Auto-Win & Anti-Grind.** Monte Carlo simulation, 100% win / 0 casualties / 0 consumables gate, pre-battle ambush resolution on map & hunt. |
| `gartok-balance-sim.md` | balance_sim.py: AI tournaments ranking races/occupations/combos (its old `economy_sim.py` half was replaced, see the next row). |
| `gartok-economy-sim-v2.md` | **Economy sim v2** (scripts/economy_*.py): per-activity table, whole-guild sim on the real engine, exploit detector, Medic / Games / Claim, the day-30 milestone. |

### Tools
| File | What it covers |
|---|---|
| `gartok-character-creator.md` | CharEditorScreen (sandbox), DUPLICATE, 3 progression steppers, npc_lib. |
| `gartok-map-editor.md` | MapEditorScreen paints the board, map_lib (git-tracked maps/*.json). |
| `gartok-name-generator.md` | gartok/names.py: procedural names, private RNG. |

### Workflow
| File | What it covers |
|---|---|
| `commit-workflow.md` | Always run pre-commit, no Co-Authored-By. (Also in `.agents/rules/`.) |
