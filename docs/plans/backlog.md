# Backlog — everything still open

The one place for open work. A task here is a few lines; when it needs more, it **points to its plan** in
`docs/plans/` ([loyalty.md](loyalty.md), [campaign_ai_roadmap.md](campaign_ai_roadmap.md)) or to the doc
that owns the subject: the test suite [../../tests/README.md](../../tests/README.md), the economy sim
[../economy_sim.md](../economy_sim.md), the web client [../web_ui/web_client.md](../web_ui/web_client.md).
What is already built is in the code, its tests and the git log.

Sizes are estimates; claims about what the code already has were checked on 2026-10-22 (the *Ready to do*
items, the plan pointers and the sim's `roll_pack` claim again on 2026-11-01). When an item is done, delete it here and, if it
changed a design premise, record it in `AGENTS.md` or the doc that owns it.

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

Goal: a stable build for the author's playtest and one with friends. Content, AI, measure and economy,
combat presentation and the hub kit are done. Left:

- **Tutorials.** Every card was checked against the code and cut to the rule it teaches (2026-10-21); the
  map's card closes onto the objectives (`gartok/objectives.py`). Left: the author reads every card in play
  and flags what still rings false.
- The *Small* items below, in order: the fighter that cannot move, the icons'
  authors, then the exe.

After the playtest (it answers them, or they are content past it): weapon actions tuning, *Tune the
specialised shops*, Magic Arc tuning, the production chain, cooking with meal buffs, the campaign AI,
Prisoners, Archaeology at Ancient Ruins.

---

# Ready to do

Order inside a size is the order to pick them up: first what blocks the friends' playtest, then bugs, then
the rest.

## Small

- **Bug: a fighter that cannot move and shows no reason (playtest 2026-10-30).** Ancient Ruins, in-game day 75,
  against the spiders, round XIV: Irekdralob could not move and nothing in the action bar said why.
  Rebuild the fight from its combat-log JSONL (`CombatLog`; the author has it as a local recording of
  2026-10-30 on another machine; it is not in the repo, so ask for it), find the
  condition or rule that blocked the move (web, a spider's web, a stuck state, no free cell, AP), then fix
  it and make the action bar always name the blocker of a disabled Move. Mock both ways first (author
  2026-11-01): the tooltip the other disabled actions have, and a fixed line on the bar; compare them with
  today's and pick. Test: the repro as a fixed board, and a disabled Move always carries a reason.

- **Complete the icons' author list (decided 2026-11-01).** The Credits screen (title menu) reads its
  authors off `gartok/assets/icons/LICENSE.txt`, which is partial. Before shipping, complete that list from
  game-icons.net for the icons actually used (one author per icon on the site); the screen picks the
  new names up with no code change.

- **Rebuild the friends' exe last (2026-11-01).** Run `build_exe.bat` on Windows once the other playtest
  items are in, so `dist/GARTOK.exe` carries their fixes.

- **Bring the author's own skills into the repo (decided 2026-11-01).** Only the author can do it: the
  skills on their machine (`~/.claude/skills/`) are out of an agent's reach. For each one the repo needs,
  copy it into `.claude/skills/<name>/SKILL.md`, then check it against the owner list in
  `AGENTS.md`: no rule an owner doc already holds, no pointer to a file that is
  gone, one line in `AGENTS.md` only if an agent would break something without it. Nothing in the repo
  depends on them being there.

## Medium


- **Rules as keywords, the next ones (playtest 2026-10-30).** `keywords.py` and the wiki's KEYWORDS chapter
  exist, with *Brutal N* the first (N more rolls of the weapon's damage; every Brutal of the game is 1;
  the crit multiplies the whole blow last). Missing: look for the next repeated rules (Flanked, Prone...)
  and add each as a `Keyword`; a keyword written inside a description (tooltips of the sheet, of the
  action bar) should link to its entry on hover; the assess card in the bestiary should link a racial
  ability and a weapon to their wiki entry on hover (playtest 2026-11-01); check the sheet's weapon-action
  chip shows the new text on hover.

- **The tests the pygame campaign's cut lost (found 2026-10-28).** Rewrite them on the web screens:
  everyone jailed, no save mid-battle, two due screens in turn, the REST row, a trip cancelled. The old
  screens and their tests are in git before the cut.

- **Review the cheapest item prices (author 2026-11-01).** Several sit at 1 or 2 copper with no logic:
  a Chisel at 1, a Scroll at 1 (below Paper at 10 and 1sqm Hide at 12), a Cloak and a Torch at 2. Price a
  tool or a crafted good above the material it is made from, then run the `balance` tier and
  `scripts/economy_report.py`. The starting kit draws items by price, so the prices set what a recruit carries.

- **Scroll of Invisibility (Magic Arc).** A Library quest unlocked at max Library reputation with a caster
  initiated in magic (direction 2026-10-19).

- **UI sound: the missing cues.** `gartok/sound.py` has 7 cues and every one
  of the 16 files in `assets/sounds/` is used, so confirm, error, equip and end of turn have no sound. The
  author picks the files (Kenney, CC0, same `LICENSE.txt`); then add them to `CUES` / `LEVEL`, write down
  which act plays which cue (one table in `docs/web_ui/web_client.md`), and wire them: equip in the sheet,
  confirm on the dialogs, the error cue in place of `miss` in `api()`. End of turn is a battle cue: it comes
  from the server (`st.sounds` off the combat log, `battle.py`), with a test in `tests/test_battle_fx.py`.
  Playtest 2026-11-01 adds two: the level-up cue is much louder than a click (lower its `LEVEL`), and the
  sound lags behind the click (measure first whether it is the audio start or the round trip to the server).

- **Warm the assets while the game opens (playtest 2026-11-01).** A screen change reloads the page, and
  the first load of each asset is still the slow one (~990 KB, ~350 ms to a ready screen). Load the fonts,
  icons, portraits and sounds while the title opens (a manifest endpoint, a short load veil there). The
  sounds are the bulk of what a warm reload still downloads (16 `Audio` files, ~180 KB: the browser does
  not reuse them from its cache). Measure again with a filmstrip (screencast frames of a reload).

- **Hover on the vocation's races shows their modifiers (author 2026-11-01).** On the vocation pick,
  hovering a race lists its attribute modifiers and racial abilities, read off the registries. Only if
  vocations stay (see *Vocations: difficulty or build?* below).

- **The dictionary crafts too fast (playtest 2026-11-01).** One was made on day 18 in about 4 or 5 hours.
  Find the time the craft takes (`craft_level.py` and the recipe) and set a target with the author, then
  review the other crafts' times against it.

- **Is a STR/CON-heavy draft objectively best? (author 2026-11-01).** The author drafts a Charisma leader
  plus the strongest, toughest bodies for the rest and cannot tell bias from fact. Measure with the headless
  fights and the economy sim: squads built on max STR/CON against squads spread over other attributes, at
  equal cost. Result decides whether the starting squad and the stat draft need a rebalance
  (*Starting squad is weak* in the playtest notes).

- **The wiki and the tutorials read every number off the code (author 2026-11-01).** The group capacity
  went wrong because the text restated the rule by hand. Three parts: a test that no string literal in
  `wiki_rules.py` holds a digit, with the constant made where the code has none either (Defend's +1 AC
  in `actions/combat.py`, the flank's -2 in `actions/base.py`, the coin values, Sneak Attack's +1d4);
  the `group.CAPACITY_TERMS` pattern (the sum is the rule, the text reads the same tuple) for the other
  formulas the wiki states (`recruit.capacity` / `leader_capacity`, `Group.herd_capacity` with Beast
  Whisperer); and the `locales/en.json` cards (the tavern's says "past the guild's second" and "$15 a
  day") filled from the constants or checked against them by a test. Then one load-bearing line in
  `AGENTS.md`.

---

# Large and later

## Large

- **Weapon actions: tune the favoured cases after a playtest.** Rebalanced 2026-10-16: out of its case an
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
- **The sim's long game (found 2026-10-21, left for later the same day).** `economy_guild.Balanced` plays the
  author's line: 92% of guilds meet the day-30 milestone, none die before it. Past it (the Pit, a recruit,
  the Wilds hunt as the income) 18 of 40 die by day 60, all hunting: a lost lethal fight takes the whole
  group. The sim gives the player `SKILL = 0.5` of the AI's losses in every fight; the author's 87 hunts
  measure 0.84 (arena 0.44, road ambushes ~0, `combat_pairs.py`). Kept at 0.5 (the sim:
  [../economy_sim.md](../economy_sim.md)).
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

## Art (made by hand, not code)

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

- **Native window for the web client (pywebview or Tauri).** Today the game opens in an Edge or Chrome app
  window. pywebview's `pythonnet` is unverified on Python 3.14. Wanted one day, not now.

- **The in-game wiki shows only what the guild already knows (author 2026-11-01, decided).** The wiki is
  the player's own notebook, not the game's encyclopedia: a player who opens it to reread how the sword's
  action works must not be spoiled on the next creature, recipe or talent. Today every chapter in
  `web/wiki_session.BUILD` prints the whole catalog from turn one (Beasts: Hit Die, size, speed, abilities
  and drop odds; Talents: every racial node of every race; Recipes: all of them). Gate each chapter on what
  the guild has met, owned or learned (`intel`, known recipes, the talents of the races in the guild), with
  a locked-entry stub or no entry at all. Cases given (author 2026-11-01): a shop's items appear once the
  guild has entered a shop that stocks them; a race appears when the guild hires one or finishes a 100%
  assess of it; a beast appears at a 100% assess. Open: whether the wiki builds partial entries (the
  assess filling a beast in bit by bit). Cases still to decide: recipes (known, or seen crafted), talents
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

- **A talent with more than one prerequisite.** The tree already draws the second requirement as a red dotted
  line, but no talent has one yet. The day one does, check that this is how it reads.
- **Roster of characters, not an army of clones (author 2026-10-31).** Many action-bar entries and each
  unit a character in its own right, friction accepted. The trade-off, named: eight identical units are
  fast to play (move, hit, hit), eight complex ones mean hundreds of buttons a turn.

## To discuss and reflect on

Not tasks and not yet decisions: premises the author wants to think over before they harden.

- **Everything is open from the day the guild is founded (author 2026-10-31).** Nothing is unlocked by
  story; what gates a thing is money, exploring a place, a reputation, a talent or a race. The author
  knows this makes levelling feel flat (*Playtest notes -> 2026-10-31 -> Levelling is vertical only*).
  Question: keep it fully open and fix levelling elsewhere, or let something be earned in order?
- **Release (author 2026-10-31).** Itch.io first, as an indie demo (pay what you want), while the game
  grows; Steam when there are 20+ hours of play ($100 fee; the generative-AI content flag must be
  ticked). Mobile does not fit: the UI is heavy, though it is a web app. A Kickstarter to pay a real
  artist was suggested. State the AI use plainly on the store page: generative AI is only the character
  portraits and a few tree sprites; the rest is drawn by code (the axe icon is an SVG written in code).
- **How power progress should work (author 2026-11-01).** Headless fights (10 each, both sides on the AI)
  showed that recruiting beats getting strong: 2 L3 lose 9 of 10 to 6 L1 wolves, one L10 (63 HP) loses
  10 of 10 to 8 L2 wolves, 3 L4 lose 9 of 10 to 4 L3 wolves, while 8 L3 sweep 2 L0 wolves and 10 L20 sweep
  6 L1 soldiers. Headcount weighs more than level, and armour barely moved the 3-against-4 result.
  Question: is that the progression the game wants, or should levels and gear count for more than bodies?
- **Co-op / multiplayer on a shared map (author 2026-10-31).** Each band a player. A daydream; the
  tester does not see it fitting. No plan.

---

# Playtest notes

## 2026-11-01

- **Vocations: difficulty or build? (author 2026-11-01).** If vocations stay, is playing Marsh objectively
  worse than Caravan? Either flag it to the player ("risky" and the like), or balance them to be equally
  desirable. Either way the game needs a way to test the vocations' balance (`balance_sim.py`,
  `economy_sim.py`; see *Vocations are far apart* under 2026-10-31).
- **The AI over-uses two things.** It stabilises allies (it loses turns and fights) and it pushes then
  flees (day 17: a wolf pushed, ran off and came back; it may push only to cut the flank when it could just
  walk away). Task, before any morale work because it touches much of `ai/`: review the priority of Stabilise
  and of push-and-flee, in a headless fight set.
- **Morale: flee or surrender (author 2026-11-01, future).** Enemies and the player's units enter a
  "fleeing" mode or surrender. Think the design (a morale number, what breaks it, what a fleeing unit does,
  prisoners) after the AI review above. It ties to *Prisoners*.

## 2026-10-31

A friend's (Johann) first session (about 2 h, no tutorial from the author). The author's stated intent from the
same talk is spread over *To discuss and reflect on*, *Notes to remember*, *Needs more information* and the
items it touches. Raw feedback, not yet sized:

- **What worked (do not "fix" it).** The character progression, combat, and the pull of "always something
  to go after" (the exclamation marks on the map). Two musicians playing while the rest worked was the
  strategy he liked. He compares it with, or above, Wartales /
  Battle Brothers / Mount & Blade for fun, and finds it easy to play in short sessions. He stopped because
  of that bug and because he had played a lot, not because he was bored.

- **Theme: the rules sit where the player does not look.** The wiki, the menu and the tutorial text were
  not read; the player learned by doing, and paid for it (rations, the draft, Delay). A fix per case is
  small; the pattern is to show the rule where the decision is made (a pick, a price, a button).
- **No difficulty signal.** He avoided the arena ("if wolves kill me, the arena will") and the first bout
  is easier than the wolves (3 level-0 fighters against 2 to 6 wolves of level 1 to 4). Ideas: a danger
  hint on a node or fight before entering (a level range, "easy / hard for this group"); the measure
  behind it exists (`encounters.pack_power`).
- **Race and vocation choice cannot be read.** He chose Delvers for the buff, by lore, not by numbers, and
  could not tell what a race gives ("mental bonus, stat check: means nothing yet"). He thought the Automaton the
  strongest race; the author says Orc and Goliath are, and the game does not show it. Show what a race gives
  in plain words at the pick, and see the vocation balance below.
- **Vocations are far apart** (author): Delvers and Caravan ahead; Warband fine for Orc / Goliath; Scholars
  for the races that cast early; Wilds and Marsh weak. Rework or balance with the vocation probation in
  *Loyalty, the oath...*; each perk should act on a daily loop. **Not validated** (author 2026-10-31: these
  are impressions, not measured). Check them first with `balance_sim.py` / `economy_sim.py` /
  `scripts/economy_report.py`: vocation ranking, and whether Orc (does not fall) and Goliath (carries
  double, no donkey to buy) really are the strongest races. Only then rework.
- **Starting squad is weak.** STR 2 or 3 carries nothing, a bow is too dear, and the start weapon is
  a dagger or a piece of an axe ("at least one real weapon"). The author would take 18 STR, 18 CON and 0
  elsewhere at level 0. The kit half is built (`starter_kit.py`: a random weapon and item by price).
- **Food was learned wrong.** He bought what looked like 20 days of shelf life and it spoiled; beer
  first (cheap at 4 copper and durable), then Potato; a farm trip for it did not pay against Fruit at the
  grocery. Show shelf life in the shop row. Check the economy report: is beer the best buy per day? No
  hangover for a beer-only diet (author 2026-10-31: does not like it). Decided: the supply is a
  constraint on purpose, not an afterthought: a group of ten plus a cart eats eleven meals a day, a
  10-day territory defence needs ~110 meals and a tavern holds tens (about 15 beers, 10 meats, 30
  potatoes). Salted meat and beer are the end-game foods (30 and 20 days), Potato lasts 7, fruit 1;
  hunting pays through meat and hides sold, then potatoes bought. Left: make that constraint visible
  (shelf life in the row, the meals a trip or a defence needs).
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
  Already in *Older raw notes* (programmable order chains) and *Epic*.

- **Tutorial cards are text only and did not help.** He read them, but plain text did not explain the
  mechanics; he learned by playing. Open question: show instead of tell (a small diagram or a
  highlight of the control on the screen), or shorter cards that point at the first action.
- **The Reputations tasks only half guide a start.** Found them "almost intuitive", not a clear "how
  to begin". Check whether the first deeds read as a path.
- **Rations are learned the expensive way.** Travel eats rations (once a day) and he found out by
  spending them. The wiki was opened once and never used. Ideas: a ration/day cost line in the
  travel preview, a first-travel warning, a link from the tutorial to the wiki.
- Good sign: he understood the screens by playing and asked whether to continue (about 2 h in).

## Older raw notes (2026-10-12, 2026-10-21)

To be sized as they are picked up. Guiding rule (2026-10-12): **fewest possible buttons on the map**: a node
has one "Enter" button and its functions are tabs inside.

- **Too few icons for the guild banner (10-21).**
- **World and soul (10-21):** the world needs story depth before the Archaeology arc; the game still lacks
  "soul" (see *Loyalty* in *Needs more information*).
- **Leveling templates:** player-made, editable autopick of talents, so the same clicks are not
  repeated every level.
- **Target equipment:** per unit, how it should be equipped; on entering a shop with an upgrade
  available it swaps by itself.
- **Programmable order chains for a group** (see *Programmable orders: brainstorm and spec* in *Needs
  more information*), e.g. gather Lumber at the Yard -> sell Lumber and
  buy food -> gather again. Large; ties to `orders.py` and the sim's planner. Intent (author
  2026-10-31): macro management through automation, **optional**. The main group is played by hand;
  the secondary groups run routines (collect wood, buy vials, craft healing potions and stock the guild
  inventory; study a spell for two months) and the player collects when back from the expedition. A
  player who likes clicking can still do 80 clicks a day. The player never runs two adventures at
  once: automation is for the world around the expedition. It is why the game has several groups
  (without it they feel slow, as in RimWorld). The author knows it may push some players away and goes
  ahead: the game is first for them. The tester's view: it only attracts, it turns micro into macro.
