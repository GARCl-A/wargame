# The Necromancer at the Front — plan

**Built 2026-10-16**, as planned below except where *As built* says otherwise. The rules now live in
RULES.md (*Magic*, *Three sides*, *Invisibility*, the errand under *Secret nodes*); this
file keeps the decisions.

**Designed 2026-10-16 (author interview).** The Faith Order's second mission. It brings in
three things the game will reuse: a **third side** on the board (hostile to everyone), **level-2
spells** (Raise Dead, Invisibility) and the **Zombie**.

Marked **(default)** = picked by me while writing the plan; the author may veto it.

## The story

Soldiers who fell at the front are getting back up days later. The Faith Order wants to know why.
The answer is a necromancer hiding, invisible, in the middle of the war, raising the dead of both
armies. Nobody sees him: the guild has to work out where the dead are rising from.

## 1. The mission

- A `MissionTemplate` on the Faith Cathedral's JOBS tab, 1 reputation through a deed like the other
  school missions. **Open to all** (not exclusive), so Faith's reachability stays safe.
- **Offered once *Mercy at the Front* is done (default)**: the story follows on from it.
- **Deadline: 14 days (default)**; a failed one comes back in 14 days, like Mercy.
- **Done = the necromancer falls.** The allied soldiers may all die: the mission does not care
  (author 2026-10-16).
- **Reward (author 2026-10-16): +1 Faith Order and the loot.** No scroll: the fight itself pays, and it
  should pay a lot. What is on the board: the necromancer's own pack (**default:** coin, gems and the
  shared spell scrolls, rolled rich for a level-15 caster), the gear of every body that fell (the
  pre-placed dead, the soldiers, the raised), and the warband's if the guild fights on (see 6).
- **Necromancy is Faith (author 2026-10-16).** Raise Dead is a Faith spell; it is a teaser of what a
  strong caster can do, not something the player learns here. Faith still needs its own level 0 and
  level 1 spells (Magic Arc item 4).
- **No search before the fight (default):** the investigation is the fight itself (the invisible
  caster, see 5). JOIN THE SKIRMISH on The Battlefield opens it for the group that holds the mission,
  like Mercy.

## 2. The board

- **A large open field (author 2026-10-16):** the Battlefield's layout (two trenches and open
  ground) on a bigger board, **48 x 30 (default)**, against today's 32 x 18. The camera already pans.
- **At night (default)**, with the trenches' watch fires as the only light: an invisible caster in
  the dark of no man's land is the point.
- **Corpses already on the field (default):** a few dead from earlier days lie in no man's land, so
  the necromancer has bodies to raise from round 1.

## 3. Four groups, three sides

| Who | Side (`team`) | Played by | Count (default) |
|---|---|---|---|
| The guild's group | `player` | the player | the squad |
| Ledger Hold soldiers | `player` (`ai_ally`) | `ai.py` | 4, two levels under the squad (as Mercy) |
| The frontier warband | `enemy` | `ai.py` | 8, one level over (more than the soldiers: author) |
| The necromancer and his dead | `undead` | `ai.py` | the necromancer + 4 Zombies at the start |

**Three real sides (author 2026-10-16):** the undead are hostile to the player's side *and* to the
warband, and the warband fights them too.

This is the new system. Today `Battle` has two hard-coded sides (`player_units` / `enemy_units`,
`winner` in `"player"` / `"enemy"`). What the third side needs:

- `Battle` holds any number of sides; "hostile" means a different `team` (most checks already read
  that way: `cells_by_side`, the `enemy` target type).
- Turn order, vision per side, `intel` (the opening read and Assess against an `undead` foe), the
  foe card, `combat_log` (frames and `rebuild`), and the board's colours (a third token colour in `T`).
- `ai.py`: the foe set is "every living unit on another team", so the warband and the undead pick
  each other too; the aggressor/search logic accepts a third side.
- **The win check is the scenario's** (`Scenario.win_check`): see 6.
- Every 2-sided fight must play exactly as before (the 2-sided path is the default; tests on the
  existing scenarios stay green).

## 4. Raise Dead (Faith, level 2)

The author's spec: **raise one dead body, it gets up with 1 HP. That is all. 2 actions.**

