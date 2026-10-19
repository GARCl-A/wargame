# Backlog — everything still open

The one place for open work. It folds the playtest review (2026-10-05), the wagon and
camp to-do list and the later playtest notes. What is already built is in the code, its
tests and the git log; the long-range AI plan is
[campaign_ai_roadmap.md](campaign_ai_roadmap.md).

Sizes are estimates; claims about what the code already has were checked on 2026-10-18. When an item is done, delete
it here and, if it changed a design premise, record it in `AGENTS.md` or the doc that owns it.

Parts:

- **Ready to do** — the task is defined enough to start. Sorted by size: small (a sitting),
  *Playtest notes* (raw, to be sized as they are picked up), *Architecture debt* (past choices to
  pay when a feature needs them), large (a system: UI, AI and tests), *Art* (made by hand) and epic (its own arc).
- **Needs more information** — a design question, a repro or another system has to land
  before the task can be sized.
- **Starting items waiting on another system** — not a question: a list of items whose
  system does not exist yet.

The *Suggested order* below comes first.

---

# Suggested order (updated 2026-10-18)

Goal read: a sandbox open-world guild manager; the run ends only on a wipe. Balance and
sim work is ahead of the content it balances, so the order favours content verticals and
the seams they need. **The magic arc is the whole focus until it closes** (author, 2026-10-15).
**Before the playtest (author 2026-10-18):** done the same day: the founding screen redrawn, the map's crowded
names, the arena bosses' lines in the dialogue system, the post-battle report / level-up / memorial screens
(`aftermath.py`), the big screens split, the level-2 scrolls, the AI's Invisibility, composite races
(`["Snake", "Dragon"]`), the Dragon racial talents (`dragon`, `dragon_breath`), the 6-node school-agnostic
magic talent tree, non-lethal damage clearing after 24 h of unbroken rest, fresh food across larder before Rotten Food,
outdoor road/city guard scenarios (`StreetScenario`), work `LevelUpScreen`, Wilds ambush card, tavern recruitment
signature, UI overlap fixes, tutorial copy fixes, guild onboarding objectives checklist (`objectives.py`),
hearing adjacent targets in the dark with -4 obscured penalty, explicit Flee blocked reasons, CTF AI flag carrier
targeting, and `Scroll of Hex` placed in the Dragon's Lair hoard (`lair.py`).

1. **Playtest on the current build, then feed it to the AI and the sim** (*Large*): the magic
   arc's pre-playtest work is in (the walked supply run, the rite, the tier 0/1/2 spells and scrolls, the 6-node
   magic talent tree, composite races and Dragon racial talents). The AI work it waited on is done (2026-10-16);
   what the AI still lacks is a short list (*Teach the AI the newer actions*), and the weapon actions' cases are
   tuned from this playtest.
2. **Magic Arc follow-ups** (*Ready to do -> Medium*): scroll acquisition sources (deferred past the arc, author
   2026-10-17 & 2026-10-18: scrolls are never sold; they will come from enemy/boss loot and missions for their
   respective factions), sim initiation policy, and tuning after the playtest.
3. **Blood's fourth mission** (the robbed dragon strikes back): only after every test scheduled after the
   magic arc (author 2026-10-17: the playtest and the tuning it feeds).
4. **Production chain between groups** (*Large*, after magic).
5. **Talent trees as long as the levels** (*Large*, after magic).
6. **Archaeology at Ancient Ruins** (Shovel tool, discovery rolls, artifact recovery; after magic).
7. **Cooking and temporary meal buffs** (after magic).
8. **Sim planner / offers integration** (`scripts/economy_offers.py` -> policy planner), once item 1's data is in.

---

# Ready to do

## Small

- **Economy report prints a FAIL on the day-30 milestone.** `scripts/economy_report.py --quick`
  (re-run 2026-10-10, after the vocations: unchanged): the `balanced` policy reaches the milestone
  in 0% of guilds (need 50%), cost from $423. It is the known gap with the recorded runs (11-14
  days by hand), so it settles with *Feed the recorded runs* and the planner, not by tuning
  prices. **Decided 2026-10-10:** recalibrate the sim until it matches the recorded runs (both
  ~60-day saves reached day 30 easily), starting with the offers list (built). The run exits 1 on a failed verdict, but no test or gate reads it.
- **Enemy info: tune the difficulties and bonuses, after the playtest (built 2026-10-11, `intel.py`).** Only the
  numbers (author 2026-10-18): `intel.BASE_DC` 8, the bands at margin 0 / +5 / +10, `RACE_DISCOUNT` 2,
  `ASSESS_BONUS` 4 and the Scholars' +2 (`vocations.info_bonus`), read off the playtest's fights.
- **Battle map camera panning with WASD (playtest 2026-10-18).** The battle camera is currently
  only moved via mouse drag (middle/right button), while arrow keys step the active unit
  tile-by-tile. Add WASD panning to `BoardView` (`battle_screen.py`). Check key conflicts:
  hotkey `A` currently confirms an armed attack (`_confirm_armed_attack`), so rebind or
  distinguish camera panning inputs.
- **Vector line-art icons for weapon actions (`icons.py`, playtest 2026-10-18).** The 11 weapon
  actions (`sneak_attack`, `cleave`, `precise_thrust`, `repel_strike`, `maiming_strike`,
  `armor_pierce`, `power_shot`, `extreme_shot`, `hook_shield`, `javelin_charge`, `parry_strike`)
  pass `action.id` to `battle_panel.draw_action_list`, but `gartok/icons.py`'s `_GLYPHS` lacks
  glyphs for these IDs, causing the action buttons to render without icons. Add vector line-art
  draw routines for each weapon action.
- **Zero-cost node entry when already at node (`orders.py`, `map_screen.py`, playtest 2026-10-19).**
  `orders.interactive(kind, hours=APPROACH_HOURS)` currently charges 1 hour to enter a node function
  (Tavern, Shop, Forge, etc.) via `APPROACH_HOURS = 1`. If the group is already standing at the node,
  clicking to enter should cost 0 hours and open the screen directly without auto-advancing the world clock.
- **Autosell includes wagon and pack animals (`market_screen.py`, playtest 2026-10-19).** `_marked_stock`
  iterates only over `self.shoppers` (`self.group.members`), ignoring `self.stores` (`self.group.wagons`
  and `herd`). Change to `(*self.shoppers, *self.stores)` so marked items stored in wagons/carts are
  included in SELL MARKED.
- **Display crafting roll modifier on crafters panel (`crafting_screen.py`, playtest 2026-10-19).**
  `_draw_roster` shows recipe count and in-progress status, but hides the crafter's progress check modifier
  (`1d20 + INT mod + craft_bonus`). Display the net modifier (e.g. `+3` or `d20+3`) next to each crafter
  to inform recipe assignment without inspecting character sheets.
- **Rotten food eaten only as last resort against starvation death (`unit_hunger.py`, playtest 2026-10-19).**
  Daily meals currently fall back to `Rotten Food` on day 1 of missing fresh food, immediately inflicting
  Sickness (-2 attributes, prevents rest healing) instead of mild 1-day hunger. Restrict automatic
  consumption of Rotten Food to when the character would die of starvation on the next day
  (`unfed_days >= data.STARVATION_DEATH_DAYS - 1`), or when explicitly forced by the player.
- **Food consumption priority order across shared larder (`unit_hunger.py`, playtest 2026-10-19).**
  `take_ration` sorts candidates by `-days_old` (absolute age) instead of remaining shelf life
  (`lifespan - days_old`), causing durable foods like potatoes to be consumed before short-lived meats.
  Furthermore, a character currently checks only their own pack before the shared larder. Evaluate candidate
  rations from the entire shared larder (eater + members with `share_food = True`) and prioritize by lowest
  remaining lifespan (`lifespan - days_old` ascending) so foods nearing spoilage are eaten first.
