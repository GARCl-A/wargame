---
name: player-text-english
description: GARTOK is fully English now — all game text and data (was pt-BR)
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4890176b-a417-48f4-aba3-7360eb61b4d8
  modified: 2026-09-10T10:03:50.502Z
---

**All of GARTOK is in English** — UI text, generated messages, combat log, and
the whole data model (item / race / occupation / alignment / size / language /
weapon / armor / ability / condition names, stat abbreviations HP/AC/MD/STR/DEX/
WIS/CHA/SPD, node ids like `"city"` / `"lumber_yard"`, the `"tavern"` kind).
Code identifiers, comments and docstrings are English too.

**Why:** the user set English as the project standard (2026-09-08) and then
asked for a full sweep with no backward-compat concern — "não precisa de
migração, pode apagar as migrações de save". Old save files were deleted;
`persist.from_save` keeps its `.get(key, default)` defensiveness but there is no
version migration.

**How to apply:** every new string — UI, log line, catalog entry — is English.

**The docs are English now too** (2026-09-10, this session): `README.md`
rewritten in English; `GARTOK-regras.md` → **`RULES.md`** (English design prose
only — combat rules, §9, world systems). The catalog tables (races, occupations,
ability effects, weapons, armor, prices, talents, constants) were pulled out of
the prose doc into a **generated `REFERENCE.md`** (`python -m gartok.reference`,
walks the registries). Nothing pt-BR is left in the repo. See
[[gartok-doc-generator]].

Done across two commits: campaign UI first, then the big combat+data sweep.
See [[gartok-tactical-project]] and [[gartok-ui-redesign]].
