---
name: gartok-talent-trees
description: "GARTOK talent trees: general->specialist premise, the tier-2 node spec (combat + work, implemented Sep 2026), and the generalized market-deal PriceMod system that came with it"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3fbff8c0-083e-4c26-94d9-e5164f2e70e8
  modified: 2026-09-10T22:40:05.416Z
---

Design intent for the GARTOK talent trees (`gartok/talents.py`, spent on the
`level_screen`). Part of [[gartok-tactical-project]] progression. The user grows
the trees by hand, node by node; this is the spec + the premise to check new
nodes against.

## The racial track + hit-die rework (Sep 2026, commit `2521b47`)

**Third track: `racial`.** `talents.TRACKS = ("combat","work","racial")`;
`XP_TRACKS = ("combat","work")` is the pair that earns XP directly. The racial
track earns nothing of its own — `Unit.racial_xp = combat_level + work_level`,
`racial_level = progression.racial_level(racial_xp)` via
`RACIAL_XP_THRESHOLDS = [2,4,6,8,10,12,14]` (cumulative sums, chosen so
`racial_level == old floor((c+w)/2)` — enemy HD / balance sim / arena scaling
unchanged; tune freely). Every level anywhere → a racial pick + (via
`collect_levels`) a hit die.

**Hit dice are now `1 + racial_level`, not `1 + mean_level`.** `mean_level`
survives only as the encounter/arena difficulty scalar (`encounters.build_enemy`,
`arena.build_challenger`). This kills the "set 2 here, 4 there, average" authoring
pain the user hated: `_level_hp_rolls` length keys off `racial_level`.

**Racial nodes are race-gated.** `Talent.race: str|None` (None = any).
`talents.racial_tree(race_name)` narrows `TREE["racial"]`. `choose_talent` rejects
a mismatched race; `set_race` drops now-invalid racial picks; `pending_picks`
stays quiet for a race with no authored node (via `Unit._has_offerable`).
`encounters.build_enemy` fills racial picks from the race's tree too.

