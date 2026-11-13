# Backlog — everything still open

The one place for open work. A task here is a few lines; when it needs more, it **points to its plan** in
`docs/plans/` ([storefront_polish.md](storefront_polish.md), [go_to_market.md](go_to_market.md), [loyalty.md](loyalty.md), [campaign_ai_roadmap.md](campaign_ai_roadmap.md), [onboarding.md](onboarding.md)) or to the doc
that owns the subject: the test suite [../../tests/README.md](../../tests/README.md), the economy sim
[../economy_sim.md](../economy_sim.md), the web client [../web_ui/web_client.md](../web_ui/web_client.md).
What is already built is in the code, its tests and the git log.

Sizes are estimates. When an item is done, delete it here and, if it changed a design premise, record it in
`AGENTS.md` or the doc that owns it.

Parts, in this order:

- **Before the friends' playtest** — what is left before the build goes out.
- **Ready to do** — defined enough to start: *Small*, then *Medium*, in the order to pick them up.
- **Large and later** — after the playtest or after another system: *Large*, *Art*, *Epic*.
- **Deprioritised**, **Notes to remember**, **To discuss and reflect on** — wanted one day, or premises to
  think over; not tasks.
- **Playtest notes** — raw notes by date, sized as they are picked up.
- **Needs more information** — a design question, a repro or another system has to land before the task
  can be sized.

---

# Before the friends' playtest (agreed 2026-10-20)

Goal: a stable build for the author's playtest and one with friends. Left:

- **Tutorials.** The author reads every card in play and flags what still rings false.
- **Onboarding (proposal 2026-11-13, awaiting the author's calls).** Plan: [onboarding.md](onboarding.md). A new
  player closes 7 cards (877 words) before the first order, and the recorded runs spend 79% of their first two
  weeks on wage shifts. The plan: a quiet map where the keepers' errands give the direction, a first season of five played chapters, notes at
  the decision in place of cards. Its phase 1 (copy and two triggers) needs no new system.
- **Translation to pt-br.** The author plays in `pt-br` and flags tone, missing accents, sort order, number and money formats
  ([../glossary_pt_br.md](../glossary_pt_br.md)).
- **Holy Symbol.** The author plays the Farmer's quest through (the offer from day 50, *Ask around*, the rite fight, the Demon's lair); the polish is in *Needs more information*.
- The *Small* items below, in order.

After the playtest (it answers them, or they are content past it): weapon actions tuning, *Tune the
specialised shops*, Magic Arc tuning, the production chain, cooking with meal buffs, the campaign AI,
Prisoners.

---

# Ready to do

Order inside a size is the order to pick them up: first what blocks the friends' playtest, then bugs, then
the rest.

## Small

- **Translation leftovers.** The combat log keeps a unit's name as the string of the moment (a `Ref` for authored NPCs would fix it);
  `routine.paused` reasons, the memorial `cause`, a dialogue's `Result.text` and the guard notices are stored already translated; an ambush
  title is chosen when the talk opens; text built from ids with `.title()` / `.capitalize()` (school, stage, node ids) and the stat labels of
  `magic.py`, `intel.py`, `unit_derive.py`, `group.py` still need a review. `REFERENCE.pt-br.md` does not exist yet: turn the literals of
  `reference.py` into keys so `python -m gartok.reference` can write it. Run `scripts/i18n_leaks.py` when a screen is added.

- **A crowded start zone puts a big body off the board or on top of another (bug, found 2026-11-12).**
  `Scenario._place` (`scenario.py`) tries the side's edge cells in random order and, when no anchor fits
  the footprint, falls back to `candidates[0]` without checking bounds or overlap. The body then stands
  partly outside the board, and the first code that asks for the neighbours of one of its cells raises
  `KeyError` in `Board.neighbors`: seen in `ai/movement._step_over_terrain` -> `actions/movement.Swim._at_water`
  (`KeyError: (16, 7)` on a 16x12 board), which kills the AI's turn in a real fight and the thread of the
  clean-stomp estimate (`autowin`). The zone is 3 columns by the board's rows, so it happens when the
  bodies only fit if packed tight. Measured over 200 seeded deployments each: 5 Centaurs (Large, 2x2) land
  wrong in 23, 6 Centaurs in 171, 3 Dragons (Huge, 3x3) in 1, 4 Dragons in 164; 4 Centaurs or 2 Dragons never.
  The Dragon is only placed by hand today (`data.AUTHORED_BEASTS`), but a Wilds pack rolls up to 6 bodies
  and a band can hold Large ones (Centaur, Horse, Ox, Donkey). Reproduce the bad deployment:
  `random.seed(0)`, `Battle([standard_unit() for _ in range(4)], [Unit("enemy", race=data.race_by_name("Dragon")) for _ in range(4)], scenario=Scenario())`
  leaves one Dragon anchored at `(15, 7)` with six cells past column 15 and three cells shared with
  another; the crash: the same two sides through `autowin.simulate_matchup(squad, pack, scenario=Scenario, max_iterations=2, max_time=30)`
  raises at seed 0 (23 of seeds 0..39 with 4 Dragons, 2 of 40 with 3). Do: place the biggest bodies first
  and pack them, widen the zone inward when the edge is full, and never leave a body out of bounds or
  overlapping (a test over seeds for 6 Large and 4 Huge bodies).

- **Ambush on the way in, at every dangerous node (author, note outside playtests).** The Wilds, the
  Frontier Outpost and the Battlefield should roll an ambush per leg like the Old Road
  (`forced.py` rolls `world.ROAD_AMBUSH_CHANCE` once per arrival at an `unsafe` node), and the map should
  mark a node that has one ("ambush on the way"). Only the Old Road is `unsafe` today; the chance per node is
  tuned together with *How lethal the Wilds should be* (*Ready to do -> Medium -> Measure the economy against the decided lines*).

