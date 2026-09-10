"""Balance tournament: which races, occupations and race/occupation combos win.

Headless AI-vs-AI. Every battle pits a homogeneous squad of one archetype against
a homogeneous squad of another -- so the win is credited cleanly to an archetype,
and racial abilities that need same-race allies (Goblin pack tactics, flanking)
still get to fire. Attributes / alignment / starting gold are re-rolled for every
clone, so what is being measured is the archetype (race mods + ability + the
occupation's weapon/item), averaged over the 3d6 noise.

Fighters are level 0 with no talents -- this is the raw creation-stat baseline,
the thing to balance before progression piles on top.

One random sweep feeds all three questions at once: a battle between a
`(race, occ)` and a `(race', occ')` squad is simultaneously a race-vs-race and an
occupation-vs-occupation result, so the race / occupation / combo Elo pools all
come out of the same games.

    python balance_sim.py                          # 20k battles, race/occ ranking, ~1 min
    python balance_sim.py --battles 60000          # tighter combo numbers too
    python balance_sim.py --scenario arena         # dark cluttered pit
    python balance_sim.py --scenario the-pit       # a hand-authored map (walls + a pit)

Writes a text report + JSON + CSVs under sim_results/ and prints the report.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone

from gartok import ai, data, map_lib
from gartok.battle import Battle
from gartok.scenario import ArenaScenario, CustomScenario, ErmosScenario
from gartok.unit import Unit

RACES = list(data.RACE_NAMES)
OCCUPATIONS = list(data.OCCUPATION_NAMES)
COMBOS = [(r, o) for r in RACES for o in OCCUPATIONS]

GUARD = 600                # per-battle turn-cap; a real 3v3 ends in ~15 rounds
                           # (~90 turns), so anything near this is a stalemate
                           # (neither AI can close) -- scored as a draw.


# --------------------------------------------------------------------------- #
# one battle                                                                  #
# --------------------------------------------------------------------------- #
def _squad(combo, team, size):
    race, occ = combo
    squad = []
    for _ in range(size):
        u = Unit(team)
        u.set_race(race)
        u.set_occupation(occ)
        squad.append(u)
    return squad


def _scenario(name):
    """`ermos` (open country), `arena` (dark cluttered pit), or any map slug from
    `map_lib` (a hand-authored board -- fixed walls, torches, pit, deploy zones)."""
    if name == "arena":
        return ArenaScenario()
    if name == "ermos":
        return ErmosScenario()
    return CustomScenario(map_lib.load_map(name))


def run_battle(combo_a, combo_b, seed, size, scenario_name, daylight):
    """Play combo_a (player side) vs combo_b (enemy side). Returns
    ('A' | 'B' | 'draw', rounds)."""
    random.seed(seed)
    a = _squad(combo_a, "player", size)
    b = _squad(combo_b, "enemy", size)
    battle = Battle(a, b, scenario=_scenario(scenario_name), daylight=daylight)
    guard = 0
    while battle.winner is None and guard < GUARD:
        guard += 1
        ai.take_turn(battle, battle.active)
    if battle.winner == "player":
        return "A", battle.round_no
    if battle.winner == "enemy":
        return "B", battle.round_no
    return "draw", battle.round_no


# --------------------------------------------------------------------------- #
# worker: a slice of the matchup list                                         #
# --------------------------------------------------------------------------- #
def _work(chunk):
    size, scenario_name, daylight, jobs = chunk
    out = []
    for combo_a, combo_b, seed in jobs:
        result, rounds = run_battle(combo_a, combo_b, seed, size, scenario_name, daylight)
        out.append((combo_a, combo_b, result, rounds))
    return out


# --------------------------------------------------------------------------- #
# Elo over a list of (key_a, key_b, score_a)  (score in {1, 0.5, 0})          #
# --------------------------------------------------------------------------- #
def elo(games, *, k_passes=(24, 16, 10, 6), base=1500.0):
    rating = defaultdict(lambda: base)
    rng = random.Random(1234)
    for k in k_passes:
        order = list(games)
        rng.shuffle(order)
        for a, b, sa in order:
            ra, rb = rating[a], rating[b]
            ea = 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))
            rating[a] = ra + k * (sa - ea)
            rating[b] = rb + k * ((1.0 - sa) - (1.0 - ea))
    return dict(rating)


# --------------------------------------------------------------------------- #
# aggregation                                                                 #
# --------------------------------------------------------------------------- #
class Tally:
    __slots__ = ("w", "l", "d")

    def __init__(self):
        self.w = self.l = self.d = 0

    @property
    def n(self):
        return self.w + self.l + self.d

    @property
    def winrate(self):
        return self.w / self.n if self.n else 0.0

    @property
    def score(self):                       # draws count as half
        return (self.w + 0.5 * self.d) / self.n if self.n else 0.0


def _wilson_lo(tally, z=1.96):
    """Lower bound of the Wilson 95% interval on the score -- a rank-by that
    doesn't reward a combo for having been sampled less."""
    n = tally.n
    if not n:
        return 0.0
    p = tally.score
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return (centre - margin) / denom


