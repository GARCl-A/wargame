# Backlog — everything still open

The one place for open work. A task here is a few lines; when it needs more, it **points to its plan** in
`docs/plans/` ([loyalty.md](loyalty.md), [campaign_ai_roadmap.md](campaign_ai_roadmap.md)) or to the doc
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

Goal: a stable build for the author's playtest and one with friends. Content, AI, measure and economy,
combat presentation and the hub kit are done. Left:

- **Tutorials.** Every card was checked against the code and cut to the rule it teaches (2026-10-21); the
  map's card closes onto the objectives (`gartok/objectives.py`). Left: the author reads every card in play
  and flags what still rings false.
- **Translation to pt-br: the author reads it in play.** Every text has a `pt-br` entry (the parity test is strict). Left: the author
  plays in `pt-br` and flags the tone, the text longer than its box (Portuguese runs 20-30% longer), accents the font lacks, sort order and
  number and money formats. The terms: [../glossary_pt_br.md](../glossary_pt_br.md); the settings screen's "Linhas do registro" note is still open.
- **Holy Symbol: the drop and the Farmer's quest** (*Needs more information*), after the translation.
- The *Small* items below, in order: the bugs (the fighter that cannot move and the rest of the 2026-11-02
  ones), the overflows, the icons' authors, then the skills.

After the playtest (it answers them, or they are content past it): weapon actions tuning, *Tune the
specialised shops*, Magic Arc tuning, the production chain, cooking with meal buffs, the campaign AI,
Prisoners, Archaeology at Ancient Ruins.

---

# Ready to do

Order inside a size is the order to pick them up: first what blocks the friends' playtest, then bugs, then
the rest.

## Small

- **Translation leftovers.** The combat log keeps a unit's name as the string of the moment (a `Ref` for authored NPCs would fix it);
  `routine.paused` reasons, the memorial `cause`, a dialogue's `Result.text` and the guard notices are stored already translated; an ambush
  title is chosen when the talk opens; text built from ids with `.title()` / `.capitalize()` (school, stage, node ids) and the stat labels of
  `magic.py`, `intel.py`, `unit_derive.py`, `group.py` still need a review. `REFERENCE.pt-br.md`: turn the 78 literals of `reference.py`
  into keys so `python -m gartok.reference` can write it. Run `scripts/i18n_leaks.py` when a screen is added.

- **Combat teaches itself: the tutorial and the conditions (playtest 2026-11-02, Johann 2026-10-31).**
  (1) The combat tutorial explains the actions: today the cards are text and did not help, so show the
  control (a highlight on the bar) and cover each action of the bar. Web only (`screens/battle/`), with the
  card's key in `locales/en.json`.

- **Ambush on the way in, at every dangerous node (author, note outside playtests).** The Wilds, the
  Frontier Outpost and the Battlefield should roll an ambush per leg like the Old Road
  (`forced.py` rolls `world.ROAD_AMBUSH_CHANCE` once per arrival at an `unsafe` node), and the map should
  mark a node that has one ("ambush on the way"). Check what `unsafe` covers today; the chance per node is
  tuned together with *How lethal the Wilds should be* (*Needs more information -> Economy numbers*).

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

- **Rules as keywords, the next ones (playtest 2026-10-30).** `keywords.py` and the wiki's KEYWORDS chapter
  exist, with *Brutal N* the first (N more rolls of the weapon's damage; every Brutal of the game is 1;
  the crit multiplies the whole blow last). Missing: look for the next repeated rules (Off-guard, Prone...)
  and add each as a `Keyword`; a keyword written inside a description (tooltips of the sheet, of the
  action bar) should link to its entry on hover; the assess card in the bestiary should link a racial
  ability and a weapon to their wiki entry on hover (playtest 2026-11-01); check the sheet's weapon-action
  chip shows the new text on hover.

