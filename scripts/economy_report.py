"""The economy report, in this order (docs/economy_sim.md):

  1. verdicts   pass or fail, each with the number that decides it
  2. exploits   money-from-nothing loops, recipe barriers, dominance (economy_exploits.py)
  3. activities what each job pays in copper and XP (economy_activities.py), each work talent
                priced on its own (economy_talents.py)
  4. sustain    a guild living 30 days under each policy, and its curve (economy_guild.py)
  5. ranking    races, weapons, CHA and languages by what they earned

A player is assumed to turn `--skill` of the AI's losses into wins (`economy_activities.player_odds`,
measured from the author's fights), so a squad a level up wins more for the player as for the AI.
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
import economy_talents as work_talents

MILESTONE_POLICY = "balanced"        # the game played as the author plays it; the milestone is judged on it
MILESTONE_SHARE = 0.5                # of its guilds that must reach it
WILDS_LEVEL = 3
SUSTAIN_POLICIES = ("lumber", "balanced")    # the floor, and the one policy that plays the game
MEDIC_POLICIES = ("balanced",)
LATE_LEVEL = 3                       # a squad that has climbed out of the Scrapper...
LATE_CAPITAL = 250                   # ...and has a first week's savings
LATE_POLICIES = ("balanced",)


@dataclass
class Settings:
    skill: float = act.SKILL
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


def _marks(settings):
    return tuple(d for d in (7, settings.days) if d <= settings.days)


def _guild_jobs(settings, level, policies, **extra):
    marks = _marks(settings)
    return [(name, dict(days=settings.days, seed=settings.seed + i, level=level, skill=settings.skill,
                        marks=marks, **extra))
            for name in policies for i in range(settings.guilds)]


def _by_policy(settings, policies, runs):
    n = settings.guilds
    return {name: runs[k * n:(k + 1) * n] for k, name in enumerate(policies)}


def _table(settings, policies, runs):
    results = _by_policy(settings, policies, runs)
    return results, {name: guild_sim.summarize(r, _marks(settings)) for name, r in results.items()}


def build(settings):
    """-> (the report text, the failed verdicts)."""
    verdicts = []

    # layer 1: the floor at level 0, the Wilds at level 3
    floor_text, floor_checks = _layer1(settings, 0)
    wilds_text, wilds_checks = _layer1(settings, WILDS_LEVEL)
    for text, ok in floor_checks + wilds_checks:
        verdicts.append((("floor" if text.startswith("Lumber") else "wilds"), ok, text))

    # layer 2: the guild, its milestone and its curve. Every guild is its own job, so they all go
    # to the pool in one batch and are sliced back in the order they were listed.
    library = guild_sim.FightLibrary(settings.library_samples)
    marks = _marks(settings)
    ranking_settings = Settings(**{**settings.__dict__, "guilds": settings.ranking_guilds})
    gather_guilds = max(1, settings.guilds // 2)
    sections = [
        ("sustain", _guild_jobs(settings, 0, SUSTAIN_POLICIES)),
        ("medic", _guild_jobs(settings, 0, MEDIC_POLICIES, medic=True)),
        ("late", _guild_jobs(settings, LATE_LEVEL, LATE_POLICIES, capital=LATE_CAPITAL)),
        ("late_medic", _guild_jobs(settings, LATE_LEVEL, LATE_POLICIES, capital=LATE_CAPITAL, medic=True)),
        ("ranking", _guild_jobs(ranking_settings, 0, ("lumber",))),
    ]
    pairs = [(node, size) for size in guild_sim.GATHER_CREWS for node in guild_sim.GATHER_PAIRS]
    for node, size in pairs:
        sections.append((("gather", node, size), guild_sim.gather_jobs(
            node, guilds=gather_guilds, seed=settings.seed, skill=settings.skill,
            level=guild_sim.GATHER_LEVEL, size=size)))
    done = guild_sim.run_guilds([job for _, jobs in sections for job in jobs], library)
    runs, at = {}, 0
    for key, jobs in sections:
        runs[key] = done[at:at + len(jobs)]
        at += len(jobs)

    _, table = _table(settings, SUSTAIN_POLICIES, runs["sustain"])
    _, medic_table = _table(settings, MEDIC_POLICIES, runs["medic"])
    _, late_table = _table(settings, LATE_POLICIES, runs["late"])
    _, late_medic = _table(settings, LATE_POLICIES, runs["late_medic"])
    ranking_results = _by_policy(ranking_settings, ("lumber",), runs["ranking"])
    gathering = [guild_sim.gather_result(node, runs[("gather", node, size)], guilds=gather_guilds,
                                         level=guild_sim.GATHER_LEVEL, size=size)
                 for node, size in pairs]
    share = table[MILESTONE_POLICY]["milestone"]
    start_cost = guild_sim.milestone_cost(guild_sim.Sim(guild_sim.Lumber(), seed=settings.seed))
    verdicts.append(("day-30 milestone", share >= MILESTONE_SHARE,
                     (f"a level-0 squad on the '{MILESTONE_POLICY}' policy can afford a weapon worth "
                      f"{guild_sim.MILESTONE_WEAPON_PRICE}+ and Studded Leather for {guild_sim.MILESTONE_SQUAD} members "
                      f"and keep ${guild_sim.food_fund()} for their food on some day by day "
                      f"{settings.days} in {share * 100:.0f}% of guilds (need >= {MILESTONE_SHARE * 100:.0f}%); "
                      f"the cost starts at ${start_cost}")))

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

    stamp = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC"
    out = [(f"Economy report  {stamp}  "
            f"(a player wins {settings.skill * 100:.0f}% of the fights the AI loses; seed {settings.seed})")]
    out.append(_section("1. VERDICTS", "\n".join(
        f"{'PASS' if ok else 'FAIL'}  {name}: {detail}" for name, ok, detail in verdicts)))
    out.append(_section("2. EXPLOITS", exploits.report(findings)))
    out.append(_section("3. ACTIVITIES, level 0", floor_text))
    out.append(_section(f"3. ACTIVITIES, level {WILDS_LEVEL}", wilds_text))
    out.append(_section("3. THE TAVERN", act.tavern_table()))
    out.append(_section("3. WORK TALENTS", work_talents.report()))
    out.append(_section("3. GATHERING", guild_sim.gather_report(
        gathering, (f"{gather_guilds} guilds a row, level {guild_sim.GATHER_LEVEL}, "
                    f"a player wins {settings.skill * 100:.0f}% of the AI's losses"))))
    label = f"{settings.guilds} guilds of 3, level 0, a player wins {settings.skill * 100:.0f}% of the AI's losses"
    out.append(_section("4. SUSTAIN", guild_sim.report(table, marks, label)
                        + "\n\n" + guild_sim.curve_report(table)
                        + "\n\n" + guild_sim.report(medic_table, marks, label + ", with a Medic")))
    late = (f"{settings.guilds} guilds of 3 at level {LATE_LEVEL} with ${LATE_CAPITAL} "
            f"(a first week behind them), a player wins {settings.skill * 100:.0f}% of the AI's losses")
    out.append(_section(
        "4. PAST THE FIRST WEEK: the arena's ladder, the Claim, the Medic",
        guild_sim.report(late_table, marks, late) + "\n\n"
        + guild_sim.adventure_report(late_table, "without a Medic") + "\n\n"
        + guild_sim.report(late_medic, marks, late + ", with a Medic") + "\n\n"
        + guild_sim.adventure_report(late_medic, "with a Medic")))
    out.append(_section(
        "4. FACTION DEEDS & ADVANCEMENT",
        guild_sim.deeds_report(table, label) + "\n\n"
        + guild_sim.deeds_report(late_table, late)))
    ranked = guild_sim.rank_traits(ranking_results["lumber"], settings.days)
    out.append(_section("5. RANKING", guild_sim.ranking_report(
        ranked, f"lumber, {settings.ranking_guilds} guilds, day {settings.days}")))
    failed = [name for name, ok, _ in verdicts if not ok]
    return "\n".join(out), failed


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true", help="fewer battles and guilds")
    ap.add_argument("--skill", type=float, default=act.SKILL)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", default="sim_results")
    act.add_workers_arg(ap)
    args = ap.parse_args()
    base = QUICK if args.quick else Settings()
    with guild_sim.guild_pool(args.workers):
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
