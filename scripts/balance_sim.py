"""Balance tournament: which races, occupations and race/occupation combos win.

Headless AI-vs-AI. Every battle pits a homogeneous squad of one archetype against
a homogeneous squad of another -- so the win is credited cleanly to an archetype,
and racial abilities that need same-race allies (Goblin pack tactics, flanking)
still get to fire. Attributes / alignment / starting gold are re-rolled for every
clone, so what is being measured is the archetype (race mods + ability + the
occupation's weapon/item), averaged over the 3d6 noise.

Fighters are level 0 with no talents by default -- the raw creation-stat baseline.
`--level N` raises combat and work to N, `--racial N` pins the racial level (hit
dice + racial pick, which unlocks at 5); talents are then picked at random from
the trees, and a TALENTS section ranks each one by how much better than its
race + occupation predicts the units holding it did.

One random sweep feeds all three questions at once: a battle between a
`(race, occ)` and a `(race', occ')` squad is simultaneously a race-vs-race and an
occupation-vs-occupation result, so the race / occupation / combo Elo pools all
come out of the same games.

    python scripts/balance_sim.py                          # 20k battles, race/occ ranking, ~1 min
    python scripts/balance_sim.py --battles 60000          # tighter combo numbers too
    python scripts/balance_sim.py --racial 5               # level-0 fighters + a racial talent
    python scripts/balance_sim.py --level 5                # combat 5 / work 5 (racial 5 derived)
    python scripts/balance_sim.py --scenario arena         # dark cluttered pit
    python scripts/balance_sim.py --scenario the-pit       # a hand-authored map (walls + a pit)

Writes a text report + JSON + CSVs under sim_results/ and prints the report.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gartok import ai, data, items, map_lib, talents
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
def spend_picks(u):
    """Random talent picks that respect each tree, until the unit has none left."""
    for track in talents.TRACKS:
        tree = (talents.TREE[track] if track in talents.XP_TRACKS
                else talents.racial_tree(u.race["name"]))
        while u.picks_available(track) > 0:
            picked = u.talents[track]
            options = [t.id for t in tree if t.id not in picked
                       and (t.requires is None or t.requires in picked)]
            if not options:
                break
            u.choose_talent(track, random.choice(options))


class Build(NamedTuple):
    """How far a fighter is levelled and kitted out. `gear`: `starting` (the
    occupation's own weapon only), `best` (highest damage die + best armor and
    shield the unit can use) or `random` (a random usable weapon, armor, shield)."""
    combat: int = 0
    work: int = 0
    racial: int | None = None
    gear: str = "starting"


def give_gear(u, mode):
    """Kit `u` out from the whole catalog (crossbows excluded: no quiver here).
    Runs after talents, so Giant's Grip opens the Large weapons."""
    if mode == "starting":
        return
    best = mode == "best"
    pool = [w for w in items.weapons().values() if not w.reload and u.can_wield(w.name)]
    weapon = max(pool, key=lambda w: (w.damage[0] * (w.damage[1] + 1) / 2, w.price)) if best else random.choice(pool)
    u.give_to_hand(weapon.name)
    shields = [i for i in items.all_items().values() if items.is_shield(i.name)]
    if weapon.hands == 1 and shields and (best or random.random() < 0.5):
        u.give_to_offhand(random.choice(shields).name)
    armors = list(items.armor().values())
    if best:
        u.give_to_armor(max(armors, key=lambda a: a.ac).name)
    elif random.random() < 2 / 3:
        u.give_to_armor(random.choice(armors).name)


def _squad(combo, team, size, build):
    race, occ = combo
    combat, work, racial, gear = build
    squad = []
    for _ in range(size):
        u = Unit(team)
        u.set_race(race)
        u.set_occupation(occ)
        if combat:
            u.set_track_level("combat", combat)
        if work:
            u.set_track_level("work", work)
        if racial is not None:
            u.set_track_level("racial", racial)
        spend_picks(u)
        give_gear(u, gear)
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


