"""Reads the build study back (`python scripts/race_study.py run`, folder `sim_results/<out>`) and writes `REPORT.md`
with one section per question the author asked: the ranking of the builds, the build x build matrix, the race x build
table (the races by vocation), the talent variants, the weapon sweeps and, per build, what the units did in the fights.

    python scripts/build_study_report.py [--out teste-builds]
"""

from __future__ import annotations

import argparse
import glob
import gzip
import json
import math
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gartok import vocations
from scripts import race_study_builds as rb

MIN_SQUADS = 40
MAP_WEIGHT = {"ctf": 0.5, "ermos": 0.5}      # the dark map and the lit one, half each
LEVEL_WEIGHT = {5: 1.0}          # level 0 has no build (no talents, no money): only level 5 scores
VIABLE = 0.5                                 # a build is viable for a race above this blended win rate


class Acc:
    """Wins as 1, draws as 0.5, losses as 0."""

    def __init__(self):
        self.n = 0
        self.s = 0.0

    def add(self, x):
        self.n += 1
        self.s += x

    @property
    def p(self):
        return self.s / self.n if self.n else float("nan")

    @property
    def se(self):
        return math.sqrt(self.p * (1 - self.p) / self.n) if self.n else float("nan")

    def __str__(self):
        return f"{100 * self.p:.1f} ±{100 * 1.96 * self.se:.1f} (n={self.n})" if self.n else "-"


def score(win, side):
    if win == "D":
        return 0.5
    return 1.0 if win == side else 0.0


def rows(out):
    for path in sorted(glob.glob(os.path.join(out, "data", "*.jsonl.gz"))):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                yield json.loads(line)


def sides(r):
    return (("A", r["ra"], r["ba"], r.get("oa") or {}), ("B", r["rb"], r["bb"], r.get("ob") or {}))


def table(header, body):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in body]
    return "\n".join(out) + "\n"


