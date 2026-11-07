"""The complete race study: squads of three of one race against squads of another, at level 0 and 5,
with many builds, on the Ribbit Brothers' map fought as plain elimination.

    python scripts/race_study.py smoke                      # a few hundred fights, timed, with sanity checks
    python scripts/race_study.py run --waves mx,fd --scale 1 --until 2026-11-06T09:00
    python scripts/race_study.py status

Every job is one fight, written as one JSON row (gzip, one file per chunk of jobs, so a run can stop and
resume): the two squads' races and builds, the winner, the rounds, and for every unit its attributes,
talents, spells, gear, hit points and the actions it took. `race_study_report.py` reads them back.
The seed of a job is a function of its wave, level and index alone, so a chunk written twice is the same.
"""

from __future__ import annotations

import argparse
import ctypes
import gzip
import json
import os
import random
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gartok import ai, data, economy, map_lib, outfit, talents
from gartok.battle import Battle
from gartok.scenario import CustomScenario, ErmosScenario
from scripts import race_study_builds as rb

OUT = os.path.join(ROOT, "sim_results", "teste-completo-racas")
DATA = os.path.join(OUT, "data")
GUARD = 600
CHUNK = 200
RACES = [r[1] for r in data.RACES]


def field_builds(lv):
    """The builds a level can field: those whose first weapon its budget pays for, and the random kit."""
    return rb.builds_at(lv) + [rb.RANDOM_KIT]


def melee_builds(lv):
    return [b for b in rb.builds_at(lv) if rb.BUILDS[b].role == "melee"]


class Counting:
    """A combat-log sink that only counts what each unit did (the interface `Battle.record_to` wants)."""

    def __init__(self):
        self.busy = False
        self.acts = {}

    def start(self, battle):
        self.acts = {id(u): Counter() for u in battle.units}

    def record(self, battle, name, actor, target, kw, run):
        self.acts.setdefault(id(actor), Counter())[name] += 1
        return run()


def _scenario(name=None):
    if name == "ermos":
        return ErmosScenario()
    return CustomScenario(map_lib.load_map(rb.MAP_SLUG))


def _squad(team, race, build, level, rng, *, fixed, drop, over=None):
    squad, notes = [], []
    for _ in range(3):
        u, n = rb.make_unit(team, race, build, level, rng, fixed=fixed, drop_racial=drop, over=over)
        squad.append(u)
        notes += n
    rb.light_squad(squad)
    if level:
        outfit.light_the_band(squad)
    return squad, notes


def _unit_row(side, u, acts):
    weapon = u.equipped_weapon
    return {
        "s": side, "race": u.race["name"], "hp_max": u.hp_max, "hp": max(u.hp, 0), "alive": u.hp > 0,
        "attr": [data.mod(getattr(u, a)) for a in data.ATTRIBUTES],
        "tal": [t for tr in talents.TRACKS for t in u.talents[tr]],
        "spells": list(u.spells_known), "weapon": weapon, "armor": u.equipped_armor,
        "off": u.equipped_offhand, "ammo": getattr(u, "ammo", None), "ac": getattr(u, "ac", None), "acts": dict(acts),
    }


def play(job):
    """Run one job; `job["sw"]` puts side A on the enemy team, to cancel any position bias."""
    random.seed(job["seed"])
    rng = random.Random(job["seed"] ^ 0x5EED)
    lv, fixed = job["lv"], job["fx"]
    sa, na = _squad("enemy" if job["sw"] else "player", job["ra"], job["ba"], lv, rng, fixed=fixed, drop=job["dr"], over=job.get("oa"))
    sb, nb = _squad("player" if job["sw"] else "enemy", job["rb"], job["bb"], lv, rng, fixed=fixed, drop=False, over=job.get("ob"))
    a, b = (sb, sa) if job["sw"] else (sa, sb)
    sink = Counting()
    battle = Battle(a, b, scenario=_scenario(job.get("map")), daylight=True)
    battle.record_to(sink)
    guard = 0
    while battle.winner is None and guard < GUARD:
        guard += 1
        ai.take_turn(battle, battle.active)
    a_team = "enemy" if job["sw"] else "player"
    win = "D" if battle.winner not in ("player", "enemy") else ("A" if battle.winner == a_team else "B")
    units = [_unit_row("A" if u.team == a_team else "B", u, sink.acts.get(id(u), {})) for u in battle.units]
    return {**job, "win": win, "rounds": battle.round_no, "capped": guard >= GUARD,
            "notes": sorted(set(na + nb)), "units": units}


