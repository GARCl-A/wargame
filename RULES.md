# GARTOK — the ruleset, reconstructed from the generator

This document reconstructs the **GARTOK** system from the one artifact that
survived: the character generator (`Gerenciador-Gartok`). It is split into:

- 🟢 **Recovered** — literally present in the generator's code / spreadsheets.
- 🟡 **Designed** — did not exist; created for the wargame, in the d20 style of
  the rest.

The **catalog data** — every race, occupation, racial-ability effect, weapon,
armor, price, talent and tunable constant — is generated from the code into
[`REFERENCE.md`](REFERENCE.md) (`python -m gartok.reference`). This document keeps
the *rules prose*: the formulas, the combat resolution, and the design premises.
Where the two disagree, `REFERENCE.md` (straight from the registries) is right.

> **The `Status: OK` mark** on a race/occupation row in the generator was the
> author's hand annotation: `OK` = that row has been revisited and its
> effect/item is the intended one, not the first inference. It does not survive
> into `REFERENCE.md`; the 🟡 racial-ability effects that are still first guesses
> are called out in `abilities.py`.

---

## 1. Attributes 🟢

Six attributes, each rolled with **3d6** (values 3–18):

`Strength · Dexterity · Constitution · Intelligence · Wisdom · Charisma`

**Modifier** = ⌊(score − 10) / 2⌋ — so 3 → −4, 10–11 → 0, 18 → +4.

After the roll, the **racial modifiers** are added (see `REFERENCE.md`).

---

## 2. Character creation 🟢

The generator's exact order:

1. Roll the 6 attributes (3d6 each).
2. Roll **race** (d100) → apply the racial mods, set the hit die, size, language,
   racial ability and age band.
3. Roll **occupation** (d100) → set the starting weapon and one starting item.
4. Roll **alignment** (d100).
5. Roll **starting gold**: **5d10 copper coins**.
6. The character starts at **Level 0, XP 1000**. 🟢 *(the meaning of that
   progression did not survive — see §9 and the Progression section.)*

---

## 3. Derived values 🟢

| Derived | Formula | Note |
|---|---|---|
| **AC** (Armor Class) | `10 + Dexterity mod` | unarmored (worn armor: 🟡, see below) |
| **Mental Defense** 🟡 | `10 + Wisdom mod` | the target number for Demoralize |
| **HP** | `1d(hit die) + Constitution mod` | minimum 1 |
| **Age** | `d100 × racial multiplier` | see `REFERENCE.md` |
| **Carry capacity (normal)** | `max(1, round((STR mod × 4 + 15) × carry mult.))` | 🟡 reworked for the wargame |
| **Carry capacity (high)** | `max(2, round((STR mod × 6 + 35) × carry mult.))` | 🟡 |
| **Unarmed attack** 🟡 | die by size (Tiny/Small 1d2 · Medium 1d3 · Large 1d4) | everyone has one; STR mod adds to the damage |

> Generator quirk: HP used `randrange(1, hit_die)`, i.e. it rolled **1 to
> (die−1)**. The wargame uses the full die (1 to die), the presumed design intent.

The **base carry multiplier** by size (Tiny 0.5 / Small 1.0 / Medium 1.0 /
Large 2.0) is unchanged; Goliath's "Strong Body" counts it as Large for carry
only. The formula itself was reworked 🟡 — deliberately tight: a Strength-10
Medium character in a chain shirt and a basic kit *is* encumbered.

---

## 4. Races 🟢

18 races, rolled on a d100 with cumulative thresholds. Each sets six attribute
mods, a hit die, a size, a language, a racial ability and an age multiplier.

**The full table is in [`REFERENCE.md`](REFERENCE.md)** (§ Races). The ability
*names* are 🟢; **what each one does is 🟡** — see §7.

Languages in the world are just the racial languages — names only, no
description survived: Ankarin, Draconic, Dwarvish, Elvish, Gnomish, Goblin,
Halfling, Jotun, Orcish, Sylvan, Verdant. A character isn't stuck with the
languages they rolled — see "Learning a language" below.

---

## 5. Sizes 🟢 / 🟡

| Size | Speed | Carry mult. | Footprint |
|---|---:|---:|---:|
| Tiny | 4.5 m (3 sq) | 0.5 | 1 cell |
| Small | 6.0 m (4 sq) | 1.0 | 1 cell |
| Medium | 9.0 m (6 sq) | 1.0 | 1 cell |
| Large | 9.0 m (6 sq) | 2.0 | **2×2 = 4 cells** |

In the wargame **1 cell = 1.5 m**. 🟡

- **Base speed does not change with size**: a **Large** creature moves the same
  as a **Medium** one (9 m / 6 cells). If a Large creature moves further, it is
  from an **ability** — the **Centaur** reaches 12 m (8 cells) only because of
  **Gallop** (+3 m), not because it is large.
- **Large creatures occupy 2×2 cells.** The stored position is the **anchor**
  (top-left); the footprint is the 4 cells from there. It applies to everything:
  collision and pathfinding (only lands where all 4 cells fit and are free),
  **reach** (melee = footprint adjacent, minimum cell-to-cell distance), **line
  of sight** and **light** (sees / lights from any footprint cell). Implemented
  in `board.cells` / `board.fits` and `Battle.cells_of`, `units_distance`,
  `los_between`, `reachable(..., footprint)`.

---

## 6. Occupations 🟢

31 occupations, rolled on a d100 (cumulative thresholds). Each grants **one
weapon** and **one item**. **The full table is in [`REFERENCE.md`](REFERENCE.md)**
(§ Occupations).

---

## 7. Racial abilities — effects 🟡

Only the **name** of each ability came from the generator; the effects were
designed for the wargame (each is an `Ability` in `gartok/abilities.py`: numeric
passives and/or hooks). **The full list with effects is in
[`REFERENCE.md`](REFERENCE.md)** (§ Racial abilities).

The design choices worth stating in prose:

- **Darkvision** — sees 12 cells (18 m) in the dark as if lit.
- **Inorganic Body** (Automaton) — at 0 HP goes *broken* instead of dying: no
  death save, no clock, waits for an ally to repair it (Stabilize: `d20 + INT`
  vs DC 15, back on its feet at 1 HP). Lost with the squad on a total defeat.
- **Ferocity** (Orc) — once per battle, the blow that would down the Orc takes it
  to 0 HP and *dying*, but it keeps acting until the **end of its own turn**;
  only then does it fall and the clock start. A second fatal hit before that
  drops it immediately.
- **Pack Tactics** (Goblin) — drops the "opposite sides" requirement of a flank:
  the attacker and one ally both adjacent to the target is enough (+2
  [circumstance]). Being circumstance, it does not stack with a strict flank.
- **Extra Language** (Human) — a second random language; can Demoralize anyone
  who shares either tongue. This is the Human's edge in market haggling too.
- **Mimic Sounds** (Kenku) — may Demoralize with no shared language (offense
  only); does **not** help haggling.
- **Autotroph** (Leshy) — photosynthesises: never eats, immune to the hunger
  rules.
- **Flight** (Sprite) — moves freely in three dimensions (up and down pits with
  no check, ignores terrain) and never takes falling damage. No numeric bonus.
- **Climber** (Lizardfolk) — climbs any surface of DC 25 or lower with no check
  (still spends the action).
- **Amphibious** (Grippli) — breathes water: never runs out of breath while
  submerged, so it can stay underwater indefinitely and never drowns. (Was a flat
  +1 speed; reworked when water terrain landed.)

