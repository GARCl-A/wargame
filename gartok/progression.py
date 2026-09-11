"""Leveling curves and the combat-XP rule  (designed for the wargame).

The generator left Level 0 / XP 1000 with no meaning (RULES.md §9).
This is the reconstruction: no classes, no class levels -- each *track* of
experience (combat, work) has its own level, and its own talent tree in
`talents.py`. A character gets better at what they actually do.

- **Combat XP** is earned only for downing an enemy of your combat level or
  above, worth `(their level - your level) + 1` (`xp_award`). Below your level
  is worth nothing -- a veteran mopping up fresh recruits does not level.
- **Work XP** is hours worked, banked in 16 h marks (`Unit.work_xp`) -- but
  gated exactly like combat XP: an activity below your work level teaches you
  nothing (`work_xp_hours`). The lumber yard is level 0 bare-handed, level 1
  once you own an Axe -- carried is enough (`economy.lumber_level`); hunting the wilds is level 3
  (`hunt.HUNT_LEVEL`), risk buying a longer runway before it too caps out.
- The **racial track** earns nothing of its own: its "XP" is the sum of the
  other track levels (`Unit.racial_xp`), run through `RACIAL_XP_THRESHOLDS`.
  Its level is what drives the hit-die gain and grants the racial talent picks
  (see `Unit`). `mean_level` survives only as the encounter/arena difficulty
  scalar -- it no longer touches hit points.

The thresholds are a first-pass guess and meant to be tuned here -- this module
is the one place the curves live, like `economy.PRICES` for money.
"""

# Cumulative XP for combat level 1, 2, 3, ...  L1 and L2 are set (the user's
# call); the rest is a stub with a widening gap (+4 each step). Tune freely.
COMBAT_XP_THRESHOLDS = [3, 10, 21, 36, 55, 78, 105]

# Cumulative work *marks* (Unit.work_xp) for work level 1, 2, 3, ...  Stub.
WORK_XP_THRESHOLDS = [2, 6, 12, 20, 30, 42]

# The racial track's "XP" is `combat_level + work_level` (Unit.racial_xp): every
# level anywhere feeds it. These cumulative sums for racial level 1, 2, 3, ...
# are set to reproduce the old `floor((combat + work) / 2)` hit-die count, so
# enemy HD / the balance sim / arena scaling do not move. Tune freely here.
RACIAL_XP_THRESHOLDS = [2, 4, 6, 8, 10, 12, 14]


def _level_for(thresholds, xp):
    return sum(1 for t in thresholds if xp >= t)


def combat_level(combat_xp):
    return _level_for(COMBAT_XP_THRESHOLDS, combat_xp)


def work_level(work_xp):
    return _level_for(WORK_XP_THRESHOLDS, work_xp)


def racial_level(racial_xp):
    """Racial-track level for a `combat_level + work_level` sum -- how many hit
    dice the character has earned past their starting one, and how many racial
    talent picks they hold."""
    return _level_for(RACIAL_XP_THRESHOLDS, racial_xp)


def mean_level(*track_levels):
    """The average track level, floored -- the encounter / arena difficulty
    scalar (`encounters.build_enemy`, `arena.build_challenger`). No longer tied
    to hit points; that is `racial_level` now."""
    return sum(track_levels) // len(track_levels)


def xp_award(attacker_level, victim_level):
    """Combat XP for downing a `victim_level` enemy while at `attacker_level`:
    `(victim - attacker) + 1` if the victim is at or above you, else 0."""
    return victim_level - attacker_level + 1 if victim_level >= attacker_level else 0


def work_xp_hours(hours, activity_level, worker_level):
    """Hours of a work shift that actually bank toward work-XP: the same "no
    free lunch" gate as `xp_award`, applied to a job instead of a kill -- full
    credit for an activity at or above your own work level, none once you have
    outgrown it (so a lumber yard you can already do in your sleep stops
    teaching you anything, even though it still pays)."""
    return hours if activity_level >= worker_level else 0


def to_next(thresholds, xp):
    """`(into, span)` for a progress bar: `into` XP earned toward the next level
    out of a `span`-wide band. At the top of the table -> `(0, 0)`."""
    level = _level_for(thresholds, xp)
    if level >= len(thresholds):
        return 0, 0
    prev = thresholds[level - 1] if level else 0
    return xp - prev, thresholds[level] - prev
