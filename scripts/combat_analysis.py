"""Read combat logs (`gartok/combat_log.py`) back: who decided what, and where a person parts from the AI.

For every log: the fight, who played each side, the result, and the decisions by controller. For
the person's decisions it prints how often they matched what `ai.py` would have done from the same
state (same action, then same action and target) and the pairs they differed on most. `--show`
replays one fight from the file alone, a line per decision.

    python scripts/combat_analysis.py combat_lab                 # every log under a folder
    python scripts/combat_analysis.py saves/<world>/combat_logs
    python scripts/combat_analysis.py combat_lab/2026-10-10/scrapper-human-vs-ai.jsonl --show
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gartok import combat_log


def find_logs(paths):
    found = []
    for path in paths:
        if os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                found += [os.path.join(root, f) for f in sorted(files) if f.endswith(".jsonl")]
        elif path.endswith(".jsonl"):
            found.append(path)
    return found


def decisions(rows):
    return [r for r in rows if r["e"] == "act"]


def agreement(rows):
    """Over the person's decisions that carry the AI's pick: how often the action matched, and the
    action together with its target. Also the (person, AI) pairs that differed, counted."""
    both = [r for r in decisions(rows) if r["by"] == "human" and r.get("ai")]
    same_action = sum(r["action"] == r["ai"]["action"] for r in both)
    same_all = sum(r["action"] == r["ai"]["action"] and r["target"] == r["ai"]["target"] for r in both)
    split = Counter((r["action"], r["ai"]["action"]) for r in both if r["action"] != r["ai"]["action"])
    return len(both), same_action, same_all, split


def summary(path):
    rows = combat_log.load(path)
    start = rows[0]
    end = next((r for r in rows if r["e"] == "end"), None)
    acts = decisions(rows)
    lines = [f"== {path}",
             f"   {start['meta'].get('fight') or start['meta'].get('kind')}, "
             f"player: {start['controllers']['player']}, enemy: {start['controllers']['enemy']}, "
             f"{len(acts)} decisions, " + (f"won by {end['winner']} in {end['rounds']} rounds"
                                           if end and end["winner"] else "left unfinished")]
    for by in ("human", "ai"):
        mine = Counter(r["action"] for r in acts if r["by"] == by)
        if mine:
            lines.append(f"   {by:<5} " + ", ".join(f"{a} {n}" for a, n in mine.most_common()))
    total, same_action, same_all, split = agreement(rows)
    if total:
        lines.append(f"   the person's {total} decisions: the AI's action {same_action / total:.0%}, "
                     f"its action and target {same_all / total:.0%}")
        for (human, ai_pick), n in split.most_common(5):
            lines.append(f"      chose {human}, the AI would {ai_pick}: {n}")
    return lines


def show(path):
    frames = combat_log.frames(combat_log.load(path))
    out = []
    for f in frames[1:]:
        row = f["row"]
        who = f["units"][row["actor"]]["name"]
        target = row["target"]
        if target and "unit" in target:
            target = f["units"][target["unit"]]["name"]
        hp = " ".join(f"{u['name'].split()[0]}:{u['hp']}" for u in f["units"] if u["status"] != "dead")
        out.append(f"r{row['round']:>2} #{row['n']:<3} {row['by']:<5} {who} {row['action']}"
                   f"{' -> ' + str(target) if target else ''}   [{hp}]")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="log files or folders")
    ap.add_argument("--show", action="store_true", help="replay each fight, a line per decision")
    args = ap.parse_args()
    logs = find_logs(args.paths)
    if not logs:
        sys.exit("no .jsonl combat logs found")
    for path in logs:
        print("\n".join(show(path) if args.show else summary(path)))


if __name__ == "__main__":
    main()
