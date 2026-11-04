"""Routines: the blocks a player assigns to a group, which then runs them under its orders.

A routine is a layer above `Order`. `Group.routine` holds the blocks and a pointer; every time the group's
order resolves, `campaign` calls `advance`, which runs the blocks that take no time and emits the next
ordinary `Order` for the one that does (`travel`, `work`, `rest`, `wait`). The routine owns no countdown.

A block is an idempotent "make this so": `Travel` is done when the group stands at the node, `Wait` when its
condition holds. Only the timed blocks that finish by elapsing (`Gather`, `Work`, `Rest`) set `inflight`, so
that the order resolving normally steps the pointer on; an interrupted order leaves the pointer on its
block and the routine paused until `resume` (the player's *Continue*).

Goods move between the packs of the members of two groups at the same node, never wagons or herds."""

import operator
from dataclasses import dataclass, field, fields, is_dataclass

from . import gather, orders, vocations

MAX_INSTANT = 16        # blocks that spend no time, one after another, before the routine is paused
WAIT_HOURS = 1          # how often a `Wait` looks at its condition again
HAND_OVER_WAIT_HOURS = 24

_OPS = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge}


@dataclass(frozen=True)
class Ref:
    """Which group a block or a condition means: the acting one, one by name, another at this node
    doing an action, or any other at this node."""
    how: str                 # "own" | "named" | "doing" | "here"
    arg: str | None = None


def own():
    return Ref("own")


def group(name):
    return Ref("named", name)


def doing(action):
    return Ref("doing", action)


def anyone_here():
    return Ref("here")


def _action_of(order):
    if order is None:
        return None
    return "gather" if order.kind == "work" and order.gather else order.kind


def find(guild, acting, ref):
    """The group `ref` names for `acting`, or None. The ones named by what they do or by being here
    are other groups at the acting group's node."""
    if ref.how == "own":
        return acting
    if ref.how == "named":
        return next((g for g in guild.groups if g.display_name == ref.arg), None)
    others = [g for g in guild.groups if g is not acting and g.node == acting.node and not g.empty]
    if ref.how == "doing":
        return next((g for g in others if _action_of(g.order) == ref.arg), None)
    return next(iter(others), None)


def count_of(target, item):
    return sum(u.count_of(item) for u in target.members)


def _hp_percent(target):
    return min((100 * u.hp / u.hp_max for u in target.members), default=0)


_METRICS = {
    "items": lambda t, item: count_of(t, item),
    "coins": lambda t, item: sum(u.money for u in t.members),
    "hp": lambda t, item: _hp_percent(t),
    "food_days": lambda t, item: t.rations_days,
}


@dataclass(frozen=True)
class Cond:
    metric: str
    ref: Ref
    item: str | None
    op: str
    value: float

    def holds(self, guild, acting):
        target = find(guild, acting, self.ref)
        return target is not None and _OPS[self.op](_METRICS[self.metric](target, self.item), self.value)


@dataclass(frozen=True, eq=False)
class Metric:
    """A number read off a group; comparing it to a number makes a `Cond` (`coins(own()) >= 500`)."""
    metric: str
    ref: Ref
    item: str | None = None

    def _cond(self, op, value):
        return Cond(self.metric, self.ref, self.item, op, value)

    def __lt__(self, value):
        return self._cond("<", value)

    def __le__(self, value):
        return self._cond("<=", value)

    def __gt__(self, value):
        return self._cond(">", value)

    def __ge__(self, value):
        return self._cond(">=", value)


def items(ref, item):
    return Metric("items", ref, item)


def coins(ref):
    return Metric("coins", ref)


def hp(ref):
    return Metric("hp", ref)


def food_days(ref):
    return Metric("food_days", ref)


@dataclass(frozen=True)
class Travel:
    node: str


@dataclass(frozen=True)
class Gather:
    hours: float = 16


@dataclass(frozen=True)
class Work:
    hours: float = 16


@dataclass(frozen=True)
class Rest:
    hours: float = 8


