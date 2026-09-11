"""Orders: what a Group is currently doing, and how long it takes.

An order is issued once (`travel`/`work`/`interactive`) and then ticked down by
`campaign.advance` until it completes. `travel` and `work` resolve silently
(auto) -- the group just arrives, or gets paid. Every other kind (`market`,
`bank`, `recruit`, `hunt`, `arena`) is interactive: the order only covers
*getting to* the activity, then `campaign.advance` hands the group back as
`TickResult.pending` for the existing screen (`MarketScreen`, `BankScreen`,
`TavernaScreen`, `HuntScreen`, the squad picker into `BattleScreen`) to actually
play it.

`group.order is None` means idle -- eligible for a fresh order, and (unlike an
active order) never blocks `campaign.advance` from jumping straight past it to
the next group's completion.
"""

from dataclasses import dataclass

from . import world

AUTO_KINDS = frozenset({"travel", "work"})
INTERACTIVE_KINDS = frozenset({"arena", "market", "bank", "recruit", "hunt"})
KINDS = AUTO_KINDS | INTERACTIVE_KINDS | {"idle"}

APPROACH_HOURS = 1          # a small "walk in and get started" cost for the interactive kinds


@dataclass
class Order:
    kind: str
    eta: float = 0.0         # total hours to completion, fixed at issue (for "done early" notes)
    remaining: float = 0.0   # counts down each tick; resolves at <= 0
    dest: str | None = None  # travel: the target node id
    hours: float = 0.0       # work: the nominal shift length (pay/XP basis, not the clock cost)

    @property
    def interactive(self):
        return self.kind in INTERACTIVE_KINDS


def travel(group, dest):
    """Order `group` to the given node id. ETA = the cheapest route's hours."""
    _, hours = world.route(group.node, dest)
    if hours == float("inf"):
        raise ValueError(f"no route from {group.node!r} to {dest!r}")
    return Order("travel", eta=hours, remaining=hours, dest=dest)


def work(guild, group, hours):
    """Order `group` to work `hours` where it stands. Brisk Hands can shrink
    the clock cost below the nominal `hours` pay/XP is banked on -- see
    `Guild.work_speedup`."""
    clock_hours = hours * guild.work_speedup(group.members)
    return Order("work", eta=clock_hours, remaining=clock_hours, hours=hours)


def interactive(kind, hours=APPROACH_HOURS):
    """A `market`/`bank`/`recruit`/`hunt`/`arena` order: a small approach cost,
    then `campaign.advance` hands the group back for its real screen."""
    if kind not in INTERACTIVE_KINDS:
        raise ValueError(f"not an interactive kind: {kind!r}")
    return Order(kind, eta=hours, remaining=hours)


def idle():
    return Order("idle")