# -- the waves -------------------------------------------------------------------------------------------------
def _job(wave, lv, i, ra, ba, rb_, bb, **kw):
    return {"w": wave, "lv": lv, "i": i, "ra": ra, "ba": ba, "rb": rb_, "bb": bb, "sw": i % 2 == 1,
            "fx": kw.get("fx", False), "dr": kw.get("dr", False), "oa": kw.get("oa"), "ob": kw.get("ob"), "map": kw.get("map"),
            "seed": _seed(wave, lv, i)}


def _seed(wave, lv, i):
    return (sum(ord(c) * (31 ** k) for k, c in enumerate(wave)) * 1000003 + lv * 7919 + i * 104729) & 0x7FFFFFFF


KITS = {"str": {}, "dex": {"weapon": "Rapier", "armor": "Studded Leather", "shield": "none"},
        "bow": {"weapon": "Longbow", "armor": "Studded Leather", "shield": "none"}}
COMBOS = (
    ("str line", "str", ("strong", "sure_strike", "heavy_hand")),
    ("strong + heavy hand", "str", ("strong", "heavy_hand")),
    ("tough line", "str", ("tough", "hardy", "bulwark")),
    ("tough + bulwark + armor bearer", "str", ("tough", "bulwark", "armor_bearer")),
    ("tough + hardy + recovery", "str", ("tough", "hardy", "recovery")),
    ("strong + tough", "str", ("strong", "tough")),
    ("strong + tough + hardy + heavy hand", "str", ("strong", "heavy_hand", "tough", "hardy")),
    ("strong + sure strike + tough", "str", ("strong", "sure_strike", "tough")),
    ("agile + deadeye + fleet", "dex", ("agile", "deadeye", "fleet")),
    ("agile + deadeye + skirmisher", "dex", ("agile", "deadeye", "nimble_skirmisher")),
    ("agile + tough", "dex", ("agile", "tough")),
    ("agile + deadeye + tough + hardy", "dex", ("agile", "deadeye", "tough", "hardy")),
    ("strong + agile", "str", ("strong", "agile")),
    ("agile + deadeye (bow)", "bow", ("agile", "deadeye")),
    ("agile + long reach (bow)", "bow", ("agile", "long_reach")),
    ("agile + deadeye + long reach (bow)", "bow", ("agile", "deadeye", "long_reach")),
    ("imposing + menacing + cull", "str", ("imposing", "menacing", "cull_the_broken")),
    ("imposing + gruesome + shout", "str", ("imposing", "gruesome_takedown", "inspiring_shout")),
    ("alert + iron will + iron stance", "str", ("alert", "iron_will", "iron_stance")),
    ("alert + quick wits + peripheral", "str", ("alert", "quick_wits", "peripheral_vision")),
    ("tactical + combat analysis + exploit", "str", ("tactical_mind", "combat_analysis", "exploit_weakness")),
    ("tactical + sharp + anatomist", "str", ("tactical_mind", "sharp_analysis", "anatomist")),
)


