"""Rolling a pack of enemies scaled to a place.

Every generated enemy used to be level 0, so the leveling and talent systems had
nothing to bite on. This is the shared spawn core: build one enemy pitched at a
target **mean level** (`build_enemy`), or roll a whole pack whose size and per-
member level are drawn from a locality's weighted table (`roll_pack`).

"Level" here is always the *mean* of a unit's two track levels (combat, work) --
`progression.mean_level`. How the mean is split between the tracks is rolled at
random and does not matter to the caller; only that the mean lands where asked
and the talent picks respect the trees (`Talent.requires`).

The Wilds is the first consumer (open country near the city -> levels 0..4, the
low end common). The arena tiers are meant to scale through here too, later;
`arena.build_challenger` already delegates to `build_enemy`.

A locality's **encounter table** (`EncounterEntry`, e.g. `WILDS_TABLE`) is a
second, orthogonal roll on top of that: which *pool* of bodies (`data.BEAST_POOL`,
`data.RACE_POOL`, ...) a pack is drawn from. `roll_encounter` picks one entry by
weight, then hands its `race_pool` down to `roll_pack`/`build_enemy` -- headcount
and level keep coming from the same weights regardless of who shows up.
"""

import random
from dataclasses import dataclass

from . import data, progression, talents
from .unit import Unit

# The Wilds: a pack is 1..6 bodies, most often 3, tapering faster on the high
# side; each body's mean level is 0..4, level 0 the common case. Weights, not
# probabilities -- retune freely, they are normalised on use.
WILDS_COUNT_WEIGHTS = {1: 10, 2: 20, 3: 30, 4: 20, 5: 7, 6: 3}
WILDS_LEVEL_WEIGHTS = {0: 40, 1: 25, 2: 18, 3: 12, 4: 5}

# The arena's second stage (the Games): opponents run level 1..6, level 1 the
# common draw and level 6 the rare one. Weights, retune freely.
ARENA_LEVEL_WEIGHTS = {1: 30, 2: 24, 3: 18, 4: 13, 5: 9, 6: 6}

_COMBAT_CAP = len(progression.COMBAT_XP_THRESHOLDS)
_WORK_CAP = len(progression.WORK_XP_THRESHOLDS)


def weighted_choice(weights, rng=random):
    """Pick one key from a `{key: weight}` dict, in proportion to the weights."""
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys])[0]


def _split_tracks(mean_level, rng):
    """A random (combat, work) level pair that averages to `mean_level`.

    `mean_level` is floor((c + w) / 2), so any pair summing to `2 * mean_level`
    hits it exactly. Pick `c` in the range the track caps allow, `w` fills in.
    `lo <= hi` holds for every `mean_level` up to (combat cap + work cap) // 2."""
    total = 2 * mean_level
    lo = max(0, total - _WORK_CAP)
    hi = min(_COMBAT_CAP, total)
    combat = rng.randint(lo, hi)
    return combat, total - combat


def build_enemy(mean_level, rng=random, race_pool=None):
    """A fresh `Unit("enemy")` pitched at `mean_level`: track levels split at
    random to that mean, then random talent picks that respect each tree.
    `race_pool` (a list of race dicts, e.g. `data.BEAST_POOL`) draws the body
    from there instead of a fresh random humanoid -- None keeps the old
    behaviour (`Unit`'s own `data.roll_race()`)."""
    u = Unit("enemy", race=rng.choice(race_pool) if race_pool else None)
    combat, work = _split_tracks(mean_level, rng)
    u.set_track_level("combat", combat)
    u.set_track_level("work", work)
    for track in talents.TRACKS:
        tree = (talents.TREE[track] if track in talents.XP_TRACKS
                else talents.racial_tree(u.race["name"]))
        guard = 0
        while u.picks_available(track) > 0 and guard < 20:
            guard += 1
            picked = u.talents[track]
            options = [t.id for t in tree
                       if t.id not in picked
                       and (t.requires is None or t.requires in picked)]
            if not options:
                break
            u.choose_talent(track, rng.choice(options))
    return u


def roll_pack(count_weights=WILDS_COUNT_WEIGHTS, level_weights=WILDS_LEVEL_WEIGHTS,
              rng=random, race_pool=None):
    """A list of enemy `Unit`s: a rolled headcount, each rolled its own level
    (and, with `race_pool` given, its own body drawn from that pool)."""
    n = weighted_choice(count_weights, rng)
    return [build_enemy(weighted_choice(level_weights, rng), rng, race_pool=race_pool)
            for _ in range(n)]


@dataclass(frozen=True)
class EncounterEntry:
    """One line of a locality's encounter table: how likely it turns up
    (`weight`, normalised against its table's siblings) and which pool of race
    dicts a pack's bodies are drawn from -- `None` means an unrestricted
    humanoid, correctly weighted by `RACES`' own thresholds (`build_enemy`'s
    `race_pool=None` falls through to `Unit`'s own `data.roll_race()`); a
    *tuple* pool (e.g. `data.BEAST_POOL`) always draws uniformly instead, since
    the bodies in it don't carry rarity thresholds of their own yet. Headcount/
    level weights are the table's own, passed to `roll_encounter` -- what
    varies entry to entry is *who* shows up, not how many or how tough."""
    weight: int
    race_pool: tuple | None


# The Wilds: mostly a wolf pack (the point of hunting there now -- see the
# Wolf's `drop_item` in `data.BEASTS`); a rarer bandit gang keeps the old
# all-humanoid rolls from before beasts existed from vanishing outright --
# `None`, not `tuple(data.RACE_POOL)`, so it stays weighted by rarity instead
# of flattening every race to an equal ~5.5% (`data.roll_race()`'s thresholds).
WILDS_TABLE = (
    EncounterEntry(70, tuple(data.BEAST_POOL)),
    EncounterEntry(30, None),
)


def roll_encounter(table, count_weights=WILDS_COUNT_WEIGHTS,
                   level_weights=WILDS_LEVEL_WEIGHTS, rng=random):
    """A pack rolled off a locality's `EncounterEntry` table: one entry picked
    by weight decides the race pool every body in the pack is drawn from."""
    i = weighted_choice({i: e.weight for i, e in enumerate(table)}, rng)
    return roll_pack(count_weights, level_weights, rng, race_pool=table[i].race_pool)