@dataclass(frozen=True)
class Wait:
    cond: Cond


@dataclass(frozen=True)
class Take:
    """Pick `count` of `item` (all of it by default) from another group's packs, or as many as it
    takes for this group's food to last `until_days`."""
    source: Ref
    item: str
    count: int | None = None
    until_days: float | None = None


@dataclass(frozen=True)
class HandOver:
    """Pass `count` of `item` (all of it by default) to another group at the same node. With `fallback`
    on, a receiver that is not there is waited for one day before the routine gives up."""
    to: Ref
    item: str
    count: int | None = None
    fallback: bool = True


@dataclass(frozen=True)
class Trade:
    """At the shop where the group stands: sell all it carries of the `sell` items, then buy `buy`
    ((item, count) pairs) and as much `food` as it takes to last `food_days`."""
    sell: tuple = ()
    buy: tuple = ()
    food_days: float | None = None
    food: str = "Potato"

    def __post_init__(self):
        object.__setattr__(self, "sell", tuple(self.sell))
        object.__setattr__(self, "buy", tuple(tuple(pair) for pair in self.buy))


@dataclass(frozen=True)
class Repeat:
    """Run `body` again and again while `cond` holds (until it holds, with `until`), checked before each pass."""
    cond: Cond
    body: tuple
    until: bool = False

    def __post_init__(self):
        object.__setattr__(self, "body", tuple(self.body))


@dataclass
class Routine:
    blocks: tuple
    path: list = field(default_factory=lambda: [0])    # index of the current block, then of its place in each Repeat body
    inflight: bool = False                             # a timed block's order is out: its resolving finishes the block
    paused: str | None = None                          # why the routine is waiting on the player
    waited_since: float | None = None                  # clock second a `HandOver` began waiting for its receiver

    def __post_init__(self):
        self.blocks = tuple(self.blocks)
        self.path = list(self.path)

    def _level(self, depth):
        level = self.blocks
        for i in self.path[:depth]:
            level = level[i].body
        return level

    def current(self):
        level = self._level(len(self.path) - 1)
        return level[self.path[-1]] if self.path[-1] < len(level) else None

    def step_on(self):
        self.waited_since = None
        self.path[-1] += 1
        while len(self.path) > 1 and self.path[-1] >= len(self._level(len(self.path) - 1)):
            self.path.pop()                            # the Repeat is looked at again


_KINDS = {c.__name__: c for c in (Ref, Cond, Travel, Gather, Work, Rest, Wait, Take, HandOver, Trade, Repeat, Routine)}


def dump(obj):
    if is_dataclass(obj):
        return {"_": type(obj).__name__, **{f.name: dump(getattr(obj, f.name)) for f in fields(obj)}}
    if isinstance(obj, (list, tuple)):
        return [dump(x) for x in obj]
    return obj


def load(data):
    if isinstance(data, dict):
        return _KINDS[data["_"]](**{k: load(v) for k, v in data.items() if k != "_"})
    if isinstance(data, list):
        return tuple(load(x) for x in data)
    return data


def assign(guild, group, routine):
    """Put `routine` on an idle `group` and start its first block. Returns the log lines."""
    if group.order is not None or group.fight_due:
        raise ValueError(f"{group.display_name} is busy")
    group.routine = routine
    return advance(guild, group)


def resume(guild, group):
    """The player's *Continue*: run the block the routine stopped on again."""
    routine = group.routine
    routine.paused = None
    routine.waited_since = None
    return advance(guild, group)


def interrupt(group, reason):
    """Hand the group back to the player, the pointer left on the block that was running."""
    routine = group.routine
    routine.paused, routine.inflight = reason, False
    return [f"{group.display_name}: routine stopped -- {reason}."]