- **The Battlefield beyond the Faith mission.** For now its only use is the Faith Order's errands, and
  it stays that way (author 2026-10-17). Later it becomes one more place of Ledger Hold work and missions:
  what an open skirmish pays, how often the front has a fight. The supply run's walked order with an
  ambush part-way (`Guild.supply_leg`, `Order.owed`) is the shape to reuse. Ledger Hold would then have
  two jobs, the supply run and the front itself (author 2026-10-30): the player enlists as reinforcement,
  is paid to arrive and to fight in the skirmish already under way, and the job is to win it. That is
  not a walked order with an ambush: the battle is the job, so it needs its own order kind.
- **Ancient Ruins as an archaeological site:** start "archaeology" work there. Postponed (2026-10-12 &
  2026-10-19) to design an excavation system with tools (Shovel / Pick), multi-step iterations,
  artifacts, money and lost lore. The Ruins now remember a raid (`Guild.ruins_cleared`) and drop off the
  inspector once empty, so a dig needs the node to keep offering something after it is cleared.
  Author 2026-10-30: still no idea of how archaeology should work to be interesting; nothing to size
  until that answer exists.
- **The Claim:** let the player build their own farm to stock food.
- **Combat leveling (Lv 1 -> 2):** the Wilds weights were fixed (`142b6f5`); assist XP or an
  intermediate arena bout wait on future playtests.

