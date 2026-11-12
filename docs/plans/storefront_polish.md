# Storefront polish: what the real screenshots show

Plan for fixing the visual defects found when the game was photographed for a store page (2026-11-12,
version 0.1.9). Written so an agent can build it without the review that produced it. Read `AGENTS.md`
first, then `docs/web_ui/web_client.md`.

The evidence is in [../photos/12112026/](../photos/12112026/): 25 screenshots at 1920x1080 from a late-game
save and from combat-lab fights, each judged in that folder's `README.md`. File names below are from there.

## Why

The map, the routines editor, the guild screen and an open-field fight already look like a finished game.
A store page and a trailer are made of those frames, so a clipped label or a broken fog in them costs more
than it does in play. Nothing here changes a rule.

## Packages

Independent, one commit each, smallest first. Stop after any of them.

| # | Package | Size | Needs the author |
|---|---|---|---|
| A | The unit panel overflows at low hit points | Small | no |
| B | The battle title is cut | Small | no |
| C | A band's pawn covers a place's name on the map | Small | no |
| D | Fog of war in a room full of pillars | Medium | yes, picks the look |
| E | A blow moves the token | Medium | no |
| F | Music | Small code | yes, picks the tracks |
| G | Small text faults the photo review found | Small | no |

### A. The unit panel overflows at low hit points

Seen in `battle_open_zoom.png` (Imob, 9 of 9 hit points): the label "HIT POINTS · 9/9" breaks into three
lines, the blood drops wrap to a second row and leave their box, and the weapon line under the stats is
pushed down until the bottom of the screen cuts it. In `battle_dungeon.png` (24 hit points, the bar) the
same panel is fine, so it is one fault, not three.

Cause, in `gartok/web/client/screens/battle/battle.css`: `.stat.hp` is 140px wide, its label is 9px Cinzel
with `.2em` spacing and may wrap, and `.drops` is capped at 112px, so ten drops of 10px plus gaps do not fit
one row. `battle.js` draws drops for `hp_max <= 10` and the bar above that.

Do: the label on one line and ten drops on one row inside the box; the panel's height must not depend on
which of the two is drawn. Check it with a unit of 1, 9, 10 and 11 maximum hit points, in `en` and `pt-br`
(the `pt-br` label is longer), by screenshot at 1920x1080.

### B. The battle title is cut

Seen in `battle_pit.png`: "CHALLENGE THE CHAMP…". `.cartouche` is 420px and `.place` is one line with an
ellipsis; the initiative row starts at 450px, so the title cannot grow.

Do: the title always reads whole. Fit the font to the width (the longest fight name in each locale is the
case to test), or let it take two lines; do not shorten the names in `locales/`. List the fight titles from
the code and check each at 1920x1080 in both languages.

### C. A band's pawn covers a place's name on the map

Seen in `map.png`: "Lumber Yard" reads "Lumi" and "The Apothecary" reads "thecary", each under a band's
portrait.

Cause: `MapSheet.labelSides()` (`screens/map/sheet.js`) picks each name's side so it misses the node marks
and the names already placed, but it does not know where the pawns are. `drawPlaces()` (`map.js`) then puts
the pawns at `bandPoint(g)`, spread 46px apart when several stand on one node.

Do: give `labelSides` the pawns' boxes as obstacles (the same boxes `drawPlaces` computes), so a name moves
to a free side. A band on the road moves every tick; the names must not jump while it walks, so only pawns
standing on a node count. Check with one, two and three bands on the same node.

### D. Fog of war in a room full of pillars

Seen in `battle_pit.png`, `battle_pit_campaign.png` and `battle_scrapper.png`: the arena reads as a
patchwork of pale, orange and black squares. Milder in `battle_dungeon.png`, where the remembered rooms are
the brightest thing on the screen and pull the eye away from the fight.

This is the approved look meeting a case it was not drawn for, not a bug. The fog was approved on
2026-10-30 (`docs/web_ui/references/battle_mockup/fog_b.png`): never seen is the dark table, seen before is
a pale paper survey, in sight is the real floor. `board.js` does exactly that: `memory()` washes the floor
with `brightness(1.55) contrast(.4)`, and `fogAndLight()` multiplies the light over the cells in sight. In a
corridor that gives large calm areas. In the Pit, pillars cut each fighter's sight into single cells, so
the three states alternate cell by cell, and at night the pale survey is brighter than the torch-lit sand.
The two comments in `board.js` also disagree: one says the survey is "sunk below the lit floor", the other
that it is pale and the lit floor sits mid.

Do, in this order:

1. **Variants for the author, on the real Pit state.** Three images at 1920x1080 of the same moment
   (`python -m gartok.web --fight champion --seed 2`, a few turns in), saved in
   `docs/web_ui/references/battle_mockup/`: (1) today; (2) the survey sunk below the lit floor, as the first
   comment says, so light is always the brightest thing; (3) (2) plus the never-seen cells *inside* a room
   the side stands in drawn as the survey's blank paper instead of the black table, so a room is one shape.
   The author picks; nothing else is built before that.
2. **Build the pick** in `board.js` and make the two comments say the same thing. Update the *Fog of war*
   line in `docs/web_ui/web_client.md` and the mockup table if the look changed.
3. **Not a client matter, ask before touching:** whether an arena bout is fully known from the start (the
   crowd's light, a place both sides walked into). That is a rule (`AGENTS.md`, *Vision is per-character*),
   so it is the author's call and is listed here only as a question.

### E. A blow moves the token

The board already answers a blow with a floating number, a miss or critical word, a critical banner, the
action's name over the actor and a dashed arc for a shot (`playEvents` and `missile` in `battle.js`, fed by
`st.fx`, `st.cues` and `st.acts`; tests in `tests/test_battle_fx.py`). What a five-second clip still lacks
is motion in the tokens themselves: nothing moves when a sword lands and nothing happens when a fighter
falls.

Do, client only, from the events the server already sends:

- The actor's token lunges a third of a cell toward the target and returns (melee acts: an act with a
  target and no `aim`).
- The target's token is knocked back a few pixels and flashes on a hit; a critical shakes the board once.
- A fighter that drops (dying, dead, knocked out) tips over or fades to its fallen state instead of
  switching in one frame.

All of it is skipped under `prefers-reduced-motion` (`board.js` already reads it as `STILL`). No new sound
here: the cues are their own backlog item (*UI sound: the missing cues*). If an event the client needs is
not sent (which unit dropped), add it to the state the combat log already produces, with a test beside the
others.

### F. Music

The game has 16 sound files and no music; a trailer cannot be cut without it, and the title and the map are
silent. The author picks the tracks (same rule as the sound cues: a licence that allows commercial use,
recorded in `assets/sounds/LICENSE.txt`). Wanted first: one theme for the title and the map, one for a
fight. Code: a looping track per screen family in the shell's `Sound`, its own volume setting apart from
the effects, a fade between the two. A tutorial card is not needed; the settings screen gets the slider.

### G. Small text faults the photo review found

Two are confirmed in the code:

- **A raw key in the shop's deal strip** ("TRADE.BENT.1" in the Smithy's and the Farm's shop photos):
  `web/shop_tab.py` sends `trade.BENT_WORDS[dist].capitalize()`, the key itself, where `trade.py` translates
  it with `i18n.t`. Translate it; add the case to the shop tab's test.
- **A doubled separator in the battle's race line** ("Goblin · · Neutral and Good", every battle shot): the
  literal `· ·` in `screens/battle/battle.js` (the unit panel and the foe card), left from a field that used
  to sit between race and alignment. The draft cards and the charter end the race with a dangling "·" for
  the same reason: find what was removed and close the gap in each.

The rest were seen in the photos and not traced; check each on the screen before changing anything:

- Clipped text on cards and lists: the last line of a draft card, the CHA value at the edge of the draft's
  squad list, the race lines under the charter's signatures, item and shopper names cut with "…" in the shop
  and the farm, the shop's last shelf row and last pack row, the last entries of the wiki's first column.
- The chronicle's first visible line is cut in half at the top of its panel (battle shots).
- A name label on the board hidden under a neighbouring token (`battle_dungeon.png`, `battle_pit_campaign.png`).
- The top row of tokens cropped by the board's paper edge when zoomed (`battle_open_zoom.png`).
- In the wiki, an item name that starts with a digit reads wrong in the display font ("1kg Coal" looks like
  "Ikg Coal").
- The dialogue's quote opens with a closing quotation mark (the dialogue photo).
- The bands tab's cart reads "CARGO 4 / 0 KG".

## Not fixes: how to take the next set of photos

- **Names.** The guild, the bands and the routines in a store shot carry presentable names; the ones in
  this set are the author's own play ("2TH BAND", "Compra batata").
- **Empty states are not shots.** The forge with no recipe known ([photo](../photos/12112026/forge_empty.png)) and the arena with nobody
  picked ([photo](../photos/12112026/arena.png)) are
  correct screens in a state with nothing to show. Photograph the forge with a crafter and a batch under
  way, the arena with the fighters chosen and the stake set.
- **Zoom the board.** `battle_open_zoom.png` sells and `battle_open.png` does not: the same fight, closer.
- **Missing from the set:** the memorial (nobody died in the run) and a forced talk with its roll.
- **The red wax "!"** on a node is the game telling the player to look there. It stays.

## When it is done

Retake the affected shots with the same save and seeds into a new dated folder under `docs/photos/` and
delete this plan's entry from the backlog.
