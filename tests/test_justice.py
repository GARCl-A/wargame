"""Crime, jurisdiction and the guard (justice.py): the catch test, jail/release,
and the patrol a fight against the guard scales up."""

import random

from tests.helpers import fixed_d20, Unit
from gartok import justice
from gartok.group import Group
from gartok.guild import Guild


def test_a_clean_record_never_gets_caught():
    u = Unit("player")
    u.crime = 0
    with fixed_d20(20):                     # the best possible roll
        assert not justice.guard_test(u)


def test_the_guard_test_climbs_a_flat_line_with_crime():
    u = Unit("player")
    u.crime = 1
    with fixed_d20(10):                     # 10 + 1 == GUARD_CHECK_MIN
        assert justice.guard_test(u)
    with fixed_d20(9):                      # one short
        assert not justice.guard_test(u)


def test_catch_only_tests_members_with_crime():
    clean, dirty = Unit("player"), Unit("player")
    clean.crime, dirty.crime = 0, 5
    group = Group([clean, dirty], node="market")
    with fixed_d20(20):
        assert justice.catch(group) == [dirty]


def test_prison_days_scale_with_crime_and_jail_moves_the_unit_off_the_group():
    random.seed(1)
    culprit, mate = Unit("player"), Unit("player")
    culprit.crime = 3
    group = Group([culprit, mate], node="city")
    guild = Guild(None, groups=[group])

    days = justice.jail(guild, culprit)

    assert days == 3 * justice.PRISON_DAYS_PER_CRIME
    assert culprit.crime == 0
    assert culprit not in group.members and mate in group.members
    assert culprit not in guild.roster                 # off the roster, same as taverna_pool
    assert (culprit, guild.clock.day + days) in guild.jailed


def test_release_due_frees_into_a_group_at_the_city_only_once_served():
    random.seed(1)
    culprit = Unit("player")
    culprit.crime = 2
    group = Group([culprit], node="city")
    guild = Guild(None, groups=[group])
    days = justice.jail(guild, culprit)

    assert justice.release_due(guild) == []             # not due yet
    guild.clock.advance_hours(24 * (days - 1))
    assert justice.release_due(guild) == []

    guild.clock.advance_hours(24)
    released = justice.release_due(guild)
    assert released == [culprit]
    assert guild.jailed == []
    assert culprit in guild.roster
    assert guild.group_of(culprit).node == "city"


def test_release_due_makes_a_fresh_group_if_none_stands_at_the_city():
    random.seed(1)
    culprit = Unit("player")
    culprit.crime = 1
    group = Group([culprit], node="road")     # nobody's at the city right now
    guild = Guild(None, groups=[group])
    justice.jail(guild, culprit)
    assert guild.groups == []                 # the lone group emptied out and was pruned

    guild.clock.advance_hours(24 * justice.prison_days(1))
    released = justice.release_due(guild)

    assert released == [culprit]
    assert any(g.node == "city" and culprit in g.members for g in guild.groups)


def test_patrol_level_is_capped_and_the_pack_matches_it():
    random.seed(2)
    assert justice.patrol_level(3) == 3
    assert justice.patrol_level(999) == justice.PATROL_LEVEL_CAP

    pack = justice.patrol_pack(3)
    assert len(pack) == justice.PATROL_SIZE
    assert all(u.mean_level == 3 for u in pack)


def test_resolve_fight_crime_adds_for_the_brawl_and_every_guard_downed():
    from gartok.campaign import BattleOutcome
    u = Unit("player")
    u.crime = 2
    outcome = BattleOutcome(won=True, survivors=[u], fallen=[], player_kos=2)

    justice.resolve_fight_crime(u, outcome)

    assert u.crime == 2 + 1 + 2               # untouched + brawled + 2 guards downed