class Study:
    def __init__(self):
        self.errors = Counter()
        self.rank = defaultdict(Acc)            # (lv, build) -> score in the field wave (the CTF map, in the dark)
        self.ermos = defaultdict(Acc)           # (lv, build) -> the same on the Ermos, lit
        self.race_build = defaultdict(Acc)      # (lv, race, build)
        self.matrix = defaultdict(Acc)          # (lv, build_a, build_b) -> score of a
        self.variant = defaultdict(Acc)         # (lv, build, variant) -> score in its mirrors
        self.pair = defaultdict(Acc)            # (lv, build, va, vb) -> score of va
        self.weapon = defaultdict(Acc)          # (lv, build, weapon)
        self.units = defaultdict(lambda: defaultdict(Counter))      # (lv, build) -> metric -> Counter
        self.talent = defaultdict(Acc)          # (lv, build, talent, held): score of the squads where one of the three held it, or none did
        self.first = defaultdict(Acc)           # (lv, build, acted_first) -> score
        self.armed = defaultdict(Acc)           # (lv, build, weapon) -> score of the fights where all three were armed
        self.armed_units = defaultdict(Counter)     # (lv, build, weapon) -> units, unarmed
        self.gear = defaultdict(Counter)        # (lv, build) -> "armor"/"off"/"weapon" -> value counts
        self.read0 = defaultdict(lambda: [0, 0])     # (lv, build) -> [foes read to HARD, foes] at the first action
        self.cell = defaultdict(Acc)            # (lv, map, race, build): the field wave on the CTF map ("ctf") and on the Ermos
        self.race_cell = defaultdict(Acc)       # (lv, map, race): the same over all its builds
        self.gw = defaultdict(Acc)              # (lv, weapon) -> plain unit with it against the Sword
        self.spell = defaultdict(Acc)           # (build, spell) -> score of the full kit against the kit without the spell (level 5)
        self.racial = defaultdict(Acc)          # (race, talent) -> score of the unit with it against the same unit without a racial

    def add(self, r):
        if r["win"] == "E":
            self.errors[r.get("err", "")[:80]] += 1
            return
        lv, wave = r["lv"], r["w"]
        for side, race, build, over in sides(r):
            x = score(r["win"], side)
            if wave == "mb" and side == "A":
                self.rank[lv, build].add(x)
                self.race_build[lv, race, build].add(x)
                self.cell[lv, "ctf", race, build].add(x)
                self.race_cell[lv, "ctf", race].add(x)
            if wave == "ef" and side == "A":
                self.ermos[lv, build].add(x)
                self.cell[lv, "ermos", race, build].add(x)
                self.race_cell[lv, "ermos", race].add(x)
            if wave == "gw" and side == "A":
                self.gw[lv, over["weapon"]].add(x)
            if wave == "sp" and side == "A":
                self.spell[build, r["ob"]["drop_spell"]].add(x)
            if wave == "rt" and side == "A":
                self.racial[race, over["rt"]].add(x)
            if wave == "rb":
                other = r["bb"] if side == "A" else r["ba"]
                self.matrix[lv, build, other].add(x)
            if wave == "vr":
                var = over.get("var")
                self.variant[lv, build, var].add(x)
                other = (r.get("ob") if side == "A" else r.get("oa") or {}).get("var")
                self.pair[lv, build, var, other].add(x)
            if wave == "ws" and side == "A":
                self.weapon[lv, build, over["weapon"]].add(x)
                mine = [u for u in r["units"] if u["s"] == "A"]
                unarmed = sum(u["weapon"] is None for u in mine)
                self.armed_units[lv, build, over["weapon"]].update(units=len(mine), unarmed=unarmed)
                if not unarmed:
                    self.armed[lv, build, over["weapon"]].add(x)
            if wave in ("mb", "rb", "vr") and build != rb.RANDOM_KIT:
                self.behaviour(r, lv, side, build, x, wave)

    def behaviour(self, r, lv, side, build, x, wave):
        """The per-unit counters. The variants' fights feed only Free Step (it is a variant of the Rapier and the Dagger, not of
        the base build)."""
        key = (lv, build)
        got = r.get("read0", {}).get(side) if wave != "vr" else None
        if got:
            tot = self.read0[key]
            tot[0] += got["full"]
            tot[1] += got["foes"]
        mine = [u for u in r["units"] if u["s"] == side]
        if wave != "vr":
            ranks = [u["init"][0] for u in mine if u.get("init")]
            if ranks:
                first = min(ranks) == 0
                self.first[lv, build, first].add(x)
                self.units[key]["init"]["fights"] += 1
                self.units[key]["init"]["shouts"] += r.get("shouts", {}).get(side, 0)
                self.units[key]["init"]["first"] += int(first)
                self.units[key]["init"]["rank"] += sum(ranks) / len(ranks)
            if build == "archer":
                for tid in rb.COMBAT_IDS - set(rb.lookup(build).combat):
                    self.talent[lv, build, tid, any(tid in u["tal"] for u in mine)].add(x)
        for u in mine:
            m = self.units[key]
            a = u["acts"]
            held = set(u["tal"])
            if wave != "vr":
                m["n"]["units"] += 1
                for k, v in a.items():
                    m["acts"][k] += v
            if wave == "vr":
                f = m["free_step"]
                side_ = "holders" if "free_step" in held else "without_units"
                f[side_] += 1
                if side_ == "holders":
                    f["used"] += int(a.get("free_step", 0) > 0)
                    f["uses"] += a.get("free_step", 0)
                    f["throws"] += a.get("throw", 0)
                else:
                    f["throws_without"] += a.get("throw", 0)
                continue
            m["init"]["bonus"] += u["init"][1] if u.get("init") else 0
            m["r1"]["dmg"] += a.get("r1dmg", 0)
            g = self.gear[key]
            g["armor:" + str(u["armor"])] += 1
            g["off:" + str(u["off"])] += 1
            g["weapon:" + str(u["weapon"])] += 1


def blend(parts):
    """The weighted mean (x100) of `(weight, Acc)` parts; the weights renormalise over the cells present (a build with no level 0
    version scores on level 5 alone)."""
    parts = [(w, a) for w, a in parts if a is not None and a.n]
    total = sum(w for w, _ in parts)
    return 100 * sum(w * a.p for w, a in parts) / total if total else None


def cells(source, *key):
    """The four cells (map x level) of a score, with their weights; `source` is `st.cell` or `st.race_cell`."""
    return [(MAP_WEIGHT[m] * LEVEL_WEIGHT[lv], source.get((lv, m, *key))) for m in MAP_WEIGHT for lv in LEVEL_WEIGHT]


