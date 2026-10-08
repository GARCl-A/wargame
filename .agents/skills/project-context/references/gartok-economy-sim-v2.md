---
name: gartok-economy-sim-v2
description: "Economy sim v2 (scripts/economy_*.py): per-activity table in copper and XP, whole-guild sim on the real engine with policies, exploit detector, the Games / Claim / Medic experiments; Oct 2026 findings"
metadata:
  node_type: memory
  type: project
  modified: 2026-10-08
---

The economy is measured by four scripts and one report (`python scripts/economy_report.py`, `--quick`
for a smoke run), plan and findings in `docs/plans/economy_sim_v2.md`. They replaced the old
`economy_sim.py` (see [[gartok-balance-sim]] for its history). XP is part of the economy, the
player's skill is a parameter (the AI plays far below a person), and a recipe's level is worked out
by `gartok/craft_level.py` and blocks nobody.

- `economy_activities.py` (layer 1): what each activity pays a squad per day in copper and XP, with
  the real walk time and real healing. Roles: lumber = floor, Scrapper and the Games = leveling,
  Wilds = income, champion / Ribbit Brothers = one-off. `--medic`, `--medic-factor`.
- `economy_guild.py` (layer 2): a real `Guild` lives N days under a policy (`lumber`, `cautious`,
  `balanced`, `games`, `claimer`, `greedy`, `maxev`, `crafter`). Order engine, upkeep and market are
  real; only the fight is a stand-in: a library of real battles keyed by (kind, combat level, work
  level, party size), drawn by outcome with `--skill`.
- `economy_exploits.py`: the detector (market loops, coins, recipes, barriers, levels, route,
  dominance among different roles, conservation fuzz).
- `economy_report.py`: verdicts (floor, Wilds, day-30 milestone, no exploit, no dominant activity),
  then the tables. Exit 1 on any FAIL; today the day-30 milestone fails on purpose ($423 for three,
  lumber affords 38%).

**Why:** the user wants to know if a squad sustains itself and if each activity's risk x time x
reward is right, with exploit hunting first and race / occupation ranking last. The user's targets:
a level-0 squad eats and keeps >= $1 a day on the worst activity; by day 30 it holds 7 days of food,
a weapon, Studded Leather and the bank strongbox; an exploit is a way to become a millionaire for
no reason.

**How to apply:** re-run the report after touching wages, purses, prices or loot (AGENTS.md says so).
Findings worth remembering: a working squad heals 1 HP a night; a garrisoned group never heals; the
Medic as backlog B1 prices it ($16 an HP) is a late-game luxury; the Games are a capital-gated XP
ladder, not income; the Wilds wipe 78-100% of level-3 guilds at 80% skill; the Claim establishes in
13-28% of skilled guilds; a house costs a lumberjack's whole wage; owning an Axe is the biggest
ranking lever (+$10), race and attributes are worthless in the economy. Later findings (same day): the
yard pays by Axe, not by level (work 2 comes ~5 days after the Axe, then Piecework +20%); a lumber
guild with Axe + Piecework meets the $423 milestone in 42% of guilds by day 60, never by day 30;
the yard-Scrapper-Games-Wilds ladder (`climber`) does worse than the yard early because it is
capital-gated; recruiting yields ~1 member a month (language gate, sponsor slots) and a crew at the
yard doubles the squad's bouts. **What NOT to redo / next:** policies are guesses; the planned
fix is a play recorder (backlog) plus three 30-day human runs to derive a `human` policy before
rebalancing wages or the milestone. Related:
[[gartok-wilds-hunting]], [[gartok-property-two-paths]], [[gartok-arena-champion-title]],
[[gartok-arena-ribbit-brothers-boss]].
