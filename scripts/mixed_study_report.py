"""Preview report of the four-test format: 3 clones x 3 clones and 3 mixed x 3 mixed, on the CTF map and on the Ermos.

    python scripts/race_study.py run --out teste-5min --chunk 30 --waves mb:0.034,mm:0.17,ef:0.12,em:0.24
    python scripts/mixed_study_report.py [--out teste-5min]

Clone fights (`mb` CTF, `ef` Ermos) credit the (race, build) cell of each side, both sides counted. Mixed fights (`mm`, `em`)
credit each of the six slots with its side's result. Scores are plain win rates (x100), the two maps weighted half each.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gartok import vocations
from scripts import race_study_builds as rb
from scripts.build_study_report import Acc, rows, score, table

MAPS = {"mb": ("clones", "CTF"), "ef": ("clones", "Ermos"), "mm": ("mixed", "CTF"), "em": ("mixed", "Ermos")}
MAP_WEIGHT = {"CTF": 0.5, "Ermos": 0.5}
DILUTION_FALLBACK = 3      # a mixed slot is one unit in three; used only when the data cannot give the factor


class Data:
    def __init__(self, out):
        self.cell = defaultdict(Acc)            # (kind, map, race, build)
        self.comp = defaultdict(Acc)            # (map, composition) -> mixed fights, every side
        self.fights = defaultdict(int)
        self.errors = 0
        for r in rows(out):
            if r["win"] == "E":
                self.errors += 1
                continue
            kind, mp = MAPS[r["w"]]
            self.fights[kind, mp] += 1
            if kind == "clones":
                for side, race, build in (("A", r["ra"], r["ba"]), ("B", r["rb"], r["bb"])):
                    self.cell[kind, mp, race, build].add(score(r["win"], side))
            else:
                for side, team in (("A", r["ta"]), ("B", r["tb"])):
                    x = score(r["win"], side)
                    for race, build in team:
                        self.cell[kind, mp, race, build].add(x)
                    self.comp[mp, composition(team)].add(x)

    def pooled(self, kind, mp, race=None, build=None):
        acc = Acc()
        for (k, m, r, b), a in self.cell.items():
            if (k, m) == (kind, mp) and race in (None, r) and build in (None, b):
                acc.n += a.n
                acc.s += a.s
        return acc if acc.n else None


def composition(team):
    roles = sorted(rb.BUILDS[b].role for _r, b in team)
    return " + ".join(f"{roles.count(x)} {x}" for x in dict.fromkeys(roles))


def blend(accs):
    """`(score, 95% half-width)` of the half-and-half mean of the maps' accumulators."""
    got = {m: a for m, a in accs.items() if a is not None}
    if not got:
        return None
    w = sum(MAP_WEIGHT[m] for m in got)
    mean = sum(MAP_WEIGHT[m] * a.p for m, a in got.items()) / w
    se = math.sqrt(sum((MAP_WEIGHT[m] * a.se) ** 2 for m, a in got.items())) / w
    return 100 * mean, 196 * se


def fmt(v):
    return "-" if v is None else f"{v[0]:.1f} ±{v[1]:.1f}"


def one(acc):
    return "-" if acc is None else f"{100 * acc.p:.1f} ±{196 * acc.se:.1f}"


def by(d, key, ids, title):
    """The race table or the build table: the clones and the mixed teams side by side."""
    body = []
    for i in ids:
        row = {kind: {m: d.pooled(kind, m, **{key: i}) for m in MAP_WEIGHT} for kind in ("clones", "mixed")}
        c, x = blend(row["clones"]), blend(row["mixed"])
        t = combine(c, x, d.dilution)
        body.append((t[0] if t else -1, (i, one(row["clones"]["CTF"]), one(row["clones"]["Ermos"]), fmt(c),
                                         one(row["mixed"]["CTF"]), one(row["mixed"]["Ermos"]), fmt(x), f"**{fmt(t)}**")))
    body.sort(key=lambda t: -t[0])
    return table([title, "clones CTF", "clones Ermos", "clones score", "mixed CTF", "mixed Ermos", "mixed score", "**total**"], [b for _s, b in body])


