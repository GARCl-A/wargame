# Backlog — everything still open

The one place for open work. It folds the playtest review (2026-10-05), the wagon and
camp to-do list and the later playtest notes. What is already built is in the code, its
tests and the git log; the long-range AI plan is
[campaign_ai_roadmap.md](campaign_ai_roadmap.md).

Sizes are estimates; claims about what the code already has were checked on 2026-10-18. When an item is done, delete
it here and, if it changed a design premise, record it in `AGENTS.md` or the doc that owns it.

Parts:

- **Ready to do** — the task is defined enough to start. Sorted by size:
  *Playtest notes* (raw, to be sized as they are picked up), *Architecture debt* (past choices to
  pay when a feature needs them), large (a system: UI, AI and tests), *Art* (made by hand) and epic (its own arc).
- **Needs more information** — a design question, a repro or another system has to land
  before the task can be sized.
- **Starting items waiting on another system** — not a question: a list of items whose
  system does not exist yet.

The *Pre-playtest plan* below comes first.

---

# Pre-playtest plan (agreed 2026-10-20)

Goal: a "stable" build for the author's playtest and one with friends. Rule of the order:
what changes the numbers first, then what measures them, last what describes the final
screens. Each item's detail stays in its own entry below.

**Phase 1 — content that moves balance** (measuring AI or stats before it is rework)
1. ~~The racial track is thin~~ done 2026-10-20: 38 new nodes, every playable race and the Ox hold 3+.
2. ~~Gold spent on equipment per level~~ done 2026-10-20: `outfit.KIT_BUDGET` (from
   `scripts/wealth_by_level.py`) outfits every humanoid `build_enemy` makes.
3. ~~The Ogre's fortress~~ done 2026-10-20: the friendly fortress is the only shelf of Large weapons.

**Phase 2 — AI** (one `scripts/combat_pairs.py` run before the phase and one after, not per item)
4. ~~Teach the AI the newer actions~~ done 2026-10-20: Hex and Grasping Roots weighed in hit points
   against the point's strike (`ai._hex_worth`, `_roots_worth`), the breather walks to next turn's cone
   (`ai._breath_spot`); "a 2-point action after a walk" is the rule, not the AI, and every spell already
   had its AI (2026-10-18).
5. ~~Combat AI benchmarking against player performance~~ done 2026-10-20: flag fights replay
   (`ReplayFlagScenario`), `combat_pairs.py --set` weighs a threshold head to head and counts the dead;
   from the 40 logs: one flag runner a side, flee at 10% (neutral), no Defend with the last point.
   Before -> after (40 trials, AI on both sides): Scrapper 66 -> 67%, champion 92%, Defend the Title 65%,
   hunts 87%, ambushes 85%; capture the flag 99% and Ribbit Brothers 67% (person 5/6) now measured.
   Dead a fight in ambushes 0.51 -> 0.58: the foes also fight on to 10% now.

**Phase 3 — measure and economy** (one `scripts/economy_report.py` run at the end)
6. ~~The economy report does not measure the work talents~~ done 2026-10-20: `scripts/economy_talents.py`
   prices all 30 with and without (report section 3, WORK TALENTS; a test fails for one with no row).
   Steady Pace is the only one worth a day's wage; the hour talents are pennies at the yard's $0.31/h.
