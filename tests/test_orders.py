"""The tick/orders engine: `campaign.advance` jumps the world to the soonest
order completion across every group, resolves `travel`/`work` silently, and
queues every other kind for the caller to play (see gartok/orders.py)."""

import random

from tests.helpers import Unit
from gartok import campaign, economy, orders, world
from gartok.clock import Clock
from gartok.group import Group
from gartok.guild import Guild


def _guild(*groups, **kw):
    kw.setdefault("clock", Clock(6 * 3600))
    return Guild(None, groups=list(groups), **kw)


def test_advance_is_a_noop_with_nothing_in_flight():
    random.seed(1)
    guild = _guild(Group([Unit("player")], node="city"))
    result = campaign.advance(guild)
    assert result.events == [] and result.pending == [] and not result.wiped


def test_idle_groups_never_block_the_jump():
    random.seed(1)
    idle_g = Group([Unit("player")], node="city")
    idle_g.order = orders.idle()
    mover = Group([Unit("player")], node="city")
    mover.order = orders.travel(mover, "market")
    guild = _guild(idle_g, mover)
    campaign.advance(guild)
    assert mover.node == "market" and idle_g.order.kind == "idle"


def test_advance_jumps_to_the_soonest_completion_and_leaves_the_rest_ticking():
    random.seed(1)
    quick = Group([Unit("player")], node="city")     # city<->market: 1 h
    slow = Group([Unit("player")], node="city")       # city<->arena: 2 h
    quick.order = orders.travel(quick, "market")
    slow.order = orders.travel(slow, "arena")
    guild = _guild(quick, slow)

    result = campaign.advance(guild)                 # dt = 1 h: only `quick` completes
    assert quick.node == "market" and quick.order is None
    assert slow.node == "city" and slow.order is not None
    assert slow.order.remaining == 1

    campaign.advance(guild)                          # dt = 1 h more: `slow` now arrives
    assert slow.node == "arena" and slow.order is None


def test_simultaneous_completions_all_resolve_in_one_advance():
    random.seed(1)
    a = Group([Unit("player")], node="city")
    b = Group([Unit("player")], node="city")
    a.order = orders.travel(a, "market")
    b.order = orders.travel(b, "market")
    guild = _guild(a, b)
    campaign.advance(guild)
    assert a.node == "market" and b.node == "market"
    assert a.order is None and b.order is None


def test_multi_hop_travel_stops_at_each_waypoint_instead_of_jumping_to_the_end():
    """city -> wilds has no direct edge: the cheapest route is city -> road (4h)
    -> wilds (6h). The group should visibly arrive at "road" first, not teleport
    straight to "wilds" the moment the whole trip's hours are up.

    'road' is `unsafe` (an ambush can pause the leg -- see test_justice_integration.py
    for that), which is not what this test is about: the ambush chance is
    zeroed out for its duration so the waypoint stop stays deterministic."""
    random.seed(1)
    orig_chance, world.ROAD_AMBUSH_CHANCE = world.ROAD_AMBUSH_CHANCE, 0.0
    try:
        g = Group([Unit("player")], node="city")
        g.order = orders.travel(g, "wilds")
        assert g.order.dest == "road" and g.order.path == ("wilds",)
        assert g.order.remaining == 4 and g.order.final_dest == "wilds"
        guild = _guild(g)

        campaign.advance(guild)                          # dt = 4 h: the city->road leg
        assert g.node == "road" and g.busy                # stopped here, not idle yet
        assert g.order.dest == "wilds" and g.order.path == ()
        assert g.order.remaining == 6

        campaign.advance(guild)                          # dt = 6 h more: the road->wilds leg
        assert g.node == "wilds" and g.order is None       # now idle at the final stop
    finally:
        world.ROAD_AMBUSH_CHANCE = orig_chance


def test_travel_to_an_unreachable_node_raises():
    random.seed(1)
    g = Group([Unit("player")], node="city")
    try:
        orders.travel(g, "nowhere")             # not a node in the graph -- no route
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_interactive_order_surfaces_in_pending_and_leaves_the_group_idle():
    random.seed(1)
    g = Group([Unit("player")], node="market")
    g.order = orders.interactive("market")
    guild = _guild(g)
    result = campaign.advance(guild)
    assert len(result.pending) == 1
    resolved_group, resolved_order = result.pending[0]
    assert resolved_group is g and resolved_order.kind == "market"
    assert g.order is None                            # idle again -- caller must reissue