- **One colour per name, then the map screen's pass on every screen (author, notes outside playtests).**
  Two steps, in this order. (1) *Tokens:* the CSS declares about 70 custom properties (23 in `shell.css`)
  against about 1600 literal colours in 17 files, so nobody can tell which colours are in use and a new
  one is a random hash. The goal (author 2026-11-04) is to cut the number of colours, not only to name
  them: the palette should be small enough that a retheme is a change of a few hashes. Go slowly: first
  catalogue every colour in use (about 360 distinct hex values today, besides `rgba()` and named ones) with
  where and what for, and find out why there are so many; only then merge the near-equal ones, name the
  survivors in `:root` (`shell.css`) and replace the literals; record the names in `docs/web_ui/web_client.md`.
  (2) *The map's pass:* the author enlarged and recoloured the ledger's `.lbl` on the map (reputation, purse,
  members), merged the *party* panel into *Bands* and cut strings (2026-11-02/03). Split each change into
  what *should* spread, to keep text, fonts and colours one pattern (`.lbl` is redefined in `guild`, `hub`,
  `draft` and `arena` with its own hex), and what *may* spread, a holistic wish to show less at all times,
  move detail to hovers and use the space better. Judge each screen against the map's and list the
  changes per screen before touching one.

- **Scroll of Invisibility (Magic Arc).** The item exists (`items.py`); missing is the Library quest, unlocked at max Library reputation with a caster
  initiated in magic (direction 2026-10-19).

- **UI sound: the missing cues.** `gartok/sound.py` has 8 cues (the upkeep meal plays `eat`, one of 7 crunches,
  off `Guild.heard` through the map's state), so confirm, error, equip and end of turn have no sound. Wanted
  first (author 2026-11-10): a cue for Demoralize, a single voice shouting (not a groan: the author
  rejected *Battlecry* by spookymodem, CC-BY, and the CC0 *Orc voice*; no single-voice CC0 war cry was found, the
  Kenney *Voiceover Pack: Fighter* taunts are speech, CC0); the rest the author notes in the next playtest. The
  author picks the files (CC0, or CC-BY if the credits screen names them: `LICENSE.txt` beside them); then add them to `CUES` / `LEVEL`, write down
  which act plays which cue (one table in `docs/web_ui/web_client.md`), and wire them: equip in the sheet,
  confirm on the dialogs, the error cue in place of `miss` in `api()`. End of turn is a battle cue: it comes
  from the server (`st.sounds` off the combat log, `battle.py`), with a test in `tests/test_battle_fx.py`.

- **Is a STR/CON-heavy draft objectively best? (author 2026-11-01).** The author drafts a Charisma leader
  plus the strongest, toughest bodies for the rest. The race study measures it (`scripts/attribute_rank.py`, on
  the `val4` run: 215 thousand squad results, race and build held fixed): +1 modifier on every unit is worth about
  +8.6 win points for CON, +8.0 STR, +7.2 DEX, and +1 to +2 for WIS, CHA and INT. So it is a fact, not bias,
  for the fighters; the mental attributes are measured over all builds, casters not apart. Left: decide whether the
  starting squad and the stat draft need a rebalance (*Starting squad is weak* in the playtest notes), and measure
  the casters' builds alone.

- **Weapon icons: give each its own (author 2026-11-08).** Broadsword, sword and rapier share the `broadsword`
  glyph; axe and hatchet share `battle-axe` (`item_icon.GLYPHS` / `HEAD_GLYPHS`). Source a distinct glyph for each: other `assets/icons/`
  folders, otherwise new game-icons.net SVGs (same licence).

- **Less of a web page: the cursor and the browser's menu (visual audit 2026-11-12).** The game has no cursor
  of its own, and the browser's context menu is blocked only on the map sheet and the battle sheet
  (`screens/map/sheet.js`, `screens/battle/battle.js`), so a right click anywhere else opens it. Do: one
  cursor for the whole client (and its pointing and dragging states) in `shell.css`, from the icon set
  already licensed, and the context menu blocked in the shell for every screen (the shop's own item menu
  stays). The native window is its own item (*Deprioritised*, and gate 3 of [go_to_market.md](go_to_market.md)).

## Medium

- **Objects on the table, not boxes on a page (visual audit 2026-11-12).** The screens that look most like
  a game are the ones made of physical things that overlap and sit a little crooked (the title: the map
  sheet, the guild card, the coins, the seal; the charter; the Victory stamp). The ones that look like a web
  dashboard are grids of 1px-bordered rectangles inside rectangles with small spaced capitals and form
  controls: the shop (about 40 boxes) and the routines editor (dropdowns, a toggle, chips, steppers) first,
  then the bands tab and the reputations. Do, one screen at a time, shop first: fewer frames (a rule or the
  material itself separates things, not a box per row), each panel a thing with a shadow that may overlap
  its neighbour and tilt a degree or two, a hand-written note in the margin where a hint sits today, and
  the empty paper filled by the composition instead of stretched panels. A mockup of the shop comes first
  (`docs/web_ui/web_client.md`, *The mockups*); the rules that come out of it go in *Art direction*. It
  comes after *One colour per name* (*Small*), which touches the same CSS.

- **Storefront polish (photo review 2026-11-12).** Plan: [storefront_polish.md](storefront_polish.md). What the
  real screenshots in [../photos/12112026/](../photos/12112026/) show: the unit panel overflowing at low hit
  points, the cut battle title, band pawns over place names on the map (three *Small*), the fog of war in a room
  full of pillars (the author picks the look).

- **Race study in four tests (`docs/race_study.md`).** The waves and `mixed_study_report.py` exist; missing: a full run
  (sizes in the doc), the mixed error (a build twice in one squad is credited twice per unit, which is the intended score, but
  its interval reads too narrow: cluster the error by squad), and deciding whether this report replaces
  `build_study_report.py`'s tables. Combat first, the economy axis after.

- **Auto flee button (playtest 2026-11-02).** One button that moves every unit of the side toward the exit
  while it can, instead of ordering each one. Read the flee rules first (what blocks a flee, who is held)
  and reuse the AI's flee path. End-to-end: web button in `screens/battle/`, `ai/`, tests, tutorial mention.

- **Intimidation build rework & mathematical tuning (author/Yohan alignment).** Overhaul the mathematical progression, DCs,
  and action economy for the Intimidation combat build (Demoralize, Provoke, and associated Charisma/Wisdom talents) to raise
  its win rate and tactical reliability in battle.

- **Workplace skills: INT/WIS in automated production loops (author/Yohan alignment).** Connect Intelligence and Wisdom
  workplace talents into automated routines (e.g., automated mushroom foraging + medicinal herbalism loops that craft and
  maintain target stocks of healing potions).

- **Measure the economy against the decided lines (author 2026-11-11).** In this order, the first is what
  the other two are measured with:
  1. *The reference scenario past the start.* The sim tests the Wilds, the Games and the Claim from a
     guild that starts at level 3 with $250 (`economy_guild.py --level 3 --capital 250`), a guess. Decided
     (author 2026-11-11): the scenario is the *How lethal the Wilds should be* squad below (3 units, combat 1, work 2, the weapon and armour
     above, its capital what that kit costs). `--level` is one number today, so the sim needs the combat and
     work tracks apart (and `--size 3`) (`scripts/economy_guild.py`).
  2. *How lethal the Wilds should be.* Decided (author 2026-11-11): 3 characters at combat 1 and work 2,
     each with a weapon of up to 50 coins and a Studded Leather, win 50% of the Wilds ambushes. Measure it
     with the headless fights and tune the Wilds packs to it; the Old Road's ambush (20% a pass,
     `world.ROAD_AMBUSH_CHANCE`) is re-measured with it (a group too strong for a pack is no longer
     ambushed by it, author 2026-11-01).
  3. *How much a crafter may earn.* Decided (author 2026-11-11): a crafter (2 craft talents) profits at least
     3x what a lumberjack earns per hour at the Yard, over a 16 h day. Craft profit = sale price - (reagents +
     food). Left: measure each crafting loop against that line with `scripts/economy_report.py` and the restock
     sweep, then tune prices and shelves. Ties to *Tune the specialised shops*.