7. ~~Gathering: loose ends~~ done 2026-10-20: the shift buttons show haul / wage / ambush odds
   (`Guild.shift_worth`) and the licence's payback for the group; report section 3, GATHERING, measures the
   payback in the engine. The author's premise (2026-10-20): the licence is for a whole group left there, so no
   numbers moved. Since shifts run back to back (2026-10-21) the wage grew more than the haul: level 3, the Yard
   pays back in 47 days for 3 and 128 for 7 (the Yard's till refills $25 a day), the Mine in 86 and 70; see
   *No fatigue* below.
   The sim's gatherers now sell at the node's till then shop by shop (one till refills $25 a day).
8. ~~Finite stock and a target per item~~ done 2026-10-20: Paper 20/5, Ink 10/2 (one each a Dictionary, no
   policy buys them in 30 days) and Lumber 20/6 (never below 10) confirmed; shop Jerky ($8) stays dearer than
   the fire's (~$6.50) on purpose, and Beer (15 on the shelf, 30-day life) is too scarce to be an expedition's
   ration (author). The sim buys food by shelf life (Claim expeditions: hungry days 151 -> 90, wipes 4 -> 2 of 16).
9. ~~Which stats matter~~ done 2026-10-20: `balance_sim.py` STATS section (score per +1 modifier, race and
   occupation out). L0 / L3 geared: STR +0.024 / +0.025, CON +0.014 / +0.019, DEX +0.013 / +0.010, the mental
   three 0 in combat (they work in the world). Matches the playtest feel; nothing glaring, nothing tuned.

**Phase 4 — combat presentation** (same files: `battle_draw.py`, `lighting.py`)
10. ~~**Darkness: fog of war.**~~ done 2026-10-21: `fog.FogMemory` per side on the battle screen; no place
    starts known (author), a flag / trap placement reveals its cells.
11. **Presentation (agreed directions):** the log on the board (hit flash, crit banner left). Done 2026-10-21:
    friend / foe plate (disc / diamond, banner as a pennant), the mark of the dead, the big vendor header.
12. **Sound:** with item 11, the same events (hit, crit, fall) fire the number and the sound; coins,
    level up and UI clicks in the same pass.
13. **A floor per place:** step 1 only (the prototype images for the author to judge). Prototyped
    2026-10-21 (Arena sand and stone, Wilds grass and roots, under the per-cell light); step 2 waits
    on the author's go.
13b. **The hub screens' new layout (approved 2026-10-21):** the hub owns the header (keeper portrait,
    name, caption and bent, their line, cards per tab: the deal, the purse, the till...), a tab row
    under it and the footer; each tab draws only its body. The shop tab becomes the author's mock:
    the shelf with a cart (click adds, - / + sets the quantity, BUY hands it to whoever has room;
    a drag still buys for one member), the footer turns to SELL when pack items are picked and to
    the auto-sell when nothing is, and the party's columns. Bigger type (title ~34 px serif small
    caps, body 15-17) for these screens. Large: every hub tab screen loses its own header, one
    commit per screen.

**Phase 5 — tutorials** (last: they describe the final screens)
14. **Tutorials (review all of them)**, with the two *Discoverability* items that teach at the moment
    of the decision (the Medic for a wounded group, how the Dictionary is made).
15. **Big screen files:** split `guild_screen.py` when phase 5 touches it; the two editors stay out.

**After the playtest** (the playtest answers them, or they are content past it): weapon actions
tuning, *Tune the specialised shops*, Magic Arc tuning, production chain (Coal for the Smith, sim
crafter policy), cooking with meal buffs, the sim planner (`economy_offers.py` -> policy), the
other Magic Arc follow-ups, Prisoners, Archaeology at Ancient Ruins.


---

# Ready to do

## Medium

- **Magic Arc follow-ups (future drops, quests & tuning).**
  1. *Scroll of Invisibility:* Library quest unlocked at max library reputation + caster initiated in magic (direction 2026-10-19).
  2. *Blood's fourth mission* (robbed dragon strikes back): the dragon attacks node-by-node seeking its eggs, closest first, with consequences if nodes are destroyed; postponed to after magic arc core content (author 2026-10-19).
  3. *Tuning after playtests:* balance numbers for Battlefield, Snake Dragon, Ogre Wildfire, Necromancer at the Front, and Dragon's Clutch once further campaign runs reach them.

