"""Headless simulation: run many AI-only battles to sanity-check the rules."""

import random
from collections import Counter

from gartok import ai
from gartok.battle import Battle
from gartok.unit import Unit


def run_one(seed):
    random.seed(seed)
    b = Battle([Unit("player") for _ in range(3)], [Unit("enemy") for _ in range(3)])
    guard = 0
    while b.winner is None and guard < 2000:
        guard += 1
        ai.take_turn(b, b.active)
    return b.winner, b.round_no, guard


if __name__ == "__main__":
    wins = Counter()
    rounds = []
    for s in range(200):
        w, r, g = run_one(s)
        wins[w] += 1
        rounds.append(r)
        assert g < 2000, f"loop stuck on seed {s}"
    print("wins  :", dict(wins))
    print("rounds:", "min", min(rounds), "avg", sum(rounds) / len(rounds), "max", max(rounds))