**Placeholder effects — to revisit when the relevant mechanic exists** (these
carry a stand-in combat bonus today so the ability is never inert; `REFERENCE.md`
lists only the current effect):

- ~~**Strong Stomach** — migrated: can eat rotten food safely.~~
- ~~**Primal Blood** → **Nature Magic** — migrated: Gnome starts initiated in
  nature magic with one random cantrip.~~
- **Keen Hearing** — now `+3 initiative`; becomes *a bonus to hear/notice things*
  once perception is a mechanic.
- ~~**Ancestral Blood** → **Blood Magic** — migrated: Kobold starts initiated in
  blood magic, +2 to spell study rolls.~~

---

## 8. Alignment 🟢 / 🟡

Rolled on a d100 (cumulative). Two axes: **order** (Lawful / Neutral / Chaotic)
and **morality** (Good / Neutral / Evil) — nine combinations, listed in
`REFERENCE.md`.

No **known** mechanical effect in the generator (🟢). The wargame gives it
weight 🟡:

- **Market spread** — the distance between the buyer's alignment and the
  vendor's tightens or loosens the price (`data.alignment_distance`, 0–4).
- **AI behaviour** — evil delivers a coup de grace, good stabilizes and drags the
  wounded out, chaotic flees sooner, lawful holds the line.
- **Recruitment** — alignment distance docks the recruiter's pitch.

---

## 9. Gaps — what the generator does NOT preserve

None of this exists in the generator; it had to be reinvented for a playable
game:

- **Combat**: initiative, actions per round, attack/damage, criticals, reach.
  → the wargame proposes a version (Combat section below).
- **Progression**: what Level / XP mean; characters start at Level 0 / XP 1000.
  → rebuilt from scratch (Progression section below).
- **Skills / attribute checks**: presumably `d20 + mod` vs a difficulty.
- **Magic**: no caster class appears in the generator; "Primal Blood", "Holy
  Symbol" and "Scroll" hinted it existed. A first system now does (see
  "Magic" below) — three spells, a racial-talent path to a magic source, and
  a slow study-at-the-tavern path to learn more. Still early: only three
  spells exist.
- **Weapons and equipment**: damage, weight, price are set; **armor and shields
  are not** — the wargame designed a five-tier armor table 🟡.
- **The effect of the racial abilities** (§7).
- **Death**: the wargame defines falling / stabilizing / permadeath (Combat
  section). Survivors return at full HP; there are no persistent wounds, fatigue
  or rest along the clock — yet.

---

## Progression 🟡

Curves and the XP rule in `gartok/progression.py`; trees in `gartok/talents.py`;
state on the `Unit` (`talents`, `_level_hp_rolls`); screen in
`gartok/level_screen.py` (opened from the member card on the Guild screen).

> **No classes, no class level.** Each **XP track** has its own level and its own
> **talent tree**. The more a character does a job, the better they get at it.
> The trees grow by hand, node by node.

**Tracks today:**

| Track | XP | Source |
|---|---|---|
| Combat | `combat_xp` | downing enemies (below) |
| Work | `work_xp` (marks, 1 per 16 h) | lumber-yard shifts, wilds hunts |
| Racial | `combat level + work level` | every level in another track feeds it |

**Level per track** — cumulative thresholds in `progression.py`, a first guess,
tunable. Combat: L1 = 3 XP, L2 = 10 XP (fixed by the author); past L2 is a stub.
Each level in combat and work grants **one pick** in that track's tree. The **racial
track** earns no XP of its own — its "XP" is the sum of the other track levels
(`RACIAL_XP_THRESHOLDS`), so it rises as the character grows anywhere. While hit
dice scale with every racial level (L1+), the **first racial talent pick unlocks
only at Racial Level 5** (`max(0, racial_level - 4)`). Its nodes are **race-gated**
(e.g., `Tongue` for Grippli, `Fruitful` for Leshy, `Cosmopolitan` for Human,
`Halfling Luck` for Halfling).

**Combat XP — only from enemies at your level or above.** Downing a standing
enemy is worth `(their combat level − yours) + 1`, and **nothing** if they are
below you. L0 kills L0 → +1; L0 kills L10 → +11; L3 kills L0 → 0.
(`progression.xp_award`; credited in `Combatant.credit_kill`, doubled at the end
of the battle by `campaign.absorb_battle`.) Wilds packs scale 0–4; the Games run 1–6.

**Talent trees** — general → specific: a tier-1 root is a broad identity; each
step deeper specialises the character in one action. **No pick is mutually
exclusive** (the `group` field is reserved): one pick per track level, filled in
any order, and over enough levels a character can hold every node. A deeper node
just needs the one above it first (`requires`), which chains down the branch. The
first tier-3 node is `Fleet` (+1 Speed, behind Deadeye). The node list with
effects is in [`REFERENCE.md`](REFERENCE.md) (§ Talent trees).

**Hit die by racial level.** Each racial level grants a hit die: `1d(racial HD) +
CON mod` (min 1), added to max HP. The rolls are saved (`_level_hp_rolls`) —
reloading does not re-roll. The scale is set to match the old `⌊(combat + work) /
2⌋`, but it now moves with *any* track and can be pinned directly in the
character creator. `mean_level` survives only as the encounter-difficulty scalar.

---

## Magic 🟡

State on `unit.py` (`magic_source`, `spells_known`, `study_target`,
`study_progress`); the registry in `gartok/magic.py` (`Spell(id, name, level,
sources)`); casting in `actions.py`'s `CastSpellAction` (+ `ShareMagicAction`
for the Sprite); AI use in `ai.py`; the `Sleeping` condition in
`conditions.py`. A first foothold, not a full system — three spells today.

