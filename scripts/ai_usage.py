"""What does the combat AI actually do -- and what is each action worth to it?

Two reports over headless AI-vs-AI battles (same setup knobs as balance_sim.py):

  usage     which actions the AI executes, and how often an action it COULD take
            (button enabled at the start of the unit's turn) is taken at all. An action
            with plenty of opportunities and ~0 executions is one the AI ignores.
  ablation  `--ablate id,id,...`: for each action, the player side loses it (its
            `available`/`can` return False) while the enemy keeps it, over mirror
            fights (same race + occupation both sides). Score < 0.5 means the AI was
            using it profitably; ~0.5 means losing it costs nothing, so either the
            action is dead weight for the AI or the AI never reached for it. The
            `blocked` column counts execute calls the AI made on the banned action
            anyway (Reload does, without asking `can`); those are dropped, so the AI
            wastes the turn on them -- read such a row as "the AI is stuck", not as
            the action's value.

    python scripts/ai_usage.py                              # usage, 4000 battles
    python scripts/ai_usage.py --level 5 --gear random      # leveled, kitted out
    python scripts/ai_usage.py --ablate defend,reload,flee --battles 6000

Writes sim_results/ai-usage-*.txt.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from balance_sim import OCCUPATIONS, RACES, Build, _scenario, _squad

from gartok import actions, ai
from gartok.battle import Battle

GUARD = 600


def _all_action_classes():
    return [c for c in vars(actions).values()
            if isinstance(c, type) and issubclass(c, actions.Action) and c is not actions.Action]


class _Probe:
    """Counts executions / opportunities and (optionally) bans actions for one team."""

    def __init__(self, ban_ids, banned_team="player"):
        self.executed = Counter()          # (team, action name) -> times executed
        self.opportunity = Counter()       # (team, action name) -> unit-turns it was enabled
        self.unit_turns = Counter()        # team -> unit-turns
        self.ban_ids = set(ban_ids)
        self.banned_team = banned_team
        self.blocked = Counter()           # banned action the AI tried to execute anyway
        self._patched = []

    def install(self):
        probe = self
        for cls in _all_action_classes():
            if "execute" in vars(cls):
                self._wrap(cls, "execute", lambda orig: probe._execute(orig))
            for meth in ("available", "can"):
                if meth in vars(cls):
                    self._wrap(cls, meth, lambda orig: probe._gate(orig))
        self._wrap(Battle, "move_unit", lambda orig: probe._move(orig))
        orig_turn = ai.take_turn
        self._patched.append((ai, "take_turn", orig_turn))
        ai.take_turn = lambda battle, unit: probe._turn(orig_turn, battle, unit)

    def _wrap(self, owner, attr, make):
        orig = vars(owner)[attr] if attr in vars(owner) else getattr(owner, attr)
        self._patched.append((owner, attr, orig))
        setattr(owner, attr, make(orig))

    def uninstall(self):
        for owner, attr, orig in reversed(self._patched):
            setattr(owner, attr, orig)
        self._patched.clear()

    def _banned(self, action, actor):
        return action.id in self.ban_ids and actor.team == self.banned_team

    def _gate(self, orig):
        probe = self

        def wrapper(action, battle, actor, *a, **kw):
            if probe._banned(action, actor):
                return False
            return orig(action, battle, actor, *a, **kw)
        return wrapper

    def _execute(self, orig):
        probe = self

        def wrapper(action, battle, actor, *a, **kw):
            key = (actor.team, action.name or action.id)
            if probe._banned(action, actor):       # the AI called execute without asking `can`
                probe.blocked[key] += 1
                return None
            probe.executed[key] += 1
            return orig(action, battle, actor, *a, **kw)
        return wrapper

    def _move(self, orig):
        probe = self

        def wrapper(battle, unit, dest, *a, **kw):
            probe.executed[(unit.team, "Walk")] += 1
            return orig(battle, unit, dest, *a, **kw)
        return wrapper

    @staticmethod
    def _enabled(act, battle, unit):
        """Usable right now: an action that needs a target also needs one in reach."""
        if not act.available(battle, unit):
            return False
        if act.target == "enemy":
            return any(act.can(battle, unit, e) for e in battle.units
                       if e.alive and e.team != unit.team)
        if act.target == "cell":
            return any(act.can(battle, unit, c) for c in act.highlight_cells(battle, unit))
        return True

    def _turn(self, orig_turn, battle, unit):
        if unit.alive and not getattr(unit, "dormant", False):
            self.unit_turns[unit.team] += 1
            for act in actions.PANEL_ACTIONS:
                try:
                    if self._enabled(act, battle, unit):
                        self.opportunity[(unit.team, act.name or act.id)] += 1
                except Exception:       # noqa: BLE001, S112 -- a probe must never change the fight
                    continue
        return orig_turn(battle, unit)


def _fight(job):
    combo_a, combo_b, seed, size, scenario_name, daylight, build, ban_ids = job
    probe = _Probe(ban_ids)
    probe.install()
    try:
        random.seed(seed)
        a = _squad(combo_a, "player", size, build)
        b = _squad(combo_b, "enemy", size, build)
        battle = Battle(a, b, scenario=_scenario(scenario_name), daylight=daylight)
        guard = 0
        while battle.winner is None and guard < GUARD:
            guard += 1
            ai.take_turn(battle, battle.active)
    finally:
        probe.uninstall()
    score = {"player": 1.0, "enemy": 0.0}.get(battle.winner, 0.5)
    return score, probe.executed, probe.opportunity, probe.unit_turns, probe.blocked


def _jobs(n, args, build, ban_ids, mirror):
    rng = random.Random(args.seed)
    jobs = []
    for _ in range(n):
        a = (rng.choice(RACES), rng.choice(OCCUPATIONS))
        b = a if mirror else (rng.choice(RACES), rng.choice(OCCUPATIONS))
        jobs.append((a, b, rng.randrange(2**31), args.team_size, args.scenario,
                     args.daylight, build, ban_ids))
    return jobs


def _run(jobs, workers):
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(_fight, jobs, chunksize=32))


def usage_report(args, build):
    results = _run(_jobs(args.battles, args, build, (), mirror=False), args.workers)
    ex_, op, turns = Counter(), Counter(), Counter()
    battles_used = Counter()
    for _score, e, o, t, _blocked in results:
        ex_ += e
        op += o
        turns += t
        for name in {name for (_team, name), n in e.items() if n}:
            battles_used[name] += 1
    names = sorted({name for _team, name in list(ex_) + list(op)})
    L = ["=" * 92, "GARTOK AI ACTION USAGE", "=" * 92,
         (f"{args.battles} battles, {args.team_size}v{args.team_size}, scenario={args.scenario}, "
          f"build={build}"),
         f"unit-turns: player {turns['player']}, enemy {turns['enemy']} (both sides run the same AI)", "",
         "executed/turn = executions per unit-turn; enabled = share of unit-turns where the",
         "action was usable at turn start (button on and, if aimed, a target in reach);",
         "take-up = executions per enabled turn",
         "(>1 means it is also used when not enabled at turn start, e.g. after moving).", "",
         f"{'action':<20}{'executed':>10}{'/turn':>9}{'enabled':>9}{'take-up':>9}{'battles':>9}"]
    total_turns = turns["player"] + turns["enemy"]
    rows = []
    for name in names:
        e = ex_[("player", name)] + ex_[("enemy", name)]
        o = op[("player", name)] + op[("enemy", name)]
        rows.append((e, name, o))
    for e, name, o in sorted(rows, reverse=True):
        take = f"{e / o:>9.2f}" if o else f"{'-':>9}"
        L.append(f"{name:<20}{e:>10}{e / total_turns:>9.3f}{o / total_turns:>9.1%}{take}"
                 f"{battles_used[name] / args.battles:>9.1%}")
    L.append("=" * 92)
    return "\n".join(L)


def ablation_report(args, build):
    ids = [i for i in args.ablate.split(",") if i]
    known = {c.id for c in _all_action_classes() if getattr(c, "id", "")}
    unknown = [i for i in ids if i not in known]
    if unknown:
        sys.exit(f"unknown action id(s): {', '.join(unknown)}\nknown: {', '.join(sorted(known))}")
    L = ["=" * 78, "GARTOK AI ACTION ABLATION", "=" * 78,
         (f"{args.battles} mirror fights per row, {args.team_size}v{args.team_size}, "
          f"scenario={args.scenario}, build={build}"),
         "player side loses the action; enemy keeps it. 0.500 = no cost. 'control' bans nothing",
         "blocked = execute calls on the banned action the AI still made (dropped)", "",
         f"{'ban':<18}{'score':>8}{'+/-SE':>8}{'z':>7}{'blocked':>8}"]
    for ban in [""] + ids:
        res = _run(_jobs(args.battles, args, build, (ban,) if ban else (), mirror=True), args.workers)
        xs = [r[0] for r in res]
        mean = sum(xs) / len(xs)
        se = math.sqrt(sum((x - mean) ** 2 for x in xs) / (len(xs) - 1) / len(xs))
        blocked = sum(sum(r[4].values()) for r in res)
        L.append(f"{ban or 'control':<18}{mean:>8.3f}{se:>8.3f}{(mean - 0.5) / se:>7.1f}{blocked:>8}")
        print(L[-1], flush=True)
    L.append("(control sits below 0.5 by the player side's own bias; compare rows to it)")
    L.append("=" * 78)
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--battles", type=int, default=4000)
    ap.add_argument("--team-size", type=int, default=3)
    ap.add_argument("--scenario", default="ermos")
    ap.add_argument("--daylight", type=lambda s: s.lower() != "false", default=True)
    ap.add_argument("--level", type=int, default=0)
    ap.add_argument("--racial", type=int, default=None)
    ap.add_argument("--gear", choices=("starting", "best", "random"), default="starting")
    ap.add_argument("--ablate", default="", help="comma-separated action ids to ban in turn")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", default="sim_results")
    args = ap.parse_args()

    build = Build(args.level, args.level, args.racial, args.gear)
    report = ablation_report(args, build) if args.ablate else usage_report(args, build)
    print("\n" + report)
    os.makedirs(args.out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    kind = "ablation" if args.ablate else "usage"
    path = os.path.join(args.out_dir, f"ai-usage-{kind}-L{args.level}-{args.gear}-{stamp}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(f"\nreport -> {path}")


if __name__ == "__main__":
    main()
