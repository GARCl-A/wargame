# Economy sim v2 — design, status and open questions

Replaces `scripts/economy_sim.py` (one character, an invented town, no risk), now deleted.
**Everything in this plan is built.** The one thing it measures is whether the guild economy
holds together: does a guild sustain itself, and is the risk x time x reward of each activity
right? **XP is part of the economy** — a level is worth money — so every activity is measured in
copper *and* in XP.

Written 2026-10-08, extended the same day after the first round of answers (the Medic, the
Games, the Claim, the racial level, the tavern; see [Answers received](#answers-received)).
The arc closes here: the next step is the play recorder (backlog), three 30-day runs of your own
play, and a `human` policy built from them. Until then every policy is my guess at how a person plays.
Nothing here is committed yet. The last three sections are the ones to read first when
validating the work: [Decisions made without asking](#decisions-made-without-asking),
[Answers received](#answers-received) and
[Questions and decisions to validate](#questions-and-decisions-to-validate).

## The tools

| Script | What it does | Run |
|---|---|---|
| `scripts/economy_report.py` | one report in this plan's order: verdicts, exploits, activities, sustain, ranking; writes `sim_results/economy-report-*.txt`; exit 1 if a verdict fails | `python scripts/economy_report.py [--quick]` |
| `scripts/economy_activities.py` | **layer 1**: what each activity pays a squad per day in copper and XP, risk, days to the next level, the floor check; the Pit and the Games; the tavern against the yard | `--level 0\|3 --skills 0.8,0.95 [--medic]` |
| `scripts/economy_guild.py` | **layer 2**: a whole guild lives 7 and 30 days under a policy on the real engine; sustain curve, milestone, ranking, restock sweep, upkeep, the Games ladder, the Wilds claim, the Medic | `--policies ... --skill 0.8 [--curve] [--ranking] [--medic] [--level 3 --capital 250]` |
| `scripts/economy_exploits.py` | the exploit detector: loops, barriers, dominance, route, conservation fuzz | `--fuzz 200` |
| `tests/test_economy_sim.py`, `test_economy_exploits.py`, `test_craft_level.py` | pytest on seeded short runs; the detector tests break the rules on purpose to prove each scan can fail | `python -m pytest tests/` |

`AGENTS.md` now says to re-run `economy_guild.py`, `economy_activities.py` and
`economy_exploits.py` (or just `economy_report.py`) after touching wages, purses, prices or loot.

## Roles: each activity has a job

Judge an activity against its own job, at the levels it is meant for, not against one money bar.

| Activity | Role | Level band | What "good" means |
|---|---|---|---|
| Lumber yard | floor | 0-1 | A squad eats and keeps >= $1 a day, always available |
| Arena: Scrapper | leveling | 0 | Takes a squad to combat level 1 cheaply. **Not a money job**: the purse is fine as is |
| Arena: Brawl, Capture the Flag (the Games) | leveling | 2-5 | The ladder after the Scrapper: non-lethal, XP-rich, costs more in stake than it pays. Not judged for money |
| Arena: Challenge the Champion, The Ribbit Brothers | one-off | 1-4, 3-6 | A gate (it opens the Games) and a capstone (six a side). Shown, not judged |
| Tavern show | side income | 0-1 | Pays about what lumber does for whoever owns the instrument |
| Wilds hunt | income + food + XP | 2-4 | Out-earns the floor by a wide margin; the risk is the price |

A level-0 squad in the Wilds normally loses and that is intended; the Wilds are judged at
level 2-3 only. The Wilds give little XP on purpose: the arena and the dungeon are the way up
(the dungeon is not in the sim: you said it need not be; the Games are).

## Targets (pass/fail) and where they stand

| Target | Today |
|---|---|
| 1. **Floor.** Lumber at level 0: eat and keep >= $1 per member per day | **PASS** (+$1.00) |
| 2. **Wilds beat the floor** at level 2-3 for a player who wins most fights | **PASS** (about +$5 for the AI, +$8-10 at 80%, +$13 at 95% per member per day, walk included) |
| 3. **Day-30 milestone.** A level-0 squad on a sensible policy has food for 7 days, a weapon and Studded Leather per member and the bank strongbox | **FAIL**: 0% of guilds; see finding 2 |
| 4. **No dominant loop.** No money-from-nothing loop; no activity beats the rest on copper and XP at no more risk | **PASS** (0 exploits, 12 fragile, 0 dominance) |

"$1" is one copper, as in `AGENTS.md`; a Gold Coin ($100) is far out of day-labour reach.

## XP in the sim

- **Combat XP** is measured from the real battle (`combatant.combat_xp_earned`): a kill is worth
  `victim level - your level + 1`, nothing below your level. Combat levels 1/2/3 need 3/10/21.
- **Work XP** follows `progression.work_xp_hours`: an hour banks `activity - worker + 1` hours,
  16 banked hours = 1 mark; work levels 1/2/3 need 2/6/12 marks. Lumber is level 0 (1 with an
  own Axe), the tavern 1, the Wilds 3, a recipe its `craft_level`.
- The racial track is combat level + work level, so both feed it.
- Reported per activity: XP per member per day and days to the next combat / work level.

## Player skill is a parameter

The AI plays a squad much worse than a person (a person wins nearly every level-0 Scrapper
bout; the AI wins about half), so a win rate measured from AI-vs-AI is a floor, not the game.
Every fight-bearing activity is reported at the AI's own win rate and at `--skills` (0.8 and
0.95 by default; the verdict uses 0.8). A skilled player's loot, XP and casualties are drawn
from the fights the AI did play, split by outcome, and the casualties in a *won* fight shrink as
skill rises (`relief`: 1 at the AI's own win rate, 0 at a perfect record). That shrink is an
assumption, in both layers; replace it with measured play when it exists.

## Layer 1 — what each activity pays

`economy_activities.py`: per level, $/run, win rate, deaths, XP/day, days to the next level, net
per day after the meal. Fights are real `Battle`s; loot is valued at the market's sell price.
Two things it accounts for that the first version did not:

- **The walk.** The Wilds are about 12 hours from the City each way (the real route at the
  squads' real speed, averaged over random squads). Per-day figures use the whole cycle: hunt +
  walk there and back + the approach hour. The Old Road's ambush (20% per pass) is layer 2's.
- **Healing.** An arena squad that rests heals `rest_heal` per 8 h; the table prices bouts per
  day from that (3 HP/day at rest at level 0, 5 at level 3), not from a flat assumption.

## Layer 2 — a guild lives its days

`economy_guild.py` runs a real `Guild` for N days under a **policy**. What is real: the order
engine (`orders` + `campaign.advance`, so walking takes the real route time and a road ambush
fires on the way), daily upkeep (meals, rot, healing, house tax, animal feed, cart wear), the
market (`MarketScreen`: prices, haggling, finite stock, the market's cash), lumber and tavern
shifts (`work_shift`, `perform_shift`), crafting (`crafting_shift`), hunts (the `hunt` module) and
rests (`rest.until_full`). What is a stand-in: the fight (a library of real battles played ahead
of time for each kind, level and party size, drawn by outcome; `--skill` picks the outcome).

Policies (a class with `step(sim)`; each step spends time):

| Policy | Behaviour |
|---|---|
| `lumber` | the floor: 16 h at the yard, 8 h sleep, shop when the packs run low |
| `cautious` | lumber, plus a Scrapper bout in the evening until everyone is combat 1; hunts only at mean level 3, healthy and fed |
| `balanced` | Scrapper to combat 1, lumber for a buffer, buys Studded Leather, then a weapon, then the strongbox when the buffer survives it; hunts from mean level 2; a day of shows only if it out-pays the yard |
| `greedy` | Scrapper and the Wilds from day one, buys food only when the packs are empty |
| `maxev` | each cycle picks the activity with the best expected copper per day from the fight library |
| `crafter` | the best crafter buys inputs, works a forge shift, sells the product (the restock experiment) |
| `games` | `balanced`, but its risky day is the arena's ladder: the champion first (it opens the Games), then the Games bout with the best expected purse, only if the stake and 3 days of food are covered |
| `claimer` | `balanced`, but its risky day is the Wilds claim: it sets aside the trip's food and the fences' Lumber first, then scouts, clears, fences, sweeps and garrisons the Claim, fighting the raids |
| `rush` | the line two recorded runs took: sell the starting kit for Axes, the Champion at level 0 once the stake is in hand, armor, one Wilds hunt for a Hide, Paper and Ink at the Library, craft the Dictionary the Library's one-off mission wants, then the rest of the gear and the strongbox (thresholds from `--profile`, like `human`) |

Knobs: `--level`, `--size`, `--skill`, `--capital N` (a guild past its first week), `--assets
house,Donkey,Cart` (what it must keep), `--restock TARGET:PER_DAY` (finite shelves), `--medic`
(the Medic, below), `--mixed` (work while healing), `--set economy.LUMBER_WAGE=2` and `--price "Studded Leather=40"`
(what-ifs), `--curve`, `--ranking`, `--restock-sweep`.

**The fight library is keyed by combat and work level.** Hit dice are `1 + racial level` and the
racial level is combat level + work level, so a squad that only fights is not the same fighter
as one that also works. A guild's fight is drawn at `(mean combat, mean work)`, rounded.

**The Medic is in the game** (the Apothecary's MEDIC tab, `medic.py`) and `--medic` is the sim's
switch for it: `Sim.heal` prices and cures through the same `medic.quote` / `medic.cure` the screen
uses (HP, sickness and poison, up to `economy.MEDIC_MAX_HOURS`, at `MEDIC_PRICE_FACTOR` 0.7x the
potions and doses it would take). A guild that cannot pay it and still eat tomorrow rests instead. Layer 1 does the same: with `medic` a bout's damage
costs potions and the bouts a day stop being capped by healing.

**The Claim** runs the real stage machine (`wilds_claim_*`, `campaign.advance(dt=24)`,
`resolve_wilds_raid` and friends): a market stop for food and 10 Lumber, the walk, a 2 h scout,
the clearing fight (3 level-2 foes), the Lumber deposited and 8 h of fences, the sweep (2 level-2
foes), then a garrison that must hold 10 days while a raid (3 level-3 foes) comes with 20%
chance per daily advance. The fights are library draws (`claim_clear`, `claim_sweep`, `raid`).

**The milestone** (`milestone_cost`): copper still missing for 7 days of the cheapest food,
Studded Leather and an Axe per member, and the strongbox; what the guild already wears or has
rented is credited. It starts at **$423** for three. A guild "meets" it at day 30 if it is alive
and its money covers what is left.

## The exploit detector

An EXPLOIT is a way to get rich without bound for no real work, risk or scarce input; the exit
code is 1. FRAGILE is a loop that only one thing holds back (a tie at the best haggle, the
market's cash, a recipe nobody knows yet). DESIGN is a rule the numbers contradict. Scans (all
read the real rules):

- market round trip at the best haggle (rounding included) and stables resale;
- the gold exchange and change-making (`Unit.money` setter) on random purses;
- every recipe: buyable inputs at buy price, scarce inputs at sell price, hours from
  `items.recipe_goal`, $/h against the lumber wage;
- barriers: who can start each recipe (found by taking every talent on a levelled unit); a
  recipe anyone can start that sells at a profit, or one nobody can learn, is FRAGILE;
- levels: a recipe's level blocks nobody and is worked out by `gartok/craft_level.py` from its
  difficulty (barrier to start: open 0 / talent 1 / race 2; scarce reagents 0-2; batch time
  under 3 h 0, 3-6 h 1, over 6 h 2; one level per 2 points). The detector checks the one input
  it cannot compute (`entry_of`) against what the talents really teach;
- missions (one-offs: re-offered after accepting is an exploit) and passive income (garrison,
  fair when it pays about a day at the lumber yard);
- **route**: what walking between the markets lets a guild sell (refill per market x markets,
  over the tour time); it reads the world's market nodes, so it prices the shops when they split;
- **dominance**: among the activities meant for a level, one that beats another by $1/day or
  more, with no less XP in either track and no more risk, leaves the other with no job;
- a conservation fuzz that drives `MarketScreen` with random buys and sells: shoppers' coins
  plus the till must be conserved and their worth at the best price must never rise.

`tests/test_economy_exploits.py` runs it and breaks the rules on purpose to prove each scan can
fail. The market's cash is a design ceiling (~$25/day per market) and is printed under CEILINGS.

## Findings

**1. The floor holds, and only just.** Lumber nets +$1.00 per member per day at level 0, as
`AGENTS.md` promises. A lumber-only squad ends day 30 with about $54 per member (it started with
about $28), i.e. $160 for the guild.

**2. The day-30 milestone is out of reach for a level-0 squad.** It costs $423; lumber affords
about 38% of it. Every policy misses it at level 0, at any skill: `lumber` $54 per member at day
30, `cautious` $11-23, `balanced` $10-16, `greedy` wiped 58-100%. `maxev` equals `lumber`: at
level 0 nothing beats the yard in copper. What it takes (`--set economy.LUMBER_WAGE=2`, the wage
per 4 h block doubled): a lumber-only squad meets it in **100%** of guilds, first at **day 23**
($170 per member at day 30); `balanced` meets it in 42%. The guild needs about $3.75 net per
member per day against the +$1 the floor gives. The cost splits into food $63, armor $165,
weapons $105, strongbox $90.

**3. Healing is the arena's limiter, and a working squad barely heals.** `pass_time` heals only
while resting: a squad that works its 16 h shift heals once, in its 8 h of sleep (1 HP per night
at CON mod 0). A Scrapper bout costs about 2.2 HP, so a bout every 2-3 days is all a working
squad sustains. After 30 days `cautious` and `balanced` have mean combat level 0.6-0.8 and have
gone hungry in 28-35% of guilds: the Scrapper does lift a squad to combat 1, slowly, at a cost of
about $30-40 per member in forgone wages. Layer 1's "2.5 days to combat 1" is the squad at rest.

**4. The Wilds pay, and the walk and the risk are the price.** At level 3, layer 1 gives the
Wilds about +$5 (AI), +$8-10 (80%), +$13 (95%) per member per day, 4-13x the floor, with 16-80%
of the squad dying per run. Layer 2 puts the whole trip on the clock (about 12 h each way, a 35%
ambush per pass of the Old Road, 1.5 hunting ambushes): a hunting guild at level 3 is wiped in
78-100% of 30-day runs at 80% skill, 50-78% at 95%, and 0% only at a perfect record, where
`cautious` reaches **$107 per member** and the milestone in 42% of guilds (first day 26) and
`balanced` in 62% (day 23). So the Wilds meet the milestone only for near-perfect play; they are
a gamble priced as one. Their XP is slow on purpose (about 0.1-0.3 combat XP a day at level 3:
58-116 days to the next combat level).

**5. Upkeep drains faster than a floor job can refill.** A guild starting with $600 under the
lumber policy ends day 30 with $253 per member with nothing to keep, **$213 with a house** (the
$30 weekly tax is $4.3/day, a lumberjack's whole wage), and **$182 with a house, a Donkey and a
Cart** (the Donkey eats a ration a day, like a member). The floor job can carry a house or an
animal, not both plus the squad.

**6. The restock limiter.** With every freely bought item on a finite shelf (`--restock
TARGET:PER_DAY`), a crafting squad's profit from the market (sales minus inputs, per day) against
the $12/day a squad earns at the yard:

| Shelves (target:refill/day) | Bear Trap crafter | Dwarf Shield crafter |
|---|---|---|
| infinite (today) | $13.9 = 1.16x | $5.8 = 0.48x |
| 20:5 | 1.12x | 0.48x |
| 10:3 | 0.75x | 0.57x |
| 6:2 | 0.49x | 0.34x |
| 4:1 | 0.26x | 0.18x |
| 1:1 | 0.20x | 0.13x |

One Bear Trap crafter earns what the whole squad would at the yard (3.5x a lumberjack's
$4/day) while the shelves are loose; a Dwarf Shield crafter 1.4x. A shelf of **about 10 with a
refill of 3 a day** holds the Bear Trap crafter at 2.3x a lumberjack and the Dwarf Shield one at
1.7x; 6:2 gives 1.5x and 1.0x; tighter than 4:1 makes crafting for sale pointless (fine if
crafting is meant for saving money, not for selling). The refill is a number to set per shop and
per item when the shops split; this sweep is the first estimate.

**7. Ranking.** Net copper per member at day 30 under `lumber` (200-400 guilds): **owning an Axe
is the biggest lever, +$10** ($36.0 vs $26.4; the yard pays 4/3). By race the spread is $26 but
only **Treefolk** (autotroph: no meal) stands out, +$17; the other races sit within $10 of each
other, mostly inside the noise. By occupation Mercenary and Woodcutter lead (they start with an
Axe). CHA, languages and every attribute modifier move it by $2-6 once the thin tails are
ignored: **race and attributes are worthless in the economy**, as the first sim found. Under `balanced` the ranking is flat and
negative (the guilds lose copper leveling).

**8. The detector.** 0 exploits. 12 fragile: three market ties at the best haggle (Club,
Potato, Salt); eight recipes (the Dictionary among them) whose margin per hour is 12-25x the
lumber wage and are held back only by gating, scarce reagents and the market's cash; and the
Dictionary's open door (anyone who speaks the language can start it). 0 dominance. The route scan: with one market a tour is about 5 h and the
refills allow $25/day, 2.1x a squad's lumber day (informational); it turns FRAGILE once the
shops split and the walk stops paying for the extra refills.

**9. The Games are a ladder, not an income, and they are gated by capital.** Layer 1 at level 3,
a player who wins 80%: a Brawl or Capture the Flag pays +$4.7 per member per bout (break-even is
69% wins, the AI wins 43% and 37%), but a bout costs about 10 HP and a resting squad heals 3-5
HP a day, so it fits less than half a bout a day: **$2.5 a member a day against $4 at the yard**.
What it buys is XP: **0.2-0.4 combat XP a day** resting between bouts (the next combat level in
35-70 days) against 0.1-0.2 in the Wilds; with a Medic mending between bouts it is **3.3-3.8 a day**
(the next level in 4-5 days), but at $168 a member a bout (finding 10). That is the role the
Scrapper plays one step lower, so both are marked *leveling* and not judged for money. In layer 2 (level 3, $250, 80%) the `games`
policy beats the champion in 92% of guilds, is never wiped (the arena is non-lethal) and ends day
30 with $40 per member and the milestone gear in 77% (against `balanced` hunting: 83% wiped), but
fights only 2.4 bouts in 30 days: the $90 stake per bout (30 each) is more than a lumber squad
keeps in a week, so the ladder is capital-gated, not time-gated. The champion bout is the gate:
its purse is $120 for a $60 stake and the AI wins it 75%. The Ribbit Brothers (six a side,
$450 purse, $240 stake) are won 3-7% of the time by the AI and are layer 1 only.

**10. The Medic as built is a luxury, not a time saver.** In layer 1 it lifts
the Games from about 0.5 bouts a day (healing-capped) to the walk's limit of 3, and 10x the XP a
day, if you pay for it. A Minor Healing Potion
costs $80 and restores 3.5 HP; at 0.7x that is **$16 an HP**. Resting costs a lumberjack about
$1.3 an HP in lost wages (3 HP a day against a $4 wage). Mending a Brawl's 10 HP costs $168 a
member, 14x what resting costs, so no early guild can afford it: in layer 2 `--medic` barely
changes any policy (the `games` guild pays $22 in 30 days and fights the same 2.2 bouts, and
`balanced` pays $3). Lowering the price does not help much either, because the Games are
capital-gated: bouts rise from 2.2 to **4.1 only at 5% of the potion price** (about $4 a potion),
and XP from 1.3 to 1.8 per member. The Medic is worth keeping as a late-game luxury, where a squad's
day is worth $50 or more; as a fix for the first month's slow healing it would have to cost about
what a rest costs.
The hospital stay (a long poison, over 24 h) is priced the same way, so it is a luxury too: the sim does
not use it, a person pays it for a patient a rest would not cure.

**11. The Claim is a gamble that needs healing it does not have.** From level 3 with $250, 12
days of food and the fence Lumber, the `claimer` establishes the Claim in **13%** of guilds at
80% skill (median day 21), **15%** at 95% (day 24) and **28%** at a perfect record (day 24); it
is wiped in 65%, 30% and 0%. Most guilds finish day 30 in `SUSTAINING` with the clock reset.
*(Measured before the fix: the game now rolls the raid and the seizure once per calendar day, and the
`hold` job heals the garrison, so the figures above overstate the gamble.)*
Why: the 10-day garrison has to survive a raid (3 level-3 foes) with 20% chance per daily
advance, and **a garrisoned group never healed** (`pass_time` heals only a group that is idle or
resting, and a `garrison` order counted as busy), so each raid wore the squad down; below a
quarter of its HP the policy walks out, and an unguarded claim resets the countdown. The
established claim then yields 1 Lumber per member per day (about $3.5 at the market's 50% buy
price against $4-5 at the yard), and the seizure roll (the same 20%) fired on **every**
`advance()` call while the guild was anywhere else, so a market trip for food was several rolls
at 20% (8-10% of all guilds had lost an established claim by day 30). As a 30-day goal the Claim is a late-game project, not a way to become rich.

**12. The tavern replaces a day at the yard, and pays more from CHA +1.** A day of shows
(16 h, one Charisma test an hour) tips $3.2 at CHA +0, $4.8 at +1, $7.2 at +2 and $16 at +5, against
$4 at the yard ($5 with your own Axe). It beats the yard without an Axe from CHA +1 and beats an
Axe-armed lumberjack from CHA +2; the sim's `show_pays` uses exactly this (a day of shows
replaces the shift, never adds to it). It also needs a Musical Instrument.

**13. The racial level changes who wins the fights.** The fight library now plays a squad at
`(combat, work)` levels, not one number. A squad that only fights (Scrapper) has fewer hit dice
than one that also works: with the same combat level 2, work 0 versus work 2 changes the racial
level by 2 and the hit dice by 2.

**14. Round two (the second set of answers).**
- *Work of level 3, per hour:* crafting a level-3 recipe nets $3.15-5.75 an hour (Minor Healing
  Potion $4.75, Antidote $3.15, Dwarf Axe $5.75, Dwarf Armor $5.59), 13-23x the yard's $0.25 an
  hour, held back only by scarce inputs and the market's till. The Wilds pay ~$19.5 a member a run
  at 80% skill: $1.6 an hour hunting, $0.5 an hour counting the walk.
- *Guild size does not rescue the milestone.* Per member it needs about $111 plus $90 / size;
  a lumber guild has ~$52 per member at day 30 whatever its size (sizes 3, 5, 8, 12: 0% in all).
  The strongbox is the only part that shrinks with size.
- *Mixed healing (`--mixed`):* hurt members work the yard while they mend (1 HP a night) instead
  of resting. For the `games` guild at level 3 it lifts day 30 from $39 to $67 per member and the
  milestone from 75% to 100%, with 2.7 bouts instead of 2.2. Caveat: the loop does not shop, so
  the hungry share is inflated.

**15. Round three: recruiting and the crew.** `grower` recruits once a week (the tavern is free,
the prison asks for bail and gives +2) and puts everyone past three fighters on a crew that works
the yard (16 h work, 8 h rest) while the squad is out.
- *Recruiting is slow, and not for lack of money.* In 30 days a level-0 guild signs on **1.0-1.2**
  strangers (3 pitches, about 40% land); the language gate (a pitch needs a shared tongue) and
  the sponsor slots (`1 + CHA mod` each) stop most visits before a roll. The prison never opens:
  bail is `sum(attributes) x (racial level + 1) + 20`, about $80-90, and the guild has $8-40.
- *Growth by itself does not pay.* A yard hand nets +$1 a day after eating, so a recruit repays a
  bail in 80 days. Per-member money and the milestone do not move.
- *The crew is what a larger guild is for.* Level 3, $250, `games` policy, 80% skill: alone, the
  guild ends with $124 total and fights 2.2 bouts; with a crew of three on the yard it ends with
  $232 and fights 4.9, because the crew's wages fund the stakes the squad could not pay.
- *Shortcuts in the crew model:* the crew meets the squad at each market visit to hand over its
  coins and take food (no walk); later recruits are added to the crew directly. The crew never
  fights. A garrison crew (the Claim) is not simulated: at 1 Lumber a member a day it earns less
  than the yard.
- *Food is not the only upkeep:* the house's weekly tax, animals' rations and the wear on carts
  and wagons are upkeep too, and the sim counts all of them; for a squad with no assets food is
  the only one, and the 3-per-day ration is what the floor job is built around.

**16. Policies now buy an Axe first.** The yard pays 4/3 to anyone carrying an Axe (+$1 a day
for $35), so every policy buys one for each member lacking it as soon as it can pay it and still
eat for 3 days. A lumber guild ends day 30 with $35 in hand (the Axe is $35 of the $53 it had),
so about $17 richer in net worth, and meets the milestone **around day 51 instead of day 80**.
Still 0% at day 30. Levels do not raise the yard's wage (finding in the answers: it reads the Axe,
not the work level); a squad starting at combat 1 / work 2 with $45 ends 20 days later with $59
per member and 0% on the milestone.

**17. Talents and the climb.** The work track pays: one pick per level, **Carrier** (tier 1) then
**Piecework** (+20% coin from paid work: the Axe's $5 becomes $6), **Brisk Hands** (10% faster)
and **Steady Pace** (heal while working, work level 4). The sim now spends picks on
`TALENT_PLAN` (work: Carrier, Piecework, Brisk Hands, Steady Pace; combat: Tough, Hardy, Bulwark,
Recovery) for guild members and for the library's fighters. From level 0, a lumber guild with the
Axe (work 2 by about day 5) and Piecework holds **$50 per member at day 30** (was $35) and meets
the full milestone in **42% of guilds by day 60** (median day 49); still 0% at day 30. The
`climber` policy (yard, then Scrapper, then Games from combat ~1, then Wilds at combat 3) does
**worse** than the yard in the first 60 days: the slowest member lags at combat 0 (kills below
your level teach nothing), the bouts and food eat the wages, and the champion's $60 stake is
rarely affordable (2% milestone by day 60, 32% when the hurt work the yard while they mend).
The sim also had a bias (a library squad's first slot never got the XP); slots are now shuffled
per fight. Starting from level 3 with $250, `lumber` alone meets the milestone in 98% of guilds
(day 18) because the talents and the Axe are in; the Wilds still wipe 88%.

**18. The recorded line (`rush`).** Two of your own runs reached the day-30 milestone gear on
days 11 and 14. `rush` plays that line on the sim (40 guilds, level 0, Old Road ambush at 20%):
the milestone is met by day 30 in **40%** of guilds at 80% skill (first on day 14) and **35%** at
95% (day 15), against 0% for `lumber` and `balanced`; the report's smaller library gives 25%. The
Champion falls in over 90% of guilds, and the Dictionary mission ($250 for $55 of Paper and Ink,
once) is what pays for the armor and the strongbox. A level-0 squad is wiped in 30% of guilds at
80% skill and 5% at 95%: a lost road ambush or a lost Wilds fight. The ambush chance was lowered
from 35% to 20% (`world.ROAD_AMBUSH_CHANCE`, a placeholder nobody had measured; the road is a
barrier to the Wilds, not a main danger) after the first run of this finding gave 32% / 42% at
35%; findings 4 and 11 below were measured at 35%. Two sim biases it fixes: policies now sell
the starting kit on day 0, and the Champion is tried at the stake, not at combat 2. The report's
sustain table now lists `rush`, `games`, `climber` and `human` too.

**19. The Champion after Adelio's CON 14 (9 HP), level 0.** The AI squad now wins the bout 27%
(it was 75%), so the AI loses $9 a run; a person at 80% nets $12 a member a run ($13 a day), at 95%
$18. It stays a one-off gate (shown, not judged) and pays less than the Wilds hunt for a person
(about $15 a day at 80%), so stake $20 and purse $120 are left alone. The recorded day-6 Champion
at combat 0 is a win at the 80-95% a person plays, not at the AI's 27%. With gear on
(`unit_compare.py --armor "Studded Leather" --weapon Axe`) a combat-0 squad has AC 12 against his 15,
so he is still the fight a bare squad should not take.

**20. `human` wipes because of its hunt threshold, not because people die.** 20 guilds, 30 days,
profile from the two recorded runs: wiped 30% (AI) / 40% (80% skill), 100% hungry; the recordings
hold no death in 25 days. The profile hunts from mean combat 0.5 (`hunt_min_level`), taken from
three hunts that were all won. With `hunt_min_level` 2.0 the wipe is 0% (80% skill). Two short
runs cannot set that threshold; it needs the third run the recorder was built for.

## Decisions made without asking

Everything below was a call I made from how the game and the backlog are going. Each could have
gone another way; the ones I was least sure of are repeated as questions in the next section.

D1. **Fights are drawn from a library of real battles, not played live in layer 2.** A 30-day
   guild, six policies and dozens of guilds per cell would take tens of minutes with live
   battles; the library (40 battles per kind, level and party size) keeps layer 2 to under a
   minute a policy and gives `--skill` a clean seam (draw a won or a lost sample). It
   regenerates every run, so it never goes stale against combat changes.
D2. **Everything but the fight is the real engine**, including walking, the Old Road ambush,
   meals and rot, the market screen and the market's cash. I preferred driving `campaign.advance`
   and `MarketScreen` headless to modelling them, so a rule change moves the sim.
D3. **`relief` carried into layer 2.** At a perfect record layer 1 said 0% deaths while layer 2
   still killed members in the AI's bloody wins; I applied the same shrink to both.
D4. **A day is a 16 h shift plus 8 h of sleep** for every policy, the same day the yard's wage
   assumes.
D5. **Policies are deliberately simple and parametrised by constants** (food buffer 2 days, buy
   to 6, an evening bout only when healthy and the stake plus 3 days of food is covered,
   `balanced` buffer = stake + 3 days of food). They are reference players, not optimisers.
D6. **The milestone is affordability, with credit for what is owned.** The "weapon" is an Axe
   ($35: the cheapest tool that also lifts the yard to level 1), armor is Studded Leather, food
   is 7 days of the cheapest ration, and the chest is the Bankers' $90. A member already holding
   gear at least that dear needs none.
D7. **The milestone verdict is judged on `balanced` at 80% skill, passing at >= 50% of guilds.**
   You gave the target, not the threshold; I read "consigam" as "most guilds".
D8. **The purse goes to the first survivor** (the player picks one member in the real flow). The
   Scrapper, the champion and the Games' brawl and capture the flag are all library kinds; the
   Ribbit Brothers need six a side, so they exist in layer 1 only.
D9. **Selling goes through the market's cash and only sells what the guild picked up or crafted.**
   Starting items (the Axe, an instrument, a Holy Symbol) are never sold.
D10. **Crafting is single-threaded on the clock**: `Guild.crafting_shift` spends the whole guild's
    clock hours, so the `crafter` policy puts one member at the forge and the others wait.
D11. **Finite shelves apply to the freely bought items only**; the items already finite
    (`economy.STOCK`: Jerkin, Studded Leather, Hide, potion, Vial) keep today's no-refill rule.
D12. **Dominance needs a $1/day gap, no less XP in either track, no more deaths**, among in-band
    activities only, with a squad of performers standing in for the tavern.
D13. **The route scan reads the world's market nodes**, so it needs no change when the shops split.
D14. **Layer 1's per-day figure includes the walk but not the road ambush**; layer 2 has the ambush.
D15. **Ranking is by guild outcome**, shared by its three members, so a trait shows only over many
    guilds; the traits ranked are the six attribute modifiers, languages, race, occupation and
    "owns an Axe".
D16. **Deleted `scripts/economy_sim.py`**, as the plan's step 5 says, and moved its references:
    `AGENTS.md`, `README.md` and the backlog's "Economy sim rewrite" item; later (you said
    "vale tratar") also the `project-context` notes, with a new reference `gartok-economy-sim-v2.md`.
D17. **Test cost.** The tests add about 26 s to the suite (22 s to 48 s): a shared fight library,
    seeded runs, a tiny report. The heaviest is the report smoke test (about 11 s).
D18. **The Games are *leveling*, not *income*.** At level 3 they pay less than the yard in copper
    and far more in XP, which is what the Scrapper is for one step lower; judging them against
    the lumber floor would have failed them for the wrong reason. Brawl and capture the flag are
    also not compared with each other by the dominance scan (they differ by noise); the scan now
    compares only activities of different roles.
D19. **The Medic is a switch (`--medic`) over the game's own `medic.quote` / `medic.cure`**
    (potions at 0.7x); `--medic-factor` changes the price. The game offers it (the Apothecary's MEDIC tab),
    but the switch stays off by default so the other findings keep their baseline.
D20. **A hurt guild goes to the Medic only if it can afford the bill and still eat tomorrow**;
    otherwise it rests. The policies themselves did not change.
D21. **The Claim expedition buys 12 days of food and the 10 Lumber, walks, and runs the stages in
    order**, stopping the run on a lost fight (the guild heals and tries again). The garrison
    stands down when anyone is under a quarter of their HP, the food is under a day or the claim
    is seized. The `claimer` policy sets that trip's cost aside before it buys any gear.
D22. **The Games policy fights only when the stake and 3 days of food are covered**, and only a
    bout whose expected purse beats its stake (the champion is always tried first: it opens the
    Games and you gave it its own reward).
D23. **Both level tracks key the fight library**, and the dominance scan, `balanced` and the rest
    use `Sim.fight_level`. Layer 1 keeps one number for both tracks (its squads level together).
D24. **The late-game scenario is level 3 with $250** (a first week behind a squad): the Games and
    the Claim cannot be reached from level 0 in 30 days, so the report starts them where a
    squad would plausibly be. The number is mine.

## Answers received

Your replies to the first 17 questions (2026-10-08), what each meant and what I did. Numbers refer
to the old question numbers.

| # | You said | What I did |
|---|---|---|
| 1 | "What is the 423?" | It is the milestone's start cost for three: food for 7 days $63 (21 rations at $3), Studded Leather $165 ($55 x 3), an Axe each $105 ($35 x 3) and the strongbox $90. See [the milestone](#layer-2--a-guild-lives-its-days). |
| 2 | (did not understand) | The verdict needs a rule for "passes"; mine is "at least half of the guilds playing `balanced` at 80% skill". It is still open: see question 1 below. |
| 3 | The Axe is fine, one of the best basic weapons; late game is axe + torch, two-hander or bow (axe + shield for dwarves) | Kept the Axe as the milestone's weapon and credited an equal weapon already owned. |
| 4 | Not sure; today crafting is click-buy-craft-sell forever | Kept the 10:3 shelf as the first estimate and moved the Specialised shops backlog item along. Open: question 2. |
| 5 | Crafting should be parallel: allocate a character, it splits from the group and crafts | New backlog item **Crafting in parallel**. The sim still has one crafter at a time. |
| 6 | Put the Medic in the count | `--medic` in both layers: [finding 10](#findings). Priced as built (`economy.MEDIC_PRICE_FACTOR`, 0.7x) it is out of reach; see question 3. |
| 7 | How lethal is the Wilds today? | Answered below. |
| 8 | Review: nodes now have many functions (a tavern recruits, works and sells) | New note under **Specialised shops**: the till and its refill belong to a shop function, not to `kind == "market"`. |
| 9 | (did not understand) | A house costs $30 a week, $4.3 a day, which is a lumberjack's whole wage ($4), and a Donkey eats a ration like a member. So a squad on day labour cannot keep a house or an animal; only an adventuring income can. Is that the intent? Question 5. |
| 10 | Reasonable. Which work has the most challenge? | The level-3 recipes (Minor Healing Potion, Antidote, Dwarf Axe, Dwarf Armor) and the Wilds hunt (activity level 3): at work level 0 they bank 4 hours of XP per hour worked. 13 recipes are level 2, 2 are level 1, the tavern is 1, the yard 0 (1 with your Axe). |
| 11 | Tavern and yard are not both; compute from when the tavern is worth it | `show_pays` already treated a day of shows as replacing the shift; `act.tavern_table()` now prints the break-even in the report: the stage beats the yard from CHA +1 (+2 against an Axe). [Finding 12](#findings). |
| 12 | No dungeon; the Games yes | Done: layer 1 rows for the champion, Brawl, Capture the Flag and the Ribbit Brothers; layer 2 kinds and a `games` policy. [Finding 9](#findings). |
| 13 | Check if the Claim can be dominated in 30 days and the impact; the Medic is important for time | Done: a `claimer` policy on the real stage machine. [Finding 11](#findings). |
| 14 | "Level" means racial level, not only combat | The fight library is keyed by (combat, work) levels and a squad built that way; [finding 13](#findings). |
| 15 | Improve the AI; make it a backlog task | New backlog item **Combat AI plays far below a person**, with the AI's win rates as the gauge. |
| 16 | Worth handling | `project-context` notes updated, new reference `gartok-economy-sim-v2.md`. |
| 17 | Do not commit yet, there is more to resolve | Nothing committed. |

**How lethal is the Wilds today** (your question 7), at the squad levels it is meant for:
layer 1, level 3, three members: a run is a 12-15 h walk each way plus about 11 h of hunting, with
1.5 ambushes of Wilds creatures; the AI wins an ambush 58-61% of the time and **50-72% of the
squad dies per run** (the 80% player: about 49%, by the `relief` assumption). Layer 2 adds the
Old Road's 35% ambush on each of the two passes and the recovery time; a hunting guild is wiped in
**78-100% of 30-day runs at 80% skill, 50-78% at 95%, and 0% only at a perfect record**. So today
a level-3 squad cannot make a living in the Wilds unless it wins almost every fight. Your
"level 0 normally dies there" holds at any skill, and the level-3 band is more dangerous than
the "go at level 2/3" idea suggests.

## Questions and decisions to validate

What is still open after your answers, in rough order of how much they change the result.

1. **Is the day-30 milestone meant to need adventure income?** Lumber alone affords 38% of the
   $423 (the day-23 lever: wage 2 a block). If the floor should nearly carry it: cheaper armor or
   weapon, a smaller strongbox, a shorter food requirement or a higher wage. If adventure is meant
   to carry it, a level-0 squad has nothing that pays and the first month is survival. Which? And
   what share of which policy counts as passing (I used 50% of `balanced` at 80% skill)?
2. **How much may a crafting specialist earn?** I assumed 2-3x a lumberjack (a shelf of about 10
   refilling 3 a day); your note says crafting is mostly to save money and reach things you cannot
   buy, and is not to be encouraged as a business. If so the shelf can be tighter (6:2 gives 1.5x).
3. **What should the Medic cost?** As built (potions at 0.7x) it is $16 an HP against $1.3 an
   HP for a rest, so only a rich squad uses it ([finding 10](#findings)). Price it at the rest it
   saves (a few copper an HP), or keep it as a late-game luxury?
4. **(Settled in the game, not yet in the sim.)** The garrison now has a `hold` job that counts as
   rest (heals in 8 h) and the raid and seizure rolls fire once per calendar day crossed, not per
   `advance()` call. The numbers in finding 11 predate that fix; re-measure the `claimer` once the
   sim models `hold`.
5. **Upkeep.** A house costs a lumberjack's whole wage and a Donkey a third more. Intended as
   "assets need an adventuring income", or should the first assets be reachable on day labour?
6. **How lethal should the Wilds be?** See the answer above. Is the Old Road's ambush (now 20%) per
   pass right, given it fires on every walk to and from the Wilds? Both set how rich a good player
   gets and how often a squad dies.
7. **The Games' stake.** A $30 stake per fighter ($90 for three) is more than a lumber squad keeps
   in a week, so the Games are capital-gated (2.4 bouts in 30 days for the `games` policy). Meant
   as a climb for a squad that has already done well, or should the stake come down?
8. **The Library's cash never refills** (and, with the tavern as a shop, neither would the
   tavern's). The backlog now says the till belongs to a shop function. Anything else to decide
   before that item is sized?
9. **Crafting is the fastest work XP for a level-0 character** (levels 1-3 mean x2-x4), because
   the recipe level is now automatic. You said it seems reasonable; I leave it as an open number
   until the parallel crafting lands, since that changes how much a crafter's hour is worth.
10. **The late-game scenario.** Level 3 with $250 is my guess at "a squad a week in". If you play
    toward another point (say level 2 with $100), say so and the report's section 4 moves.
11. **Nothing is committed.** The files: `AGENTS.md`, `README.md`, `docs/plans/backlog.md`,
    `docs/plans/economy_sim_v2.md`, `scripts/economy_activities.py`, `scripts/economy_exploits.py`,
    `scripts/economy_guild.py`, `scripts/economy_report.py`, `scripts/economy_sim.py` (deleted),
    `tests/test_economy_exploits.py`, `tests/test_economy_sim.py`, and the `project-context`
    notes (`SKILL.md`, three references, one new). I would commit the scripts and tests together,
    the notes and the doc separately.

## Known limitations

- Policies are reference players, not optimal ones; `maxev` uses expected values from the
  library, not a search.
- A guild's day-D figure is read at the first step boundary at or after D, so it can overshoot by
  up to a day or two.
- Library battles come from fresh squads at the party's mean combat and work level, with starting
  kit; a guild that has bought armor or a weapon is not drawn stronger.
- The champion's title and its 15-day defense cycle, and the Ribbit Brothers, are not in layer 2.
- The Claim has no campfire, oven or garage in the sim (the game has the oven since the Stone
  Brick commit; the sim does not model it), nor the garrison's `hold` job (rest, heals in 8 h);
  the garrison only gathers Lumber.
- The Medic and the Games' stake are the numbers the code has (or the backlog proposes), not tuned.
- The hunt and the road each use their own encounter table (`hunt.wilds_pack`, the Old Road's
  `encounter_table`); the pack rolled by `campaign` for an ambush is not the one fought.
- Animals and carts only cost upkeep: no pack saddle, no hitched wagon carrying anything.
- Layer 1 ignores the Old Road's ambush and the market's cash (layer 2 has both).
- Layer-1 figures move by a few copper between seeds (the squads are random); read them as
  ranges, not points.

## Build order (all done)

1. Layer 1 table, floor and Wilds checks, XP, the walk and real healing.
2. Exploit detector, with the barriers, level, route and dominance scans.
3. Layer 2: the real engine, the fight library, eight policies, the market's cash on every sale,
   finite shelves, upkeep assets, the sustain curve and the ranking.
4. The day-30 milestone check and the report in this plan's order.
5. Deleted the old `Vendor` / `run_trader` script.
6. After the first answers: the Medic switch, the Games (layer 1 and the `games` policy), the Claim
   (the `claimer` policy), the fight library keyed by combat and work level, the tavern table.

Tests: the floor and the Wilds check, a week on the real clock, every policy, the market's cash,
the shelves, the milestone, the ranking and the report all run as `pytest` on seeded short
configurations, so a wage or price change that breaks them fails the suite.
