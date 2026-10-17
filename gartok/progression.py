"""Leveling curves and the combat-XP rule  (designed for the wargame).

The generator left Level 0 / XP 1000 with no meaning (RULES.md §9).
This is the reconstruction: no classes, no class levels -- each *track* of
experience (combat, work) has its own level, and its own talent tree in
`talents.py`. A character gets better at what they actually do.

- **Combat XP** is earned only for downing an enemy of your combat level or
  above, worth `(their level - your level) + 1` (`xp_award`). Below your level
  is worth nothing -- a veteran mopping up fresh recruits does not level.
- **Work XP** is hours worked, banked in 16 h marks (`Unit.work_xp`) -- but
  scaled exactly like combat XP: an hour is worth `(activity - your work level)
  + 1` banked hours, and an activity below your work level teaches you
  nothing (`work_xp_hours`). The lumber yard is level 0 bare-handed, level 1
  once you own an Axe -- carried is enough (`economy.lumber_level`); hunting the wilds is level 3
  (`hunt.HUNT_LEVEL`), risk buying a longer runway before it too caps out.
- **Magic XP** comes from magic: a last hit dealt with a spell or a magic talent's action
  (the combat rule's amount, banked as magic instead), and a spell studied to the end.
- The **racial track** earns nothing of its own: its "XP" is the sum of the
  other track levels (`Unit.racial_xp`), run through `RACIAL_XP_THRESHOLDS`.
  Its level is what drives the hit-die gain and grants the racial talent picks
  (see `Unit`). `mean_level` survives only as the encounter/arena difficulty
  scalar -- it no longer touches hit points.

The curves are formulas with no top (`Curve`): a level is always one more threshold away.
They are a first-pass guess and meant to be tuned here -- this module is the one place
the curves live, like `economy.PRICES` for money.
"""

class Curve:
    """Cumulative XP for level 1, 2, 3, ... with no top: `curve[i]` is level i+1's threshold,
    worked out by `fn(level)`. `text` is the formula, for the reference."""

    def __init__(self, fn, text):
        self.fn = fn
        self.text = text

    def __getitem__(self, i):
        if i < 0:
            raise IndexError("a curve has no last level")
        return self.fn(i + 1)

    def level(self, xp):
        n = 0
        while self.fn(n + 1) <= xp:
            n += 1
        return n

    def first(self, n):
        return [self.fn(k) for k in range(1, n + 1)]


# Combat: L1 = 3 and L2 = 10 are set (the user's call); the gaps widen by 4 a level.
COMBAT_XP_THRESHOLDS = Curve(lambda n: 2 * n * n + n, "2n² + n")

# Work marks (Unit.work_xp): the gaps widen by 2 a level.
WORK_XP_THRESHOLDS = Curve(lambda n: n * (n + 1), "n(n + 1)")

# Magic XP: combat's curve until magic is played.
MAGIC_XP_THRESHOLDS = COMBAT_XP_THRESHOLDS

# The racial track's "XP" is `combat_level + work_level + magic_level` (Unit.racial_xp): every
# level anywhere feeds it, two of them a racial level -- the old `floor((combat + work) / 2)`
# hit-die count, so enemy HD / the balance sim / arena scaling do not move.
RACIAL_XP_THRESHOLDS = Curve(lambda n: 2 * n, "2n")
RACIAL_PICK_EVERY = 5
LEVEL_UI_CAP = 30         # the highest level an editor stepper offers; the curves themselves go on


def combat_level(combat_xp):
    return COMBAT_XP_THRESHOLDS.level(combat_xp)


def work_level(work_xp):
    return WORK_XP_THRESHOLDS.level(work_xp)


def magic_level(magic_xp):
    return MAGIC_XP_THRESHOLDS.level(magic_xp)


def racial_level(racial_xp):
    """Racial-track level for a `combat_level + work_level + magic_level` sum -- how many hit
    dice the character has earned past their starting one, and how many racial
    talent picks they hold."""
    return RACIAL_XP_THRESHOLDS.level(racial_xp)


def racial_picks(level):
    """Racial talent picks earned at racial `level`: one every `RACIAL_PICK_EVERY` levels."""
    return level // RACIAL_PICK_EVERY


def next_racial_pick(level):
    """The racial level that earns the next pick."""
    return (level // RACIAL_PICK_EVERY + 1) * RACIAL_PICK_EVERY


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
    """Hours of a work shift that bank toward work-XP, the same rule as
    `xp_award` applied to a job instead of a kill: a multiplier of
    `(activity - worker) + 1` for an activity at or above your own work level,
    none once you have outgrown it (a lumber yard you can already do in your
    sleep stops teaching you anything, even though it still pays)."""
    return hours * (activity_level - worker_level + 1) if activity_level >= worker_level else 0


def to_next(thresholds, xp):
    """`(into, span)` for a progress bar: `into` XP earned toward the next level
    out of a `span`-wide band."""
    level = thresholds.level(xp)
    prev = thresholds[level - 1] if level else 0
    return xp - prev, thresholds[level] - prev


def eligible_work_activities(worker_level, unit=None) -> list[str]:
    """Return human-readable descriptions of work activities that grant work-XP
    to a worker of `worker_level`."""
    activities = []
    for place, node_id, tool in (("Lumber Yard", "lumber_yard", "Axe"), ("Mine", "mine", "Pick")):
        if worker_level == 0:
            activities.append(f"{place} (bare-handed or {tool})")
        elif worker_level == 1:
            if unit is not None:
                from . import economy
                if economy.work_level(unit, node_id) >= 1:
                    activities.append(f"{place} (with your {tool})")
                else:
                    activities.append(f"{place} (requires owning {'an' if tool[0] in 'AEIOU' else 'a'} {tool})")
            else:
                activities.append(f"{place} (requires {tool})")

    # Tavern stage
    if worker_level <= 1:
        activities.append("Tavern stage (with a Musical Instrument)")

    # Hunting in the Wilds
    if worker_level <= 3:
        activities.append("Hunting (Lv 3 in Wilds)")

    # Frontier Supply Run at Ledger Hold
    if worker_level <= 5:
        activities.append("Frontier Supply Run (Lv 5 at Ledger Hold)")

    # Crafting (dynamically generated from registered recipes)
    from . import craft_level, items
    recipes_by_level = {}
    for r_name, r in items.CRAFTING_RECIPES.items():
        lvl = craft_level.level_of(r)
        if lvl >= worker_level:
            recipes_by_level.setdefault(lvl, []).append(r_name)

    if worker_level <= 1:
        if recipes_by_level:
            activities.append("Crafting (Lv 1+ recipes)")
    else:
        for lvl in sorted(recipes_by_level.keys()):
            names = recipes_by_level[lvl]
            summary_names = []
            dict_count = 0
            for n in names:
                if n.startswith("Dictionary of "):
                    dict_count += 1
                else:
                    summary_names.append(n)
            if dict_count:
                summary_names.append(f"{dict_count} Dictionaries" if summary_names else "Dictionaries")
            label = ", ".join(summary_names[:4])
            if len(summary_names) > 4:
                label += ", ..."
            activities.append(f"Crafting (Lv {lvl}: {label})")

    return activities