def pct(x):
    return "-" if x is None else f"{x:.1f}"


def pm(acc):
    return f"{100 * acc.p:.1f} ±{196 * acc.se:.1f}" if acc is not None and acc.n else "-"


def weapon_table(st):
    names = sorted({w for (_lv, w) in st.gw}, key=lambda w: -(100 * st.gw[5, w].p if (5, w) in st.gw else 0))
    body = [(w, pm(st.gw.get((0, w))), pm(st.gw.get((5, w)))) for w in names]
    return table(["weapon (a plain fighter, same race both sides, against the Sword)", "level 0", "level 5"], body)


def spell_table(st):
    body = []
    for (bid, sid), acc in sorted(st.spell.items(), key=lambda t: -t[1].p):
        m = st.units.get((5, bid))
        used = m["acts"]["cast_" + sid] / m["n"]["units"] if m and m["n"]["units"] else float("nan")
        body.append((bid, sid, f"{100 * (acc.p - 0.5):+.1f} ±{196 * acc.se:.1f}", f"{used:.2f}", acc.n))
    return table(["build", "spell", "what it adds (points of win rate, full kit against the kit without it)", "casts/unit", "fights"], body)


def build_scores(st):
    ids = sorted({b for (_l, _m, _r, b) in st.cell})
    body = []
    for bid in ids:
        pooled = {}
        for lv in LEVEL_WEIGHT:
            for m in MAP_WEIGHT:
                acc = Acc()
                for (l, mm, _r, b), a in st.cell.items():
                    if (l, mm, b) == (lv, m, bid):
                        acc.n += a.n
                        acc.s += a.s
                pooled[lv, m] = acc if acc.n else None
        parts = [(MAP_WEIGHT[m] * LEVEL_WEIGHT[lv], pooled[lv, m]) for m in MAP_WEIGHT for lv in LEVEL_WEIGHT]
        body.append((blend(parts), bid, *[pm(pooled[lv, m]) for m in MAP_WEIGHT for lv in LEVEL_WEIGHT]))
    body.sort(key=lambda t: -(t[0] if t[0] is not None else -1))
    return table(["build", "score", *[f"{name} L{lv}" for name in ("CTF", "Ermos") for lv in LEVEL_WEIGHT]], [(b, pct(sc), *rest) for sc, b, *rest in body])


def race_scores(st):
    """`race -> (blended score, {build: blended score})`: the build score of a race blends its four cells."""
    races = sorted({r for (_l, _m, r, _b) in st.cell})
    out = {}
    for race in races:
        builds = sorted({b for (_l, _m, r, b) in st.cell if r == race})
        out[race] = (blend(cells(st.race_cell, race)), {b: blend(cells(st.cell, race, b)) for b in builds})
    return out


def race_table(scores):
    body = []
    for race, (sc, per) in sorted(scores.items(), key=lambda t: -(t[1][0] or 0)):
        ranked = sorted(per.items(), key=lambda t: -(t[1] or 0))
        viable = sum(1 for _b, v in ranked if v is not None and v > 100 * VIABLE)
        top = [v for _b, v in ranked[:3] if v is not None]
        body.append((race, pct(sc), f"{viable}/{len(ranked)} ({100 * viable / len(ranked):.0f}%)" if ranked else "-",
                     pct(sum(top) / len(top)) if top else "-",
                     ", ".join(f"{b} {pct(v)}" for b, v in ranked[:3])))
    return table(["race", "score", f"flexibility (builds above {100 * VIABLE:.0f}% / builds it fields)", "mean of its three best", "its three best builds (win rate)"], body)


def vocation_table(scores):
    body = []
    for v in vocations.VOCATIONS.values():
        got = [(r, scores[r][0]) for r in v.races if r in scores and scores[r][0] is not None]
        if got:
            body.append((sum(x for _r, x in got) / len(got), v.id, ", ".join(f"{r} {x:.0f}" for r, x in got)))
    body.sort(reverse=True)
    return table(["vocation", "score (mean of its races)", "its races"], [(v, pct(sc), rs) for sc, v, rs in body])