def run_battle(combo_a, combo_b, seed, size, scenario_name, daylight, levels=None):
    """Play combo_a (player side) vs combo_b (enemy side). Returns
    ('A' | 'B' | 'draw', rounds, talents_a, talents_b) -- the talent ids each
    unit of a side ended up with."""
    random.seed(seed)
    levels = levels or Build()
    a = _squad(combo_a, "player", size, levels)
    b = _squad(combo_b, "enemy", size, levels)
    tal_a = [tuple(t for tr in talents.TRACKS for t in u.talents[tr]) for u in a]
    tal_b = [tuple(t for tr in talents.TRACKS for t in u.talents[tr]) for u in b]
    battle = Battle(a, b, scenario=_scenario(scenario_name), daylight=daylight)
    guard = 0
    while battle.winner is None and guard < GUARD:
        guard += 1
        ai.take_turn(battle, battle.active)
    result = {"player": "A", "enemy": "B"}.get(battle.winner, "draw")
    return result, battle.round_no, tal_a, tal_b


# --------------------------------------------------------------------------- #
# worker: a slice of the matchup list                                         #
# --------------------------------------------------------------------------- #
def _work(chunk):
    size, scenario_name, daylight, levels, jobs = chunk
    out = []
    for combo_a, combo_b, seed in jobs:
        result, rounds, tal_a, tal_b = run_battle(
            combo_a, combo_b, seed, size, scenario_name, daylight, levels)
        out.append((combo_a, combo_b, result, rounds, tal_a, tal_b))
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
    __slots__ = ("d", "l", "w")

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

    for combo_a, combo_b, result, r, _tal_a, _tal_b in results:
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


def talent_effects(results, agg):
    """Per talent: how much better (score) its holders did than their race +
    occupation alone predict. Unit-slot attribution -- each holder is credited
    with its squad's result -- so teammates' talents are noise that averages out;
    the SE ignores that within-battle correlation, so read it as a floor."""
    overall = sum(t.score * t.n for t in agg["combo"].values()) / \
              sum(t.n for t in agg["combo"].values())
    race_mean = {r: agg["race"][r].score for r in RACES}
    occ_mean = {o: agg["occ"][o].score for o in OCCUPATIONS}
    samples = defaultdict(list)
    slots = 0
    for combo_a, combo_b, result, _r, tal_a, tal_b in results:
        sa = {"A": 1.0, "B": 0.0, "draw": 0.5}[result]
        for (race, occ), score, squad in ((combo_a, sa, tal_a), (combo_b, 1.0 - sa, tal_b)):
            expected = race_mean[race] + occ_mean[occ] - overall
            for tals in squad:
                slots += 1
                for tid in tals:
                    if talents.get(tid).track != "racial":     # see run_racial_ab
                        samples[tid].append(score - expected)
    out = {}
    for tid, xs in samples.items():
        n = len(xs)
        mean = sum(xs) / n
        var = sum((x - mean) ** 2 for x in xs) / (n - 1) if n > 1 else 0.0
        out[tid] = {"n": n, "holders": n / slots, "delta": mean,
                    "se": math.sqrt(var / n)}
    return out


# --------------------------------------------------------------------------- #
# report                                                                      #
# --------------------------------------------------------------------------- #
def _bar(x, lo=0.30, hi=0.70, width=20):
    frac = max(0.0, min(1.0, (x - lo) / (hi - lo)))
    fill = round(frac * width)
    return "#" * fill + "." * (width - fill)


