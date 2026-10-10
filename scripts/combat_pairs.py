"""The AI against the same squads a person played: the win rate to move when `ai.py` changes.

A combat log names its fight, level, squad size and seed, and the seed pins both squads, so the AI can
play exactly the fight the person played, many times over (each trial reseeds the dice the same way,
so a before and an after differ only by the code). Run it before and after an `ai.py` change.

    python scripts/combat_pairs.py combat_lab --trials 100            # every logged fight, person vs AI
    python scripts/combat_pairs.py combat_lab --fight scrapper
    python scripts/combat_pairs.py --fresh scrapper:0:3 --seeds 40    # unseen squads, no person to compare
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


def ai_win_rate(fight, level, squad, seed, trials):
    """Share of `trials` the AI wins as the player's side, both sides driven by `ai.take_turn`."""
    wins = 0
    for t in range(trials):
        battle, _meta = combat_lab.build(fight, level, squad, seed=seed)
        random.seed(DICE_BASE + t)
        for _ in range(MAX_DECISIONS):
            if battle.winner is not None:
                break
            ai.take_turn(battle, battle.active)
        wins += battle.winner == "player"
    return wins / trials


def played(paths, fight=None):
    """`[(name, meta, person_won)]` for every log where a person played the player's side against the AI."""
    out = []
    for path in find_logs(paths):
        rows = combat_log.load(path)
        start = rows[0]
        end = next((r for r in rows if r["e"] == "end"), None)
        meta = start["meta"]
        if start["controllers"] != {"player": "human", "enemy": "ai"} or end is None or not end.get("winner"):
            continue
        if "seed" not in meta or (fight and meta.get("fight") != fight):
            continue
        out.append((os.path.basename(path), meta, end["winner"] == "player"))
    return out


def report_logs(paths, trials, fight=None):
    rows = played(paths, fight)
    if not rows:
        sys.exit("no logged fight with a seed where a person played the player's side against the AI")
    rates = []
    for name, meta, won in rows:
        rate = ai_win_rate(meta["fight"], meta["level"], meta["squad"], meta["seed"], trials)
        rates.append(rate)
        print(f"{name:<34} person {'W' if won else 'L'}   AI on the same squads {rate:.0%}")
    print(f"\nperson {sum(w for *_, w in rows)}/{len(rows)}   AI {mean(rates):.0%} over {trials} trials each")


def report_fresh(spec, seeds, trials):
    fight, level, squad = spec.split(":")
    rng = random.Random(0)
    rates = [ai_win_rate(fight, int(level), int(squad), rng.randrange(1 << 30), trials) for _ in range(seeds)]
    print(f"{fight} level {level}, {squad} a side: AI {mean(rates):.0%} over {seeds} unseen squads x {trials} trials")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="log files or folders")
    ap.add_argument("--trials", type=int, default=60, help="AI replays per fight")
    ap.add_argument("--fight", help="only this fight id (scrapper, brawl, ...)")
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
