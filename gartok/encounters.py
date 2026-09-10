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
"""

import random

from . import progression, talents
from .unit import Unit

# The Wilds: a pack is 1..6 bodies, most often 3, tapering faster on the high
# side; each body's mean level is 0..4, level 0 the common case. Weights, not
# probabilities -- retune freely, they are normalised on use.
WILDS_COUNT_WEIGHTS = {1: 10, 2: 20, 3: 30, 4: 20, 5: 7, 6: 3}
WILDS_LEVEL_WEIGHTS = {0: 40, 1: 25, 2: 18, 3: 12, 4: 5}

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


def build_enemy(mean_level, rng=random):
    """A fresh `Unit("enemy")` pitched at `mean_level`: track levels split at
    random to that mean, then random talent picks that respect each tree."""
    u = Unit("enemy")
    combat, work = _split_tracks(mean_level, rng)
    u.set_track_level("combat", combat)
    u.set_track_level("work", work)
    for track in talents.TRACKS:
        guard = 0
        while u.picks_available(track) > 0 and guard < 20:
            guard += 1
            picked = u.talents[track]
            options = [t.id for t in talents.TREE[track]
                       if t.id not in picked
                       and (t.requires is None or t.requires in picked)]
            if not options:
                break
            u.choose_talent(track, rng.choice(options))
    return u


def roll_pack(count_weights=WILDS_COUNT_WEIGHTS, level_weights=WILDS_LEVEL_WEIGHTS,
              rng=random):
    """A list of enemy `Unit`s: a rolled headcount, each rolled its own level."""
    n = weighted_choice(count_weights, rng)
    return [build_enemy(weighted_choice(level_weights, rng), rng) for _ in range(n)]
