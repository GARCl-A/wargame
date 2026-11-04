"""The garrison engine (Sistema 1, [[gartok-property-two-paths]]): a Group
parked indefinitely on a `"garrison"` order instead of asking for fresh ones,
its daily job (`world.Node.garrison_job`), the `Group.busy`/`locked` split that lets
split/merge see past a standing garrison, and `campaign.advance` excluding it from the tick
engine's chase.
These tests set `garrison_job` on a stand-in node the way `test_road_ambush.py`
forces `world.ROAD_AMBUSH_CHANCE`."""

import random

from gartok import campaign, orders
from gartok.group import Group
from gartok.guild import Guild
from tests.helpers import Unit, standard_unit, world


def _job_node(node_id="market", job="hold"):
    """Temporarily give an existing node a `garrison_job`, restoring it after
    -- same idiom `test_road_ambush.py` uses for `world.ROAD_AMBUSH_CHANCE`."""
    node = world.node(node_id)
    orig = node.garrison_job
    node.garrison_job = job
    return node, orig


# --------------------------------------------------------------------------- #
# Group.busy / Group.locked                                                   #
# --------------------------------------------------------------------------- #

def test_a_garrisoned_group_is_busy_but_not_locked():
    random.seed(1)
    g = Group([Unit("player")], node="city")
    g.order = orders.garrison("hold")
    assert g.busy and not g.locked


def test_a_travelling_group_is_busy_and_locked():
    random.seed(1)
    g = Group([Unit("player")], node="city")
    g.order = orders.travel(g, "market")
    assert g.busy and g.locked


def test_an_idle_group_is_neither():
    g = Group([Unit("player")], node="city")
    assert not g.busy and not g.locked


# --------------------------------------------------------------------------- #
# split/merge see past a standing garrison order                              #
# --------------------------------------------------------------------------- #

def test_a_garrisoned_group_can_still_be_split():
    random.seed(1)
    a, b = Unit("player"), Unit("player")
    g = Group([a, b], node="city")
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("hold")

    new = guild.split_group(g, [a])
    assert a in new.members and b in g.members
    assert g.order.kind == "garrison"          # the order stays on the group that kept it


def test_two_garrisoned_groups_can_still_be_merged():
    random.seed(1)
    a, b = Unit("player"), Unit("player")
    g1 = Group([a], node="city")
    g2 = Group([b], node="city")
    guild = Guild(None, groups=[g1, g2])
    g1.order = orders.garrison("hold")
    g2.order = orders.garrison("hold")

    guild.merge_groups(g1, g2)
    assert g2 not in guild.groups
    assert set(g1.members) == {a, b}


def test_a_travelling_group_still_cannot_be_split_or_merged():
    random.seed(1)
    a, b = Unit("player"), Unit("player")
    g = Group([a, b], node="city")
    other = Group([Unit("player")], node="city")
    guild = Guild(None, groups=[g, other])
    g.order = orders.travel(g, "market")

    try:
        guild.split_group(g, [a])
        assert False, "expected a ValueError"
    except ValueError:
        pass
    try:
        guild.merge_groups(g, other)
        assert False, "expected a ValueError"
    except ValueError:
        pass


# --------------------------------------------------------------------------- #
# daily production                                                            #
# --------------------------------------------------------------------------- #

def test_a_garrison_at_a_plain_node_runs_no_job():
    random.seed(1)
    g = Group([Unit("player")], node="market")     # market.garrison_job is None
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("study")

    guild.pass_time(24)
    assert g.order.kind == "garrison" and g.order.job == "study"


# --------------------------------------------------------------------------- #
# campaign.advance excludes garrison from the tick engine's chase             #
# --------------------------------------------------------------------------- #

def test_advance_is_a_no_op_when_only_a_garrison_is_in_flight():
    random.seed(1)
    g = Group([Unit("player")], node="city")
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("hold")

    result = campaign.advance(guild)
    assert result.events == [] and result.pending == []
    assert g.order.kind == "garrison"           # untouched -- never "resolved"


def test_advance_chases_a_travelling_group_past_a_garrisoned_one():
    random.seed(1)
    traveller = Unit("player")
    garrisoned = Unit("player")
    g1 = Group([traveller], node="city")
    g2 = Group([garrisoned], node="market")
    guild = Guild(None, groups=[g1, g2])
    g1.order = orders.travel(g1, "market")
    g2.order = orders.garrison("hold")

    result = campaign.advance(guild)
    assert g1.node == "market" and g1.order is None      # the travel resolved normally
    assert g2.order.kind == "garrison"                   # the garrison is still just sitting there


def test_a_forced_maintenance_stop_does_not_disturb_a_garrison_order():
    random.seed(1)
    node, orig = _job_node()
    try:
        g = Group([Unit("player")], node="market")
        guild = Guild(None, groups=[g])
        g.order = orders.garrison("hold")

        campaign.advance(guild, dt=1)               # a forced stop (a hunt's hours)
        assert g.order.kind == "garrison"
    finally:
        node.garrison_job = orig


# --------------------------------------------------------------------------- #
# a garrison with days: counted on the clock, a routine's block waits on it    #
# --------------------------------------------------------------------------- #

def _bounded(days, node="market"):
    g = Group([standard_unit()], node=node)
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("hold", days=days)
    return guild, g


def test_a_garrison_with_days_ends_by_itself_and_the_clock_runs_to_it():
    guild, g = _bounded(3)
    assert guild.can_auto_advance
    start = guild.clock.seconds

    campaign.advance(guild)
    assert g.order is None
    assert guild.clock.seconds - start == 3 * 24 * 3600


def test_a_garrison_without_days_is_still_never_counted():
    g = Group([standard_unit()], node="market")
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("hold")
    assert not orders.counts_down(g.order) and not guild.can_auto_advance


def test_a_garrison_with_days_counts_down_in_a_forced_stop_beside_other_orders():
    guild, g = _bounded(2)
    walker = Group([standard_unit()], node="city")
    guild.groups.append(walker)
    walker.order = orders.travel(walker, "market")

    campaign.advance(guild, dt=24)
    assert g.order is not None and 0 < g.order.remaining < g.order.eta
    campaign.advance(guild, dt=24)
    assert g.order is None


def test_rooms_released_in_the_tick_leave_the_bounded_garrison_idle_without_a_crash():
    g = Group([standard_unit()], node="tavern")
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("study", days=3)           # nobody has a target: the upkeep lets the rooms go

    result = campaign.advance(guild)
    assert g.order is None
    assert any("rooms released" in e for e in result.events)


def test_the_days_of_a_garrison_survive_a_save():
    from gartok import persist
    order = orders.garrison("study", days=2)
    back = persist.order_from_dict(persist.order_to_dict(order))
    assert back == order and orders.counts_down(back)
