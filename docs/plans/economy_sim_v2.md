# Economy sim v2 — design

Replaces `scripts/economy_sim.py` (one character, an invented town, no risk). The old
script keeps answering "do race and attributes earn a living"; this one answers whether
the guild economy holds together. **XP is part of the economy**: a level is worth money, so
every activity is measured in copper *and* in XP.

## Roles: each activity has a job

Judge an activity against its own job, at the levels it is meant for, not against a single
money bar.

| Activity | Role | Level band | What "good" means |
|---|---|---|---|
| Lumber yard | floor | 0-1 | A squad eats and keeps >= $1 a day, always available |
| Arena: Scrapper | leveling | 0 | Takes a squad to combat level 1 cheaply. **Not a money job**: the purse is fine as is |
| Tavern show | side income | 0-1 | Pays about what lumber does for whoever owns the instrument |
| Wilds hunt | income + food + XP | 2-4 | Out-earns the floor by a wide margin; the risk is the price |

A level-0 squad in the Wilds normally loses and that is intended; the Wilds are judged at
level 2-3 only.

## Targets (pass/fail)

1. **Floor.** Lumber at level 0: eat and keep >= $1 per member per day.
2. **Wilds beat the floor** at level 2-3, for a player who wins a reasonable share of fights.
3. **Day-30 milestone** for a level-0 squad on a sensible policy: food for 7 days, a weapon
   and Studded Leather ($55) per member, the bank strongbox ($90). Needs layer 2.
4. **No dominant loop.** No activity beats the rest in $/hour *and* XP at comparable risk,
   and no buy/sell cycle makes money without work.

"$1" is one copper, as in `AGENTS.md`; a Gold Coin ($100) is far out of day-labour reach.

## XP in the sim

- **Combat XP** is measured from the real battle (`combatant.combat_xp_earned`): a kill is
  worth `victim level - your level + 1`, nothing below your level. Combat levels 1/2/3 need
  3/10/21 XP.
- **Work XP** follows `progression.work_xp_hours`: an hour banks `activity - worker + 1`
  hours, 16 banked hours = 1 mark; work levels 1/2/3 need 2/6/12 marks. Lumber is level 0
  (1 with an own Axe), the tavern 1, the Wilds 3.
- The racial track is combat level + work level, so both feed it.
- Reported per activity: XP per member per day and days to the next combat / work level.

## Player skill is a parameter

The AI plays a squad much worse than a person (a person wins nearly every level-0 Scrapper
bout; the AI wins about half), so a win rate measured from AI-vs-AI is a floor, not the
game. Every fight-bearing activity is reported at the AI's own win rate and at
`--skills` (default 0.8 and 0.95). Loot, XP and casualties for a skilled player are drawn
from the fights the AI did play, split by outcome; casualties in won fights shrink as
skill rises (an assumption, flagged in the code). Replace with measured play when it exists.

## Layers

**Layer 1 (built, `scripts/economy_activities.py`)** — a table per level: $/run, win rate,
deaths, XP/day, days to level, net per day after the meal. Fights are real `Battle`s,
healing caps arena bouts per day (3 HP/day), loot is valued at the market's sell price.

**Layer 2 (next)** — the real `Guild`, market, `market_cash` and daily upkeep (house tax,
garrison, wagon wear, animal feed, group rest) for 7 and 30 days, driven by a policy:
lumber only, cautious, balanced, greedy, max-EV. Output: daily balance, gear and level at
day 7 / 30, share of guilds broke or wiped, first day each milestone is affordable.
Selling loot must go through `market_cash` ($100 start, +$25/day): layer 1 ignores it.

**Exploit detector (built, `scripts/economy_exploits.py`)** — an EXPLOIT is a way to get rich
without bound for no real work, risk or scarce input; the exit code is 1. FRAGILE is a loop
that only one thing holds back (a tie at the best haggle, the market's cash, a recipe nobody
knows yet). It scans the real rules:

- market round trip at the best haggle (rounding included) and stables resale;
- the gold exchange and change-making (`Unit.money` setter) on random purses;
- every recipe: buyable inputs at buy price, scarce inputs at sell price, hours from
  `Unit.crafting_goal`, $/h against the lumber wage;
- barriers: who can start each recipe (found by taking every talent on a levelled unit),
  whether a recipe's level really stops a beginner, which inputs are scarce; a recipe
  anyone can start that sells at a profit, or one nobody can learn, is FRAGILE;
- levels: a recipe's level blocks nobody and is worked out by `gartok/craft_level.py` from its
  difficulty (barrier to start: open 0 / talent 1 / race 2; scarce reagents 0-2; batch time
  under 3 h 0, 3-6 h 1, over 6 h 2; one level per 2 points). It is the label and, for a
  crafter below it, the work-XP multiplier. The detector checks the one input it cannot
  compute (`entry_of`) against what the talents really teach. The weights are a proposal;
- missions (one-offs: re-offered after accepting is an exploit) and passive income (garrison,
  fair when it pays about a day at the lumber yard);
- a conservation fuzz that drives `MarketScreen` with random buys and sells: shoppers' coins
  plus the till must be conserved and their worth at the best price must never rise.

`tests/test_economy_exploits.py` runs it and also breaks the rules on purpose to prove each
scan can fail. The market's cash is a design ceiling (~$25/day per market); the detector
prints it under CEILINGS. Not built yet: a route scan (money per hour of walking between
shops, needs the shops split) and a Pareto dominance check on the layer-1 table.

## Report order

1. Pass/fail verdicts with the number that decides each.
2. Exploits and dominant activities.
3. Activity table with risk and XP.
4. Sustain and level curve per policy.
5. Ranking by attribute, occupation and race (last).

## Build order

1. Layer 1 table, floor and Wilds checks, XP. **Done.**
2. Exploit detector. **Done** (route scan waits for the shops).
3. Layer 2 with the lumber-only policy, then the others; `market_cash` on every sale.
4. Day-30 milestone check and report.
5. Delete the old `Vendor`/`run_trader` once the ranking runs on the new engine.

Tests: the floor and the Wilds check run as `pytest` on a short, seeded configuration, so
a wage or price change that breaks them fails the suite.