def aggregate(results):
    combo = defaultdict(Tally)
    race = defaultdict(Tally)
    occ = defaultdict(Tally)
    combo_games, race_games, occ_games = [], [], []
    rounds = []
    side = Counter()               # did the player (side A) or enemy (side B) win

    for combo_a, combo_b, result, r in results:
        rounds.append(r)
        ra, oa = combo_a
        rb, ob = combo_b
        sa = {"A": 1.0, "B": 0.0, "draw": 0.5}[result]
        side[result] += 1

        # combo tallies
        for c, is_a in ((combo_a, True), (combo_b, False)):
            t = combo[c]
            won = (result == "A") == is_a
            if result == "draw":
                t.d += 1
            elif won:
                t.w += 1
            else:
                t.l += 1
        combo_games.append((combo_a, combo_b, sa))

        # race marginal (skip race mirrors -- no signal)
        if ra != rb:
            for rc, is_a in ((ra, True), (rb, False)):
                t = race[rc]
                if result == "draw":
                    t.d += 1
                elif (result == "A") == is_a:
                    t.w += 1
                else:
                    t.l += 1
            race_games.append((ra, rb, sa))

        # occupation marginal (skip occ mirrors)
        if oa != ob:
            for oc, is_a in ((oa, True), (ob, False)):
                t = occ[oc]
                if result == "draw":
                    t.d += 1
                elif (result == "A") == is_a:
                    t.w += 1
                else:
                    t.l += 1
            occ_games.append((oa, ob, sa))

    return {
        "combo": combo, "race": race, "occ": occ,
        "combo_games": combo_games, "race_games": race_games, "occ_games": occ_games,
        "rounds": rounds, "side": side,
    }


# --------------------------------------------------------------------------- #
# report                                                                      #
# --------------------------------------------------------------------------- #
def _bar(x, lo=0.30, hi=0.70, width=20):
    frac = max(0.0, min(1.0, (x - lo) / (hi - lo)))
    fill = round(frac * width)
    return "#" * fill + "." * (width - fill)


