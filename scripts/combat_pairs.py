"""The AI against the same squads a person played: the win rate to move when `ai.py` changes.

Each log is put back at its opening (`combat_log.rebuild`: the same characters, board and cells), and
the AI plays it many times over, both sides driven by `ai.py`. Each trial reseeds the dice the same way,
so a before and an after differ only by the code. Run it before and after an `ai.py` change. Campaign
fights (`saves/<world>/combat_logs`) and lab fights both work; a fight with an objective of its own
(the Ruins, a mission's) is skipped; capture the flag comes back with both flags planted. `--fresh`
plays unseen lab squads instead. Besides the win rate it counts the player's side's dead a fight.

`--set NAME=VALUE` changes one of `ai.py`'s thresholds for the player's side only (the other side
plays the code as it is), so a threshold is weighed head to head; `FLAG_RUNNERS` retags the
player's runners (`battle.tag_flag_runners`).

    python scripts/combat_pairs.py combat_lab --trials 100
    python scripts/combat_pairs.py saves/<world>/combat_logs --fight hunt
    python scripts/combat_pairs.py combat_lab/campaign --set FLEE_HP=0.34 --set FLEE_OUTNUMBERED=0
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
from gartok import battle as battle_mod

DICE_BASE = 10_000
MAX_DECISIONS = 400


def _turn(overrides):
    """`ai.take_turn` with `overrides` (NAME -> value of `ai`'s module constants) in force on the
    player's side's turns only."""
    if not overrides:
        return ai.take_turn
    base = {name: getattr(ai, name) for name in overrides}

    def turn(battle, unit):
        for name, value in (overrides if unit.team == "player" else base).items():
            setattr(ai, name, value)
        try:
            ai.take_turn(battle, unit)
        finally:
            for name, value in base.items():
                setattr(ai, name, value)
    return turn


def ai_win_rate(make_battle, trials, overrides=None):
    """`(wins, dead)`: the share of `trials` the AI wins as the player's side, both sides driven by
    `ai.take_turn`, and the player's side's dead a trial."""
    overrides = dict(overrides or {})
    runners = overrides.pop("FLAG_RUNNERS", None)
    turn = _turn(overrides)
    wins = dead = 0
    for t in range(trials):
        random.seed(DICE_BASE + t)
        battle = make_battle()
        if runners is not None and battle.is_ctf:
            battle_mod.tag_flag_runners(battle.player_units, runners)
        for _ in range(MAX_DECISIONS):
            if battle.winner is not None:
                break
            turn(battle, battle.active)
        wins += battle.winner == "player"
        dead += sum(1 for u in battle.player_units if u.dead)
    return wins / trials, dead / trials


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


def report_logs(paths, trials, fight=None, overrides=None):
    found, skipped = played(paths, fight)
    if not found:
        sys.exit("no finished log where a person played the player's side against the AI")
    by_fight = {}
    for name, rows, won in found:
        rate, dead = ai_win_rate(lambda rows=rows: combat_log.rebuild(rows), trials, overrides)
        drifted = drift(rows)
        by_fight.setdefault(fight_name(rows), []).append((rate, dead, won))
        print(f"{name:<38} person {'W' if won else 'L'}   AI on the same squads {rate:>4.0%}  dead {dead:.2f}"
              + (f"   (stats differ: {', '.join(drifted)})" if drifted else ""))
    print()
    for kind, rs in by_fight.items():
        print(f"{kind:<22} person {sum(w for *_, w in rs)}/{len(rs)}   AI {mean(r for r, *_ in rs):.0%}"
              f"   dead {mean(d for _, d, _ in rs):.2f}")
    print(f"AI over {trials} trials per fight" + (f"; {skipped} log(s) skipped (an objective of their own)" if skipped else "")
          + (f"; player's side with {overrides}" if overrides else ""))


def report_fresh(spec, seeds, trials, overrides=None):
    fight, level, squad = spec.split(":")
    rng = random.Random(0)
    rates = [ai_win_rate(lambda seed=rng.randrange(1 << 30): combat_lab.build(fight, int(level), int(squad), seed=seed)[0],
                         trials, overrides)[0] for _ in range(seeds)]
    print(f"{fight} level {level}, {squad} a side: AI {mean(rates):.0%} over {seeds} unseen squads x {trials} trials")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="log files or folders")
    ap.add_argument("--trials", type=int, default=60, help="AI replays per fight")
    ap.add_argument("--fight", help="only this fight (scrapper, brawl, hunt, ambush, ...)")
    ap.add_argument("--fresh", metavar="FIGHT:LEVEL:SQUAD", help="unseen squads instead of the logged ones")
    ap.add_argument("--seeds", type=int, default=30, help="how many unseen squads with --fresh")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                    help="an ai.py threshold for the player's side only (repeatable)")
    args = ap.parse_args()
    overrides = {}
    for item in args.set:
        name, _, value = item.partition("=")
        if name != "FLAG_RUNNERS" and not hasattr(ai, name):
            ap.error(f"ai.py has no {name}")
        overrides[name] = float(value) if "." in value else int(value)
    if args.fresh:
        report_fresh(args.fresh, args.seeds, args.trials, overrides)
    elif args.paths:
        report_logs(args.paths, args.trials, args.fight, overrides)
    else:
        ap.error("give log paths or --fresh")


if __name__ == "__main__":
    main()
