# Backlog — everything still open

The one place for open work. What is already built is in the code, its tests and the git
log; the long-range AI plan is [campaign_ai_roadmap.md](campaign_ai_roadmap.md).

Sizes are estimates; claims about what the code already has were checked on 2026-10-22. When an item is done, delete
it here and, if it changed a design premise, record it in `AGENTS.md` or the doc that owns it.

Parts:

- **Pre-playtest plan** — what is left before the author's playtest, in order.
- **Ready to do** — the task is defined enough to start, sorted by size.
- **Needs more information** — a design question, a repro or another system has to land
  before the task can be sized.
- **Starting items waiting on another system** — items whose system does not exist yet.

---

# Web front-end (decided 2026-10-23)

The presentation moves from pygame to HTML/CSS/Canvas, and the Python core stays. The battle
spike is built (`python -m gartok.web`), and the author's verdict is go. The decisions so far
and the next steps are in [web_frontend.md](web_frontend.md), in this order:

1. fluidity (the AI's turn played step by step)
2. light
3. colour
4. parity with the pygame battle
5. speed on big boards
6. migrating the other screens

---

# Pre-playtest plan (agreed 2026-10-20)

Goal: a "stable" build for the author's playtest and one with friends. Phases 1-4 (content,
AI, measure and economy, combat presentation: the fog of war, the log on the board with its sound,
a floor per place in `ui/floors.py`, every screen on the hub kit) are done; what is left:

**Phase 5 — tutorials** (last: they describe the final screens)
5. **Tutorials.** Done 2026-10-21: every card checked against the code and cut to the rule it
   teaches (~4,800 words -> ~3,000); the map's card closes onto the objectives (17, all open,
   `gartok/objectives.py`); the wounded group's Medic line and the Library's WRITE hint are in.
   Left: the author reads every card in play and flags what still rings false.
6. **Big screen files:** split `guild_screen.py` (~800 lines) when phase 5 touches it; the two editors
   (`map_editor_screen.py`, `char_editor_screen.py`, ~800-970) stay out. When any of them takes a new
   node or tab, split by concern instead of growing it.