---

# Needs more information

- **Programmable orders: brainstorm and spec (author 2026-11-01).** Not a build task: first find out
  exactly what the author wants, then write it in a plan (`docs/plans/programmable_orders.md`) so the
  implementations are chosen from a real specification. Several entries want a composed or automated order
  and today each names its own shape: the programmable chains and the secondary groups on routines (*Older
  raw notes*), the Ledger Hold front where the battle is the job (*The Battlefield beyond the Faith
  mission*), the production chain's gather-sell-buy loop, and the stints in `stints.py`. Deliverables: (1)
  brainstorm with the author the use cases (which routines, who runs them, what interrupts them, what the
  player collects and when); (2) identify every place that already runs an order (`orders.py`,
  `stints.py`, `MapSession.spend`, the supply run and the hunt) and what they share; (3) document the
  options (a list of ordinary orders run by the one clock, or a new order kind with state) with a
  recommendation. Constraint to keep: only `campaign.advance` moves the clock.

- **Loyalty, the oath and who the members are** — plan: [loyalty.md](loyalty.md) (design talk 2026-10-23, no
  code). The player is the guild; a member is a statblock + named traits + an aspiration; one loyalty bar
  per member; the oath is composed once, by the player; recruiting is one person convincing another;
  occupations are gone and the vocation stays on probation. The plan ends with its open questions.

