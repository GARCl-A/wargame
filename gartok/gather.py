"""Gathering at a work node: a licence, then a shift that yields items instead of the wage.

The Lumber Yard and the Mine pay a wage for a shift (`economy.work_pay`). With the node's
licence (bought once there, held by the whole guild) a group may gather instead: every worker
rolls `rolls(hours)` times on the node's drop table, rarer items further down, and the haul goes
into their pack. A pack may find the crew first (`ambushed`); the haul is banked only if the
crew wins. `Guild.gather_shift` runs it, `campaign` and `app` play the fight.

The tables, the rate and the licence prices are tuned so that a shift sold to a shop is worth more
than the best wage for the same hours, and a full day (16 h) at least `PREMIUM` copper more (a test
holds both); a licence pays back in about `PAYBACK_DAYS` days for `PAYBACK_CREW` workers gathering
16 h a day. Rolls are a rate, not a count: a shift gets `hours / HOURS_PER_ROLL` of them, the
fraction left over being the chance of one more.
"""

import random
from collections import Counter

from . import economy, encounters, items

HOURS_PER_ROLL = 7
PREMIUM = 3
DAY_HOURS = 16
PAYBACK_DAYS = 30
PAYBACK_CREW = 3

# node id -> ((item, weight), ...), each weight the percent chance of one roll
TABLES = {
    "lumber_yard": (("Lumber", 75), ("Fruit", 25)),
    "mine": (("Stone Brick", 55), ("1kg Coal", 25), ("Iron Ore", 15),
             (items.GEM_ITEM, 4), (items.PRECIOUS_GEM_ITEM, 1)),
}
LICENCE_PRICE = {"lumber_yard": 270, "mine": 385}
RISK_PER_HOUR = {"lumber_yard": 0.005, "mine": 0.01}
AMBUSH_TABLES = {"lumber_yard": encounters.LUMBER_YARD_TABLE, "mine": encounters.MINE_TABLE}
AMBUSH_LEVEL_WEIGHTS = encounters.WILDS_LEVEL_WEIGHTS


def can_gather(node_id):
    return node_id in TABLES


def rolls(hours):
    return hours / HOURS_PER_ROLL


def licence_price(node_id):
    return LICENCE_PRICE[node_id]


def drops(node_id):
    """`[(item, percent)]` of the node's table, most common first."""
    return list(TABLES[node_id])


def roll_haul(node_id, hours, mult=1.0, rng=random):
    """The items one worker gathers in a shift of `hours`: `rolls(hours)` rolls on the table,
    times `mult` (the Delvers' bonus; the fraction of a roll left over is a chance of one more)."""
    count = rolls(hours) * mult
    n = int(count) + (rng.random() < count - int(count))
    table = TABLES[node_id]
    picks = rng.choices([name for name, _ in table], weights=[w for _, w in table], k=n)
    return Counter(picks)


def expected_value(node_id, hours):
    """Average copper one worker's shift is worth when sold, from the table alone."""
    table = TABLES[node_id]
    total = sum(w for _, w in table)
    per_roll = sum(economy.sell_price(name) * w for name, w in table) / total
    return per_roll * rolls(hours)


def ambushed(node_id, hours, chance_mult=1.0, rng=random):
    """Whether a pack finds a crew that gathered `hours` (the odds of at least one hour's roll)."""
    per_hour = RISK_PER_HOUR[node_id] * chance_mult
    return rng.random() < 1 - (1 - per_hour) ** hours


def ambush_pack(node_id, rng=random):
    return encounters.roll_encounter(AMBUSH_TABLES[node_id], encounters.GATHER_COUNT_WEIGHTS,
                                     AMBUSH_LEVEL_WEIGHTS, rng)


def describe(haul):
    """`'2 Stone Brick, 1 Coal'` for the log."""
    return ", ".join(f"{n} {name}" if n > 1 else name for name, n in sorted(haul.items())) or "nothing"
