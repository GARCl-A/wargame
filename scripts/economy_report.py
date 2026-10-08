"""The economy report, in the plan's order (docs/plans/economy_sim_v2.md):

  1. verdicts   pass or fail, each with the number that decides it
  2. exploits   money-from-nothing loops, recipe barriers, dominance (economy_exploits.py)
  3. activities what each job pays in copper and XP (economy_activities.py)
  4. sustain    a guild living 30 days under each policy, and its curve (economy_guild.py)
  5. ranking    races, occupations, CHA and languages by what they earned

The player is assumed to win `--skill` of the fights (the AI plays much worse than a person).
Exit code 1 if any verdict fails; the report is also written to sim_results/.

    python scripts/economy_report.py                # a few minutes
    python scripts/economy_report.py --quick        # a smoke run, about a minute
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.dirname(SCRIPTS))

import economy_activities as act
import economy_exploits as exploits
import economy_guild as guild_sim

MILESTONE_POLICY = "balanced"        # the sensible play the day-30 milestone is judged on
MILESTONE_SHARE = 0.5                # of its guilds that must reach it
WILDS_LEVEL = 3
SUSTAIN_POLICIES = ("lumber", "cautious", "balanced", "greedy", "maxev", "rush", "games", "climber", "human")
MEDIC_POLICIES = ("cautious", "balanced", "greedy")
LATE_LEVEL = 3                       # a squad that has climbed out of the Scrapper...
LATE_CAPITAL = 250                   # ...and has a first week's savings
LATE_POLICIES = ("balanced", "games", "claimer")


@dataclass
class Settings:
    skill: float = 0.8
    trials: int = 150            # battles per layer-1 activity
    guilds: int = 40             # per policy, layer 2
    ranking_guilds: int = 200
    fuzz: int = 200
    dominance_trials: int = 40
    library_samples: int = 40    # real battles kept per kind, level and party size, layer 2
    days: int = 30
    seed: int = 0


QUICK = Settings(trials=25, guilds=10, ranking_guilds=40, fuzz=40, dominance_trials=10,
                 library_samples=12)


def _section(title, body):
    return f"\n{'=' * 78}\n{title}\n{'=' * 78}\n{body}"


def _layer1(settings, level):
    random.seed(settings.seed)
    meal, tables = act.build_tables(level, 3, settings.trials, [settings.skill])
    text, checks = [], []
    for skill, label, rows in tables:
        body, _ = act.report(rows, meal, 3, level, label)
        text.append(body)
        if skill == settings.skill:
            checks = act.judge(rows, meal, level)
    return "\n\n".join(text), checks


def _layer2(settings, level, policies, library=None, **extra):
    library = library or guild_sim.FightLibrary(settings.library_samples)
    marks = tuple(d for d in (7, settings.days) if d <= settings.days)
    results = {}
    for name in policies:
        results[name] = [guild_sim.run_guild(name, days=settings.days, seed=settings.seed + i,
                                             level=level, skill=settings.skill, library=library,
                                             marks=marks, **extra)
                         for i in range(settings.guilds)]
    table = {name: guild_sim.summarize(runs, marks) for name, runs in results.items()}
    return results, table, marks


def build(settings):
    """-> (the report text, the failed verdicts)."""
    verdicts = []

    # layer 1: the floor at level 0, the Wilds at level 3
    floor_text, floor_checks = _layer1(settings, 0)
    wilds_text, wilds_checks = _layer1(settings, WILDS_LEVEL)
    for text, ok in floor_checks + wilds_checks:
        verdicts.append((("floor" if text.startswith("Lumber") else "wilds"), ok, text))

    # layer 2: the guild, its milestone and its curve
    library = guild_sim.FightLibrary(settings.library_samples)
    _, table, marks = _layer2(settings, 0, SUSTAIN_POLICIES, library)
    _, medic_table, _ = _layer2(settings, 0, MEDIC_POLICIES, library, medic=True)
    _, late_table, _ = _layer2(settings, LATE_LEVEL, LATE_POLICIES, library, capital=LATE_CAPITAL)
    _, late_medic, _ = _layer2(settings, LATE_LEVEL, LATE_POLICIES, library, capital=LATE_CAPITAL,
                               medic=True)
    share = table[MILESTONE_POLICY]["milestone"]
    start_cost = guild_sim.milestone_cost(guild_sim.Sim(guild_sim.Lumber(), seed=settings.seed))
    verdicts.append(("day-30 milestone", share >= MILESTONE_SHARE,
                     (f"a level-0 squad on the '{MILESTONE_POLICY}' policy affords food for 7 days, "
                      f"a weapon and Studded Leather each and the strongbox in {share * 100:.0f}% of "
                      f"guilds at day {settings.days} (need >= {MILESTONE_SHARE * 100:.0f}%); the "
                      f"cost starts at ${start_cost}")))

    # the detector
    findings = exploits.run_all(settings.fuzz, settings.seed, settings.dominance_trials)
    bad = [f for f in findings if f.severity == exploits.EXPLOIT]
    verdicts.append(("no exploit", not bad,
                     "no money-from-nothing loop" if not bad
                     else "; ".join(f"[{f.area}] {f.subject}" for f in bad)))
    clash = [f for f in findings if f.area == "dominance" and f.severity == exploits.DESIGN]
    verdicts.append(("no dominant activity", not clash,
                     "no activity beats another on copper and XP at no more risk" if not clash
                     else "; ".join(f.subject for f in clash)))

    ranking_results, _, _ = _layer2(
        Settings(**{**settings.__dict__, "guilds": settings.ranking_guilds}), 0, ("lumber",))

    stamp = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC"
    out = [(f"Economy report  {stamp}  "
            f"(player wins {settings.skill * 100:.0f}% of fights; seed {settings.seed})")]
    out.append(_section("1. VERDICTS", "\n".join(
        f"{'PASS' if ok else 'FAIL'}  {name}: {detail}" for name, ok, detail in verdicts)))
    out.append(_section("2. EXPLOITS", exploits.report(findings)))
    out.append(_section("3. ACTIVITIES, level 0", floor_text))
    out.append(_section(f"3. ACTIVITIES, level {WILDS_LEVEL}", wilds_text))
    out.append(_section("3. THE TAVERN", act.tavern_table()))
    label = f"{settings.guilds} guilds of 3, level 0, a player wins {settings.skill * 100:.0f}%"
    out.append(_section("4. SUSTAIN", guild_sim.report(table, marks, label)
                        + "\n\n" + guild_sim.curve_report(table)
                        + "\n\n" + guild_sim.report(medic_table, marks, label + ", with a Medic")))
    late = (f"{settings.guilds} guilds of 3 at level {LATE_LEVEL} with ${LATE_CAPITAL} "
            f"(a first week behind them), a player wins {settings.skill * 100:.0f}%")
    out.append(_section(
        "4. PAST THE FIRST WEEK: the arena's ladder, the Claim, the Medic",
        guild_sim.report(late_table, marks, late) + "\n\n"
        + guild_sim.adventure_report(late_table, "without a Medic") + "\n\n"
        + guild_sim.report(late_medic, marks, late + ", with a Medic") + "\n\n"
        + guild_sim.adventure_report(late_medic, "with a Medic")))
    ranked = guild_sim.rank_traits(ranking_results["lumber"], settings.days)
    out.append(_section("5. RANKING", guild_sim.ranking_report(
        ranked, f"lumber, {settings.ranking_guilds} guilds, day {settings.days}")))
    failed = [name for name, ok, _ in verdicts if not ok]
    return "\n".join(out), failed


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true", help="fewer battles and guilds")
    ap.add_argument("--skill", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", default="sim_results")
    args = ap.parse_args()
    base = QUICK if args.quick else Settings()
    text, failed = build(Settings(**{**base.__dict__, "skill": args.skill, "seed": args.seed}))
    print(text)
    os.makedirs(args.out_dir, exist_ok=True)
    path = os.path.join(args.out_dir, f"economy-report-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print(f"\nwritten to {path}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