**After the playtest** (the playtest answers them, or they are content past it): weapon actions
tuning, *Tune the specialised shops*, Magic Arc tuning, production chain (the sim's crafter policy:
smelting Iron Bar, Coal's use), cooking with meal buffs, the sim planner (`economy_offers.py` -> policy), the
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

## Playtest notes 2026-10-21 (guild Herança)

Raw notes from the author's playtest, to be sized as they are picked up.

- **Presentation:**
  - The pause menu (Esc) lists many options that belong behind one SETTINGS entry.
  - Too few icons for the guild banner.
- **World and soul:** the world needs story depth before the Archaeology arc; the game still lacks "soul".
- **Occupations are bland:** today they only roll the starting items. Give each one a reason to matter
  (proposed answer: the drama engine, *Needs more information*).
- **Combat board:**
  - Shadows and fog of war are not continuous: hard to tell fog (not seen) from darkness (seen, unlit).
  - Hit sounds do not fit the game (the UI sounds are fine); swap the Kenney variants in `assets/sounds/`.

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
  artifacts, money and lost lore. The Ruins now remember a raid (`Guild.ruins_cleared`) and drop off the
  inspector once empty, so a dig needs the node to keep offering something after it is cleared.
- **The Claim:** let the player build their own farm to stock food.
- **Combat leveling (Lv 1 -> 2):** the Wilds weights were fixed (`142b6f5`); assist XP or an
  intermediate arena bout wait on future playtests.

## Large

- **Weapon actions: tune the favoured cases after a playtest.** Rebalanced 2026-10-16: out of its case an
  action is one strike; in it the strike lands twice over plus a small edge (RULES.md *Weapon actions*,
  `favoured` on each action, the premise held by `test_ai_actions`). Left: whether each case comes up
  often enough (Repel Strike's wall, Maiming Strike's helpless foe, Parry & Strike's two foes, whose margin is
  the slimmest), Long Thrust (Glaive, 2026-10-22: one strike past reach, no double, the narrowest by design),
  and the old Extreme Shot / Power Shot niches (Power Shot is now on the Longbow too).
- **Production chain between groups (after the magic arc, author 2026-10-15).** The first place where one
  group's output is another's input, the heart of the open-world vision. The Carpenter is open (2026-10-19).
  The Forge already smelts Iron Bar (2 Iron Ore + 1kg Coal). Next: wagon crafting, a crafting branch for
  the sim's `balanced` policy (smelt, then forge or sell) and tests. Gives Coal and the gems a use and
  closes `sources.py`'s `traded` goods one chain at a time.
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

- **Members with a will of their own: the drama engine (to evaluate, proposed 2026-10-22).** The market
  read: as a guild manager the game sells on the stories its people make, not on its numbers ("the game
  still lacks soul", *Occupations are bland*). Each member wants things and reacts to what already
  happens to them, built on the occupation and alignment every character already rolls:
  - **Occupation = what they want to do.** Group the 31 into about 6 wants (fight, labour, city, road,
    care, faith), plus one detail of each occupation's own: the Woodcutter is content at the Yard, the
    Mercenary resents labour and wants fights and pay, the Physician suffers a death left untreated.
    It gives the waiting starting items (Deck of Cards, Map, Compass) a reason to matter.
  - **Alignment = how they react.** Lawful/Chaotic to orders, the leader and crime; Good/Evil to
    cruelty and greed (an ally abandoned, captives killed, the loot split, a member left hungry).
  - **Opinion of each other and of the leader** (a small -3..+3 between pairs), moved by events that
    already exist: a death in the group, hunger, ten days at the Yard, the loot, a bad order.
  - **Short events that ask the player for a decision** ("Brakka wants a double share or leaves with
    their own"; "Tovi will not march with Grok"; "Mira mourns Hal and will not fight for three days"), each
    one written as a line of a guild chronicle the player can reread.
  - Extends what alignment already drives (`cohesion.py`'s walk-outs and loot, `recruit.py`, `dialogue.py`,
    `ai.py`'s temper) instead of a new system beside them.
  Open: the want list and the reactions per axis, which triggers ship first, how it stays readable
  (not a spreadsheet), and what the economy sim and `cohesion.py` must learn. The test: after an hour of
  play the player tells a story with a character's name in it.

- **Open design questions from the 2026-10-18 playtests** (no code yet).
  - **The world moving by itself** (a Wilds node turns into a lair if nobody clears it). The author's
    long-term vision for time pressure; waits on earlier subsystems. The members' half (an idle veteran
    asks for work or threatens to leave) is the drama engine above.
  - **Time pressures from the world itself.** Today's (Bankers' rent, the title defence, the Ogre's
    deadline) are all ones the player chooses. Lumber saturating the wood price enters with the production chain.
  - **Weather fog**, if it ever exists: how it looks apart from darkness. Questions for the author:
    (1) does weather live on the world map, on the board, or both? (2) does it change rules (sight, shots)
    or only the look? (3) before the playtest or after (proposed: after)?

- **Magic as the vertical progression.** The arc's work is in *Ready to do -> Medium*. The schools are
  rival factions but not mutually exclusive for a character; magic comes strictly before Archaeology.
  Open: tier 2+ spells and any reputation penalty for rivalry.

- **Found-the-guild charter** (`draft_screen.py`, `vocation_screen.py`). The vocation is built; left:
  - **Measure the Wilds perk.** `scripts/vocation_report.py` does not price it. Run `balanced` under
    `--vocation wilds` with the group on *Cautious* against *Normal*, past the milestone (the hunts),
    and price the ambushes avoided. Questions for the author: (1) is the sim's measure enough, or should it
    wait for the author's own Wilds playtest? (2) if it comes out weak, raise the number or swap the perk?
  - **Price the Scholars' perk** (`vocations.info_bonus`: +2 on the opening read and on Assess). Its value
    is how much sooner a guild reads a foe, so it needs a fight-level measure, not a copper-a-day one.
  - **Oath (deferred, not scheduled):** what binds the members together and how a stranger would tell
    someone belongs to the guild (a creed, a mark, a code). Cannot be broken, can be changed. Mechanics in
    **cohesion** (`cohesion.py`) and a **combat/world rule** (a lock for a bonus); not economy or
    reputation. Open: the list, the effects, whether NPCs react to it, the cost of changing one.
    Questions for the author: (1) is it a code of conduct ("we never leave a wounded one behind") or a mark
    of identity (a creed, a sign)? (2) since it cannot be broken, what does changing it cost, and how often?
    (3) does a recruit swear it on joining, or does it bind only the founders? (4) do NPCs and factions
    react to it (a sign seen on the road, a deed that honours it)?
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