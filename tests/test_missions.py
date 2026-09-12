"""Missions: paid, time-boxed jobs, scoped to the accepting *unit* (not the
group it happened to be standing in -- see missions.py's module docstring) --
and the market's finite stock on a few items (economy.STOCK)."""

import random

from tests.helpers import economy, Unit
from gartok import missions
from gartok.guild import Guild


def _guild_with_two_groups():
    random.seed(1)
    hunters = [Unit("player") for _ in range(2)]
    stay_home = [Unit("player")]
    guild = Guild(hunters + stay_home)
    hunting_group, home_group = guild.split_group(guild.groups[0], hunters), guild.groups[0]
    return guild, hunting_group, home_group


def test_only_the_signers_current_groups_hides_count_toward_turn_in():
    guild, hunters, home = _guild_with_two_groups()
    signer = hunters.members[0]
    m = missions.accept(guild, signer, missions.TANNER_HIDES)

    home.members[0].give_to_pack("1sqm Hide")
    assert missions.progress(guild, m) == 0
    assert not missions.can_turn_in(guild, m)

    for _ in range(15):
        signer.give_to_pack("1sqm Hide")
    assert missions.progress(guild, m) == 15
    assert missions.can_turn_in(guild, m)


def test_mission_follows_its_signer_into_a_new_group_after_a_split():
    """The whole point of scoping to a unit, not a Group object: a group is
    reshuffled constantly, so the mission must survive the signer moving to a
    different one."""
    guild, hunters, home = _guild_with_two_groups()
    signer, other_hunter = hunters.members
    m = missions.accept(guild, signer, missions.TANNER_HIDES)

    # the signer splits off alone into a brand new group -- the old `hunters`
    # Group object no longer holds them (and may not even still exist).
    solo = guild.split_group(hunters, [signer])
    signer_gold_before = signer.gold
    other_hunter_gold_before = other_hunter.gold
    for _ in range(15):
        signer.give_to_pack("1sqm Hide")

    assert missions.progress(guild, m) == 15          # still resolves via the unit
    missions.turn_in(guild, m)
    assert m.state == "done"
    assert signer.gold == signer_gold_before + missions.TANNER_HIDES.reward  # solo: whole reward
    assert other_hunter.gold == other_hunter_gold_before  # left behind, untouched


def test_turn_in_consumes_the_hides_and_splits_the_reward():
    guild, hunters, _home = _guild_with_two_groups()
    signer = hunters.members[0]
    m = missions.accept(guild, signer, missions.TANNER_HIDES)
    for _ in range(15):
        signer.give_to_pack("1sqm Hide")
    for u in hunters.members:
        u.gold = 0

    missions.turn_in(guild, m)

    assert m.state == "done"
    assert signer._base_inventory.count("1sqm Hide") == 0
    assert sum(u.gold for u in hunters.members) == missions.TANNER_HIDES.reward


def test_missed_deadline_fails_the_mission_and_a_giver_offers_again():
    guild, hunters, home = _guild_with_two_groups()
    m = missions.accept(guild, hunters.members[0], missions.TANNER_HIDES)
    assert missions.TANNER_HIDES.id not in {t.id for t in missions.offers_at(guild, "city")}

    for u in guild.roster:                       # keep everyone fed -- not what's under test
        for _ in range(10):
            u.give_to_pack("Meat")

    guild.pass_time(24 * (missions.TANNER_HIDES.deadline_days + 1))

    assert m.state == "failed"
    assert missions.TANNER_HIDES.id in {t.id for t in missions.offers_at(guild, "city")}


def test_signers_death_leaves_the_mission_unreachable():
    guild, hunters, home = _guild_with_two_groups()
    signer = hunters.members[0]
    m = missions.accept(guild, signer, missions.TANNER_HIDES)
    guild.remove_members([signer])
    assert missions.progress(guild, m) == 0
    assert not missions.can_turn_in(guild, m)


def test_market_stock_is_finite_for_scarce_items_and_unlimited_otherwise():
    random.seed(2)
    guild = Guild([Unit("player")])
    assert guild.market_stock["1sqm Hide"] == 0
    assert economy.stock_of(guild.market_stock, "Meat") is None   # never scarce
