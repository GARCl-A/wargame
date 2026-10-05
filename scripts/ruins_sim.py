"""Ancient Ruins boss fight, AI vs AI: the roster of a real save against the
dungeon's own enemies (sentries, Archivist, spiders), N times.

    python scripts/ruins_sim.py [world] [--runs 100] [--only boss] [--level 5]

Reports win rate, rounds, which actions each team executes, and how the party
ends up (status, HP, poison). `--only boss` drops the two sentries and starts
everyone awake in the sanctum's approach, to isolate the boss room.
"""

import argparse
import os
import random
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gartok import actions, ai, persist, talents
from gartok.battle import Battle
from gartok.scenario import AncientRuinsScenario

GUARD = 1500
EXEC = Counter()


def _hook_actions():
    for cls in vars(actions).values():
        if isinstance(cls, type) and issubclass(cls, actions.Action) and "execute" in vars(cls):
            orig = cls.execute

            def wrapped(self, battle, actor, *a, _orig=orig, **k):
                EXEC[(actor.team, getattr(self, "name", type(self).__name__),
                      getattr(self, "spell_id", None))] += 1
                return _orig(self, battle, actor, *a, **k)
            cls.execute = wrapped


def _level_to(u, level):
    """Raise a character to `level` on both tracks and spend every talent pick at
    random inside the trees (the way `encounters.build_enemy` does)."""
    u.set_track_level("combat", max(u.track_level["combat"], level))
    u.set_track_level("work", max(u.track_level["work"], level))
    for track in talents.TRACKS:
        tree = (talents.TREE[track] if track in talents.XP_TRACKS
                else talents.racial_tree(u.race["name"]))
        for _ in range(20):
            if u.picks_available(track) <= 0:
                break
            picked = u.talents[track]
            opts = [t.id for t in tree if t.id not in picked
                    and (t.requires is None or t.requires in picked)]
            if not opts:
                break
            u.choose_talent(track, random.choice(opts))


def one(world, seed, only, level=None):
    random.seed(seed)
    guild = persist.load_game(world)
    party = [m for g in guild.groups for m in g.members]
    if level:
        for m in party:
            _level_to(m, level)
    sc = AncientRuinsScenario()
    enemies = sc.enemies
    if only == "boss":
        enemies = [e for e in enemies if "Sentry" not in e.name]
    b = Battle(party, enemies, scenario=sc, daylight=False, lethal=True)
    if only == "boss":
        b.alarm_triggered = True
    guard = 0
    while b.winner is None and guard < GUARD:
        guard += 1
        ai.take_turn(b, b.active)
    return b, guard


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("world", nargs="?", default="518eda62")
    ap.add_argument("--runs", type=int, default=100)
    ap.add_argument("--only", choices=["all", "boss"], default="all")
    ap.add_argument("--level", type=int, default=None, help="raise the whole party to this level first")
    a = ap.parse_args()
    _hook_actions()

    wins, rounds, stuck = Counter(), [], 0
    alive_hist = Counter()
    per = defaultdict(lambda: Counter())
    hp_end = defaultdict(list)
    poisoned = Counter()
    foes_dead = Counter()
    for s in range(a.runs):
        b, g = one(a.world, s, a.only, a.level)
        stuck += g >= GUARD
        wins[b.winner] += 1
        rounds.append(b.round_no)
        alive = 0
        for u in b.player_units:
            per[u.name][u.status] += 1
            hp_end[u.name].append(max(u.hp, 0))
            alive += u.status == "up"
            if u.poisoned:
                poisoned[u.name] += 1
        alive_hist[alive] += 1
        for e in b.enemy_units:
            foes_dead[(e.name, e.status)] += 1

    n = a.runs
    print(f"world {a.world}  runs {n}  mode {a.only}  level {a.level or "as saved"}")
    print("wins:", dict(wins), f" stuck: {stuck}")
    print(f"rounds: min {min(rounds)} avg {sum(rounds) / n:.1f} max {max(rounds)}")
    print("party standing at the end:", dict(sorted(alive_hist.items())))
    print("\nparty member       up   dying stable broken dead fled | avg end HP | ended poisoned")
    for name in per:
        c = per[name]
        print(f"{name[:18]:18} {c['up']:4} {c['dying']:5} {c['stable']:6} {c['broken']:6} "
              f"{c['dead']:4} {c['fled']:4} | {sum(hp_end[name]) / n:9.1f} | {poisoned[name]}")
    print("\nenemy end state:")
    for (name, st), c in sorted(foes_dead.items()):
        print(f"  {name:24} {st:9} {c}")
    for team in ("player", "enemy"):
        print(f"\nactions executed by {team} (total / per run):")
        rows = sorted(((v, k) for k, v in EXEC.items() if k[0] == team), reverse=True)
        for v, (_, nm, sp) in rows:
            print(f"  {nm + (' [' + sp + ']' if sp else ''):28} {v:7} {v / n:7.1f}")


if __name__ == "__main__":
    main()
