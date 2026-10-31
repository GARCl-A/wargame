# Vision — what the author says the game is

Intent, not rules. Taken from the author's own words in a playtest talk (2026-10-31, with a friend, Johann)
and written down so it is not lost in a chat. `AGENTS.md` keeps the durable premises the code relies on;
`RULES.md` and `REFERENCE.md` say how the game works today; [plans/backlog.md](plans/backlog.md) holds the work.
Where this file names a direction that is not built, the backlog item (if any) is linked by name.

## What it is

- **Battle Brothers + Wartales + D&D/Pathfinder + the author's spreadsheets.** Made first for the author
  to play the way they want; other players are welcome, not the target of every choice.
- **A guild you manage and a roster of RPG characters, not an army of clones.** The author leans to many
  action-bar entries and each unit a character in its own right, accepting the friction. The trade-off is
  named: eight identical units are fast to play (move, hit, hit), eight complex ones mean hundreds of
  buttons a turn.
- **Everything is open from the day the guild is founded.** Nothing is unlocked by story. What gates a
  thing is money, exploring a place, a reputation, a talent or a race. The author knows this makes levelling
  feel flat (see *Open problems*).

## Directions the author stated

- **Macro management through automation, optional.** The main group is played by hand, down to the last
  detail. The secondary groups run routines: collect wood, buy vials, craft healing potions, put them in
  the guild inventory; or study a spell for two months while away. The player collects when back from the
  expedition. A player who likes clicking can still do 80 clicks a day. The player does **not** run two
  adventures at once: automation is for the world around the expedition. This is why the game has several
  groups; without the automation, the groups feel slow (see the backlog's *Programmable order chains*
  and *Auto battler*). The author worries that it pushes some players away and goes ahead because the game is for
  themselves. The friend's view: well done, it only attracts, since it turns micro into macro.
- **A living economy.** Prices answer to what players do: a guild that cuts wood 24 h a day floods the
  market and the work stops paying; the carpenter buys wood from the lumberjack and iron from the smith, the
  smith buys ore and coal from the mine. How the player enters that chain against the shops is open. Left
  for after the core is solid (backlog: *Production chain*). A friend's idea to fold in: a market stall
  (a licence, then selling your own goods at a better price), so every area allows some interaction.
- **Food that matters, with better food giving more.** A group of ten plus a cart eats eleven meals a day;
  a ten-day territory defence needs ~110 meals while a tavern's stock holds tens (about 15 beers, 10
  meats, 30 potatoes): the supply is meant to be a constraint, not an afterthought. Salted meat and beer are the
  end-game foods (30 and 20 days); the Potato lasts 7 days, fruit 1. Hunting pays through meat and hides
  sold, then potatoes bought. Better dishes should buff (backlog: *Better food*). A hangover for a beer-only
  diet (as in Baldur's Gate 3) was suggested by the friend.
- **Recipes learned by having the thing or a teacher.** Today a recipe comes from a race (Dwarf at level 5)
  or a crafting talent (Apothecary, Smith); few exist. The intent is to learn by owning an item (take the
  axe to the smith and study it until you can make it) or being taught. A first form: the Library
  makes dictionaries, so a leader who speaks only Draconic hires a Lizardfolk and writes the dictionary
  to learn the language. Some recipes come from missions; artefacts come from quests. The Kobold learns trap
  recipes and places traps farther. A research system to discover formulas was the friend's idea.
- **Occupations go; something with soul replaces them.** An occupation only gives a weapon and one item, so it
  does nothing (the friend agreed: "to me it was a nothing"). The author has no replacement yet.
  Backlog: *Remove occupations* and *Loyalty, the oath and who the members are*.
- **Information is found by playing, but not by guessing.** The author wants the player to learn by doing
  the maths ("I worked it out!") and is unsure when that tips into "this makes no sense". Rule of thumb from
  the playtest: the numbers can be discovered, the rules and where to act cannot be hidden (see *Playtest
  lessons*).
- **Recall Knowledge grows into a combat tree.** The INT combat tree: study the foe, and what you know
  grants crit and to-hit. A turn spent investigating before the beating is a real option. Not built to
  the author's liking yet.
- **Growing the action bar slowly.** Giving every unit many actions at the start is too much friction to
  begin with; new actions have to come in gradually (so a new player is not flooded) while the
  complexity builds.
- **Trade-offs on the talent trees.** Group size and recruiting come from Charisma talents that cost a pick
  that would otherwise make a better individual fighter: a big guild or a strong fighter, not both.
- **Group limits.** A group's size is capped by its leader (level plus Charisma modifier, per the author's
  wiki; the code is `BASE_CAPACITY` 3 + CHA mod + half the racial level, so check the wiki). The number of
  groups is capped by the guild's reputation. Recruiting carries a crowd penalty (-1 per member against an
  opposed Charisma roll), which is what keeps the roster small, since 8 characters is already a lot. A
  group of 8 seen at end game; 13 groups possible, 2 held.