def racial_table(st):
    body = []
    for race in sorted({r for (r, _t) in st.racial}):
        mine = sorted(((100 * (a.p - 0.5), 196 * a.se, t, a.n) for (r, t), a in st.racial.items() if r == race), reverse=True)
        felt = [m for m in mine if abs(m[0]) > m[1]]
        quiet = [m[2] for m in mine if abs(m[0]) <= m[1]]
        top = felt[0] if felt else None
        body.append((race, f"{top[2]} ({top[0]:+.1f} ±{top[1]:.1f})" if top else "no impact",
                     ", ".join(f"{t} {d:+.1f}" for d, _e, t, _n in felt[1:]) or "-", ", ".join(quiet) or "-"))
    return table(["race", "strongest racial talent (points over having none)", "others with impact", "no impact in combat"], body)


def sweep_section(st, lv):
    out = []
    for bid in (*rb.SWEEP_BUILDS, "thrower"):
        rows_ = sorted(((acc, w) for (lvl, b, w), acc in st.weapon.items() if lvl == lv and b == bid), key=lambda t: -t[0].p)
        if not rows_:
            continue
        body = []
        for acc, w in rows_:
            u = st.armed_units[lv, bid, w]
            armed = st.armed.get((lv, bid, w))
            body.append((w, acc, f"{100 * (1 - u['unarmed'] / u['units']):.0f}%", armed or "-"))
        out.append(f"**{bid}**\n\n" + table(["weapon", "score vs sword and shield", "units armed", "score of the fights where all three were armed"], body))
    return "\n".join(out)


def per_unit(m, name):
    n = m["n"]["units"]
    return m["acts"][name] / n if n else float("nan")


def attack_names(m):
    """The actions that rolled to hit: those with a `hit.` or `miss.` counter."""
    return {k.split(".", 1)[1] for k in m["acts"] if k.startswith(("hit.", "miss."))}


def share(m, prefix):
    """Of the actions that rolled to hit, the share that had the context `prefix` (`f.` off-guard foe, `d.` demoralized foe)."""
    names = attack_names(m)
    total = sum(m["acts"][nm] for nm in names)
    return sum(m["acts"][prefix + nm] for nm in names) / total if total else float("nan")


def behaviour_section(st, lv):
    body = []
    for bid in rb.BUILD_IDS:
        m = st.units.get((lv, bid))
        if not m:
            continue
        n = m["n"]["units"]
        full, foes = st.read0[lv, bid]
        casts = {k[5:]: v / n for k, v in m["acts"].items() if k.startswith("cast_")}
        body.append((
            bid, n,
            f"{per_unit(m, 'attack'):.1f}", f"{100 * share(m, 'f.'):.0f}%", f"{per_unit(m, 'sneak_attack'):.2f}",
            f"{per_unit(m, 'demoralize'):.2f}", f"{100 * share(m, 'd.'):.0f}%",
            f"{per_unit(m, 'assess'):.2f}", f"{m['acts']['assess.full'] / n:.2f}", f"{full / foes:.2f}" if foes else "-",
            f"{per_unit(m, 'throw'):.2f}", f"{sum(casts.values()):.1f}",
            ", ".join(f"{k} {v:.1f}" for k, v in sorted(casts.items(), key=lambda t: -t[1])[:4]) or "-",
        ))
    head = ["build", "units", "attacks/unit", "attacks on an off-guard foe", "sneak attacks/unit", "demoralize/unit",
            "attacks on a demoralized foe", "assess/unit", "foes read to HARD by an assess/unit",
            "foes at HARD at the first action (of 3)", "throws/unit", "casts/unit", "spells (per unit)"]
    return table(head, body)


def free_step_section(st, lv):
    out = []
    for bid in ("rapier_duelist", "dagger_skirmisher"):
        m = st.units.get((lv, bid))
        if not m or not m["free_step"]:
            continue
        f = m["free_step"]
        out.append(f"- **{bid}**: {f['holders']} units hold Free Step; {100 * f['used'] / f['holders']:.0f}% used it at least once"
                   f" ({f['uses'] / f['holders']:.1f} times per unit). " if f["holders"] else f"- **{bid}**: nobody held Free Step. ")
        out[-1] += f"Throws per unit: {f['throws'] / f['holders']:.2f} with Free Step, " if f["holders"] else "Throws per unit: "
        out[-1] += f"{f['throws_without'] / max(f['without_units'], 1):.2f} without."
    return "\n".join(out)


