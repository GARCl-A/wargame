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

# Suggested order (updated 2026-10-19)

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
**Shipped 2026-10-19:** combat camera WASD pan, attack confirmation Enter/F, 11 weapon action vector icons (`icons.py`),
zero-cost node entry when already present, autosell stores support, crafting roll modifier display, rotten food
starvation emergency restriction, shelf-life prioritized shared larder consumption, coin rebalance & locked item
magnet in distribute load, map alert `!` for faction jobs, AI 2-action tactical lookahead with replanning (`ai.py`),
archived 40 campaign playtest logs and extracted human profile (`recordings/2026-10-19/`), calibrated Balanced policy
and resolved day-30 milestone verdict in economy report.

1. **Magic Arc follow-ups** (*Ready to do -> Medium*): scroll acquisition sources (deferred past the arc, author
   2026-10-17 & 2026-10-18: scrolls are never sold; they will come from enemy/boss loot and missions for their
   respective factions), sim initiation policy, and tuning after the playtest.
2. **Blood's fourth mission** (the robbed dragon strikes back): only after every test scheduled after the
   magic arc (author 2026-10-17: the playtest and the tuning it feeds).
3. **Production chain between groups** (*Large*, after magic).
4. **Talent trees as long as the levels** (*Large*, after magic).
5. **Archaeology at Ancient Ruins** (Shovel tool, discovery rolls, artifact recovery; after magic).
6. **Cooking and temporary meal buffs** (after magic).
7. **Sim planner / offers integration** (`scripts/economy_offers.py` -> policy planner).

---

# Ready to do

## Medium

- **Combat level stepping-stone progression (Levels 1 to 2) and encounter curve tuning (playtest 2026-10-19).**
  Level 0->1 requires 3 XP (3 kills of level 0 enemies); Level 1->2 requires 10 cumulative XP (7 kills of
  level 1+ enemies). However, downing enemies below attacker level yields 0 XP (`xp_award`), Pit Scrapper
  fields only level 0 opponents, Pit Brawl costs 30 cp, Wilds packs heavily weight level 0 beasts, and only
  the killing blow receives combat XP. Characters spend 80+ days at Work level 4 while stranded at Combat
  level 1. Design and implement a smoother combat progression curve: evaluate assist/squad combat XP
  participation, intermediate arena bouts accessible to level 1 fighters, and fractional XP or training options.

- **Magic Arc — what is left.**
  1. *Scroll sources:* `Scroll of Hex` is placed in Dragon's Lair hoard (`lair.py`); `Scroll of Spare the Dying` has 0.1% drop chance on Battlefield enemy defeat (`loot.py`); `Scroll of Invisibility`: Library quest unlocked at max library reputation + caster initiated in magic (direction 2026-10-19).
  2. *Sim initiation policy:* no policy boards a member; lands with sim tuning after playtests.
  3. *Blood's fourth mission* (robbed dragon strikes back): the dragon attacks node-by-node seeking its eggs, closest first, with consequences if nodes are destroyed; postponed to after magic arc core content (author 2026-10-19).
  4. *Racial trees for authored beasts:* Zombie has no racial tree yet; Dragon Kharzuul has higher tier picks unspent.
  5. *Tuning after playtests:* balance numbers for Battlefield, Snake Dragon, Ogre Wildfire, Necromancer at the Front, and Dragon's Clutch.

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
- **Player notes & feel:**
  - *Weapon actions:* Cleave felt cool ("Cleave foi maneiro"); Cleave and Flank conditions are
    reasonable to position on the board. Rapier's Finesse makes it feel distinctly different from an Axe.
  - *Intel:* Main use is reading enemy AC and sometimes HP; works well and felt fair for martial squads.
  - *Lethality:* The road ambush wipe was a clear player error (fighting 2v3 without armour against
    stronger enemies with Pack Tactics, instead of retreating as a full squad).
  - *Economy & Rest loop:* The initial Lumber Yard + Potato loop is fast and painless; 24 h of rest after
    one bout + 16 h of lumber work felt balanced and reasonable without leading to a poverty spiral.
  - *Magic arc:* Untested in this run; left for a subsequent run reaching faction reputation 2.

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
- **Open takeaway:** Combat leveling bottleneck (Lv 1 -> 2) tracked in *Ready to do -> Medium*.

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

