# Economy sim — what it measures and how to read it

The one question: does the guild economy hold together? Does a guild sustain itself, and is the
risk x time x reward of each activity right? **XP is part of the economy** (a level is worth
money), so every activity is measured in copper *and* in XP. The sim replaced
the old `economy_sim.py` script (one character, an invented town, no risk), now deleted.

This is a reference, not a plan: the work still open is in [plans/backlog.md](plans/backlog.md)
(*Measure the economy against the decided lines*, *The sim's long game*, *Sim policies*). The measurements of the
first rounds (2026-10-08 to 2026-10-22: twenty dated findings, the author's answers, the first
decisions) are in git: `git show 1a999bf:docs/plans/economy_sim_v2.md`. The frozen story is the
`project-context` reference `gartok-economy-sim-v2`.

After touching wages, purses, prices or loot run `python scripts/economy_report.py` (or `--quick`)
and `python -m pytest tests/ -n auto -m balance` (`AGENTS.md` carries the rule).

## The tools

| Script | What it does | Run |
|---|---|---|
| `scripts/economy_report.py` | one report: verdicts, exploits, activities, sustain, ranking; writes `sim_results/economy-report-*.txt`; exit 1 if a verdict fails | `python scripts/economy_report.py [--quick]` |
| `scripts/economy_activities.py` | **layer 1**: what each activity pays a squad per day in copper and XP, risk, days to the next level, the floor check; the Pit and the Games; the tavern against the yard | `--level 0\|3 --skills 0.8,0.95 [--medic]` |
| `scripts/economy_guild.py` | **layer 2**: a whole guild lives N days under a policy on the real engine; sustain curve, milestone, ranking, restock sweep, upkeep, the Games ladder, the Wilds claim, the Medic | `--policies ... --skill 0.95 [--curve] [--ranking] [--medic] [--level 3 --capital 250]` |
| `scripts/economy_exploits.py` | the exploit detector: loops, barriers, dominance, route, conservation fuzz | `--fuzz 200` |
| `scripts/economy_offers.py` | what is on offer to a guild today, each priced in copper and days (the input of a future planner) | `[--size 4 --money 400]` |
| `tests/test_economy_sim.py`, `test_economy_exploits.py`, `test_economy_offers.py`, `test_craft_level.py` | pytest on seeded short runs; the detector tests break the rules on purpose to prove each scan can fail; the ones that judge a design number off a sim are marked `balance` | `python -m pytest tests/` (`-m balance` for those) |

Every script above that runs many independent trials or guilds (`economy_report`, `economy_activities`,
`economy_guild`, `economy_exploits`, `vocation_report`, `wealth_by_level`) takes `--workers N`, default
`cpu_count - 2` (`vocation_report` defaults to 1: its run is shorter than starting the pool). A battle trial or a guild is a job seeded on its own (`economy_activities.isolated`), so the
numbers are the same for any N; `--workers 1` runs in-process with no pool, for a debugger. The guild
workers share the fight library on disk (`economy_guild.SharedLibrary`), each pool played once. An
unseeded call (`arena_row` and `hunt_row` with no `seed`) draws its base seed from the global `random`, so
a script seeds it first (`--seed`).

## Roles: each activity has a job

Judge an activity against its own job, at the levels it is meant for, not against one money bar.

| Activity | Role | Level band | What "good" means |
|---|---|---|---|
| Lumber yard | floor | 0-1 | A squad eats and keeps >= $1 a day, always available. With no fatigue the Yard pays ~50% over that floor: accepted 2026-10-22, hunger is the one upkeep |
| Arena: Scrapper | leveling | 0 | Takes a squad to combat level 1 cheaply. **Not a money job**: the purse is fine as is |
| Arena: Brawl, Capture the Flag (the Games) | leveling | 2-5 | The ladder after the Scrapper: non-lethal, XP-rich, costs more in stake than it pays. Not judged for money |
| Arena: Challenge the Champion, The Ribbit Brothers | one-off | 1-4, 3-6 | A gate (it opens the Games) and a capstone (six a side). Shown, not judged |
| Tavern show | side income | 0-1 | Pays about what lumber does for whoever owns the instrument; a day of shows replaces the shift, never adds to it |
| Wilds hunt | income + food + XP | 2-4 | Out-earns the floor by a wide margin; the risk is the price |
| Crafting | saving money, reaching what is not for sale | by recipe | Not meant as a business (author): a specialist earning 2-3x a lumberjack is the ceiling the shelves aim at |

A level-0 squad in the Wilds normally loses and that is intended; the Wilds are judged at level
2-3 only. The Wilds give little XP on purpose: the arena and the dungeon are the way up (the
dungeon is not in the sim; the Games are). "$1" is one copper, as in `RULES.md`.

## Targets (pass/fail)

The report prints today's number next to each; the exit code is 1 if one fails.

1. **Floor.** Lumber at level 0: eat and keep >= $1 per member per day.
2. **Wilds beat the floor** at level 2-3 for a player who wins most fights.
3. **Day-30 milestone: a healthy guild.** A level-0 squad on the `balanced` policy can, by day 30, equip
   at least 3 members (a weapon worth 35+, an Axe, and Studded Leather) and still hold the copper for
   7 days of food for 3 (7 x 3 x the cheapest food price) in >= 50% of its guilds
   (`economy_report.MILESTONE_SHARE`). `milestone_cost` takes the 3 members cheapest to equip and
   credits what they already wear; a bigger guild adds nothing to it. The strongbox is not part of it.
4. **No dominant loop.** No money-from-nothing loop (EXPLOIT); no activity beats another of its
   level on copper and XP at no more risk.

## How the sim models play

- **XP** is measured from the real battle (`combatant.combat_xp_earned`) and follows
  `progression.work_xp_hours`; the racial track is combat + work + magic, so all three feed it.
  Per activity the report gives XP per member per day and days to the next combat / work level.
- **Player skill is a parameter.** The AI plays a squad worse than a person, so a win rate from
  AI-vs-AI is a floor. `SKILL` (`economy_activities.SKILL`, 0.5 pooled) is the share of the AI's
  losses a person turns into wins, measured by replaying the author's recorded fights with the AI
  (`scripts/combat_pairs.py`, 229 fights, 2026-11-06, after the combat-AI fix: 93% to the AI's 85%).
  It differs by kind of fight, so the default is `Measured`: `SKILL_BY_FIGHT` gives hunts 0.78 (122
  fights), the Pit's Scrapper 0.13 (33), road and gather ambushes 0.10 (29), and any kind with too
  few fights (the champion, the Games, the claims) keeps 0.5 (`skill_for`). An explicit `--skill N`
  is a plain float and applies flat to every fight. `--skills` adds other rates; the casualties of
  a *won* fight shrink as skill rises (`relief`), an assumption in both layers. Re-measure with
  `combat_pairs.py combat_lab/campaign saves/<world>/combat_logs` after a `gartok/ai` change.
- **Layer 1** (`economy_activities.py`): per level, $/run, win rate, deaths, XP/day, net per day
  after the meal. Fights are real `Battle`s; loot is valued at the market's sell price. Per-day
  figures include the walk (the Wilds are ~12 h from the City each way) but not the road ambush
  (layer 2's), and healing is priced from `rest_heal`.
- **Layer 2** (`economy_guild.py`) runs a real `Guild` under a **policy**. Real: the order engine
  (`orders` + `campaign.advance`, so walking takes the real route time and a road ambush fires),
  daily upkeep (meals, rot, healing, house tax, animal feed, cart wear), the market
  (`trade.Counter`: prices, haggling, finite stock, the market's cash), lumber and tavern shifts,
  crafting, hunts and rests. Stand-in: the fight, drawn from a **library of real battles** played
  ahead of time per kind, level and party size, by outcome (`--skill` picks the outcome). The
  library is keyed by `(combat, work)` level, because hit dice follow the racial level, and it is
  rebuilt every run so it never goes stale against combat changes.
- **Policies** (`class Policy`, `step(sim)` spends time) are reference players, not optimisers:
  `lumber` (the floor: shift after shift, shop when the packs run low), `balanced` (the author's
  line: the sprint to the day-30 milestone, then the Pit, a recruit and the Wilds hunt as the
  income), and `gatherer`, `miner`, `miner_wage` (probes: a gathering licence against its wage). A day is a
  16 h shift plus 8 h of sleep. Policies buy an Axe first (the yard pays 4/3 to anyone carrying
  one) and spend talent picks on `TALENT_PLAN`.
- **Knobs:** `--level`, `--size`, `--skill`, `--capital N` (a guild past its first week; the
  late-game scenario is level 3 with $250, a guess), `--assets house,Donkey,Cart`, `--restock
  TARGET:PER_DAY` (finite shelves), `--medic` / `--medic-factor`, `--mixed` (the hurt work while
  they mend), `--vocation`, `--set economy.LUMBER_WAGE=2` and `--price "Studded Leather=40"`
  (what-ifs), `--curve`, `--ranking`.
- **Vocations (`--vocation`)** pass the id to the real `Guild`, so every perk runs through
  `gartok/vocations.py`; the script adds no rule. Delvers: the hunt's and the gathering shifts'
  yield. Caravan: `vocations.travel_mult` on every walk. Survivors: `vocations.hunger_relief` softens the real hunger penalty (the sim's
  members eat every day, so it never fires there).
  Wanderers: the guild travels *Cautious* (`Sim.main.stance`, the crew's too), which the rules
  make free, so the perk's x0.8 reaches the hunt hour, the Old Road leg and the gathering shift.
  Scholars: the library's fights are played with `battle.intel.bind("player", None,
  vocations.info_bonus(guild))` (`FightLibrary.with_info_bonus`; same seeds and cache as the plain
  library, only the bonus differs), so the squad reads its foes at +2 and the AI acts on more.
  Warband: its +1 is starting morale in a fight, and the library's fights are played from fixed
  seeds without the guild's vocation, so the sim never exercises it. Missing sim behaviour: the
  vocation reaching the library's fighters. Also unexercised: the Scholars' Assess action and the
  bestiary's race discount (the library has no persistent bestiary, so only the opening read
  is bonused), the Night Prowler and Woodland Scout (talents, not vocations), and a Cautious
  guild's lost XP and loot beyond the fewer fights it draws.
- **The Medic** is a switch (`--medic`) over the game's own `medic.quote` / `medic.cure`
  (potions at `MEDIC_PRICE_FACTOR` 0.7x); off by default so the other numbers keep their baseline.
  As built it is a late-game luxury (about $16 an HP against $1.3 an HP for a rest): a hurt guild
  goes to it only if it can pay and still eat tomorrow.
- **Claim, Games and crew are engine, not policy.** `Sim` can run the Claim's real stage machine
  (`wilds_claim_*`, `campaign.advance(dt=24)`, `resolve_wilds_raid`: market stop, walk, scout,
  clearing fight, fences, sweep, then a 10-day garrison with a daily raid roll), draw the arena's
  bouts (`Sim.bout`: `arena`, `champion`, `brawl`, `ctf`) and keep a crew on the yard while the squad
  is out. Since the policies were cut to `lumber` and `balanced` (2026-10-21) none is built around
  them; the old `games`, `claimer`, `grower`, `rush` and `climber` policies are in git.
  What they showed still holds: the Claim is a gamble and a late-game project, not a way to get rich
  in 30 days; the Games are a ladder, not an income, and capital-gated (the 30-a-fighter stake is more
  than a lumber squad keeps in a week); a crew on the yard funds the stakes the squad could not pay.
- **Ranking** is by guild outcome, shared by its members, so a trait shows only over many guilds.
  Owning an Axe is the biggest lever; race and attributes are worth little in the economy
  (Treefolk, who eat no meal, are the exception).

## The exploit detector

An EXPLOIT is a way to get rich without bound for no real work, risk or scarce input (exit code
1). FRAGILE is a loop that only one thing holds back (a tie at the best haggle, the market's
cash, a recipe nobody knows yet). DESIGN is a rule the numbers contradict. Scans, all on the
real rules:

- market round trip at the best haggle (rounding included) and stables resale;
- the gold exchange and change-making (`Unit.money` setter) on random purses;
- every recipe: buyable inputs at buy price, scarce inputs at sell price, hours from
  `items.recipe_goal`, $/h against the lumber wage;
- barriers: who can start each recipe (found by taking every talent on a levelled unit); a recipe
  anyone can start that sells at a profit, or one nobody can learn, is FRAGILE;
- levels: a recipe's level blocks nobody and is worked out by `gartok/craft_level.py` from its
  difficulty (barrier to start; scarce reagents; batch time; one level per 2 points). The detector
  checks the one input it cannot compute (`entry_of`) against what the talents really teach;
- missions (a one-off re-offered after accepting is an exploit);
- **route**: what walking between the market nodes lets a guild sell (refill per market x markets,
  over the tour time);
- **dominance**: among activities meant for a level, one that beats another by $1/day or more,
  with no less XP in either track and no more risk, leaves the other with no job; compared only
  across different roles;
- a conservation fuzz that drives `trade.Counter` with random buys and sells: shoppers' coins plus
  the till must be conserved and their worth at the best price must never rise.

`tests/test_economy_exploits.py` runs it and breaks the rules on purpose to prove each scan can
fail. The market's cash is a design ceiling (~$25/day per market), printed under CEILINGS.

## Modelling choices that still shape the numbers

- Everything but the fight is the real engine, so a rule change moves the sim; the fight is a
  library draw, which keeps a 30-day guild under a minute a policy.
- Selling goes through the market's cash and only sells what the guild picked up or crafted;
  starting items (an Axe, an instrument, a Holy Symbol) are never sold.
- Crafting is single-threaded on the clock (the sim's `Guild.crafting_shift` spends the whole guild's
  hours), so a crafting guild puts one member at the forge and the others wait.
- Finite shelves apply to freely bought items only; the items already finite (`economy.STOCK`)
  keep their no-refill rule. A shelf of about 10 refilling 3 a day holds a crafter near 2x a
  lumberjack; the number is a first estimate.
- Upkeep is food, the house's weekly tax, animals' rations and cart wear; for a squad with no
  assets food is the only one, and the 3-a-day ration is what the floor job is built around. The
  yard cannot carry a house or an animal by itself, only an adventuring income can.
- The purse goes to the first survivor; the Ribbit Brothers (six a side) exist in layer 1 only.

## Known limitations

- Policies are reference players, not optimal ones.
- A guild's day-D figure is read at the first step boundary at or after D (it can overshoot by a
  day or two).
- Library battles come from fresh squads with starting kit: gear a guild bought does not draw a
  stronger fighter.
- The champion's title and its 15-day defence, and the Ribbit Brothers, are not in layer 2.
- The Claim has no campfire, oven or garage. Its garrison holds (rest, heals in 8 h) and a crew
  with an Axe gathers a 16 h shift a day from its post (`Gathering`, no licence); the rest of the
  day is the garrison's advance. Its numbers predate the shift rule.
- The hunt and the road each use their own encounter table (`hunt.wilds_pack`, the Old Road's
  `encounters.OLD_ROAD_TABLE`); the pack `campaign` rolls for an ambush is not the one fought.
- Animals and carts only cost upkeep: no pack saddle, no hitched wagon carrying anything.
- Layer 1 ignores the Old Road's ambush and the market's cash (layer 2 has both).
- Layer-1 figures move by a few copper between seeds (random squads): read them as ranges.
