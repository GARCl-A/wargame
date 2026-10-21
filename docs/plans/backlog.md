# Backlog — everything still open

The one place for open work. What is already built is in the code, its tests and the git
log; the long-range AI plan is [campaign_ai_roadmap.md](campaign_ai_roadmap.md).

Sizes are estimates; claims about what the code already has were checked on 2026-10-21. When an item is done, delete
it here and, if it changed a design premise, record it in `AGENTS.md` or the doc that owns it.

Parts:

- **Pre-playtest plan** — what is left before the author's playtest, in order.
- **Ready to do** — the task is defined enough to start, sorted by size.
- **Needs more information** — a design question, a repro or another system has to land
  before the task can be sized.
- **Starting items waiting on another system** — items whose system does not exist yet.

---

# Pre-playtest plan (agreed 2026-10-20)

Goal: a "stable" build for the author's playtest and one with friends. Phases 1-3 (content,
AI, measure and economy) and the fog of war are done; what is left:

**Phase 4 — combat presentation** (same files: `battle_draw.py`, `lighting.py`)
1. **The log on the board:** a hit flash and a crit banner. The floating damage numbers
   (`battle_fx.py`), the friend / foe plate and the mark of the dead are built.
2. **Sound:** with item 1, the same events (hit, crit, fall) fire the number and the sound; coins,
   level up and UI clicks in the same pass. The author dropped four Kenney packs in `scratch/audios/`
   (impact, interface, RPG, UI; about 330 files, all CC0, licence files included). `scratch/` is
   git-ignored, so the sounds used move to `gartok/assets/` with their licence.
3. **A floor per place, step 2** (waits on the author's go). Step 1, the prototype (Arena sand and
   stone, Wilds grass and roots, under the per-cell light), was rendered 2026-10-21. Step 2: every
   place gets its own floor (Wilds grass and roots, Old Road packed earth, Arena sand and stone, the
   Ruins...); today every board is the same grey. Brogue is the reference.