- **Economy numbers to sign off (open since the sim's first rounds, 2026-10-08).** The sim meets its
  targets ([../economy_sim.md](../economy_sim.md)); these are calls only the author can make, in rough
  order of impact. Settled (author 2026-11-01): the Medic stays a luxury for an instant cure when one is
  needed now (planning a rest is the way otherwise); upkeep is intended: the City house is a guild seat
  and dear on purpose ($30 a week), and a day labourer lives to work, eat and sleep, so the Yard alone
  never keeps a house or an animal.
  1. *The Games pay too little for their risk (direction decided 2026-11-01, numbers open).* A Games bout
     (Brawl or Capture the Flag, 3 a side) costs $30 a fighter ($90 for the three) and pays a flat $130,
     against three opponents rolled level 1 to 6 each (`encounters.ARENA_LEVEL_WEIGHTS`: 30/24/18/13/9/6,
     mostly 1 to 3, mean ~2.7); the Ribbit Brothers' bout costs $40 a fighter for $450, six a side,
     lackeys at level 3. A level 3-4 group has no reason to risk being beaten up for that: the purse (or
     the stake against it) has to make a bout worth more than what the same group earns elsewhere in
     the same days, the Wilds first. Measure the Games' net per bout against the Wilds hunt for that group
     (`scripts/economy_activities.py`, `economy_report.py`), then set the numbers.
  2. *How lethal the Wilds should be.* A level-3 squad that does not win nearly every fight cannot make a
     living there, and the Old Road's ambush (20% a pass, `world.ROAD_AMBUSH_CHANCE`) fires on every walk.
     Re-measure now that a group too strong for a pack is no longer ambushed by it (author 2026-11-01).
  3. *How much a crafting specialist may earn.* The shelves aim at 2-3x a lumberjack; the author's note says
     crafting is for saving money and reaching what cannot be bought, not a business. Needs the sum first
     (author 2026-11-01): what each crafting loop earns a day against the Yard, with
     `scripts/economy_report.py` and the restock sweep, before the call. Ties to *Tune the specialised
     shops*.
  4. *The reference scenario past the start.* The sim tests the Wilds, the Games and the Claim from a
     guild that starts at level 3 with $250 (`economy_guild.py --level 3 --capital 250`), a guess. The
     author's own line (2026-11-01): a group of **4 at combat 1, work 2** already goes to the Wilds for
     hides and mushrooms. Make that the scenario: `--level` is one number today, so the sim needs the
     combat and work tracks apart (and `--size 4`); the starting coin is still open (proposal: what the
     sim's own guild holds the day it reaches combat 1, work 2).
  5. *The Claim's numbers are old.* The Wilds claim (the guild's own holding in the Wilds, built by a
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
  1. *Charisma tree (work and combat):* +1 group size limit while leading; -10% crowd penalty
     (`recruit.size_penalty`); and a joint pitch. Joint pitch, as the author means it: A (holds the
     talent) recruits a target that B could also recruit on their own. A "consumes" B: instead of one
     roll per recruiter, the pitch is N rolls (A and every other ally who could recruit that target), each
     `1d20 + A's CHA + 1 per other ally who could`. A has +2 and B +1 in the author's example, so two
     rolls of `d20+3`. A failure spends the week's attempt (`recruit.bar`) of everyone involved.
     Decided (author 2026-11-01): the best roll counts (the talent is a way to try more than once); the
     holder becomes `recruited_by`; "could recruit" means every requirement the ally would need to
     recruit that target alone (`slots_free`, the shared language, the rest of `recruit.py`'s checks).
     Open: three nodes or one chain, which tier; and whether "group size limit" is `cohesion.py`'s
     capacity (to be replaced by Loyalty, see above).
  2. *Intelligence tree (combat), two talents:* (a) **group leader only: places the whole group** before
     the fight; (b) **places only oneself**. Together they are a ladder (b the early node, a the late one),
     and (a) needs the leader to be on the board. Decided (author 2026-11-01): only inside the start zone;
     the UI is like the flag's placement (a pre-fight setup step, `BattleSession` already has "flag" and
     "trap"), placing the characters one after another in initiative order. (a) works only when the
     leader is on the board (an arena bout picks its fighters, a hunt leaves its guards behind: without
     the leader, no one places the group). Open: how `ai/` places its own side: keep today's start
     for now, then record how the author places in a few scenarios and train the AI on them.
  3. *Charisma + Wisdom compound:* Demoralize on beasts. The point is the language: a beast has none,
     so `Demoralize._can_provoke` (`actions/combat.py`) never allows it. The talent gives the holder what
     `AbilityDef.demoralize_ignores_language` gives the racial one (offence only), limited to targets
     with no language of their own. The effect on the beast is the same as on a humanoid
     (`Demoralized`: cannot move, lower defenses). Open: the compound talents' shape (no cross-tree node
     yet, see *Notes to remember -> a talent with more than one prerequisite*) and whether it also needs the holder
     to be able to see the beast for a turn (the existing sight check already does).

- **Assess grows into an Intelligence combat tree (author 2026-10-31).** Study the foe, and what you
  know grants crit and to-hit: a turn spent investigating before the beating is a real option. Not built
  to the author's liking yet. Sits beside the Intelligence talents in *Talent ideas* above.

- **New body actions: Takedown and one per natural weapon (`prone` is shared).** Both need a design pass
  first, and both want the same new condition, so `prone` is designed once, for both. Decided (author
  2026-11-01): `prone` is a simple condition: standing up costs AP, a prone unit cannot move (it must stand
  first) and attacks at -2 while down. Before building, compare Takedown with Grab in the sim so neither
  dominates the other:
  - *Takedown* (like Push and Grab): knock a foe prone, with a roll. No `prone` condition exists yet
    (`conditions.py`).
  - *A 2 AP action for `Claws`, `Bite`, `Fangs`, `Hooves` and `Horns`*: one special action per natural
    weapon (`natural_weapons.py` is built), like Wrest for `Unarmed`, as a trait of that weapon. Open:
    the action for each. Each is end-to-end (rules, web tab, AI, tests, tutorial card).
  Open: how many AP standing up costs, Takedown's roll, to-hit against a prone foe, and which of the five
  natural actions knock prone too.

- **Growing the action bar slowly (author 2026-10-31).** Giving every unit many actions at the start is
  too much friction; new actions have to come in gradually, so a new player is not flooded while the
  complexity builds. Open: which actions come at which level or talent. Decide it after *New body
  actions* (author 2026-11-01): Takedown and the natural and unarmed actions are most of what the bar
  would gate. Ties to *Roster of characters* (*Notes to remember*) and *Levelling is vertical only*.

- **Magic as the vertical progression.** The arc's work is the *Scroll of Invisibility* (*Ready to do ->
  Medium*) and *Magic Arc, later* (*Large*). The schools are
  rival factions but not mutually exclusive for a character; magic comes strictly before Archaeology.
  Open: tier 2+ spells and any reputation penalty for rivalry.