def test_work_order_pays_without_double_advancing_the_clock():
    random.seed(1)
    a, b = Unit("player"), Unit("player")
    start_a, start_b = a.gold, b.gold
    g = Group([a, b], node="lumber_yard")
    guild = _guild(g, clock=Clock(0))
    g.order = orders.work(guild, g, 8)
    result = campaign.advance(guild)
    assert guild.clock.seconds == 8 * 3600            # advanced exactly once, not twice
    pay = economy.lumber_pay(8)
    assert a.gold == start_a + pay and b.gold == start_b + pay
    assert a.work_hours == 8 and b.work_hours == 8
    assert any("Lumber yard" in e for e in result.events)
    assert g.order is None


def test_group_busy_treats_none_and_explicit_idle_the_same():
    random.seed(1)
    g = Group([Unit("player")], node="city")
    assert not g.busy                                  # order is None
    g.order = orders.idle()
    assert not g.busy                                  # explicit idle order
    g.order = orders.travel(g, "market")
    assert g.busy


def test_forced_dt_keeps_an_in_flight_orders_eta_synced_with_the_clock():
    """The map's MAINTENANCE stop forces a short dt instead of jumping to the
    soonest completion -- an order that ISN'T due yet must still lose exactly
    that many hours, so it can't drift out of sync with the shared clock."""
    random.seed(1)
    g = Group([Unit("player")], node="city")
    g.order = orders.travel(g, "arena")                # city<->arena: 2 h
    guild = _guild(g)
    result = campaign.advance(guild, dt=1)              # forced 1 h stop, not the ETA
    assert not result.wiped and not result.pending
    assert g.node == "city" and g.order is not None and g.order.remaining == 1

    campaign.advance(guild, dt=1)                       # the remaining hour completes it
    assert g.node == "arena" and g.order is None


def test_forced_dt_also_runs_eat_now_pass_thats_what_makes_it_maintenance():
    """A forced dt (the map's MAINTENANCE button) must feed anyone still
    hungry right now, not just advance the clock -- otherwise MAINTENANCE is
    just a short ADVANCE with no reason to exist."""
    random.seed(1)
    hungry = Unit("player")
    hungry._base_inventory = ["Meat"]
    hungry.unfed_days = 2                    # hungry, but has food on hand
    g = Group([hungry], node="city")
    guild = _guild(g)
    result = campaign.advance(guild, dt=1)   # forced -- no order in flight at all
    assert hungry.unfed_days == 0 and hungry._base_inventory == []
    assert any("Stopped to eat" in e for e in result.events)


def test_an_unforced_advance_does_not_run_eat_now_pass():
    random.seed(1)
    hungry = Unit("player")
    hungry._base_inventory = ["Meat"]
    hungry.unfed_days = 2
    g = Group([hungry], node="city")
    g.order = orders.travel(g, "market")     # 1 h -- something to jump to
    guild = _guild(g)
    campaign.advance(guild)                  # dt=None: the ADVANCE button
    assert hungry.unfed_days == 2 and hungry._base_inventory == ["Meat"]


def test_forced_dt_still_resolves_an_order_that_completes_within_it():
    random.seed(1)
    g = Group([Unit("player")], node="city")
    g.order = orders.travel(g, "market")                # 1 h -- shorter than the forced stop
    guild = _guild(g)
    campaign.advance(guild, dt=3)
    assert g.node == "market" and g.order is None


def test_a_tick_that_starves_the_guild_out_reports_wiped_and_resolves_nothing():
    random.seed(1)
    doomed = Unit("player")
    doomed._base_inventory = []
    doomed.share_food = False
    g = Group([doomed], node="lumber_yard")
    guild = _guild(g, clock=Clock(6 * 3600))
    g.order = orders.work(guild, g, 24 * 6)            # 6 days -- starves inside one tick
    result = campaign.advance(guild)
    assert result.wiped and guild.empty
    assert not result.pending                          # never got to resolving the order