def build_report(agg, cfg, tal_fx=None):
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
    c, w, rac, gear = cfg["levels"]
    p("Method: homogeneous squad vs homogeneous squad, fresh 3d6 rolls per clone,")
    p(f"combat L{c}, work L{w}, racial {'derived' if rac is None else f'pinned {rac}'}"
      f"{', random talent picks' if (c or w or rac) else ', no talents'}. "
      f" gear={gear}. Elo from the same games, three ways (K-passes 24>16>10>6).")
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

    if tal_fx:
        p("")
        p("-" * 78)
        p("TALENTS  (holder score minus race+occupation prediction; + = the talent helps)")
        p("random picks; unit-slot attribution, SE is a floor; |z| < 2 is noise")
        p("a branch's tier-2 nodes carry their root's pull; racial talents are not")
        p("ranked here (the race's own mean already contains them) -- use --racial-ab")
        p("-" * 78)
        for track in talents.XP_TRACKS:
            rows = [(tid, fx) for tid, fx in tal_fx.items() if talents.get(tid).track == track]
            if not rows:
                continue
            p(f"{track.upper()}:")
            p(f"  {'talent':<24}{'race':<12}{'holders':>8}{'delta':>8}{'+/-SE':>8}{'z':>6}")
            for tid, fx in sorted(rows, key=lambda r: r[1]["delta"], reverse=True):
                t = talents.get(tid)
                z = fx["delta"] / fx["se"] if fx["se"] else 0.0
                p(f"  {t.name:<24}{(t.race or ''):<12}{fx['holders']:>8.1%}"
                  f"{fx['delta']:>+8.3f}{fx['se']:>8.3f}{z:>6.1f}")

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


def _ab_battle(job):
    """One racial A/B fight: two squads of the same race and occupation, both with
    the racial level pinned (same hit dice), one holding its racial talent and the
    other with it dropped. Returns (race, talent_side_score)."""
    race, occ, seed, size, scenario_name, daylight, levels, swap = job
    random.seed(seed)
    with_t = _squad((race, occ), "enemy" if swap else "player", size, levels)
    without = _squad((race, occ), "player" if swap else "enemy", size, levels)
    for u in without:
        for tid in list(u.talents["racial"]):
            u.drop_talent("racial", tid)
        if u.equipped_weapon and not u.can_wield(u.equipped_weapon):   # Giant's Grip's Large weapon
            u.equipped_weapon = None
            give_gear(u, levels.gear)
    a, b = (without, with_t) if swap else (with_t, without)
    battle = Battle(a, b, scenario=_scenario(scenario_name), daylight=daylight)
    guard = 0
    while battle.winner is None and guard < GUARD:
        guard += 1
        ai.take_turn(battle, battle.active)
    if battle.winner is None:
        return race, 0.5
    talent_side = "enemy" if swap else "player"
    return race, 1.0 if battle.winner == talent_side else 0.0


