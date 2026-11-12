"""What one point of each attribute modifier is worth in a fight, read from a race-study run (no new fights).

    python scripts/attribute_rank.py sim_results/teste-1h-int [--kind clones|mixed|all]

Every unit of the study is logged with its six modifiers. A squad's attribute is the mean of its units' modifiers minus the
mean of their (race, build, level) cell, so race and build are held fixed and only the 3d6 roll is left. The squad's result
(1 win, 0.5 draw, 0 loss) is regressed on those six deviations by least squares; the slope times 100 is the win points one
extra modifier point on every unit of the squad gives. Modifier points, not scores: a modifier is (score - 10) // 2.
"""

from __future__ import annotations

import argparse
import glob
import gzip
import json
import math
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gartok import data

CLONES = {"mb", "ef"}


def fights(path, kind):
    for f in sorted(glob.glob(os.path.join(path, "data", "*.jsonl.gz"))):
        if (os.path.basename(f)[:2] in CLONES) != (kind == "clones") and kind != "all":
            continue
        with gzip.open(f, "rt") as fh:
            for line in fh:
                yield json.loads(line)


def solve(a, b):
    n = len(a)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        for r in range(n):
            if r != c:
                k = m[r][c] / m[c][c]
                m[r] = [x - k * y for x, y in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] for i in range(n)]


def inverse(a):
    n = len(a)
    return [solve(a, [1.0 if i == j else 0.0 for i in range(n)]) for j in range(n)]


def builds_of(r, side):
    """The build of each unit of a side, in the order of the logged units (a clone squad has one build; a mixed one lists its cells)."""
    if r["w"] in CLONES:
        return [r["ba"] if side == "A" else r["bb"]] * 3
    return [b for _race, b in r["ta" if side == "A" else "tb"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--kind", default="all", choices=("clones", "mixed", "all"))
    args = ap.parse_args()
    rows = list(fights(args.path, args.kind))
    cell = defaultdict(lambda: [0, [0.0] * 6])
    sides = []
    for r in rows:
        for side in ("A", "B"):
            us = [u for u in r["units"] if u["s"] == side]
            bs = builds_of(r, side)
            if len(us) != len(bs):
                continue
            keys = [(u["race"], b, r["lv"]) for u, b in zip(us, bs)]
            for k, u in zip(keys, us):
                cell[k][0] += 1
                cell[k][1] = [s + x for s, x in zip(cell[k][1], u["attr"])]
            sides.append((r, side, us, keys))
    mean = {k: [x / n for x in s] for k, (n, s) in cell.items()}
    xs, ys = [], []
    for r, side, us, keys in sides:
        dev = [0.0] * 6
        for u, k in zip(us, keys):
            dev = [d + (a - b) / len(us) for d, a, b in zip(dev, u["attr"], mean[k])]
        xs.append(dev)
        ys.append(1.0 if r["win"] == side else 0.5 if r["win"] == "D" else 0.0)
    n = len(ys)
    xtx = [[sum(x[i] * x[j] for x in xs) for j in range(6)] for i in range(6)]
    xty = [sum(x[i] * y for x, y in zip(xs, ys)) for i in range(6)]
    beta = solve(xtx, xty)
    resid = sum((y - sum(b * v for b, v in zip(beta, x))) ** 2 for x, y in zip(xs, ys))
    sigma2 = resid / (n - 6)
    inv = inverse(xtx)
    sd = [math.sqrt(sum((x[i]) ** 2 for x in xs) / n) for i in range(6)]
    print(f"{n} squad results from {len(rows)} fights ({args.kind}); mean 50 by construction\n")
    print("| attribute | win points per +1 modifier | 95% | spread of the roll (sd, modifier points) |\n|---|---|---|---|")
    for i in sorted(range(6), key=lambda i: -beta[i]):
        print(f"| {data.ATTRIBUTES[i]} | {100 * beta[i]:+.1f} | +/-{196 * math.sqrt(sigma2 * inv[i][i]):.1f} | {sd[i]:.2f} |")


if __name__ == "__main__":
    main()
