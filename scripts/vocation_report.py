"""Vocation perks on one yardstick: copper per guild-day, against the guild's daily wage.

The perks live in `gartok/vocations.py`. This prices each one from the game's own constants (the
defaults below read them) and shows what share of the guild's daily wage it is worth. A perk that fires every day for everyone should
land at a few percent of that wage; far above it is too strong, far below it is not worth a slot.

The wage `w` is the copper a member earns per day, at two points: early (the yard's pay) and late
(a Wilds hunt at `--level`, loot per member per day, from `economy_activities`). A lost unit costs
7 days of `w` (the weekly recruit pool is the time to replace it); a desertion adds what the
unit's alignment lets it carry out (`cohesion.depart`), taken here as `--kit` copper.

Not priced: the Wilds perk, because the travel stance makes it a choice and not a flow, and
Scholars, which waits for the combat info modal. Shares the sim does not count yet (how much of a day is
gathering or travelling, how much food rots) are arguments with a stated default.

    python scripts/vocation_report.py
    python scripts/vocation_report.py --level 4 --trials 20 --travel 0.3 --caravan 0.2
"""

from __future__ import annotations

import argparse
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.dirname(SCRIPTS))

import economy_activities as act
import economy_guild as eg

from gartok import economy, recruit, vocations

REPLACE_DAYS = recruit.REFRESH_DAYS
MD_STEP = vocations.COHESION_BONUS / 20                      # +1 Mental Defense moves the d20 walk-out roll by one face


def yard_wage():
    """Copper a member earns per day at the yard: a 16 h shift of 4 h blocks."""
    return economy.LUMBER_WAGE * (eg.SHIFT_HOURS // economy.LUMBER_BLOCK_HOURS)


def late_wage(level, size, trials):
    """Copper a member earns per day on the Wilds hunt at `level`, the top of the ladder
    (loot only, before eating): the wage a veteran gives up when a perk keeps them alive."""
    return act.hunt_row(size, level, trials).per_day


def perks(w, a):
    """Copper per guild-day each perk is worth at the effect the backlog proposes."""
    walk = REPLACE_DAYS * w + a.kit
    return {
        "Warband": ("+1 MD in the cohesion roll", a.overextended * MD_STEP * walk),
        "Delvers": (f"+{a.delvers:.0%} gathering yield", a.delvers * a.size * w * a.gather),
        "Caravan": (f"-{a.caravan:.0%} travel time", a.caravan * a.size * w * a.travel),
        "Marsh": (f"{a.marsh:.0%} of food rot avoided",
                  a.marsh * a.size * eg.cheapest_food_price() * a.rot_share),
    }


def report(label, w, a):
    wage = a.size * w
    print(f"\n{label}: wage {w:.2f} cp per member-day, {a.size} members "
          f"({wage:.1f} cp per guild-day), a lost unit {REPLACE_DAYS * w:.1f} cp")
    print(f"  {'perk':<8} {'effect':<30} {'cp/day':>8} {'share of wage':>14}")
    for name, (effect, value) in perks(w, a).items():
        print(f"  {name:<8} {effect:<30} {value:>8.2f} {value / wage:>14.1%}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--level", type=int, default=3, help="combat level of the late reference squad")
    ap.add_argument("--trials", type=int, default=12, help="hunts simulated for the late wage")
    ap.add_argument("--size", type=int, default=6, help="members of the reference (wide) guild")
    ap.add_argument("--kit", type=float, default=30, help="copper of kit a deserter carries out")
    ap.add_argument("--overextended", type=float, default=1.0,
                    help="share of days a group is past its leader's capacity (Warband is wide)")
    ap.add_argument("--gather", type=float, default=0.5, help="share of the day spent gathering")
    ap.add_argument("--travel", type=float, default=0.25, help="share of the day spent travelling")
    ap.add_argument("--rot-share", type=float, default=0.1,
                    help="share of the food the guild buys that rots before it is eaten")
    ap.add_argument("--delvers", type=float, default=vocations.GATHER_BONUS, help="Delvers' extra gathering yield")
    ap.add_argument("--caravan", type=float, default=1 - vocations.TRAVEL_FACTOR, help="Caravan's travel time saved")
    ap.add_argument("--marsh", type=float, default=1 / vocations.FOOD_PAUSE_EVERY, help="Marsh's share of rot avoided")
    a = ap.parse_args()

    report("EARLY (yard wage)", yard_wage(), a)
    report(f"LATE (Wilds hunt, level {a.level})", late_wage(a.level, 3, a.trials), a)
    print("\nAssumed, not measured: gather, travel, rot-share, kit, overextended.")


if __name__ == "__main__":
    main()