- **A test that opens every screen in the browser.** The client's scripts are checked only as text: a
  typo in a screen is found by whoever opens it. Open each screen in headless Edge on a copy of a real
  save (the screenshot recipe in `docs/web_ui/web_client.md`) and fail on a script error. *Fault capture*
  already leaves every script error in the save folder's log (`errors.jsonl`).

---

# Large and later

## Large

- **Screens stop reloading the page.** Every screen change is a `location.reload()`, so the page, its scripts and
  the decoded sounds are rebuilt each time (measured 2026-11-12, day-4 guild, headless Edge at 1920x1080: the map
  opens in 0.24 s with the files cached and 1.8 s on a CPU slowed 4 times, of which the browser rebuilding the
  page, mostly one tiny SVG document per icon, is most). Only a screen that swaps in place fixes that; it touches
  every screen. Measure first on a modest laptop with a late save, and the hub and battle screens too.

- **Loyalty & Aspirations system (author/Yohan alignment).** Plan: [loyalty.md](loyalty.md). Replaces traditional
  alignment with organic motivation mechanics. Characters receive individual aspirations organically tied to their
  attributes, background, and personal vocation:
  - *Exploration* ("See the world"): requires discovering and visiting new map nodes.
  - *Economy* ("Get rich"): requires continuous growth of personal coin.
  - *Labor* ("Master miner / Master craftsman"): requires hitting extraction or crafting quotas.
  - *Dissatisfaction triggers:* unmet aspirations over prolonged periods cause members to voice complaints in dialogue/notices
    and suffer progressive, accelerating loyalty loss.
  - *Guild collective model:* the guild functions as a collective / partnership rather than top-down subordination, demanding
    constant conciliation between member ambitions and organizational priorities.

- **Food system & Morale rework: de-combatize and diet monotony (author/Yohan alignment).** De-combatize food utility away
  from immediate mid-fight buffs toward resting recovery, inspiration, travel sustain, and guild morale management. A
  monotonous diet (such as surviving exclusively on potatoes daily) steadily erodes party morale, humor, and member loyalty,
  requiring food variety and culinary planning. (Supersedes the old combat-buff cooking concept).
  Decided 2026-11-10: each unit keeps the foods it ate in the last 7 days, an ordered list of 7 entries (a saved
  `Unit` field with a neutral default in `SAVE_DEFAULTS`). Decided (author 2026-11-11): the diet variation is a value from 1 to 7, the number of distinct
  foods eaten in those 7 days. How the value maps to morale is decided with *Loyalty*, after it is designed (author 2026-11-11). Rotten Food (decided 2026-11-11): it is thrown away, eaten by a Gnoll, and
  an emergency ration so a badly planned group does not starve (RULES.md, *Rotten Food is not a ration*);
  later it is compost when the guild can farm.

- **AI Leveling & Large Guild Build Planner (author/Yohan alignment).**
  (1) AI leveling logic for rival/opponent guilds so opposing factions build cohesive, optimized characters.
  (2) Player-facing "Build Planner" to automate level-ups, talent picks, and stat allocations across large rosters (e.g., 30+
  members) without repetitive manual clicks.

- **Terrain alteration spells (author/Yohan alignment).** Field manipulation spells for casters (e.g., creating stone/ice walls,
  digging pits/trenches, or dropping temporary physical obstacles on the tactical grid) to control choke points and enemy movement.

- **Game Modes & Character Creation Flow (author/Yohan alignment).**
  (1) *Game Modes:* Evaluate splitting into two distinct experiences: structured Campaign mode (handcrafted story milestones,
  authored progression) vs. procedural Sandbox mode (procedurally generated map, nodes, and encounters).
  (2) *Character Creation:* Retain the Draft system for the standard/campaign mode for emergent diversity and replayability; provide
  a direct character builder / commission token system for players who prefer exact custom starting parties (RimWorld / XCOM style).

