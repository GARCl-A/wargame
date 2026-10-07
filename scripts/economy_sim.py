"""Economy tournament: can racial abilities + attributes earn a living?

Combat aside -- this asks the world-first question. A generated character
(race + occupation, fresh 3d6 rolls) spends `--days` in a town with a handful of
vendors, trading every day, and we measure the net copper they end up with.
Aggregate by race / occupation / combo the same way `balance_sim.py` does, over a
random sample.

The market in `economy.py` is a pure sink: `buy = base*(1-deal)`,
`sell = base*(0.5 + 0.4*deal)`, deal <= 0.25, so buy and sell never cross. The
only things that move `deal` at level 0 are **Charisma**, **speaking the vendor's
language**, and **alignment distance** to the vendor; `autotroph` (Leshy) also
skips the daily meal. Three modes let you see that lever from three angles:

  --mode bleed        no income. Just the cost of eating for `--days`. Ranks who
                      loses the least (autotroph = 0, high-CHA polyglots less).
  --mode production   the occupation makes its starting item once a day and sells
                      it; you also have to eat. Net = sale revenue - food cost.
  --mode work         the character works the lumber yard (`economy.lumber_pay`:
                      their own Axe pays more, Piecework adds coin, Brisk Hands and
                      Tireless Worker fit more shifts into the day) and eats.
  --mode arbitrage    vendors get a fixed per-item price multiplier (+/- --spread,
                      NOT a live-game mechanic -- flagged as a sim assumption), so
                      buy-here-sell-there can turn a profit. CHA / languages /
                      alignment widen every window.

    python scripts/economy_sim.py                       # production, 20000 traders
    python scripts/economy_sim.py --mode arbitrage --traders 40000
    python scripts/economy_sim.py --mode bleed
    python scripts/economy_sim.py --mode work --level 5 --racial 5   # talents in play

Writes sim_results/economy-<mode>-*.{txt,json,csv}.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from balance_sim import spend_picks

from gartok import data, economy, talents
from gartok.unit import Unit

RACES = list(data.RACE_NAMES)
OCCUPATIONS = list(data.OCCUPATION_NAMES)
ALIGN_NAMES = [name for _, name in data.ALIGNMENTS]

FOOD = sorted(data.FOOD_ITEMS)                       # {"Meat", "Potato"}

# Goods that can change hands: every occupation's starting item that isn't a
# creature, plus food and a few staples. Everything has a price (real or a
# weight-based fallback via economy._base_price).
TRADE_GOODS = sorted(
    {o["item"] for o in map(data.occupation_by_name, OCCUPATIONS)
     if o["item"] not in data.CREATURE_ITEMS}
    | set(FOOD) | {"Torch", "Rope"}
)

# What each occupation produces per day in --mode production (its table item).
PRODUCE = {o["name"]: o["item"] for o in map(data.occupation_by_name, OCCUPATIONS)
           if o["item"] not in data.CREATURE_ITEMS}


# --------------------------------------------------------------------------- #
# pricing: reuse economy.py's haggle math, vary only the base per vendor      #
#                                                                             #
# A trader's `deal` with a given vendor is fixed for the whole visit (their   #
# Charisma / languages / alignment and the vendor's language / alignment      #
# don't change, and the trader never goes hungry here), so each vendor bakes  #
# a full buy/sell price table for the trader once, up front.                  #
# --------------------------------------------------------------------------- #
class Vendor:
    def __init__(self, rng, *, arbitrage, spread, stock_cap):
        self.language = rng.choice(data.LANGUAGES)
        self.alignment = rng.choice(ALIGN_NAMES)
        self.mult = {g: (rng.uniform(1 - spread, 1 + spread) if arbitrage else 1.0)
                     for g in TRADE_GOODS}
        self.cap = {g: rng.choice([0, 0, stock_cap // 2, stock_cap, stock_cap])
                    for g in TRADE_GOODS}
        for f in FOOD:                       # guarantee food is buyable somewhere
            if rng.random() < 0.6:
                self.cap[f] = stock_cap
        self.stock = dict(self.cap)
        self.buy = {}                        # filled by price_for(trader)
        self.sell = {}

    def replenish(self, frac):
        for g, c in self.cap.items():
            if c:
                self.stock[g] = min(c, self.stock[g] + max(1, math.ceil(c * frac)))

    def price_for(self, trader):
        """Bake this trader's buy/sell tables from the live `economy.buy_price` /
        `sell_price` (CHA + shared language + alignment distance + talent mods,
        item-scoped ones included), scaled by this vendor's per-item multiplier."""
        mods = economy.deal_mods([trader], self.language, self.alignment)
        self.deal = economy.deal_value(mods, None, "buy")
        for g in TRADE_GOODS:
            self.buy[g] = max(1, round(economy.buy_price(g, mods) * self.mult[g]))
            self.sell[g] = max(1, round(economy.sell_price(g, mods) * self.mult[g]))


