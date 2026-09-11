"""Group membership: every unit is in exactly one group; add/remove keep that
true across the guild. See gartok/group.py + the Guild.roster/node shims."""

import random

from tests.helpers import Unit
from gartok.group import Group
from gartok.guild import Guild


def test_group_of_finds_the_right_group():
    random.seed(1)
    a, b, c = Unit("player"), Unit("player"), Unit("player")
    g1, g2 = Group([a, b], node="city"), Group([c], node="wilds")
    guild = Guild(None, groups=[g1, g2])
    assert guild.group_of(a) is g1 and guild.group_of(c) is g2
    assert guild.group_of(Unit("player")) is None


def test_add_member_joins_the_given_group_only():
    random.seed(1)
    a = Unit("player")
    g1, g2 = Group([a], node="city"), Group([], node="wilds")
    guild = Guild(None, groups=[g1, g2])
    newbie = Unit("player")
    guild.add_member(newbie, g2)
    assert newbie in g2.members and newbie not in g1.members
    assert guild.group_of(newbie) is g2


def test_remove_members_drops_from_whichever_group_holds_them():
    random.seed(1)
    a, b, c = Unit("player"), Unit("player"), Unit("player")
    g1, g2 = Group([a, b], node="city"), Group([c], node="wilds")
    guild = Guild(None, groups=[g1, g2])
    guild.remove_members([b, c])
    assert g1.members == [a] and g2.members == []
    assert guild.roster == [a]


def test_roster_is_flattened_across_every_group():
    random.seed(1)
    a, b = Unit("player"), Unit("player")
    guild = Guild(None, groups=[Group([a], node="city"), Group([b], node="wilds")])
    assert guild.roster == [a, b]
    assert guild.group_of(a).node == "city" and guild.group_of(b).node == "wilds"


def test_split_group_peels_a_subset_off_at_the_same_node():
    random.seed(1)
    a, b, c = Unit("player"), Unit("player"), Unit("player")
    home = Group([a, b, c], node="city")
    guild = Guild(None, groups=[home])
    away = guild.split_group(home, [b])
    assert home.members == [a, c] and away.members == [b]
    assert away.node == "city" and away is not home
    assert guild.group_of(b) is away and len(guild.groups) == 2


def test_split_group_refuses_an_empty_or_full_subset():
    random.seed(1)
    a, b = Unit("player"), Unit("player")
    home = Group([a, b], node="city")
    guild = Guild(None, groups=[home])
    for subset in ([], [a, b]):
        try:
            guild.split_group(home, subset)
            assert False, "expected ValueError"
        except ValueError:
            pass


def test_split_group_refuses_a_group_with_an_order_in_flight():
    from gartok import orders
    random.seed(1)
    a, b = Unit("player"), Unit("player")
    home = Group([a, b], node="city")
    home.order = orders.travel(home, "market")
    guild = Guild(None, groups=[home])
    try:
        guild.split_group(home, [a])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_merge_groups_folds_b_into_a_at_the_same_node():
    random.seed(1)
    a_unit, b_unit = Unit("player"), Unit("player")
    a, b = Group([a_unit], node="city"), Group([b_unit], node="city")
    guild = Guild(None, groups=[a, b])
    merged = guild.merge_groups(a, b)
    assert merged is a and set(a.members) == {a_unit, b_unit}
    assert b not in guild.groups and len(guild.groups) == 1


def test_merge_groups_refuses_different_nodes_or_an_order_in_flight():
    from gartok import orders
    random.seed(1)
    a, b = Group([Unit("player")], node="city"), Group([Unit("player")], node="wilds")
    guild = Guild(None, groups=[a, b])
    try:
        guild.merge_groups(a, b)
        assert False, "expected ValueError"
    except ValueError:
        pass

    b.node = "city"
    b.order = orders.travel(b, "market")   # any real order in flight
    try:
        guild.merge_groups(a, b)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_roster_assignment_shim_requires_exactly_one_group():
    random.seed(1)
    solo = Guild([Unit("player")], node="city")
    solo.roster = [Unit("player"), Unit("player")]     # single-group shim: fine
    assert len(solo.roster) == 2

    multi = Guild(None, groups=[Group([Unit("player")], node="city"),
                                Group([Unit("player")], node="wilds")])
    try:
        multi.roster = [Unit("player")]
        assert False, "expected NotImplementedError"
    except NotImplementedError:
        pass