- **Review the cheapest item prices (author 2026-11-01).** Several sit at 1 or 2 copper with no logic:
  a Chisel at 1, a Scroll at 1 (below Paper at 10 and 1sqm Hide at 12), a Cloak and a Torch at 2. Price a
  tool or a crafted good above the material it is made from, then run the `balance` tier and
  `scripts/economy_report.py`. The starting kit draws items by price, so the prices set what a recruit carries.

- **Scroll of Invisibility (Magic Arc).** The item exists (`items.py`); missing is the Library quest, unlocked at max Library reputation with a caster
  initiated in magic (direction 2026-10-19).

- **UI sound: the missing cues.** `gartok/sound.py` has 7 cues and every one
  of the 16 files in `assets/sounds/` is used, so confirm, error, equip and end of turn have no sound. The
  author picks the files (Kenney, CC0, same `LICENSE.txt`); then add them to `CUES` / `LEVEL`, write down
  which act plays which cue (one table in `docs/web_ui/web_client.md`), and wire them: equip in the sheet,
  confirm on the dialogs, the error cue in place of `miss` in `api()`. End of turn is a battle cue: it comes
  from the server (`st.sounds` off the combat log, `battle.py`), with a test in `tests/test_battle_fx.py`.
  Playtest 2026-11-01 adds two: the level-up cue is much louder than a click (lower its `LEVEL`), and the
  sound lags behind the click (measure first whether it is the audio start or the round trip to the server).

- **The battle takes ~1 s to open, and each action repaints for ~230 ms (playtest 2026-11-01; the author does
  not feel it, so investigate before changing anything).** Title,
  map and hub are ready in ~350-450 ms; the battle is not, even with every file cached. The time is not the
  files: `Board.draw` (`screens/battle/board.js`) runs on every state change and costs ~230 ms in a headless Chromium
  without GPU, most of it `fogAndLight` (blurred light and fog layers at full resolution) and `memory`;
  `drawStatic` (floor and walls) is cached and runs once. Real GPU timings are unknown. Options: draw the
  light and fog layers at a lower resolution; skip the repaint of those layers when an action did not change
  what the side sees; paint a first frame (cached floor) before the light.

- **Hover on the vocation's races shows their modifiers (author 2026-11-01).** On the vocation pick,
  hovering a race lists its attribute modifiers and racial abilities, read off the registries.

- **The dictionary crafts too fast (playtest 2026-11-01).** One was made on day 18 in about 4 or 5 hours.
  Target (author 2026-11-04): a character with INT 10 and no bonus takes about 3 days. Find the time the
  craft takes (`craft_level.py` and the recipe) and bring it to that, without lengthening the other
  crafts (the author fears slow, boring crafts): check their times against the dictionary's before
  touching any.

- **Is a STR/CON-heavy draft objectively best? (author 2026-11-01).** The author drafts a Charisma leader
  plus the strongest, toughest bodies for the rest and cannot tell bias from fact. Measure with the headless
  fights and the economy sim: squads built on max STR/CON against squads spread over other attributes, at
  equal cost. Result decides whether the starting squad and the stat draft need a rebalance
  (*Starting squad is weak* in the playtest notes).

