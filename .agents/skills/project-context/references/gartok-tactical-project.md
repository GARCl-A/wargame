---
name: gartok-tactical-project
description: "c:\\dev\\wargame = GARTOK Tactical, a Python/pygame-ce turn-based squad wargame rebuilding the lost GARTOK tabletop RPG from its char generator"
metadata: 
  node_type: memory
  type: project
  originSessionId: e8c74a1e-914a-469b-9b88-6880aab3a82b
  modified: 2026-09-11T02:54:57.567Z
---

`c:\dev\wargame` = **GARTOK Tactical**, turn-based tactical wargame in Python /
pygame-ce. Presentation layer: see [[gartok-ui-redesign]].

## Context

The user (GARCl-A) had a homebrew tabletop RPG "GARTOK" but **lost all the rules
documentation**. The only surviving artifact is the character-generator repo
`github.com/GARCl-A/Gerenciador-Gartok` (private; cloned to
`c:\dev\Gerenciador-Gartok`). This project rebuilds a playable game from it.
**Now a git repo** (`main`, ~31 commits, all Sep 8–9 2026). The *generator*
clone at `c:\dev\Gerenciador-Gartok` is the one with no VCS.

- Python 3.14 → `pygame-ce` (no `pygame` wheel). `requirements.txt` = just that.
- `RULES.md` (was `GARTOK-regras.md`, English since 2026-09-10) — reconstructed
  *rules prose*, 🟢 recovered vs 🟡 designed. The catalog data lives in the
  generated `REFERENCE.md` (`python -m gartok.reference`). See
  [[gartok-doc-generator]].
- `data.py` tables were ported from the generator's `.xlsx` (`openpyxl` was a
  one-time port tool, not a dependency now). Weapon stats, prices and the
  mechanical effect of racial abilities were **designed here**.

## Design premises (from the user — durable)