- Target: a body whose status is `dead` (not dying or stable), in range: **6 squares (default,
  the Dagger's thrown range, like Water Jet)**, in line of sight.
- The body stands up with **1 HP on the caster's side**, as the same body (race, gear, weapons),
  and gains the undead traits: **immune to Sleep (default)**.
- **A raised body that falls again stays dead** and cannot be raised a second time **(default)**.
- **A guild member's body can be raised** against the guild: the character was already dead, and
  stays dead after the fight.
- After the battle, raised bodies are bodies again (their gear is loot as usual).
- **Only the necromancer casts it for now (author 2026-10-16):** a teaser of high magic. No scroll, no
  study; the player's side does not get it from this mission. Built as a normal spell in
  `magic.SPELLS` (level 2, `("faith",)`), so a later source can teach it.
- Level 2 is new: check that `magic` / spell study / scrolls accept it.

## 5. Invisibility (level 2, all three schools)

**The necromancer starts the fight invisible (author 2026-10-16)**; the player has to read where
the dead are rising from.

- An invisible unit is **not seen by anyone** (`vision.can_see` false for every other unit): no
  token, no target, the AI does not know where he is.
- **Raising does not break it (default)**, or the puzzle disappears. **Dealing damage breaks it
  (default).**
- **What gives him away (default):**
  - each raise writes a log line and leaves a mark on the risen body's cell for a round ("the earth
    stirs"), so the player triangulates from the range (6);
  - a unit that steps into his cell bumps into him and reveals him to its side;
  - **Investigate** (the existing action) on a cell area reveals him with a WIS check;
  - an area effect (Dragon Breath, a Light Globe) shows him while it lasts.
- **Duration:** until broken, or the end of the fight **(default)**. Cast at the start; the AI may
  recast it when it has the AP and is not seen.
- Player use: a scroll later; it belongs to all three schools, like Sleep.

## 6. The end of the fight

- **The necromancer falls -> every undead falls with him** and the mission is done (author).
- The player then chooses **(author 2026-10-16)**:
  - **Withdraw:** the fight ends, the group leaves with what it has.
  - **Fight on:** the board stays, now two-sided (guild + soldiers against the warband), for the
    warband's loot. A loss here does not undo the mission **(default)**.
- The necromancer can also be captured (Capture, Non-lethal): it counts as fallen **(default)**.
- The guild wiped -> the mission fails.

## 7. The necromancer

- An authored NPC (`npcs/necromancer.json`), **level 15 (author)**: racial 15, so a track sum of 30
  under the racial rule, with **magic as his main track (default: combat 5 / work 10 / magic 15)**.
  Race: **Human (default)**. He casts Raise Dead, Invisibility and the shared spells.
- His AI: stay invisible and out of reach, raise the strongest body in range **(default)**, fall back
  when found. He never attacks while he still has bodies to raise.
- Portrait by hand (`/gen-portrait`).

## 8. The Zombie

- A new row in `data.UNDEAD` beside the Skeleton: **slow and tough (default)** (STR +2, DEX -2,
  CON +4, INT -4, WIS -2, CHA -4; Sleep immune; HD 8; Medium), never a player race.
- **Portraits:** the three in `assets/portraits/undead/` (author: they are the zombies); the folder
  becomes `zombie/` so the race finds them, and the pool is short (3).
- Racial tree: none for now **(default)**.
- The zombies on the field at the start are raised soldiers of both armies.

## 9. AI

- Undead: attack the nearest living unit of any other side.
- Warband and soldiers: treat the undead as foes; they cannot target the invisible necromancer.
- The necromancer: section 7.

## 10. Tests

Happy path and edges for: three sides (hostility, turn order, vision, the 2-sided path unchanged),
Raise Dead (dead only, 1 HP, side change, no second raise, a member's body), Invisibility (not
seen, not targeted, broken by damage, kept on raise, the giveaways), the necromancer's fall ending
the undead and the mission, withdraw / fight on, the Zombie race, the mission's offer / deadline /
deed, the AI per side, and a lab fight in `combat_lab`.

## Order of work

1. The third side in `Battle` (the biggest piece; nothing else plays without it).
2. Invisibility and Raise Dead (level 2, with their AI).
3. The Zombie.
4. The scenario, the necromancer NPC, the end-of-fight choice.
5. The mission, the docs (RULES, AGENTS, REFERENCE), the lab fight, tuning.

## As built (2026-10-16)

- **Investigate finds him (author 2026-10-16: one action, not two):** besides an adjacent secret wall,
  it is offered while something unseen is on the field, `d20 + WIS` against `10 + its INT` within 3 cells. A found caster is
  seen until the start of its own next turn; a wound shows it to every side; a bump shows it to the
  bumper's side. The area-effect giveaway is the wound (Dragon Breath, fire): no separate rule.
- **The dead of days before** are a fourth, never-acting side (`fallen`), laid out dead by the
  scenario; the battle skips a dead body when it rolls the first turn.
- **The loot is items and armour (author 2026-10-16), no coin:** every body on the field, the dead
  allies' included, gives up what it wore (`Scenario.strips_the_dead`, this field only). Generated foes
  wear nothing, so the raiders here wear Studded Leather and the dead of both armies their army's
  armour; the general answer is *Gold spent on equipment per level* in the backlog. The necromancer's
  pack: gems, two scrolls, potions.
- **The necromancer's stats** are his honest rolls (13, 17, 12, 7, 16, 10), arranged so INT and WIS
  lead (INT 18 with the Human +1): 96 HP, AC 12, a Light Pick he never swings while a body is left.
- **Fallen = not standing:** dying, bound or dead all meet the errand. With a Rope in the squad, the
  fight then opens its round to bind him, like any other.
- **AI against AI** (lab "necromancer", squad of 4): the AI squad loses at level 3 and at level 6;
  it never searches while it has another target in sight. A person plays the puzzle; tune after a
  playtest.
- **Not built:** the Zombie pool has 3. The necromancer's portrait came after (`portraits/npc/necromancer.png`).