**First racial node: `tongue` "Tongue" (Grippli only)** — `Effect("melee_reach",
1)`, channel `melee_reach`. **It is an equipment slot, not a flat bonus** (commit
`4dd6b5b`, user's call). The tongue is a third limb with its own weapon slot
(`Unit.equipped_tongue`), 1-handed weapons only, stowed to the pack when the
talent goes away (`_derive_combat` guard). **No lockout** — the hands can still
wield a 2-handed weapon alongside. New action `actions.AttackTongue` ("Lash", id
`attack_tongue`, aimed panel action, `contextual` in battle_screen): reach
`Combatant.tongue_reach` = `1 + talent_bonus("melee_reach")`, rolls the tongue
weapon. The Grippli **chooses per turn** between the hand weapon and the lash
(`ai._pick_attack`: whichever reaches, then bigger die -- `_hand_die` handles the
improvised-crossbow case). The AI also **positions for the reach**: commit
`1cf8af3` gave `board/battle.path_step_toward` a `reach=` arg (stop as soon as
you're in range, not at adjacent; default 1 = no change for anyone else), and
`ai._approach_reach` passes `tongue_reach` only when the lash is the attack it'd
pick at that distance. `Attack.execute` / `AttackTongue.execute` share
`actions._strike()`; `attack_mods` / `damage_roll` / `_resolve_hit` take
`weapon=`. `Combatant.attack_range` (hand) is back to `1`.
`LoadoutMoveMixin` + gear/editor screens got a `"tongue"` zone; tongue line on
sheet / sheet_panel / draft. Lore (user): NPCs should be things a player can also
become — a real earnable node, not a boss stat. `npcs/ribit.json` fights with the
tongue (Quarterstaff in the slot).

Shipped alongside: **Broadsword** (`data.WEAPONS`) — 1d12, 2 hands, 4 kg, 105 cp
(3× Axe), in `MARKET_STOCK`. The first 2-handed melee weapon: raw die is the
payoff for *not* taking the reach tongue.

**Still open / user musing:** how the racial tree grows long-term (it's XP-fed
but the picks may want to be rarer than 1/level); other races' racial trees are
empty for now, grown by hand like combat/work were.

**Status: tier 1 + tier 2 implemented and merged to `main`** (commit `80efa90`,
Sep 2026 — built on a `feat/talent-tier2` worktree while a teammate's UI work was
in flight, then rebased + fast-forwarded onto `main`).

**Effect model reworked (Sep 2026, later session, not pushed).** The ~13 typed
knob fields on `Talent` collapsed into `effects: tuple[Effect(channel, amount,
stat="")]` — the PriceMod idea generalized past pricing, as the user asked.
`talents.bonus(talent_ids, channel, stat="")` sums the amounts; `Unit.talent_bonus(
channel, stat="")` is the per-character wrapper (replaced `_talent_sum` /
`_talent_attr`). Channels + their single consumer, in `talents.py`'s docstring
table: `attr` (`_apply_attributes`, stat=attr name), `to_hit` (`attack_bonus` /
`Combatant.attack_mods`, stat="strength"|"dexterity"), `melee_damage`,
`ranged_reach`, `hp_per_hd`, `ac` (all in `_derive_*` / `Combatant`),
`carry_buffer` (`_carry_relief`, still weight-capped), `haggle_cha`,
`food_haggle`, `coin_gain`, `activity_speed`, `recruit_cha`. New node reusing a
channel = edit only `talents.py`; new channel = one consumer call site.

## Guiding premise (durable — from the user)

**General -> specific as you go deeper.** A tier-1 root is a broad identity; each
step deeper makes the character a **specialist in one particular action**. If a
proposed node is broader than its parent, or sits at the wrong depth, it's
misplaced — check it against this.

- Tier 1 = "what kind of X are you" (the seeded roots).
- Tier 2 = the first fork *within* that identity: specialise toward one of two
  concrete pay-offs.
- Tier 3+ = deferred ("deixa por hora" — decided 2026-09).

Structural rules (see [[gartok-tactical-project]]): one pick per track level;
`Talent.requires` (prereq by id) is coded but unused so far — **tier 2 is the
first real use of `requires`** (each tier-2 node is gated behind its specific
tier-1 root).

Each `Talent` also carries `icon` (`"<category>/<name>"` under `assets/icons/`,
e.g. `"action/muscle-up"`) for the level-screen node graph — see
[[gartok-ui-redesign]].

**NO talent choice is mutually exclusive** unless a specific node says otherwise
(user, 2026-09). The `group` field stays unused for now. The player fills the
tree however they want — bottom-up, straight down one branch, spread wide;
all valid. Over enough levels a character can hold every node.

## Combat track — tier 2 (each needs its tier-1 root)

The two "+1 to hit" nodes are NOT the same node — each keys to the attribute of
its root, so they don't converge:

- **Strong** (root `strong`, +1 STR score):
  - `sure_strike` "Sure Strike" — **+1 to hit on STR-based attacks** (melee STR;
    also unarmed / improvised, which roll STR).
  - `heavy_hand` "Heavy Hand" — **+1 damage on melee attacks** (not thrown).
- **Agile** (root `agile`, +1 DEX score):
  - `long_reach` "Long Reach" — **+1 square of range on ranged AND thrown**
    (`attack_range` + `throw_range`; not melee reach).
  - `deadeye` "Deadeye" — **+1 to hit on DEX-based attacks** (ranged, thrown,
    finesse when DEX ≥ STR).
- **Tough** (root `tough`, +1 CON score):
  - `hardy` "Hardy" — **+1 max HP per Hit Die** (`1 + len(_level_hp_rolls)` dice).
  - `bulwark` "Bulwark" — **+1 AC** (folded into `ac_base`, so it shows on every
    roster preview).

## Work track — tier 2

- **Carrier** (root `carrier`, overload relief). Reworked 2026-09-08: NOT
  per-item any more. It is a flat **+1 kg buffer on the stagger threshold**,
  capped at the real weight of pack cargo that is neither weapon nor consumable
  (no such cargo -> no bonus). Knob `carry_buffer` (was `carry_light_items`);
  `Unit._carry_relief()` -> `Unit.carry_relief`, folded straight into
  `carry_normal` in `_derive_combat` (so every screen's `load > carry_normal` /
  `encumbered` check is correct with no per-screen math). `carry_load` deleted.
  Never touches displayed `load` or the `carry_max` ceiling (loot/market cap
  unaffected). Screens that judged encumbrance off raw `load` were fixed to use
  `.encumbered`, and detail views show a `(carrier +N)` hint.
  - `piecework` "Piecework" — **+20% coin from work that pays in coin**
    (`talents.COIN_BONUS`; per-worker in `work_shift`, on the nominal-hours pay).
  - `brisk_hands` "Brisk Hands" — **the worker finishes their shift faster**
    (`talents.ACTIVITY_SPEEDUP`, currently 0.10; user weighing 0.05, pending a
    work-economy balance pass). INDIVIDUAL: a Brisk worker is done early and the
    others finish later; the guild token only moves on once the SLOWEST worker is
    done, so `work_shift` advances the clock by `hours * max(1 - each worker's
    speedup)` — the clock saving lands only with a solo Brisk worker or an
    all-Brisk crew. Pay + work-XP always bank the full nominal hours.
- **Negotiator** (root `negotiator`, +1 CHA in the haggle):
  - `fixer` "Fixer" — **+1 to the recruiter's pitch** (`recruit.convince` adds
    `(knack, "Fixer")` to the mod list; `taverna_screen._best` mirrors it).
  - `provisioner` "Provisioner" — **+1 haggle step (`economy.CHA_DEAL_STEP` =
    0.04) on food, buy side, shared language or not**. Implemented via the
    generalized deal system (see below), NOT a special-case price channel.

## Market deal generalized (done with `provisioner`)

`economy`: the market "deal" is no longer a scalar threaded through `buy_price`.
`economy.PriceMod(amount, label, *, kind=None, applies=None)` — one scoped
contribution; `applies(item, side)` (side "buy"/"sell") gates which line items it
touches. `deal_mods(party, lang, align)` returns the list (base haggle as one
untyped mod + each shopper's `Unit.price_mods()`); `buy_price`/`sell_price` take
that list (or still a bare float for old callers via `_as_mods`) and resolve it
per item through `data.resolve_bonus` — same typed-bonus shape as combat.
`market_deal()` stays as the scalar-headline alias. **Principle: a price/check
modifier is a contribution, not a parameter** — new source = append a PriceMod,
no new code path. `recruit.convince` already half-did this (its `mods` list);
same shape.

Rounding reality: at `CHA_DEAL_STEP` 0.04 the food discount rounds away on cheap
food (Meat 5c × 0.96 → 5); it only bites stacked on a real haggle or on pricier
goods. Fine for now — flagged for the balance pass.

## Combat track — the Alert (Wisdom) root + the first tier-3 node (Sep 2026)

Added when the user built the CTF boss team (see [[gartok-character-creator]]).
The "wisdom tree" the user wanted is **not** a new XP track — it is a **4th root
in the combat tree**, earned by combat XP like the other three:

- **Alert** (root `alert`, +1 Wisdom score) — WIS is already combat-relevant
  (drives initiative + Mental Defense).
  - `quick_wits` "Quick Wits" — **+2 initiative** (flat).
  - `iron_will` "Iron Will" — **+2 Mental Defense** (flat; harder to Demoralize).

**First tier-3 node**: `fleet` "Fleet" — **+1 square of Speed**, `requires="deadeye"`
(so the chain is agile → deadeye → fleet; `drop_talent` cascades it). Deliberately
deep because +1 movement is strong. `requires` now chains more than one level —
`choose_talent`/`drop_talent` already handled it (fixpoint cascade).

Three new channels, each one consumer: `mental_defense` (`Unit._derive_ac`, folded
into `mental_defense_base` so both Unit + Combatant see it), `initiative`
(`Combatant.initiative_bonus`), `speed` (`Unit._derive_speed`, added to the base
before armor/encumbrance subtraction). Icons: `head/gaze`, `head/quick-man`,
`action/meditation`, `action/leapfrog`. Tests in `test_progression.py`.
