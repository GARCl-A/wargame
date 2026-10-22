"""Orders: what a Group is currently doing, and how long it takes.

An order is issued once (`travel`/`work`/`rest`/`interactive`) and then ticked down by
`campaign.advance` until it completes. `travel`, `work` and `rest` resolve silently
(auto) -- the group just arrives, gets paid, has rested (and sits down to eat), or is
done with a solo task (`solo.finish`: discharged cured, or a craft rolled). Every other
kind (`market`,
`bank`, `recruit`, `hunt`, `arena`, `tanner`) is interactive: the order only
covers *getting to* the activity, then `campaign.advance` hands the group back
as `TickResult.pending` for the existing screen (`MarketScreen`, `BankScreen`,
`TavernaScreen`, `HuntScreen`, `TannerScreen`, the squad picker into
`BattleScreen`) to actually play it.

`group.order is None` means idle -- eligible for a fresh order, and (unlike an
active order) never blocks `campaign.advance` from jumping straight past it to
the next group's completion.

`"garrison"` is a fourth kind the player DOES issue, but it fits neither
bucket above: nothing resolves it (no `eta`/`remaining` countdown -- it just
sits on the group until cancelled or interrupted), and no screen opens for it
either. `campaign.advance` excludes it from the groups it chases toward
completion for exactly that reason (see its own docstring); its daily payoff
runs instead through `Guild._garrison_upkeep`, alongside food, on every day
crossed. `Group.busy` still reports True for it (a garrisoned group doesn't
need fresh orders, same as any other order in flight) but `Group.locked`
carves it out so `Guild.split_group`/`merge_groups` can still shuffle a
garrison's membership without cancelling it first -- see [[gartok-property-two-paths]].

The forced kinds (the guard, ambushes, raids, seizures) are never issued by the player:
`forced.py` owns them, where each is caught, played and settled, and the extra fields
below (`caught`, `prev_node`, `resume_path`, `pack`, `job`) are theirs.
"""

from dataclasses import dataclass

from . import world

AUTO_KINDS = frozenset({"travel", "work", "rest", "solo"})
INTERACTIVE_KINDS = frozenset({"arena", "market", "bank", "recruit", "prison", "hunt", "tanner",
                               "ledger", "property", "claim", "forge", "carpenter", "apothecary",
                               "library", "ancient_ruins", "stable", "trust", "ox_hunt", "shrine",
                               "serpents_nest", "skirmish", "camp_fight", "ogre_fight", "dragon_lair"})
WORK_KINDS = frozenset({"work", "garrison"})     # a group on these is working where it stands (not travelling)

APPROACH_HOURS = 1          # default approach cost when dispatched from away


@dataclass
class Order:
    kind: str
    eta: float = 0.0         # total hours to completion, fixed at issue (for "done early" notes)
    remaining: float = 0.0   # counts down each tick; resolves at <= 0
    dest: str | None = None  # travel: the CURRENT leg's target node id
    hours: float = 0.0       # work: the nominal shift length (pay/XP basis, not the clock cost)
    path: tuple = ()         # travel: waypoints still to come after `dest`, ending at the final stop
    caught: tuple = ()       # guard: uids of the units the guard just caught (justice.py)
    prev_node: str | None = None   # guard: node to fall back to on "flee"
    resume_path: tuple = ()  # guard/ambush: travel waypoints still owed once resolved (empty = was the final stop)
    pack: tuple = ()         # ambush: the enemy Units rolled at the moment of the catch (encounters.py)
    job: str | None = None   # garrison: which job (economy.GARRISON_JOBS) the group is working
    task: str | None = None  # solo: "hospital" or "craft"
    who: str | None = None   # solo: uid of the member doing the task
    recipe: str | None = None  # solo craft: what is being made
    gather: bool = False     # work: gather items at the node (gather.py) instead of taking the wage
    parley: dict | None = None  # forced: how the talk before the fight ended (`dialogue.Result.to_dict`), once rolled
    owed: float = 0.0        # supply run: hours of this leg still to walk past the ambush the order stops at

    @property
    def interactive(self):
        return self.kind in INTERACTIVE_KINDS

    @property
    def final_dest(self):
        """travel: where the group is ultimately headed, past every waypoint."""
        return self.path[-1] if self.path else self.dest


def travel(group, dest, pace=1.0):
    """Order `group` to the given node id, one map edge at a time -- it visibly
    stops at each waypoint of the cheapest route before continuing, rather than
    jumping straight from here to `dest`. See `campaign.advance`, which chains
    `next_leg` orders together as each one resolves."""
    full_path, distance = world.route(group.node, dest)
    if distance == float("inf"):
        raise ValueError(f"no route from {group.node!r} to {dest!r}")
    if len(full_path) < 2:                      # already there
        return Order("travel", eta=0, remaining=0, dest=dest)
    return next_leg(group.node, full_path[1:], group.speed, pace)


def next_leg(src, remaining_path, speed, pace=1.0):
    """The order for the single next edge (`src` -> `remaining_path[0]`) at the
    group's `speed`, carrying whatever waypoints still follow it.
    `campaign.advance` calls this again each time a leg resolves, so the group
    visibly stops at every waypoint of a multi-hop route instead of jumping
    straight to the end."""
    nxt = remaining_path[0]
    hours = world.hours(next(w for v, w in world.neighbors(src) if v == nxt), speed) * pace
    return Order("travel", eta=hours, remaining=hours, dest=nxt,
                path=tuple(remaining_path[1:]))