- **Every unit is its own individual** (user: "importantíssima pro projeto
  inteiro"). Each character is themselves — own stats, own gear, own talents,
  own outcome. A shared activity resolves per-person: e.g. a fast worker
  finishes their shift early and the others finish later (the guild token only
  moves on once the *slowest* is done). One character's talent/ability never
  bleeds onto a crewmate. This is the same thread as "guild roams as ONE token"
  and "vision is per-character": the group is a container, the unit is the atom.
- **World-first.** Rules are written thinking about *the world* and how
  characters interact with it, not just combat. Combat is central, but each
  system exists first as a world thing; if it talks to combat, better. Systems
  land bit by bit.
- **Disposable early squad.** Early mortality is very high; the starting 3 are
  meant to be lost. Whoever survives the first fights becomes valuable; from
  there the player hires replacements, who also die, and so on. Resurrection is
  far-future.
- **Recruitment must mean something** — joining a guild is not a buy-a-recruit
  button. First cut shipped Sep 2026 (`recruit.py` + taverna node): a guild
  member makes the pitch, pure Charisma-vs-Charisma contest, no money (a signing
  bonus would just land in the recruit's own pack). See the Recruitment section
  below.
- **No guild treasury.** Money (copper coins) lives on the character. The guild
  *is* its roster — no hall, vault or bank. That's the seam hired hands / a
  physical base hang off later.
- **The whole guild roams the map as ONE token.** "Esquadrão" = who deploys into
  a given fight. Open world (parties splitting off, many activities) is the
  long-term vision, "megalomania" for now — the current map graph is the first
  bridge out of combat-only.
- **Vision is per-character, not per-player.** The map is always dark. On your
  turn the screen shows only what the active unit sees; `L` toggles to the squad
  union. Enemy turn = squad union.
- **Typed-bonus rule.** Same-type bonuses don't stack (highest wins); untyped
  bonuses and all penalties stack. `data.resolve_bonus()`. Types: `circunstancia`,
  `natural`, `status`.

**Text is English now** (translated Sep 2026, commits `5973ee4` UI + `f728f21`
domain data/combat). All player-facing strings AND domain content — race,
occupation, alignment, size, language, weapon, item names — are English in the
code ("Dwarf", "1kg Meat", "Lawful and Evil", "Leather Jerkin"). Identifiers
were always English. **`GARTOK-regras.md` stayed Portuguese** (design doc) — so
it and `data.py` no longer share verbatim strings; the map-node ids ("cidade",
"madeireira") are kept as save keys. A teammate does UI work on `main` in
parallel — expect the tree to move under you; branch for anything non-trivial.

## Architecture — one concern per module, adding a system usually touches one file

- **`actions.py`** — every combat action is an `Action` subclass (`cost`,
  `target`, `aimed`; `available`/`can`/`execute`/`label`/`highlight_*`).
  `PANEL_ACTIONS` drives the UI buttons; `ai.py` scores the same objects.
  Move/Attack = default board click; Throw/Demoralize/Stabilize are `aimed`.
- **`conditions.py`** — `Condition` subclasses (Defending, Demoralized):
  contribute typed mods, expire themselves. `unit.conditions`;
  `unit.has_condition(id)`; `unit.defending`/`unit.demoralized` props.
- **`abilities.py`** — `Ability` frozen-dataclass registry: numeric passives
  (`hp_max`, `speed`, `ac_natural`, `damage_reduction`, `initiative`,
  `melee_damage`, `darkvision`, `extra_languages`, `demoralize_ignores_language`,
  `carry_size`, `breaks_when_downed`) + optional hook callables (`attack_mods`,
  `feint`, `on_attack_miss`, `on_downed`, `on_turn_start`). `unit.ability`.
  Once-per-battle via `unit.spend_once(key)`. A brand-new *kind* of hook still
  needs a core call site — no plugin bus.
- **`board.py`** — `Board`: grid geometry (`COLS,ROWS = 16,12`), wall gen
  (connectivity-checked, `min_seg`/`max_seg`), `los_clear` (Bresenham +
  diagonal-corner rule), `reachable`/`path_to`/`path_step_toward` BFS (take
  `blocked`/`passable` sets + `footprint`). Pure — no battle state.
- **`vision.py`** — free fns over `battle`: `unit_light`/`ground_light` (one
  "emits light" concept), `cell_lit`, `can_see` (dist 0 always True;
  `ambient_light` drops the light requirement, LOS+range still apply),
  `can_see_unit`, plus the on-screen set (`observers`/`visible_cells`/…).
- **`ground.py`** — `GroundObject` (`kind` weapon|torch) + `Creature` (neutral
  body: no turn, not a target, blocks its cell — the Shepherd's sheep).
- **`scenario.py`** — `Scenario` base: side deployment, unit creatures, torch
  scatter; `build(battle)` populates board / positions / creatures / ground /
  `ambient_light`. `ArenaScenario` (dark pit, torches), `ErmosScenario`
  (`outdoor` → ambient light tracks `battle.daylight`, no torches). **The seam
  for objectives / prebuilt maps / deployment zones.**
- **`unit.py`** — `Unit` = the **persistent character**: a stable `uid`
  (uuid4 hex, persisted, back-filled on load — recruiter binding references it) +
  `recruited_by` (uid of the recruiter, or None) + generation +
  `_derive_combat` (now an orchestrator: `_derive_carry` → `_derive_attribute_mods`
  → `_derive_hp` → `_derive_ac` → `_derive_speed`, that dependency order matters;
  folds ability passives + hunger + encumbrance + armor + talents) + hunger + the
  persistent loadout (`equipped_weapon`/`equipped_offhand`/`_base_inventory`) + roster item
  shuffling (`give_to_hand` …) + a few read-only combat previews (`ac`, `weapon`,
  `load`, `ranged`, `mental_defense` — condition-free) so roster screens need no
  Combatant. `from_save` bypasses `__init__`. **No battle state here.**
- **`combatant.py`** — `Combatant(char, team)` = a Unit *inside one battle*.
  Owns hp / ap / pos / `status` (`up|dying|stable|broken|fled|dead`) /
  `death_clock` / `conditions` / `weapon_hand` / `torch_hand` / `weapon` /
  `inventory` / `ammo` / `first_aid_charges` / `initiative`, and every battle
  behaviour (attack rolls, `take_damage`, `go_down`, `start_turn`/`end_turn`,
  equip/drop). `__getattr__` delegates every other read to `self.char`. A fight
  never touches the roster; `reset_battle_state` re-seeds from the character.
- **`battle.py`** — `Battle` holds board / units / ground / creatures / turn
  order; **wraps each character it is given in a `Combatant`**. Turn flow,
  initiative, falling / stabilize / death, `_check_winner`. Combat resolution
  lives in `actions.py`.
- **`ai.py`** — heuristic over `actions.py`, sees through each unit's own eyes.
  Tendency (alignment axes) tempers the edges: **evil** finishes downed enemies,
  **good** stabilizes a downed ally first, **chaotic** flees sooner, **lawful**
  holds the line. No pathfinding to an ally / to the map edge yet.
- **`loot.py`** — `field_loot(battle, fallen_combatants)` → sorted item names
  from defeated enemies' + fallen allies' on-field kit + `battle.ground`.
- **`progression.py` / `talents.py`** — leveling (see Progression section). Pure
  data + one rule fn; no gartok imports, so safe to import anywhere.
- **World / campaign — restructured Sep 2026 by the Guild→Groups→Units refactor,
  see [[gartok-groups-refactor]] for the full design + build log.** `world.py`
  (Node graph, `EDGES` in hours, `route` Dijkstra, `ARENA_TIERS`/`arena_offers`;
  node kinds town/battle/market/**taverna**), `recruit.py` (recruitment contest +
  the weekly taverna pool — see its section; `enlist` joins the recruiter's own
  `Group`), `clock.py` (`Clock` seconds, daylight 06–18), `group.py` (**new** —
  `Group` = a physical subset of the guild: `members`/`node`/`order`; every unit
  is in exactly one group, even solo), `guild.py` (`Guild.groups: list[Group]` is
  now the real state; `roster`/`node` are read-mostly Phase-1-style shims over a
  single group, kept for the ~50 single-group test/construction call sites but
  ambiguous with >1 group — `group_of`/`add_member`/`remove_members` (the real
  mutation path, prunes emptied groups)/`split_group`/`merge_groups` (same-node
  only) are the group-aware API; `pass_time(hours)` → daily hunger upkeep,
  `_shared_larder` scoped to the eater's own group (see
  [[gartok-food-sharing]]); `gold` = sum over the roster), `orders.py` (**new** —
  `Order(kind, eta, remaining, dest, hours)`; `AUTO_KINDS={travel,work}` resolve
  silently, `INTERACTIVE_KINDS={arena,market,bank,recruit,hunt}` hand back to a
  screen), `campaign.py` (`absorb_battle(...)` unchanged in shape, now calls
  `guild.remove_members`; **`advance(guild, dt=None)`** is the tick engine — jumps
  to the soonest order completion (or a forced `dt`, used by MAINTENANCE so an
  order in flight can't drift out of sync with the clock), returns
  `TickResult(events, pending, wiped)`), `factions.py` (factions + one-shot deeds
  → reputation, see [[gartok-factions-reputation]] — unaffected, already
  node-parameterized), `economy.py` (`PRICES`, `MARKET_STOCK`, `market_deal` /
  `buy_price` / `sell_price`, `STARTING_WEALTH_DICE`), `persist.py` (JSON slots,
  atomic write; save v7 = `"groups": [{gid,name,node,members}]` replacing flat
  `"roster"`/`"node"`, falls back to one group for an older save; `SAVE_VERSION`
  stamp exists, no migration beyond that fallback — fine while runs start fresh).
- **`app.py`** — pygame shell: every scene draws straight to the real window
  (`native = True`, lays out from `screen.get_size()`); screens read `self.mouse`.
  Loop: `menu → draft → MAP ⇄ guild`. On the map you select a `Group` and issue
  it an order (travel / work / an on-node activity); **ADVANCE** →
  `app._advance()` → `campaign.advance` → drains `TickResult.pending` one screen
  at a time via `_after_activity` (the shared on_done/on_back target for every
  activity screen): `squad → battle → loot/reward → [next pending] → MAP`,
  `party → market/bank/taverna → [next pending] → MAP`. Market/Bank/Taverna/Hunt
  no longer party-pick from the whole roster — the resolving group's own
  `.members` **is** the party; `SquadScreen` survives only for the Arena (squad
  size vs. stake tier is still a real choice). **`WorkScreen` is deleted** — work
  is a fully silent order now, resolved into notices like travel, never a
  screen. `_battle_end` still calls `campaign.absorb_battle`, then
  `_after_activity` instead of going straight to the map. Autosaves after the
  draft / every map return / every battle.
- **Screens** — `screen.Screen` base folds the shared plumbing (`self.mouse`,
  left-click → `self._click`, no-op `update`); each screen adds `draw(surface)`
  and its `_click`. menu / draft / map / guild / squad / battle / loot / reward /
  market / taverna / **work** / **level**. Roster screens read `Unit`'s preview
  props directly; the full-sheet modal wraps the member in a throwaway `Combatant`.
  `guild_screen` + `level_screen` are `native = True` (draw straight to the
  window at real size, `W,H = screen.get_size()` responsive layout — crisp on
  resize); the rest still draw to the fixed canvas. `app` branches on
  `getattr(scene, "native", False)` (`_scene_pos` / `_blit_scene`). Migrating the
  other screens to native is a separate track (teammate's UI work).

## Rules implemented (see GARTOK-regras.md for the full spec)

2 AP/turn (every action costs 1). Movement: enemies + neutral creatures block
passing and stopping, allies you cross but don't end on; two walls at a corner
block the diagonal squeeze (move + LOS). d20 combat: init `d20+Des`, attack
`d20+mods` vs AC, crit 20 / fumble 1, finesse = max(FOR,DES), unarmed die by
size. Throw (Adaga only, 6 sq). PickUp (self/adjacent). Demoralize (12 sq, mutual
sight + shared language; Kenku bypasses on offense). Falling → dying → death save
on the 3rd own turn (d20 ≥ 11); automaton → broken (ally repairs, INT vs 15);
non-lethal bout → knocked out, nobody dies. Flee (map edge, deterministic escape
check, drags adjacent downed allies). Ammo (Aljava 20, not recoverable) →
improvised melee at 0. Flanking: strict = +2 circ to all, loose feeds only Goblin
pack tactics. Light: darkvision 12 sq, torch 4 sq, Lanterna 9 sq. Hunger: one
meal/day travelling, tiers −2 / −4+hp1 / incapacitated / dead@4d (Leshy exempt).
Economy: 5d10 copper on the character, market common purse + haggle (language +
CHA + alignment distance, sell always below buy), arena staked non-lethal bouts
unlocked by `arena_reputation`.

## Recruitment (first cut, Sep 2026)

`recruit.py` + `taverna_screen.py` + a `taverna` world node (`cidade↔taverna`
1 h). Flow: MAP → taverna → `SquadScreen` party picker → `TavernaScreen`.

**The pool.** `TAVERNA_SIZE = 3` strangers live on the `Guild`
(`taverna_pool` / `taverna_week` / `taverna_blocked`, all persisted). Same faces
across every visit until `REFRESH_DAYS = 7` pass — `recruit.refresh_pool(guild)`
re-rolls the crop and clears the bars when `current_week(clock)` turns over
(`(clock.day − 1) // 7`). A hire is `pool.remove`d permanently (until refresh).

**The pitch.** Pick a stranger, pick the party member who talks.
- **`recruit.convince(recruiter, candidate, roster_size, rng=random)`** →
  `Pitch` dataclass (full roll breakdown for the screen). Gate: a **shared
  language** (`can_pitch`) or no pitch. Contest: `d20 + recruiter CAR mod + mods`
  **must strictly beat** `d20 + candidate CAR mod` — **a tie goes to the
  stranger**. Mods on the recruiter's side: `−1 × alignment_distance` (0..4) and
  `−1 × size_penalty(roster_size)`, `size_penalty(n) = max(0, n − FREE_SLOTS)`,
  `FREE_SLOTS = 2` — **the balance lever** (bigger guild → harder to recruit;
  ramps *within* a visit as hires land). All tuning constants at the top of
  `recruit.py`.
- **No money** (user dropped the signing-bonus idea — it would just land in the
  recruit's own pack).
- **One shot per (stranger, recruiter) pair per week.** A failed pitch calls
  `recruit.bar` → `[cand.uid, recruiter.uid]` into `taverna_blocked`; another
  member can still try that stranger. Bars clear on the weekly refresh.
- **`recruit.enlist(guild, candidate, recruiter)`** sets
  `candidate.recruited_by = recruiter.uid`, appends to roster, removes from pool.
  Binding is **inert for now** — shown as "recrutado por X" on the guild card
  (uid→name via the live roster; "alguem que ja se foi" if the recruiter is
  dead). Seam for future morale / desertion.

## Open gaps / candidates (user-hinted, not requested)

Morale / the recruiter bond doing something (user: "depois"). AI pathfinding to a
downed ally / the map edge. Fatigue/wounds (the eventual
non-lethal-arena risk). Torch fuel/duration. Multiple parties.
A dedicated `RuinasScenario` (Ruinas reuses
`ArenaScenario`, lethal — user says fine for now). Magic. Neutral-creature AI.
Un-`OK` racial-ability effects are still guesses.

**Scenario objectives beyond "eliminate all" — SEAM DONE** (2026-09-09,
[[gartok-wilds-hunting]]): `Scenario.win_check(battle) -> "player"|"enemy"|None`,
consulted first in `_check_winner`. Inert (no override yet); ready for a
non-battle-win faction deed.

**Enemy scaling — DONE** (2026-09-09, [[gartok-wilds-hunting]]): `encounters.py`
builds packs at a target mean level. The Wilds uses it (levels 0..4); the staked
arena tiers too (Sep 2026, `world.Bout.level` 0/1/2/3, via `gartok/matchup.py` —
`build(node, offer, *, squad_size, guild) -> (enemies, scenario)`, pulled out of
`app._start_battle`).

**The Wilds is now an activity node** ([[gartok-wilds-hunting]]) — `kind="wilds"`,
first activity is Hunt (meat + per-hour ambush risk). The map loop gained
`map -> hunt party picker -> HuntScreen <-> ambush battle`.

**Name generator** — done Sep 2026 (`gartok/names.py`, commit after the champion
map wiring): `names.random_name()` (2–4 syllables, own `random.Random()` stream so
it never disturbs the seeded global sequence). `Unit.__init__` / `set_name("")`
call it instead of the `"Race Occupation"` label; screens still show
`race · occupation` as a separate subtitle. Authored NPCs keep their own names.

**Progression (built Sep 2026, branch `feat/leveling`).** No classes — each XP
track has its own level + talent tree (user grows the trees by hand, node by
node). `progression.py` = curves (`COMBAT_XP_THRESHOLDS` L1=3/L2=10 fixed, rest
stub; `WORK_XP_THRESHOLDS` stub) + `xp_award(atk_lvl, vic_lvl)` = `vic-atk+1` if
`vic>=atk` else 0. `talents.py` = `Talent` frozen-dataclass registry mirroring
`abilities.py`; tier 1 + 2 built (see [[gartok-talent-trees]] for the node spec
and the `Effect(channel, amount, stat)` model that replaced the typed knobs).
`Unit`: `talents` dict + `_level_hp_rolls` (persisted, save v2);
props `combat_level`/`work_level`/`mean_level`/`pending_picks`/`picks_available`;
`choose_talent` / `collect_levels` (rolls `1dHD+modCon` per mean-level gained,
idempotent, called on XP gain not load); `talent_bonus(channel, stat="")` is the
one resolver (was `_talent_sum` / `_talent_attr`). `_apply_attributes` folds
talent +score alongside racial mods. `Combatant.credit_kill(victim)` replaces `kills+=1` at the
two down sites (`actions._resolve_hit`, ferocity `end_turn`) — `kills` stays a
count, `combat_xp_earned` accrues the level-scaled XP; `campaign.absorb_battle`
folds it + `collect_levels()`. `guild.work_shift` calls `collect_levels()`.
`level_screen.py` (native) opened from the guild card (`GuildScreen(on_level=)` →
`app._open_level`, autosaves via `on_change`). (Enemies were all level 0; the
Wilds, arena tiers and the Games now scale — see the enemy-scaling note above.)
Roots are **not** mutually exclusive — taking a 2nd/3rd root with a later level's
pick is fine by design (user confirmed); `group` field in `talents.py` is a TODO
for if that changes. Curve past L2 is a stub.

**Armor (added Sep 2026).** `data.ARMOR` table: `ac` / `max_dex` (Dex-to-AC
cap, None = uncapped) / `speed` (squares shaved, floored at 1) / `weight`.
5 tiers Gibao de couro → Armadura de placas; buy price in `economy.PRICES`
(20 / 55 / 160 / 400 / 950 — steep on purpose, plate = many arena purses),
all in `MARKET_STOCK`. `unit.equipped_armor` (persisted) + `armor` /
`armor_name` props; `_derive_combat` folds AC + Dex-cap + speed penalty;
`give_to_armor` / `take_from_armor` re-derive. Guild screen has a CORPO slot;
market shows/sells worn armor. Combatant reads it through delegation — no
Combatant changes.

**Encumbrance (added Sep 2026).** `unit.encumbered` = `load > carry_normal`;
while set: −2 FOR score, −2 DES score, −1 speed (folded into `_derive_combat`,
parallel to hunger — the −2 is to the *score*, so ~−1 to the mod). `carry_normal`
/ `carry_max` are computed from the hunger-adjusted (not encumbrance-adjusted)
Strength — the penalty must not feed back and shrink its own threshold.

Carry formula reworked at the same time (user chose the "lean" target, size
multipliers left alone): `carry_normal = max(1, round((mod_FOR*4 + 15) * cm))`,
`carry_max = max(2, round((mod_FOR*6 + 35) * cm))`. A normal person (FOR 10,
Medio) = **15 / 35 kg**; each FOR mod point is +4 / +6. Deliberately tight —
a FOR-10 character in a chain shirt + basic kit *is* encumbered; that's the
intended feel. Default gear now tips ~4 % of raw recruits over `carry_normal`
(down from ~14 %), all extreme-low-FOR small races near the floor. `cm` still
Diminuto 0.5 / Pequeno 1.0 / Medio 1.0 / Grande 2.0 (Pequeno == Medio — user
knows, left as-is for now). 200-battle sim ~unchanged (avg rounds ~5.15).

## Architecture pass (done 2026-09-08, after the doc cleanup)

The four risks flagged in the review were all addressed:
- **`Character` / `Combatant` split** — `Unit` is now purely the persistent
  character; `combatant.py` holds battle state + behaviour and delegates reads.
  Battle wraps instead of deep-copying. `_sync()` / `reset_battle_state` calls
  gone from the roster screens (`Unit.load` etc. compute from the loadout).
- **`campaign.py`** extracted from `app._battle_end` (`absorb_battle` →
  `BattleOutcome`).
- **`screen.Screen`** base class — all 9 screens subclass it; `theme.token_badge`
  widget replaces the copy-pasted token circle.
- **`economy.py`** peeled off `data.py` (prices / stock / haggling). Dice +
  `resolve_bonus` deliberately kept in `data.py` — fine there.

RNG streams and the 200-battle sim came out byte-identical, so battle behaviour
was preserved exactly. 88 rule tests green.

Doc drift is now guarded: `REFERENCE.md` is generated from the tables and a test
fails if it is stale (2026-09-10, [[gartok-doc-generator]]).
**No save version/migration** (deferred — runs start fresh). (Scenario objectives:
`Scenario.win_check` seam added 2026-09-09 — see above.)

## Tests

`tests/` package — one file per domain, ~208 rule tests, shared fixtures in
`tests/helpers.py`. Run: **`python -m pytest tests/`** (split from the old single
`test_gartok.py` on 2026-09-10, [[gartok-doc-generator]]).
`sim_test.py` — 200 headless AI-vs-AI battles
(avg ~4.93 rounds, 0 stalls since the [[gartok-z-axis]] work rewrote
`board.path_step_toward` to route over the whole board — the old "byte-identical"
RNG stream no longer holds, and `main` itself had 9/200 stalling seeds before).

**Doc-drift swept 2026-09-08** (session after the food-sharing commit): the
`campaign.py` / `persist.py` / `loot.py` docstrings that still said "Battle
deep-copies the roster" now say it wraps each unit in a `Combatant`. Nothing else
in the repo repeats the deep-copy wording.
