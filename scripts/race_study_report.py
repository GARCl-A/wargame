"""Reads the race study's fights (`sim_results/teste-completo-racas/data`) and writes the tables.

    python scripts/race_study_report.py            # -> REPORT.md and tables/*.csv next to the data

One streaming pass; a score is a win rate with draws counted half, with its standard error. Nothing here
decides what the score should be: SCORE.md argues that from these tables.
"""

from __future__ import annotations

import csv
import glob
import gzip
import json
import math
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gartok import data, vocations

OUT = os.path.join(ROOT, "sim_results", "teste-completo-racas")
TABLES = os.path.join(OUT, "tables")
ATTRS = list(data.ATTRIBUTES)
RACES = [r[1] for r in data.RACES]
HD = {r[1]: r[7] for r in data.RACES}


class Acc:
    """Score accumulator: wins as 1, draws as 0.5, losses as 0."""

    __slots__ = ("d", "n", "s", "ss")

    def __init__(self):
        self.n = self.s = self.ss = self.d = 0

    def add(self, x):
        self.n += 1
        self.s += x
        self.ss += x * x
        self.d += x == 0.5

    @property
    def mean(self):
        return self.s / self.n if self.n else float("nan")

    @property
    def se(self):
        if self.n < 2:
            return float("nan")
        var = max(self.ss / self.n - self.mean ** 2, 0) * self.n / (self.n - 1)
        return math.sqrt(var / self.n)


def score(win, side):
    if win == "D":
        return 0.5
    return 1.0 if win == side else 0.0


def rows():
    for path in sorted(glob.glob(os.path.join(OUT, "data", "*.jsonl.gz"))):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                yield json.loads(line)