## Where it goes

- **Release.** Itch.io first, as an indie demo (pay what you want), while it grows; the Steam release when
  there are 20+ hours of play ($100 fee; the generative-AI content flag must be ticked). Mobile does not fit:
  the UI is heavy, though it is a web app in the browser. A Kickstarter to pay a real artist was suggested.
- **AI content, stated plainly.** Generative AI is only the character portraits and a few tree sprites. The
  rest is drawn by code (the axe icon is an SVG written in code). Say so on the store page.
- **Co-op / multiplayer on a shared map** (each band a player) is a daydream; the friend does not see it fitting.
  No plan.
- **References to play or compare:** Battle Brothers, Wartales, Mount & Blade, RimWorld (several groups feel
  slow), Pathfinder (delay turn), Siralim Ultimate (programmable fights; the author put 40 hours into it in a week).

## Open problems the author named

- **Levelling lacks a thrill.** Progression is vertical (doing the same better) and nothing new opens up
  (nothing new to *do*). Not wanted: only bigger numbers or a pile of skills. Wanted: a new thing to do per
  level (a bard that can play at court or recruit; the Charisma line that earns money and recruits is the
  model). Magic is the main hope, but it arrives late (reputation with the schools, unless the start is a Gnome or
  Kobold, the races that begin as casters).
- **Combat gets dull over time** (attack, defend, weapon special) and slow with many characters. Magic and
  more weapon-driven mechanics should relieve it; the friend suggested a way to link characters or make
  them act together.
- **Vocations are unbalanced.** Delvers and Caravan are far ahead; Warband works because Orc and Goliath
  are the strongest races; Scholars matters through the races that start in magic; Wilds and Marsh are weak. The
  strongest races are Orc (does not fall) and Goliath (carries double: no donkey to buy at the start).
  The player cannot know this when starting, and the author is unsure whether that is fine.
- **Hunting is not worth it** against buying food. Badly balanced.
- **The Automaton** should go down *broken* and need a repair, not come back whole by itself.

## Playtest lessons (the friend, 2026-10-31, about 2 h)

What worked: the character progression, combat, and the pull of "always something to go after" (the
exclamation marks on the map); two musicians playing while the rest worked was the strategy he liked; it
compares with, or beats, Wartales / Battle Brothers / Mount & Blade for fun and is easy to play in short
sessions. He stopped because of a bug (see the backlog's split-clock bug), because he had played a lot, not
because he was bored.

What did not reach him, in one line: **the game's rules are in places the player does not look.** The wiki
is not read (the author says nobody reads one, including them); the menu was not read (Delay existed,
on key 9, and he asked for it); the commission tokens were not understood; the race and vocation screens
did not tell what a pick gives; a node does not say "this is too hard", so he skipped the arena, which
is easier than the wolves that had just killed him. Put the information where the decision is made.
