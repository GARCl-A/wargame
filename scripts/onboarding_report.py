"""How a guild's first weeks went, read off the play recorder's logs (gartok/recorder.py).

Docs: docs/plans/onboarding.md. One row per run: the day of the first job taken, the first fight, the
first combat level and the first recruit, and the share of the first two weeks' member-hours spent on
wage shifts. The plan's exit test is read from this table.

    python scripts/onboarding_report.py recordings saves
    python scripts/onboarding_report.py saves/<world>/play.jsonl
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)

import play_analysis as pa

WINDOW_DAYS = 14          # the stretch whose hours are split by kind of order
COLUMNS = ("days", "job", "fight", "combat 1", "recruit", "work %")


def logs(paths):
    """Every recorder log under `paths` (a file, or a folder walked for `play.jsonl` and loose `*.jsonl` runs)."""
    found = []
    for path in paths:
        if os.path.isfile(path):
            found.append(path)
            continue
        for folder, _, files in os.walk(path):
            if os.path.basename(folder) == "combat_logs":
                continue
            found += [os.path.join(folder, f) for f in sorted(files) if f.endswith(".jsonl") and f != "errors.jsonl"]
    return found


def _first(rows, wanted):
    return next((pa.day_of(r["t"]) for r in rows if wanted(r)), None)


def onboarding(rows):
    """The first-weeks figures of one run; a milestone the run never reached is None."""
    hours = {}
    for r in rows:
        if r["e"] == "order" and pa.day_of(r["t"]) <= WINDOW_DAYS:
            hours[r["kind"]] = hours.get(r["kind"], 0) + r.get("hours", 0) * r.get("size", 1)
    total = sum(hours.values())
    return {
        "days": max(pa.day_of(r["t"]) for r in rows),
        "job": _first(rows, lambda r: r["e"] == "mission" and r.get("what") == "accept"),
        "fight": _first(rows, lambda r: r["e"] == "fight"),
        "combat 1": _first(rows, lambda r: r["e"] == "day" and any(u["combat"] >= 1 for u in r["roster"])),
        "recruit": _first(rows, lambda r: r["e"] == "recruit" and r.get("ok")),
        "work %": round(100 * hours.get("work", 0) / total) if total else None,
    }


def _name(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    return os.path.basename(os.path.dirname(path)) if stem == "play" else stem


def report(paths):
    """The table: one row per run, the longest log of a run that was recorded twice. A log that opens past
    day 1 has no start to read and is left out; a run shorter than the window is marked and kept out of the median."""
    runs = {}
    for path in logs(paths):
        rows = [r for r in pa.load(path) if "t" in r]
        if rows and pa.day_of(rows[0]["t"]) == 1 and len(rows) > len(runs.get(_name(path), ())):
            runs[_name(path)] = rows
    table = [(name, onboarding(rows)) for name, rows in runs.items()]
    lines = [f"{'run':30}" + "".join(f"{c:>10}" for c in COLUMNS)]
    for name, row in table:
        mark = "" if row["days"] >= WINDOW_DAYS else " *"
        lines.append(f"{name[:28] + mark:30}" + "".join(f"{'-' if row[c] is None else row[c]:>10}" for c in COLUMNS))
    full = [row for _, row in table if row["days"] >= WINDOW_DAYS]
    if full:
        medians = [[row[c] for row in full if row[c] is not None] for c in COLUMNS]
        lines.append(f"{'median':30}" + "".join(f"{round(statistics.median(v)) if v else '-':>10}" for v in medians))
        lines.append(f"* shorter than {WINDOW_DAYS} days: not in the median, which counts only the runs that reached each milestone")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("paths", nargs="+", help="recorder logs, or folders to walk for them")
    print(report(p.parse_args().paths))


if __name__ == "__main__":
    main()
