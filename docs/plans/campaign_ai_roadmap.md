# Campaign AI: a planner, then a genetic algorithm

Status: **not started** (backlog, *Large -> Campaign AI*). Phase 1 exists; nothing past it does.

## Goal

An AI that plays the campaign layer (orders, shopping, talents, loadouts), not only the fights
(`gartok/ai/` already plays those). It is for the sims, not for the player: to
1. optimise builds, talent picks and loadouts;
2. maximise roster XP, survivability and faction reputation;
3. stress-test the rules and surface exploits or broken metas on its own.

## Why it is cheap here

The core (`battle`, `campaign`, `guild`, `orders`, `progression`) has no pygame and no UI, a 30-day
guild runs headless in seconds on CPU with the fights drawn from `economy_guild.FightLibrary`, and
runs are seedable. A genetic algorithm over a utility policy suits the problem better than the
alternatives: a scripted bot only does what is hardcoded (that is what `economy_guild`'s policies
are today); pure RL (PPO/DQN) suffers from sparse rewards and a combinatorial macro action space; an
LLM agent is too slow to run thousands of guilds.

## Exploit hypotheses to test

Expected to emerge from the rules; none is covered by `scripts/economy_exploits.py` (the detector
scans markets, recipes, missions, routes and dominance). Check each in the code before building on it.

1. **Last-hit funnel.** `progression.xp_award(attacker, victim) = (victim - attacker) + 1` when
   `victim >= attacker`, else 0, and only the lethal blow earns XP: veterans soften a boss, a level-0
   recruit lands the last hit.
2. **Mean-level twinking.** Encounter and arena difficulty scale with `progression.mean_level`
   (`encounters.py`): one level-3 veteran plus three level-0 recruits is a mean of 0.
3. **Cross-training HP.** Hit dice follow the racial level (combat + work + magic), so safe day
   labour raises HP before a unit risks permadeath.
4. **Reputation deeds.** They are one-shot (`factions.py`): buy and resell five cheap items for
   "Diverse Portfolio", or field an unarmoured runner in Capture the Flag for "Untouchable".

## Design: a utility engine parametrised by a genome

The genome sets the weights and thresholds of a decision loop; it does not write code.

- **Genome:** work vs adventure preference, risk tolerance (minimum squad HP before the Arena or a
  hard fight), copper reserve before buying gear, tool-buying priority, weapon bias (reach vs damage),
  armour investment, talent-tree focus.
- **Decision loop** at each node or day: list the options (`Order.march`, `work`, `arena`, `rest`,
  the offers in `scripts/economy_offers.py`), score each as a function of the state and the genome,
  dispatch the best through `orders.py`, let `ai/` run the fights.
- **Fitness:** reputation, roster combat and work XP, copper, minus the fallen. The weights are the
  author's call (an early guess: reputation x100, combat XP x10, work XP x5, copper x0.1, fallen -50).

## Phases

1. **Headless runner.** Done: `scripts/economy_guild.py` (a 30-day guild on the real
   `campaign.advance`, hand-written policies).
2. **Policy planner / `CampaignAgent(genome)`.** The first open step (it is also the sim's "policies
   that find the opportunities themselves"): `economy_offers.py` already lists what a guild can take up in copper and days; the planner enumerates and prices the
   offers dynamically, then picks by genome-weighted utility (travel by `world.route`, tools and
   weapons, when to enter the Arena or take a mission, auto-equip and talent picks). Compare it
   against `balanced` as the baseline.
3. **Evolutionary loop.** Population 30-50 guilds, 20-30 generations, top 20% kept, blend crossover,
   small Gaussian mutation (about 5%).
4. **Telemetry.** Convergence logs: best score per generation, dominant builds, deeds unlocked,
   roster survival. Read the exploits it found against the hypotheses above.
