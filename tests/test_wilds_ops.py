"""Sistema 4 -- operating an ESTABLISHED Wilds claim: the periodic seizure
attempt (unguarded auto-seizes, garrisoned fights for it), and retaking a
seized claim by simply travelling there and winning. Closes the risk loop
Sistema 3 left open once a claim is finally the guild's own ground.
[[gartok-property-two-paths]]."""

import random

from gartok import campaign, forced, orders
from gartok.group import Group
from gartok.guild import Guild
from tests.helpers import Unit, economy, world

NODE = world.WILDS_TERRITORY_NODE


def _established_guild(*, garrisoned=False):
    """A guild with an already-ESTABLISHED, guild-owned claim -- optionally
    with a group actively garrisoning it right now."""
    p = Unit("player")
    g = Group([p], node=NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_stage = "ESTABLISHED"
    guild.wilds_claim_owner = "guild"
    if garrisoned:
        g.order = orders.garrison("lumber")
    return guild, g, p


def _forced_raid_chance(value):
    orig = economy.WILDS_RAID_CHANCE
    economy.WILDS_RAID_CHANCE = value
    return orig


# --------------------------------------------------------------------------- #
# the periodic seizure attempt                                                #
# --------------------------------------------------------------------------- #

def test_an_unguarded_established_claim_is_seized_without_a_fight():
    random.seed(1)
    orig = _forced_raid_chance(1.0)
    try:
        guild, g, p = _established_guild(garrisoned=False)
        result = campaign.advance(guild, dt=24)
    finally:
        economy.WILDS_RAID_CHANCE = orig

    assert guild.wilds_claim_owner == "seized"
    assert not result.pending                     # no fight -- nobody there to make one
    assert any("unguarded" in e for e in result.events)


def test_a_garrisoned_established_claim_can_be_attacked():
    random.seed(1)
    orig = _forced_raid_chance(1.0)
    try:
        guild, g, p = _established_guild(garrisoned=True)
        result = campaign.advance(guild, dt=24)
    finally:
        economy.WILDS_RAID_CHANCE = orig

    assert g.order is None
    order = next(o for grp, o in result.pending if grp is g)
    assert order.kind == "wilds_seizure" and order.job == "lumber" and len(order.pack) > 0
    assert guild.wilds_claim_owner == "guild"      # not seized yet -- the fight decides


def test_no_seizure_attempt_before_established_or_after_already_seized():
    random.seed(1)
    orig = _forced_raid_chance(1.0)
    try:
        guild, g, p = _established_guild(garrisoned=True)
        guild.wilds_claim_stage = "SWEPT"          # not established yet
        result = campaign.advance(guild, dt=24)
        assert not result.pending and guild.wilds_claim_owner == "guild"

        guild.wilds_claim_stage = "ESTABLISHED"
        guild.wilds_claim_owner = "seized"         # already lost -- nothing left to seize
        result = campaign.advance(guild, dt=24)
        assert not result.pending
    finally:
        economy.WILDS_RAID_CHANCE = orig


def test_no_seizure_roll_ever_touches_a_sustaining_claim():
    """Regression: `_wilds_claim_attack_check` must route SUSTAINING to the
    raid check (reset-the-timer consequence), never the seizure check
    (owner-transfer consequence) -- the two must not cross wires."""
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

    order = next(o for grp, o in result.pending if grp is g)
    assert order.kind == "wilds_raid"              # not "wilds_seizure"
    assert guild.wilds_claim_owner is None          # never touched pre-ESTABLISHED


# --------------------------------------------------------------------------- #
# resolving the seizure fight                                                 #
# --------------------------------------------------------------------------- #

def test_winning_the_seizure_fight_keeps_the_claim_and_resumes_the_garrison():
    random.seed(1)
    guild, g, p = _established_guild(garrisoned=False)
    order = orders.Order("wilds_seizure", pack=(Unit("enemy"),), job="lumber")

    outcome = campaign.BattleOutcome(won=True, survivors=[p], fallen=[])
    events = forced.resolve_wilds_seizure(guild, g, order, outcome)
    assert guild.wilds_claim_owner == "guild"
    assert g.order.kind == "garrison" and g.order.job == "lumber"
    assert any("holds the claim" in e for e in events)


def test_losing_the_seizure_fight_seizes_the_claim():
    random.seed(1)
    guild, g, p = _established_guild(garrisoned=False)
    order = orders.Order("wilds_seizure", pack=(Unit("enemy"),), job="lumber")

    outcome = campaign.BattleOutcome(won=False, survivors=[p], fallen=[])
    events = forced.resolve_wilds_seizure(guild, g, order, outcome)
    assert guild.wilds_claim_owner == "seized"
    assert g.order.kind == "idle"
    assert any("seized" in e for e in events)


def test_a_full_wipe_during_the_seizure_fight_still_seizes_the_claim():
    random.seed(1)
    guild, g, p = _established_guild(garrisoned=False)
    order = orders.Order("wilds_seizure", pack=(Unit("enemy"),), job="lumber")
    guild.remove_members([p])                       # the fight wiped the garrison

    outcome = campaign.BattleOutcome(won=False, survivors=[], fallen=[p])
    events = forced.resolve_wilds_seizure(guild, g, order, outcome)
    assert guild.wilds_claim_owner == "seized"
    assert any("seized" in e for e in events)        # must not crash on an emptied group


# --------------------------------------------------------------------------- #
# retaking a seized claim on arrival                                          #
# --------------------------------------------------------------------------- #

def test_arriving_at_a_seized_claim_forces_a_retake_fight():
    random.seed(1)
    rescuer = Unit("player")
    g = Group([rescuer], node="wilds")
    guild = Guild(None, groups=[g])
    guild.wilds_claim_stage = "ESTABLISHED"
    guild.wilds_claim_owner = "seized"
    g.order = orders.travel(g, NODE)

    result = campaign.advance(guild)
    assert g.node == NODE and g.order is None
    order = next(o for grp, o in result.pending if grp is g)
    assert order.kind == "wilds_retake" and len(order.pack) > 0


def test_arriving_at_an_owned_established_claim_is_untouched():
    random.seed(1)
    visitor = Unit("player")
    g = Group([visitor], node="wilds")
    guild = Guild(None, groups=[g])
    guild.wilds_claim_stage = "ESTABLISHED"
    guild.wilds_claim_owner = "guild"
    g.order = orders.travel(g, NODE)

    result = campaign.advance(guild)
    assert g.node == NODE and g.order is None
    assert not result.pending


def test_winning_the_retake_restores_guild_ownership_and_resumes_travel():
    random.seed(1)
    p = Unit("player")
    g = Group([p], node=NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_owner = "seized"
    order = orders.Order("wilds_retake", pack=(Unit("enemy"),), resume_path=())

    outcome = campaign.BattleOutcome(won=True, survivors=[p], fallen=[])
    events = forced.resolve_wilds_claim_retake(guild, g, order, outcome)
    assert guild.wilds_claim_owner == "guild"
    assert g.order.kind == "idle"
    assert any("retaken" in e for e in events)


def test_losing_the_retake_leaves_the_claim_seized():
    random.seed(1)
    p = Unit("player")
    g = Group([p], node=NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_owner = "seized"
    order = orders.Order("wilds_retake", pack=(Unit("enemy"),), resume_path=())

    outcome = campaign.BattleOutcome(won=False, survivors=[p], fallen=[])
    events = forced.resolve_wilds_claim_retake(guild, g, order, outcome)
    assert guild.wilds_claim_owner == "seized"
    assert any("stays lost" in e for e in events)


# --------------------------------------------------------------------------- #
# the screen reflects a seized claim without offering to collect from it      #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# the full lifecycle, seam to seam (Sistemas 1+3+4 chained together)          #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# save round trip                                                             #
# --------------------------------------------------------------------------- #

def test_wilds_claim_owner_survives_a_save_round_trip():
    import os

    from gartok import persist
    slot = "testworld"
    if os.path.exists(persist.save_path(slot)):
        return
    random.seed(1)
    guild = Guild([Unit("player")])
    guild.wilds_claim_stage = "ESTABLISHED"
    guild.wilds_claim_owner = "seized"
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot)
        assert back.wilds_claim_owner == "seized"
    finally:
        persist.delete_world(slot)
