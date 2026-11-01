# Backlog — everything still open

The one place for open work. A task here is a few lines; when it needs more, it **points to its plan** in
`docs/plans/` ([loyalty.md](loyalty.md), [campaign_ai_roadmap.md](campaign_ai_roadmap.md)) or to the doc
that owns the subject: the test suite [../../tests/README.md](../../tests/README.md), the economy sim
[../economy_sim.md](../economy_sim.md), the web client [../web_ui/web_client.md](../web_ui/web_client.md).
What is already built is in the code, its tests and the git log.

Sizes are estimates; claims about what the code already has were checked on 2026-10-22 (the *Ready to do*
items again on 2026-10-30, the plan pointers on 2026-11-01). When an item is done, delete it here and, if it
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
- The *Small* items below, in order: the version, the exe, the two bugs the friend hit.

After the playtest (it answers them, or they are content past it): weapon actions tuning, *Tune the
specialised shops*, Magic Arc tuning, the production chain, cooking with meal buffs, the campaign AI,
Prisoners, Archaeology at Ancient Ruins.

---

# Ready to do

Order inside a size is the order to pick them up: first what blocks the friends' playtest, then bugs, then
the rest.

## Small

- **Complete the icons' author list (decided 2026-11-01).** The Credits screen (title menu) reads its
  authors off `gartok/assets/icons/LICENSE.txt`, which is partial. Before shipping, complete that list from
  game-icons.net for the icons actually used (one author per icon on the site); the screen picks the
  new names up with no code change.

- **Playtest build for friends (checked 2026-10-30).** `build_exe.bat` (PyInstaller `--onefile`, stdlib
  only) builds a `GARTOK.exe` that opens and serves the client; it is only the way to hand the game to
  playtesters, not the official release. Left: play a whole session in the exe, put `build_exe.bat` in English,
  rebuild `dist/GARTOK.exe` (still the 2026-10-10 pygame one). Do it after the version item so the exe
  carries it.

