"""Hidden factions: known only after the guild enters one of their nodes."""

from gartok import factions, forced, persist
from gartok.guild import Guild
from tests.helpers import Unit

OPEN = {"arena", "bankers"}


def _ids(guild):
    return {f.id for f in factions.known(guild)}


def test_only_the_arena_and_the_bankers_start_known():
    guild = Guild([Unit("player")], node="city")
    assert _ids(guild) == OPEN
    assert {f.id for f in factions.FACTIONS.values() if f.hidden} == set(factions.FACTIONS) - OPEN


def test_every_hidden_faction_owns_a_real_node():
    from gartok import world
    for f in factions.FACTIONS.values():
        assert all(world.node(n) for n in f.nodes)
        assert f.nodes or not f.hidden


def test_entering_a_node_meets_its_faction_once():
    guild = Guild([Unit("player")], node="city")
    assert [f.id for f in guild.meet_factions_at("library")] == ["library"]
    assert guild.meet_factions_at("library") == []
    assert _ids(guild) == OPEN | {"library"}


def test_arriving_reports_the_faction_found():
    guild = Guild([Unit("player")], node="city")
    notes = forced.arrival_notices(guild, "tanner")
    assert notes == ["You have found The Tanners."]
    assert forced.arrival_notices(guild, "tanner") == []


def test_standing_alone_makes_a_faction_known():
    guild = Guild([Unit("player")], node="city")
    guild.reputation["apothecary"] = 1
    assert "apothecary" in _ids(guild)


def test_met_factions_survive_a_save():
    world_id = persist.new_world_id()
    guild = Guild([Unit("player")], node="city")
    guild.meet_factions_at("ledger_hold")
    persist.save_game(world_id, guild)
    assert "ledger_hold" in persist.load_game(world_id).met_factions
