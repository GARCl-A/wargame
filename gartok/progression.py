"""Leveling curves and the combat-XP rule  (designed for the wargame).

The generator left Level 0 / XP 1000 with no meaning (RULES.md §9).
This is the reconstruction: no classes, no class levels -- each *track* of
experience (combat, work) has its own level, and its own talent tree in
`talents.py`. A character gets better at what they actually do.

- **Combat XP** is earned only for downing an enemy of your combat level or
  above, worth `(their level - your level) + 1` (`xp_award`). Below your level
  is worth nothing -- a veteran mopping up fresh recruits does not level.
- **Work XP** is the lumber-yard marks (`Unit.work_xp`, one per 16 h).
- The **mean** of the track levels drives the hit-die gain (see `Unit`).

The thresholds are a first-pass guess and meant to be tuned here -- this module
is the one place the curves live, like `economy.PRICES` for money.
"""

# Cumulative XP for combat level 1, 2, 3, ...  L1 and L2 are set (the user's
# call); the rest is a stub with a widening gap (+4 each step). Tune freely.
COMBAT_XP_THRESHOLDS = [3, 10, 21, 36, 55, 78, 105]

# Cumulative work *marks* (Unit.work_xp) for work level 1, 2, 3, ...  Stub.
WORK_XP_THRESHOLDS = [2, 6, 12, 20, 30, 42]


def _level_for(thresholds, xp):
    return sum(1 for t in thresholds if xp >= t)


def combat_level(combat_xp):
    return _level_for(COMBAT_XP_THRESHOLDS, combat_xp)


def work_level(work_xp):
    return _level_for(WORK_XP_THRESHOLDS, work_xp)


def mean_level(*track_levels):
    """The average track level, floored -- how many hit dice the character has
    earned past their starting one."""
    return sum(track_levels) // len(track_levels)


def xp_award(attacker_level, victim_level):
    """Combat XP for downing a `victim_level` enemy while at `attacker_level`:
    `(victim - attacker) + 1` if the victim is at or above you, else 0."""
    return victim_level - attacker_level + 1 if victim_level >= attacker_level else 0


def to_next(thresholds, xp):
    """`(into, span)` for a progress bar: `into` XP earned toward the next level
    out of a `span`-wide band. At the top of the table -> `(0, 0)`."""
    level = _level_for(thresholds, xp)
    if level >= len(thresholds):
        return 0, 0
    prev = thresholds[level - 1] if level else 0
    return xp - prev, thresholds[level] - prev
