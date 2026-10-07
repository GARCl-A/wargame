"""Fame -> group slots, and the daily cohesion test on an overextended group.

See RULES.md's "Fame and group slots" and gartok/cohesion.py.
"""

import os
import random

import pytest

from gartok import cohesion, orders, persist, recruit
from gartok.group import BASE_CAPACITY, BASE_SLOTS, FAME_PER_SLOT, Group
from gartok.guild import Guild
from tests.helpers import Unit

ALWAYS_FAILS = lambda: 20      # a roll at or above any Mental Defense
NEVER_FAILS = lambda: 1      


def _unit(seed, wis=10, alignment="Neutral and Neutral"):
    random.seed(seed)
    u = Unit("player")
    u.set_base_attribute("wisdom", wis)
    u.set_base_attribute("charisma", 10)    # modifier 0
    u._racial_override = 0                  # capacity is exactly BASE_CAPACITY
    u.alignment = alignment
    return u


def _crowded(extra=2, wis=None):
    """A guild of one group `extra` members past its capacity. Index 0 leads;
    `wis` (per member, after the leader) pins who is weakest."""
    n = BASE_CAPACITY + extra
    wis = wis or [10] * (n - 1)
    members = [_unit(1, wis=14)] + [_unit(2 + i, wis=w) for i, w in enumerate(wis)]
    guild = Guild(None, groups=[Group(members, node="city", leader=members[0])])
    return guild, guild.groups[0], members


def _fame(guild, slots_extra):
    guild.reputation["arena"] = slots_extra * FAME_PER_SLOT


# --------------------------------------------------------------------------- #
# fame -> slots
# --------------------------------------------------------------------------- #

def test_slots_come_from_the_sum_of_all_reputation():
    guild = Guild([_unit(1)], node="city")
    assert guild.group_slots == BASE_SLOTS
    guild.reputation = {"arena": 2, "bankers": 1}
    assert guild.fame == 3 and guild.group_slots == BASE_SLOTS + 1
    guild.reputation = {"arena": 2, "bankers": 2, "library": 2}
    assert guild.group_slots == BASE_SLOTS + 2
    assert guild.fame_to_next_slot == FAME_PER_SLOT


def test_split_needs_a_free_slot():
    members = [_unit(i) for i in range(1, 6)]
    guild = Guild(members, node="city")
    guild.split_group(guild.groups[0], [members[1]])       # 2nd group: fits the base slots
    assert guild.free_slots == 0
    with pytest.raises(ValueError, match="slot"):
        guild.split_group(guild.groups[0], [members[2]])
    _fame(guild, 1)
    guild.split_group(guild.groups[0], [members[2]])
    assert len(guild.groups) == 3


def test_a_merge_frees_the_slot_again():
    a, b, c = _unit(1), _unit(2), _unit(3)
    guild = Guild([a, b, c], node="city")
    away = guild.split_group(guild.groups[0], [c])
    assert guild.free_slots == 0
    guild.merge_groups(guild.groups[0], away)
    assert guild.free_slots == 1


# --------------------------------------------------------------------------- #
# the daily test
# --------------------------------------------------------------------------- #

def test_a_group_within_capacity_is_never_tested():
    guild, _group, _ = _crowded(extra=0)
    assert cohesion.daily(guild, ALWAYS_FAILS) == []
    assert len(guild.groups) == 1


def test_the_weakest_member_breaks_away_when_a_slot_is_free():
    guild, group, m = _crowded(extra=2, wis=[12, 6, 12, 12])
    events = cohesion.daily(guild, ALWAYS_FAILS)
    assert len(guild.groups) == 2
    assert guild.group_of(m[2]) is not group          # wis 6 = lowest Mental Defense
    assert len(guild.group_of(m[2]).members) == 1
    assert m[2].name in events[0]


def test_a_roll_under_their_defense_changes_nothing():
    guild, _group, _ = _crowded(extra=2)
    assert cohesion.daily(guild, NEVER_FAILS) == []
    assert len(guild.groups) == 1 and not guild.leaving