def build_report(agg, cfg):
    combo_elo = elo(agg["combo_games"])
    race_elo = elo(agg["race_games"])
    occ_elo = elo(agg["occ_games"])

    L = []
    p = L.append
    p("=" * 78)
    p("GARTOK BALANCE TOURNAMENT")
    p("=" * 78)
    p(f"generated   : {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    p(f"battles     : {cfg['battles']}  ({cfg['team_size']}v{cfg['team_size']}, "
      f"scenario={cfg['scenario']}, daylight={cfg['daylight']})")
    n = len(agg["rounds"])
    draws = agg["side"]["draw"]
    p(f"rounds      : avg {sum(agg['rounds'])/n:.2f}  max {max(agg['rounds'])}")
    p(f"draws       : {draws} ({draws/n:.1%})   (turn-cap {GUARD} or mutual wipe)")
    p(f"side bias   : side-A (player/left) won {agg['side']['A']/n:.1%} of decisive-or-not battles")
    p("")
    p("Method: homogeneous squad vs homogeneous squad, fresh 3d6 rolls per clone,")
    p("level 0, no talents. Elo from the same games, three ways (K-passes 24>16>10>6).")
    p("'score' counts a draw as half. Win% is decisive wins / games.")

    def table(title, ratings, tally, keys, note=""):
        p("")
        p("-" * 78)
        p(title + (f"   {note}" if note else ""))
        p("-" * 78)
        p(f"{'':4}{'name':<16}{'Elo':>6}{'score':>8}{'win%':>7}{'games':>8}   trend")
        ranked = sorted(keys, key=lambda kk: ratings.get(kk, 1500.0), reverse=True)
        for i, kk in enumerate(ranked, 1):
            t = tally[kk]
            label = kk if isinstance(kk, str) else f"{kk[0]} {kk[1]}"
            p(f"{i:<4}{label:<16}{ratings.get(kk,1500.0):>6.0f}"
              f"{t.score:>8.3f}{t.winrate:>7.1%}{t.n:>8}   {_bar(t.score)}")

    table("RACES  (occupation randomised out)", race_elo, agg["race"], RACES)
    table("OCCUPATIONS  (race randomised out)", occ_elo, agg["occ"], OCCUPATIONS)

    # combos: need a minimum sample; rank by Wilson lower bound so thin cells
    # don't float to the top on variance
    min_games = cfg["min_combo_games"]
    solid = [c for c in COMBOS if agg["combo"][c].n >= min_games]
    p("")
    p("-" * 78)
    p(f"COMBO EXTREMES   (>= {min_games} games each; {len(solid)}/{len(COMBOS)} combos qualify)")
    p("ranked by Wilson-95%-low score, so under-sampled cells can't spike")
    p("-" * 78)
    by_lo = sorted(solid, key=lambda c: _wilson_lo(agg["combo"][c]), reverse=True)

    def combo_row(c):
        t = agg["combo"][c]
        return (f"  {c[0]+' '+c[1]:<24}{combo_elo.get(c,1500):>6.0f}"
                f"{t.score:>8.3f}{t.winrate:>7.1%}{t.n:>7}   lo={_wilson_lo(t):.3f}  {_bar(t.score)}")

    p("STRONGEST 20:")
    for c in by_lo[:20]:
        p(combo_row(c))
    p("")
    p("WEAKEST 20:")
    for c in by_lo[-20:][::-1]:
        p(combo_row(c))

    # interaction: combo score vs an additive race+occ model
    overall = sum(t.score * t.n for t in agg["combo"].values()) / \
              sum(t.n for t in agg["combo"].values())
    race_mean = {r: agg["race"][r].score for r in RACES}
    occ_mean = {o: agg["occ"][o].score for o in OCCUPATIONS}
    resid = []
    for c in solid:
        pred = race_mean[c[0]] + occ_mean[c[1]] - overall
        resid.append((c, agg["combo"][c].score - pred))
    resid.sort(key=lambda x: x[1])
    p("")
    p("-" * 78)
    p("INTERACTION  (combo score minus additive race+occ prediction)")
    p("positive = the pairing is worth more than its parts; negative = anti-synergy")
    p("-" * 78)
    p("STRONGEST SYNERGY:")
    for c, dv in resid[::-1][:12]:
        p(f"  {c[0]+' '+c[1]:<24}{dv:+.3f}   (combo {agg['combo'][c].score:.3f})")
    p("")
    p("STRONGEST ANTI-SYNERGY:")
    for c, dv in resid[:12]:
        p(f"  {c[0]+' '+c[1]:<24}{dv:+.3f}   (combo {agg['combo'][c].score:.3f})")

    p("")
    p("=" * 78)
    return "\n".join(L), {
        "combo_elo": {f"{k[0]}|{k[1]}": v for k, v in combo_elo.items()},
        "race_elo": race_elo, "occ_elo": occ_elo,
    }


# --------------------------------------------------------------------------- #
# driver                                                                      #
# --------------------------------------------------------------------------- #
def make_jobs(battles, seed):
    rng = random.Random(seed)
    jobs = []
    for i in range(battles):
        a = (rng.choice(RACES), rng.choice(OCCUPATIONS))
        b = (rng.choice(RACES), rng.choice(OCCUPATIONS))
        while b == a:
            b = (rng.choice(RACES), rng.choice(OCCUPATIONS))
        jobs.append((a, b, rng.randrange(2**31)))
    return jobs


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--battles", type=int, default=20000,
                    help="20k: solid race/occ ranking in ~1 min. 60k: tight combos too.")
    ap.add_argument("--team-size", type=int, default=3)
    ap.add_argument("--scenario", default="ermos",
                    help="ermos | arena | a map slug from map_lib (e.g. the-pit)")
    ap.add_argument("--daylight", type=lambda s: s.lower() != "false", default=True,
                    help="ermos only: True = fought by day (default), False = night")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--min-combo-games", type=int, default=0,
                    help="0 = auto (max(30, battles/#combos * 0.6))")
    ap.add_argument("--out-dir", default="sim_results")
    args = ap.parse_args()

    if args.min_combo_games == 0:
        args.min_combo_games = max(30, round(args.battles * 2 / len(COMBOS) * 0.6))

    cfg = {
        "battles": args.battles, "team_size": args.team_size,
        "scenario": args.scenario, "daylight": args.daylight,
        "min_combo_games": args.min_combo_games, "seed": args.seed,
    }

    print(f"planning {args.battles} battles on {args.workers} workers ...")
    jobs = make_jobs(args.battles, args.seed)

    n_chunks = args.workers * 8
    size = math.ceil(len(jobs) / n_chunks)
    chunks = [(args.team_size, args.scenario, args.daylight, jobs[i:i + size])
              for i in range(0, len(jobs), size)]

    t0 = time.time()
    results = []
    done = 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for part in ex.map(_work, chunks):
            results.extend(part)
            done += 1
            frac = done / len(chunks)
            el = time.time() - t0
            eta = el / frac - el
            print(f"  {done}/{len(chunks)} chunks  ({frac:.0%})  "
                  f"elapsed {el:.0f}s  eta {eta:.0f}s", flush=True)
    print(f"done in {time.time()-t0:.0f}s")

    agg = aggregate(results)
    report, elos = build_report(agg, cfg)
    print("\n" + report)

    os.makedirs(args.out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tag = f"{args.scenario}{'-night' if not args.daylight else ''}-{args.battles}-{stamp}"

    rep_path = os.path.join(args.out_dir, f"balance-{tag}.txt")
    with open(rep_path, "w", encoding="utf-8") as f:
        f.write(report + "\n")

    with open(os.path.join(args.out_dir, f"balance-{tag}.json"), "w", encoding="utf-8") as f:
        json.dump({
            "config": cfg,
            "elo": elos,
            "race": {r: vars_of(agg["race"][r]) for r in RACES},
            "occ": {o: vars_of(agg["occ"][o]) for o in OCCUPATIONS},
            "combo": {f"{r}|{o}": vars_of(agg["combo"][(r, o)]) for r, o in COMBOS},
        }, f, indent=2)

    for name, keys, tally in (("race", RACES, agg["race"]),
                              ("occ", OCCUPATIONS, agg["occ"]),
                              ("combo", COMBOS, agg["combo"])):
        with open(os.path.join(args.out_dir, f"balance-{tag}-{name}.csv"),
                  "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["key", "games", "wins", "losses", "draws", "winrate", "score",
                        "wilson_lo", "elo"])
            elo_map = elos[f"{name}_elo"] if name != "combo" else elos["combo_elo"]
            for kk in keys:
                t = tally[kk]
                label = kk if isinstance(kk, str) else f"{kk[0]}|{kk[1]}"
                w.writerow([label, t.n, t.w, t.l, t.d, f"{t.winrate:.4f}",
                            f"{t.score:.4f}", f"{_wilson_lo(t):.4f}",
                            f"{elo_map.get(label, 1500):.1f}"])

    print(f"\nreport  -> {rep_path}")
    print(f"json/csv-> {args.out_dir}/balance-{tag}*")


def vars_of(t):
    return {"games": t.n, "wins": t.w, "losses": t.l, "draws": t.d,
            "winrate": round(t.winrate, 4), "score": round(t.score, 4),
            "wilson_lo": round(_wilson_lo(t), 4)}


if __name__ == "__main__":
    main()
