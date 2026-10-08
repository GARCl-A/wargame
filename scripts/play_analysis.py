"""Read the play recorder's logs (gartok/recorder.py) and turn them into what the economy sim needs.

  1. the day-by-day table the sim prints (money per member, levels, what the guild did)
  2. the decision thresholds a person plays by: the cash held when the Axe was bought, the
     days of food they shop at and up to, the HP and level before a bout or a hunt, the
     day they left the yard
  3. with --out, a profile JSON that `economy_guild.py --profile` feeds the `human` policy

Pass one log per run; with several, each threshold is the median of the runs'.

    python scripts/play_analysis.py saves/<world>/play.jsonl [more.jsonl ...]
    python scripts/play_analysis.py a.jsonl b.jsonl c.jsonl --out sim_results/human_profile.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(SCRIPTS))

from gartok import items, orders
from gartok.clock import SECONDS_PER_DAY

CURVE_DAYS = (1, 3, 7, 14, 21, 30)
ADVENTURE_ORDERS = frozenset({"arena", "hunt"})
FOOD_TRIP_GAP = 2 * 3600          # food bought within this many seconds is one shopping trip


def day_of(t):
    return t // SECONDS_PER_DAY + 1


def load(path):
    """The rows of one run in order. Loading an earlier save rewinds the clock; the rows the
    player then replayed over are dropped, so the log is the one timeline that survived."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("e") == "session":
                rows = [r for r in rows if r["t"] < row["t"]]
            rows.append(row)
    return rows


def day_table(rows):
    """One entry per recorded day: money per member, mean levels, rations, and the activity
    that took most of the day's order hours ('-' when no order was given)."""
    hours = {}
    for r in rows:
        if r["e"] == "order":
            per_kind = hours.setdefault(day_of(r["t"]), {})
            per_kind[r["kind"]] = per_kind.get(r["kind"], 0) + max(r["hours"], 0.01)
    table = []
    for r in rows:
        if r["e"] != "day":
            continue
        members = r["roster"]
        if not members:
            continue
        spent = hours.get(r["day"] - 1) or hours.get(r["day"]) or {}
        table.append({
            "day": r["day"],
            "alive": len(members),
            "money_pm": sum(m["money"] for m in members) / len(members),
            "combat": statistics.mean(m["combat"] for m in members),
            "work": statistics.mean(m["work"] for m in members),
            "rations": r["rations"],
            "activity": max(spent, key=spent.get) if spent else "-",
        })
    return table


def table_report(table, label):
    by_day = {t["day"]: t for t in table}
    pick = [d for d in CURVE_DAYS if d in by_day] or sorted(by_day)[:6]
    lines = [f"== {label}: copper per member, by day",
             f"{'':<10}" + "".join(f"{f'd{d}':>8}" for d in pick)]
    for name, key, fmt in (("money", "money_pm", "{:>8.0f}"), ("combat", "combat", "{:>8.1f}"),
                           ("work", "work", "{:>8.1f}"), ("alive", "alive", "{:>8d}")):
        lines.append(f"{name:<10}" + "".join(fmt.format(by_day[d][key]) for d in pick))
    lines.append(f"{'doing':<10}" + "".join(f"{by_day[d]['activity']:>8}" for d in pick))
    return "\n".join(lines)


def _median(values):
    return round(statistics.median(values), 2) if values else None


def _is_food(item):
    try:
        return items.is_food(item)
    except KeyError:
        return False


def food_trips(rows):
    """[(days of food before, days after)] for each shopping trip: food bought in one go."""
    trips, current = [], None
    for r in rows:
        if r["e"] != "buy" or not _is_food(r["item"]):
            continue
        before = r["food_days"] - r["qty"] / max(1, r["members"])
        if current is not None and r["t"] - current["t"] <= FOOD_TRIP_GAP:
            current["after"], current["t"] = r["food_days"], r["t"]
        else:
            if current is not None:
                trips.append((current["before"], current["after"]))
            current = {"before": before, "after": r["food_days"], "t": r["t"]}
    if current is not None:
        trips.append((current["before"], current["after"]))
    return trips


def first_axe(rows):
    """Cash per member and days of food in hand when the first Axe was bought (the price
    comes back: `money` is read after the purchase)."""
    for r in rows:
        if r["e"] == "buy" and r["item"] == "Axe":
            return (r["money"] + r["price"] * r["qty"]) / max(1, r["members"]), r["food_days"]
    return None


def fights(rows):
    forced = orders.FORCED_KINDS
    bouts = [r for r in rows if r["e"] == "fight" and r["kind"] not in forced and r["kind"] != "hunt"]
    hunts = [r for r in rows if r["e"] == "fight" and r["kind"] == "hunt"]
    return bouts, hunts


def leave_day(rows):
    """The first day the guild did anything but the yard and the walk: an arena or hunt order,
    or a fight."""
    days = [day_of(r["t"]) for r in rows
            if (r["e"] == "order" and r["kind"] in ADVENTURE_ORDERS) or r["e"] == "fight"]
    return min(days) if days else None


def thresholds(rows):
    """What one run says about how this person decides. A key is missing when the run never
    did the thing (no Axe bought, no hunt): the sim then falls back to its own default."""
    out = {}
    axe = first_axe(rows)
    if axe:
        out["axe_cash_per_member"], out["axe_food_days"] = round(axe[0], 2), round(axe[1], 2)
    trips = food_trips(rows)
    if trips:
        out["food_low_days"] = _median([b for b, _ in trips])
        out["food_target_days"] = _median([a for _, a in trips])
    bouts, hunts = fights(rows)
    if bouts:
        out["bout_min_hp"] = min((r["hp_frac"] for r in bouts if "hp_frac" in r), default=None)
        out["bout_cash_per_member"] = _median([r["money_before"] / max(1, r["members_before"])
                                               for r in bouts if "money_before" in r])
        out["bout_win_rate"] = round(sum(r["won"] for r in bouts) / len(bouts), 2)
    if hunts:
        out["hunt_min_hp"] = min((r["hp_frac"] for r in hunts if "hp_frac" in r), default=None)
        out["hunt_min_level"] = min((r["level_before"] for r in hunts if "level_before" in r), default=None)
        out["hunt_win_rate"] = round(sum(r["won"] for r in hunts) / len(hunts), 2)
    day = leave_day(rows)
    if day is not None:
        out["yard_leave_day"] = day
    return {k: v for k, v in out.items() if v is not None}


def profile(runs):
    """The median of every threshold across `runs` (a threshold seen in some runs only
    counts those)."""
    per_run = [thresholds(r) for r in runs]
    keys = sorted({k for p in per_run for k in p})
    merged = {k: _median([p[k] for p in per_run if k in p]) for k in keys}
    merged["runs"] = len(runs)
    return merged


def report(profile_):
    lines = ["== thresholds (median over the runs)"]
    lines += [f"  {k:<22}{v}" for k, v in profile_.items()]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logs", nargs="+", help="play.jsonl files, one per run")
    ap.add_argument("--out", default=None, help="write the profile JSON the human policy reads")
    args = ap.parse_args()
    runs = [load(p) for p in args.logs]
    for path, rows in zip(args.logs, runs):
        print(table_report(day_table(rows), os.path.basename(os.path.dirname(os.path.abspath(path)))))
        print()
    prof = profile(runs)
    print(report(prof))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(prof, f, indent=2)
        print(f"\nprofile written to {args.out}")


if __name__ == "__main__":
    main()
