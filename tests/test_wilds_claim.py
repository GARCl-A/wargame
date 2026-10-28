"""The Wilds claim campaign (Sistema 3, [[gartok-property-two-paths]]): the
six-stage state machine, the two deliberate fights (CLEAR/SWEEP), hauling
Lumber to raise the fences, garrisoning to sustain the claim, and the
periodic raid that can reset the sustain countdown. Also the first real
consumer of Sistema 1's garrison engine (`world.WILDS_TERRITORY_NODE` is the
first node with a `garrison_job` actually set)."""

import random

from gartok import campaign, forced, orders
from gartok.group import Group
from gartok.guild import Guild
from tests.helpers import Unit, economy, packed, world

NODE = world.WILDS_TERRITORY_NODE


# --------------------------------------------------------------------------- #
# the node itself                                                             #
# --------------------------------------------------------------------------- #

def test_the_claim_node_exists_reachable_from_the_wilds_and_offers_the_lumber_job():
    node = world.node(NODE)
    assert node.has("claim") and node.garrison_job == "lumber"
    path, hours = world.route("wilds", NODE)
    assert path == ["wilds", NODE] and hours > 0


# --------------------------------------------------------------------------- #
# the stage state machine                                                     #
# --------------------------------------------------------------------------- #

def test_scouting_flips_the_stage_with_no_check():
    random.seed(1)
    guild = Guild([Unit("player")])
    assert guild.wilds_claim_stage == "NONE"
    guild.wilds_claim_scout()
    assert guild.wilds_claim_stage == "SCOUTED"


def test_building_fences_consumes_the_banked_lumber():
    random.seed(1)
    guild = Guild([Unit("player")])
    guild.wilds_claim_deposit_lumber(economy.WILDS_CLAIM_FENCE_LUMBER + 3)
    guild.wilds_claim_build_fences()
    assert guild.wilds_claim_stage == "FENCED"
    assert guild.wilds_claim_fence_lumber == 3


def test_starting_to_sustain_sets_the_full_countdown():
    random.seed(1)
    guild = Guild([Unit("player")])
    guild.wilds_claim_start_sustaining()
    assert guild.wilds_claim_stage == "SUSTAINING"
    assert guild.wilds_claim_sustain_days_left == economy.WILDS_CLAIM_SUSTAIN_DAYS