def estimate_dilution(d, races, builds):
    """`(k, n)`: how many times farther from 50 the clones' scores are than the mixed teams' for the same race or build, read off the
    data itself. It is the ratio of the two spreads (sum of squared distances from 50), each with its sampling noise taken out, over
    the `n` races and builds; the plain slope of one on the other would be pulled down by the noise of the mixed side."""
    sc = sx = 0.0
    n = 0
    for key in [{"race": r} for r in races] + [{"build": b} for b in builds]:
        c = blend({m: d.pooled("clones", m, **key) for m in MAP_WEIGHT})
        x = blend({m: d.pooled("mixed", m, **key) for m in MAP_WEIGHT})
        if c and x:
            sc += (c[0] - 50) ** 2 - (c[1] / 1.96) ** 2
            sx += (x[0] - 50) ** 2 - (x[1] / 1.96) ** 2
            n += 1
    return (math.sqrt(sc / sx), n) if sc > 0 and sx > 0 else (DILUTION_FALLBACK, 0)


def combine(c, x, k):
    """One score from the clones' and the mixed teams'. The mixed distance from 50 is scaled back up by `k` (`estimate_dilution`) and the two are
    averaged by their inverse variance (the mixed one, scaled, is noisier: it weighs less)."""
    if not c or not x:
        return c or x
    wc, wx = 1 / c[1] ** 2, 1 / (k * x[1]) ** 2
    return 50 + (wc * (c[0] - 50) + wx * k * (x[0] - 50)) / (wc + wx), 1 / math.sqrt(wc + wx)


def cell_score(d, race, build):
    return blend({m: d.cell.get(("clones", m, race, build)) for m in MAP_WEIGHT})


def flex_rows(d, races, builds):
    """Per race: `(race, builds above 50, builds it fields, clearly above 50, mean of its three best, the three best)`."""
    rows = []
    for race in races:
        got = [(b, v) for b in builds if (v := cell_score(d, race, b))]
        got.sort(key=lambda t: -t[1][0])
        top = got[:3]
        rows.append((race, sum(1 for _b, v in got if v[0] > 50), len(got), sum(1 for _b, v in got if v[0] - v[1] > 50),
                     sum(v[0] for _b, v in top) / len(top) if top else None, top))
    return rows


def flexibility(rows):
    """How many of its builds the clones put above 50, the best three and their mean. The cells are few fights each, so the count
    also shows the builds that are above 50 beyond the noise (the lower end of the 95% interval above 50)."""
    body = [(mean or 0, (race, f"{above}/{n} ({100 * above / n:.0f}%)", clear, f"{mean:.1f}" if mean is not None else "-",
                         ", ".join(f"{b} {v[0]:.0f} ±{v[1]:.0f}" for b, v in top)))
            for race, above, n, clear, mean, top in rows]
    body.sort(key=lambda t: -t[0])
    return table(["race", "builds above 50 / it fields", "clearly above 50 (95%)", "mean of its three best", "its three best builds (score ±)"],
                 [b for _s, b in body])


BANDS = {"build": (40, 60), "race": (45, 55), "vocation": (47, 53), "cell": (30, 75)}    # the cells' 70 is the target, up to 75 for a signature combo
FLEX_OK = (7, 60)           # a race is flexible enough with this many builds above 50 and its three best averaging this
FLEX_NO_NICHE = 5           # fewer builds above 50 than this, and the three best under FLEX_OK[1]: a race with no niche


def verdict(v, band):
    """`None` inside the band, else `(nerf|buff, clear|probable)`: clear when the whole 95% interval is outside it."""
    lo, hi = band
    score, hw = v
    if lo <= score <= hi:
        return None
    up = score > hi
    return ("nerf" if up else "buff", "clear" if (score - hw > hi if up else score + hw < lo) else "probable")