- **The wiki and the tutorials read every number off the code (author 2026-11-01).** The group capacity
  went wrong because the text restated the rule by hand. Three parts: a test that no string literal in
  `wiki_rules.py` holds a digit, with the constant made where the code has none either (Defend's +1 AC
  in `actions/combat.py`, the off-guard -2 in `actions/base.py`, the coin values, Sneak Attack's +1d4);
  the `group.CAPACITY_TERMS` pattern (the sum is the rule, the text reads the same tuple) for the other
  formulas the wiki states (`recruit.capacity` / `leader_capacity`, `Group.herd_capacity` with Beast
  Whisperer); and the `locales/en.json` cards (the tavern's says "past the guild's second" and "$15 a
  day") filled from the constants or checked against them by a test. Then one load-bearing line in
  `AGENTS.md`. Playtest 2026-11-02 adds a case: the wiki states the Glaive's extra action but not its
  +1 reach (if it has one), so a weapon's entry must list every property it carries, read off its
  `ItemDef`.

- **Body size AC adjustment (playtest sim balance, author 2026-11-08).** Simulation shows 4 of 5 small races
  underperform (score < 50) due to reduced weapon damage. Apply size AC adjustments: Tiny (+2 AC), Small (+1 AC),
  Medium (0 AC), Large (-1 AC) in `unit_derive.py`. Re-measure with `scripts/combat_pairs.py` and `scripts/economy_report.py`.

- **Vocation tweaks: Warband, Delvers, Marsh (author 2026-11-08).**
  (1) Warband: +1 Morale for group members.
  (2) Delvers: bonus restricted specifically to licensed gathering (mining and lumber with license)
  and hunting/foraging, instead of an unspecific wage bonus across all work.
  (3) Marsh: softens hunger attribute penalties by 2 (day 1 Hungry gives 0 penalty instead of -2;
  day 2 Starving gives -2 instead of -4, while HP max remains capped at 1; days 3 and 4 remain unchanged:
  day 3 Incapacitated, day 4 Starvation death). Replaces the old "food pause every 10 days" perk.

- **Wiki: document Hunger and Starvation rules.** The in-game wiki does not yet explain the hunger rules.
  Document: 1 meal/ration required per day at upkeep; hunger progression (fed -> hungry -> starving -> dying);
  attribute penalties (-2 for hungry, -4 for starving); HP max capped at 1 when starving; incapacitation on day 3;
  starvation death at 4 missed meals; Rotten Food eaten only in last-resort desperation.

- **Wiki: dynamic alphabetical chapter ordering & Conditions vs Keywords.** Sort wiki chapters dynamically
  by translated label (`locales/*.json`) so ordering is natural in all languages. Check whether "Fleeing" belongs
  under Conditions (`conditions.py`) rather than Keywords.

- **Draft screen: weapon ability tooltip on hover (author 2026-11-08).** Hovering over a drafted character's
  weapon should show the weapon ability tooltip, clarifying tactical traits during hiring.

- **Map screen: overencumbered member tag (author 2026-11-08).** In the band member dropdown on the left side
  of the map screen, add an "overencumbered" tag alongside the existing "leading" and "hungry" status tags.

- **Combat log: full damage roll breakdown (author 2026-11-08).** The log currently displays the hit roll
  breakdown but not the damage roll. Add damage roll detail at the same level of transparency.

- **AI heuristics: Shove vs Attack x2 (playtest 2026-11-08).** Review AI combat priorities when surrounded or
  flanked. Ensure the AI does not overvalue shoving a foe away (to break flanking or force movement) over
  attacking twice to eliminate or soften an immediate threat.

- **AI target selection against flying units (playtest 2026-11-08).** When an enemy flyer (fairy) is out of
  reach, nearby melee AI (wolves) defaulted to Defend instead of advancing to attack reachable grounded allies.
  Adjust AI target evaluation to seek alternate reachable targets.

- **Wiki race metadata translations and UI text polish (playtest 2026-11-08).** Ensure "Small", "Hit Die",
  "Speed", "Speaks" and attribute abbreviations are properly localized in the races wiki (`locales/pt-br.json`).
  Avoid double hyphens ("--") in dialogue text boxes. Capitalize the first letter in talent descriptions.

---

# Large and later

## Large

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
  assess of it; a beast appears at a 100% assess. Decided 2026-11-04: entries are partial (the assess
  fills a beast in bit by bit). What exists to gate on: the guild's `Bestiary` (`intel.py`: races fought,
  abilities seen, the best read of each authored NPC) and each unit's `known_recipes`; nothing records an item
  seen, so an item's entry needs a new saved set. A recipe's entry shows only for a recipe someone knows; an
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

- **A talent with more than one prerequisite.** The tree already draws the second requirement as a red dotted
  line, but no talent has one yet. When the prerequisites become a list, check that this is how it reads.
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

## 2026-11-08

PT-BR playtest (commit 4dca9e05):
- **UI & layout regressions:** Check font hierarchy and styling on post-fight recap ("who killed whom")
  and roster screen. Ensure "consumables & equipment" header text wrapping looks balanced. Check occasional
  image cache misses on screen transition.

## 2026-11-02

The session's recordings (saves and combat logs) are not in the repo yet; the author sends them when a note
needs a fight rebuilt.

- **Is the two-step charge worth it? (author 2026-11-02, doubt).** Having one charge with two different
  values feels more of a hindrance than interesting. Review the rule against the Aurochs fight (day 112) and
  decide: keep, merge into one value, or drop. Measure with `scripts/combat_pairs.py`.
- **The Snake Dragon dungeon was too easy (author 2026-11-02).** Possibly because the squad had grinded
  before. Check the encounter's level against the squad's on entry in the headless set before changing it.

## 2026-11-01

- **Vocations: difficulty or build? (author 2026-11-01).** Vocations stay and get more investment (author
  2026-11-04). Is playing Survivors objectively worse than Caravan? Either flag it to the player ("risky" and
  the like), or balance them to be equally desirable. Either way the game needs a way to test the vocations' balance (`balance_sim.py`,
  `economy_sim.py`; see *Vocations are far apart* under 2026-10-31).
