"""The AI against the same squads a person played: the win rate to move when `ai.py` changes.

Each log is put back at its opening (`combat_log.rebuild`: the same characters, board and cells), and
the AI plays it many times over, both sides driven by `ai.py`. Each trial reseeds the dice the same way,
so a before and an after differ only by the code. Run it before and after an `ai.py` change. Campaign
fights (`saves/<world>/combat_logs`) and lab fights both work; a fight with an objective of its own
(flags, the Ruins) is skipped. `--fresh` plays unseen lab squads instead.

    python scripts/combat_pairs.py combat_lab --trials 100
    python scripts/combat_pairs.py saves/<world>/combat_logs --fight hunt
    python scripts/combat_pairs.py --fresh scrapper:0:3 --seeds 40
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from combat_analysis import find_logs
from gartok import ai, combat_lab, combat_log

DICE_BASE = 10_000
MAX_DECISIONS = 400


def ai_win_rate(make_battle, trials):
    """Share of `trials` the AI wins as the player's side, both sides driven by `ai.take_turn`."""
    wins = 0
    for t in range(trials):
        battle = make_battle()
        random.seed(DICE_BASE + t)
        for _ in range(MAX_DECISIONS):
            if battle.winner is not None:
                break
            ai.take_turn(battle, battle.active)
        wins += battle.winner == "player"
    return wins / trials


def fight_name(rows):
    meta = rows[0]["meta"]
    return meta.get("fight") or meta.get("kind") or "?"


def played(paths, fight=None):
    """`([(name, rows, person_won)], skipped)` for every finished log where a person played the
    player's side against the AI; `skipped` counts the ones whose scenario cannot be rebuilt."""
    out, skipped = [], 0
    for path in find_logs(paths):
        rows = combat_log.load(path)
        end = next((r for r in rows if r["e"] == "end"), None)
        if rows[0]["controllers"] != {"player": "human", "enemy": "ai"} or end is None or not end.get("winner"):
            continue
        if fight and fight_name(rows) != fight:
            continue
        if rows[0]["scenario"] not in combat_log.REPLAYABLE:
            skipped += 1
            continue
        out.append((os.path.basename(path), rows, end["winner"] == "player"))
    return out, skipped


def drift(rows):
    """Names of the units whose rebuilt HP, AC or speed differ from what the log says they had: a
    character saved after a stat went stale (see the sickness note in the backlog) comes back different."""
    battle = combat_log.rebuild(rows)
    return [static["name"] for static, unit in zip(rows[0]["units"], battle.units)
            if (static["hp_max"], static["ac"], static["speed"]) != (unit.hp_max, unit.ac, unit.speed)]


def report_logs(paths, trials, fight=None):
    found, skipped = played(paths, fight)
    if not found:
        sys.exit("no finished log where a person played the player's side against the AI")
    by_fight = {}
    for name, rows, won in found:
        rate = ai_win_rate(lambda rows=rows: combat_log.rebuild(rows), trials)
        drifted = drift(rows)
        by_fight.setdefault(fight_name(rows), []).append((rate, won))
        print(f"{name:<38} person {'W' if won else 'L'}   AI on the same squads {rate:>4.0%}"
              + (f"   (stats differ: {', '.join(drifted)})" if drifted else ""))
    print()
    for kind, rs in by_fight.items():
        print(f"{kind:<22} person {sum(w for _, w in rs)}/{len(rs)}   AI {mean(r for r, _ in rs):.0%}")
    print(f"AI over {trials} trials per fight" + (f"; {skipped} log(s) skipped (an objective of their own)" if skipped else ""))


def report_fresh(spec, seeds, trials):
    fight, level, squad = spec.split(":")
    rng = random.Random(0)
    rates = [ai_win_rate(lambda seed=rng.randrange(1 << 30): combat_lab.build(fight, int(level), int(squad), seed=seed)[0],
                         trials) for _ in range(seeds)]
    print(f"{fight} level {level}, {squad} a side: AI {mean(rates):.0%} over {seeds} unseen squads x {trials} trials")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="log files or folders")
    ap.add_argument("--trials", type=int, default=60, help="AI replays per fight")
    ap.add_argument("--fight", help="only this fight (scrapper, brawl, hunt, ambush, ...)")
    ap.add_argument("--fresh", metavar="FIGHT:LEVEL:SQUAD", help="unseen squads instead of the logged ones")
    ap.add_argument("--seeds", type=int, default=30, help="how many unseen squads with --fresh")
    args = ap.parse_args()
    if args.fresh:
        report_fresh(args.fresh, args.seeds, args.trials)
    elif args.paths:
        report_logs(args.paths, args.trials, args.fight)
    else:
        ap.error("give log paths or --fresh")


if __name__ == "__main__":
    main()