def wave_jobs(wave, lv, scale):
    rng = random.Random(_seed(wave, lv, 0))
    jobs, i = [], 0
    field = field_builds(lv)

    def add(ra, ba, rb_, bb, **kw):
        nonlocal i
        jobs.append(_job(wave, lv, i, ra, ba, rb_, bb, **kw))
        i += 1

    if wave == "mx":
        for x, ra in enumerate(RACES):
            for rb_ in RACES[x:]:
                for _ in range(int(60 * scale)):
                    add(ra, rb.MELEE_REF, rb_, rb.MELEE_REF)
    elif wave in ("fd", "fx"):
        for ra in RACES:
            for _ in range(int((3000 if wave == "fd" else 1500) * scale)):
                add(ra, rng.choice(field), rng.choice(RACES), rng.choice(field), fx=wave == "fx")
    elif wave == "mb":
        for ra in RACES:
            for ba in rb.builds_at(lv):
                for _ in range(int(150 * scale)):
                    add(ra, ba, rng.choice(RACES), rng.choice(field))
    elif wave == "ab":
        if lv:
            for ra in RACES:
                for _ in range(int(600 * scale)):
                    ba = rng.choice(melee_builds(lv))
                    add(ra, ba, ra, ba, dr=True)
    elif wave == "tl":
        if lv:
            for t in [t.id for t in talents.TREE["combat"]]:
                for _ in range(int(250 * scale)):
                    add(rr := rng.choice(RACES), "plain", rr, "plain", oa={"force": [t]}, ob={"ban": [t]})
    elif wave == "tc":
        if lv:
            for name, kit, chain in COMBOS:
                for _ in range(int(400 * scale)):
                    rr = rng.choice(RACES)
                    add(rr, "plain", rr, "plain", oa={**KITS[kit], "force": list(chain), "tag": name},
                        ob={**KITS[kit], "ban": list(chain), "tag": name})
    elif wave == "ef":
        for ra in RACES:
            for _ in range(int(1500 * scale)):
                add(ra, rng.choice(field), rng.choice(RACES), rng.choice(field), map="ermos")
    elif wave == "cg":
        gear = {"weapon": "Hammer", "armor": "Chainmail" if lv else "Leather Jerkin", "shield": "none"}
        ids = ("plain", "nature_striker", "nature_control", "blood_striker", "blood_hexer", "faith_support",
               "faith_striker", "battlemage")
        for x, ba in enumerate(ids):
            for bb in ids[x:]:
                for _ in range(int(300 * scale)):
                    rr = rng.choice(RACES)
                    add(rr, ba, rr, bb, oa=gear, ob=gear)
    elif wave == "lw":
        if lv:
            for race in ("Centaur", "Goliath"):
                for ba in melee_builds(lv):
                    for _ in range(int(150 * scale)):
                        add(race, ba, race, ba, oa={"large": True})
    elif wave == "gw":
        for wpn in [w for w in rb.CATALOG if rb.affordable(w, lv)]:
            for _ in range(int(250 * scale)):
                rr = rng.choice(RACES)
                add(rr, "plain", rr, "plain", oa={"weapon": wpn}, ob={"weapon": "Sword"})
    elif wave == "ga":
        base = economy.buy_price("Sword")
        for arm in [a for a in rb.ARMORS if base + economy.buy_price(a) <= outfit.budget(lv)] + ["none"]:
            for _ in range(int(250 * scale)):
                rr = rng.choice(RACES)
                add(rr, "plain", rr, "plain", oa={"armor": arm, "shield": "none"}, ob={"armor": "none", "shield": "none"})
    elif wave == "gs":
        if economy.buy_price("Sword") + economy.buy_price(rb.SHIELD) <= outfit.budget(lv):
            for _ in range(int(2000 * scale)):
                rr = rng.choice(RACES)
                add(rr, "plain", rr, "plain", oa={"shield": rb.SHIELD}, ob={"shield": "none"})
    elif wave == "sp":
        if lv:
            for bid in ("nature_striker", "nature_control", "blood_striker", "blood_hexer", "faith_support", "faith_striker"):
                for sid in rb.BUILDS[bid].spells5:
                    for _ in range(int(150 * scale)):
                        rr = rng.choice(RACES)
                        add(rr, bid, rr, bid, ob={"drop_spell": sid})
    elif wave == "rb":
        for ba in rb.builds_at(lv):
            for bb in rb.builds_at(lv):
                for _ in range(int(60 * scale)):
                    add(rng.choice(RACES), ba, rng.choice(RACES), bb)
    else:
        raise SystemExit(f"unknown wave {wave}")
    return jobs