4. **Hub tab bodies in the new type.** The frame (`ui/hub_frame.py`) and the shop tab are done and every
   tab sits inside the frame; the other bodies (Tavern, Stables, Forge / Carpentry / Write, the jobs
   boards, Medic, Initiation, Gathering, the Bank's vault) are still drawn in the old small type.
   Restyle each in the hub kit as the shop (title ~34 px serif small caps, body 15-17), one commit per screen.

**Phase 5 — tutorials** (last: they describe the final screens)
5. **Tutorials (review all of them).** About 25 modal cards, the map's with six paragraphs; the guild's
   goal is the 12th. Decided 2026-10-18: the first card only says "this is your guild; your objectives
   are here" and points to the objectives list (`gartok/objectives.py`); every other card gets much
   shorter, since each stays one `?` click away. Both coexist: the objectives list guides with small
   tasks, the cards explain the systems. With it, teach at the moment of the decision (one line where
   the choice is made):
   - nothing points a wounded group to the Medic;
   - the Library's "A New Translation" asks for a Dictionary of an Unarchived Tongue and nothing says
     how one is made (the WRITE tab).
6. **Big screen files:** split `guild_screen.py` (812 lines) when phase 5 touches it; the two editors
   (`map_editor_screen.py` 970, `char_editor_screen.py` 807) stay out. When any of them takes a new
   node or tab, split by concern instead of growing it.

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

- **The sim's long game (found 2026-10-21).** `economy_guild.Balanced` plays the author's line: 92% of guilds
  meet the day-30 milestone, none die before it. Past it (the Pit, a recruit, the Wilds hunt as the income) 18 of
  40 die by day 60, all hunting: a lost lethal fight takes the whole group. The sim gives the player `SKILL = 0.5`
  of the AI's losses in every fight; the author's 87 hunts measure 0.84 (arena 0.44, road ambushes ~0,
  `combat_pairs.py`). Decided 2026-10-21: keep 0.5 and leave the long game for later.

- **No fatigue: shifts run back to back (found 2026-10-21).** Rest only heals HP, clears non-lethal damage and
  sickness, and a meal falls once a calendar day whatever the hours worked, so a crew chains 16 h shifts (~1.5 a
  day). The yard then pays about 50% over the premise's floor ("16 h = cheapest meal + $1"): `lumber` alone
  affords the day-30 milestone in about half its guilds, and the licence pays back in 47 days for 3 at the Yard,
  128 for 7 (its till refills $25 a day), the Mine in 86 and 70. Open: a cost for going without sleep, a lower
  wage, or a new premise. Layer 1's floor check still counts one shift a day.

- **The work tree's STR root breaks the pattern (author 2026-10-21).** Five of the six work roots are
  "+1 attribute" (Charismatic, Clever, Nimble Fingers, Sturdy, Observant); the STR root is `carrier`
  (+1 kg of gear before staggering), not "+1 Strength" (`talents.py`, the work block). Open: make the STR
  root +1 Strength and move Carrier's carry buffer deeper in the branch (or fold it into Heavy Haul),
  then re-run `scripts/economy_talents.py` and fix REFERENCE.md.

## Playtest notes 2026-10-12

Raw notes, to be sized as they are picked up. Guiding rule: **fewest possible buttons on the
map**: a node has one "Enter" button and its functions are tabs inside.

- **Leveling templates:** player-made, editable autopick of talents, so the same clicks are not
  repeated every level.
- **Target equipment:** per unit, how it should be equipped; on entering a shop with an upgrade
  available it swaps by itself.
- **Programmable order chains for a group**, e.g. gather Lumber at the Yard -> sell Lumber and
  buy food -> gather again. Large; ties to `orders.py` and the sim's planner.
- **The Battlefield beyond the Faith mission.** For now its only use is the Faith Order's errands, and
  it stays that way (author 2026-10-17). Later it becomes one more place of Ledger Hold work and missions:
  what an open skirmish pays, how often the front has a fight. The supply run's walked order with an
  ambush part-way (`Guild.supply_leg`, `Order.owed`) is the shape to reuse.
- **Ancient Ruins as an archaeological site:** start "archaeology" work there. Postponed (2026-10-12 &
  2026-10-19) to design an excavation system with tools (Shovel / Pick), multi-step iterations,
  artifacts, money and lost lore.
- **The Claim:** let the player build their own farm to stock food.
- **Combat leveling (Lv 1 -> 2):** the Wilds weights were fixed (`142b6f5`); assist XP or an
  intermediate arena bout wait on future playtests.

## Large

- **Weapon actions: tune the favoured cases after a playtest.** Rebalanced 2026-10-16: out of its case an
  action is one strike; in it the strike lands twice over plus a small edge (RULES.md *Weapon actions*,
  `favoured` on each action, the premise held by `test_ai_actions`). Left: whether each case comes up
  often enough (Repel Strike's wall, Maiming Strike's helpless foe, Parry & Strike's two foes, whose margin is
  the slimmest), and the old Extreme Shot / Power Shot niches.
- **Production chain between groups (after the magic arc, author 2026-10-15).** The first place where one
  group's output is another's input, the heart of the open-world vision. The Carpenter is open (2026-10-19).
  Next: Coal for the Smith (Iron Bar recipe), wagon crafting, a crafting branch for the sim's `balanced`
  policy and tests. Gives Coal and the gems a use and closes `sources.py`'s `traded` goods one chain at a time.
  **Market supply and demand / lumber saturation:** endless day labour at the Yard should flood wood prices.
- **Item properties: base material sources (after the production chain).**
  (1) widen base materials beyond `RAW_TYPES` to include gear recipes as the Smith's chain lands; (2) seven
  declared `traded` goods (Potato, Sugar, Salt, 1L Beer, Vial, Paper, Ink) awaiting their production chains.
- **Prisoners.** Decided 2026-10-19: (1) sell to City Prison via interactive tab/dialogue for bounty based on
  captive level/crime; (2) recruit contest; (3) forced manual labor in lumber/mine: captive eats group food (or
  starves), escape/revolt check fires daily after captive recovers to full HP. Left: UI tabs, escape check,
  enemy capturing player units, and battlefield rescue.
- **Sim policies that find the opportunities themselves.** The offers list is built (`scripts/economy_offers.py`);
  left: a policy planner that enumerates and prices offers dynamically in copper and days.
- **Tune the specialised shops.** Confirm distances and alignments of shop keepers; verify world-tied
  restocking (the Carpenter is verified).

## Art (made by hand, not code)

Portraits are engraved medallions in `gartok/assets/portraits/<race>/N.png` from the `/gen-portrait`
skill (about 7 minutes of GPU a portrait, curated by hand); the rest is game-icons.net SVG
silhouettes. Order is the suggested priority.

- **Fill the short portrait pools** (12 is complete). Short: Snake Dragon (1), Dragon (2), Ogre (3),
  Snake (3), Zombie (3), Giant Spider (4), Donkey (4), Horse (4), Sheep (4), Ox (7), Wolf (8),
  Skeleton (9), Goliath (10), Dwarf (11), Lizardfolk (11).
- **The Mine's art.** The Mine has no visual of its own on the map or its screens; the Lumber Yard's
  look is the model.
- **Battle-board objects.** Dropped weapon, torch and the neutral corpse (`ground.py`) are
  drawn procedurally. Lowest priority.

## Epic

- **Riding and mounts.** Riding a Centaur ally is built. Left: riding animals (a riding saddle enters
  `animals.TACK`; the rider and animal pair goes into combat), and controllable / AI-driven animals in
  combat (today the Shepherd's Sheep only stands still). The creature abstraction should not make it harder.
- **Auto battler with priority programming** (Siralim Ultimate style). Its own arc and
  branch: UI, AI and tests.

### Constraints for the wagon, animal and camp systems

Keep these while building them:

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

- **Open design questions from the 2026-10-18 playtests** (no code yet).
  - **The world moving by itself and members with a will of their own** (a Wilds node turns into a lair
    if nobody clears it; an idle veteran asks for work or threatens to leave). The author's long-term
    vision for time pressure; waits on earlier subsystems.
  - **Time pressures from the world itself.** Today's (Bankers' rent, the title defence, the Ogre's
    deadline) are all ones the player chooses. Lumber saturating the wood price enters with the production chain.
  - **Weather fog**, if it ever exists: how it looks apart from darkness.
  - **Art direction for the board and shops.** The author is not an artist and worries that an engraved
    board, or AI-made textures, would look bad or cause trouble later.

- **Magic as the vertical progression.** The arc's work is in *Ready to do -> Medium*. The schools are
  rival factions but not mutually exclusive for a character; magic comes strictly before Archaeology.
  Open: tier 2+ spells and any reputation penalty for rivalry.

- **Found-the-guild charter** (`draft_screen.py`, `vocation_screen.py`). The vocation is built; left:
  - **Measure the Wilds perk.** `scripts/vocation_report.py` does not price it. Run `balanced` under
    `--vocation wilds` with the group on *Cautious* against *Normal*, past the milestone (the hunts),
    and price the ambushes avoided.
  - **Price the Scholars' perk** (`vocations.info_bonus`: +2 on the opening read and on Assess). Its value
    is how much sooner a guild reads a foe, so it needs a fight-level measure, not a copper-a-day one.
  - **Oath (deferred, not scheduled):** what binds the members together and how a stranger would tell
    someone belongs to the guild (a creed, a mark, a code). Cannot be broken, can be changed. Mechanics in
    **cohesion** (`cohesion.py`) and a **combat/world rule** (a lock for a bonus); not economy or
    reputation. Open: the list, the effects, whether NPCs react to it, the cost of changing one.
  - **Presentation, later:** a founding charter that writes itself line by line, signed with the banner
    and the oath, kept as the first entry of the guild's chronicle.

- **Better food: dishes with buffs (after the magic arc).** Food only quells hunger and the Potato does it
  cheapest. The preservation recipes are built (Jerky, Roast Meat, Fruit Compote; no buffs, by design).
  Decided: cooking is an ordinary craft; a premium dish gives a 24 h buff that moves one number (HP, an
  attribute, advantage on a named kind of action...), and only the most recent meal's buff is active.
  Open: the dishes and their buffs, and the cost to the economy sim (`cheapest_food_price` stops being
  the one price of a meal). Marsh's slower rot is priced low until this lands.

---

# Starting items waiting on another system

Each occupation starts with one item (`data.OCCUPATIONS`), useful and **unique to it**. These wait
for a system that does not exist yet:

- **Scissors** (Barber). Shearing sheep once player husbandry/farms land (Claim/property).
- **Pliers** (Goldsmith). High-yield, long-duration jewelry crafting (money and craftable artifacts).
- **Shovel** (Grave Robber). Archaeology at Ancient Ruins (after the magic arc).
- **Map** (Cartographer). Finds treasures and secret zones.
- **Compass** (Guide). Avoids getting lost on very long trips; waits for a getting-lost system.
- **Deck of Cards** (Gambler). A card minigame at the tavern, among others. Its own arc.