- **A shop for Tiny gear.** Today the town shops stock Tiny, Small and Medium at the same counts
  (`economy.TOWN_SIZES`). A dedicated Tiny-gear shop takes Tiny off the town shelves (`RULES.md`, Item sizes).
- **Sized recipes.** Crafting yields Medium gear only; a Small or Large recipe (or a size choice on the
  existing one) is missing.

- **Routine unlocks (author 2026-11-04). A POSSIBLE IDEA, not a design decision.** It is decided only after
  the playtest with every routine open from the start. Today every block and every place is open to a routine
  (`routine_book.py`, the Book of routines). The idea: blocks are mission
  rewards (every action `work`, `gather`, `craft`, `rest`, `travel`, `trade`, `hand_over`, `take` and every
  condition, items, coins, HP%..., is a right the player earns); a node (the Lumber Yard...) only accepts a
  routine after its mission; one gate at a time, as an arc of missions. The routines' theme is its own, apart
  from the economic gather licence (`Guild.has_licence`), which they never read. The seats' constants
  (`routine_book.BASE_SLOTS`, `FAME_PER_SLOT`) exist; their values are tuned with it.
- **Campaign AI reading routines (author 2026-11-04).** It keeps issuing loose orders; later it reads the
  same block vocabulary of `routines.py` so the planner ([campaign_ai_roadmap.md](campaign_ai_roadmap.md))
  and the spec do not grow apart. Not part of the programmable orders arc.
- **Weapon actions: tune the favoured cases after a playtest.** Out of its case an
  action is one strike; in it the strike lands twice over plus a small edge (RULES.md *Weapon actions*,
  `favoured` on each action, the premise held by `test_ai_actions`). Left: whether each case comes up
  often enough (Repel Strike's wall, Maiming Strike's helpless foe, Parry & Strike's two foes, whose margin is
  the slimmest), Long Thrust (Glaive, 2026-10-22: one strike past reach, no double, the narrowest by design),
  and the old Extreme Shot / Power Shot niches (Power Shot is now on the Longbow too).
- **Magic Arc, later.** (1) *Blood's fourth mission* (the robbed dragon strikes back): the dragon attacks
  node by node seeking its eggs, closest first, with consequences if nodes are destroyed; after the magic
  arc's core content (author 2026-10-19). (2) *Tuning after playtests:* the numbers for the Battlefield,
  the Snake Dragon, the Ogre Wildfire, the Necromancer at the Front and the Dragon's Clutch, once campaign
  runs reach them.
- **The sim's long game.** Past day 30 (the Pit, a recruit, the Wilds hunt as the income) 18 of 40 sim guilds
  die by day 60, all hunting. Left: decide whether `SKILL = 0.5` (the player's share of the AI's losses)
  stays, since the author's 87 hunts measure 0.84 (`combat_pairs.py`); see [../economy_sim.md](../economy_sim.md).
- **Production chain between groups (after the magic arc, author 2026-10-15).** The first place where one
  group's output is another's input, the heart of the open-world vision. The Carpenter is open (2026-10-19).
  The Forge already smelts Iron Bar (2 Iron Ore + 1kg Coal). Next: wagon crafting, a crafting branch for
  the sim's `balanced` policy (smelt, then forge or sell) and tests. Gives Coal and the gems a use and
  closes `sources.py`'s `traded` goods one chain at a time.
  **Market supply and demand / lumber saturation:** endless day labour at the Yard should flood wood prices.
  Intent (author 2026-10-31): a living economy, prices answer to what players do (a guild that cuts wood 24
  h a day floods the market and the work stops paying); the carpenter buys wood from the lumberjack and
  iron from the smith, the smith buys ore and coal from the mine. How the player enters that chain against
  the shops is open. After the core is solid.