- **Auto flee button (playtest 2026-11-02).** One button that moves every unit of the side toward the
  exit while it can, instead of ordering each one. Needs the flee rules read first (what blocks a flee,
  who is held) and the AI's flee path reused. End-to-end: web button, `ai/`, tests.
- **Surrender and prisoners (author 2026-11-01, future).** Morale and the rout shipped; a fighter whose morale is
  spent could give up instead of running. Think what a surrender does and tie it to *Prisoners*.

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
  for the races that cast early; Wanderers and Survivors weak. Rework or balance with the vocation probation in
  *Loyalty, the oath...*; each perk should act on a daily loop. **Not validated** (author 2026-10-31: these
  are impressions, not measured). Check them first with `balance_sim.py` / `economy_sim.py` /
  `scripts/economy_report.py`: vocation ranking, and whether Orc (does not fall) and Goliath (carries
  double, no donkey to buy) really are the strongest races. Only then rework.
- **Starting squad is weak.** STR 2 or 3 carries nothing, a bow is too dear, and the start weapon is
  a dagger or a piece of an axe ("at least one real weapon"). The author would take 18 STR, 18 CON and 0
  elsewhere at level 0.
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

- **Tutorial cards are text only and did not help.** He read them, but plain text did not explain the
  mechanics; he learned by playing. Open question: show instead of tell (a small diagram or a
  highlight of the control on the screen), or shorter cards that point at the first action. The combat
  card is *Combat teaches itself* (*Medium*); the other screens wait for its answer.
- **The Reputations tasks only half guide a start.** Found them "almost intuitive", not a clear "how
  to begin". Check whether the first deeds read as a path.
- **Rations are learned the expensive way.** Travel eats rations (once a day) and he found out by
  spending them. The wiki was opened once and never used. Left: a link from the tutorial to the wiki.
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
  Author 2026-10-30: still no idea of how archaeology should work to be interesting; nothing to size
  until that answer exists.
- **The Claim:** let the player build their own farm to stock food.
- **Combat leveling (Lv 1 -> 2):** assist XP or an
  intermediate arena bout wait on future playtests.

---

# Needs more information

- **Catfolk balance and glyph.** The race is in (slots, Catfall, Sylvan, the three talents, Caravan, 11
  portraits). The head glyph (`sly`) is a stand-in: the icon set has no feline head. Its numbers (the +1 DEX/+1 CHA body, the three talents)
  wait for the vocation balance work (*Vocations: difficulty or build?*).

- **Playtest with every routine open (author 2026-11-04).** Every block and place is open to a routine today.
  The playtest decides *Routine unlocks* (in *Large*), whether the editor needs validation marks (today a routine
  that cannot run stops at run time with its reason and *Continue*), and whether switching between groups is
  pleasant. The build goes to the other testers again only after a few more features.