def test_the_roll_is_against_the_weakest_mental_defense():
    guild, _group, m = _crowded(extra=2, wis=[12, 6, 12, 12])
    md = m[2].mental_defense
    assert cohesion.daily(guild, lambda: md - 1) == []         # just misses
    assert cohesion.daily(guild, lambda: md)                   # meets it: they walk


def test_leaders_are_exempt():
    guild, group, m = _crowded(extra=2, wis=[2, 2, 2, 2])
    group.set_leader(m[1])
    guild.leader = m[2]
    assert cohesion.weakest(guild, group) not in (m[1], m[2])


def test_a_group_with_nobody_testable_is_skipped():
    a, b = _unit(1), _unit(2)
    a.set_base_attribute("charisma", 6)                   # modifier -2: capacity 1, the second member overextends
    guild = Guild(None, groups=[Group([a, b], node="city", leader=a)], leader=b)
    assert guild.groups[0].overextension > 0
    assert cohesion.daily(guild, ALWAYS_FAILS) == []


def test_a_group_on_an_order_waits_until_it_can_split():
    guild, group, _ = _crowded()
    group.order = orders.travel(group, "market")
    assert cohesion.daily(guild, ALWAYS_FAILS) == []
    assert len(guild.groups) == 1


# --------------------------------------------------------------------------- #
# no slot: notice, then the door
# --------------------------------------------------------------------------- #

def _full_guild(**kw):
    """An overextended group and one more, so every base slot is taken."""
    guild, group, members = _crowded(**kw)
    other = _unit(40)
    guild.groups.append(Group([other], node="city"))
    guild._sync_leadership()
    assert guild.free_slots == 0
    return guild, group, members


def test_no_free_slot_gives_a_seven_day_notice():
    guild, group, m = _full_guild(extra=2, wis=[12, 6, 12, 12])
    events = cohesion.daily(guild, ALWAYS_FAILS)
    assert guild.leaving == {m[2].uid: guild.clock.day + cohesion.NOTICE_DAYS}
    assert cohesion.NOTICE_DAYS == 7
    assert guild.group_of(m[2]) is group                  # still in the group meanwhile
    assert "notice" in events[0]


def test_a_group_with_a_notice_standing_is_not_tested_again():
    guild, _group, _ = _full_guild()
    cohesion.daily(guild, ALWAYS_FAILS)
    assert cohesion.daily(guild, ALWAYS_FAILS) == []
    assert len(guild.leaving) == 1


def test_a_slot_opening_turns_the_notice_into_a_split():
    guild, _group, _m = _full_guild(wis=[12, 6, 12, 12])
    cohesion.daily(guild, ALWAYS_FAILS)
    uid = next(iter(guild.leaving))
    _fame(guild, 1)
    events = cohesion.daily(guild, NEVER_FAILS)
    assert not guild.leaving
    assert len(guild.groups) == 3
    assert any("room of their own" in e for e in events)
    assert next(u for u in guild.roster if u.uid == uid) in guild.groups[-1].members


def test_the_notice_is_dropped_when_the_group_is_no_longer_overextended():
    guild, group, _m = _full_guild(extra=1)
    cohesion.daily(guild, ALWAYS_FAILS)
    leaver = next(u for u in guild.roster if u.uid in guild.leaving)
    other = next(g for g in guild.groups if g is not group)
    other.members.append(group.members.pop(group.members.index(next(
        u for u in group.members if u is not leaver and u is not group.leader))))
    guild._sync_leadership()
    events = cohesion.daily(guild, NEVER_FAILS)
    assert not guild.leaving and any("drops the notice" in e for e in events)
    assert leaver in guild.roster


def test_a_notice_is_dropped_if_the_member_is_made_leader():
    guild, group, _m = _full_guild()
    cohesion.daily(guild, ALWAYS_FAILS)
    leaver = next(u for u in guild.roster if u.uid in guild.leaving)
    group.set_leader(leaver)
    cohesion.daily(guild, NEVER_FAILS)
    assert not guild.leaving and leaver in guild.roster


def _lapse(guild):
    guild.clock.advance_hours(24 * cohesion.NOTICE_DAYS)
    return cohesion.daily(guild, NEVER_FAILS)


