# Plan — Brazilian Portuguese translation (`pt-br`)

Goal: the whole game playable in `pt-br`, chosen in Settings, with English still the default and the
fallback. Status: **phases 1-4 done** (2026-11-05; each phase's deliberate limits are listed under it); the audit counts what is left. The translation must be COMPLETE before the next playtest (author 2026-11-04),
all six phases (see [backlog.md](backlog.md)).

Sizes below come from greps (2026-11-04), not from reading each module: re-count at the start of each phase.

## What exists

- `gartok/i18n.py`: nested `locales/<lang>.json` flattened to dotted keys; `t()` falls back current language
  → `en` → the key itself; `has()`, `set_language()`, `language()`. Global language, no interpolation, no plural.
- Converted so far: `tutorial.*` (~107 keys), `arena_talk.*`, the credits. Everything else is literal English.

## What is left (the size of it)

| Area | Where | Size |
|---|---|---|
| Sentences in code | `gartok/` — combat log, action messages, web tabs and sessions, job offers, dialogues | ~1,100 literals + ~700 f-strings |
| Manual plurals and casing | `+ "s"`, `.title()`, `.capitalize()` | ~54 sites |
| Catalog text | `items.py` (1,127 lines), `talents.py`, `conditions.py`, `abilities.py`, `weapon_traits.py` | names + descriptions |
| Content JSON | `npcs/`, `maps/`, dialogue data | text embedded in files |
| Web client | `gartok/web/client/` — ~7k lines JS, ~370 lines HTML, ~40 fixed labels | most text arrives from the server |
| Docs generated from registries | `REFERENCE.md` | stays English |
| Tests | assertions on English text | pin the language to `en` |

## Decisions (author 2026-11-04)

1. **Id vs name: decided.** An id is an id and the string on screen is another thing; the displayed name comes
   from a catalog key and never feeds back into logic. Breaking saves for a better standard is accepted
   (`SAVE_VERSION` bump, no migration), so ids are not bound to today's English names. Wagons get ids and
   names the player can set.
2. **One catalog: leaning, not certain.** A single i18n catalog rather than one per domain; revisit if it
   gets in the way. Language is per process behind the `i18n.language()` API.
3. **Combat log: decided.** It records ids and parameters; the human string is rendered only in the interface,
   so a recording replays in any language.
4. **Content JSON.** NPC/map/dialogue text: keys in the catalog, resolved through `i18n` (still open
   whether per-file `text` keys or a parallel file; prefer the catalog).
5. **Grammar.** Portuguese needs gender and articles ("o/a", "do/da", "no/na"). Rule: no sentence is built
   by joining translated fragments; each sentence is one key with placeholders, and a noun that changes an
   article carries its gender in the catalog entry (`{"name": "Espada Longa", "gender": "f"}`).

## Phases

Each phase ends with the test gate green and the game playable, English unchanged. Fallback to `en` keeps a
half-translated build usable.

### 1. Framework

- `i18n.t(key, **params)` with `str.format` placeholders; plural helper (`i18n.plural(key, n)` with
  `one`/`other` forms).
- `i18n.name(kind, id)` for catalog names/descriptions with fallback to the id.
- Settings: a `language` entry in `settings.SPEC` (`en`, `pt-br`), saved with the other settings;
  `set_language` at boot. Language names are written in their own language.
- Test: every key in `locales/pt-br.json` exists in `en.json` and uses the same placeholders; every `en`
  key has a `pt-br` one (a gap list is allowed while phases are open, then the test goes strict).
- Test: a test that runs the whole suite's text assertions with `en` pinned (a fixture in `conftest.py`).
- Tooling: `scripts/i18n_audit.py` lists remaining literal sentences per module (AST: string constants with
  a space and a letter, in a call that reaches the UI or log), so progress is a number that falls.
- Docs: `AGENTS.md` ("All text is English" becomes "all text has an `en` key"), `README.md` recipe,
  `tests/README.md`.

### 2. Web client and chrome

Menus, tabs, buttons, tooltips, settings, errors, the 31 HTML screens' fixed labels, the JS strings.
Client text moves to keys served by `/api/locale` (the `ui.*` group, `en` filling gaps) and the client reads
them with `tr` / `trn` / `data-t`. Tutorial cards and credits get their `pt-br` text here too.

Done (2026-11-04): the mechanism, `shell.js`, `kit.js`, the member sheet, settings, title, the hub (every
tab), the guild (members, charter, reputations, bands, routines), the draft, the talk, the talents, the arena, the hunt, the watch, the wiki, the report, the map and the battle. `i18n_audit.py` does not see JS: count with `grep -c` on each file's literals.

### 3. Messages and combat log

Action messages, end-of-turn, traps/flags, results, AI-visible text excluded (the AI reads data, not
prose). Convert module by module (`actions/`, `combat_log.py`, `campaign_fight.py`, `hunt`, `craft`,
`trade`, `work_desk`, `vault`, `job_board`, …), highest-traffic first. Replace manual plurals as they are met.

Mechanism (done): `battle.log(key, **params)` keeps an `i18n.Msg`; the combat log (format 2) stores `{k, p}`
for a converted line and a plain string for one not converted yet; `i18n.Ref` names a catalog thing and resolves at
render time; `i18n.Text` makes an action's name/description a catalog read. Done: `actions/` (all of it, spells and
movement included), the turn flow, traps, falls, drowning and death saves in `battle.py`, the `go_down`/condition/ferocity
lines (`combatant.py`, `conditions.py`, `abilities.py`), the roll modifier labels (`log.mod.*`), `web/battle_session.py`
errors, and the `unit_poison`/`unit_levels`/`unit_hunger` messages; `campaign._death_note` reads the line keys; `web/campaign_fight.py`, the `campaign.py` notices, `hunt.py`, `stints.py` and `scenario.held_note`
(`campaign.*`, `hunt.*`, `stint.*`, `log.held.*`). Left: the
rest of the list (`combat_lab.py` descriptions, `craft`, `trade`, `work_desk`, `vault`, `job_board`, `tavern`, `ledger`, `routines`, ...),
and the attribute abbreviations (STR/DEX/CHA, a glossary decision).

