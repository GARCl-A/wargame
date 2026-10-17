# Dialogue before initiative — plan

**Slice 1 built 2026-10-16**, as planned below except where *As built* says otherwise; the rules now live
in RULES.md (*Dialogue before initiative*). **Designed 2026-10-16 (author interview, first pass).** A general tool for talking before a fight: when
the guild meets a foe, a dialogue opens before anyone rolls initiative, and what is said decides
whether there is a fight and how it starts. It comes **before the Blood Cult's third mission**
([dragon_lair.md](dragon_lair.md)), whose kobold patrols are its first on-board use.

Marked **(default)** = picked by me while writing the plan; the author may veto it. **Open** = still
to decide.

## Why a system, not more actions

Talking exists today, built once per case:
- the Wildfire's foci and the Ogre: a CHA-then-INT chain of buttons in the map's inspector
  (`wildfire.talk`, `map_screen._wildfire_blocks`);
- recruitment: the language gate (`recruit.shared_languages`) and a CHA contest;
- the guard's check (`GuardScreen`: prison / flee / fight) and the arena's prompts (Adelio, Ribbit).

**Decided (author 2026-10-16):** one dialogue system, its own step, and **the Wildfire's talk moves
into it**. The dragon lair's Parley is not a new combat action: it is a dialogue at the patrol's
contact.

## 1. When a dialogue opens

- **On the map (slice 1):** a forced encounter whose foes can talk, before its battle: the road ambush
  (`forced.EVENTS["ambush"]`), the gather and supply ambushes, and a Wildfire focus (the crew, the Ogre).
- **On the board (slice 2, built with the dragon lair):** a sleeper or patrol that spots the squad
  mid-battle. The board pauses, the dialogue resolves, the battle goes on with the outcome.
- **Not for beasts:** a foe with no language (snakes, wolves, the Aurochs) opens none.
- **The guard's check, in slice 1 (author 2026-10-16):** see 5b. The arena's prompts (Adelio, Ribbit)
  stay as they are for now.

## 2. The card

A modal card (a new `ui/dialogue_panel.py`, data-driven like the rest of `ui/`):
- the leader's portrait, name and line ("Your purse or your blood.");
- **what the guild knows of them**, from `intel.known_fields` (count, bands): the same read the foe card
  shows, so Intimidate is an informed choice;
- **who speaks**: the player picks a member; that member's attributes and languages count (the unit is
  the atom);
- the options, each with its check and odds. **An option the guild cannot take shows greyed with the
  reason** ("needs Draconic", "not enough coin"): the closed door is what makes a language worth having.

## 3. The verbs

One registry (`dialogue.VERBS`, like `abilities.py`); an encounter lists the verbs it offers.

| Verb | Check | Pass | Fail |
|---|---|---|---|
| **Bluff** | CHA vs 10 + leader's WIS mod | no fight (they leave, or let you by) | they strike first |
| **Intimidate** | CHA, + a bonus when `autowin` rates the squad stronger | they start **Demoralized** (built), or flee | they get +initiative |
| **Bribe** | none: coin from the speaker's pack | no fight | — |
| **Persuade** | CHA vs 10 + leader's WIS mod, alignment shifts the DC | no fight, or an encounter-specific outcome | normal fight |
| **Attack** | none | the squad strikes first | — |
| **Leave** | none | as today's flee where the encounter allows it | — |
| **Surrender** | none | the encounter's price (the guard: prison) | — |

- **Language gate (default):** every verb but Bribe, Attack and Leave needs a shared language
  (`recruit.shared_languages`). With none, coin and steel still talk.
