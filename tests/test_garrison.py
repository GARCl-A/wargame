"""The garrison engine (Sistema 1, [[gartok-property-two-paths]]): a Group
parked indefinitely on a `"garrison"` order instead of asking for fresh ones,
its daily job output (`economy.GARRISON_JOBS`, `world.Node.garrison_job`),
the `Group.busy`/`locked` split that lets split/merge see past a standing
garrison, and `campaign.advance` excluding it from the tick engine's chase.
No real node offers a job yet -- these tests set `garrison_job` on a stand-in
node the way `test_road_ambush.py` forces `world.ROAD_AMBUSH_CHANCE`, rather
than waiting on Sistema 3's Wilds territory node to exist."""

import random

from tests.helpers import economy, Unit, world
from gartok import campaign, orders
from gartok.group import Group
from gartok.guild import Guild


def _job_node(node_id="market", job="lumber"):
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
    g.order = orders.garrison("lumber")
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
    g.order = orders.garrison("lumber")

    new = guild.split_group(g, [a])
    assert a in new.members and b in g.members
    assert g.order.kind == "garrison"          # the order stays on the group that kept it


def test_two_garrisoned_groups_can_still_be_merged():
    random.seed(1)
    a, b = Unit("player"), Unit("player")
    g1 = Group([a], node="city")
    g2 = Group([b], node="city")
    guild = Guild(None, groups=[g1, g2])
    g1.order = orders.garrison("lumber")
    g2.order = orders.garrison("lumber")

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

def test_a_garrison_at_a_job_site_banks_output_each_day():
    random.seed(1)
    node, orig = _job_node()
    try:
        a, b = Unit("player"), Unit("player")
        g = Group([a, b], node="market")
        guild = Guild(None, groups=[g])
        g.order = orders.garrison("lumber")

        guild.pass_time(24)
        assert guild.garrison_stock_at("market") == ["Lumber"] * (
            2 * economy.GARRISON_YIELD_PER_MEMBER_PER_DAY)
        guild.pass_time(24)
        assert guild.garrison_stock_at("market") == ["Lumber"] * (
            4 * economy.GARRISON_YIELD_PER_MEMBER_PER_DAY)
    finally:
        node.garrison_job = orig


def test_a_garrison_at_a_plain_node_produces_nothing():
    random.seed(1)
    g = Group([Unit("player")], node="market")     # market.garrison_job is None
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("lumber")

    guild.pass_time(24)
    assert guild.garrison_stock_at("market") == []


def test_the_wrong_job_at_the_right_node_produces_nothing():
    random.seed(1)
    node, orig = _job_node(job="lumber")
    try:
        g = Group([Unit("player")], node="market")
        guild = Guild(None, groups=[g])
        g.order = orders.garrison("something_else")

        guild.pass_time(24)
        assert guild.garrison_stock_at("market") == []
    finally:
        node.garrison_job = orig


def test_a_starved_out_garrison_stops_producing():
    """Regression risk: `_garrison_upkeep` runs after `remove_members` has
    already pruned an empty group for the day -- must not crash on a group
    that no longer exists."""
    random.seed(1)
    node, orig = _job_node()
    try:
        lone = Unit("player")
        lone._base_inventory = []                  # no food at all
        g = Group([lone], node="market")
        guild = Guild(None, groups=[g])
        g.order = orders.garrison("lumber")

        events = guild.pass_time(24 * (economy.CITY_PROPERTY_DEBT_GRACE_DAYS))
        assert guild.empty or guild.garrison_stock_at("market") == []
    finally:
        node.garrison_job = orig


# --------------------------------------------------------------------------- #
# campaign.advance excludes garrison from the tick engine's chase             #
# --------------------------------------------------------------------------- #

def test_advance_is_a_no_op_when_only_a_garrison_is_in_flight():
    random.seed(1)
    g = Group([Unit("player")], node="city")
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("lumber")

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
    g2.order = orders.garrison("lumber")

    result = campaign.advance(guild)
    assert g1.node == "market" and g1.order is None      # the travel resolved normally
    assert g2.order.kind == "garrison"                   # the garrison is still just sitting there


def test_a_forced_maintenance_stop_does_not_disturb_a_garrison_order():
    random.seed(1)
    node, orig = _job_node()
    try:
        g = Group([Unit("player")], node="market")
        guild = Guild(None, groups=[g])
        g.order = orders.garrison("lumber")

        campaign.advance(guild, dt=1)               # the MAINTENANCE button's forced 1h stop
        assert g.order.kind == "garrison"
    finally:
        node.garrison_job = orig


# --------------------------------------------------------------------------- #
# save round trip (persist.py)                                                #
# --------------------------------------------------------------------------- #

def test_garrison_stock_survives_a_save_round_trip():
    import os

    from gartok import persist
    slot = persist.NUM_SLOTS - 1
    if os.path.exists(persist.slot_path(slot)):
        return
    random.seed(1)
    guild = Guild([Unit("player")])
    guild.garrison_stock = {"market": ["Lumber", "Lumber"]}
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot)
        assert back.garrison_stock_at("market") == ["Lumber", "Lumber"]
    finally:
        persist.delete_slot(slot)


def test_city_property_state_survives_a_save_round_trip():
    """Regression: Sistema 2 shipped without wiring its new guild fields into
    `persist.py` at all -- a bought/repossessed/squatted property silently
    reset on every save/load. Fixed alongside Sistema 1."""
    import os

    from gartok import persist
    slot = persist.NUM_SLOTS - 1
    if os.path.exists(persist.slot_path(slot)):
        return
    random.seed(1)
    p = Unit("player")
    guild = Guild([p])
    guild.buy_city_property()
    guild.property_city_items = ["Rope"]
    guild.property_city_missed_payments = 2
    guild.bankers_debt = 15
    guild.property_city_debt_since = guild.clock.day
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot)
        assert back.property_city_unlocked and back.property_city_items == ["Rope"]
        assert back.property_city_missed_payments == 2
        assert back.property_city_tax_due_day == guild.property_city_tax_due_day
        assert back.bankers_debt == 15
        assert back.property_city_debt_since == guild.property_city_debt_since
    finally:
        persist.delete_slot(slot)


def test_a_squatting_property_survives_a_save_round_trip():
    import os

    from gartok import persist
    slot = persist.NUM_SLOTS - 1
    if os.path.exists(persist.slot_path(slot)):
        return
    random.seed(1)
    guild = Guild([Unit("player")])
    guild.buy_city_property()
    guild.squat_city_property()
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot)
        assert back.property_city_unlocked and back.property_city_squatting
        assert back.property_city_tax_due_day is None
    finally:
        persist.delete_slot(slot)
