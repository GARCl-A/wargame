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

---

# Web front-end (decided 2026-10-23)

The presentation moves from pygame to HTML/CSS/Canvas, and the Python core stays. The battle
spike is built (`python -m gartok.web`), and the author's verdict is go. The decisions so far
and the steps are in [web_frontend.md](web_frontend.md) ("Next steps"): fluidity, speed and
zoom, the battle's parity with pygame and the shared base (the shell every screen runs in)
and the art as far as Gemini got are done; next are colour and light, the map, the hubs and
the swap.

- **CTF stalemate, AI against AI** (small, AI): the Ribbit Brothers' capture the flag with
  `combat_lab.build("boss", 2, 6, seed=7)` and the player's flag at the first legal cell
  never ends (1,400 rounds): two survivors, one sitting on its own flag, and nobody goes
  for the other flag. Found by `tests/test_web.py`, which plays every lab fight to its end.

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

- **Remove occupations (decided 2026-10-23).** The first step of *Needs more information -> Loyalty,
  the oath and who the members are*: an occupation is only a preset of the starting weapon and item
  (`unit.py`), so the starting kit is rolled at random and nothing is written on the character. Touches
  `data.OCCUPATIONS`, `Unit` (roll, save, `unit_edit`), `artwork.OCCUPATION_ICON` and `role_for` (the
  member's icon needs another source: the race's, or the weapon's), every label that prints
  "Race Occupation" (tavern, guild, squad, medic, initiation, crafting, watch, `dialogue.py`, the web
  board), `aftermath.Memorial` and the memorial screen, `recorder.py`, `npc_lib` / `npcs/*.json`,
  `outfit.py` (level 0 keeps the occupation's kit), `reference.py` / REFERENCE.md, the sims' rankings
  (`economy_guild.py`, `balance_sim.py`, `unit_compare.py`) and their tests. Saves of the old shape stop
  loading unless the key gets a default. The occupation-unique items lose their reason to exist: drop
  them from the start, they come back if a system ever needs them. Check the economy sim afterwards:
  a starting Axe or Pickaxe was a work tool.

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
- **Occupations are bland:** answered 2026-10-23, they go (*Ready to do -> Remove occupations*) and an
  aspiration takes their place (*Needs more information -> Loyalty, the oath and who the members are*).
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

- **Art to generate for the web board and UI** (step 4 of [web_frontend.md](web_frontend.md);
  files go in `gartok/web/client/img/`). Each is one seamless 1024 texture in the sepia
  engraving of the reference portraits, seen from above, mid value, with no 2x2 copies of
  its motif inside (Gemini's habit: the 2026-10-23 batch was four copies of a 512 block).
  - [x] Cave rock floor — `rock.jpg`
  - [x] Grass floor — `grass.jpg`
  - [x] Stone floor — `flagstones.jpg`
  - [x] Arena sand — `sand.jpg`
  - [x] Trees from above — `tree_1..3.png` (cut out of their parchment)
  - [x] UI materials — `paper.png`, `leather.png`, `brass_button.png` /
    `brass_button_pressed.png`, `seal.png` (End Turn), `portrait_frame.png`
  - [ ] Boulders from above — one of three, `boulder.png` (the other came inside a drawn
    circle)
  - [ ] Road earth (twice wrong: straight ruts like grid lines, then a copy of `rock.jpg`;
    attach no floor texture as a reference, Gemini copies it)
  - [ ] Town cobbles (twice wrong: too dark and contrasty, then a copy of `rock.jpg`)
  - [ ] Masonry wall from above (twice wrong: a wall seen from the front, then a light
    floor of blocks that does not tile top to bottom)
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

- **Loyalty, the oath and who the members are (design talk 2026-10-23, no code).** Replaces the
  2026-10-22 "drama engine" and the oath of the old *Found-the-guild charter* entry. Its first concrete
  step is *Ready to do -> Remove occupations*.

  **The problem.** "No soul, it is all one big calculator": a character is a statblock plus an
  alignment that only serves recruitment and shops; nobody wants anything. Several systems were built
  each for a piece of the same need (vocation: "the guild must have something"; alignment: "alike people
  like each other"; the oath: "why the member stays"; leadership and cohesion: a limit on growth) and
  none of them talks to the others. The author's worry: piling up subsystems of friction ("making a
  duck"). The aim is fewer concepts covering those roles, not more content. The test: after an hour
  of play the player tells a story with a character's name in it.

  **Decided.**
  - **The player is the guild**, an entity outside the groups; that is why it commands several groups
    at once. No avatar: an avatar dies to a wolf in a game built on a disposable early squad. Members
    are **partners, not employees** (no wages, no treasury: the guild has to be worth it to them).
    The guild leader and the group leaders are managerial roles, not a hierarchy.
  - **A member is a statblock + named traits + an aspiration.**
    - **Occupations go** (a classless game; an occupation is only a preset of the random item roll).
    - **The aspiration** is what the member wants to become: a mage, famous, rich (their own coins), to
      see the world, a quiet life, to serve faction X. The main loyalty input, and it ties loyalty to
      progression: a talent or an initiation spent on them is spent toward what they want. A fulfilled
      aspiration is a story beat (a new one, or they retire a legend).
    - **Alignment becomes named traits.** The two axes stay underneath, shown as words (proposed:
      Steadfast / Fickle on the law axis, Merciful / Ruthless on the moral one). What alignment does
      today, in the author's words: keeping one's word, holding the formation (law); not killing, not
      stealing (moral). The traits carry both halves: how the member **behaves** when the player is not
      in control (`ai.py`'s temper, what a deserter takes, `dialogue.py`) and what they **value**
      (loyalty inputs: a Merciful one suffers a captive left to die). Further personality traits, if
      ever, are more inputs of the same bar.
  - **Loyalty: one bar per member, shown as a number** (the author likes a transparent game). Inputs:
    doing what they want, their relations with the other members, killing when they did not want to,
    progressing when they wanted to, the oath kept or broken. At 0% they announce they are leaving
    (reuse `cohesion.py`'s 7-day notice, the window where the player can still react).
    - **It accelerates**: the more loyal, the more they tolerate (losses are dampened); the less loyal,
      the faster it falls.
    - **Founders start at ~70%**: they founded the guild. Recruits start mid-bar (~50%), whatever the
      pitch; one who has little in common with the guild simply falls fast, with no special rule.
    - **A group past its leader's capacity costs the group leader loyalty**, in place of `cohesion.py`
      rolling against the weakest member's Mental Defense (absorbs the leadership open problem).
  - **Relations between members are in**, and they are also a reason to run more than one group
    (keeping two who cannot stand each other apart). How the player manages them is open.
  - **Recruiting is one person convincing another**, never the guild recruiting. The recruiter pitches
    who the guild is and its oath ("this is us, this is the oath, you in?"); CHA still matters, it covers
    the gap between what the guild offers and what the candidate wants ("not exactly what you want, but
    close: try it?"). The recruiter's traits against the candidate's can stay (alike people get along);
    the guild-vs-candidate alignment distance goes.
  - **The tavern is the world.** Who drinks there is there on their own; the player has no say in who
    shows up. (Rejected: a "races the guild welcomes" list steering the tavern or the draft. It locks the
    player out of the Grippli they meet later and fights world-first.)
  - **The draft stays, as the founding**, not a recruitment: nobody convinced anybody. Choosing a
    starting crew among random strangers is common in the genre and liked (RimWorld's colonists,
    Wildermyth); attachment comes from what happens to a character, not from picking them (XCOM).
    Today's draft is a numbers pick; once candidates show traits and an aspiration it becomes a choice
    between people.
  - **The oath** (pf2e's edicts and anathemas):
    - **Composed by the player, choice by choice**, along axes with trade-offs (e.g. killing: everyone
      must die / free / nobody dies). The guild is as complex as the player wants it to be.
    - **Every clause points at an event the game already records**, or it is abstract. "Get rich" alone
      is no trade-off (every player wants it); it works as an edict loyalty reads. Candidates from the
      talk: "nobody is left behind" (a downed ally or body abandoned), "no blood for nothing" (killing
      one who surrendered, a captive left to die), "we come home alive" (withdrawing is never shameful),
      "we keep the City's law" (a crime, `justice.py`).
    - **Binds every member**, founders and recruits alike.
    - **Can never be changed**: the guild is the player, and the oath is the commitment the player makes
      by starting the run.
    - **Factions and NPCs do not react to the oath**, only to what the guild does.
  - **Vocation stays for now, on probation.** It is cut, merged or diluted into another system as soon
    as one does its job better. Today it is six races + one perk; that coupling makes a fan of one race
    pick a perk they do not want, and the author only ever plays Caravan or Delvers: those two touch
    something done every day (travel, gathering), the other four rare events (the cohesion roll, a
    Cautious ambush, the opening read, every 10th day's food). If it is reworked, each perk acts on a
    daily loop.

  **Rules of thumb for every input and output.** An input is an event the game already has (a death,
  hunger, days at the Yard, the loot, a withdrawal, a crime); an output is a mechanism that already
  exists (leaving, recruiting, maybe combat morale); nothing needs a new screen to manage, it shows as a
  line in the log or a one-off request ("Brakka wants a double share or leaves with their own"); it
  produces a decision (profit against a person, a person against a person), not only an upkeep like
  hunger. And not everything feeds loyalty: if perk, oath, aspiration and trait only move the same bar,
  loyalty becomes the new calculator.

  **Proposed, not yet answered.**
  - **Origins** (a starting situation in place of a perk: "a wagon and a debt to the Bankers",
    "survivors of a Ruins expedition") are the form the genre likes best for a founding; new content, so
    noted, not now. A candidate for what the vocation could become.

  **Open (closes with play or numbers).**
  - How far each input moves the bar, the acceleration curve, what high loyalty buys besides tolerance.
  - The aspiration list and how each one is read off existing state.
  - The oath's axes and the steps on each.
  - How the player sees and manages relations between members.
  - What the economy sim (`economy_guild.py`) and `cohesion.py` must learn.
  - Presentation, later: a founding charter that writes itself line by line, signed with the banner and
    the oath, the first entry of the guild's chronicle.

- **Open design questions from the 2026-10-18 playtests** (no code yet).
  - **The world moving by itself** (a Wilds node turns into a lair if nobody clears it). The author's
    long-term vision for time pressure; waits on earlier subsystems. The members' half (an idle veteran
    asks for work or threatens to leave) is the loyalty entry above.
  - **Time pressures from the world itself.** Today's (Bankers' rent, the title defence, the Ogre's
    deadline) are all ones the player chooses. Lumber saturating the wood price enters with the production chain.
  - **Weather fog**, if it ever exists: how it looks apart from darkness. Questions for the author:
    (1) does weather live on the world map, on the board, or both? (2) does it change rules (sight, shots)
    or only the look? (3) before the playtest or after (proposed: after)?

- **Magic as the vertical progression.** The arc's work is in *Ready to do -> Medium*. The schools are
  rival factions but not mutually exclusive for a character; magic comes strictly before Archaeology.
  Open: tier 2+ spells and any reputation penalty for rivalry.

- **Better food: dishes with buffs (after the magic arc).** Food only quells hunger and the Potato does it
  cheapest. The preservation recipes are built (Jerky, Roast Meat, Fruit Compote; no buffs, by design).
  Decided: cooking is an ordinary craft; a premium dish gives a 24 h buff that moves one number (HP, an
  attribute, advantage on a named kind of action...), and only the most recent meal's buff is active.
  Open: the dishes and their buffs, and the cost to the economy sim (`cheapest_food_price` stops being
  the one price of a meal). Marsh's slower rot is priced low until this lands.