def attention(d, races, builds, flex):
    """The closing section: what to change, from the targets alone (combat only, level 5, both maps). Builds, races and vocations are
    judged on the total (clones and mixed together); the cells and the flexibility on the clones, the only ones that see a cell."""
    out = ["## Points of attention\n",
           ("Objective checks against the targets; combat only (the economy is a later layer). Builds, races and vocations use the "
            "**total** score, with the clones' and the mixed teams' beside it (when they disagree, look at why before changing a number); "
            "the cells and the flexibility use the clones, because only they measure a cell. **clear**: the whole 95% interval is "
            "outside the band. **probable**: the score is outside but the interval crosses it, so collect more fights before touching "
            "the number. A vocation is only its six races here (its perk is left out). Distance is to the nearest end of the band.\n")]

    def totals(**key):
        c = blend({m: d.pooled("clones", m, **key) for m in MAP_WEIGHT})
        x = blend({m: d.pooled("mixed", m, **key) for m in MAP_WEIGHT})
        return combine(c, x, d.dilution), f"{c[0]:.0f} / {x[0]:.0f}" if c and x else "-"

    def block(title, items, band):
        rows = []
        for name, v, extra in items:
            r = verdict(v, band) if v else None
            if r:
                rows.append((abs(v[0] - (band[1] if r[0] == "nerf" else band[0])), name, v, r, extra))
        rows.sort(key=lambda t: (t[3][1] != "clear", -t[0]))
        out.append(f"### {title} (band {band[0]} to {band[1]})\n")
        out.append(table(["", "total ±", "clones / mixed", "to the band", "change", "evidence"],
                         [(n, fmt(v), extra, f"{x:.1f}", f"**{r[0]}**", r[1]) for x, n, v, r, extra in rows]) if rows else "Nothing outside the band.\n")
        return {n for _x, n, _v, _r, _e in rows}

    flagged_b = block("Builds", [(b, *totals(build=b)) for b in builds], BANDS["build"])
    flagged_r = block("Races", [(r, *totals(race=r)) for r in races], BANDS["race"])
    vocs, vc, vx = [], vocation_rows(d, "clones"), vocation_rows(d, "mixed")
    for v in vocations.VOCATIONS.values():
        got = [t for t, _e in (totals(race=r) for r in v.races) if t]
        if got:
            vocs.append((v.id, (sum(t[0] for t in got) / len(got), math.sqrt(sum(t[1] ** 2 for t in got)) / len(got)),
                         f"{vc[v.id]:.0f} / {vx[v.id]:.0f}"))
    block("Vocations (combat only, their races)", vocs, BANDS["vocation"])

    weak = [(race, above, n, mean) for race, above, n, _c, mean, _t in flex if mean is not None and (above < FLEX_OK[0] or mean < FLEX_OK[1])]
    out.append(f"### Flexibility (acceptable: at least {FLEX_OK[0]} builds above 50 and the three best averaging {FLEX_OK[1]} or more)\n")
    out.append(table(["race", "builds above 50", "three best", "change", "why"],
                     [(race, f"{above}/{n}", f"{mean:.1f}", "**buff**",
                       "no niche: few builds above 50 and no strong one" if above < FLEX_NO_NICHE and mean < FLEX_OK[1]
                       else ("too few builds above 50" if above < FLEX_OK[0] else "its best three are not strong")) for race, above, n, mean in sorted(
                           weak, key=lambda t: (not (t[1] < FLEX_NO_NICHE and t[3] < FLEX_OK[1]), t[1]))])
              if weak else "Nothing outside the targets.\n")
    out.append("There is no upper limit on flexibility: a race that wins with everything shows up as a high race score above.\n")

    cells = [(f"{r} + {b}", v, "clones only") for r in races for b in builds if (v := cell_score(d, r, b)) and r not in flagged_r and b not in flagged_b]
    hidden = sum(1 for r in races for b in builds if (v := cell_score(d, r, b)) and verdict(v, BANDS["cell"]) and (r in flagged_r or b in flagged_b))
    flagged = block("Build x race cells, outside what the build or the race explain", cells, BANDS["cell"])
    out.append(f"{len(flagged)} cell(s) listed. {hidden} more are outside the band but belong to a build or a race flagged above: fix those first.\n")
    return out


