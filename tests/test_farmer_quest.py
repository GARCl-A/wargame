"""The Farmer's quest (`docs/plans/holy_symbol_quest.md`): the gate on its job, the Farm's Jobs tab and the
shop shut while Edric waits for his daughter."""

import pytest

from gartok import items, job_board, missions, orders, world
from gartok.clock import SECONDS_PER_DAY
from gartok.group import Group
from gartok.guild import Guild
from gartok.web.hub_session import HubSession
from gartok.web.map_session import MapSession
from tests.helpers import standard_unit

T = missions.FARMER_DAUGHTER


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setattr(missions, "FARMER_QUEST_LIVE", True)


def _guild(day=30, revealed=("faith_cathedral",)):
    u = standard_unit()
    u.give_to_pack(items.COIN_ITEM, 200)
    guild = Guild([u])
    guild.groups = [Group([u], "farm")]
    guild.clock.seconds = (day - 1) * SECONDS_PER_DAY
    guild.revealed |= set(revealed)
    return guild


def test_the_template_is_the_farmers_and_carries_the_symbol():
    assert (T.giver, T.node, T.deadline_days, T.goal_captive) == ("farmer", "farm", 20, "farmers_daughter")
    assert T.reward == 300 and T.reward_items == (items.HOLY_SYMBOL_ITEM,)
    assert missions.TEMPLATES[T.id] is T and T.name and T.blurb


def test_nothing_is_offered_while_the_release_switch_is_off():
    assert not missions.FARMER_QUEST_LIVE
    assert T not in missions.offers_at(_guild(day=60), "farm")


def test_it_opens_on_day_30_with_the_cathedral_found(live):
    assert T in missions.offers_at(_guild(day=30), "farm")


def test_it_is_not_offered_the_day_before(live):
    assert T not in missions.offers_at(_guild(day=29), "farm")


def test_it_is_not_offered_without_the_cathedral(live):
    assert T not in missions.offers_at(_guild(day=45, revealed=()), "farm")


def test_the_cathedral_found_late_opens_it_then(live):
    guild = _guild(day=45, revealed=())
    guild.reveal_node("faith_cathedral")
    assert T in missions.offers_at(guild, "farm")


def test_the_job_is_offered_only_at_the_farm(live):
    assert T not in missions.offers_at(_guild(day=30), "city")


def test_the_farm_gets_a_jobs_tab_only_when_live(live, monkeypatch):
    guild = _guild()
    hub = HubSession(MapSession(guild), guild.groups[0], orders.Order("stable"))
    assert [k for k, _ in hub.tabs] == ["shop", "stable", "jobs"]
    monkeypatch.setattr(missions, "FARMER_QUEST_LIVE", False)
    hub = HubSession(MapSession(guild), guild.groups[0], orders.Order("stable"))
    assert [k for k, _ in hub.tabs] == ["shop", "stable"]


def test_the_board_shows_the_offer_and_the_leader_signs(live):
    guild = _guild()
    g = guild.groups[0]
    board = job_board.FarmerBoard(guild, g)
    assert board.get_templates() == [T]
    assert board.accept(T)
    m = next(m for m in guild.missions if m.template_id == T.id)
    assert m.deadline_day == m.accepted_day + 20 and m.unit_uid == g.leader.uid
    assert "20" in board.get_req_str(T) and board.get_status_str(T, 0, False, 20)


def test_the_farm_sells_nothing_while_the_job_is_out(live):
    from gartok.web.shop_tab import ShopTab
    guild = _guild()
    g = guild.groups[0]
    node = world.node("farm")
    assert ShopTab(guild, g, node).state()["closed"] is None
    job_board.FarmerBoard(guild, g).accept(T)
    tab = ShopTab(guild, g, node)
    st = tab.state()
    assert st["closed"] and st["shelf"] == []
    with pytest.raises(ValueError):
        tab.buy("Potato")
    with pytest.raises(ValueError):
        tab.sell([])


def test_the_farm_shop_is_open_while_the_quest_is_dark():
    from gartok.web.shop_tab import ShopTab
    guild = _guild()
    node = world.node("farm")
    assert ShopTab(guild, guild.groups[0], node).state()["closed"] is None
