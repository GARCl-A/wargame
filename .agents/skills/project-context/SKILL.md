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
| `gartok-ui-redesign.md` | Presentation layer: theme.py design system, 100% procedural rendering, Screen base class contract. |
| `player-text-english.md` | Why everything is English, the sweep that made it so. |
| `gartok-doc-generator.md` | REFERENCE.md generation, repo structure, drift test, RULES.md prose-only rule. |

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
| `gartok-talent-trees.md` | General→specialist premise, tier-2 spec, Alert root, Fleet tier-3; racial track; Grippli Tongue. |
| `gartok-z-axis.md` | Per-cell elevation & pits: fall damage, Climb/Push/Jump/Drop-in, flight/climber. |
| `gartok-map-size-water.md` | Board carries cols/rows; water terrain (shallow=difficult, deep=Swim+breath/drown); Amphibious; camera zoom/scroll. |
| `gartok-arena-champion-title.md` | "Champion of the Pit": per-character title, arena-only Demoralize perks, title-defense cycle. |
| `gartok-arena-ribbit-brothers-boss.md` | Games capstone: 3 authored Grippli + 3 goons, CTF on an authored map. |
| `gartok-wilds-hunting.md` | The Wilds activity node: Hunt for meat with per-hour ambush risk; encounters.py scaled-enemy core. |
| `gartok-balance-sim.md` | balance_sim.py + economy_sim.py: AI tournaments ranking races/occupations/combos. |

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
