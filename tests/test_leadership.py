"""Leadership: the guild's one "who am I" title, and each group's own leader.

See RULES.md's "Leadership" section and gartok/group.py / gartok/guild.py.
"""

import random

from tests.helpers import Unit, _unit
from gartok.group import BASE_CAPACITY, Group
from gartok.guild import Guild


def _cha(seed, cha):
    """A deterministic unit with a pinned Charisma modifier (rest random)."""
    u = _unit(seed=seed)
    u.mod_charisma = cha
    return u


def test_group_defaults_its_leader_to_the_highest_charisma_member():
    weak, strong = _cha(1, 0), _cha(2, 3)
    g = Group([weak, strong], node="city")
    assert g.leader is strong


def test_set_leader_requires_membership():
    a, b = _cha(1, 0), _cha(2, 0)
    g = Group([a], node="city")
    try:
        g.set_leader(b)
        assert False, "expected ValueError"
    except ValueError:
        pass
    g.set_leader(a)                          # a real member: fine, free, no restriction
    assert g.leader is a


def test_group_leader_auto_succeeds_when_the_leader_stops_being_a_member():
    low, high = _cha(1, -1), _cha(2, 2)
    g = Group([low, high], node="city", leader=high)
    g.members.remove(high)                   # simulate death/removal without going through Guild
    g.ensure_leader()
    assert g.leader is low


def test_group_capacity_and_overextension():
    leader = _cha(1, 2)                      # +2 CHA -> capacity BASE_CAPACITY + 2
    capacity = BASE_CAPACITY + 2
    mates = [_cha(i, 0) for i in range(2, 2 + capacity)]   # + the leader = one past capacity
    g = Group([leader] + mates, node="city", leader=leader)
    assert g.capacity == capacity
    assert len(g.members) == capacity + 1
    assert g.overextension == 1


def test_overextension_docks_mental_defense_for_every_member():
    random.seed(4)
    leader = _cha(1, 0)
    roster = [leader] + [_unit(seed=i) for i in range(2, 2 + BASE_CAPACITY + 3)]
    for u in roster:
        u.mod_charisma = 0 if u is leader else u.mod_charisma
    baseline = {u.uid: u.mental_defense_base + u.group_overextension for u in roster}
    guild = Guild(None, groups=[Group(roster, node="city", leader=leader)])
    over = guild.groups[0].overextension
    assert over > 0
    for u in roster:
        assert u.group_overextension == over
        assert u.mental_defense == baseline[u.uid] - over


def test_fresh_guild_leader_also_leads_the_starting_group():
    a, b, c = Unit("player"), Unit("player"), Unit("player")
    guild = Guild([a, b, c], node="city", leader=b)
    assert guild.leader is b
    assert guild.groups[0].leader is b


def test_guild_leader_manual_swap_costs_the_one_free_change():
    a, b, c = Unit("player"), Unit("player"), Unit("player")
    guild = Guild([a, b, c], node="city", leader=a)
    guild.set_leader(b)
    assert guild.leader is b and guild.leader_swaps_used == 1
    try:
        guild.set_leader(c)
        assert False, "expected ValueError: no free swap left"
    except ValueError:
        pass
    assert guild.leader is b                 # the blocked attempt changed nothing


def test_setting_the_already_current_guild_leader_is_a_free_no_op():
    a, b = Unit("player"), Unit("player")
    guild = Guild([a, b], node="city", leader=a)
    guild.set_leader(a)                      # already the leader: not a "change"
    assert guild.leader_swaps_used == 0


def test_guild_leader_auto_succeeds_on_death_without_spending_the_free_swap():
    a, b = Unit("player"), Unit("player")
    guild = Guild([a, b], node="city", leader=a)
    guild.remove_members([a])
    assert guild.leader is b
    assert guild.leader_swaps_used == 0      # death isn't a "deliberate" swap -- the free swap survives


def test_group_leader_swaps_are_always_free():
    a, b = Unit("player"), Unit("player")
    guild = Guild([a, b], node="city", leader=a)
    g = guild.groups[0]
    g.set_leader(b)
    g.set_leader(a)
    g.set_leader(b)
    assert g.leader is b
    assert guild.leader_swaps_used == 0      # a group leader swap never touches the guild title


def test_split_group_gives_the_new_group_a_leader_of_its_own():
    a, b, c = _cha(1, -1), _cha(2, 0), _cha(3, 2)
    guild = Guild([a, b, c], node="city", leader=a)
    home = guild.groups[0]
    away = guild.split_group(home, [c])
    assert away.leader is c                  # only member peeled off: trivially its leader
    assert home.leader in (a, b)             # original group still has a valid leader