- **Bribe's price (default):** a fixed rate a foe, scaled by their mean level; an encounter can refuse
  bribes (zealots, the Ogre's pride). Paid in copper first, like every purchase.
- **One try per verb (default)**; a failure that starts the fight ends the dialogue.
- **Striking first, the new seam:** today the battle only rolls initiative (`Battle._roll_initiative`;
  `raise_initiative` exists). "Strikes first" = a **Surprised** condition on the other side: no action on
  its first turn **(default)**.
- **No criticals (author 2026-10-16):** a natural 1 or 20 is just its number. `wildfire.talk`'s auto-fail
  on 1 and auto-pass on 20 go away when it moves in.

## 4. What a dialogue returns

An outcome the caller applies, so the system never knows about ambushes or fires:
`none` (no fight) / `fight` with start effects (who is Surprised, conditions such as Demoralized,
+initiative) / `paid` (coin moved) / encounter-specific results (a Wildfire focus taught).

## 5. The Wildfire moves in

- A focus's crew and the Ogre become dialogues: **Persuade** (CHA, "get a hearing") then a second step,
  **Teach** (INT, "show them how"), an encounter-specific verb. Same DCs (`wildfire.talk_dc`, -1 a taught
  focus), same results (`_taught`), a failure still starts `camp_fight` / `ogre_fight`.
- The inspector's per-member talk buttons go; the inspector gets one TALK button that opens the card.
- **Bribe the goblins? (default: refused):** the Coven's errand is about teaching them, not paying them.

## 5b. The guard moves in

`GuardScreen` (`justice_screen.py`) becomes the patrol's dialogue, decided for the whole catch at once
as today:
- **Surrender** = ACCEPT ARREST (`forced.resolve_guard_prison`);
- **Leave** = RUN (`forced.resolve_guard_flee`), hidden when there is nowhere to fall back to, as today;
- **Attack** = FIGHT THE PATROL (`app._start_guard_battle`, its crime aftermath unchanged);
- new: **Bluff** ("wrong man") and **Bribe**. Passing lets the group go with its crime still on the
  books (the next patrol can catch it again) **(default)**. The price scales with the caught members'
  crime **(default)**; a failed Bluff is a fight with the patrol striking first.

## 6. AI

- **The foe's side:** no choices of its own: the encounter's DCs, refusals and the alignment
  (`ai.py`'s axes) are its answer.
- **The squad's side, when the AI plays it** (the lab, `combat_pairs`): pick the option with the best
  expected result (odds x outcome, `autowin` for the fight's cost), Attack when nothing beats it.
- **Logs:** the dialogue goes into the combat log before round 1 (choice, roll, outcome), so
  `combat_log.rebuild` replays it, and into `recorder.py` as a play row.

## 7. Saves

A forced encounter is saved as a group's `pending` order. **Default:** the dialogue's result is stored
on that order the moment the roll is made, so reloading cannot re-roll it.

## 8. Slices

1. `dialogue.py` (verbs, outcomes, the roll), `ui/dialogue_panel.py`, `dialogue_screen.py` with its
   tutorial card; Surprised in `conditions.py`; the road / gather / supply ambushes open it; the
   Wildfire and the guard moved in; AI for the squad's side; tests (each verb, the language gate,
   refusals, the save, the Wildfire's and the guard's old results).
2. With the dragon lair: the on-board pause at a patrol's contact, the lair's own rules (+2 a bluff
   told, no parley with an egg in sight).

## As built (slice 1, 2026-10-16)

- **Attack is a plain fight** (initiative as rolled), not the squad striking first: an ambush is the
  foe's move, and a free first round on every ambush would have been a buff nobody asked for.
- **Bribes come from the group's purses, richest first** (`economy.charge_richest_first`), not only the
  speaker's: the speaker talks, the group pays.
- **Intimidate's odds** read the squad's hit points against the pack's (±4 on the DC), not an
  `autowin` run: the estimator is a background Monte Carlo and the card needs the number at once.
- **The card lists the foes by name and race**, not the INT read: that read (`intel.py`) happens on the
  board when a side first sees a foe, and the dialogue comes before the board.
- **The Wildfire needs no shared language** (`WildfireTalk.language_gate = False`): it had none before
  and its results stay the same.
- **The economy sim talks first** (`economy_guild.talked_down`): a road or gather ambush the AI talks
  down is never fought.
- `Surprised` is a condition (`conditions.py`) that `Battle._advance_turn` skips like Sleeping;
  `Battle.open_with` applies an opening, and the combat log's `start` row carries it so
  `combat_log.rebuild` starts the same way.