def racial_ab(args, levels):
    """`--racial-ab N`: for every race, N mirror fights, talent vs the same squad
    without it. This is the clean read on a racial talent -- the unit-slot method
    can't isolate it, since every member of a race holds the same single node."""
    levels = levels._replace(racial=5 if levels.racial is None else levels.racial)
    rng = random.Random(args.seed)
    jobs = [(race, rng.choice(OCCUPATIONS), rng.randrange(2**31), args.team_size,
             args.scenario, args.daylight, levels, i % 2)
            for race in (args.race or RACES) for i in range(args.racial_ab)]
    print(f"racial A/B: {len(jobs)} mirror fights on {args.workers} workers ...")
    scores = defaultdict(list)
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for race, sc in ex.map(_ab_battle, jobs, chunksize=64):
            scores[race].append(sc)
    L = ["=" * 78, "GARTOK RACIAL TALENT A/B", "=" * 78,
         (f"{args.racial_ab} mirror fights per race, {args.team_size}v{args.team_size}, "
          f"scenario={args.scenario}, combat L{levels[0]}, work L{levels[1]}, racial {levels[2]}, "
          f"gear={levels.gear}"),
         "talent squad vs the identical squad with the racial node dropped (same hit dice);",
         "score = talent side's, draws half; 0.500 = the talent changes nothing in combat", "",
         f"{'':3}{'talent':<24}{'race':<12}{'score':>8}{'+/-SE':>8}{'z':>6}{'games':>8}"]
    rows = []
    for race, xs in scores.items():
        n = len(xs)
        mean = sum(xs) / n
        se = math.sqrt(sum((x - mean) ** 2 for x in xs) / (n - 1) / n)
        node = next((t for t in talents.racial_tree(race)), None)
        rows.append((mean, se, n, race, node.name if node else "(no node)"))
    for i, (mean, se, n, race, name) in enumerate(sorted(rows, reverse=True), 1):
        L.append(f"{i:<3}{name:<24}{race:<12}{mean:>8.3f}{se:>8.3f}{(mean - 0.5) / se:>6.1f}{n:>8}")
    L.append("=" * 78)
    report = "\n".join(L)
    print(report)
    os.makedirs(args.out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(args.out_dir, f"balance-racial-ab-{args.scenario}-{stamp}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(f"\nreport  -> {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--battles", type=int, default=20000,
                    help="20k: solid race/occ ranking in ~1 min. 60k: tight combos too.")
    ap.add_argument("--team-size", type=int, default=3)
    ap.add_argument("--level", type=int, default=0,
                    help="combat AND work level for every fighter (talents picked at random)")
    ap.add_argument("--gear", choices=("starting", "best", "random"), default="starting",
                    help="starting = the occupation's weapon; best / random draw weapon, "
                         "armor and shield from the whole catalog")
    ap.add_argument("--combat-level", type=int, default=None)
    ap.add_argument("--work-level", type=int, default=None)
    ap.add_argument("--racial", type=int, default=None,
                    help="pin the racial level (hit dice + racial pick at 5); default derived")
    ap.add_argument("--scenario", default="ermos",
                    help="ermos | arena | a map slug from map_lib (e.g. the-pit)")
    ap.add_argument("--daylight", type=lambda s: s.lower() != "false", default=True,
                    help="ermos only: True = fought by day (default), False = night")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--min-combo-games", type=int, default=0,
                    help="0 = auto (max(30, battles/#combos * 0.6))")
    ap.add_argument("--out-dir", default="sim_results")
    ap.add_argument("--race", action="append", help="--racial-ab: only this race (repeatable)")
    ap.add_argument("--racial-ab", type=int, default=0, metavar="N",
                    help="instead of the tournament: N mirror fights per race, the "
                         "racial talent vs the same squad without it")
    args = ap.parse_args()

    if args.min_combo_games == 0:
        args.min_combo_games = max(30, round(args.battles * 2 / len(COMBOS) * 0.6))

    levels = Build(args.level if args.combat_level is None else args.combat_level,
                   args.level if args.work_level is None else args.work_level,
                   args.racial, args.gear)
    if args.racial_ab:
        racial_ab(args, levels)
        return
    cfg = {
        "levels": levels, "battles": args.battles, "team_size": args.team_size,
        "scenario": args.scenario, "daylight": args.daylight,
        "min_combo_games": args.min_combo_games, "seed": args.seed,
    }

    print(f"planning {args.battles} battles on {args.workers} workers ...")
    jobs = make_jobs(args.battles, args.seed)

    n_chunks = args.workers * 8
    size = math.ceil(len(jobs) / n_chunks)
    chunks = [(args.team_size, args.scenario, args.daylight, levels, jobs[i:i + size])
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
    leveled = any(levels[:2]) or levels[2] or levels.gear != "starting"
    tal_fx = talent_effects(results, agg) if leveled else None
    report, elos = build_report(agg, cfg, tal_fx)
    print("\n" + report)

    os.makedirs(args.out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    lvl = (f"-L{levels[0]}.{levels[1]}" + ("" if levels[2] is None else f"r{levels[2]}")
           + ("" if levels.gear == "starting" else f"-{levels.gear}")) if leveled else ""
    tag = f"{args.scenario}{'-night' if not args.daylight else ''}{lvl}-{args.battles}-{stamp}"

    rep_path = os.path.join(args.out_dir, f"balance-{tag}.txt")
    with open(rep_path, "w", encoding="utf-8") as f:
        f.write(report + "\n")

    with open(os.path.join(args.out_dir, f"balance-{tag}.json"), "w", encoding="utf-8") as f:
        json.dump({
            "config": cfg,
            "elo": elos,
            "talents": tal_fx or {},
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