def _chunk_path(wave, lv, c):
    return os.path.join(DATA, f"{wave}_L{lv}_{c:05d}.jsonl.gz")


def run_chunk(args):
    wave, lv, c, jobs, deadline = args
    path = _chunk_path(wave, lv, c)
    if os.path.exists(path):
        return wave, lv, c, 0, 0.0
    if deadline and time.time() > deadline:
        return wave, lv, c, -1, 0.0
    t0, rows = time.time(), []
    for job in jobs:
        try:
            rows.append(play(job))
        except Exception as e:  # noqa: BLE001 -- a failed fight is recorded, never lost silently
            rows.append({**job, "win": "E", "err": f"{type(e).__name__}: {e}"[:200]})
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    os.replace(tmp, path)
    return wave, lv, c, len(rows), time.time() - t0


def keep_awake():
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)


def log(msg):
    line = f"{datetime.now():%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "progress.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def cmd_run(args):
    os.makedirs(DATA, exist_ok=True)
    keep_awake()
    deadline = datetime.fromisoformat(args.until).timestamp() if args.until else 0
    levels = [int(x) for x in args.levels.split(",")]
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for spec in args.waves.split(","):
            wave, _, sc = spec.partition(":")
            for lv in levels:
                jobs = wave_jobs(wave, lv, float(sc) if sc else args.scale)
                tasks = [(wave, lv, c, jobs[c * CHUNK:(c + 1) * CHUNK], deadline)
                         for c in range((len(jobs) + CHUNK - 1) // CHUNK)]
                if not tasks:
                    continue
                log(f"wave {wave} L{lv}: {len(jobs)} fights in {len(tasks)} chunks")
                t0, fights = time.time(), 0
                for done, (_, _, _, n, _) in enumerate(ex.map(run_chunk, tasks, chunksize=1), 1):
                    fights += max(n, 0)
                    keep_awake()
                    if done % 20 == 0 or done == len(tasks):
                        log(f"  {wave} L{lv}: {done}/{len(tasks)} chunks, {fights} new fights, {time.time() - t0:.0f}s")
                if deadline and time.time() > deadline:
                    log("deadline reached, stopping")
                    return


def cmd_smoke(args):
    sys.setrecursionlimit(10000)
    for lv in (0, 5):
        for wave in ("mx", "fd", "mb", "ab", "lw", "rb"):
            jobs = wave_jobs(wave, lv, 0.02)[: args.n]
            if not jobs:
                continue
            t0, res = time.time(), [play(j) for j in jobs]
            wins = Counter(r["win"] for r in res)
            acts, notes = Counter(), Counter()
            for r in res:
                for u in r["units"]:
                    acts.update(u["acts"])
                notes.update(r["notes"])
            print(f"L{lv} {wave}: {len(res)} fights {time.time() - t0:.1f}s ({(time.time() - t0) / len(res):.2f}s each) "
                  f"A/B/D {dict(wins)} capped {sum(r['capped'] for r in res)} rounds {sum(r['rounds'] for r in res) / len(res):.1f}")
            print("   notes", dict(notes), "| actions", dict(acts.most_common(14)))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("smoke")
    s.add_argument("-n", type=int, default=30)
    r = sub.add_parser("run")
    r.add_argument("--waves", default="mr,mx,fd,mb,ab,fx,rb")
    r.add_argument("--levels", default="0,5")
    r.add_argument("--scale", type=float, default=1.0)
    r.add_argument("--workers", type=int, default=15)
    r.add_argument("--until", default="")
    args = ap.parse_args()
    {"smoke": cmd_smoke, "run": cmd_run}[args.cmd](args)


if __name__ == "__main__":
    main()