Phase 3 closed (2026-11-05): every notice, result, error, button label and status chip of the rule modules and the web
sessions/tabs is a key (one group per module). Deliberate limits: `routine.paused` reasons and the memorial `cause` are stored
as already-translated strings; text built from ids with `.title()`/`.capitalize()` (school, stage, node ids) and the attribute
abbreviations stay for the phase 6 review; the title quote marks its bold part with `**` (the client turns it into `<b>`).
Left for later phases (audit, 1,238 literals): catalog text (`talents`, `items`, `abilities`, `weapon_traits`, `data`) in
phase 4; authored content (`world`, `factions`, `dialogue`, `missions`, `forced`, `objectives`, `node_functions`, `job_board`
keeper lines, arena blurbs) in phase 5; dev text (`combat_lab`, `reference`, `wiki_rules`).

### 4. Catalog

Item, talent, condition, racial ability, weapon trait, race, node, faction, skill and material names and
descriptions. `REFERENCE.md` stays English (generated from registries, the `REFERENCE.md must match the
registries` test keeps passing); the in-game wiki reads the catalog keys so it shows `pt-br`.

Done (2026-11-05): two kinds of registry. An entry with an `id` (talent, racial ability, weapon trait, faction, spell, poison,
vocation, archetype) has no text in the code: `name` / `desc` are properties that read `name.<kind>.<id>` / `desc.<kind>.<id>`
(`i18n.name`, `i18n.desc`) on every access, the English moved into `locales/en.json` and `REFERENCE.md` came out identical. A thing
whose id is its English name (items, races, alignments, sizes) keeps the name as the id and is shown through `i18n.name(kind, name)`:
the item tooltip, shelf life and stack notes (`item.*`), `Unit.race_label` for the races in every web payload, the alignments,
the wiki cards, the notices that name an item or tool, and in the client `nm("item", name)` (the server serves the `name.*` group
with `/api/locale`; the string posted back is still the id). A node keeps its English name as the default (a node made in play has no entry) and `name.node.<id>` wins; every item, race, size and static node has its `name.*` entry in `en.json`. A scroll is found through its spell by the item's `spell_id`, never by a shown name.
`tests/test_i18n_catalog.py` plays the first days with every shown name altered: it fails when a rule reads a shown name as an id.
`i18n_audit.py` ignores the strings that are catalog ids (item and race names, alignments, sizes) and the Editor's help text.
Deliberate limits, for phase 6: `pt-br` entries for items/races/nodes/spells (the English fallback shows until someone writes them,
composed names such as "Large Dagger", "Scroll of X", "Dictionary of X" included: write each one out); an item or race in a
sentence has no article by gender yet (`i18n.gender` exists); a beast's unit name is its species, shown as written; the
condition names inside `log.mod.*` labels are phase 3's; `magic.py`, `intel.py`, `unit_derive.py`, `group.py`, `sources.py`,
`wiki_terms.py` and `talent_session` still hold stat labels and derivation notes (audit); node and faction lore (`blurb`, deeds)
is phase 5.

### 5. Content and dialogue

NPC names/lines, map names, job and event text, forced events, the arena talk. Needs the decision above
on JSON text.

### 6. Translate and review

Fill `pt-br.json`. The text is written in Portuguese sentence by sentence, with the game's context and an
author-approved glossary of its terms (Takedown, Grab, Brutal...) first; never machine translation, and no
translation service runs in the game. Then the author reads it in play, as with the tutorial cards.
Check: overflow on long strings (Portuguese runs ~20–30% longer: the overflow items in the backlog apply),
accents and the font's glyph coverage (ç, ã, õ, é…), sort order, number and money formats.

## Rules while the work is open

- A new feature adds its text as keys from day one (never a new literal sentence in `gartok/`).
- Commits stay Portuguese without accents, as always; this is about game text only.
- Don't mix a phase with other changes: one phase per commit series, gate green after each.

## Done when

- `scripts/i18n_audit.py` reports zero literal sentences outside the allow-list (ids, log keys, dev text).
- The key-parity test is strict.
- A full run (title → guild → map → battle → report) in `pt-br` shows no English and no raw key.
- The author has read the `pt-br` text in play.