- **Market stall (tester's idea, playtest 2026-10-31).** A licence to open a stall in any market and sell
  your own goods at a better price, so every area allows some interaction. Not sized; it belongs with the
  production chain above and needs it first.
- **Item properties: base material sources (after the production chain).**
  (1) widen base materials beyond `RAW_TYPES` to include gear recipes as the Smith's chain lands; (2) seven
  declared `traded` goods (Potato, Sugar, Salt, 1L Beer, Vial, Paper, Ink) awaiting their production chains.
- **Prisoners.** Decided 2026-10-19: (1) sell to City Prison via interactive tab/dialogue for bounty based on
  captive level/crime; (2) recruit contest; (3) forced manual labor in lumber/mine: captive eats group food (or
  starves), escape/revolt check fires daily after captive recovers to full HP. Left: UI tabs, escape check,
  enemy capturing player units, and battlefield rescue.
- **Campaign AI: a policy planner, then a genetic algorithm** — plan: [campaign_ai_roadmap.md](campaign_ai_roadmap.md).
  The offers list is built (`scripts/economy_offers.py`); left: a planner that enumerates and prices
  offers dynamically in copper and days (the plan's phase 2), then the evolutionary loop and its telemetry.
- **Tune the specialised shops.** Confirm distances and alignments of shop keepers; verify world-tied
  restocking (the Carpenter is verified). The shelf numbers (target and refill per shop and item) are a
  first estimate from the sim's restock sweep, and a shop's till and its refill belong to a shop function, not
  to `kind == "market"` (the Library's cash never refills, nor would the tavern's).

- **The native client, before the game is published.** Later, not for the playtest: an installer (the zip is
  enough for friends); auto-update; code signing (an unsigned `GARTOK.exe` triggers SmartScreen); Linux and macOS
  builds (`build_client.py` is win32-x64 only); the Steam build, with its overlay tested on the Chromium window
  ([go_to_market.md](go_to_market.md), gate 3). The window icon is under *Art*.

## Art (made by hand, not code)

- **A window icon for the native client.** No `.ico` exists, so `GARTOK.exe` shows Electron's default one; with
  the file, `scripts/build_client.py` takes it as one `--icon` argument to `electron-packager`.

Portraits are engraved medallions in `gartok/assets/portraits/<race>/N.png`; the rest is game-icons.net
SVG silhouettes. How the art is made (Gemini first, anchored on the four reference portraits; the
`/gen-portrait` LoRA is the weaker fallback) is in [../web_ui/web_client.md](../web_ui/web_client.md); an
agent asks for art instead of generating it. Order is the suggested priority.

- **Art to generate for the web board and UI** (the art direction in [../web_ui/web_client.md](../web_ui/web_client.md);
  files go in `gartok/web/client/img/`). Each is one seamless 1024 texture in the sepia
  engraving of the reference portraits, seen from above, mid value, with no 2x2 copies of
  its motif inside (Gemini's habit: the 2026-10-23 batch was four copies of a 512 block).
  **Prompts are not kept in the repo yet** (the Gemini prompts for the finished textures were not
  saved). From now on save each prompt that works (and the reference images attached) next to the
  texture, in `docs/art/<name>_options/`, and write the prompt that failed under its item.
  - [ ] Boulders from above — one of three, `boulder.png` (the other came inside a drawn
    circle)
  - [ ] Road earth (twice wrong: straight ruts like grid lines, then a copy of `rock.jpg`;
    attach no floor texture as a reference, Gemini copies it)
  - [ ] Town cobbles (twice wrong: too dark and contrasty, then a copy of `rock.jpg`)
  - [ ] Ancient Ruins floor (playtest 2026-10-30): the tile repeats and its edges do not meet, so the
    seams show in the first room. Same rules as the others (seamless, no 2x2 copies); check the
    edges by tiling it 3x3 before it goes in, and replace the file the Ruins floor reads in `ui/floors.py`.
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
  combat (today a neutral creature only stands still and blocks its cell). The creature abstraction should not make it harder.
- **Auto battler with priority programming** (Siralim Ultimate style). Its own arc and
  branch: UI, AI and tests.

---

# Deprioritised, notes and reflection

- **Port the Editor to the web (author 2026-10-30: wanted one day, not now).** The character creator, the map
  editor and the combat lab's menu stay pygame (the `editor/` package, `python -m editor`: `editor_app`, `editor_menu_screen`,
  `char_editor_screen`, `map_editor_screen`, `combat_lab_screen`, and `battle_screen` + `battle_draw` for the
  lab's fights). Until then they are only maintained, not extended; nothing in `gartok/` may import them. When picked up, each Editor screen becomes a web screen (a session, a client folder, the
  rules in a pygame-free module) and its pygame screen and tests are deleted; the lab's fights already run in
  the browser (`python -m gartok.web --fight <lab fight>`). Porting it deletes `editor/` and drops pygame from the repo.

- **The in-game wiki shows only what the guild already knows (author 2026-11-01, decided).** The wiki is
  the player's own notebook, not the game's encyclopedia: a player who opens it to reread how the sword's
  action works must not be spoiled on the next creature, recipe or talent. Today every chapter in
  `web/wiki_session.BUILD` prints the whole catalog from turn one (Beasts: Hit Die, size, speed, abilities
  and drop odds; Talents: every racial node of every race; Recipes: all of them). Gate each chapter on what
  the guild has met, owned or learned (`intel`, known recipes, the talents of the races in the guild), with
  a locked-entry stub or no entry at all. Cases given (author 2026-11-01): a shop's items appear once the
  guild has entered a shop that stocks them; a race appears when the guild hires one or finishes a 100%
  assess of it; a beast appears at a 100% assess. Decided 2026-11-04: entries are partial (the assess
  fills a beast in bit by bit). What exists to gate on: the guild's `Bestiary` (`intel.py`: races fought,
  abilities seen, the best read of each authored NPC) and each unit's `known_recipes`; nothing records an item
  seen, so an item's entry needs a new saved set (author 2026-11-12: breaking saves is not a concern). A recipe's entry shows only for a recipe someone knows; an
  item's entry does not depend on knowing its recipe. Cases still to decide: recipes (known, or seen crafted), talents
  (of the races in the guild), conditions (first suffered or inflicted), weapon traits and actions (when a
  unit owns or gets them), places and factions (visited, met), spells (known or a scroll owned), what
  comes with the guild on day one (the rules chapters). Then whether the wiki says that something is still
  hidden. The complete catalog is `REFERENCE.md`, a design doc for
  developers and agents, spoilers included; if it is ever published it becomes the game's general wiki,
  outside the game, and the in-game one stays the discovered subset.

- **Test suite: faster tiers (found 2026-10-28).** If `-n auto` is ever not enough: ~78 tests between 0.1 s
  and 1 s make up about half of the fast tier's serial time (look there first); and
  `test_economy_sim._rows` replays 50 battles per call with no sharing, so a module-level cache would cut
  the `balance` tier by ~10 s if it is run often.

## Notes to remember when the case comes up

- **Roster of characters, not an army of clones (author 2026-10-31).** Many action-bar entries and each
  unit a character in its own right, friction accepted. The trade-off, named: eight identical units are
  fast to play (move, hit, hit), eight complex ones mean hundreds of buttons a turn.

## To discuss and reflect on

Not tasks and not yet decisions: premises the author wants to think over before they harden.

- **Everything is open from the day the guild is founded (author 2026-10-31).** Nothing is unlocked by
  story; what gates a thing is money, exploring a place, a reputation, a talent or a race. The author
  knows this makes levelling feel flat (*Playtest notes -> 2026-10-31 -> Levelling is vertical only*).
  Question: keep it fully open and fix levelling elsewhere, or let something be earned in order?
- **Release (author 2026-10-31).** Strategy and order of work: [go_to_market.md](go_to_market.md) (2026-11-12), which revises the itch.io-first idea below. Itch.io first, as an indie demo (pay what you want), while the game
  grows; Steam when there are 20+ hours of play ($100 fee; the generative-AI content flag must be
  ticked). Mobile does not fit: the UI is heavy, though it is a web app. A Kickstarter to pay a real
  artist was suggested. State the AI use plainly on the store page: generative AI is only the character
  portraits and a few tree sprites; the rest is drawn by code (the axe icon is an SVG written in code).
- **How power progress should work (author 2026-11-01).** Headless fights (10 each, both sides on the AI)
  showed that recruiting beats getting strong: 2 L3 lose 9 of 10 to 6 L1 wolves, one L10 (63 HP) loses
  10 of 10 to 8 L2 wolves, 3 L4 lose 9 of 10 to 4 L3 wolves, while 8 L3 sweep 2 L0 wolves and 10 L20 sweep
  6 L1 soldiers. Headcount weighs more than level, and armour barely moved the 3-against-4 result.
  Question: is that the progression the game wants, or should levels and gear count for more than bodies?
  Measured again 2026-11-12 with the race study's builds (`scripts/race_study_builds.py`) raised to level 10, one
  fighter against level 2 wolves, 200 fights each, both sides on the AI, open field: against 8 wolves a Glaive
  build wins 8 to 10% (Human, Orc, Dwarf, Goliath), sword and shield 8.5%, Broadsword 6%, the Fortress 7%, a
  random level 10 body 4%; the Human Glaive wins 45% against 4 wolves, 15% against 6, 4% against 12. The built
  fighter is about twice the random one and still loses: headcount weighs more than level.
  This now blocks tuning: every new race and talent is balanced on a curve the author has not chosen (headcount
  against level, and a +1 in CON or STR worth about four times a +1 in WIS, CHA or INT).
- **Co-op / multiplayer on a shared map (author 2026-10-31).** Each band a player. A daydream; the
  tester does not see it fitting. No plan.

---

# Playtest notes

## 2026-11-02

- **Is the two-step charge worth it? (author 2026-11-02, doubt).** Having one charge with two different
  values feels more of a hindrance than interesting. Review the rule against the Aurochs fight (day 112) and
  decide: keep, merge into one value, or drop. Measure with `scripts/combat_pairs.py`.
- **The Snake Dragon dungeon was too easy (author 2026-11-02).** Compare the encounter's level with the squad's on entry in the headless set before changing it.

## 2026-11-01

- **Surrender and prisoners (author 2026-11-01, future).** Morale and the rout shipped; a fighter whose morale is
  spent could give up instead of running. Think what a surrender does and tie it to *Prisoners*.

## 2026-10-31

A friend's (Johann) first session (about 2 h, no tutorial from the author). The author's stated intent from the
same talk is spread over *To discuss and reflect on*, *Notes to remember*, *Needs more information* and the
items it touches. Raw feedback, not yet sized:

- **Theme: the rules sit where the player does not look.** The wiki, the menu and the tutorial text were
  not read; the player learned by doing, and paid for it (rations, the draft, Delay). A fix per case is
  small; the pattern is to show the rule where the decision is made (a pick, a price, a button).
- **Starting squad is weak.** STR 2 or 3 carries nothing, a bow is too dear, and the start weapon is
  a dagger or a piece of an axe ("at least one real weapon"). The author would take 18 STR, 18 CON and 0
  elsewhere at level 0. Decided (author 2026-11-12): the starting weapon stays as it is; a Dagger is not a
  bad weapon (good actions, and finesse makes a Dexterity character work) and the starting weapon is not the problem.
- **Food was learned wrong.** He bought what looked like 20 days of shelf life and it spoiled; beer
  first (cheap at 4 copper and durable), then Potato; a farm trip for it did not pay against Fruit at the
  grocery. Check the economy report: is beer the best buy per day? No
  hangover for a beer-only diet (author 2026-10-31: does not like it). Decided: the supply is a
  constraint on purpose, not an afterthought: a group of ten plus a cart eats eleven meals a day, a
  10-day territory defence needs ~110 meals and a tavern holds tens (about 15 beers, 10 meats, 30
  potatoes). Salted meat and beer are the end-game foods (30 and 20 days), Potato lasts 7, fruit 1;
  hunting pays through meat and hides sold, then potatoes bought.
- **Hunting is not cheaper than buying** (the first mechanic he tried); the author felt it was badly
  balanced but it is **not validated**: it needs an economic analysis first (author 2026-10-31).
  Re-run `scripts/economy_report.py` for the Wilds hunt (meat and hides sold, then food bought) against
  the cheapest meal, per hour and per risk of ambush, before any change.
- **No recipes to be found.** He found none: recipes are few (race, crafting talents). The design
  question is in *Needs more information -> Recipes learned by owning the item or a teacher*.
- **Combat will dull with time; the bar is only attack, defend, special.** Open: group actions, linking units,
  a way to make many units cheap to play (the sim's auto-play, *Auto battler*). Magic is the author's answer,
  but it comes late. More weapon-driven mechanics should relieve it too, and the tester suggested a way to
  link characters or make them act together.
- **Levelling is vertical only.** Nothing new to do at a higher level. The Charisma line (earns money,
  recruits) is the example he liked. Open design question for the talent trees: each level should open a
  thing to do, not only a bigger number. Not wanted (author 2026-10-31): only bigger numbers, or a pile of
  skills. Wanted: a new thing to do per level (a bard that can play at court or recruit). Magic is the
  main hope but it arrives late (reputation with the schools, unless the start is a Gnome or Kobold, the
  races that begin as casters).
- **Switching between groups.** The author asked if it is pleasant; the answer was not clear in the record.
  Ask again. The friend's view: up to 8 units is fine, more groups slow it unless there is automation.
- **Automation** (secondary groups on routines) is the author's answer to the macro load and was well received.

- **The Reputations tasks only half guide a start.** Found them "almost intuitive", not a clear "how
  to begin". Check whether the first deeds read as a path.

## Older raw notes (2026-10-12, 2026-10-21)

To be sized as they are picked up. Guiding rule (2026-10-12): **fewest possible buttons on the map**: a node
has one "Enter" button and its functions are tabs inside.

- **Too few icons for the guild banner (10-21).**
- **World and soul (10-21):** the world needs story depth before the Archaeology arc; the game still lacks
  "soul" (see *Loyalty* in *Needs more information*).
- **Leveling templates / Build Planner:** see *AI Leveling & Large Guild Build Planner* under *Large*.
  Player-made, editable autopick of talents and stats, so the same clicks are not repeated every level across
  large rosters.
- **Target equipment:** per unit, how it should be equipped; on entering a shop with an upgrade
  available it swaps by itself.
- **The Battlefield beyond the Faith mission.** For now its only use is the Faith Order's errands, and it
  stays that way (author 2026-10-17). Later it becomes one more place of Field Command work and missions: what
  an open skirmish pays, how often the front has a fight. The supply run's walked order with an ambush
  part-way (`Guild.supply_leg`, `Order.owed`) is the shape to reuse. Field Command would then have two jobs,
  the supply run and the front itself (author 2026-10-30): the player enlists as reinforcement, is paid to
  arrive and to fight in the skirmish already under way, and the job is to win it. That is not a walked
  order with an ambush: the battle is the job, so it needs its own order kind.
- **Ancient Ruins as an archaeological site:** start "archaeology" work there. Postponed (2026-10-12 &
  2026-10-19) to design an excavation system with tools (Shovel / Pick), multi-step iterations,
  artifacts, money and lost lore. The Ruins now remember a raid (`Guild.ruins_cleared`) and drop off the
  inspector once empty, so a dig needs the node to keep offering something after it is cleared.
  Author 2026-10-30: still no idea of how archaeology should work to be interesting. Author 2026-11-12: the
  Farmer's quest (clues gathered one by one, `investigation.py`) opened possibilities and is a subsystem a dig
  could reuse; not yet a design.
- **The Claim:** let the player build their own farm to stock food.
- **Combat leveling (Lv 1 -> 2):** assist XP or an
  intermediate arena bout wait on future playtests.

---

# Needs more information

- **Catfolk glyph.** The head glyph (`sly`) is a stand-in: the icon set has no feline head.

- **Playtest with every routine open (author 2026-11-04).** Every block and place is open to a routine today.
  The playtest decides *Routine unlocks* (in *Large*), whether the editor needs validation marks (today a routine
  that cannot run stops at run time with its reason and *Continue*), and whether switching between groups is
  pleasant. The build goes to the other testers again only after a few more features.

- **Loyalty, the oath and who the members are** — plan: [loyalty.md](loyalty.md) (design talk 2026-10-23, no
  code). The player is the guild; a member is a statblock + named traits + an aspiration; one loyalty bar
  per member; the oath is composed once, by the player; recruiting is one person convincing another;
  occupations are gone and the vocation stays on probation. The plan ends with its open questions.

- **Economy numbers (open since the sim's first rounds, 2026-10-08).** The sim meets its
  targets ([../economy_sim.md](../economy_sim.md)); the calls were made (*Ready to do -> Medium -> Measure the
  economy against the decided lines*), what is left is a re-measure.
  - *The Claim's numbers are old.* The Wilds claim (the guild's own holding in the Wilds, built by a
     garrison that sustains it until it is established, then raided now and then) was measured before
     the garrison's `hold` job (rest and heal on the claim) existed, so the sim's "a gamble, established
     by 13-28% of guilds" may be wrong. Not a call: a re-measure, when a sim policy goes for the Claim.

- **Open design questions from the 2026-10-18 playtests** (no code yet).
  - **The world moving by itself** (a Wilds node turns into a lair if nobody clears it). The author's
    long-term vision for time pressure; waits on earlier subsystems. The members' half (an idle veteran
    asks for work or threatens to leave) is the loyalty entry above.
  - **Time pressures from the world itself.** Today's (Bankers' rent, the title defence, the Ogre's
    deadline) are all ones the player chooses. Lumber saturating the wood price enters with the production chain.
  - **Weather fog**, if it ever exists: how it looks apart from darkness. Questions for the author:
    (1) does weather live on the world map, on the board, or both? (2) does it change rules (sight, shots)
    or only the look? (3) before the playtest or after: decided 2026-10-30, after the playtest; nothing exists yet.