- **Sources.** `magic_source` (`nature` / `blood` / `faith`) gates which
  spells a character can ever learn. It comes from a race (Gnome starts
  `nature`, Kobold starts `blood`) or a racial talent (the Kenku's "Faith
  Initiate", the Sprite's "Nature Initiate").
- **Casting** costs 1 action point and only shows up once the spell's id is
  in `spells_known`:
  - **Magic Missile** (level 0) — ranged (6 cells), `d20 + INT` vs AC, `1d4`
    damage on a hit; a natural 20 crits (rolls the die twice), a natural 1
    fumbles with no effect.
  - **Sleep** (level 1) — ranged (6 cells), `d20 + INT` vs the target's
    Mental Defense; a hit applies `Sleeping` (`−2 status` to AC). A race with
    the **Sleep Immunity** ability (the Elf) is never affected.
  - **Light Globe** / **Floating Disk** (level 0) — drop a ground object at a
    cell in range (6 cells): a light source, or a rideable/carryable disk.
  - **Share Magic** — a Sprite Nature Initiate's own action: spends a point
    to teach a random ally one of its known spells for the rest of the
    battle.
- **Learning a spell** happens outside combat, at the Tavern
  (`taverna_screen.py`'s "rent a quiet room" button issues an
  `orders.garrison("study")` order — the same engine the garrison jobs use,
  see Property below). Each day the order holds, a member with a
  `study_target` set and the matching `Scroll of <Spell>` in their pack pays
  `economy.TAVERN_STUDY_COST_PER_DAY` (15 copper) and rolls `1d20 + INT mod`
  toward `magic.points_to_learn(spell)` — `(15 + level) × (level + 1) × 7`
  points, so a level-0 spell needs 105 (roughly a week of daily rolls) and
  Sleep (level 1) needs 224. No gold, no scroll, or no `magic_source` yet all
  mean no progress that day (the room is still paid for if the gold is
  there). Hitting the threshold banks the spell and clears the study slot.
- **Setting a study target**: right-click a `Scroll of <Spell>` on the Gear
  screen for a "study" row on the send-to menu (the same idiom the locked
  chest uses for "open") — offered once the character has a `magic_source`
  and doesn't already know the spell, and toggles off the same way. The
  sandbox character editor has the identical control for authored NPCs.

### Learning a language 🟡

Same process as learning a level-0 spell, minus the `magic_source` gate — any
character can pick this up. `magic.language_for_dictionary` and
`magic.progress_study`'s language branch do the work; state still lives on
the shared `Unit.study_target` / `study_progress` pair, so a character is
always studying at most one thing (a spell *or* a language, never both).

- **The item**: a `Dictionary of <Language>` in the pack. The **Linguist**
  occupation starts with one, naming a language *other than* the one they
  already speak (`unit._configure_occupation`).
- **Cost**: `magic.points_to_learn(0)` = 105 points, the same threshold as a
  level-0 spell (roughly a week of daily `1d20 + INT mod` rolls at the
  Tavern's "study" garrison job), no `magic_source` bonuses involved.
- **Setting a study target**: right-click a `Dictionary of <Language>` on the
  Gear screen for a "study" row — offered once the character doesn't already
  speak it. Same toggle idiom as scrolls; the sandbox character editor has
  the identical control.
- Hitting the threshold appends the language to `Unit.languages` — it
  immediately counts for Demoralize, haggling and recruitment (all gated on
  `languages`, see §7 and Property/Economy below).

---

## The wargame's combat 🟡 (proposal)

Where each part lives: the persistent character in `gartok/unit.py`, the
combatant in a battle (HP, AP, conditions, hands, combat behaviour) in
`gartok/combatant.py`, actions in `gartok/actions.py`, conditions in
`gartok/conditions.py`, abilities in `gartok/abilities.py`, vision/light in
`gartok/vision.py`, board/pathfinding/LOS in `gartok/board.py`, ground objects
and neutral creatures in `gartok/ground.py`, map assembly in
`gartok/scenario.py`, picking the opponents + map for a given fight in
`gartok/matchup.py`, turn flow in `gartok/battle.py`.

> **Design premise:** the rules are written thinking about *the world* — how
> characters interact with it — not just about combat. Combat is the central
> mechanic, but each system exists first as a world thing; if it talks to combat,
> better. Systems land bit by bit.

### Action points

- Each character has **2 action points per turn**.
- **Attack**, **Walk** and **Defend** cost **1 point** each.
- Combine freely: walk+walk, attack+attack, walk+attack, attack+defend…
- **Walk** (1 point) = move up to the unit's speed in cells (8 directions). A
  walk can be split across several clicks until the speed is spent; then walking
  again costs another point.
  - **Diagonals alternate 1-2-1-2** (the 3.5/Pathfinder rule): a straight step
    costs 1; the 1st diagonal costs 1, the 2nd costs 2, the 3rd costs 1, and so
    on — it approximates √2 with integers. The count is **per Walk action**: the
    fractions of one walk share the alternation; a fresh Walk restarts from 1.
    Held in `Combatant.diag_steps`; a route's cost comes from `board.path_cost`
    (which also adds `+1` for each difficult-terrain cell entered).
  - **Enemies block completely:** you cannot stop **or pass through** an enemy's
    cell (nor a neutral creature's, like the Sheep).
  - **Allies you can cross**, but not end your move on.
  - The pathfinding is Dijkstra over `(cell, diagonal parity)`.
- **Defend** (1 point) = **+1 circumstance bonus** to AC until the start of your
  next turn.
- **Throw** (1 point) = throws the weapon in hand, if it is a **thrown weapon**
  (for now only the **Dagger**, range 9 m = 6 cells). See below.
- **Lash** (1 point) = the Grippli's **Tongue** attack — the 1-handed weapon in
  the `equipped_tongue` slot, swung at **+1 cell of reach**. A separate action, so
  a Grippli chooses each turn between the reach lash and the hand weapon (e.g. a
  2-handed Broadsword). The tongue is a third limb; it does not use a hand.
- **Pick Up** (1 point) = picks up a `ground.GroundObject` in your cell or
  adjacent: a weapon only if you are **unarmed**; a torch for anyone (armed = a
  swap).
- **Demoralize** (1 point) = a verbal provocation up to **18 m (12 cells)**.
  See below.
- **Stabilize** / **First Aid** (1 point) = try to bring a downed ally back to
  `stable`. See below.
- **Flee** (1 point, ends the turn) = leave combat by the map edge. See below.
- **Climb / Push / Jump / Drop In** (1 point) = the Z-axis moves. See below.

### Typed bonuses — the core rule

> **Bonuses of the same type do not stack** — only the largest applies.
> **Untyped** bonuses and **all penalties** add normally.

Implemented in `data.resolve_bonus()`. Types in use: `circumstance`, `natural`,
`status`. Example: Defend (+1 circ. to AC) does not stack with any other
circumstance bonus to AC; Pack Tactics (+2 circ. to attack) does not add to the
+2 of a strict flank — a Goblin flanking gets +2, not +4.

### Initiative and attack

- **Initiative**: `d20 + Wisdom mod` (+ racial bonus, + the Quick Wits talent).
  Decreasing order, fixed for the battle.
- **Attack**: `d20 + mods` vs the target's `AC`.
  - base mod = `Strength mod` (melee), `Dexterity mod` (ranged / thrown), or the
    **better of Strength and Dexterity** (a *finesse* weapon).
  - other mods are typed and pass through the accumulation rule above.
  - **natural 20** = automatic hit + crit (roll the damage die twice).
  - **natural 1** = automatic miss.
- **Flanking**: `+2 [circumstance]` to the attack when the attacker **and** an
  ally are both adjacent to the target and on **opposite sides** — the line
  between their cells crosses the target's footprint. Pack Tactics (Goblin) drops
  the "opposite sides" requirement. Both being circumstance, flank and Pack
  Tactics do **not** add (+2, never +4).
- **Damage**: `weapon die (+ Strength mod if melee)`, minimum 1, minus the
  target's damage reduction.
- **Reach**: melee = adjacent cells; ranged = the weapon's range in cells; the
  Grippli **Tongue** lash = melee + 1 cell.
  Distance between units = the **shortest distance between the two footprints'
  cells**. It uses the **diagonal metric** (`board.grid_distance`:
  `max + min // 2` — diagonals alternate 1-2), so every reach radius is an
  **octagon**, not a square. Adjacency (`≤ 1`) is the same in both metrics, so
  melee, Pick Up, Stabilize and flanking do not change.
- **Line of sight**: a ranged attack and a throw need **clear LOS** *and* to
  **see** the target (see Vision). Melee (adjacent cell) does not require sight.

### Falling, stabilizing and death 🟡

States and the clock in `combatant.py`; the `Stabilize` / `FirstAid` actions in
`actions.py`; turn flow and victory in `battle.py`.

> **Design premise (from the author):** at the first levels mortality is very
> high and the starting squad is **disposable**. Whoever survives the first
> fights becomes valuable; from there the player hires replacements, who also
> die, and so on. Resurrection is a far-future concern.

**A unit's states:**

| State | What it is |
|---|---|
| `up` | fighting normally |
| `dying` | 0 HP, down on its cell, death clock running — still savable |
| `stable` | 0 HP, unconscious, out of the fight; **survives** the battle |
| `broken` | Automaton only: 0 HP, down, **no clock** — waits for a repair; survives |
| `dead` | permadeath |

A body (`dying` or `stable`) stays on its cell and **can be drawn, targeted and
attacked**, but does **not count as a combatant**: it does not count for
victory, is not an AI target, does not block or occupy a path.

**Falling.** When HP hits 0 the unit enters `dying`, the clock resets, and it
counts **its own turns** on the initiative. On those turns it does nothing but
run the clock.

**Death clock.** On the unit's **3rd turn** down: a **death save** — roll `d20`,
**11–20 lives** (50%). Fail → `dead`. Pass → `stable`. The clock fires once, on
the 3rd turn; every time a unit goes from `up`/`stable` to `dying` it restarts.

**Stabilize (ally, empty hands).** 1-point action; an adjacent `dying` ally.
Triggers **one extra death save on the spot** (`d20`, 11–20). Success → `stable`.
Failure → nothing. Several allies can try in sequence, turn after turn.
- **A `broken` Automaton target:** the same action repairs it, but the check is
  `d20 + INT mod` vs **DC 15**, and success brings it back `up` at 1 HP. No
  attempt limit.

**First Aid (kit).** 1-point action; an adjacent `dying` ally; needs a **First
Aid Kit** in hand with charges. A Wisdom check: `d20 + WIS mod` vs **DC 10**.
Success → `stable`. Failure → nothing. **Consumes 1 charge either way.** The kit
has 10 charges and is **persistent** — once empty, it is discarded, and a new one
must be purchased from the Market.

**Coup de grace.** A normal attack (melee or ranged) may target a downed body:
- `dying` target → the hit **kills instantly** (`dead`), no damage roll;
- `stable` target → the hit deals normal damage, the unit **returns to `dying`**
  and the clock restarts.

**Victory.** A side loses when it has no unit still `up`. Units still `dying` on
the clock when the battle ends take **one last death save** to settle
`stable`/`dead`.

The **AI** treats downed bodies by **alignment**: **Evil** delivers the coup de
grace to an adjacent `dying` enemy before fighting on; **Good** stabilizes an
adjacent downed ally before anything else. Otherwise a body is not a target.
The AI **pathfinds** to reach a downed ally (stopping adjacent to stabilize) or
navigates toward the nearest map edge when it decides to flee.

### Ammo and improvised weapon 🟡

- The **Light Crossbow** needs **ammo** and holds **one bolt at a time**. The
  **Quiver** (the Crossbowman's item) carries **20 bolts**; bolts are **not
  recovered**.
- Quivers track **persistent charges** across battles. An emptied quiver is
  discarded after battle, and automatically reloads from any spare quiver carried
  in the unit's inventory.
- **Reload** is a 1-point action: takes a bolt from the Quiver and chambers it.
  **The crossbow enters the battle unloaded.**
- Firing needs the crossbow **loaded** and empties it — in practice the
  Crossbowman gets **one shot per turn** (Reload + Shoot spend both points).
- **An unloaded crossbow = an improvised weapon:** a **melee** attack, range 1,
  damage equal to the **size's unarmed die** + Strength mod. It rolls with
  Strength (melee), never Dexterity.
- "Improvised weapon" is a reusable concept; for now only the crossbow triggers
  it.

### Terrain 🟡

- **Wall** — blocks movement and line of sight.
- **Difficult terrain** — costs **one extra square** to enter (`board.difficult`,
  folded into the pathfinder and the walk accounting). Not double: doubling
  breaks on the diagonal-alternation rule, so it is a flat `+1`. **Shallow water**
  (below) is the only source today; mud, rubble and scree can join later.
- The generated map lays a few short wall segments in the middle; the generation
  guarantees the two sides stay connected (nobody gets boxed in).
- **Diagonal corner:** the grid is square, so two walls often meet at a corner.
  When **both orthogonal cells** of a corner are walls, you **cannot cut the
  diagonal** there — neither walking nor seeing. A **single** wall at a corner
  blocks nothing. In `board.diagonal_corner_blocked`, applied in `reachable`,
  `path_step_toward` and `los_clear`.

### Pits and depth — the Z axis 🟡

The board has a **Z axis**: each cell has an integer **elevation**
(`board.elevation`, 0 by default). A **negative** elevation is a **pit** — that
is all that exists for now; positive (rises, platforms) is reserved. A pit N
cells deep is a cell at elevation `−N`. Pit cells are painted in the scenario
editor (the **PIT** tool, adjustable depth) and stored in the map as `[x, y, z]`
triples.

- **Walking never changes elevation.** Normal pathfinding never crosses an
  elevation difference — a pit edge is a wall to anyone walking. **Exception:**
  anyone who **flies** (or, in future, has a climb speed) moves in three
  dimensions as normal movement and a pit does not stop them.
- **Fall damage.** Descending `h` levels at once costs `max(0, h−1)d6` — the
  first level is free, each level beyond it is 1d6. Fliers take no fall damage.
  In `battle.apply_fall`.
- **Climb** (1-point action, target = an adjacent cell of different elevation):
  a **Strength** check `d20 + STR mod` vs the **surface DC** — bare stone **15**,
  with a **rope 10** (`board.surface_dc`; the rope is an editor marker on a pit
  cell). Success climbs/descends **one** cell with no damage; a slip wastes the
  action. The **Climber** (Lizardfolk) skips the check at DC ≤ 25.
- **Drop In** (1-point action): steps down on purpose into an adjacent lower
  cell, no check, taking the fall damage.
- **Jump** (1-point action): a horizontal leap. Rolls `d20 + STR mod` and
  advances in a line toward the aimed cell up to **`result ÷ 5`** cells (never
  more than the unit's speed), passing **over** any pit on the way; a wall or a
  body stops the jump short. Landing lower than it started takes the fall.
- **Push** (1-point action, target = an adjacent enemy up to 1 level of
  difference): `d20 + STR mod` (attacker) vs **10 + Constitution mod** (target).
  Success shoves the target **1 cell** straight back; if the cell behind is a
  pit, they fall. A wall or a body behind the target stops the shove.
- **Vertical combat.** Melee reaches between two elevations if the difference is
  **≤ 1** (a fight at the lip). A difference of **2 or more** takes the target
  out of melee reach until someone climbs — a **ranged** attack still connects.

### Water — shallow and deep 🟡

A cell can hold **water** (`board.water`, the **WATER** editor tool, stored in the
map as `[x, y]` cells). Its behaviour depends on whether the cell is a pit:

- **Shallow water** (water on ground level) — a puddle, a mud flat, knee-high
  water. It is **difficult terrain** (see Terrain: `+1` to enter). Nothing else:
  you wade through, no check, no breath.
- **Deep water** (water over a pit) — a flooded trench. You **cannot walk** into
  or across it (`Battle._impassable_water` blocks it for anyone not flying); a
  flier passes over. A plunge into deep water takes **no fall damage** — the water
  breaks the fall.
- **Swim** (1-point action, like Jump) — the only way through deep water on foot.
  `d20 + STR mod`, cross **`result ÷ 5`** cells toward the aimed cell, capped at
  **half** the unit's speed. The swim runs only through water cells; a wall, a
  body or the water's edge ends it there (climb out with a separate **Climb**).
- **Breath.** A submerged unit holds its breath **`4 + Constitution mod`** rounds
  (`data.BREATH_BASE`). Every round under past that: **escalating drowning
  damage** — `1d6`, then `2d6`, then `3d6`, … — each of its turns until it
  surfaces or goes down (`Battle._apply_submersion`, run at the top of the turn).
  Surfacing resets the count.
- **Amphibious** (Grippli) — breathes water; the breath clock never starts.

### Vision and light 🟡

Rules in `board.py` (`los_clear`) and `vision.py` (`cell_lit`, `can_see`).

- **Line of sight (LOS):** a straight trace (Bresenham) between the cells; a
  **wall** in the middle blocks it, and **two walls closing a corner** also
  block the diagonal that would pass between them. A character sees
  "infinitely" along the LOS — the cap is **200 m (133 cells)**, more than the
  board.
- **Light:** the map is **always dark**. A character sees **only their own
  cell**; the rest is **black**, except:
  - cells within a **light source's** radius (with LOS to the source);
  - targets within **12 cells (18 m)** of a character with **Darkvision** — they
    see as if lit.
  - Any light reveals the area **for both teams**.
  - Every radius (light and Darkvision) is measured with the **diagonal metric**
    — an **octagon**, not a square.
- **Light sources:**
  | Source | Radius | How |
  |---|---|---|
  | **Lantern** (the Guard's item) | 9 m (6 cells) | in the item slot, always lit |
  | **Torch** | 6 m (4 cells) | lights the same held or dropped; held, it takes the weapon hand (you attack unarmed while holding it) |
- **Torches** are **ground objects** (`GroundObject`, `kind = "torch"`). Pick Up:
  unarmed picks it up; armed **swaps** (the weapon drops). Picking a weapon back
  up **drops the torch**.
- **Vision is the CHARACTER's, not the player's.**
  - **On your turn:** the screen shows only what the **active character** sees.
    `L` toggles to the **squad vision** (the living team's union) and back.
  - **On the enemy turn:** always the **union of your living squad**.
  - Your own characters always show; what changes is the revealed map and which
    enemies you see.
- Enemies out of sight are **hidden**: not drawn, cannot be targeted or
  inspected.
- The **AI** sees through each of its units' eyes: it only attacks what that unit
  sees, but still advances toward the nearest enemy. It ignores torches (only
  chases a dropped weapon when unarmed).

### Throwing 🟡

- Only a **thrown weapon** works. For now **only the Dagger** (range 9 m =
  6 cells).
- **Hit:** `d20 + Dexterity mod` (+ typical mods) vs AC. Natural 20 = crit;
  natural 1 = fumble.
- **Damage:** the weapon die **+ Strength mod** (strength goes into the damage,
  not the hit).
- After throwing, the character is **unarmed** (uses the size's unarmed attack)
  — *whether or not it hit*.
- The weapon **lands on a free cell adjacent to the target** and becomes a
  ground object.

### Demoralize 🟡

Rule in `actions.py` (the `Demoralize` class). A **social** attack: it saps the
target's confidence instead of wounding them.

- **Cost:** 1 action point.
- **Range:** **18 m (12 cells)**.
- **Requirements (all):** the two characters **see each other** (LOS + the
  vision rule in **both directions**) **and** share at least **one language**.
  - **Exception — Kenku ("Mimic Sounds"):** drops the shared-language
    requirement **as the attacker**. This does not apply on defense: to
    demoralize *a Kenku*, the provoker still needs a common tongue.
  - **Exception — the arena title holder:** the Champion of the Pit may
    Demoralize any target inside the arena, shared language or not (+1 to the
    roll when a language *is* shared), and gets +1 Mental Defense vs Demoralize.
- **Hit:** `d20 + Charisma mod` vs the target's **Mental Defense** (`10 + WIS
  mod`, + the Iron Will talent). Natural 20 = automatic crit; natural 1 =
  fumble. No damage.
- **Effect (hit):** the target becomes **Demoralized** — a **−1 `status`
  penalty** to **attack, AC and Mental Defense**.
- **Duration:** the condition expires **at the end of the sufferer's own turn**.
  So a target demoralized right after its turn carries the −1 for the whole round
  until its next turn closes.
- The **AI** uses Demoralize when it cannot reach the target to attack and the
  target is not already demoralized.

### Ground objects 🟡

- An object occupies a cell but **does not block** movement or a line of fire.
- Kinds today (`GroundObject.kind`): **`weapon`** (a thrown/dropped weapon) and
  **`torch`**.
- The **Pick Up** action (1 point), object in the cell or **adjacent**:
  - **weapon:** only if you are **unarmed**.
  - **torch:** anyone — armed = a swap (the weapon drops).
- The AI prioritises recovering its own dropped weapon before attacking again
  (it ignores torches).

### Fleeing 🟡

Action in `actions.py` (the `Flee` class). For **both sides** — player and AI.

- **Cost:** 1 point, and it **ends the turn** (you are running, not fighting).
- **Position requirement:** you can only flee from a cell **on the map edge**
  (any footprint cell touching `x = 0`, `x = COLS−1`, `y = 0` or `y = ROWS−1`).
  Off the edge the button is dark ("reach the edge").
- **The flee succeeds** (deterministic — the button lights only when it works)
  if **either**:
  - your **speed** is **greater** than the fastest living pursuer's; **or**
  - you are already **far enough** — the nearest living enemy is **further** than
    the fastest pursuer's speed: in a race off the map they cannot close the
    gap.
  - With no living enemies, you always flee.
- **Effect:** the character enters the `fled` state — off the board (not drawn,
  does not block, does not count for victory, not a target), but **survives** the
  battle and returns to the guild with what it carried. Not loot.
- **Drags adjacent downed allies.** On fleeing, every **downed** ally (dying /
  stable / broken) in a cell **adjacent** to the fugitive also leaves (becomes
  `fled`, survives). Anyone further away is **left behind**: if the last one up
  flees, the other side "wins" and the bodies left are **lost with the defeat**.
- If **all enemies** flee/fall, the player wins normally.

**AI behaviour by alignment** — alignment tempers the AI's edges, mostly on the
moral axis:

- **Evil:** delivers the **coup de grace** to an adjacent downed enemy (kills the
  `dying` on the spot, denies the player a stabilize) before fighting on. Only in
  a **lethal** fight — in the arena it just knocks out.
- **Good:** **stabilizes** an adjacent downed ally before anything else and, when
  it flees, drags the wounded along.
- **Chaotic:** breaks and runs **sooner** (HP ≤ 50 %, and merely outnumbered).
  **Lawful:** flees only when **no ally is still up**.
- **Pathfinding to flee:** when an AI unit breaks and runs, it moves toward the
  nearest map edge turn by turn before executing the Flee action.

### Weapons table 🟡

The full table (damage, range, finesse, thrown, hands, weight, price) is in
[`REFERENCE.md`](REFERENCE.md) (§ Weapons). By design the game starts with only
the Dagger as a thrown weapon; the Light Crossbow is the one ranged weapon and it
must be reloaded between shots.

---

## World systems 🟡

Rules that exist **outside combat** — the guild on the map, time passing, the
economy. Each starts as a "world thing" and only then talks to the fight.

### Identity 🟡

Purely cosmetic, no mechanical effect: after the three squad picks, the draft's
"identity" phase asks for a **guild name** and a **banner** — a colour and an
emblem, both from a small curated set (`theme.BANNER_COLORS`,
`artwork.BANNER_ICONS`), not a free painter. The chosen colour becomes every
unit token's fill for the rest of the run (`theme.set_player_color`, read live
by `theme.token_badge` — every roster card in the game uses it without
knowing it changed). `battle_screen`'s player/enemy colour-coding is untouched
on purpose: that one is a readability cue, not an identity, and must stay
distinct from `ENEMY_C`. A save from before this existed shows "The Guild" in
a default colour (`Guild.DEFAULT_BANNER_COLOR`/`DEFAULT_BANNER_ICON`).

### Leadership 🟡

Two kinds of leader (`gartok/group.py`, `gartok/guild.py`), answering two
different questions:

- **The guild's leader** (`Guild.leader`) is "who am I" — chosen at the draft
  (`DraftScreen`'s leader-pick step, after the three squad picks) and held for
  the whole run. It is a title, not a place: it does not move a leader between
  groups or change who leads any of them. It **auto-succeeds by Charisma** the
  instant it stops being a living roster member (death); a *deliberate* change
  (`Guild.set_leader`) costs the run's **one free swap** — spend it whenever,
  on whoever, but after that only death reshuffles the title again.
- **A group's leader** (`Group.leader`) is who speaks for *that* group, and
  can be **swapped freely, any time**, for any member of the group — no cost,
  no limit (a group is reshuffled by splits/merges constantly; its leader
  should be too). It auto-succeeds by Charisma the moment the current leader
  stops being a member (death, or split off into a different group). A fresh
  group's default leader — and the guild's starting group at the draft — is
  its highest-Charisma member unless set explicitly.

**What a leader is for, today:**

- **Haggling** (`economy._haggle_fraction`) — the shopping party's leader
  speaks for it, if they share the vendor's language; otherwise the highest
  Charisma modifier among the eligible speakers does, same as before leaders
  existed.
- **A cap on cohesion.** `Group.capacity` = `BASE_CAPACITY` (3) + the leader's
  Charisma modifier — how many members one leader can hold as a coalition.
  Past it, `Group.overextension` counts the excess and docks that amount, flat,
  off every member's **Mental Defense** (`Unit._derive_ac`) — an overstretched
  group doesn't get blocked from growing, it just gets easier to rattle
  (Demoralize, and any future check against Mental Defense). This caps how big
  one *group* can comfortably be — it does nothing to stop the roster itself
  from splitting into any number of small groups instead.
- **A hard wall on the roster itself.** `recruit.capacity(guild, unit)`
  = `BASE_RECRUIT_CAPACITY` (1) + the unit's own Charisma modifier — how many
  people *that specific member* can personally sponsor into the guild
  (`recruit.slots_free`, checked against how many roster members already carry
  their uid in `recruited_by`). Low-Charisma members cap out fast and become
  the guild's floor — recruited, but unable to recruit in turn. **The guild
  leader adds their own racial level on top** — the one mechanical thing
  `Guild.leader` does today, and why the title is worth keeping past the
  draft. This is the actual answer to "what stops the guild from being
  100,000 characters": every new member needs a living sponsor with room left,
  so growth is a tree fed mostly by the leader, not a free action for anyone
  on the roster.

Recruitment pitches (`recruit.py`) already let the player pick who does the
talking — the leader doesn't override that choice, it only fills in where no
choice was being made (the market's "whoever has the best Charisma" auto-pick).

### Hunger 🟡

State on `unit.py` (`unfed_days`, `hunger_*` properties); the daily routine in
`Guild.pass_time` / `Guild._daily_upkeep`, run when the guild **travels** or
takes a **maintenance stop** (battle time is in seconds and does not count a
meal).

- **Every character eats once a day.** For each map day crossed, a character
  consumes **1 food item** (`data.FOOD_ITEMS` — today `Meat`, `Potato`).
  Ate → counter resets.
- **Shared food (on by default), scoped to the group.** Each character eats from
  their **own pack** first (a full first pass over the roster); anyone still
  hungry then draws a ration from a **group-mate** (physically together, so the
  only ones who could actually hand over food) with `share_food` on
  (`Unit.share_food`, toggled on the member panel of the guild screen). Two
  passes so nobody loses their own meal to a mate earlier in roster order. A
  guild-mate in a different group is out of reach. The Autotroph (Leshy) never
  enters this.
- **Maintenance** (a button on the map -- `campaign.advance(guild, dt=1)`, a
  forced tick): every group stops 1 h where it stands; passes the time (which
  can cross midnight and trigger the daily meal) and then **anyone still
  hungry eats now** (`Guild.eat_now_pass`) — own pack, then the group's shared
  larder.
- **No food anywhere in reach:** the days-unfed counter rises.

  | Days unfed | Condition | Effect |
  |---:|---|---|
  | 1 | **hungry** | −2 to **all attributes** (−1 to the mods) |
  | 2 | **starving** | −4 to all attributes; **max HP = 1** |
  | 3 | **starving to death** | **incapacitated** — cannot be sent to battle |
  | 4 | — | **dies** (removed from the guild) |

  > The death trigger is `data.STARVATION_DEATH_DAYS = 4`.

- **Autotroph (Leshy):** photosynthesises — never eats, never starves.
- Food is **for sale at the market** (`Meat` 5c, `Potato` 3c).
- Eating/dying **re-derives** the character's attributes, so the sheet, the guild
  cards and the next battle already show the right numbers. If the whole guild
  starves on the road, the campaign ends.

### Encumbrance 🟡

`unit.encumbered` = `load > carry_normal`. While set: −2 Strength score, −2
Dexterity score, −1 speed (folded into `_derive_combat`, parallel to hunger).
`carry_normal` / `carry_max` are computed from the hunger-adjusted (not
encumbrance-adjusted) Strength — the penalty must not feed back and shrink its
own threshold.

### The lumber yard: day-labour by the hour 🟡

The `lumber_yard` node (a `town` with `work=True`), 1 h from the City. Rule in
`Guild.work_shift` / `economy.lumber_pay`; on the map it's an order, resolved
silently by `campaign.advance` (`gartok/orders.py`). It is the **economic
floor**: whoever lost everything in the arena goes there to trade time for
copper instead of walking into the wilds and dying.

- **How it works:** pick a group standing at the yard and a **shift** — 4, 8, 12
  or 16 h — which issues a work order; ADVANCE resolves it: passes the time (can
  cross midnight and trigger the day's meal) and pays each worker.
- **Pay:** `economy.LUMBER_WAGE` = **3 copper per whole 4-hour block**; a partial
  hour does not count. A full 16 h day = **12 copper** per head, straight into
  each one's purse.
- **Work XP:** `Unit.work_hours` accumulates the hours; `Unit.work_xp` =
  `work_hours // 16` — **one mark per 16 h worked**. It feeds the work level and
  the work talent tree.
- **No wood:** the axe is borrowed and the tree is not yours; you take only the
  wage for the hours, no item.
- **Deliberately meagre.** 0.75 copper/h. A full day feeds you (a Potato is 3c)
  and leaves ~9 over; rebuilding a minimal kit (~30 copper) takes ~3 days. An
  arena purse or a wilds haul pays several times faster — the yard is a safety
  net, not a career.
- A character **incapacitated by hunger can work** (it is not combat) — that is
  exactly who needs it most.

### The Forge: crafting 🟡

`crafting_screen.py`, at the City (`Node.forge = True`). A member needs a
learned recipe (`Unit.recipes`) before they can start; the recipe's materials
are consumed the moment `crafting_target` is set, not on completion — an
abandoned craft doesn't get them back.

- **Progress** rolls `1d20 + INT mod` per hour worked (`Unit.progress_crafting`,
  driven by `Guild.crafting_shift`) toward the recipe's point target; hitting
  it drops the finished item into the pack and clears the target.
- **Recipes** are granted the same way a magic source is (see Magic above) —
  a racial talent (the Dwarf's "Dwarf Crafting" hands over the Dwarf
  Axe/Shield/Armor recipes outright) — with no other way to learn one yet.
- **Traps** (Bear Trap, Alarm Trap) are crafted items, but they are placed
  through a real battlefield mechanic, not just carried: at the start of a
  battle a carrier is queued (`Battle.trap_setup_queue`/`awaiting_trap`) to
  click a tile and plant it (`GroundObject.trap`, consuming the item), the
  same click-to-place idiom the CTF flag uses. Once down, an enemy who walks
  or is pushed onto it triggers it (`Battle.trigger_trap`) — a Bear Trap
  damages and stops the mover, an Alarm Trap only stops it — and the trap is
  removed from the board.

### The Wilds: hunting 🟡

The `wilds` node (`kind = "wilds"`). Its first activity is **Hunt**: `hunt.py` +
`hunt_screen.py`. Pick a party and a shift; the hunt spends hours one at a time,
with a per-hour **ambush** chance (`hunt.AMBUSH_CHANCE_PER_HOUR`). An ambush drops
the party into a **lethal** fight against a scaled pack (`encounters.roll_pack`,
mean level 0–4). Win it → field loot, and if daylight is left you may keep
hunting. Meat accrues at 1 kg per 2 hours, split among the surviving hunters at
the end; the hours bank **work** XP.

### Market and haggling 🟡

Rule in `economy.py` (`market_deal` / `buy_price` / `sell_price`); screen in
`market_screen.py`. A `market` node carries the vendor's **language** and
**alignment** (today: the Market speaks **Ankarin**, alignment **Lawful and
Neutral**).

- **The tabled price** (`economy.PRICES`) is the base. You buy at the table and
  resell at **50 %** (`SELL_FACTOR`) — always a loss.
- **Haggling** tightens the spread into a single `deal` fraction for the visit:
  - **Only shoppers who speak the vendor's language haggle.** Among them, the
    one with the **highest Charisma modifier** speaks for the group. Nobody
    speaks it → `deal = 0`, tabled prices. (This is the **Human**'s edge with
    "Extra Language"; the Kenku's "Mimic Sounds" does **not** help here.)
  - **Charisma:** `+0.04` of `deal` per positive modifier point.
  - **Alignment:** the distance between the negotiator's alignment and the
    vendor's (0–4): `0 → +0.10 · 1 → +0.05 · 2 → 0 · 3 → −0.05 · 4 → −0.10`.
  - `deal` is clamped to **[−0.15, +0.25]**.
- Applied: `buy = base × (1 − deal)`, `sell = base × (0.5 + 0.4 × deal)`. The
  `deal` cap keeps sell **below** buy, so you cannot make money buying and
  reselling.
- Haggling is generalised: a price modifier is a `PriceMod` contribution, not a
  parameter — the Provisioner talent adds one scoped to food, buy-side.

### Recruitment 🟡

Rule in `recruit.py`; there is no taverna hall or vault — the guild *is* its
roster. Whether a stranger signs on is a Charisma contest (`recruit.convince`,
`d20 + Charisma` each side, a tie favours the stranger) between the pitching
member and the candidate, docked for **no shared language** (no pitch at all),
**alignment distance** (`−1` per step, 0–4), and **guild size** (`−1` per
member past `FREE_SLOTS = 2`). A failed pitch bars that recruiter from that
same candidate until the pool turns over (`taverna_blocked`); another member
can still try.

- **Capacity.** Each member can personally sponsor `BASE_RECRUIT_CAPACITY`
  (1) + their own Charisma modifier recruits (`recruit.capacity`); the guild
  leader adds their own racial level on top — the mechanical reason the title
  is worth keeping past the draft (see Leadership above). This is what caps
  the roster: every new member needs a living sponsor with room left.
- **The Tavern** (`taverna_screen.py`): a free pool of `TAVERNA_SIZE` (3)
  strangers, re-rolled every `REFRESH_DAYS` (7) days (`recruit.refresh_pool`).
  No money changes hands.
- **The Prison** (`prison_screen.py`, at the City's `prison` node): a second,
  separate weekly pool (`recruit.refresh_prison_pool`) of minor criminals.
  Unlike the Tavern, you must pay `recruit.bail_cost` — `(sum of the six
  attributes × (racial level + 1)) + 20` copper — before you can even pitch;
  the payment adds a **+2** bonus to the Charisma contest (their gratitude).
  Lose the pitch and the bail is gone too — they walk free with your money.

### Reputation and factions 🟡

Registry in `factions.py` (`Faction` + `Deed`, in the style of `talents.py` /
`abilities.py`); state on the `Guild` (`reputation = {id: points}`,
`deeds_done`). `factions.settle(guild, event)` runs after any moment a deed
might fire on and banks the ones whose condition now holds; a `factions.Event`
carries `kind` ("battle", "travel", …), the `node`, and per-kind payload (a
battle event carries the `campaign.BattleOutcome`). Live call sites: after a
battle (`campaign.absorb_battle`) and on arriving somewhere on the map
(`map_screen`). A market / hunt / hire trigger is one `settle` line at that flow
when a non-arena faction grows a deed that needs it.

> **A faction is an organisation, not a place.** It can hold ground across
> several nodes. Reputation with it **only rises by completing *deeds*** — there
> is no per-win grind. A deed is a one-shot achievement: a named condition that,
> once true, is banked forever and pays its `rep` points. A faction works its
> deeds **in any order** (`requires` only when order must be forced). They grow
> by hand, one at a time — a faction's rules *are* what it wants from you.

**Faction #1 — The Pits (`arena`).** The first arena's sub-campaign is three
independent deeds (see [`REFERENCE.md`](REFERENCE.md) § Factions and deeds):

| Deed | Condition | Reward |
|---|---|---|
| **First Blood** | win a staked arena bout | +1 reputation |
| **Lone Wolf** | win the cheapest bout (entry tier) with **a single fighter** | +1 reputation |
| **Dethrone the Champions** | beat the arena's **champion team** | +1 reputation |

All three → 3 reputation. **Dethrone** is fought via the "Challenge the Champion"
bout on the hand-authored `maps/the-pit.json` (Adelio Small-Knife + 2 hired
bodies); the win condition is unchanged — put the whole team down.

Arena progression is now tied entirely to these narrative deeds rather than
static reputation ladders. Completing the "First Blood" deed opens the way to
the champion, and dethroning the champion unlocks The Games (`arena.py`'s
stage 2 bouts): **Bloodsport** (win a stage 2 bout), **Flag Runner** (capture enemy
flag), **Untouchable** (capture flag without KOs), and **The Ribbit Brothers** (beat
the 3 Grippli boss team). Each bout is defined in `arena.py` and assembled in `matchup.build`.

**Faction #2 — The Bankers (`bankers`).** The coin-lenders of the City. Four deeds
measure the guild's standing:
- **Good for Business:** complete an economic job in the City.
- **Steady Customer:** spend 1,000 copper at the market.
- **Diverse Portfolio:** sell 5 different kinds of goods to the market.
- **Earned Trust:** carry the Bankers' sealed chest intact to Ledger Hold and
  return their receipt (`bankers_trust_chest` mission).

What they sell today is the guild's **first shared property**: a **strongbox** at the bank.

- The `city` node carries `bank=True`; **VISIT THE BANK** on the map opens
  `bank_screen` for the chosen party (the market's party-picker path).
- The chest is **guild state** (`guild.bank_capacity` kg, `guild.bank_items`) —
  the guild owns nothing else as a body. `bank_capacity == 0` = not rented.
- **Renting** costs a flat `economy.BANK_CHEST_PRICE` (**50 copper**), split
  across the visiting party (poorest first, shortfall rolling onto whoever still
  has coin), and grants `economy.BANK_CHEST_CAPACITY` (**10 kg**) of storage.
  Stashing itself is free, so members keep their own money — nothing is pooled or
  redivided. One tier for now; the field is shaped for a later, bigger box.
- **Stashing** moves **pack** items only, in either direction: into the chest
  while `bank_load + weight ≤ bank_capacity`, out of it while it fits the taker's
  carry max. Wielding/wearing still happens on the gear screen.
- The chest lives at the bank — gear in it is **only reachable from the City**.
- Lending against the future (and collecting on it) is the Bankers' other trade,
  not yet built.

### Missions 🟡

Registry `gartok/missions.py` (`MissionTemplate` + `Mission`), distinct from a
`factions.Deed`: a mission has a named giver, a concrete goal item/quantity, a
copper reward, and a real deadline (`deadline_day`) — it can fail. Only one
instance of a given template can be active guild-wide at a time
(`missions.offers_at`); an overdue one expires automatically via
`Guild._daily_upkeep` (`missions.expire_overdue`).

- **Scoped to the accepting Unit, not the Group that signed it** — a group is
  reshuffled by splits/merges constantly, so `progress`/`turn_in` always
  resolve the signer's *current* group (`guild.group_of`) and count that
  whole group's packs, the same trick the shared food larder uses.
- **The Tanner** (`tanner_screen.py`, at the City): wants 15× `1sqm Hide`,
  pays 200 copper, 5 days. Hides only drop from Wilds beasts, not from hours
  hunted; a finite market stock (`economy.STOCK`, `Guild.market_stock`) keeps
  the hide from just being bought instead of hunted.
- **The Bankers' trust mission** (`trust_screen.py` at the City,
  `ledger_screen.py` at Ledger Hold): hands the signer a sealed chest
  (`data.MISSION_CHEST_ITEM`) instead of asking for a gathered item; the
  "goal" is a letter of receipt, traded for the chest at Ledger Hold and
  carried back. Opening the sealed chest early — mistaking it for an
  ordinary locked one, see Crime below — fails the mission and marks the
  opener a criminal instead of paying out.

### Property and holdings 🟡

Two mutually-affordable-but-not-mutually-exclusive paths to guild land, both
shipped start to finish (buy/claim, use, lose, recover):

- **City Property** (`city_property_screen.py`). Bought from the Bankers at
  the City once `guild.reputation["bankers"] ≥ economy.CITY_PROPERTY_REP_GATE`
  (4) — the Bankers' trust mission (see Missions) is the gate's real
  prerequisite. `economy.CITY_PROPERTY_PRICE` = **1000 copper**, one-time,
  for `economy.CITY_PROPERTY_CAPACITY` (**20 kg**) of shared storage, plus a
  recurring tax (`economy.CITY_PROPERTY_TAX` = **40 copper** every
  `CITY_PROPERTY_TAX_PERIOD_DAYS` = **7** days, charged automatically by
  `Guild._city_property_upkeep`). `CITY_PROPERTY_MISSED_PAYMENTS_LIMIT` (3)
  unpaid cycles force a choice (`RepossessionScreen`): **return** the
  property (and owe the Bankers a debt that blocks their other services until
  paid, escalating to the guard after `CITY_PROPERTY_DEBT_GRACE_DAYS` = 14
  days), or **squat** — keep it tax-free but illegal, and the guard
  periodically raids it (a new `"eviction"` order, same shape as a `"guard"`
  or `"ambush"` pause).
- **The Wilds Claim** (`wilds_claim_screen.py`, the `wilds_territory` node,
  `Node.claim = True`). A mini-campaign through
  `guild.WILDS_CLAIM_STAGES` = `NONE → SCOUTED → CLEARED → FENCED → SWEPT →
  SUSTAINING → ESTABLISHED`: **Scout** is a pure time gate; **Clear** and
  **Sweep** are real scaled fights (the whole present group, no stakes, no
  squad picker); **Fence** consumes hauled-in Lumber (bought at the Market
  until the claim can produce its own); **Sustain** parks a garrisoned group
  there for a countdown, rolling a raid chance
  (`economy.WILDS_RAID_CHANCE` = 0.2) each `campaign.advance()` — losing only
  resets the sustain timer, never the earlier stages. Once **Established**,
  the garrison produces Lumber daily (`economy.GARRISON_JOBS`,
  `Guild._garrison_upkeep`) and the claim becomes a real target: an
  unguarded one can be **silently seized** (no fight); a guarded one that
  loses its defense is also seized, but the structure survives either way —
  **retaking** it is a normal arrival fight against the occupiers, never a
  redo of the claim campaign.
- **The garrison engine** underneath both (`orders.garrison(job)`,
  `Group.locked` vs `Group.busy`) is generic per node
  (`guild.garrison_stock[node_id]`), not hard-wired to either property — the
  Tavern's "study" job (see Magic above) reuses the exact same order kind.
- **Not built yet, on purpose:** no autonomous job besides Wilds Lumber
  (the City property has none), no mechanical battle-map cover from fences
  (a checklist step only, no combat-terrain hookup), no per-unit job choice
  inside a garrison.

### Crime and justice 🟡

Rule in `justice.py`. A **personal** record (`Unit.crime`), not a guild one —
it can catch up with a character wherever the City's authority reaches
(`world.Node.jurisdiction`).

- **The catch.** `campaign.advance` tests every member of a group arriving at
  a jurisdiction node: `d20 + crime ≥ 11` (`justice.GUARD_CHECK_MIN`) — a
  clean record (`crime == 0`) can never roll high enough to be caught. Anyone
  caught pauses the whole group on a `"guard"` order for
  `justice_screen.GuardScreen`, decided once for everyone caught together:
  - **Accept arrest** — `prison_days = crime × constants.PRISON_DAYS_PER_CRIME`
    (2 days per point), crime resets to 0, the unit leaves its group into
    `Guild.jailed` (released automatically, back into a City group, once its
    day is up).
  - **Fight the patrol** — a real, lethal fight against
    `constants.PATROL_SIZE` (3) guards scaled to
    `min(constants.PATROL_LEVEL_CAP, crime)`; winning does **not** clear the
    slate — it adds `1 + kills` more crime on top.
  - **Flee** — falls back to wherever the group came from, which can itself
    land it on a fresh `"guard"` or `"ambush"` pause.
- **The Old Road** (`world.Node.unsafe`) rolls an ambush per travel leg
  through it — deserters, bandits and roving packs — the same
  pause/resume seam the guard uses, unrelated to jurisdiction or crime.
- **Locked chests** (`chest.py`, `data.CHEST_ITEM`): a generic pack item
  picked open outside battle (`gear_screen.py`'s right-click send menu),
  `d20 + Dexterity ≥ data.CHEST_DC`. A miss costs nothing, just try later.
  The Bankers' mission chest (see Missions) is a deliberately different item
  so it's never picked open by mistake — doing so fails that mission and
  banks crime instead of quietly paying out.

### The Champion of the Pit 🟡

Beating the champion team hands the **Champion of the Pit** title to whoever on
the winning squad lands the blow that puts Adelio down. It is a *character's*
title, held on the `Unit` (`unit.arena_title`), never the guild's. A messy finish
(nobody on the player's side downs him cleanly) leaves it vacant, with no
rematch — the deed banks either way.

The title only bites inside the arena (see the Demoralize exception above). Every
`arena.CHALLENGE_CYCLE` (15) days a formal challenge falls due; the champion has
`CHALLENGE_GRACE` (7) days to turn up at the arena for a 1v1 or the title is
forfeit for the run. The challenger is built to the champion's own mean level + 1
(`encounters.build_enemy`), so it keeps pace as the champion levels on these
fights. Once dethroned, Adelio becomes a fixture: a 5 % chance any ordinary pit
bout fields him as one of the opponents. He never levels.