def advance(guild, group):
    """Run the group's routine up to the next timed block and give the group its order. Returns the
    log lines; the routine ends (`group.routine` is cleared) when the last block is done."""
    routine = group.routine
    if routine is None or routine.paused:
        return []
    if routine.inflight:
        routine.inflight = False
        routine.step_on()
    for _ in range(MAX_INSTANT):
        block = routine.current()
        if block is None:
            group.routine = None
            return [f"{group.display_name}: routine finished."]
        if isinstance(block, Repeat):
            if block.cond.holds(guild, group) != block.until and block.body:
                routine.path.append(0)
            else:
                routine.step_on()
            continue
        outcome = _run(guild, group, routine, block)
        if isinstance(outcome, str):
            return interrupt(group, outcome)
        if outcome is not None:
            group.order = outcome
            return []
        routine.step_on()
    return interrupt(group, "too many blocks in no time")


def _run(guild, group, routine, block):
    """An `Order` to wait on, a string (why the block cannot run), or None when it is done."""
    if isinstance(block, Travel):
        if group.node == block.node:
            return None
        try:
            return orders.travel(group, block.node, vocations.travel_mult(guild, group))
        except ValueError as err:
            return str(err)
    if isinstance(block, (Gather, Work)):
        if isinstance(block, Gather) and not gather.can_gather(group.node):
            return "nothing to gather here"
        try:
            order = orders.work(guild, group, block.hours, gather=isinstance(block, Gather))
        except ValueError as err:
            return str(err)
        routine.inflight = True
        return order
    if isinstance(block, Rest):
        routine.inflight = True
        return orders.rest(block.hours)
    if isinstance(block, Wait):
        return None if block.cond.holds(guild, group) else orders.wait(WAIT_HOURS)
    if isinstance(block, Take):
        return _take(guild, group, block)
    if isinstance(block, Trade):
        return _trade(guild, group, block)
    return _hand_over(guild, group, routine, block)


def _other_here(guild, group, ref):
    other = find(guild, group, ref)
    return other if other is not None and other is not group and other.node == group.node else None


def _take(guild, group, block):
    source = _other_here(guild, group, block.source)
    if source is None:
        return "no group to take from"
    wanted = block.count
    if block.until_days is not None:
        wanted = max(0, group.rations_for(block.until_days) - group.rations)
        if not wanted:
            return None
    if not _move(source, group, block.item, wanted):
        return f"no {block.item} to take"
    return None


def _hand_over(guild, group, routine, block):
    receiver = _other_here(guild, group, block.to)
    if receiver is None:
        if not block.fallback or routine.waited_since is not None:
            return "the receiving group is not here"
        routine.waited_since = guild.clock.seconds
        return orders.wait(HAND_OVER_WAIT_HOURS)
    if not _move(group, receiver, block.item, block.count):
        return f"no {block.item} to hand over"
    return None


def _move(src, dst, item, count):
    """Move up to `count` of `item` (all by default) from the packs of `src` to those of `dst`, shared
    out evenly. Returns how many moved."""
    taken = 0
    for u in src.members:
        want = u.count_of(item) if count is None else min(count - taken, u.count_of(item))
        if want > 0:
            taken += u.remove_named(item, want)
    for i, u in enumerate(dst.members):
        share = taken // len(dst.members) + (i < taken % len(dst.members))
        if share:
            u.give_to_pack(item, share)
    return taken


def _trade(guild, group, block):
    from . import trade, world
    node = world.node(group.node)
    if "shop" not in node.functions:
        return "no shop here"
    counter = trade.Counter(guild, list(group.members), node)
    for name in block.sell:
        held = count_of(group, name)
        counter.sell_named([name])
        if count_of(group, name) == held:
            return counter.notice.rstrip(".")
    wants = {}
    for name, count in block.buy:
        wants[name] = wants.get(name, 0) + count
    if block.food_days is not None:
        short = max(0, group.rations_for(block.food_days) - group.rations)
        wants[block.food] = wants.get(block.food, 0) + short
    before = {name: count_of(group, name) for name in wants}
    counter.buy_named(wants)
    if any(count_of(group, name) - before[name] < count for name, count in wants.items()):
        return counter.notice.rstrip(".")
    return None