- **Distribute load coin rebalancing & wagon handling (`unit_loadout.py`, `market_screen.py`, `stash_screen.py`, playtest 2026-10-19).**
  `market_screen` and `stash_screen` call `distribute_load(..., share_coins=False)`, locking coins completely
  so that characters selling or withdrawing copper become overloaded and cannot rebalance coins. Allow coin
  distribution or adjust coin redistribution so players aren't stranded with overloaded characters.
- **Locked items act as distribution magnet up to normal capacity (`unit_loadout.py`, playtest 2026-10-19).**
  In `distribute_load`, when an item is locked on a unit, prioritize pulling surplus copies of that item from
  the pool to that unit until their `carry_normal` is filled, before scattering remainder to others.
- **Map alert indicator for new faction jobs (`map_screen.py`, `missions.py`, playtest 2026-10-19).**
  Nodes currently show an alert `!` only for tavern/prison recruit rotation (`recruit.has_new_faces`). Add
  visual alert on the map node (and inspector note) when an unaccepted job is available on a node's
  mission board (e.g. Library Ancient Codex, Tanner Biwolf), so major questlines and magic unlocking
  are discoverable.

## Medium

- **Combat level stepping-stone progression (Levels 1 to 2) and encounter curve tuning (playtest 2026-10-19).**
  Level 0->1 requires 3 XP (3 kills of level 0 enemies); Level 1->2 requires 10 cumulative XP (7 kills of
  level 1+ enemies). However, downing enemies below attacker level yields 0 XP (`xp_award`), Pit Scrapper
  fields only level 0 opponents, Pit Brawl costs 30 cp, Wilds packs heavily weight level 0 beasts, and only
  the killing blow receives combat XP. Characters spend 80+ days at Work level 4 while stranded at Combat
  level 1. Design and implement a smoother combat progression curve: evaluate assist/squad combat XP
  participation, intermediate arena bouts accessible to level 1 fighters, and fractional XP or training options.

- **AI 2-action tactical lookahead with replanning (`gartok/ai.py`, playtest 2026-10-19).**
  The AI currently operates as a greedy 1-ply decision maker (`take_turn` loop spends 1 AP at a time with no
  intent memory). This causes nonsensical sequences: on AP 1 the AI shoves a player to break a flank, and on
  AP 2, finding itself out of melee reach, executes `_step_toward` and immediately walks right back into melee,
  wasting both APs with 0 net damage dealt. Implement compound 2-action evaluation with replanning:
  1. Evaluate candidate pairs of actions `(a1, a2)` (e.g. `[Shove, Retreat]`, `[Attack, Defend]`, `[Attack, Attack]`,
     `[Demoralize, Attack]`) so futile sequences like `[Shove, Walk back to target]` are eliminated.
  2. Execute `a1`.
  3. Re-evaluate the board state for `a2` given `a1`'s outcome (e.g. if Shove succeeds, execute the planned Retreat;
     if Shove fails and the target remains adjacent, pivot to Defend (+2 AC) instead of stepping into danger).

- **Magic Arc — what is left.** The rules of what is built are in RULES.md (*Secret nodes*, *Magic*, *Capture*,
  *Dragon Breath*, *Fire on the board*, *Dialogue before initiative*). Premises that stay: initiation belongs to the character; a school takes 2 reputation
  with its faction (a threshold, not spent); exclusivity is intended and the guild's choices may close a school
  (accepted 2026-10-16); the third missions are the endgame bosses, each worth a racial-15 character, so they are
  authored NPCs (generated enemies stop at `constants.ENEMY_COMBAT_CAP` / `ENEMY_WORK_CAP`); Faith consumes a Holy
  Symbol (uncommon, $80 since 2026-10-18; from the Priest's birth or a Priest's loot; shops buy it, none stocks it); Blood tests `magic_blood` first and costs no hit points. Done 2026-10-18: the magic talent tree is 6 school-agnostic nodes (`arcane_mind`, `spell_focus`, `destructive_casting`, `blessed_hands`, `focused_will`, `far_cast`), `dragon` and `dragon_breath` moved to the `Dragon` racial talent tree, and the Snake Dragon is a composite `["Snake", "Dragon"]` race (`unit.races`, attribute modifiers averaged and rounded down, HD average rounded down to `d8`, size average rounded up to `Large`, union of abilities, languages and racial talent trees). Left:
  1. *Scrolls (decided 2026-10-18):* scrolls are never sold. `Scroll of Hex` is secret loot inside the
     Dragon's Lair (`lair.py`, placed 2026-10-18); `Scroll of Spare the Dying` will be a reward from a Faith quest;
     `Scroll of Invisibility` is deferred out of this stage, to enter only with future quests. (Every spell has its scroll
     since 2026-10-18; the level-2 ones are $750, `economy.scroll_price`).
     Today the 4 level-0 Nature scrolls come as the Scribe's starting Scroll (`Magic Missile` also drops from the
     Ancient Archivist), `Sleep` is in the Ancient Ruins chest, `Raise Dead` and `Healing Touch` are carried by the
     Necromancer, `Hex` is in the Dragon's Lair hoard, `Water Jet` is the Nature Coven's Wildfire reward, and
     `Dragonfire` is the Blood Cult's Dragon's Clutch reward.
  2. *The sim does not initiate anyone:* no policy boards a member, the same multi-day investment step the Claim oven
     lacks; both land with the sim's tuning after the playtest (*Playtest on the current build*, step 4).
  3. *Blood's fourth mission* (the robbed dragon keeps attacking): not designed; not before every test scheduled
     after the arc (author 2026-10-17).
  4. *Open-ended:* future Blood bloodlines (angel and demon, author 2026-10-18); more magic XP sources (today a magic kill and a
     finished study, `progression.py`, on combat's curve as a placeholder); hatching a Dragon Egg (an author idea,
     not designed; today the egg is only sold).
  5. *Racial trees for the authored beasts:* the Dragon now has `dragon` (tier 1) and `dragon_breath` (tier 2), leaving two of Kharzuul's four picks unspent until higher tiers exist; the Zombie has no tree yet. Neither blocks anything.
  6. *Tuning, after a playtest:* the Battlefield's sides (4 soldiers at -2, 6 raiders at +1, the 6 potions); the Snake Dragon's numbers (level 8, Dragon Breath 2d6, the nest's packs), the 7-day
     captive and the 3-day corpse are first picks. **After the racial rule (2026-10-16):** the Ribbit Brothers went
     from work 2 to 4 to earn their one racial talent at racial 5, so they are mean 5 (the arena rule was boss = +1
     over an expected level 3, i.e. 4) with one more hit die each (Bufo 38 -> 44 HP, Peep 23 -> 27, Ribit 31 -> 37);
     the Ancient Archivist lost Deft Bones (3 talents at racial 10, which earns 2); the Aurochs carries work 13
     instead of a pin (same 13 HD). Re-check those fights in the lab. **The Ogre's Wildfire:** the Ogre is 4d6-drop-lowest (STR 17,
     98 HP), in Plate Armor (AC 15, speed 4) with a Huge Club; his escort is 5 at level 6 (7 at the hostile fortress).
     AI against AI in the lab (`combat_lab` "fortress", squad at mean 6): the squad wins 2/30 with four, 4/30 with
     six. Play it in the lab first (an AI squad plays far below a person), then tune the fire (2d6 a cell, 1-2 cells a
     round), the camp's crew (3 Goblins + a Hobgoblin a level over), the DCs (13 / 15, -1 a taught focus), the
     put-out (16 h, DC 13) and the meat loss (5% a burned focus, for good). **The Necromancer at the Front:** the field
     (48 x 30, night), the sides (4 soldiers at -2, 8 raiders and 4 Zombies at +1, 6 bodies), the necromancer (racial 15,
     96 HP, a raise a turn, reach 6) and Investigate's search (3 cells, WIS vs 10 + INT); AI against AI the squad loses at level 3
     and 6 (`combat_lab` "necromancer"). **The Dragon's Clutch:** the noise (stir 6, wake 14, the sounds' worth, the
     14-cell hearing), the patrols (two of three, sight 6, a torch each), the dragon (racial 20, 227 HP, AC 15, a
     Huge body the tunnel keeps out), the hoard and the egg prices ($400 at the Market, $1200 at a keeper); AI
     against AI at level 3 the squad gets out with an egg in 4 of 20 (`combat_lab` "lair"). **The dialogue
     before initiative:** every number is a first pick (`dialogue.BASE_DC` 10 +
     the leader's WIS, a bribe of $3 a foe per level + 1 and $10 a crime point for a patrol, Persuade's ±3 by
     alignment, Intimidate's ±4 and the rout at +5, the +5 initiative a failed Intimidate gives, +2 a bluff
     told in a Challenge).