- **Teach the AI the newer actions: what is left.**
  Left: (1) a 2-point weapon action cannot follow a walk (two points a turn; Javelin Charge is 1 point after walk); (2) AI use of scrolls for all spell types; (3) Grasping Roots and Hex scored in expected-damage terms rather than rule of thumb; (4) Dragon Breath breather moving to position optimal cones.
- **Weapon actions: tune the favoured cases after a playtest.** Rebalanced 2026-10-16 (author: two plain attacks
  win in general, the 2-point action wins in its favoured case): out of its case an action is one strike; in it
  the strike lands twice over plus a small edge (RULES.md *Weapon actions*, `favoured` on each action, the
  premise held by `test_ai_actions`); Javelin Charge is 1 point after a walk. Left: whether each case comes up
  often enough (Repel Strike's wall, Maiming Strike's helpless foe, Parry & Strike's two foes, whose margin is
  the slimmest), and the old Extreme Shot / Power Shot niches.
- **Production chain between groups (after the magic arc, author 2026-10-15).** The first place where one
  group's output is another's input, which is the heart of the open-world vision. Lumber feeds a
  carpenter (bows, wagons: the Tanner holds the Shortbow and Light Crossbow until one exists), Coal feeds the
  Smith (Iron Bar is already a forge recipe). Gives Coal and the gems a use and closes `sources.py`'s
  `traded` goods one chain at a time. Needs recipes, a carpenter node or function, the sim's `crafter`
  policy and tests. **Lumber saturating wood price (decided 2026-10-18):** enters together with or right after
  this production chain (the Yard produces Lumber by how many work there, so endless day labour floods the market).
- **Talent trees are shorter than the levels (to be authored by hand, after the magic arc).** The XP
  curves have no top since 2026-10-16 (`progression.Curve`), and each level grants one pick: combat has
  25 nodes (updated 2026-10-19 with CHA and INT branches) and work 14, so work picks past the last node wait unspent
  and neither tree has full room to choose. The racial
  track has 34 nodes split across races (some shared, like Giant's Grip); a race needs only 3 of
  its own (one pick at racial 5, 10 and 15), and most have 1. Goal: **at least 30
  combat and 30 work talents**, and 3+ racial nodes per race. Only 5 combat nodes remain to hit the 30-talent goal;
  work track requires further expansion.
  The magic track (6 school-agnostic nodes since 2026-10-18) is being reviewed by the author: its size and how it is
  managed are open.
- **Gathering: loose ends.**
  Left: (1) sim payback gap calibration vs day labour; (2) shift picker displaying average worth of a shift against wage; (3) Mine visual art. (Fruit preservation completed with Fruit Compote recipe).
- **Item properties: base material sources (after the production chain).**
  Left: (1) widen base materials beyond `RAW_TYPES` to include gear recipes as the Smith's chain lands; (2) seven declared `traded` goods (Potato, Sugar, Salt, 1L Beer, Vial, Paper, Ink) awaiting their production chains.
- **Prisoners.**
  Left: what a captive is for beyond a mission (decided 2026-10-19: sell to prison if bandit/outlaw, recruit or enslave), enemy side capturing player's units, and rescuing a captive in battle.
- **Combat AI benchmarking against player performance.**
  Current benchmark across the 40 campaign logs (`combat_pairs.py`): Scrapper 77% (player 80%), Champion 90% (player 100%), Defend Title 95% (player 100%), hunts 92% (player 92%), road ambushes 72% AI vs 40% player.
  Left: derive combat policy thresholds into `ai.py` (retreating when low HP, objective prioritization in CTF).
- **Sim policies that find the opportunities themselves.**
  Offers list built (`scripts/economy_offers.py`); left: policy planner that enumerates and prices offers dynamically in copper and days.
- **Finite stock and a target per item, in every shop.**
  Left: confirm Paper 20/5, Ink 10/2 and Lumber 20/6 shelf targets; verify Jerky ($8, 10/3) doesn't undercut camp cooking; sim food fallback for long expeditions.
- **Tune the specialised shops.**
  Left: confirm distances and alignments of shop keepers; verify world-tied restocking and carpenter node.

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