- **The sim's long game (found 2026-10-21).** `economy_guild.Balanced` now plays the author's line (the draft
  with Commission Tokens, Axes on day one, shift after shift with no forced sleep, the Champion at combat 0, armor,
  the strongbox): 92% of guilds meet the day-30 milestone (fastest day 13.9, the author's own playtest took 14),
  none die before it. Past it (the Pit, a recruit, the Wilds hunt as the income) 18 of 40 die by day 60, all
  hunting: a lost lethal fight takes the whole group. The sim gives the player `SKILL = 0.5` of the AI's losses in
  every fight; the author's 87 hunts measure 0.84 (arena 0.44, road ambushes ~0, `combat_pairs.py`).
  Decided 2026-10-21: keep 0.5 and leave the long game for later.

- **No fatigue: shifts run back to back (found 2026-10-21).** Rest only heals HP, clears non-lethal damage and
  sickness, and a meal falls once a calendar day whatever the hours worked, so a crew chains 16 h shifts (~1.5 a
  day; the author's 14-day milestone run did). The yard then pays about 50% over the premise's floor
  ("16 h = cheapest meal + $1"): `lumber` alone affords the day-30 milestone in about half its guilds. Open:
  a cost for going without sleep, a lower wage, or a new premise. Layer 1's floor check still counts one shift a day.

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
- **Ancient Ruins as an archaeological site:** start "archaeology" work there.
  Decided 2026-10-12 & 2026-10-19: postponed to design an innovative and fun excavation system with tools (Shovel/Pick), multi-step iterations, artifacts, money and lost lore.
- **The Claim:** let the player build their own farm to stock food.

**Balance question**

## Playtest notes 2026-10-18 (Claude's 30-day run from a new game)

**Not the author's playtest.** This is a run Claude played through a headless driver; the author's own
playtests are logged below it. A fresh Warband
guild played from the main menu to day 30 through the real UI (real clicks; some fights left to the AI). End state: 4 members, no deaths, $66 (started $89), 1 reputation,
two members sick. Screenshots and the full write-up: the "GARTOK em 30 Dias" artifact. Design questions
raised by the same run are under *Needs more information -> Playtest 2026-10-18*.

**Tutorials (review all of them)**
- Volume: about 25 modal cards, the map's with six paragraphs; the guild's goal ("what you're playing
  for") is the 12th. Decided 2026-10-18: the first card only says "this is your guild; your objectives
  are here" and points to the guild objectives list (`gartok/objectives.py`); every other card gets
  much shorter, since each stays one `?` click away.

**Discoverability**
- Nothing points a wounded group to the Medic.
- Ledger Hold is reachable before the Bankers hand over the chest, so the first visit is a wasted, risky
  trip. **Decided 2026-10-18:** keep as old-school exploration (`ledger_screen.py` shows a narrative gatehouse
  sentry line before the Bankers' trust test is completed).
- The Library's "A New Translation" asks for a Dictionary of an Unarchived Tongue and nothing says how
  one is made (presumably the WRITE tab).
- Direction 2026-10-18: teach at the moment of the decision (one line where the choice is made) rather
  than with a card earlier.

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
- **The log on the board:** floating damage numbers (built, `battle_fx.py`) and the mark of the dead (built);
  left: a hit flash, a crit banner.

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
- **Open takeaway:** Combat leveling bottleneck (Lv 1 -> 2) resolved by rebalancing Wilds encounter weights to 60% Lv 1 (commit `142b6f5`); deeper assist XP / intermediate arena bout deferred to future playtests.

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

- **Weapon actions: tune the favoured cases after a playtest.** Rebalanced 2026-10-16 (author: two plain attacks
  win in general, the 2-point action wins in its favoured case): out of its case an action is one strike; in it
  the strike lands twice over plus a small edge (RULES.md *Weapon actions*, `favoured` on each action, the
  premise held by `test_ai_actions`); Javelin Charge is 1 point after a walk. Left: whether each case comes up
  often enough (Repel Strike's wall, Maiming Strike's helpless foe, Parry & Strike's two foes, whose margin is
  the slimmest), and the old Extreme Shot / Power Shot niches.
- **Production chain between groups (after the magic arc, author 2026-10-15).** The first place where one
  group's output is another's input, which is the heart of the open-world vision. Carpenter node opened
  on 2026-10-19 (crafting station for bows, crossbows, spear, club, torch; Rowan keeper; bows migrated from Tanner).
  Next: Coal for Smith (Iron Bar recipe), wagon crafting, a crafting branch for the sim's `balanced` policy and tests. Gives Coal and the
  gems a use and closes `sources.py`'s `traded` goods one chain at a time. **Market supply and demand / lumber saturation:**
  simulate relatively complex market dynamics with supply and demand (so endless day labour at the Yard floods wood prices).
- **Item properties: base material sources (after the production chain).**
  Left: (1) widen base materials beyond `RAW_TYPES` to include gear recipes as the Smith's chain lands; (2) seven declared `traded` goods (Potato, Sugar, Salt, 1L Beer, Vial, Paper, Ink) awaiting their production chains.
- **Prisoners.**
  Decided 2026-10-19: (1) sell to City Prison via interactive tab/dialogue for bounty based on captive level/crime; (2) recruit contest; (3) forced manual labor in lumber/mine: captive eats group food (or starves), escape/revolt check fires daily after captive recovers to full HP. Left: UI tabs, escape check implementation, enemy capturing player units, and battlefield rescue.
- **Sim policies that find the opportunities themselves.**
  Offers list built (`scripts/economy_offers.py`); left: policy planner that enumerates and prices offers dynamically in copper and days.
- **Tune the specialised shops.**
  Left: confirm distances and alignments of shop keepers; verify world-tied restocking (carpenter node verified 2026-10-19).

## Art (made by hand, not code)

Portraits are engraved medallions in `gartok/assets/portraits/<race>/N.png`; the rest of the
art is game-icons.net SVG silhouettes. Portraits come from the `/gen-portrait` skill (local
Stable Diffusion + a LoRA trained on this pool, `scripts/gen_portrait.py`; about 7 minutes of
GPU a portrait, curated by hand). Each task below is its own sitting of art-making;
the ones that also need code say so. Order is the suggested priority.

- **Fill the short portrait pools.** Pools with 12+ portraits are complete (Goblin, Centaur, Kenku, Treefolk, Automaton, Gnoll, Gnome, Elf, Human, Orc, Kobold, Grippli, Halfling, Hobgoblin, Sprite). Remaining short (< 12): Ogre (3), Snake (3), Giant Spider (4), Donkey (4), Horse (4), Sheep (4), Ox (7), Wolf (8), Skeleton (9), Lizardfolk (11), Goliath (10), Dwarf (11), Zombie (3, the former `portraits/undead/`), Dragon (2), Snake Dragon (1).
- **The Mine's art.** The Mine (a gathering node since 2026-10) has no visual of its own on the map
  or its screens; the Lumber Yard's look is the model.
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
  - **Darkness vs fog on screen.** Settled as fog of war (done 2026-10-21). Still open: how weather fog, if
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
  - **Measure the Wilds perk.** The sim takes `--vocation`; `scripts/vocation_report.py` still does
    not price the Wilds perk. Run `balanced` under `--vocation wilds` with its group's stance set to
    *Cautious* against the same on *Normal*, past the milestone (the hunts), and price the ambushes avoided.
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
  one number for 24 h (HP, an attribute, advantage on a named kind of action...). Confirmed 2026-10-19: strictly only the most recent meal
  buff is active (eating a new meal buff overwrites the previous one). Specific upcoming recipes built 2026-10-12: (1) Jerky (2 Meat + 1 Salt); (2) Roast Meat (pure Meat + campfire, quick cooked meat); (3) Fruit Compote (introduces new base item `Sugar`; Sugar + Vial + Fruit -> long-lasting Fruit Compote, preventing gathered fruit from spoiling in 24 h). Decided 2026-10-12: neither of these two new recipes grant temporary stat buffs; their purpose is food preservation (extending lifespan of raw gathered meat and fruit). Dishes with temporary stat buffs are explicitly scheduled for AFTER the magic arc. Open: future premium dishes that grant temporary buff stats per dish, and the cost to the economy sim
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