- **Bug: a fighter that cannot move and shows no reason (playtest 2026-10-30).** Ancient Ruins, day 75,
  against the spiders, round XIV: Irekdralob could not move and nothing in the action bar said why.
  Rebuild the fight from its combat-log JSONL (`CombatLog`; the save is the author's), find the
  condition or rule that blocked the move (web, a spider's web, a stuck state, no free cell, AP), then fix
  it and make the action bar always name the blocker of a disabled Move (the tooltip the other disabled
  actions have). Test: the repro as a fixed board, and a disabled Move always carries a reason.

- **Show items lying on a cell a character stands on.** An item dropped or thrown onto a cell with a
  unit on it (a weapon that lands under a surrounded foe, a drop under your own fighter) is hidden by the
  token. Improve how the web board shows it (a corner badge on the token, or a marker in the cell ring)
  and how it reads in the inspect panel, so the player knows it is there and can Pick it up.

- **Draft: say what a commission does (playtest 2026-10-31).** The tester did not know the COMMISSION tokens
  force a reroll until the card has the asked tag (+2 on that attribute) and took the first cards he saw,
  one with STR 2. Put a one-line explanation at the button ("3 tokens: replace a card by one with the tag you
  pick") and the token count where the cards are. Web only (`screens/draft/draft.js`).

- **Prisoners: bail is paid only if the recruit succeeds, plus optional extra bail (playtest 2026-10-30,
  decided).** Today `tavern.Prison._bail` charges `recruit.bail_cost` before the pitch and a failed pitch
  keeps the money ("walks away free"). Change: the pitch is rolled first with the bail's +2
  (`BAIL_BONUS`) promised, and the copper is taken only on success (the price is checked up front, so a
  pitch is refused when the group cannot cover it). Extra bail: before the pitch the player may raise the
  offer in steps (+50% of `bail_cost` each, at most 3 steps; +1 to the contest per step, on top of the
  +2); the extra is paid only on success too. The tab shows the offer, the bonus and the total due. The
  bar after a failed pitch (`prison_bar`) stays. Tests: failure costs nothing, success takes bail + extra
  (copper first, change from gold), steps add to the roll, an unaffordable step is disabled; `ai/` does
  not use the prison. Re-run `scripts/economy_report.py` (recruiting cost). Rewrite the sentences that
  say a failed pitch keeps the bail: `RULES.md` (*Prison*, "Lose the pitch and the bail is gone too")
  and the prison's tutorial card in `locales/en.json` ("they walk free with your money").

- **Gathering teaches at the node's level and needs the tool (playtest 2026-10-30, decided).**
  `bank_haul` banks work XP at `economy.work_level(u, node_id)` (0 or 1: the tool), the same as a wage
  shift. Change: a gathering shift banks at activity level 3 at the Lumber Yard and 4 at the Mine
  (`progression.work_xp_hours` already pays `(activity - level + 1)` per hour and nothing once outgrown),
  so gathering is the way past the wage's level 1. And gathering needs the node's tool (`Axe` / `Pick`,
  `economy.WORK_TOOLS`) on the worker: a worker without it takes no roll and no XP, and the crew card
  says who is missing it (the licence stays the guild's gate). Check `gather.py`'s docstring, the shift's
  preview (`work_desk`) and the tutorial card for the new rule. Tests: XP at 3/4, no tool means no haul,
  a mixed crew. Re-run `scripts/economy_report.py` (a crew now needs tools).

- **Hit sounds swap (`assets/sounds/`).** Hit sounds do not fit the game (the UI sounds are fine);
  swap the Kenney variants in `assets/sounds/`.

- **Map blocks: drop pygame's layout hints.** `gap_before` and `height` in `map_view.py`'s blocks are
  ignored by the web; the Editor does not count (author 2026-10-30). Delete them.

- **Can Rotten Food be sold? (author 2026-11-01).** Rotten Food has `price=2`, so a counter pays $1 for it
  (the floor). Decide whether spoiled food should sell at all (a tanner or a farm that takes it as
  compost, say) or be refused like trash, and then give the Snake Dragon Corpse (`price=1`) the same rule.

- **REFERENCE.md: the plain Dictionary breaks the Dictionary row.** `python -m gartok.reference` now groups
  `Dictionary` with the `Dictionary of <language>` rows and prints `Dictionary of (, Ankarin, ...)`, a stray
  comma. Keep the plain one out of the group (or give it its own row).

- **Bring the author's own skills into the repo (decided 2026-11-01).** Only the author can do it: the
  skills on their machine (`~/.claude/skills/`) are out of an agent's reach. For each one the repo needs,
  copy it into `.claude/skills/<name>/SKILL.md`, then check it against the owner list in
  `AGENTS.md`: no rule an owner doc already holds, no pointer to a file that is
  gone, one line in `AGENTS.md` only if an agent would break something without it. Nothing in the repo
  depends on them being there.

## Medium

- **A hunt out on the clock must survive a save (decided 2026-11-01).** Since the one-clock change a hunt
  stretch is a `hunting` order the map runs while the player plays the other bands, so a save is taken
  mid-hunt all the time (every map landing autosaves). Today `persist.group_from_dict` drops that order:
  on load the party is back idle and loses the hours spent and the haul so far, which makes no sense now
  that the hunt is just another order. Save it: the `hunt.HuntState` (party and guard uids, hours left and
  hunted, `yield_hours`, finds, fights, target, multipliers, Biwolf) and what the stretch rolled (an ambush
  or not, and whose: Biwolf, Wilds pack, the ox) go into the order or the group, and on load
  `MapSession.hunts` is rebuilt from them so the stretch comes due and `HuntSession.arrive` opens as usual.
  The ambush pack itself is rolled at arrival, so it needs no saving. Change the AGENTS.md / RULES.md rule
  "a battle or hunt in progress is never saved" to "a battle in progress is never saved" and drop the
  `hunting` case from `persist` and its test in `tests/test_one_clock.py`. Tests: save and load mid-stretch
  keeps the clock, the party, the yield and the ambush; a save with the hunt screen open (setup,
  interlude) still refuses or keeps working as it does now.

- **2 AP actions for `Claws`, `Bite`, `Fangs`, `Hooves` and `Horns` (future, after *Natural weapons*).** One special action
  per natural weapon, like Wrest for `Unarmed`, as a trait of that weapon. Design call open for each.
  Medium, not Small: a new action is end-to-end (rules, web tab, AI, tests, tutorial card).

- **Takedown as its own action (like Push and Grab).** Knock a foe prone: needs a `prone` condition (none
  exists) and a roll; sized when designed.

- **An ambush needs a pack with a chance to win (playtest 2026-10-30, decided).** On day 105 a guild of
  eight stopped for two wolves. The premise: an ambush only exists if the pack would plausibly attack
  that group. Where a pack is rolled against a group (the road, `world.ROAD_AMBUSH_CHANCE`; the work
  nodes, `gather.ambushed` / `ambush_pack`; the Wilds hunt), compare the rolled pack with the group
  before the fight starts, with one function in `encounters.py` (the pack's strength against the group's:
  levels, count and HP, the same measure `combat_pairs.py` / the sim use for a win chance) and a
  threshold. Below it the pack does not attack: the roll is spent, the log says so ("Two wolves watch the
  column pass and keep to the trees"), no board, the group keeps its clock. Only the odds are
  tested, not a free pass: the pack is re-rolled once at a size that fits the group (`GATHER_COUNT_WEIGHTS`
  scaled by the group's size) before giving up, so a big guild still meets big packs. Threshold
  (start at ~15% win chance for the pack, tune with `sim_test.py`), and whether the hunt shares it, are
  open until the first run. The Wilds hunt shares the check (author 2026-10-31). Not for forced/story fights (`Group.pending`, quests, the Biwolf escort).
  Tests: eight L3 against two L0 wolves never opens a fight, a lone L0 against the same wolves does, the
  re-roll scales with size, forced fights are untouched, the `ai/` side is unaffected (the foe only
  decides inside a battle).

- **Audit: which fights are ambushes and which are not (author 2026-10-31).** Do it before or together
  with *An ambush needs a pack with a chance to win*, because the check only belongs to the ambushes.
  List every place the game starts a fight (road legs, gather shifts, Wilds hunt, supply run,
  Ledger Hold, wagon watch, node fights such as the Ruins and the Serpent's Nest, the arena, forced
  events, quests) in a table in `RULES.md` with its kind: **ambush** (the pack comes to the group; the
  win-chance check applies), **sought** (the group goes in: the player chose the risk, no check) or
  **forced** (a quest or story fight). Each row names who starts it and what the group can do (flee,
  pay, hide). Put the kind on the code that rolls it (one field, not a comment) so the check reads it.
  Output: the table, the field, a test that every fight source has a kind. Expect to find fights that
  should change kind (a Ruins visit that behaves like an ambush); each is a short question for the author.

- **Rules as keywords (playtest 2026-10-30).** A rule repeated in prose ("the blow lands twice over (a
  second roll of the weapon's damage)" in `weapon_traits.py`, `actions/weapon_actions.py`,
  `wiki_rules.py`) becomes one keyword with its own wiki entry, and the descriptions say only the
  keyword: shorter text, and the rules become a set of words that always mean the same thing. Start with
  *Double blow* (the name is open) and look for the next ones (Flanked, Prone, the conditions already
  are). A keyword's entry goes in `wiki_terms.terms()` and the wiki already links it (`wiki_terms.of_item`) and shows it on hover; `ai/` and the numbers do not change.

- **What only pygame had, in the browser (found 2026-10-28, when the pygame campaign was cut).** The broken
  wagon left behind, the hand-over card between groups, the vault read from the guild screen and the auto-win
  are done (2026-10-30). Left: the tests the cut lost: everyone
  jailed, no save mid-battle, two due screens in turn, the REST row, a trip
  cancelled. The old screens are in git before the cut.

- **Test suite: the last luck-dependent tests (found 2026-10-28).** The suite is seeded per test and
  runs under `pytest-xdist` (how it works: [../../tests/README.md](../../tests/README.md)); four tests
  still lean on luck and only their seed holds them green, so a change to `Unit` generation may turn one
  red. Rebuild each on `standard_unit`:
  `test_combat_talents.py::test_gruesome_takedown_demoralizes_nearest_foe_on_down`,
  `test_objectives.py::test_the_medic_marks_its_objective`,
  `test_poison.py::test_a_bite_that_hurts_forces_a_save_and_a_failure_poisons`,
  `test_web_hub.py::test_a_trust_order_opens_the_bankers_jobs_alone`. The rest of the suite moves by
  touch: a file whose tests are edited moves its `Unit(...)` rolls to `standard_unit`.

- **Remove occupations (decided 2026-10-23). Close this soon, and until then do not maintain the idea.**
  Occupations are going, so no new code, label, icon, test or sim ranking may lean on them (author
  2026-10-30): every new screen that prints "Race Occupation" raises the cost of this removal. It is spread
  over five core modules plus the labels below. The first step of *Needs more information -> Loyalty,
  the oath and who the members are*: an occupation is only a preset of the starting weapon and item
  (`unit.py`), so the starting kit is rolled at random and nothing is written on the character. Touches
  `data.OCCUPATIONS`, `Unit` (roll, save, `unit_edit`), `artwork.OCCUPATION_ICON` and `role_for` (the
  member's icon needs another source: the race's, or the weapon's), every label that prints
  "Race Occupation" (tavern, guild, squad, medic, initiation, crafting, watch, `dialogue.py`, the web
  board and talk), `aftermath.Memorial` and the memorial screen, `recorder.py`, `npc_lib` / `npcs/*.json`,
  `outfit.py` (level 0 keeps the occupation's kit), `reference.py` / REFERENCE.md, the sims' rankings
  (`economy_guild.py`, `balance_sim.py`, `unit_compare.py`) and their tests. Saves of the old shape stop
  loading unless the key gets a default. The occupation-unique items lose their reason to exist: drop
  them from the start, they come back if a system ever needs them. Check the economy sim afterwards:
  a starting Axe or Pickaxe was a work tool.
  `tests/helpers.standard_unit` drops its `set_occupation("Guide")` and must still hand back a Quarterstaff
  and an empty pack.

- **Magic Arc follow-ups (future drops, quests & tuning).**
  1. *Scroll of Invisibility:* Library quest unlocked at max library reputation + caster initiated in magic (direction 2026-10-19).
  2. *Blood's fourth mission* (robbed dragon strikes back): the dragon attacks node-by-node seeking its eggs, closest first, with consequences if nodes are destroyed; postponed to after magic arc core content (author 2026-10-19).
  3. *Tuning after playtests:* balance numbers for Battlefield, Snake Dragon, Ogre Wildfire, Necromancer at the Front, and Dragon's Clutch once further campaign runs reach them.

- **The sim's long game (found 2026-10-21).** `economy_guild.Balanced` plays the author's line: 92% of guilds
  meet the day-30 milestone, none die before it. Past it (the Pit, a recruit, the Wilds hunt as the income) 18 of
  40 die by day 60, all hunting: a lost lethal fight takes the whole group. The sim gives the player `SKILL = 0.5`
  of the AI's losses in every fight; the author's 87 hunts measure 0.84 (arena 0.44, road ambushes ~0,
  `combat_pairs.py`). Decided 2026-10-21: keep 0.5 and leave the long game for later (the sim: [../economy_sim.md](../economy_sim.md)).

---

# Large and later

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
- **Prisoners.** The bail rule is its own item in *Ready to do*. Decided 2026-10-19: (1) sell to City Prison via interactive tab/dialogue for bounty based on
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
  a locked-entry stub or no entry at all. Open: what counts as "known" per chapter, and whether the
  wiki says that something is still hidden. The complete catalog is `REFERENCE.md`, a design doc for
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
- **Co-op / multiplayer on a shared map (author 2026-10-31).** Each band a player. A daydream; the
  tester does not see it fitting. No plan.

---

# Playtest notes

## 2026-10-31

A friend's (Johann) first session (about 2 h, no tutorial from the author). The two bugs, the Delay label, the
draft's commission text and the export are in *Ready to do* (Small). The author's stated intent from the
same talk is spread over *To discuss and reflect on*, *Notes to remember*, *Needs more information* and the
items it touches. Raw feedback, not yet sized:

- **What worked (do not "fix" it).** The character progression, combat, and the pull of "always something
  to go after" (the exclamation marks on the map). Two musicians playing while the rest worked was the
  strategy he liked (hence the split-clock bug is the worst one). He compares it with, or above, Wartales /
  Battle Brothers / Mount & Blade for fun, and finds it easy to play in short sessions. He stopped because
  of that bug and because he had played a lot, not because he was bored.

- **Theme: the rules sit where the player does not look.** The wiki, the menu and the tutorial text were
  not read; the player learned by doing, and paid for it (rations, the draft, Delay). A fix per case is
  small; the pattern is to show the rule where the decision is made (a pick, a price, a button).
- **No difficulty signal.** He avoided the arena ("if wolves kill me, the arena will") and the first bout
  is easier than the wolves (3 level-0 fighters against 2 to 6 wolves of level 1 to 4). Ideas: a danger
  hint on a node or fight before entering (a level range, "easy / hard for this group"); it ties to
  *An ambush needs a pack with a chance to win* (wolves killed an early squad).
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
  elsewhere at level 0. The occupation removal rolls the start kit anew: give it a real weapon then.
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
- **The group limit was not visible.** He did not know how many a group holds or that recruiting gets harder
  with every member (-1 per member). Show the capacity and the crowd penalty at the recruit pitch.
  The author's wiki said "level + CHA mod" for the capacity: the wiki is wrong, the code (`BASE_CAPACITY`
  3 + CHA mod + half the racial level) is the intent (author 2026-10-31). Fix the wiki text.
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
- **Programmable order chains for a group**, e.g. gather Lumber at the Yard -> sell Lumber and
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

- **Loyalty, the oath and who the members are** — plan: [loyalty.md](loyalty.md) (design talk 2026-10-23, no
  code). The player is the guild; a member is a statblock + named traits + an aspiration; one loyalty bar
  per member; the oath is composed once, by the player; recruiting is one person convincing another;
  occupations go and the vocation stays on probation. First concrete step: *Remove occupations* in *Ready
  to do*. The plan ends with its open questions.

- **Economy numbers to sign off (open since the sim's first rounds, 2026-10-08).** The sim meets its
  targets ([../economy_sim.md](../economy_sim.md)); these are calls only the author can make, in rough
  order of impact:
  1. *The Medic's price.* As built it is $16 an HP against $1.3 an HP for a rest, so only a rich squad uses
     it: keep it a late-game luxury, or price it at the rest it saves?
  2. *Upkeep.* A house costs a lumberjack's whole wage and a Donkey a third more. Intended (assets need an
     adventuring income), or should the first assets be reachable on day labour?
  3. *The Games' stake.* $30 a fighter is more than a lumber squad keeps in a week, so the ladder is
     capital-gated: a climb for a guild that has done well, or should the stake come down?
  4. *How lethal the Wilds should be.* A level-3 squad that does not win nearly every fight cannot make a
     living there, and the Old Road's ambush (20% a pass, `world.ROAD_AMBUSH_CHANCE`) fires on every walk.
     Ties to *An ambush needs a pack with a chance to win*.
  5. *How much a crafting specialist may earn.* The shelves aim at 2-3x a lumberjack; the author's note says
     crafting is for saving money and reaching what cannot be bought, not a business. Ties to *Tune the
     specialised shops*.
  6. *The reference late-game scenario* (level 3 with $250) is a guess at "a guild a week in".
  7. The Claim's numbers predate the `hold` job fix: re-measure when a sim policy goes for the Claim.

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
     rolls of `d20+3`. A failure spends the week's attempt (`recruit.bar`) of everyone involved. Open:
     does one roll above the target's resolve win, or must all of them (proposal: the best roll counts, the
     talent is a way to try more than once); who becomes `recruited_by` (the holder; the earlier idea
     was the highest Charisma); whether "could recruit" counts `slots_free` and the shared language;
     three nodes or one chain, which tier; and whether "group size limit" is `cohesion.py`'s capacity
     (to be replaced by Loyalty, see above).
  2. *Intelligence tree (combat), two talents:* (a) **group leader only: places the whole group** before
     the fight; (b) **places only oneself**. Together they are a ladder (b the early node, a the late one),
     and (a) needs the leader to be on the board. Open: the placement zone (the start zone only), the
     UI on the board, an undo, what happens to a group whose leader is absent, and how `ai/` places its
     own side (the premise "the AI knows the mechanic" applies, even if it only keeps today's random
     start).
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

- **Growing the action bar slowly (author 2026-10-31).** Giving every unit many actions at the start is
  too much friction; new actions have to come in gradually, so a new player is not flooded while the
  complexity builds. Open: which actions come at which level or talent. Ties to *Roster of characters*
  (*Notes to remember*) and *Levelling is vertical only*.

- **Magic as the vertical progression.** The arc's work is in *Ready to do -> Medium* (*Magic Arc follow-ups*). The schools are
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