def work(guild, group, hours, gather=False, task=None):
    """Order `group` to work `hours` where it stands. Brisk Hands can shrink
    the clock cost below the nominal `hours` pay/XP is banked on -- see
    `Guild.work_speedup`. With `gather` the shift yields the node's drops, not the wage."""
    if gather and not guild.has_licence(group.node):
        raise ValueError(f"no gathering licence for {group.node!r}")
    clock_hours = hours * guild.work_speedup(group.members)
    return Order("work", eta=clock_hours, remaining=clock_hours, hours=hours, gather=gather, task=task)


def put_out(guild, group):
    """Order `group` to fight the fire at the wildfire focus it stands on (`wildfire.put_out`
    rolls when the hours are spent)."""
    from . import wildfire
    hours = wildfire.PUT_OUT_HOURS
    clock_hours = hours * guild.work_speedup(group.members)
    return Order("work", eta=clock_hours, remaining=clock_hours, hours=hours, task="put_out")


def search(task, hours):
    """Order a group to search where it stands for `hours`; `campaign.SEARCHES[task]` rolls
    when they are spent."""
    return Order("work", eta=hours, remaining=hours, hours=hours, task=task)


SUPPLY_START, SUPPLY_TURN ="ledger_hold", "frontier_outpost"


def supply_route():
    """The waypoints of a supply run after Ledger Hold: out to the Frontier Outpost and back."""
    out, _ = world.route(SUPPLY_START, SUPPLY_TURN)
    back, _ = world.route(SUPPLY_TURN, SUPPLY_START)
    return out[1:] + back[1:]


def supply_hours(guild, group):
    """How long `group` walks a whole supply run, there and back, with no ambush."""
    from . import vocations
    distance = world.route(SUPPLY_START, SUPPLY_TURN)[1] + world.route(SUPPLY_TURN, SUPPLY_START)[1]
    return world.hours(distance, group.speed) * vocations.travel_mult(guild, group)


def supply_run(guild, group):
    """Order `group` to walk a Ledger Hold supply caravan to the Frontier Outpost and back
    (`Guild.supply_leg` per leg). Needs Ledger Hold and `SUPPLY_RUN_CARGO_KG` of free cargo."""
    from . import economy
    if group.node != SUPPLY_START:
        raise ValueError(f"supply runs can only be issued at {SUPPLY_START}, got {group.node!r}")
    if group.free_cargo_capacity < economy.SUPPLY_RUN_CARGO_KG:
        raise ValueError(
            f"group needs at least {economy.SUPPLY_RUN_CARGO_KG} kg free cargo capacity, has {group.free_cargo_capacity:.1f}"
        )
    return guild.supply_leg(group, group.node, supply_route())


def rest(hours):
    """Order a group to rest where it stands for `hours`. Unlike a forced clock
    jump it is one group's business: the others keep their own orders, and the
    clock runs through `campaign.advance` like for any order. The group counts
    as resting (`Guild.pass_time`) -- it heals -- instead of busy. `rest.py`
    says how long a stretch is worth, for the "until full" row."""
    return Order("rest", eta=hours, remaining=hours, hours=hours)


def solo(task, who, hours, recipe=None, clock_hours=None):
    """One member (`who`, a uid) busy with `task` for `hours` while the rest of the guild acts:
    they split off into a group of their own when there is a slot, else their whole group waits.
    `solo.finish` pays the task out when the clock runs out. Not a rest, so nothing heals on the
    side, and not cancellable: a hospital stay is paid up front and a craft's materials are in use.
    `hours` is the nominal length (what a craft rolls); `clock_hours` is what the clock runs when
    Brisk Hands shortens it."""
    clock = hours if clock_hours is None else clock_hours
    return Order("solo", eta=clock, remaining=clock, hours=hours, task=task, who=who, recipe=recipe)


def interactive(kind, hours=APPROACH_HOURS):
    """A `market`/`bank`/`recruit`/`hunt`/`arena` order: a small approach cost,
    then `campaign.advance` hands the group back for its real screen."""
    if kind not in INTERACTIVE_KINDS:
        raise ValueError(f"not an interactive kind: {kind!r}")
    return Order(kind, eta=hours, remaining=hours)


def garrison(job):
    """Park a group where it stands, working `job` indefinitely -- see the
    module docstring for why this is neither an `AUTO_KINDS` nor an
    `INTERACTIVE_KINDS` member. Ended only by the player cancelling it (any
    fresh order) or an event forcing the issue (an "eviction" raid);
    `Guild._garrison_upkeep` reads `job` once a day to bank output, if the
    group's node actually offers it (`world.Node.garrison_job`)."""
    return Order("garrison", job=job)


def is_resting(order):
    """A `rest`, or a garrison that only holds the place: standing there doing nothing is
    resting, so the body heals (`Guild.pass_time`)."""
    return order is not None and (order.kind == "rest" or (order.kind == "garrison" and order.job == "hold"))


def idle():
    return Order("idle")