- **Recipes learned by owning the item or a teacher (author 2026-10-31).** Today a recipe comes only from
  a race (Dwarf at level 5) or a crafting talent (Apothecary, Smith), and few exist. The intent: learn by
  owning an item (take the axe to the smith and study it until you can make it) or by being taught. A
  first form: the Library makes dictionaries, so a leader who speaks only Draconic hires a Lizardfolk and
  writes the dictionary to learn the language. Some recipes come from missions, artefacts from quests;
  the Kobold learns trap recipes and places traps farther. The tester's idea: a research system to
  discover formulas. Open: teachers (who, what it costs), study time, what the Library's dictionary
  gives, research. Size a first form when the production chain is picked up.

- **Better food: dishes with buffs (after the magic arc).** Food only quells hunger and the Potato does it
  cheapest. The preservation recipes are built (Jerky, Roast Meat, Fruit Compote; no buffs, by design).
  Decided: cooking is an ordinary craft; a premium dish gives a 24 h buff that moves one number (HP, an
  attribute, advantage on a named kind of action...), and only the most recent meal's buff is active.
  Open: the dishes and their buffs, and the cost to the economy sim (`cheapest_food_price` stops being
  the one price of a meal). Marsh's slower rot is priced low until this lands.
  - **A use for Rotten Food (author 2026-11-01).** Today it is worthless (`price=0`) and a keeper bins
    it. Weigh giving it a use, compost at the Farm or a crafting material, when the food patch or the
    farm patch comes up.

- **DECIDE HOW HOLY SYMBOL DROPS (author 2026-11-01).** No recruit starts with one (only the Priest did) and no shelf sells it, while Faith's rite
  (`rite.py`) consumes it, so the Faith school has no way to get it.
  Not for sale at the Market (author's call). Decide the source: a lair pile, a mission reward, a rare
  drop from a given foe, or a temple quest. Until then the rite cannot start in a new game.