def crit_section(st, lv):
    out = []
    for bid in ("smart_miner",):
        m = st.units.get((lv, bid))
        if not m:
            continue
        rows_ = []
        for name in ("attack", "armor_pierce"):
            rolls = m["acts"][f"hit.{name}"] + m["acts"][f"miss.{name}"]
            crits, dmg, critdmg = m["acts"][f"crit.{name}"], m["acts"][f"dmg.{name}"], m["acts"][f"critdmg.{name}"]
            hits = m["acts"][f"hit.{name}"]
            normal = (dmg - critdmg) / max(hits - crits, 1)
            rows_.append((name, m["acts"][name], rolls, crits, f"{100 * crits / rolls:.1f}%" if rolls else "-",
                          f"{normal:.1f}", f"{critdmg / crits:.1f}" if crits else "-"))
        out.append(table(["action", "used", "rolls", "crits", "crit rate", "damage of a normal hit", "damage of a crit"], rows_))
    return "\n".join(out)


def shield_section(st, lv):
    body = []
    for bid in rb.BUILD_IDS:
        g = st.gear.get((lv, bid))
        if not g or not rb.lookup(bid).shield:
            continue
        n = sum(v for k, v in g.items() if k.startswith("off:"))
        body.append((bid, n, f"{100 * g['off:' + rb.SHIELD] / n:.0f}%", f"{100 * g['weapon:None'] / n:.0f}%",
                     ", ".join(f"{k[6:]} {100 * v / n:.0f}%" for k, v in g.most_common() if k.startswith("armor:"))[:90]))
    return table(["build", "units", "got the shield", "unarmed", "armour"], body)


def talent_section(st, lv, build):
    """The lift of a random talent: the score of the squads where one of the three held it against those where none did (per
    squad, so the three units of a squad are one observation)."""
    body = []
    for (lvl, b, t, held), acc in st.talent.items():
        if lvl == lv and b == build and held:
            none = st.talent.get((lvl, b, t, False))
            if none and acc.n >= MIN_SQUADS and none.n >= MIN_SQUADS:
                se = math.sqrt(acc.se ** 2 + none.se ** 2)
                body.append((100 * (acc.p - none.p), t, 196 * se, acc.n))
    body.sort(reverse=True)
    return table(["talent (a random pick)", "lift (points)", "95% +-", "squads holding it"],
                 [(t, f"{d:+.1f}", f"{e:.1f}", n) for d, t, e, n in body[:12] + body[-5:]])


def initiative_section(st, lv):
    body = []
    for bid in rb.BUILD_IDS:
        m = st.units.get((lv, bid))
        i = m["init"] if m else None
        if not i or not i["fights"]:
            continue
        yes, no = st.first.get((lv, bid, True)), st.first.get((lv, bid, False))
        body.append((bid, f"{i['rank'] / i['fights']:.2f}", f"{i['bonus'] / m['n']['units']:+.2f}",
                     f"{100 * i['first'] / i['fights']:.0f}%", yes or "-", no or "-",
                     f"{i['shouts'] / i['fights']:.2f}"))
    return table(["build", "mean rank of its squad (0 = first)", "initiative bonus", "squad had the first turn", "score when first",
                  "score when not", "inspiring shouts/squad"], body)


def first_turn_section(st, lv):
    body = []
    for bid in ("crossbow", "archer", "sage_archer", "thrower", "dagger_skirmisher", "sword_board"):
        m = st.units.get((lv, bid))
        if m and m["n"]["units"]:
            n = m["n"]["units"]
            body.append((bid, f"{m['r1']['dmg'] / n:.1f}", f"{m['acts']['reload'] / n:.2f}", f"{m['acts']['dmg.attack'] / n:.1f}"))
    return table(["build", "damage dealt in round 1 (per unit)", "reloads/unit", "damage by attack/unit (whole fight)"], body)