- **Talent ideas (author 2026-10-30, answered 2026-10-31; still to be sized).** Talent rules: no
  immunities, no extra AP, no loot multipliers, no one-node perks. Trade-off rule (author 2026-10-31):
  group size and recruiting come from Charisma talents that cost a pick which would otherwise make a
  better individual fighter; a big guild or a strong fighter, not both.
  1. *Charisma tree (work): group size +1 while leading.* Decided (author 2026-11-12): it waits for *Loyalty*
     (`cohesion.py`'s capacity is replaced by it), and is a work talent, a node that may connect to the
     others (Fixer, Joint Pitch and Crowd Pleaser are built). What a big guild gives up (author 2026-11-12): its
     work is slower, it has fewer specialists in craft or healing, so it knows fewer recipes, carries less and
     earns less per action: the bonuses on the work it does are smaller. Open: the tier of the node (deep:
     recruiting is the strongest thing in the game so far).
  2. *Charisma + Wisdom compound:* Demoralize on beasts. A beast has no language, so `Demoralize._can_provoke`
     (`actions/combat.py`) never allows it, and Wordless Menace works on humanoids only. Decided (author
     2026-11-11): not built until the Wisdom (combat) tree has its Beastmaster talents (*Beastmaster talents*
     below). It requires Wordless Menace (Charisma, combat) and one of them, the `also` prerequisite
     (`Talent.also`, as Ready Hand and Ambush Shot use it). The talent gives the holder what
     `AbilityDef.demoralize_ignores_language` gives the racial one (offence only), limited to targets with no
     language of their own; the effect on the beast is the same as on a humanoid (`Demoralized`). Open: whether
     it also needs the holder to see the beast for a turn (the existing sight check already does).

- **Beastmaster talents in the Wisdom tree.** Add Beastmaster talents to the Wisdom (combat) tree, which today
  holds only Alert -> Quick Wits (-> Peripheral Vision) and Iron Will (-> Iron Stance). The first use is the
  prerequisite of *Demoralize on beasts* (*Talent ideas*, item 2), which waits for this tree. Decided (author 2026-11-11): the set is Demoralize on
  beasts, a pre-encounter dialogue window with beasts, taming a captured beast, and at the top commanding beasts in combat.
  Decided (author 2026-11-12): the order is Alert -> the dialogue window; the dialogue window + Wordless Menace (Charisma) -> taming;
  taming -> commanding in combat. *Demoralize on beasts* stays as *Talent ideas*, item 2 says (it waits for this tree).
  Open: the tier of each node (`Group.herd_capacity` is already Beast Whisperer's in the work tree).

- **Does the Assess action itself need a reward? (author 2026-10-31, author/Yohan alignment).** The talent line
  under Tactical Mind (Analytical Eye, Exploit Weakness, Anatomist, Surgical Strike; `talents.py`) already pays
  for a full read, and the AI reads by expected value. Open: whether the action also reveals resistances and
  vulnerabilities or grants a to-hit bonus on its own, so a turn spent investigating competes with a direct
  attack even for a unit with none of those talents. Sits beside the Intelligence talents in *Talent ideas* above.

- **New body actions: one per natural weapon.** `Claws`, `Fangs` and `Horns` still have no 2 AP action
  (`Hooves` and `Bite` have Trample and Clamp, `natural_weapons.py`, `actions/weapon_actions.py`). One
  special action per natural weapon, as a trait of that weapon, like Wrest for `Unarmed`. Decided (author
  2026-11-12): none of the three knocks the foe `Prone`; their actions are about something else. Open: what each
  one does. Each is end-to-end (rules, web tab, AI, tests, tutorial card). Compare with Takedown and Grab in the
  sim so none dominates.

- **Growing the action bar slowly (author 2026-10-31).** Giving every unit many actions at the start is
  too much friction; new actions have to come in gradually, so a new player is not flooded while the
  complexity builds. Open: which actions come at which level or talent. Decide it after *New body
  actions* (author 2026-11-01): Takedown and the natural and unarmed actions are most of what the bar
  would gate (author 2026-11-12: it is gated behind *New body actions*). Takedown and Stand Up are on the bar for everyone today. Ties to *Roster of characters* (*Notes to remember*) and *Levelling is vertical only*.

- **Magic as the vertical progression.** The arc's work is the *Scroll of Invisibility* (*Ready to do ->
  Small*) and *Magic Arc, later* (*Large*). The schools are
  rival factions but not mutually exclusive for a character; magic comes strictly before Archaeology.
  Open: tier 2+ spells and any reputation penalty for rivalry.

- **Recipes learned by owning the item or a teacher (author 2026-10-31).** A recipe paper
  is studied like a level-0 spell (Apothecary's Antidote errand is the first). Open: where more recipe papers
  come from. Today a recipe comes from a race (Dwarf at level 5), a crafting talent (Apothecary, Smith) or that
  paper, and few exist. The intent: learn by owning an item (take the axe to the smith and study it until you can make it)
  or by being taught. A first form: the Library makes dictionaries, so a leader who speaks only Draconic hires a Lizardfolk and
  writes the dictionary to learn the language. Some recipes come from missions, artefacts from quests; the Kobold learns trap
  recipes and places traps farther. The tester's idea: a research system to discover formulas. Author 2026-11-12, the source of more recipes: write a
  recipe from paper, ink, leather and an item of the kind to be written, "studying" that item until the recipe is
  learned; the recipe is then written down the same way a dictionary is. The Library's dictionary teaches more
  languages, which count in Demoralize, trade and recruiting. Decided (author 2026-11-11): a teacher is
  either an NPC who teaches for free or another member of the group held back studying with the student, as if that member were
  the dictionary, recipe or scroll itself; the study time depends on the level of what is learned, and the teacher's Charisma
  bonus helps the student. Open: what the Library's dictionary gives, research. Size a first form when the production chain is picked up.

- **Holy Symbol quest: polish after the first playthrough (author 2026-11-11).** The quest is built and live
  (`missions.FARMER_QUEST_LIVE`, `cult_site.py`, `demon_lair.py`, `investigation.py`). Left:
  - **Art.** Four Demon portraits from the author's Gemini run (prompt and references in
    `docs/art/demon_options/README.md`): the best to `--npc the-demon`, the other three to the `--race Demon`
    pool. Portraits for the six cultists, a Demon glyph of its own (`art_files.RACE_ICON` borrows the Kobold's
    "horned-reptile"), the Cult Site's floor.
  - **Validate the rite by playing it.** The bar (18, three steps of 6), the DCs, the levels and the `+1` per
    clue are first numbers: the sim has no player who reads the bar (the raw cultist fight is level for a guild
    of level 6 to 8 with 6 to 8 members; with the bar on, the sim player almost always loses). The Demon is
    meant to be a problem and is not tuned for the guild to win.
  - **The Demon knows only Hex and Dragonfire.** More schools wait for the new spells the author will design.

================

Adicionar uma carne no kit inicial de cada persaongem.

ACho que os avisos de tutorial estão com MUITO TEXTO, precisaremos ver um jeito de diminuir a quantidade de texto por card e deixar as coisas mais interativas.

O jogo não avisa que gastar tudo de uma vez pode prejudicar o próximo passo. Quado o jogador chegar a 9cp a primeira vez, um aviso fala pra ele tomar cuidado com o dinheiro.

Tavern Recruit: ninguém do grupo fala a língua dos recrutas disponíveis. -> na primeira vez os 3 personagens da ataverna nao forem recrutaveis, ou seja pq o jogador tentou todos e nao conseguiu nenhum ou pq nenhum fala o idioma dele, fvale mostra rum "volte aqui daqui uns dias, talvez tenham novos aventureiros" e explica q a taverna se renova semanalmente.