"""What a stretch of rest costs a group, and how long "until full" lasts.

`orders.rest(hours)` is the order; this is the arithmetic the REST menu shows
before it is issued. "Until full" is HP only (not sickness): the time every
hurt member needs at `guild_upkeep.rest_heal` per `HOURS_PER_HEAL`, cut short
so the group is never left unable to eat the next day -- far from food, a
zeroed larder is worse than a wound.

The plan is a simulation on copies of the members and of what the group
carries, running the same meal (`Guild._meal_pass`), rot (`Guild._rot_food`)
and heal (`rest_heal`) rules the clock does, so plan and actual agree --
`tests/test_rest.py` holds them to it. Poison (`tick_poison` moves HP hourly) is
refused rather than predicted.
"""

import copy
import math
from dataclasses import dataclass

from .clock import SECONDS_PER_DAY, SECONDS_PER_HOUR
from .guild_upkeep import HOURS_PER_HEAL, rest_heal

MAX_DAYS = 200
JUST_BEFORE_MIDNIGHT = 1 / 60          # a capped rest stops a minute short of the meal it cannot afford


@dataclass
class RestPlan:
    hours: float = 0.0
    meals: int = 0                     # midnights crossed: one ration each
    capped: bool = False               # the floor, not full health, ended it
    reason: str | None = None          # why it is unavailable
    worst: tuple | None = None         # (name, hp, hp_max) of the one furthest from full at the end
    short_days: int = 0                # when capped: the days of rations still missing to reach full health

    @property
    def available(self):
        return self.reason is None


def hours_to_midnight(guild):
    left = SECONDS_PER_DAY - guild.clock.seconds % SECONDS_PER_DAY
    return left / SECONDS_PER_HOUR


def midnights(guild, hours):
    """How many midnights a rest of `hours` crosses (each one a daily meal)."""
    first = hours_to_midnight(guild)
    return 0 if hours < first - 1e-9 else int((hours - first) // 24) + 1


def format_hours(hours):
    if hours < 1:
        return f"{round(hours * 60)} min"
    days, rest = divmod(round(hours), 24)
    return " ".join(([f"{days} d"] if days else []) + ([f"{rest} h"] if rest else []))


def fixed(guild, hours):
    """The plain 1 h / 8 h rows: no floor, just what the hours cost."""
    return RestPlan(hours=hours, meals=midnights(guild, hours))


class _Camp:
    """The group's members and what it carries, as copies the plan may eat from."""

    def __init__(self, group):
        self.members = copy.deepcopy(group.members)
        self.stores = copy.deepcopy(group.food_stores())

    def larder(self, eater):
        return [u._base_inventory for u in self.members if u is not eater and u.share_food] + self.stores

    def midnight(self, guild):
        """One daily meal: rot, bloom, eat. True when everyone was fed fresh food."""
        for u in self.members:
            guild._rot_food(u._base_inventory)
        for pack in self.stores:
            guild._rot_food(pack)
        for u in self.members:
            if u.has_talent("fruitful"):
                u.give_to_pack("Fruit")
        rotten = self._rotten()
        outcomes = guild._meal_pass(self.members, self.larder)
        return self._rotten() == rotten and all(o == "ate" for o in outcomes.values())

    def _rotten(self):
        """Rotten Food left in the packs: a meal that eats some was not a fresh one."""
        total = 0
        for pack in (*(u._base_inventory for u in self.members), *self.stores):
            for entry in pack:
                if entry.name.startswith("Rotten Food"):
                    total += entry.qty
        return total

    def can_feed_tomorrow(self, guild):
        return copy.deepcopy(self).midnight(guild)


def until_full(guild, group):
    blocked = _blocked(group)
    if blocked:
        return RestPlan(reason=blocked)
    camp = _Camp(group)
    guild._eat_now(camp.members, camp.larder)
    starved = next((u for u in camp.members if u.hunger_level), None)
    if starved is not None:
        return RestPlan(reason=f"{starved.name} is hungry and has nothing to eat")

    heals = {id(u): _heal_times(u) for u in camp.members if u.hp < u.hp_max}
    full_at = max(times[-1] for times in heals.values())
    first = hours_to_midnight(guild)
    wanted = midnights(guild, full_at)

    if not camp.can_feed_tomorrow(guild):
        return RestPlan(reason="the group is already down to its last day of rations")
    allowed = 0
    while allowed < min(wanted, MAX_DAYS):
        camp.midnight(guild)
        if not camp.can_feed_tomorrow(guild):
            break
        allowed += 1

    if allowed >= wanted:
        hours, capped = full_at, False
    else:
        hours, capped = first + 24 * allowed - JUST_BEFORE_MIDNIGHT, True
    if hours <= 0:
        return RestPlan(reason="the group is already down to its last day of rations")
    return RestPlan(hours=hours, meals=allowed if capped else wanted, capped=capped,
                    worst=_worst(camp.members, heals, hours), short_days=wanted - allowed if capped else 0)


def _blocked(group):
    if not any(u.hp < u.hp_max for u in group.members):
        return "nobody is hurt"
    poisoned = next((u for u in group.members if u.poisons), None)
    if poisoned is not None:
        return f"{poisoned.name} is poisoned"
    return None


def _heal_times(unit):
    """Hours into the rest at which each heal lands, from the carried-over rest."""
    each = rest_heal(unit)
    count = math.ceil((unit.hp_max - unit.hp) / each)
    start = HOURS_PER_HEAL - unit.consecutive_rest_hours
    return [start + HOURS_PER_HEAL * i for i in range(count)]


def _worst(members, heals, hours):
    worst = None
    for u in members:
        done = sum(1 for t in heals.get(id(u), ()) if t <= hours + 1e-9)
        hp = min(u.hp_max, u.hp + rest_heal(u) * done)
        if worst is None or hp / u.hp_max < worst[1] / worst[2]:
            worst = (u.name, hp, u.hp_max)
    return worst