def test_sustaining_counts_down_only_while_actually_garrisoned():
    random.seed(1)
    g = Group([Unit("player")], node=NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_start_sustaining()
    g.order = orders.garrison("lumber")

    guild.pass_time(24)
    assert guild.wilds_claim_sustain_days_left == economy.WILDS_CLAIM_SUSTAIN_DAYS - 1

    g.order = orders.idle()                    # pulled out early, not raided
    guild.pass_time(24)
    assert guild.wilds_claim_sustain_days_left == economy.WILDS_CLAIM_SUSTAIN_DAYS


def test_sustaining_the_full_stretch_establishes_the_claim():
    random.seed(1)
    p = Unit("player")
    p._base_inventory = packed(["Meat"] * (economy.WILDS_CLAIM_SUSTAIN_DAYS + 2))   # never starves mid-test
    g = Group([p], node=NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_start_sustaining()
    g.order = orders.garrison("lumber")

    for _ in range(economy.WILDS_CLAIM_SUSTAIN_DAYS):
        guild.pass_time(24)
    assert guild.wilds_claim_stage == "ESTABLISHED"
    assert guild.wilds_claim_sustain_days_left is None


def test_a_garrison_elsewhere_does_not_count_toward_sustaining_here():
    random.seed(1)
    g = Group([Unit("player")], node="market")
    guild = Guild(None, groups=[g])
    guild.wilds_claim_start_sustaining()
    g.order = orders.garrison("lumber")

    guild.pass_time(24)
    assert guild.wilds_claim_sustain_days_left == economy.WILDS_CLAIM_SUSTAIN_DAYS


# --------------------------------------------------------------------------- #
# the screen: scouting, depositing/building, garrisoning                      #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# claim battles (CLEAR / SWEEP) through app._battle_end                       #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# the raid during SUSTAINING                                                  #
# --------------------------------------------------------------------------- #

def _forced_raid_chance(value):
    orig = economy.WILDS_RAID_CHANCE
    economy.WILDS_RAID_CHANCE = value
    return orig


def test_a_garrison_can_be_raided_mid_sustain():
    random.seed(1)
    orig = _forced_raid_chance(1.0)
    try:
        g = Group([Unit("player")], node=NODE)
        guild = Guild(None, groups=[g])
        guild.wilds_claim_start_sustaining()
        g.order = orders.garrison("lumber")

        result = campaign.advance(guild, dt=24)
    finally:
        economy.WILDS_RAID_CHANCE = orig

    assert g.order is None
    order = next(o for grp, o in result.pending if grp is g)
    assert order.kind == "wilds_raid" and order.job == "lumber" and len(order.pack) > 0


def test_no_raid_outside_the_sustaining_stage():
    random.seed(1)
    orig = _forced_raid_chance(1.0)
    try:
        g = Group([Unit("player")], node=NODE)
        guild = Guild(None, groups=[g])
        g.order = orders.garrison("lumber")        # no claim in progress at all
        result = campaign.advance(guild, dt=24)
    finally:
        economy.WILDS_RAID_CHANCE = orig

    assert g.order.kind == "garrison" and not result.pending


def test_winning_the_raid_resumes_the_same_garrison_job():
    random.seed(1)
    p = Unit("player")
    g = Group([p], node=NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_start_sustaining()
    order = orders.Order("wilds_raid", pack=(Unit("enemy"),), job="lumber")

    outcome = campaign.BattleOutcome(won=True, survivors=[p], fallen=[])
    events = forced.resolve_wilds_raid(guild, g, order, outcome)
    assert g.order.kind == "garrison" and g.order.job == "lumber"
    assert guild.wilds_claim_stage == "SUSTAINING"
    assert any("drives off" in e for e in events)


def test_losing_the_raid_resets_the_sustain_countdown():
    random.seed(1)
    p = Unit("player")
    g = Group([p], node=NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_start_sustaining()
    guild.wilds_claim_sustain_days_left = 1     # about to finish -- then a raid hits
    order = orders.Order("wilds_raid", pack=(Unit("enemy"),), job="lumber")

    outcome = campaign.BattleOutcome(won=False, survivors=[p], fallen=[])
    events = forced.resolve_wilds_raid(guild, g, order, outcome)
    assert g.order.kind == "idle"
    assert guild.wilds_claim_sustain_days_left == economy.WILDS_CLAIM_SUSTAIN_DAYS
    assert any("scattered" in e for e in events)


# --------------------------------------------------------------------------- #
# app wiring: opening the screen                                              #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Sistema 1's engine finally has a real consumer                              #
# --------------------------------------------------------------------------- #

def test_a_garrison_at_the_real_claim_node_produces_lumber():
    random.seed(1)
    g = Group([Unit("player"), Unit("player")], node=NODE)
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("lumber")

    guild.pass_time(24)
    assert guild.garrison_stock_at(NODE) == ["Lumber"] * (
        2 * economy.GARRISON_YIELD_PER_MEMBER_PER_DAY)


# --------------------------------------------------------------------------- #
# real draw, through pygame -- every stage panel at least once                #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# save round trip                                                             #
# --------------------------------------------------------------------------- #

def test_wilds_claim_state_survives_a_save_round_trip():
    import os

    from gartok import persist
    slot = "testworld"
    if os.path.exists(persist.save_path(slot)):
        return
    random.seed(1)
    guild = Guild([Unit("player")])
    guild.wilds_claim_start_sustaining()
    guild.wilds_claim_fence_lumber = 4
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot)
        assert back.wilds_claim_stage == "SUSTAINING"
        assert back.wilds_claim_sustain_days_left == economy.WILDS_CLAIM_SUSTAIN_DAYS
        assert back.wilds_claim_fence_lumber == 4
    finally:
        persist.delete_world(slot)


# --------------------------------------------------------------------------- #
# a garrisoned group is still reachable from the map                          #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# the attack chance is per day, not per call; a holding garrison rests        #
# --------------------------------------------------------------------------- #

def _sustaining_guild(job="lumber"):
    g = Group([Unit("player")], node=NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_start_sustaining()
    g.order = orders.garrison(job)
    return guild, g


def test_hour_long_advances_roll_the_raid_once_a_day_not_once_a_call(monkeypatch):
    rolls = []
    monkeypatch.setattr(forced.random, "random", lambda: rolls.append(1) or 0.99)
    guild, _ = _sustaining_guild()
    for _ in range(24):
        campaign.advance(guild, dt=1)
    assert len(rolls) == 1


def test_a_call_that_crosses_no_midnight_never_rolls(monkeypatch):
    monkeypatch.setattr(forced.random, "random", lambda: 0.0)
    guild, g = _sustaining_guild()
    result = campaign.advance(guild, dt=1)
    assert not result.pending and g.order.kind == "garrison"


def test_several_days_in_one_jump_raise_the_odds_of_a_hit():
    assert not forced.claim_attack_rolls(0)
    hits = lambda days: sum(forced.claim_attack_rolls(days) for _ in range(4000))
    random.seed(3)
    one, five = hits(1), hits(5)
    assert 0.15 < one / 4000 < 0.25
    assert 0.62 < five / 4000 < 0.72


def test_a_holding_garrison_heals_and_a_gathering_one_does_not():
    for job, heals in (("hold", True), ("lumber", False)):
        guild, g = _sustaining_guild(job)
        p = g.members[0]
        p.hp = max(1, p.hp_max - 5)
        before = p.hp
        guild.pass_time(8)
        assert (p.hp > before) is heals, job


def test_hold_is_a_known_garrison_job_that_produces_nothing():
    assert "hold" in economy.GARRISON_JOBS and economy.GARRISON_JOBS["hold"] is None
    assert orders.is_resting(orders.garrison("hold"))
    assert not orders.is_resting(orders.garrison("lumber"))
    assert orders.is_resting(orders.rest(8))
