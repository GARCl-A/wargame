"""Tests for the Apothecary faction and its deeds in factions.py."""

from gartok import factions, missions, world
from gartok.guild import Guild
from gartok.unit import Unit


def test_apothecary_faction_registered():
    assert "apothecary" in factions.FACTIONS
    fac = factions.faction("apothecary")
    assert fac.name == "The Apothecary"
    assert "apothecary_mushrooms" in [d.id for d in factions.DEEDS_BY_FACTION["apothecary"]]


def test_apothecary_mushrooms_turn_in_banks_deed_and_reputation():
    u = Unit("player")
    u.give_to_pack("Red Mushroom", 15)
    guild = Guild([u], node="apothecary")

    m = missions.accept(guild, u, missions.APOTHECARY_MUSHROOMS)
    assert m.state == "active"
    assert "apothecary_mushrooms" not in guild.deeds_done

    earned = missions.turn_in(guild, m)
    earned_ids = {d.id for d in earned}
    assert "apothecary_mushrooms" in earned_ids
    assert "apothecary_mushrooms" in guild.deeds_done
    assert guild.reputation.get("apothecary", 0) == 1