- **Loyalty, the oath and who the members are** — plan: [loyalty.md](loyalty.md) (design talk 2026-10-23, no
  code). The player is the guild; a member is a statblock + named traits + an aspiration; one loyalty bar
  per member; the oath is composed once, by the player; recruiting is one person convincing another;
  occupations are gone and the vocation stays on probation. The plan ends with its open questions.

- **Economy numbers to sign off (open since the sim's first rounds, 2026-10-08).** The sim meets its
  targets ([../economy_sim.md](../economy_sim.md)); these are calls only the author can make, in rough
  order of impact.
  1. *The Games pay too little for their risk? (direction decided 2026-11-01; the author feels it balanced
     on 2026-11-04, so this is a measurement, not a call: drop the item if the numbers agree).* A Games bout
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
     Decided (author 2026-11-04): three separate nodes that may connect. Group size +1: *combat*, T4 or T5
     (recruiting is the strongest thing in the game so far). Crowd penalty -10%: *combat*, T3 or T4. Joint
     pitch: *work*, T2 or T3, after Fixer. Open: whether "group size limit" is `cohesion.py`'s capacity (to be
     replaced by Loyalty, see above).
  2. *Intelligence tree (combat), two talents:* (a) **group leader only: places the whole group** before
     the fight; (b) **places only oneself**. Together they are a ladder (b the early node, a the late one),
     and (a) needs the leader to be on the board. Decided (author 2026-11-01): only inside the start zone;
     the UI is like the flag's placement (a pre-fight setup step, `BattleSession` already has "flag" and
     "trap"), placing the characters one after another in initiative order. (a) works only when the
     leader is on the board (an arena bout picks its fighters, a hunt leaves its guards behind: without
     the leader, no one places the group). `ai/` places its own side at random at first; after a playtest with the talent, the author's placements
     train it. Open: the tier of each.
  3. *Charisma + Wisdom compound:* Demoralize on beasts. The point is the language: a beast has none,
     so `Demoralize._can_provoke` (`actions/combat.py`) never allows it. The talent gives the holder what
     `AbilityDef.demoralize_ignores_language` gives the racial one (offence only), limited to targets
     with no language of their own. The effect on the beast is the same as on a humanoid
     (`Demoralized`: cannot move, lower defenses). Decided (author 2026-11-04): it requires a Charisma (combat) talent and a Wisdom (combat) talent, which
     needs the list of prerequisites (*Ready to do -> Medium*). Open: whether it also needs the holder to be
     able to see the beast for a turn (the existing sight check already does).
  4. *Archery (playtest 2026-11-02):* a combat talent giving +1 damage with a bow; and a second that
     adds a conditional *Brutal* to the blow, possibly "in a straight line" along the 8 directions (the
     shot must travel straight). Decided (author 2026-11-04): the +1 damage comes first and the Brutal one chains after it. "In a straight
     line" is the queen's move: shooter and target aligned on a row, a column or a diagonal. The *Brutal N*
     keyword exists (`keywords.py`). Open: the tiers.

- **Assess grows into an Intelligence combat tree (author 2026-10-31).** Study the foe, and what you
  know grants crit and to-hit: a turn spent investigating before the beating is a real option. Not built
  to the author's liking yet. Sits beside the Intelligence talents in *Talent ideas* above.

- **New body actions: one per natural weapon.** A 2 AP action for `Claws`, `Bite`, `Fangs`, `Hooves` and
  `Horns`: one special action per natural weapon (`natural_weapons.py` is built), like Wrest for `Unarmed`,
  as a trait of that weapon. Open: the action for each, and which of the five knock the foe `Prone` (the
  condition and Takedown exist, `conditions.py`, `actions/combat.py`). Each is end-to-end (rules, web tab,
  AI, tests, tutorial card). Compare with Takedown and Grab in the sim so none dominates.