def cells(d, races, builds):
    """The race x build matrix of the clones' blended score, and the cells at both ends with their error."""
    got = {}
    for race in races:
        for build in builds:
            v = blend({m: d.cell.get(("clones", m, race, build)) for m in MAP_WEIGHT})
            if v:
                got[race, build] = v
    matrix = table(["race \\ build", *builds], [(r, *[f"{got[r, b][0]:.0f}" if (r, b) in got else "-" for b in builds]) for r in races])
    ranked = sorted(got.items(), key=lambda t: -t[1][0])
    ends = table(["", "race", "build", "score"], [("top", r, b, fmt(v)) for (r, b), v in ranked[:10]]
                 + [("bottom", r, b, fmt(v)) for (r, b), v in ranked[-10:]])
    sums = defaultdict(int)
    for (k, _m, r, b), a in d.cell.items():
        if k == "clones":
            sums[r, b] += a.n
    n = sorted(sums.values())
    return matrix, ends, (n[0], n[len(n) // 2], n[-1]) if n else None


def vocation_rows(d, kind):
    out = []
    for v in vocations.VOCATIONS.values():
        scores = [blend({m: d.pooled(kind, m, race=r) for m in MAP_WEIGHT}) for r in v.races]
        scores = [s[0] for s in scores if s]
        if scores:
            out.append((sum(scores) / len(scores), v.id))
    return {vid: sc for sc, vid in out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="teste-5min")
    out = os.path.join(ROOT, "sim_results", ap.parse_args().out)
    d = Data(out)
    races = sorted({r for (_k, _m, r, _b) in d.cell})
    builds = sorted({b for (_k, _m, _r, b) in d.cell if b in rb.BUILDS})
    flex = flex_rows(d, races, builds)
    d.dilution, k_n = estimate_dilution(d, races, builds)
    md =["# Preview: 3 clones and 3 mixed, CTF and Ermos\n",
          "Fights: " + ", ".join(f"{kind} {mp} {n}" for (kind, mp), n in sorted(d.fights.items())) + (f" ({d.errors} errors)" if d.errors else "") + "\n",
          ("Every cell is a win rate (x100) with its 95% half-width. **Clones**: both sides of every fight counted. **Mixed**: each of the "
          "six slots is credited with its side's result, so it is the win rate of a squad *containing* the race or build, diluted "
          "towards 50 (one unit in three), and its error is optimistic (two slots of one build on a team share one outcome). "
          f"The two maps weigh half each. **Total**: the mixed distance from 50 is scaled back up (x{d.dilution:.2f}, estimated from the data: "
          f"{k_n} races and builds) and the two scores are averaged by "
          "their inverse variance, so it leans on the clones.\n"),
          "## Race\n", by(d, "race", races, "race"),
          "## Race: flexibility (clones)\n",
          ("How many builds each race wins with, and how good its best three are: a race with a high mean of its three best but few "
          "builds above 50 is a specialist. Each cell is few fights, so the three best are picked from noise and read a little high.\n"),
          flexibility(flex),
          "## Build\n", by(d, "build", builds, "build")]
    matrix, ends, spread = cells(d, races, builds)
    md += ["## Build x race (clones only)\n",
           f"Fights behind each cell (both maps, both sides): min {spread[0]}, median {spread[1]}, max {spread[2]}.\n" if spread else "",
           matrix, "Both ends, with the error:\n", ends]
    md += ["## Vocation\n", "A vocation is a group of races (`vocations.VOCATIONS`): its score is the mean of its races' scores.\n"]
    vc, vm = vocation_rows(d, "clones"), vocation_rows(d, "mixed")
    md.append(table(["vocation", "clones", "mixed"], [(v, f"{vc[v]:.1f}" if v in vc else "-", f"{vm[v]:.1f}" if v in vm else "-")
                                                      for v in sorted(vc, key=lambda v: -vc[v])]))
    roles = {}
    for (mp, comp), a in d.comp.items():
        roles.setdefault(comp, {})[mp] = a
    md += ["## Team composition (mixed only)\n", "What the clones cannot say: the role mix of the three, by the builds' roles.\n",
           table(["composition", "CTF", "Ermos", "score"],
                 [(c, one(m.get("CTF")), one(m.get("Ermos")), fmt(blend(m))) for c, m in sorted(roles.items(), key=lambda t: -(blend(t[1]) or (0,))[0])])]
    md += attention(d, races, builds, flex)
    path = os.path.join(out, "PREVIEW.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(path)


if __name__ == "__main__":
    main()