def solve(a, b):
    """Gauss elimination for the normal equations; a is n x n, b is n."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[p][c]) < 1e-12:
            return [float("nan")] * n
        m[c], m[p] = m[p], m[c]
        for r in range(n):
            if r != c:
                k = m[r][c] / m[c][c]
                m[r] = [x - k * y for x, y in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] for i in range(n)]


class Study:
    def __init__(self):
        self.inventory = Counter()
        self.errors = Counter()
        self.rounds = defaultdict(list)
        self.draws = Counter()
        self.capped = Counter()
        self.race = defaultdict(Acc)            # (wave, lv, race) -> Acc over both sides
        self.race_a = defaultdict(Acc)          # side A only
        self.pair = defaultdict(Acc)            # (wave, lv, ra, rb) as seen from ra
        self.build = defaultdict(Acc)           # (wave, lv, build)
        self.race_build = defaultdict(Acc)      # (lv, race, build)  [mb]
        self.build_pair = defaultdict(Acc)      # (lv, ba, bb) [rb]
        self.ab = defaultdict(Acc)              # (lv, race): kept side's score
        self.bias = defaultdict(Acc)            # (wave, lv): score of the player-team side
        self.weapon = defaultdict(Acc)          # (lv, weapon)
        self.armor = defaultdict(Acc)
        self.offhand = defaultdict(Acc)
        self.talent = defaultdict(Acc)          # (lv, talent) unit-level, same-build baseline in talent_base
        self.talent_base = defaultdict(Acc)     # (lv, build) unit-level mean
        self.talent_unit = defaultdict(Acc)     # (lv, build, talent)
        self.spell = defaultdict(Acc)           # (lv, spell) unit-level, units that know it
        self.acts = defaultdict(Counter)        # (lv, build) -> action counts
        self.acts_units = Counter()             # (lv, build) -> units
        self.act_win = defaultdict(lambda: [Counter(), Counter(), 0, 0])  # lv -> winners, losers, nW, nL
        self.race_acts = defaultdict(Counter)
        self.race_units = Counter()
        self.race_alive = defaultdict(Acc)      # (lv, race) survival of its units (fd)
        self.margin = defaultdict(Acc)          # (lv, race): fraction of hit points left on the winning side
        self.attr_sum = defaultdict(lambda: [0.0] * 6)
        self.attr_n = Counter()
        self.hp_sum = defaultdict(float)
        self.reg = {}                           # (wave-group, lv) -> normal equation accumulators
        self.fixed = defaultdict(Acc)           # (lv, race) [fx]
        self.vs_role = defaultdict(Acc)         # (lv, role_a, role_b)
        self.cg = defaultdict(Acc)
        self.single = defaultdict(Acc)          # (wave, lv, key): score of side A in the single-factor tests
        self.single_race = defaultdict(Acc)     # (wave, lv, race)

    # -- one fight --------------------------------------------------------------------------------------
    def feed(self, r):
        wave, lv = r["w"], r["lv"]
        self.inventory[(wave, lv)] += 1
        if r["win"] == "E":
            self.errors[(wave, lv, r.get("err", "?"))] += 1
            return
        win = r["win"]
        self.rounds[(wave, lv)].append(r["rounds"])
        self.draws[(wave, lv)] += win == "D"
        self.capped[(wave, lv)] += bool(r.get("capped"))
        sa, sb = score(win, "A"), score(win, "B")
        ra, rb_ = r["ra"], r["rb"]
        sw = r["sw"]
        self.bias[(wave, lv)].add(sb if sw else sa)
        if wave in ("tl", "tc", "gw", "ga", "gs", "sp", "cg", "lw"):
            oa, ob = r.get("oa") or {}, r.get("ob") or {}
            key = {"tl": lambda: oa["force"][0], "tc": lambda: oa["tag"], "cg": lambda: f'{r["ba"]} vs {r["bb"]}', "gw": lambda: oa["weapon"], "lw": lambda: ra, "ga": lambda: oa["armor"],
                   "gs": lambda: "shield vs torch", "sp": lambda: f'{r["ba"]} without {ob["drop_spell"]}'}[wave]()
            self.single[(wave, lv, key)].add(sa)
            self.single_race[(wave, lv, ra)].add(sa)
        if wave == "cg":
            self.cg[(lv, r["ba"], r["bb"])].add(sa)
            if r["ba"] != r["bb"]:
                self.cg[(lv, r["bb"], r["ba"])].add(sb)
        if wave == "mx":
            self.pair[(lv, ra, rb_)].add(sa)
            if ra != rb_:
                self.pair[(lv, rb_, ra)].add(sb)
        if wave in ("fd", "fx", "mb", "rb", "mx", "ef"):
            self.race[(wave, lv, ra)].add(sa)
            self.race[(wave, lv, rb_)].add(sb)
            self.race_a[(wave, lv, ra)].add(sa)
        if wave == "fx":
            self.fixed[(lv, ra)].add(sa)
            self.fixed[(lv, rb_)].add(sb)
        if wave in ("fd", "mb", "rb", "ef"):
            self.build[(wave, lv, r["ba"])].add(sa)
            self.build[(wave, lv, r["bb"])].add(sb)
        if wave == "mb":
            self.race_build[(lv, ra, r["ba"])].add(sa)
        if wave == "rb":
            self.build_pair[(lv, r["ba"], r["bb"])].add(sa)
            if r["ba"] != r["bb"]:
                self.build_pair[(lv, r["bb"], r["ba"])].add(sb)
        if wave == "ab":
            self.ab[(lv, ra)].add(sb)
        if wave in ("fd", "mb", "rb"):
            self._units(r, lv, wave, sa, sb)

    def _units(self, r, lv, wave, sa, sb):
        units = r["units"]
        res = {"A": sa, "B": sb}
        builds = {"A": r["ba"], "B": r["bb"]}
        win = r["win"]
        side_hp = {"A": [0.0, 0.0], "B": [0.0, 0.0]}
        for u in units:
            s = u["s"]
            x = res[s]
            b = builds[s]
            key = (lv, b)
            self.weapon[(lv, u["weapon"])].add(x)
            self.armor[(lv, u["armor"])].add(x)
            self.offhand[(lv, u["off"])].add(x)
            self.talent_base[key].add(x)
            for t in set(u["tal"]):
                self.talent_unit[(lv, b, t)].add(x)
            for sp in u["spells"]:
                self.spell[(lv, sp)].add(x)
            for k, v in u["acts"].items():
                self.acts[key][k] += v
                self.race_acts[(lv, u["race"])][k] += v
            self.acts_units[key] += 1
            self.race_units[(lv, u["race"])] += 1
            self.race_alive[(lv, u["race"])].add(1.0 if u["alive"] else 0.0)
            side_hp[s][0] += u["hp"]
            side_hp[s][1] += u["hp_max"]
            if win in ("A", "B"):
                bucket = self.act_win[lv]
                idx = 0 if s == win else 1
                for k, v in u["acts"].items():
                    bucket[idx][k] += v
                bucket[2 + idx] += 1
        if win in ("A", "B") and side_hp[win][1]:
            self.margin[(lv, r["ra"] if win == "A" else r["rb"])].add(side_hp[win][0] / side_hp[win][1])
        if wave == "fd":
            self._regress(r, lv, sa)

    def _regress(self, r, lv, sa):
        if r["win"] == "D":
            return
        feats = []
        for attr_i in range(6):
            va = [u["attr"][attr_i] for u in r["units"] if u["s"] == "A"]
            vb = [u["attr"][attr_i] for u in r["units"] if u["s"] == "B"]
            feats.append(sum(va) / len(va) - sum(vb) / len(vb))
        feats.append((HD[r["ra"]] - HD[r["rb"]]) / 2.0)
        feats.append(1.0)
        y = 1.0 if r["win"] == "A" else 0.0
        n = len(feats)
        acc = self.reg.setdefault(lv, [[[0.0] * n for _ in range(n)], [0.0] * n, 0])
        for i in range(n):
            for j in range(n):
                acc[0][i][j] += feats[i] * feats[j]
            acc[1][i] += feats[i] * y
        acc[2] += 1


def write_csv(name, header, body):
    os.makedirs(TABLES, exist_ok=True)
    with open(os.path.join(TABLES, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(body)


def fmt(a, d=3):
    return f"{a.mean:.{d}f} ±{a.se:.{d}f} (n={a.n})" if a.n else "-"


def md_table(header, body):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in body]
    return "\n".join(out)


def race_scores(st, lv):
    """The field score of every race: fd, both sides pooled."""
    return {race: st.race[("fd", lv, race)] for race in RACES if ("fd", lv, race) in st.race}


MAP_WEIGHT = {"fd": 0.5, "ef": 0.5}           # Ribbit Brothers (fd) and Ermos (ef), half each
LEVEL_WEIGHT = {0: 1 / 3, 5: 2 / 3}           # level 5 shows the build better than level 0
BUILD_WAVE = {"fd": "mb", "ef": "ef"}         # the wave each map's build score is read from


def blend(parts):
    """`(score x100, se x100)` of the weighted mean of `(weight, Acc)`; the weights are renormalised over the parts present
    (a build with no level-0 version scores on level 5 alone)."""
    parts = [(w, a) for w, a in parts if a is not None and a.n]
    total = sum(w for w, _ in parts)
    if not total:
        return None
    return (100 * sum(w * a.mean for w, a in parts) / total,
            100 * math.sqrt(sum((w * a.se) ** 2 for w, a in parts)) / total)


def score_parts(key):
    """The four cells of a score: Ribbit (fd) and Ermos (ef) at each level; `key(wave, lv)` finds the Acc."""
    return [(MAP_WEIGHT[wave] * LEVEL_WEIGHT[lv], key(wave, lv)) for wave in MAP_WEIGHT for lv in LEVEL_WEIGHT]


def _pct(table, key):
    return f"{100 * table[key].mean:.1f}" if key in table else "-"


def score_blocks(st):
    L = []
    comp = {r: blend(score_parts(lambda w, lv, r=r: st.race.get((w, lv, r)))) for r in RACES}
    comp = {r: v for r, v in comp.items() if v}
    if comp:
        rk = sorted(comp, key=lambda r: -comp[r][0])
        L += ["## 0. Proposed combat score", "",
              ("Race score = 100 x the weighted mean of the field win rate on two maps (Ribbit Brothers, Ermos: half each) at two "
               "levels (L5 two thirds, L0 one third); 50 = an average race in this field. Vocation score = mean of its six races."), "",
              md_table(["rank", "race", "Ribbit L0", "Ribbit L5", "Ermos L0", "Ermos L5", "score", "SE"],
                       [[i, r] + [_pct(st.race, (w, lv, r)) for w in MAP_WEIGHT for lv in LEVEL_WEIGHT] + [f"{comp[r][0]:.1f}", f"{comp[r][1]:.1f}"]
                        for i, r in enumerate(rk, 1)]), ""]
        vrows = []
        for v in vocations.VOCATIONS.values():
            vals = [comp[r][0] for r in v.races if r in comp]
            vrows.append([v.id, f"{sum(vals) / len(vals):.1f}", f"{min(vals):.1f}", f"{max(vals):.1f}",
                          ", ".join(f"{r} {comp[r][0]:.0f}" for r in sorted(v.races, key=lambda r: -comp[r][0]) if r in comp)])
        vrows.sort(key=lambda row: -float(row[1]))
        L += [md_table(["vocation", "score", "weakest", "strongest", "races"], vrows), ""]
        write_csv("proposed_score_races.csv", ["race", "score", "se"], [[r, comp[r][0] / 100, comp[r][1] / 100] for r in rk])
        write_csv("proposed_score_vocations.csv", ["vocation", "score", "weakest", "strongest", "races"], vrows)

    ids = sorted({k[2] for k in st.build if k[0] in BUILD_WAVE.values()})
    bsc = {b: blend(score_parts(lambda w, lv, b=b: st.build.get((BUILD_WAVE[w], lv, b)))) for b in ids}
    bsc = {b: v for b, v in bsc.items() if v}
    if bsc:
        bk = sorted(bsc, key=lambda b: -bsc[b][0])
        L += ["## 0b. Proposed build score", "",
              ("Same weights as the race score. Ribbit comes from the build wave (mb), Ermos from the field wave (ef). A build whose "
               "first weapon the level-0 budget cannot pay for (the bows, the crossbow, the Rapier) has no level-0 cells and scores on level 5."), "",
              md_table(["rank", "build", "Ribbit L0", "Ribbit L5", "Ermos L0", "Ermos L5", "score", "SE"],
                       [[i, b] + [_pct(st.build, (BUILD_WAVE[w], lv, b)) for w in MAP_WEIGHT for lv in LEVEL_WEIGHT] + [f"{bsc[b][0]:.1f}", f"{bsc[b][1]:.1f}"]
                        for i, b in enumerate(bk, 1)]), ""]
        write_csv("proposed_score_builds.csv", ["build", "score", "se"], [[b, bsc[b][0] / 100, bsc[b][1] / 100] for b in bk])
    return L


def build_report(st):
    L = ["# Race study: tables", "", "Generated by `scripts/race_study_report.py`. Score = win rate, draws half.", ""]
    L += ["## 1. Data", ""]
    body = []
    for (wave, lv), n in sorted(st.inventory.items()):
        rr = st.rounds.get((wave, lv), [])
        body.append([wave, lv, n, f"{st.draws[(wave, lv)] / max(len(rr), 1):.1%}", st.capped[(wave, lv)],
                     f"{sum(rr) / max(len(rr), 1):.1f}", sum(c for (w, l, _), c in st.errors.items() if (w, l) == (wave, lv))])
    L += [md_table(["wave", "level", "fights", "draws", "turn-capped", "mean rounds", "errors"], body), ""]
    L += ["### Side bias (score of the player-team side; 0.5 = none)", ""]
    L += [md_table(["wave", "level", "score"], [[w, lv, fmt(a)] for (w, lv), a in sorted(st.bias.items())]), ""]

    for lv in (0, 5):
        scores = race_scores(st, lv)
        if not scores:
            continue
        ranked = sorted(scores.items(), key=lambda kv: -kv[1].mean)
        rows_ = []
        for race, a in ranked:
            fx = st.fixed.get((lv, race))
            mx = [st.pair[(lv, race, o)].mean for o in RACES if (lv, race, o) in st.pair]
            ab = st.ab.get((lv, race))
            rows_.append([race, HD[race], fmt(a), fmt(fx) if fx else "-", f"{sum(mx) / len(mx):.3f}" if mx else "-",
                          fmt(ab) if ab else "-", f"{st.race_alive[(lv, race)].mean:.2f}" if (lv, race) in st.race_alive else "-"])
        L += [f"## 2. Race scores, level {lv}", "",
              "field = vs a uniform field of races and builds (wave fd); fixed = same with every attribute 10 and "
              "average hit dice (wave fx); matrix = mean over the 19 opposing races with the reference build "
              "(sword, shield, chainmail; wave mx); racial = score of the squad that keeps its racial talents vs the "
              "same squad without them (wave ab, level 5); survival = share of the race's units alive at the end (fd/mb/rb).", "",
              md_table(["race", "hit die", "field", "fixed body", "matrix", "racial on vs off", "survival"], rows_), ""]
        write_csv(f"race_scores_L{lv}.csv", ["race", "hd", "field", "se", "n", "fixed", "matrix"],
                  [[r, HD[r], a.mean, a.se, a.n, st.fixed[(lv, r)].mean if (lv, r) in st.fixed else "",
                    (sum(st.pair[(lv, r, o)].mean for o in RACES if (lv, r, o) in st.pair) / max(1, sum(1 for o in RACES if (lv, r, o) in st.pair)))] for r, a in ranked])

        voc = []
        for v in vocations.VOCATIONS.values():
            vals = [scores[r].mean for r in v.races if r in scores]
            ses = [scores[r].se for r in v.races if r in scores]
            voc.append([v.id, ", ".join(v.races), f"{sum(vals) / len(vals):.3f}",
                        f"±{math.sqrt(sum(s * s for s in ses)) / len(ses):.3f}", f"{min(vals):.3f} .. {max(vals):.3f}"])
        voc.sort(key=lambda row: -float(row[2]))
        L += [f"### Vocation combat score, level {lv} (mean of its six races' field scores)", "",
              md_table(["vocation", "races", "score", "SE", "range"], voc), ""]
        write_csv(f"vocation_scores_L{lv}.csv", ["vocation", "races", "score", "se", "range"], voc)

        L += [f"### Pair matrix, level {lv} (row race beats column race; reference build)", ""]
        header = ["race"] + [r[:4] for r in RACES]
        mrows = [[a] + [f"{st.pair[(lv, a, b)].mean:.2f}" if (lv, a, b) in st.pair else "-" for b in RACES] for a in RACES]
        L += [md_table(header, mrows), ""]
        write_csv(f"pair_matrix_L{lv}.csv", ["race"] + RACES, mrows)

        reg = st.reg.get(lv)
        if reg and reg[2] > 500:
            coef = solve(reg[0], reg[1])
            names = [f"{a} mod" for a in ATTRS] + ["hit die (one step, d6->d8)", "intercept"]
            L += [f"### What decides a fight, level {lv} (wave fd; linear probability on squad differences, {reg[2]} fights)", "",
                  "Each coefficient is the change in P(A wins) for +1 on the squad mean difference: one attribute modifier, "
                  "or one step of the race's hit die. One Constitution modifier point (+2 score) is +1 HP per hit die, the same "
                  "as one die step on average, so the two rows should be close.", "",
                  md_table(["term", "coefficient"], [[n, f"{c:+.4f}"] for n, c in zip(names, coef)]), ""]

    titles = {"cg": "caster builds in identical gear (Hammer; Chainmail at L5, Leather Jerkin at L0), school against school",
              "tl": "combat talent forced vs banned (same race, plain sword/shield/chainmail kit)",
              "tc": "talent combination (all of its talents forced vs all banned; dex lines on a Rapier, bow lines on a Longbow)",
              "lw": "Large weapons first (a Centaur's body, a Goliath's Giant's Grip) vs the same build with Medium ones, same race",
              "gw": "weapon vs Sword (same race, same kit otherwise)",
              "ga": "armour vs no armour and no shield (same race, Sword)",
              "gs": "Dwarf Shield (no torch) vs Torch (no shield)",
              "sp": "caster build with every spell vs the same build missing one spell"}
    for wave, title in titles.items():
        for lv in (0, 5):
            body = sorted(((k[2], a) for k, a in st.single.items() if k[0] == wave and k[1] == lv), key=lambda kv: -kv[1].mean)
            if body:
                L += [f"## 9. Single-factor test `{wave}`, level {lv}: {title}", "",
                      "Score of the side that has the factor; 0.50 = no effect.", "",
                      md_table(["factor", "score", "z"], [[k, fmt(a), f"{(a.mean - 0.5) / a.se:+.1f}" if a.se else "-"] for k, a in body]), ""]
                write_csv(f"single_{wave}_L{lv}.csv", ["factor", "score", "se", "n"], [[k, a.mean, a.se, a.n] for k, a in body])

    L += score_blocks(st)
    for lv in (0, 5):
        ids = sorted({k[1] for k in st.cg if k[0] == lv})
        if ids:
            g = [[a] + [f"{st.cg[(lv, a, b)].mean:.2f}" if (lv, a, b) in st.cg else "-" for b in ids] for a in ids]
            avg = [[a, f"{sum(st.cg[(lv, a, b)].mean for b in ids if (lv, a, b) in st.cg and b != a) / max(1, sum(1 for b in ids if (lv, a, b) in st.cg and b != a)):.3f}"] for a in ids]
            L += [f"## 2c. Casters in identical gear, level {lv} (wave cg; row beats column; same race both sides)", "",
                  md_table(["build"] + [b[:8] for b in ids], g), "", md_table(["build", "mean vs the others"], sorted(avg, key=lambda x: -float(x[1]))), ""]
    L += ["## 3. Racial ability value (level 5, wave ab)", "",
          "Score of the squad that keeps its racial talents against the identical squad without them. 0.50 = worth nothing in this fight.", ""]
    ab = sorted(((r, a) for (lv, r), a in st.ab.items() if lv == 5), key=lambda kv: -kv[1].mean)
    L += [md_table(["race", "score", "z"], [[r, fmt(a), f"{(a.mean - 0.5) / a.se:+.1f}" if a.se else "-"] for r, a in ab]), ""]

    for lv in (0, 5):
        mb = [(b, st.build[("mb", lv, b)]) for b in sorted({k[2] for k in st.build if k[0] == "mb" and k[1] == lv})]
        if not mb:
            continue
        L += [f"## 4. Builds, level {lv}", "", "Score of the build against the uniform field (wave mb, races pooled).", "",
              md_table(["build", "score"], [[b, fmt(a)] for b, a in sorted(mb, key=lambda kv: -kv[1].mean)]), ""]
        builds = [b for b, _ in sorted(mb, key=lambda kv: -kv[1].mean)]
        grid = [[r] + [f"{st.race_build[(lv, r, b)].mean:.2f}" if (lv, r, b) in st.race_build else "-" for b in builds] for r in RACES]
        L += [f"### Race x build, level {lv}", "", md_table(["race"] + [b[:8] for b in builds], grid), ""]
        write_csv(f"race_build_L{lv}.csv", ["race"] + builds, grid)
        best = []
        for r in RACES:
            cells = [(st.race_build[(lv, r, b)].mean, b) for b in builds if (lv, r, b) in st.race_build]
            if cells:
                best.append([r, f"{max(cells)[1]} {max(cells)[0]:.2f}", f"{min(cells)[1]} {min(cells)[0]:.2f}"])
        L += [f"### Best and worst build per race, level {lv}", "", md_table(["race", "best", "worst"], best), ""]
        pairs = sorted({k[1] for k in st.build_pair if k[0] == lv})
        if pairs:
            g2 = [[a] + [f"{st.build_pair[(lv, a, b)].mean:.2f}" if (lv, a, b) in st.build_pair else "-" for b in pairs] for a in pairs]
            L += [f"### Build vs build, level {lv} (row beats column; races random; wave rb)", "",
                  md_table(["build"] + [b[:6] for b in pairs], g2), ""]
            write_csv(f"build_pair_L{lv}.csv", ["build"] + pairs, g2)

    for lv in (0, 5):
        w = sorted(((k[1], a) for k, a in st.weapon.items() if k[0] == lv and a.n >= 200), key=lambda kv: -kv[1].mean)
        ar = sorted(((k[1], a) for k, a in st.armor.items() if k[0] == lv and a.n >= 200), key=lambda kv: -kv[1].mean)
        of = sorted(((k[1], a) for k, a in st.offhand.items() if k[0] == lv and a.n >= 200), key=lambda kv: -kv[1].mean)
        L += [f"## 5. Gear, level {lv} (unit level: score of the side of the units holding it; confounded with the build)", "",
              md_table(["weapon", "score"], [[str(k), fmt(a)] for k, a in w]), "",
              md_table(["armour", "score"], [[str(k), fmt(a)] for k, a in ar]), "",
              md_table(["off hand", "score"], [[str(k), fmt(a)] for k, a in of]), ""]

    L += ["## 6. Talents (level 5)", "",
          "Lift = score of units holding the talent minus the mean of their own build (same build, so the weapon and "
          "armour cancel). Only talents the build did not fix show a real lift; the build's own priority talents "
          "always come together.", ""]
    lifts = defaultdict(lambda: [0.0, 0])
    for (lv, b, t), a in st.talent_unit.items():
        if lv != 5 or a.n < 30:
            continue
        base = st.talent_base[(lv, b)]
        if base.n:
            lifts[t][0] += (a.mean - base.mean) * a.n
            lifts[t][1] += a.n
    trows = sorted(((t, s / n, n) for t, (s, n) in lifts.items() if n >= 300), key=lambda x: -x[1])
    L += [md_table(["talent", "lift", "unit-fights"], [[t, f"{x:+.3f}", n] for t, x, n in trows]), ""]
    write_csv("talent_lift_L5.csv", ["talent", "lift", "unit_fights"], trows)

    L += ["## 7. Spells (units that knew the spell)", ""]
    for lv in (0, 5):
        sp = sorted(((k[1], a) for k, a in st.spell.items() if k[0] == lv), key=lambda kv: -kv[1].mean)
        L += [f"Level {lv}", "", md_table(["spell", "score"], [[k, fmt(a)] for k, a in sp]), ""]

    L += ["## 8. Actions", ""]
    for lv in (0, 5):
        win, lose, nw, nl = st.act_win[lv]
        if not nw:
            continue
        names = sorted(set(win) | set(lose), key=lambda k: -(win[k] + lose[k]))[:25]
        body = [[k, f"{win[k] / nw:.2f}", f"{lose[k] / nl:.2f}", f"{win[k] / nw - lose[k] / nl:+.2f}"] for k in names]
        L += [f"Actions per unit per fight, winners vs losers, level {lv}", "",
              md_table(["action", "winners", "losers", "diff"], body), ""]
    classes = sorted({k[1] for k in st.acts_units})
    for lv in (0, 5):
        cols = ["attack", "move", "demoralize", "assess", "defend", "stabilize", "first_aid", "cast_magic_missile",
                "cast_sleep", "cast_hex", "cast_dragonfire", "cast_water_jet", "cast_grasping_roots",
                "cast_healing_touch", "reload", "power_shot", "parry_strike"]
        body = []
        for b in classes:
            n = st.acts_units.get((lv, b))
            if n:
                body.append([b] + [f"{st.acts[(lv, b)][c] / n:.2f}" for c in cols])
        L += [f"Actions per unit per fight by build, level {lv}", "", md_table(["build"] + [c.replace("cast_", "") for c in cols], body), ""]
    return "\n".join(L)


def main():
    st = Study()
    n = 0
    for r in rows():
        st.feed(r)
        n += 1
    text = build_report(st)
    with open(os.path.join(OUT, "REPORT.md"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"{n} fights -> {os.path.join(OUT, 'REPORT.md')}")


if __name__ == "__main__":
    main()