- **Growing the action bar slowly (author 2026-10-31).** Giving every unit many actions at the start is
  too much friction; new actions have to come in gradually, so a new player is not flooded while the
  complexity builds. Open: which actions come at which level or talent. Decide it after *New body
  actions* (author 2026-11-01): Takedown and the natural and unarmed actions are most of what the bar
  would gate. Takedown and Stand Up are on the bar for everyone today. Ties to *Roster of characters* (*Notes to remember*) and *Levelling is vertical only*.

- **Magic as the vertical progression.** The arc's work is the *Scroll of Invisibility* (*Ready to do ->
  Medium*) and *Magic Arc, later* (*Large*). The schools are
  rival factions but not mutually exclusive for a character; magic comes strictly before Archaeology.
  Open: tier 2+ spells and any reputation penalty for rivalry.

- **Recipes learned by owning the item or a teacher (author 2026-10-31).** A recipe paper
  is studied like a level-0 spell (Apothecary's Antidote errand is the first). Open: where more recipe papers
  come from. Today a recipe comes from a race (Dwarf at level 5), a crafting talent (Apothecary, Smith) or that
  paper, and few exist. The intent: learn by owning an item (take the axe to the smith and study it until you can make it)
  or by being taught. A first form: the Library makes dictionaries, so a leader who speaks only Draconic hires a Lizardfolk and
  writes the dictionary to learn the language. Some recipes come from missions, artefacts from quests; the Kobold learns trap
  recipes and places traps farther. The tester's idea: a research system to discover formulas. Open: teachers (who, what it costs),
  study time, what the Library's dictionary gives, research. Size a first form when the production chain is picked up.

- **Better food: dishes with buffs (after the magic arc).** Food only quells hunger and the Potato does it
  cheapest. The preservation recipes are built (Jerky, Roast Meat, Fruit Compote; no buffs, by design).
  Decided: cooking is an ordinary craft; a premium dish gives a 24 h buff that moves one number (HP, an
  attribute, advantage on a named kind of action...), and only the most recent meal's buff is active.
  Open: the dishes and their buffs, and the cost to the economy sim (`cheapest_food_price` stops being
  the one price of a meal). Survivors's slower rot is priced low until this lands.
  - **A use for Rotten Food (author 2026-11-01).** Today it is worthless (`price=0`) and a keeper bins
    it. Weigh giving it a use, compost at the Farm or a crafting material, when the food patch or the
    farm patch comes up.

- **Holy Symbol source (author 2026-11-01, quest decided 2026-11-04).** No recruit starts with one (only the
  Priest did) and no shelf sells it, while Faith's rite (`rite.py`) consumes it, so the Faith school has no
  way to get it. Not for sale at the Market. Direction: (1) a super rare drop from bandit ambushes; (2) a
  Farmer's quest: his daughter went to the church and has sent no word for a while; an investigation ends
  with the body found on the new node between the church and the country roads, and the Holy Symbol is on
  it. Open: the drop chance, the node, and the investigation's steps (it needs the story thought through). Order
  (author 2026-11-04): after the translation, before the next playtest. Until then the rite cannot start in a
  new game.

- **Does an arena bout cost hours? (author 2026-11-01)** A bout advances the clock only by its rounds
  (6 s each, `campaign.py`), which is about a minute: a squad can chain bouts the same day with no
  meal or rest in between. That is plausible for the fight itself; the open question is whether the
  preparation and the recovery around a bout should be an order (a stint through `MapSession.spend`),
  and whether it matters to the economy (`scripts/economy_report.py`). Decide after the
  playtest shows whether bout chains break anything.

- **Kenku archetype design (author 2026-11-08).** Kenku stats (DEX/WIS/CHA) leave it neither a pure caster
  nor a melee bruiser. Design space: high-initiative ranged archery and Demoralize synergy.

- **Weapon SVG icons audit (author 2026-11-08).** Broadsword, sword and rapier share an icon; axe and hatchet share
  an icon. Check local `gartok/assets/` pool for distinctive alternatives before sourcing external SVGs.
