"""The offers list (scripts/economy_offers.py): what a guild can take up today, priced from the game's tables."""

import importlib.util
import os
import sys

import pytest

from gartok import arena, economy, missions
from gartok.guild import Guild

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
sys.path.insert(0, SCRIPTS)
_spec = importlib.util.spec_from_file_location("economy_offers", os.path.join(SCRIPTS, "economy_offers.py"))
offers = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = offers
_spec.loader.exec_module(offers)

import economy_activities as act


@pytest.fixture
def guild():
    return Guild(act.make_squad(3, 0), node="city")


def _by_name(found, fragment):
    return next(o for o in found if fragment in o.name)


def test_a_fresh_guild_is_offered_the_levers_the_recorded_runs_pulled(guild):
    found = offers.all_offers(guild, money=500)
    assert {o.kind for o in found} == set(offers.KINDS)
    assert _by_name(found, "Axe").kind == "tool"
    assert _by_name(found, "Challenge the Champion").covered
    assert _by_name(found, "A New Translation").gain == missions.LIBRARY_DICTIONARY.reward


def test_a_bout_costs_its_stake_per_fighter_and_pays_the_purse(guild):
    champion = arena.champion_bout()
    offer = _by_name(offers.bout_offers(3, money=0), "Challenge the Champion")
    assert (offer.cost, offer.gain) == (champion.entry * 3, champion.purse)
    assert not offer.covered and offer.net == champion.purse - champion.entry * 3


def test_the_boss_bout_is_priced_for_the_fighters_it_takes():
    boss = arena.boss_bout()
    offer = _by_name(offers.bout_offers(3, money=10_000), "Ribbit")
    assert offer.cost == boss.entry * min(3, boss.squad_max)
    assert offer.covered


def test_affordability_follows_the_money(guild):
    assert not _by_name(offers.all_offers(guild, money=0), "Challenge the Champion").covered
    assert _by_name(offers.all_offers(guild, money=10_000), "Challenge the Champion").covered


def test_a_tool_pays_back_in_shifts_and_disappears_once_owned(guild):
    members = [m for g in guild.groups for m in g.members]
    for u in members:
        u._base_inventory = []
        u.equipped_weapon = None
    axe = _by_name(offers.tool_offers(members, 1000), "Axe")
    assert axe.cost == 3 * 35
    for u in members:
        u.give_to_pack("Axe")
    assert not [o for o in offers.tool_offers(members, 1000) if "Axe" in o.name]


def test_a_mission_already_taken_is_no_longer_offered(guild):
    unit = guild.groups[0].members[0]
    assert any("A New Translation" in o.name for o in offers.mission_offers(guild, 3, 500))
    missions.accept(guild, unit, missions.LIBRARY_DICTIONARY)
    assert not any("A New Translation" in o.name for o in offers.mission_offers(guild, 3, 500))


def test_the_dictionary_is_priced_at_its_paper_and_ink(guild):
    offer = _by_name(offers.mission_offers(guild, 3, 500), "A New Translation")
    assert offer.cost == sum(economy.buy_price(n) for n in economy.LIBRARY_SUPPLIES)
    assert offer.hours > 0 and offer.per_day > 0


def test_kit_offers_skip_food_and_coin(guild):
    for offer in offers.kit_offers([m for g in guild.groups for m in g.members]):
        assert "Coin" not in offer.name and "Potato" not in offer.name


def test_the_report_has_a_line_per_offer(guild):
    found = offers.all_offers(guild, money=500)
    assert len(offers.report(found).splitlines()) == len(found) + 1