## Playtest notes 2026-10-12

Raw notes from a playtest, grouped; split each into a sized item as it is picked up. Guiding
rule from the notes: **fewest possible buttons on the map**: a node has one "Enter" button and
its functions are tabs inside.

**Draft, leveling and talents**
- **Leveling templates:** player-made, editable autopick of talents, so the same clicks are not
  repeated every level.
- **Target equipment:** per unit, how it should be equipped; on entering a shop with an upgrade
  available it swaps by itself.

**Auto orders**
- **Programmable order chains for a group**, e.g. gather Lumber at the Yard -> sell Lumber and
  buy food -> gather again. Large; ties to `orders.py` and the sim's planner.

**Factions, nodes and world**
- **The Battlefield beyond the Faith mission (author 2026-10-15).** For now its only use is the Faith
  Order's errands, and it stays that way (author 2026-10-17). Later it becomes one more place of Ledger
  Hold work and missions: what an open skirmish pays, how often the front has a fight. The supply run's
  walked order with an ambush part-way (`Guild.supply_leg`, `Order.owed`) is the shape to reuse.
- **Gold spent on equipment per level (author 2026-10-15).** A table of how much kit a body of a given
  level should carry (weapon, armour, consumables), for the enemy generators (`encounters.py`, the
  Battlefield's soldiers and warband) and for future balance. Today a generated body carries its
  occupation's weapon and item whatever its level.
- **Ancient Ruins as an archaeological site:** start "archaeology" work there (deferred to after the magic arc).
  Decided 2026-10-12: complex system requiring tools (Shovel/Pick), multi-step iterations and costs to unearth artifacts, money and lost lore.
- **The Claim:** let the player build their own farm to stock food.
- **The Ogre's fortress after the Wildfire.** Convinced, it stays as a friendly node with the Ogre as its
  `Vendor` and **no function** (author 2026-10-17: it stays so; trade with him later, once richer trade
  subsystems exist).

**Balance question**
- **Which stats matter.** Playtest feel: CON > STR > DEX > CHA > INT > WIS in importance. Negative STR/CON is very punishing
  (armour is hard to wear, healing is slow); low CHA caps guild growth; the mental stats hurt little.
  Decided 2026-10-12: keep current stat severity for now; revisit attribute weighting and severity after the magic arc lands.

## Playtest notes 2026-10-18 (Claude's 30-day run from a new game)

**Not the author's playtest.** This is a run Claude played through a headless driver; the playtest in
*Suggested order* item 2 (after the magic arc) is still the author's own and still to do. A fresh Warband
guild played from the main menu to day 30 through the real UI (real clicks; some fights left to the AI). End state: 4 members, no deaths, $66 (started $89), 1 reputation,
two members sick. Screenshots and the full write-up: the "GARTOK em 30 Dias" artifact. Design questions
raised by the same run are under *Needs more information -> Playtest 2026-10-18*.

**Tutorials (review all of them)**
- Volume: about 25 modal cards, the map's with six paragraphs; the guild's goal ("what you're playing
  for") is the 12th. Decided 2026-10-18: the first card only says "this is your guild; your objectives
  are here" and points to the guild objectives list (`gartok/objectives.py`); every other card gets
  much shorter, since each stays one `?` click away.

**Discoverability**
- Nothing suggests a light source before a night hunt (a Torch is $2 and decides the fight).
- Nothing points a wounded group to the Medic.
- Ledger Hold is reachable before the Bankers hand over the chest, so the first visit is a wasted, risky
  trip. **Decided 2026-10-18:** keep as old-school exploration (`ledger_screen.py` shows a narrative gatehouse
  sentry line before the Bankers' trust test is completed).
- The Library's "A New Translation" asks for a Dictionary of an Unarchived Tongue and nothing says how
  one is made (presumably the WRITE tab).
- Direction 2026-10-18: teach at the moment of the decision (one line where the choice is made) rather
  than with a card earlier.
- The work level 2 opening (level 1 at the Yard, buy Axes, level 2: a second hit die) is the author's
  own first move every run, and nothing in the game shows it. Decided 2026-10-18: it becomes a chain in
  the guild objectives (work level 1 -> buy Axes -> work level 2), not a card.

**Darkness: fog of war (direction agreed 2026-10-18)**
- Three states per cell: never seen (black), seen before but out of light now (terrain dimmed, no units),
  visible. A first visit starts black and the torch reveals it; a known place (arena, city, the Claim)
  starts in the second state. Pairs with *heard* adjacent foes (attackable with a penalty) and a way for
  a contact-less fight to end, both under *Needs more information*.

**Sound**
- The author dropped four Kenney packs in `scratch/audios/` (impact, interface, RPG, UI; about 330 files,
  all CC0, licence files included). To explore: hits, coins, level up, UI clicks. `scratch/` is git-ignored,
  so the sounds used move to `gartok/assets/` with their licence.

**Presentation (agreed directions)**
- **A floor per place, prototype first.** Step 1: a code-drawn prototype of two boards, the Arena and
  the Wilds, rendered to images for the author to judge before anything lands (tight palette per place,
  soft tile-to-tile variation, small scattered marks, soft shadows, torch light tinting the floor; Brogue
  is the reference for simple tiles made beautiful by colour and light). Step 2, if approved: every
  place gets its own floor (Wilds grass and roots, Old Road packed earth, Arena sand and stone, the
  Ruins...); today every board is the same grey.
- **The log on the board:** floating damage numbers, a hit flash, a mark on the fallen, a crit banner.
- **Friend / foe apart from the banner colour:** a fixed ring or shape per side; the banner only as a
  detail. A red banner makes the squad and the foes the same red.
- **Bigger vendor portrait** in the shop screens, with a line of their own. Decided 2026-10-18: no accent
  colour per shop (the game would change colour all the time) and the stock stays as rows, not an icon
  grid (name and weight matter; the icons are not strong enough to lead).

## Playtest notes 2026-10-18 (Author's run: "Olhos de Odin")

The author's 21-day campaign run from a fresh game.
- **Squad & opening:** Veldrix (Kenku Mercenary), Garia (Human Musician), Ashelin (Halfling Guard).
  Started with the classic Lumber Yard work opening -> bought 2 Axes on days 2 and 5 -> stocked
  potatoes at the Farm -> Tavern & Prison visits -> entered the Pit.
- **Pit & Champion:** 3 Scrapper victories (d08, d09, d09), learning combat talents (`tough`, `strong`).
  On day 12 challenged Champion Adelio Small-Knife in "Challenge the Champion", defeating his team in
  4 rounds to claim the Champion of the Pit title (`factions.arena_dethrone`) and a $120 purse ($148 total).
  Recruitment pitch on Adelio failed. Bought two Rapiers at the Smith ($130) on day 12.
- **Turn of events & wipe:**
  - Day 19 Pit Scrapper bout: 1v3 (only Veldrix was fielded; two critical misses dropped Veldrix at
    0 HP; non-lethal knockout).
  - Day 20 Road ambush: ambushed by 3 bandits (Morskelcaz, Bexmor, Rigtikgormmir) with Pack Tactics.
    Ashelin fled round 1; Veldrix and Garia downed Morskelcaz, but bandits stabilized him and
    flanked/focused both fighters down in round 3 (lethal; both died).
  - Day 21 Wilds hunt: Ashelin hunted alone in the Wilds against 4 beasts. Downed one foe (Irtasbexma),
    which was stabilized by the pack, then was overwhelmed 3v1 by enemies with Pack Tactics (+4 to hit)
    in round 3 -> full guild wipe.
- **Player notes & takeaways:**
  1. *WASD camera panning on the battle board:* currently only middle/right mouse drag pans the camera;
     arrow keys step the active unit. Added to *Ready to do -> Small*.
  2. *Missing weapon action icons:* all 11 weapon actions render with blank icon boxes because
     `gartok/icons.py` has no glyphs for their action IDs. Added to *Ready to do -> Small*.
  3. *Weapon actions feel:* Cleave felt cool ("Cleave foi maneiro"); Cleave and Flank conditions are
     reasonable to position on the board. Rapier's Finesse makes it feel distinctly different from an Axe.
  4. *Intel feel:* Main use is reading enemy AC and sometimes HP; works well and didn't feel unfair for
     martial squads (casters still to be evaluated).
  5. *Lethality feel:* The road ambush wipe was a clear player error (fighting 2v3 without armour against
     stronger enemies with Pack Tactics, instead of retreating as a full squad).
  6. *Economy & Rest loop:* The initial Lumber Yard + Potato loop is fast and painless; 24 h of rest after
     one bout + 16 h of lumber work felt balanced and reasonable without leading to a poverty spiral.
  7. *Magic arc:* Untested in this run; left for a subsequent run reaching faction reputation 2.

## Playtest notes 2026-10-19 (Author's run: "Caneco Mijado", 100 days)

The author's 103-day campaign run from a fresh game (`ef6890c7`), archiving 33 combat logs (`Caneco-Mijado-ef6890c7`).
- **Milestones reached:** 30 battles won, 9 faction deeds completed (Arena champion dethroning Adelio,
  Bankers steady customer / good for business / diverse portfolio, Tanners hides, Library initiate,
  Apothecary mushrooms). Bank chest expanded to 30 kg. The Wilds Claim scouted, fenced, and established.
- **Caravan & Logistics:** Purchased a Donkey ($180) and Cart ($150) with Harness at the Stables.
  Divided the guild into two groups: Group 0 holding The Claim (4 members), Group 1 operating as a supply
  caravan with Donkey + Cart (4 members led by Adelio).
- **Ambush parleys:** Pre-combat dialogue occurred in 4 road ambushes: 2 successfully de-escalated
  without casualties (one by paying a 9 cp toll, another resolved peacefully for 0 cp); 2 resulted in fights.
- **Crafting & Scriptorium:** 17 crafting shifts executed: 8 roasting meat, 1 making Jerky, and 8 shifts
  by Surkaeldralka to complete the *Dictionary of Ankarin* for the Library mission.
- **The turn of events & casualties:**
  - Day 83 road ambush: Group 1 (supply caravan with Donkey + Cart) was ambushed by 2 wolves with Pack
    Tactics (one with 27 HP). Two characters entered with 1-2 HP and unfed; squad was overwhelmed in round 4,
    resulting in the death of Adelio, Rurigtikquen, Braeorn, and Felorn, and losing the Cart and Donkey.
  - Day 88 Claim seizure: Group 0 successfully retook/defended the Claim but suffered heavy injuries.
  - Day 89 road ambush: Group 0 returning on the road was ambushed by 5 humanoids; two fighters entered
    with 1 HP, and a natural 20 critical throw from a dwarven Light Pick (12 damage) dropped Nyxuln,
    resulting in heavy casualties.
- **Key takeaways & design decisions:**
  1. *Entering a node:* Clicking to enter a node the group is already standing on should cost 0 hours
     rather than advancing the world clock by `APPROACH_HOURS = 1`.
  2. *NPC talent bug:* Adelio had `negotiator` (Tier 2, requires `charismatic`) while at work level 1.
     Fixed in `npcs/adelio-small-knife.json` to `charismatic`.
  3. *Combat leveling curve (Lv 1 -> 2):* Combat leveling bottleneck: level 0 foes grant 0 XP to level 1
     fighters, only killing blows award XP, and low-level accessible arena bouts are lacking. Added to
     *Ready to do -> Medium*.
  4. *Rotten food:* Automatic daily eating of Rotten Food is a trap on day 1 of hunger; restrict automatic
     eating to starvation emergencies (`unfed_days >= STARVATION_DEATH_DAYS - 1`).
  5. *Food consumption order:* Evaluate candidates across the shared larder (`share_food`) and prioritize
     by soonest to spoil (`lifespan - days_old` ascending) rather than absolute age.
  6. *Coin distribution:* Coin rebalancing must function in market/stash/group so characters don't become
     trapped in overloaded states.
  7. *Locked items as distribution magnet:* A locked item on a unit should attract surplus copies of that
     item up to normal carrying capacity (`carry_normal`).
  8. *Crafting roll modifier visibility:* Show net roll modifier (`d20 + N`) on crafter panel.
  9. *Autosell includes wagon stores:* Include `self.stores` in `_marked_stock`.
  10. *Map alert for faction jobs:* Add map indicator `!` when an NPC faction has unaccepted jobs on its board.
  11. *AI push frequency:* The AI's 13 uses of `push` were driven by `_unflank_worth` (breaking flanking
      pairs formed by player positioning) and Mighty Shove wall-slam expected damage exceeding weapon swings.

---

## Architecture debt

Past choices that now fight the direction. Each has the cost of fixing it; pay one when the
feature that needs it is next, not before. Debts already written as part of a feature are
pointed to, not repeated.

- **Big screen files.** Split 2026-10-13 (`app.py` into `app_*.py`, `battle_draw.py`) and 2026-10-18 (`map_inspector.py`,
  `market_draw.py` / `market_trade.py`, `group_draw.py`, `taverna_draw.py`): only `map_editor_screen.py` (970),
  `guild_screen.py` (812) and `char_editor_screen.py` (807) remain over 800 lines. When one takes a new
  node or tab, split by concern instead of growing it. **Cost: low per split.**
- **Saves have no migration (on purpose).** Fine while the author is the only player. Decided 2026-10-12: keep the strict premise that "an older shape does not load"; no migration bridge needed for now. **Cost: zero.**

## Large

- **Teach the AI the newer actions: what is left.** Done 2026-10-16 (`tests/test_ai_actions.py`): the 2-point
  weapon actions are scored by expected damage (hit odds against the AC the unit can reckon: the read number,
  else 10 + the armour and shield it sees) against the two plain attacks the same points buy (one shot for a
  crossbow), so each is taken only where it pays (Cleave on two foes, Armor Pierce on heavy armour, Extreme Shot
  past the crossbow's range, Power Shot on the last arrow, Maiming Strike on a flag runner, Parry & Strike when the
  swing barely lands and foes crowd in); Throw with the last point at a foe it may drop, a flag runner, or when it
  cannot get nearer; Jump over a gap it cannot walk; Push also into a pit, a bear trap or out of a flank on itself;
  traps it sees are walked round, stopped short of and disarmed when in the way; a secret wall it is stalled beside
  is opened; a rider never walks off its mount, waits for it (Delay), dismounts beside a foe to strike, and does not
  remount with a foe in reach. Earlier: Dragon Breath, Capture and Non-lethal, fire, Mighty Shove, Water Jet,
  Dragonfire, the necromancer (`ai._necromancy`), Investigate on the unseen, the patrols (`ai._patrol`) and the
  heist (`ai._heist`). **Gauge (`combat_pairs.py combat_lab --trials 40`, 97 logs, the AI on both sides, HEAD
  before -> after):** Scrapper 49 -> 48%, the Pit's Scrapper 55 -> 63%, champion 89 -> 92%, ambushes 85 -> 92%,
  hunts 83 -> 89%, Defend the Title 46 -> 65%, brawl 92 -> 95%; the one-log Claim fights move within noise.
  `sim_test.py`: no stuck seed, 98/102, 5.4 -> 4.8 rounds a fight. After the weapon-action rebalance (same
  day): Scrapper 46%, the Pit's 63%, champion 91%, ambushes 92%, hunts 89%, Defend the Title 62%, brawl 98%,
  within a run's swing of the line above. These are the new numbers to beat.
  Left: (1) a 2-point weapon action cannot follow a walk (two points a turn): the rule, not the AI (Javelin Charge
  is the exception, 1 point after a walk since 2026-10-16); (2) done 2026-10-18: Raise Dead and Invisibility
  have scrolls, and any caster uses Invisibility as a way out (`ai._try_vanish`: when it would run, or at a third of
  its HP with a foe in reach; invisible at half or less it makes for the edge); the Necromancer carries `Scroll of Raise Dead` and `Scroll of Healing Touch`, while `Scroll of Invisibility` has no world source yet (*Magic Arc*, 1); (3) the tier 0/1 spells have their AI (2026-10-17, `ai._hex_or_roots`, `_try_healing_touch`), but Grasping
  Roots and Hex are rules of thumb, not scored in `ai._strike_worth`'s expected-damage terms; (4) Dragon Breath's breather does not move to set up a better cone.
- **Weapon actions: tune the favoured cases after a playtest.** Rebalanced 2026-10-16 (author: two plain attacks
  win in general, the 2-point action wins in its favoured case): out of its case an action is one strike; in it
  the strike lands twice over plus a small edge (RULES.md *Weapon actions*, `favoured` on each action, the
  premise held by `test_ai_actions`); Javelin Charge is 1 point after a walk. Left: whether each case comes up
  often enough (Repel Strike's wall, Maiming Strike's helpless foe, Parry & Strike's two foes, whose margin is
  the slimmest), and the old Extreme Shot / Power Shot niches.
- **Playtest on the current build, then feed it to the AI and the sim.**
  Order: (1) teach the AI the newer actions (above, done 2026-10-16), so the enemy is worth feeling;
  (2) play a fresh run on the current build with `record_play` ON (weapon actions, 2-AP actions, magic once in);
  (3) run `play_analysis.py` over the new run into a fresh profile, and re-baseline `combat_pairs.py` with the
  new campaign logs; (4) then settle *Economy report prints a FAIL* and the planner with that data. Same pass,
  the Mine's leftovers in the sim: `Crafter.pick` (`economy_guild.py`) skips every recipe with a
  `economy.MINE_SUPPLIES` input (Coal, Iron Ore, Stone Brick), so the forge's Coal recipes and Iron Bar go
  unpriced, and no policy builds the Claim oven.
- **Production chain between groups (after the magic arc, author 2026-10-15).** The first place where one
  group's output is another's input, which is the heart of the open-world vision. Lumber feeds a
  carpenter (bows, wagons: the Tanner holds the Shortbow and Light Crossbow until one exists), Coal feeds the
  Smith (Iron Bar is already a forge recipe). Gives Coal and the gems a use and closes `sources.py`'s
  `traded` goods one chain at a time. Needs recipes, a carpenter node or function, the sim's `crafter`
  policy and tests. **Lumber saturating wood price (decided 2026-10-18):** enters together with or right after
  this production chain (the Yard produces Lumber by how many work there, so endless day labour floods the market).
- **Talent trees are shorter than the levels (to be authored by hand, after the magic arc).** The XP
  curves have no top since 2026-10-16 (`progression.Curve`), and each level grants one pick: combat has
  15 nodes and work 14 (checked 2026-10-15), so a pick past the last node waits unspent and neither tree
  has room to choose. The racial
  track has 34 nodes split across races (some shared, like Giant's Grip); a race needs only 3 of
  its own (one pick at racial 5, 10 and 15), and most have 1. Goal: **at least 30
  combat and 30 work talents**, and 3+ racial nodes per race. Nothing built; the author will design them.
  The magic track (6 school-agnostic nodes since 2026-10-18) is being reviewed by the author: its size and how it is
  managed are open.
- **Gathering: loose ends (built 2026-10-11, `gather.py`, RULES.md).** The licence, the drop tables,
  the pay rule, the ambush and the sim's `gatherer` policy (and `miner` gathering once it can afford
  the licence) are in. **Retuned 2026-10-11:** a shift rolls `hours / 7` times (a rate, with the leftover as a
  chance of one more), so a full 16 h day sold is worth at least 3 copper more than the best wage (Yard 8 against
  5, Mine 14.3 against 10, `gather.PREMIUM`), and the licences are priced for a 30-day payback at that gain for 3
  workers ($270 and $385). The Snake joined the Yard's packs (Wolf 45 / Snake 30 / Giant Spider 25). Left:
  (1) **the sim says the payback is longer than the table's.** Measured over 90 days (20 guilds of 3 starter workers at level 0, skill 0.95):
  median money a member at day 30 / 60 / 90 is $37 / 107 / 172 for `lumber` and $35 / 65 / 136 for `gatherer`
  (3 of 20 wiped by the pack); with the ambush off the gatherer ends at $137. Why day 50? A starter guild of 3 works day-labour first to pool the $270 licence (reached around day 20-25); once bought, it nets about +$1.70 a day per member over day labour, not +$3: hauls lose value to rotting Fruit (24 h life), bi-daily selling cycles, and haggling. Thus cumulative money only catches up to pure day-labour around day 50. Applies to both Lumber Yard ($270) and Mine ($385; $10 road each way, higher pack risk). **Decided 2026-10-12: keep current licence prices ($270 and $385)**; the payback gap will naturally improve when future food crafting recipes allow processing Fruit into longer-lasting rations/food (preserving haul value without forced rapid resale); the Mine's higher ambush risk on the Old Road is intentional and accepted. (2) The sim plays the gathering ambush (`gather:<node>`) as real battles of the
  node's own pack, but with no recorded fights of a person against these packs, the win rate is the AI's or the
  skill knob's. (3) The shift picker shows the drops and the rolls but not the average worth of a shift against the
  wage. (4) The Mine has no art yet (the Gathering tutorial card was delivered in 2026-10-12 for both Yard and Mine).
  (5) Coal and the gems have no use but to be sold (Coal waits for the Smith's chain); Fruit is food, but it rots in
  a day, so a Yard crew eats it or sells it that evening. (6) **Snake Venom Gland:** Built 2026-10-12: `CRAFTING_RECIPES` is a dictionary of lists mapping each produced item to its recipe variants; the Antidote in the Apothecary has two recipe variants under "Antidote" (one with Spider Venom Gland and one with Snake Venom Gland), both yielding Antidote. Blade poison coating for player/enemy weapons will be a separate craft, scheduled for after the new weapon actions and traits land.
- **Item properties: base material sources (after the production chain).** Built 2026-10-11
  (`sources.py`, REFERENCE.md *Base materials*): a base material is a material, food or gem no recipe
  makes (derived), and a test fails for one with no source (gathered, dropped, hunted, foraged, quest,
  traded or spoiled; gathered and beast drops are read off `gather.TABLES` / `data.BEASTS`). Rarity per base
  material is set and each shop's target follows it (`economy.SHELVES`). Left (checked 2026-10-18): (1) the rule
  reads only `sources.RAW_TYPES` (material, food, gem), though some gear has recipes now (the Dwarf Axe, Shield
  and Armor, the Bear and Alarm traps); widen it as the Smith's chain lands. (2) Seven goods are declared `traded`:
  Potato and Sugar (Farm), Salt, 1L Beer and Vial (Market), Paper and Ink (Library); each waits for its production
  chain. Iron Bar is a forge recipe since 2026-10-12.
- **Prisoners.** (First slice built 2026-10-15 for the Snake Dragon: the Non-lethal toggle, Capture with a Rope or
  Chains, captives kept by a group for 7 days on the herd limit, `captives.py`; decided that anything captured follows
  that same scheme.) Left: what a captive is *for* beyond a mission (ransom, questioning, recruiting, the prison), the
  enemy side capturing the player's people, and rescuing a captive in battle.
- **Combat AI plays far below a person.** (Reframed 2026-10-10: on the author's own fights the AI
  playing the player's squad wins hunts 96% and ambushes 100%, so it is close to a person there;
  the gap is the arena duels. The author wins 60 of 62 against the AI and the game feels easy, so
  the lever is a smarter enemy built on what it can see (`intel.known_fields`, built), not stronger enemies.
  Wiping is the end of the run, so a person should still win almost everything.) Every economy number depends on how often the
  squad wins, and a person wins far more than `ai.py` does: measured in the economy report
  (layer 1 prints the AI's own win rate beside the skilled ones), the AI wins the Scrapper
  95%, the champion bout 75%, a Games brawl 43%, capture the flag 37%, a Wilds ambush at
  level 3 61% and the Ribbit Brothers 7%. A person wins the Pit's bouts "almost always".
  Goal: AI win rates close to a competent player's on those benchmark fights, so the sim
  (and `autowin`) stop needing a `--skill` knob. **Benchmark scenarios (decided):** Scrapper,
  Games brawl, champion, capture the flag, Ribbit Brothers, dungeon and ambush (wolves and
  bandits); the player's recorded fights on these train the policy. Start from what the AI
  does badly in the Games (objective play in capture the flag, focus fire), re-run
  `scripts/economy_activities.py` as the gauge. Needs AI changes, tests and `sim_test.py`.
  - **Way in: record the player's combat, as was done for the economy.** The recorder is built
    (2026-10-10): `combat_log.py` writes one JSONL file per fight with the whole fight, every
    decision with its legal options and what `ai.py` would have done, and each state after it;
    a controller per team (human or AI) drives `BattleScreen`; the Combat lab (Editor menu,
    `combat_lab.py`) sets up Scrapper, champion, brawl, capture the flag, Ribbit Brothers, Wilds
    and Old Road ambushes and the Ancient Ruins and logs into `combat_lab/<date>/<name>.jsonl`;
    campaign fights log into `saves/<world>/combat_logs/` while `record_play` is ON (git does not track
    `saves/`: run `scripts/archive_combat_logs.py` after playing and commit `combat_lab/campaign/`);
    `scripts/combat_analysis.py` reads them (action mix, how often a person matched the AI, a
    replay). What is left, in order:
    1. **Play the fights** (the user, in the Combat lab). **Scrapper at level 0 is done**: 10 fights,
       human (player 1) against the AI, in `combat_lab/2026-10-10/`. Left, 10 each: champion at 0-1,
       brawl and capture the flag at 1-3, Wilds and Old Road ambushes at 3, Ancient Ruins at 2-3,
       Ribbit Brothers at 3. Play to win, as you would in the campaign: the win rate comes out of the
       same logs and is the number to compare with the AI's benchmark rates. Then **two Ribbit
       Brothers fights human against human** (one decision list per side): one clean
       `boss-human-vs-human.jsonl` is in, one is still to play. The brothers changed on 2026-10-10
       (Peep and Ribit swap the Tongue for Webbed Feet, so no Lash).
    2. **Derive the policy** from the rows the way `play_analysis.py` derived the `human` economy
       profile: thresholds and priorities (when to focus fire, when to retreat, when to go for
       the flag). A new script over `combat_log.frames`.
    3. **Feed it to `ai.py`** and measure against the benchmark win rates above. The gauge is
       `scripts/combat_pairs.py` (the AI replays each logged fight through `combat_log.rebuild`, same dice
       before and after a change; campaign logs work too; `--fresh` plays unseen lab squads). Tried before
       step 5 and dropped or kept for free: Defend with a spare point (no change), an evil unit finishing a
       downed body only when no standing foe is in reach (kept, costs nothing), and waiting one turn
       instead of walking into a foe's reach (no gain on hunts). A fight swings about 8 points between runs.
    4. **Where the AI trails (read of two campaign saves, 2026-10-10).** The person won 60 of 62 fights
       (hunts and ambushes all); the AI replaying those squads wins hunts and ambushes almost as often, so
       **the gap is the arena**: Defend the Title, the Scrapper and the champion. The lost bout (day 45)
       is a 1-on-1 against a 32 HP foe the AI never beats. **Losses do write their `end` row.** Step 5
       studied the duels: they read as stat gaps more than decisions.
    5. **Tactics tried against a baseline (2026-10-11).** A better way to measure a change than the AI on
       both sides (where the two cancel out and a squad pair reads about 50%): the *challenger* plays the
       player's side with the new rule and the old `ai.py` plays the enemy's, same squads, same dice, over the
       72 finished logs x 40 trials. Baseline (the AI on both sides, after the intel and role changes):
       Scrapper 50%, the Pit's Scrapper 74%, champion 85%, hunts 89%, ambushes 93%, Defend the Title 26%.
       **Re-baselined 2026-10-11 with flanking in, `combat_pairs.py combat_lab --trials 40` (72 logs, the dice
       now fixed before the rebuild): Scrapper 49%, the Pit's Scrapper 71%, champion 91%, hunts 90%, ambushes
       93%, Defend the Title 26%.** Use these as the number to beat; a fight swings about 8 points between runs.
       **Kept:** flanking (a melee unit walks to the far side of a foe an ally already holds): 80.7% to 82.1%
       over all logs, every fight type equal or better. **Dropped, no gain or worse (arena subset, 20 logs):**
       focus fire (nearest first became weakest-reachable first with a crowd bonus, 58.6% to 56.9%), holding
       once to let a melee foe close and answering with two attacks (56.6%), demoralizing first (57.2%),
       and stopping an archer at its range (no ranged unit in the logs, identical). The arena duels did not
       move: Defend the Title stays at 26%, the lost bout is a stat gap (a 32 HP foe) and not a decision.
    Known limits of the lab: the opposing flag is always placed at random, an AI-run guild plants
    its own flag and skips its traps, and `ai.py` only knows the objectives of the enemy side.
- **Feed the recorded runs to the economy sim.** Two runs are kept in
  `recordings/2026-10-08/` (14 and 11 days, not 30; a third was judged not worth playing) with
  the `human_profile.json` that `scripts/play_analysis.py` makes from them. Run
  `economy_guild.py --policies human --profile recordings/2026-10-08/human_profile.json`.
  The `food_low_days` of 0 is real, not a recorder bug: the player shops the day the larder is
  empty (Potatoes, 4-5 days at a time), so the policy now shops *at* the threshold, not under
  it (`keep_fed(at_low=True)`). With that, all `human` guilds go hungry at some point, which
  is what the recordings show a person doing. It wipes 30-40% of 20 guilds, and that is the
  threshold, not the player: `hunt_min_level` 0.5 comes from three won hunts, and at 2.0 the
  wipe is 0% ([finding 20](economy_sim_v2.md)). **Analysed 2026-10-10 over four runs** (the two of 2026-10-08 and the 65- and 95-day saves in
  `recordings/2026-10-10/`, which add the Old Road ambushes; profile in
  `recordings/2026-10-10/human_profile_4runs.json`). The person won **68 of 70 fights** (hunts 48/48,
  ambushes 7/7, Scrapper 8/9, champion 4/4, Defend the Title 1/2). Medians: hunt at 0.71 HP and level
  0.36, bout cash $12.7 a member, food target 4.1 days, leave the yard on day 5. Run through the sim
  (`economy_guild.py --policies human --guilds 40`), the `human` guild is wiped in **65% at skill 0.8
  (the report's setting), 42% at 0.9, 30% at 0.95 and 0% at 1.0**, so the wipes are the fight win rate, not
  the thresholds (the hunt HP floor 0.92 to 0.71 alone takes the wipe from 25% to 60% at 0.8). At 1.0 the
  day-30 milestone comes in 28% of guilds, first on day 28, against 11-14 days by hand. **Decided 2026-10-10:** the report's default `--skill` is now 0.95 (it was 0.8; the verdicts did not change at
  0.95, the milestone still fails at 0%), and the sim's findings below were measured at 0.8. The day-96 wipe in the
  Gozatron save (three of five starved with $237 in hand after three days at 0 food) was the player clicking
  work without buying food; the map now raises a red card in the command bar when the larder is empty or low (`Guild.food_alert`). Then compare
  `human` with `lumber`, `balanced`, `climber`. Findings it should settle are in
  [economy_sim_v2.md](economy_sim_v2.md): the day-30 milestone, the Axe-first order, whether the
  ladder (yard, Scrapper, Games, Wilds) is how people really climb. What the runs show: the
  milestone gear (Axe each, Studded Leather or better each, strongbox) in 11-14 days against the
  sim's 49-80; the starting kit sold on day 0 to buy Axes (the sim never sells starting items);
  the Champion beaten on day 6 at combat 0 and day 12 at ~0.3; the library Dictionary mission
  turned in on day 11 (Paper + Ink bought, $250 paid). Known gaps: the other shops (Smith,
  Apothecary, Tanner) do not log purchases yet; HP before a fight is the squad's at the
  battle's start.
- **Sim policies that find the opportunities themselves.** **The offers list is built
  (`scripts/economy_offers.py`, 2026-10-10)**: one-off missions, bouts with their stake, kit worth
  selling and the work tools, each priced in copper and days; what is left is the planner that reads it
  (a hunt or forage mission's hours price one trip only, and a bout's win chance is not in the list). Every policy in `economy_guild.py` is
  a hand-written line (`rush` is the player's own, recorded). The recorded runs found things the
  earlier policies never tried: selling the starting kit on day 0, the Champion at the stake and
  not at combat 2, a one-off mission whose material is a Wilds trip away. Rebuild `maxev` (or a new
  planner) so it enumerates what is on offer (one-off missions and what each needs, bouts whose
  stake is covered, kit worth selling, gear that lifts the yard's wage), prices each in copper and
  days, and picks the order. Success is that it re-discovers the `rush` line unprompted and finds
  any line the recordings missed; `rush` stays as the reference. Then retire the guessed
  policies that it beats. Needs the planner, the offers listing (the missions, bouts and kit
  hooks the policies reach by hand today) and tests.
- **Finite stock and a target per item, in every shop.** Built 2026-10-11 in `economy.SHELVES`
  (item -> target, units a day) and `Shop.refill`: every item on the Market, the Yard, the Mine and the
  Library is finite, opens at its target and walks back a little each day (a slow item accrues a fraction;
  a surplus the player sold walks down; Hide has rate 0). The Smith, Tanner, Apothecary, Farm and
  Tavern shelves are now their own nodes' (*Specialised shops*).
  The report's verdicts did not change (the day-30 milestone still fails). A stray (an item the player sold
  a shop that is not on its shelf) is listed and resold there and stays until bought (the Library lists them on a
  RESALE tab). Left: (1) the Library's Paper 20/5 and Ink 10/2 and the Market's Lumber
  20/6 are my guesses, not from the table; (2) Jerky's $8 (tavern shelf, 10/3) is
  the batch (2 Meat + 1 Salt + 3 = $16) over its 2 units; (3) the sim's food buying now falls back to the next
  cheapest food when the cheapest runs out (a 12-day Claim trip outgrows 30 Potatoes).
- **Tune the specialised shops.** The Smithy, Tannery and Apothecary are nodes (0.5 h from Ankareth, 0.3 h between them), every node has its own shelf and the sim walks the round (2026-10-11; the report's
  verdicts did not change). What is left:
  - **Distances and bents are a first guess.** Re-run on 2026-10-11 (button labels in): verdicts unchanged, 0 exploits; the route scan (9 shops, a 43.6 h tour,
    a cap of $124/day, 10.3x the yard) is a cap and not income, and only the Mine's road makes the tour long, so `world.EDGES` stays until a playtest says the walk is wrong;
    the tongue of each shop follows its keeper's race, the alignments of the Tannery (Chaotic and Neutral),
    Library (Lawful and Evil) and Apothecary (Chaotic and Good) are authored; the Smithy (Lawful and Neutral),
    Tavern (Neutral and Good) and Farm (Lawful and Good) are picks to confirm, and so is the Farm's second
    tongue (Sylvan).
  - **Jerky is on the Tavern shelf** (10/3, $8). The report says it does not sell at a profit; check it
    does not undercut camp cooking (`cooking` tests, the Claim's food).
  - **Old saves** keep their Market stock as strays there (Axe, Potato...): harmless, listed and
    resold; a sweep on load would clean it.
  - **Production chain** (lumberjack -> carpenter, smith) and world-tied restocking are a later arc; the
    tanner holds the Shortbow and Light Crossbow until a carpenter exists.

## Art (made by hand, not code)

Portraits are engraved medallions in `gartok/assets/portraits/<race>/N.png`; the rest of the
art is game-icons.net SVG silhouettes. Portraits come from the `/gen-portrait` skill (local
Stable Diffusion + a LoRA trained on this pool, `scripts/gen_portrait.py`; about 7 minutes of
GPU a portrait, curated by hand). Each task below is its own sitting of art-making;
the ones that also need code say so. Order is the suggested priority.

- **Fill the short portrait pools.** Pools with 12+ portraits are complete (Goblin, Centaur, Kenku, Treefolk, Automaton, Gnoll, Gnome, Elf, Human, Orc, Kobold, Grippli, Halfling, Hobgoblin, Sprite). Remaining short (< 12): Ogre (3), Snake (3), Giant Spider (4), Donkey (4), Horse (4), Sheep (4), Ox (7), Wolf (8), Skeleton (9), Lizardfolk (11), Goliath (10), Dwarf (11), Zombie (3, the former `portraits/undead/`), Dragon (2), Snake Dragon (1).
- **Battle-board objects.** Dropped weapon, torch and the neutral corpse (`ground.py`) are
  drawn procedurally. Lowest priority.

## Epic

- **Riding and mounts.** Riding a Centaur ally is built (Mount / Dismount in `actions/support.py`, the
  `centaur_mount` talent; the AI rider since 2026-10-16). What is left is riding animals: a riding saddle enters
  `animals.TACK`; the rider and animal pair goes into combat. Controllable and AI-driven animals in combat (today the Shepherd's
  Sheep only stands still on the board) belong to this arc. The creature abstraction
  should not make it harder.
- **Auto battler with priority programming** (Siralim Ultimate style). Its own arc and
  branch: UI, AI and tests.

### Constraints for the wagon, animal and camp systems

Nothing there blocks anything; each item waits for a reason to build it. Keep these while
building them:

- The game is meant to get big (many groups, animals and wagons): shape these systems for
  that now and prefer the general model over a patch for the small case.
- Storage trades capacity for something: pack is free and goes to combat; chest and house
  are static and safe; a wagon is mobile, lost with the group, needs animals that eat and
  sets the trip's pace; pack animals sit between pack and wagon.
- Tack decides an animal's role (Pack Saddle carries, Harness pulls, a riding saddle later);
  the wagon is a box and transport is derived.
- Wagons never enter a battle map: when combat starts, passengers get off and fight.

---

# Needs more information

- **Playtest 2026-10-18: open design questions** (being discussed with the author, no code yet).
  - **Healing dominates the early economy.** An arena bout nets $2 and costs about 3 days of rest or
    $112-224 a member at the Medic. Author 2026-10-18: cheap healing should stay a milestone (potions
    from a production chain), so do not make healing cheap across the board. Getting wounded is intentionally
    expensive in time and food. "Rest until full" already removes the tedium; the arena side is built (non-lethal
    damage clears after 24 h of unbroken rest), and lethal recovery stays at 1 HP per 8 h at racial level 1.
  - **The world moving by itself and members with a will of their own** (a Wilds node turns into a lair
    if nobody clears it; an idle veteran asks for work or threatens to leave). The author's long-term
    vision for time pressure; non-trivial in design and code and waits on earlier subsystems.
  - **Time pressures from the world itself.** Today's time pressures (Bankers' rent, the title
    defence, the Ogre's deadline) are all ones the player chooses; nothing comes from the world itself.
    (Lumber saturating the wood price was decided 2026-10-18 to enter with/after the production chain.)
  - **Darkness vs fog on screen.** Settled as fog of war (*Ready to do*). Still open: how weather fog, if
    it ever exists, looks apart from darkness.
  - **Art direction for the board and shops.** The author is not an artist and worries that an engraved
    board, or AI-made textures, would look bad or cause trouble later.
  - **Tutorial shape.** Both coexist (author 2026-10-18): the guild objectives list (`gartok/objectives.py`)
    guides the player with small actionable tasks on the guild screen, while the modal tutorial cards remain
    to explain game systems in detail (to be shortened).

- **Magic as the vertical progression.** The biggest content gap; the arc's work is in *Ready to do -> Medium*.
  The schools are rival factions but not mutually exclusive for a character. Magic comes strictly before
  Archaeology. Still open, beyond that list: tier 2+ spells and any reputation penalty for rivalry.

- **Found-the-guild charter** (`draft_screen.py`, `vocation_screen.py`). Founding the guild should be the
  heaviest choice of the run: squad members die, the guild does not, and the player *is*
  the guild. The vocation is built (`vocations.py`, see RULES.md); what is left:
  - **Measure the Wilds perk.** The sim has the `wary` policy (`cautious` with the group always
    *Cautious*) and `--vocation`; `scripts/vocation_report.py` still does not price the Wilds
    perk. Compare `cautious` and `wary` under `--vocation wilds` at level 3+ (level 0 never
    reaches an ambush) and price the ambushes avoided.
  - **Price the Scholars' perk.** It is live since 2026-10-11 (`vocations.info_bonus`: +2 on the opening
    read and on Assess), and `vocation_report.py` does not price it yet; the perk's value is how much
    sooner a guild reads a foe, so it needs a fight-level measure, not a copper-a-day one.
  - **Oath (deferred, not scheduled)** (separate from the vocation): *what binds the members
    together, and how a stranger would tell someone belongs to the guild* (a creed, a mark, a code). It cannot be
    broken, but it can be changed. It has a mechanical side in two places: **cohesion**
    (`cohesion.py`, how members stay or leave) and a **combat/world rule** (something the
    guild will or will not do, trading a lock for a bonus). Not economy or per-faction
    reputation. Open: the list, the exact effects, how the guild is recognised in the world
    (does an NPC react to it?), and the cost of changing one.
  - **Presentation, later:** a founding charter that writes itself line by line, signed with
    the banner and the oath, kept as the first entry of the guild's chronicle. (The look of the
    founding screen itself is built.)

- **Better food (not started; direction 2026-10-09: buffs for eating good food, which leads to a
  recipe book).** Food only quells hunger today and the Potato does that at the
  lowest price, so nothing else is worth buying. Add dishes that are better and dearer and spoil
  fast (a bonus for the meal, a short `lifespan`), so what rots matters and a larder is a choice.
  Marsh's slower rot (see the charter) is priced low until this lands. **Decided 2026-10-10 & 2026-10-12:**
  cooking is an ordinary craft activity, and eating the dish gives a temporary buff that moves
  one number for 24 h (HP, an attribute, advantage on a named kind of action...). Only the most recent meal
  buff is active by default, but the data model on `Unit` stores an active buff list to support future talents that
  allow multiple buffs simultaneously. Specific upcoming recipes built 2026-10-12: (1) Jerky (2 Meat + 1 Salt); (2) Roast Meat (pure Meat + campfire, quick cooked meat); (3) Fruit Compote (introduces new base item `Sugar`; Sugar + Vial + Fruit -> long-lasting Fruit Compote, preventing gathered fruit from spoiling in 24 h). Decided 2026-10-12: neither of these two new recipes grant temporary stat buffs; their purpose is food preservation (extending lifespan of raw gathered meat and fruit). Dishes with temporary stat buffs are explicitly scheduled for AFTER the magic arc. Open: future premium dishes that grant temporary buff stats per dish, and the cost to the economy sim
  (`cheapest_food_price` stops being the one price of a meal).

---

# Starting items waiting on another system

Each occupation starts with one item (`data.OCCUPATIONS`). Rule: every occupation's item
is useful and **unique to it**, as an occupation is only a weapon and an item. Items that
already work: Meat, Potato, Quiver, 1L Beer, 1sqm Hide, Iron Bar, Lumber, 1kg Coal, Stone Brick
(the Claim oven's material), First
Aid Kit, Lantern, Scroll, Dictionary, Salt, Ink, Rope and Chains (Capture), Bear Trap, Chisel (crafting tool for Signal Horn), Holy Symbol (the Faith rite consumes it). The Merchant starts with a Semi-precious Gemstone (a store of value), and Rotten Food is the Slave's on purpose (eating it makes you sick). These wait
for a system that does not exist yet:

- **Scissors** (Barber). For shearing sheep once player husbandry/farms land (Claim/property).
- **Pliers** (Goldsmith). High-yield, long-duration jewelry crafting recipes (generating substantial money and craftable artifacts).
- **Shovel** (Grave Robber). Archaeology at Ancient Ruins (scheduled after Magic arc).
- **Map.** Finds treasures and secret zones. Waits for those systems.
- **Compass.** Avoids getting lost on very long trips through unknown paths. Waits for a
  getting-lost system.
- **Deck of Cards.** A card minigame at the tavern, among others. Its own arc.