def race_section(st, lv):
    races = sorted({race for (lvl, race, _b) in st.race_build if lvl == lv})
    body = []
    for race in races:
        mine = sorted(((acc, b) for (lvl, r_, b), acc in st.race_build.items() if lvl == lv and r_ == race), key=lambda t: -t[0].p)
        role = defaultdict(list)
        for acc, b in mine:
            role[rb.lookup(b).role].append(acc.p)
        body.append((race, ", ".join(f"{b} {100 * acc.p:.0f}" for acc, b in mine[:3]),
                     *[(f"{100 * sum(role[k]) / len(role[k]):.0f}" if role[k] else "-") for k in ("melee", "ranged", "caster")]))
    return table(["race", "its three best builds (score)", "mean over melee builds", "over ranged", "over casters"], body)


BUILDS_INTRO = """# As builds do estudo, uma a uma

Gerado por `scripts/build_study_report.py` a partir de `scripts/race_study_builds.py`: este texto nunca diverge do que o estudo monta.
Todas valem para qualquer raça que consiga empunhar a arma; atributos 3d6; só os talentos de trabalho depois das raízes e a rolagem variam.

## Como um personagem é montado

- **Nível 5** = nível racial 5; combate, trabalho e magia somam 10 níveis. Corpo a corpo e arqueiros: 5 de combate, 5 de trabalho, 0 de magia.
  Conjuradores: 3 de combate, 4 de trabalho, 3 de magia. Racial: 1 talento sorteado entre os que a raça pode pegar primeiro (a onda `rt` mede cada um). **Nível 0**: nenhum talento.
- Combate, magia e raízes de trabalho seguem a lista da build, na ordem dos pré-requisitos; o que sobra é sorteado entre os legais.
  Um talento da lista que o personagem não consegue pegar vira o aviso `talent X not legal` (o teste `test_race_study_builds` trava isso).
- **Compra, em ordem:** a arma (a versão Large primeiro, se o corpo empunha), a aljava de quem atira, a armadura (a que dá mais CA somando a
  Destreza, a mais barata entre as empatadas), mais aljavas ou reservas de arremesso, o escudo. **Fortress inverte:** armadura, escudo, e a arma
  com o que sobra; se nada sobra, luta **desarmado** (aviso `unarmed`); uma arma de duas mãos devolve o escudo.
- **Luz:** o mapa do CTF é escuro; só os Ermos têm luz. Depois de montar os três, se ninguém leva luz e o esquadrão não é todo de visão no escuro
  (ex.: só anões), um deles leva a Tocha: quem tem a mão livre; se todos usam duas mãos, um troca a arma por uma de uma mão. Arqueiros ficam sem tocha.
- Uma build só entra com uma raça que consiga empunhar a arma dela. No nível 0, conjurador só existe para a raça que já começa com magia (Gnomo, natureza).
- Variantes de talento (Robusto ou Baluarte, os pares do Rapier e do Dagger, Abater/Derrubada x Mão Pesada/Golpe Certeiro) lutam em espelho; Passo
  Livre exige Veloz, então são 2 pares legais em cada.
- Javelin = Shortspear (não existe item Javelin); o arremessador compra reservas até o teto medido em `tests/test_thrown_supply.py`.

## As builds

"""