# --------------------------------------------------------------------------- #
# one trader, one town, `days` days                                           #
# --------------------------------------------------------------------------- #
def _eat(trader, vendors, produced):
    """Resolve the day's meal. Returns copper spent (0 if free)."""
    if trader.ability.id == "autotroph":
        return 0
    for f in FOOD:                                  # a butcher/farmer eats their own produce
        if produced.get(f, 0) > 0:
            produced[f] -= 1
            return 0
    best = None
    for v in vendors:
        for f in FOOD:
            if v.stock.get(f, 0) > 0 and (best is None or v.buy[f] < best[2]):
                best = (v, f, v.buy[f])
    if best is None:
        return 0                                    # nothing to buy; goes hungry (unmodelled)
    v, f, p = best
    if trader.money >= p:
        trader.money -= p
        v.stock[f] -= 1
        return p
    return 0


def run_trader(combo, seed, cfg):
    race, occ = combo
    rng = random.Random(seed)
    random.seed(seed)
    t = Unit("trader")
    t.set_race(race)
    t.set_occupation(occ)
    combat, work, racial = cfg["levels"]
    if combat:
        t.set_track_level("combat", combat)
    if work:
        t.set_track_level("work", work)
    if racial is not None:
        t.set_track_level("racial", racial)
    spend_picks(t)
    t.money = cfg["start_gold"] or t.money           # 0 => keep the rolled 5d10
    start = t.money

    vendors = [Vendor(rng, arbitrage=cfg["mode"] == "arbitrage",
                      spread=cfg["spread"], stock_cap=cfg["stock_cap"])
               for _ in range(cfg["vendors"])]
    for v in vendors:
        v.price_for(t)

    food_spent = revenue = arb_profit = 0
    wage_per_day = 0
    if cfg["mode"] == "work":
        # Brisk Hands & co. shave clock time off a shift, so more nominal hours fit
        # in the day's work budget; pay is by whole 4 h blocks of nominal hours.
        speed = min(0.9, t.talent_bonus("activity_speed"))
        hours = int(cfg["work_budget"] / (1 - speed))
        pay = economy.lumber_pay(hours, economy.lumber_level(t))
        wage_per_day = round(pay * (1 + t.talent_bonus("coin_gain")))
    for _ in range(cfg["days"]):
        produced = defaultdict(int)

        if wage_per_day:
            t.money += wage_per_day
            revenue += wage_per_day

        if cfg["mode"] == "production" and occ in PRODUCE:
            produced[PRODUCE[occ]] += cfg["produce_qty"]

        if cfg["mode"] == "arbitrage":
            for _ in range(cfg["trades_per_day"]):
                best = None                        # (margin, lo, hi, item, buy_price)
                for item in TRADE_GOODS:
                    lo = min((v for v in vendors if v.stock[item] > 0),
                             key=lambda v: v.buy[item], default=None)
                    if lo is None:
                        continue
                    hi = max(vendors, key=lambda v: v.sell[item])
                    if hi.sell[item] > lo.buy[item] and (
                            best is None or hi.sell[item] - lo.buy[item] > best[0]):
                        best = (hi.sell[item] - lo.buy[item], lo, hi, item, lo.buy[item])
                if best is None:
                    break
                margin, lo, hi, item, bp = best
                qty = min(lo.stock[item], t.money // bp, cfg["max_lot"])
                if qty <= 0:
                    break
                lo.stock[item] -= qty
                t.money += qty * (hi.sell[item] - bp)
                arb_profit += qty * margin

        # sell the day's production to the best-paying vendor
        for item, qty in list(produced.items()):
            if qty <= 0 or item in FOOD:
                continue
            got = qty * max(v.sell[item] for v in vendors)
            t.money += got
            revenue += got
            produced[item] = 0

        food_spent += _eat(t, vendors, produced)
        for v in vendors:
            v.replenish(cfg["replenish"])

    return {
        "delta": t.money - start,
        "start": start,
        "cha_mod": data.mod(t.charisma),
        "langs": len(t.languages),
        "autotroph": t.ability.id == "autotroph",
        "food_spent": food_spent,
        "revenue": revenue,
        "arb_profit": arb_profit,
        "talents": tuple(x for tr in talents.TRACKS for x in t.talents[tr]),
    }


# --------------------------------------------------------------------------- #
# aggregation + report                                                        #
# --------------------------------------------------------------------------- #
class Acc:
    __slots__ = ("auto", "cha", "deltas", "food", "free", "langs", "rev")

    def __init__(self):
        self.deltas, self.cha, self.langs, self.food, self.rev = [], [], [], [], []
        self.auto = self.free = 0

    def add(self, r):
        self.deltas.append(r["delta"])
        self.cha.append(r["cha_mod"])
        self.langs.append(r["langs"])
        self.auto += r["autotroph"]
        self.free += r["food_spent"] == 0
        self.food.append(r["food_spent"])
        self.rev.append(r["revenue"] + r["arb_profit"])

    @property
    def n(self):
        return len(self.deltas)

    @property
    def mean(self):
        return statistics.mean(self.deltas) if self.deltas else 0.0

    @property
    def median(self):
        return statistics.median(self.deltas) if self.deltas else 0.0

    @property
    def se(self):
        return (statistics.pstdev(self.deltas) / math.sqrt(self.n)) if self.n > 1 else 0.0


def _table(lines, title, accs, keys, days, note=""):
    p = lines.append
    p("")
    p("-" * 82)
    p(title + (f"   {note}" if note else ""))
    p("-" * 82)
    p(f"{'':4}{'name':<16}{'net/15d':>9}{'net/day':>9}{'median':>9}{'+/-SE':>8}"
      f"{'chaMod':>8}{'langs':>7}{'gross':>8}{'food$':>7}{'free':>6}{'games':>8}")
    ranked = sorted(keys, key=lambda k: accs[k].mean, reverse=True)
    for i, k in enumerate(ranked, 1):
        a = accs[k]
        label = k if isinstance(k, str) else f"{k[0]} {k[1]}"
        p(f"{i:<4}{label:<16}{a.mean:>9.0f}{a.mean/days:>9.1f}{a.median:>9.0f}"
          f"{a.se:>8.1f}{statistics.mean(a.cha):>8.1f}{statistics.mean(a.langs):>7.1f}"
          f"{statistics.mean(a.rev):>8.0f}{statistics.mean(a.food):>7.0f}"
          f"{a.free/a.n:>5.0%} {a.n:>7}")


def talent_effects(rows, race_acc, occ_acc):
    """Per talent: mean net copper of its holders minus what their race + occupation
    alone predict (in copper over the run). `rows` = [(race, occ, result)]."""
    overall = statistics.mean(x for a in race_acc.values() for x in a.deltas)
    samples = defaultdict(list)
    for race, occ, r in rows:
        expected = race_acc[race].mean + occ_acc[occ].mean - overall
        for tid in r["talents"]:
            if talents.get(tid).track != "racial":     # a race's mean already contains its node
                samples[tid].append(r["delta"] - expected)
    return {tid: {"n": len(xs), "holders": len(xs) / len(rows), "delta": statistics.mean(xs),
                  "se": statistics.pstdev(xs) / math.sqrt(len(xs)) if len(xs) > 1 else 0.0}
            for tid, xs in samples.items()}


def build_report(race_acc, occ_acc, combo_acc, cfg, tal_fx=None):
    L = []
    p = L.append
    d = cfg["days"]
    p("=" * 82)
    p(f"GARTOK ECONOMY TOURNAMENT  --  mode: {cfg['mode']}")
    p("=" * 82)
    p(f"generated : {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    p(f"traders   : {cfg['traders']}   days each: {d}   vendors: {cfg['vendors']}")
    p(f"start gold: {'rolled 5d10' if not cfg['start_gold'] else cfg['start_gold']}"
      f"   stock cap: {cfg['stock_cap']}  replenish: {cfg['replenish']:.0%}/day")
    if cfg["mode"] == "arbitrage":
        p(f"price spread: +/-{cfg['spread']:.0%} per vendor per item "
          f"(SIM ASSUMPTION -- not in the live game)   trades/day cap: {cfg['trades_per_day']}")
    if cfg["mode"] == "work":
        p(f"work       : {cfg['work_budget']} clock-hours/day at the lumber yard (live `economy.lumber_pay`)")
    c, w, rac = cfg["levels"]
    if c or w or rac:
        p(f"levels     : combat L{c}, work L{w}, racial "
          f"{'derived' if rac is None else f'pinned {rac}'}, random talent picks")
    if cfg["mode"] == "production":
        p("production : 1x the occupation's table item per day, sold to the best vendor")
    all_d = [x for a in race_acc.values() for x in a.deltas]
    p(f"overall   : net/15d mean {statistics.mean(all_d):.0f}  median "
      f"{statistics.median(all_d):.0f}  (min {min(all_d)}  max {max(all_d)})")
    p("")
    p("net/15d = copper at day 15 minus starting copper. Positive = came out ahead.")
    p("free-eat = share of traders that never paid for food (autotroph, or a")
    p("butcher/farmer eating their own stock).")

    _table(L, "RACES  (occupation randomised out)", race_acc, RACES, d)
    _table(L, "OCCUPATIONS  (race randomised out)", occ_acc, OCCUPATIONS, d)

    solid = [c for c in combo_acc if combo_acc[c].n >= cfg["min_combo"]]
    by = sorted(solid, key=lambda c: combo_acc[c].mean, reverse=True)
    p("")
    p("-" * 82)
    p(f"COMBO EXTREMES  (>= {cfg['min_combo']} traders each; {len(solid)}/{len(combo_acc)} qualify)")
    p("-" * 82)
    p("RICHEST 15:")
    for c in by[:15]:
        a = combo_acc[c]
        p(f"  {c[0]+' '+c[1]:<26}{a.mean:>8.0f}/15d   {a.mean/d:>6.1f}/day   n={a.n}")
    p("")
    p("POOREST 15:")
    for c in by[-15:][::-1]:
        a = combo_acc[c]
        p(f"  {c[0]+' '+c[1]:<26}{a.mean:>8.0f}/15d   {a.mean/d:>6.1f}/day   n={a.n}")
    if tal_fx:
        p("")
        p("-" * 82)
        p("TALENTS  (holder net copper minus race+occupation prediction, over the run)")
        p("combat/work only: a racial node's effect shows in its race's row above")
        p("-" * 82)
        for track in talents.XP_TRACKS:
            rows = [(tid, fx) for tid, fx in tal_fx.items() if talents.get(tid).track == track]
            if not rows:
                continue
            p(f"{track.upper()}:")
            p(f"  {'talent':<24}{'race':<12}{'holders':>8}{'delta cp':>10}{'+/-SE':>8}")
            for tid, fx in sorted(rows, key=lambda r: r[1]["delta"], reverse=True):
                t = talents.get(tid)
                p(f"  {t.name:<24}{(t.race or ''):<12}{fx['holders']:>8.1%}"
                  f"{fx['delta']:>+10.1f}{fx['se']:>8.1f}")
    p("")
    p("=" * 82)
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# driver                                                                      #
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=("production", "arbitrage", "bleed", "work"),
                    default="production")
    ap.add_argument("--traders", type=int, default=20000)
    ap.add_argument("--days", type=int, default=15)
    ap.add_argument("--vendors", type=int, default=4)
    ap.add_argument("--start-gold", type=int, default=0, help="0 = roll 5d10 like the game")
    ap.add_argument("--spread", type=float, default=0.15, help="arbitrage: +/- per-vendor price")
    ap.add_argument("--stock-cap", type=int, default=20)
    ap.add_argument("--replenish", type=float, default=0.5, help="fraction of cap restocked per day")
    ap.add_argument("--trades-per-day", type=int, default=20)
    ap.add_argument("--max-lot", type=int, default=10)
    ap.add_argument("--produce-qty", type=int, default=1)
    ap.add_argument("--work-budget", type=int, default=8,
                    help="work mode: clock hours of lumber-yard work per day")
    ap.add_argument("--level", type=int, default=0,
                    help="combat AND work level for every trader (talents picked at random)")
    ap.add_argument("--racial", type=int, default=None,
                    help="pin the racial level (a racial pick unlocks at 5)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", default="sim_results")
    args = ap.parse_args()

    cfg = {
        "mode": args.mode, "traders": args.traders, "days": args.days,
        "vendors": args.vendors, "start_gold": args.start_gold, "spread": args.spread,
        "stock_cap": args.stock_cap, "replenish": args.replenish,
        "trades_per_day": args.trades_per_day, "max_lot": args.max_lot,
        "produce_qty": args.produce_qty, "work_budget": args.work_budget,
        "levels": (args.level, args.level, args.racial),
        "min_combo": max(20, round(args.traders / len(RACES) / len(OCCUPATIONS) * 0.5)),
    }

    rng = random.Random(args.seed)
    race_acc = defaultdict(Acc)
    occ_acc = defaultdict(Acc)
    combo_acc = defaultdict(Acc)
    rows = []

    for i in range(args.traders):
        combo = (rng.choice(RACES), rng.choice(OCCUPATIONS))
        r = run_trader(combo, rng.randrange(2**31), cfg)
        race_acc[combo[0]].add(r)
        occ_acc[combo[1]].add(r)
        combo_acc[combo].add(r)
        rows.append((combo[0], combo[1], r))
        if (i + 1) % 5000 == 0:
            print(f"  {i+1}/{args.traders}", flush=True)

    leveled = bool(args.level or args.racial)
    tal_fx = talent_effects(rows, race_acc, occ_acc) if leveled else None
    report = build_report(race_acc, occ_acc, combo_acc, cfg, tal_fx)
    print("\n" + report)

    os.makedirs(args.out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    lvl = f"-L{args.level}" + ("" if args.racial is None else f"r{args.racial}") if leveled else ""
    tag = f"{args.mode}{lvl}-{args.traders}-{stamp}"
    with open(os.path.join(args.out_dir, f"economy-{tag}.txt"), "w", encoding="utf-8") as f:
        f.write(report + "\n")

    def dump(name, accs, keys):
        with open(os.path.join(args.out_dir, f"economy-{tag}-{name}.csv"),
                  "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["key", "n", "mean_net", "net_per_day", "median_net", "se",
                        "cha_mod", "langs", "free_eat_frac"])
            for k in sorted(keys, key=lambda k: accs[k].mean, reverse=True):
                a = accs[k]
                label = k if isinstance(k, str) else f"{k[0]}|{k[1]}"
                w.writerow([label, a.n, f"{a.mean:.1f}", f"{a.mean/args.days:.2f}",
                            f"{a.median:.1f}", f"{a.se:.2f}",
                            f"{statistics.mean(a.cha):.2f}",
                            f"{statistics.mean(a.langs):.2f}", f"{a.auto/a.n:.3f}"])

    dump("race", race_acc, RACES)
    dump("occ", occ_acc, OCCUPATIONS)
    dump("combo", combo_acc, list(combo_acc))
    with open(os.path.join(args.out_dir, f"economy-{tag}.json"), "w", encoding="utf-8") as f:
        json.dump({"config": cfg,
                   "race": {k: {"n": a.n, "mean": a.mean, "median": a.median}
                            for k, a in race_acc.items()},
                   "occ": {k: {"n": a.n, "mean": a.mean, "median": a.median}
                           for k, a in occ_acc.items()}}, f, indent=2)
    print(f"\nreport -> {args.out_dir}/economy-{tag}.txt")


if __name__ == "__main__":
    main()