def _loaded_leaver(alignment):
    guild, group, m = _full_guild(extra=2, wis=[12, 6, 12, 12])
    leaver = m[2]
    leaver.alignment = alignment
    leaver.money = 100
    leaver.give_to_pack("Rope")
    leaver.equipped_weapon = "Dagger"
    cohesion.daily(guild, ALWAYS_FAILS)
    assert leaver.uid in guild.leaving
    leader_gold = group.leader.money
    leader_rope = sum(u.count_of("Rope") for u in group.members if u is not leaver)
    return guild, group, leaver, leader_gold, leader_rope


def test_when_the_notice_lapses_they_leave_the_guild():
    guild, _group, leaver, *_ = _loaded_leaver("Lawful and Good")
    events = _lapse(guild)
    assert leaver not in guild.roster and not guild.leaving
    assert any("leaves the guild" in e for e in events)


def test_a_lawful_leaver_takes_only_what_they_wear_and_wield():
    guild, group, leaver, gold, rope = _loaded_leaver("Lawful and Good")
    _lapse(guild)
    assert group.leader.money == gold + 100
    assert sum(u.count_of("Rope") for u in group.members) == rope + 1   # spread by distribute_load
    assert leaver.equipped_weapon == "Dagger"            # went out the door with them


def test_a_neutral_leaver_keeps_the_pack_but_leaves_the_gold():
    guild, group, leaver, gold, rope = _loaded_leaver("Neutral and Evil")
    _lapse(guild)
    assert group.leader.money == gold + 100
    assert sum(u.count_of("Rope") for u in group.members) == rope
    assert leaver.count_of("Rope") == 1


def test_a_chaotic_leaver_takes_everything():
    guild, group, leaver, gold, rope = _loaded_leaver("Chaotic and Neutral")
    _lapse(guild)
    assert group.leader.money == gold
    assert sum(u.count_of("Rope") for u in group.members) == rope
    assert leaver.money == 100


def test_a_neutral_leaver_leaves_gold_coins_as_gold():
    guild, group, leaver, *_ = _loaded_leaver("Neutral and Evil")
    leaver.give_to_pack("Gold Coin", 2)
    _lapse(guild)
    assert group.leader.count_of("Gold Coin") == 2


@pytest.mark.parametrize("name,law", [("Lawful and Evil", "Lawful"), ("Neutral and Good", "Neutral"),
                                      ("Chaotic and Good", "Chaotic"), (None, "Neutral")])
def test_lawfulness_reads_the_law_axis(name, law):
    assert cohesion.lawfulness(name) == law


# --------------------------------------------------------------------------- #
# wiring
# --------------------------------------------------------------------------- #

def test_the_daily_upkeep_runs_the_cohesion_test(monkeypatch):
    guild, _group, _ = _crowded()
    calls = []
    monkeypatch.setattr(cohesion, "daily", lambda g, *a: calls.append(g) or ["x"])
    events, _ = guild._daily_upkeep()
    assert calls == [guild] and "x" in events


def test_notices_survive_a_save_round_trip():
    slot = "testworld"
    if os.path.exists(persist.save_path(slot)):
        return                                        # never clobber a real save
    guild, _group, m = _full_guild(wis=[12, 6, 12, 12])
    cohesion.daily(guild, ALWAYS_FAILS)
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot)
        assert back.leaving == {m[2].uid: guild.leaving[m[2].uid]}
    finally:
        persist.delete_world(slot)


def test_an_old_save_without_notices_loads_clean():
    assert Guild([_unit(1)], node="city").leaving == {}


def test_recruiting_into_a_full_group_with_no_slot_is_allowed_with_a_warning():
    guild, group, m = _full_guild(extra=0)
    assert len(group.members) == group.capacity and guild.free_slots == 0
    cand = _unit(1)                                   # same seed as the sponsor: shares a language
    assert recruit.pitch_block_reason(guild, [m[0]], cand) is None
    assert "group is full" in recruit.overflow_warning(guild, m[0])
    _fame(guild, 1)
    assert recruit.overflow_warning(guild, m[0]) is None