def builds_doc():
    body = []
    for b in rb.BUILDS.values():
        weapon = b.weapons[0] + (" (primeiro Large)" if b.weapons else "")
        body.append((b.id, b.label, weapon, b.shield or "-", "armadura > escudo > arma" if b.armor_first else "arma > armadura > escudo",
                     ", ".join(b.combat), ", ".join(b.work) + " + sorteio", ", ".join(b.magic_talents) or "-", ", ".join(b.spells5) or "-"))
    text = BUILDS_INTRO + table(["build", "descricao", "arma", "escudo", "compra", "talentos de combate (ordem)", "trabalho", "magia", "magias L5"], body)
    text += "\n## Variantes (espelhos da mesma build)\n\n"
    text += table(["build", "variante", "talentos de combate"], [(b, v, ", ".join(c)) for b, vs in rb.VARIANTS.items() for v, c in vs.items()])
    text += "\n## Varredura de armas\n\n" + table(["build", "armas testadas no nivel 5"], [
        (b, ", ".join(rb.sweep_weapons(b, 5))) for b in (*rb.SWEEP_BUILDS, "thrower")])
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="teste-builds")
    args = ap.parse_args()
    out = os.path.join(ROOT, "sim_results", args.out)
    st, fights = Study(), 0
    for r in rows(out):
        st.add(r)
        fights += 1
    md = [f"# Build study ({fights} fights)\n"]
    if st.errors:
        md.append("**Fights that failed:** " + "; ".join(f"{k} x{v}" for k, v in st.errors.items()) + "\n")
    scores = race_scores(st)
    md.append("\n## Summary, from the smallest piece to the largest (every score is a win rate, draws count half)\n")
    md.append("### Weapons\n\nA plain fighter (no talents, no build) with the weapon against the same fighter with the Sword.\n")
    md.append(weapon_table(st))
    md.append("### Spells\n\nThe full kit of the caster build against the same kit without that one spell; positive means the spell adds.\n")
    md.append(spell_table(st))
    md.append("### Builds\n\nScore: the CTF map (dark) and the Ermos (lit) half each, level 5 only (level 0 has no build).\n")
    md.append(build_scores(st))
    md.append("### Races\n\nScore: the same blend over every build the race fields. Flexibility: the builds above 50% over the builds the race fields.\n")
    md.append(race_table(scores))
    md.append("### Vocations\n\nThe mean of the blended scores of the vocation's six races.\n")
    md.append(vocation_table(scores))
    md.append("### Racial talents\n\nEach first-pick racial talent of a race, level 5, against the same unit with no racial talent "
              "(a random build of the race, same on both sides). 'No impact': inside the 95% interval of zero.\n")
    if st.racial:
        md.append(racial_table(st))
    for lv in sorted({lv for (lv, _b) in st.rank}):
        md.append(f"\n## Level {lv}\n")
        ranked = sorted(((acc, b) for (l, b), acc in st.rank.items() if l == lv), key=lambda t: -t[0].p)
        md.append("### Ranking of the builds (each against a random squad of the field, every race)\n")
        md.append(table(["build", "score"], [(b, acc) for acc, b in ranked]))
        ids = [b for _, b in ranked]
        md.append("### Build x build (row's score; races drawn at random)\n")
        md.append(table(["", *ids], [(a, *[(f"{100 * st.matrix[lv, a, b].p:.0f}" if st.matrix.get((lv, a, b)) else "-") for b in ids]) for a in ids]))
        races = sorted({race for (l, race, _b) in st.race_build if l == lv})
        md.append("### Race x build (score; the races by vocation)\n")
        md.append(table(["race", *ids], [(race, *[(f"{100 * st.race_build[lv, race, b].p:.0f}" if st.race_build.get((lv, race, b)) else "-") for b in ids]) for race in races]))
        md.append("### What the units did (per unit, in the fights of the ranking and the matrix)\n")
        md.append(behaviour_section(st, lv))
        md.append("### Races: the best builds of each and the mean by role (the vocations)\n")
        md.append(race_section(st, lv))
        md.append("### Initiative\n")
        md.append(initiative_section(st, lv))
        md.append("### The first turn (damage dealt in round 1) and reloads\n")
        md.append(first_turn_section(st, lv))
        md.append("### Free Step and the thrown dagger\n")
        md.append(free_step_section(st, lv) + "\n")
        md.append("### Shields (bought after the armour; Fortress buys it before the weapon)\n")
        md.append(shield_section(st, lv))
        if lv:
            md.append("### Variants (mirrors of one build; the score of the variant)\n")
            body = [(b, v, acc) for (l, b, v), acc in sorted(st.variant.items()) if l == lv]
            md.append(table(["build", "variant", "score in its mirrors"], body))
            md.append("### Variant against variant\n")
            md.append(table(["build", "variant", "against", "score"], [(b, va, vb, acc) for (l, b, va, vb), acc in sorted(st.pair.items()) if l == lv]))
            md.append("### Pick and crit (Smart Miner)\n")
            md.append(crit_section(st, lv))
            md.append("### The random talents of the Archer\n")
            md.append(talent_section(st, lv, "archer"))
        md.append("### Weapon sweeps (against the sword and shield with Hardy, same race both sides)\n")
        md.append(sweep_section(st, lv))
    with open(os.path.join(out, "BUILDS.md"), "w", encoding="utf-8") as f:
        f.write(builds_doc())
    path = os.path.join(out, "REPORT.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"{fights} fights -> {path}")


if __name__ == "__main__":
    main()
