"""Gathering at the Lumber Yard and the Mine: a licence, a shift that rolls the node's drops,
a pack that may find the crew, and a wage it has to beat."""

import random

import pytest

from gartok import (
    ai,
    campaign,
    data,
    economy,
    forced,
    gather,
    items,
    orders,
    persist,
    world,
)
from gartok.battle import Battle
from gartok.clock import Clock
from gartok.guild import Guild
from gartok.map_screen import MapScreen
from gartok.ui.tokens import fonts as ui_fonts
from gartok.unit import Unit

SHIFTS = (4, 8, 12, 16)


def _worker(money=0):
    u = Unit("player")
    u._base_inventory = []
    u.money = money
    u._derive_combat()
    return u


def _crew(node, n=1, licensed=True, money=0):
    guild = Guild([_worker(money) for _ in range(n)], clock=Clock(6 * 3600), node=node)
    if licensed:
        guild.licences.add(node)
    return guild, guild.groups[0]


def test_a_table_is_a_hundred_percent_of_real_items_each_rarer_than_the_last():
    for table in gather.TABLES.values():
        weights = [w for _, w in table]
        assert sum(weights) == 100
        assert weights == sorted(weights, reverse=True) and len(set(weights)) == len(weights)
        assert all(items.get(name) is not None for name, _ in table)


def test_the_yard_drops_lumber_and_fruit_and_the_mine_stone_coal_ore_and_gems():
    assert [n for n, _ in gather.TABLES["lumber_yard"]] == ["Lumber", "Fruit"]
    assert [n for n, _ in gather.TABLES["mine"]] == [
        "Stone Brick", "1kg Coal", "Iron Ore", items.GEM_ITEM, items.PRECIOUS_GEM_ITEM]


def test_gem_prices_and_the_merchants_kit():
    assert items.get(items.GEM_ITEM).price == 60
    assert items.get(items.PRECIOUS_GEM_ITEM).price == 240
    assert any(o[1] == "Merchant" and o[3] == items.GEM_ITEM for o in data.OCCUPATIONS)


@pytest.mark.parametrize("node_id", sorted(gather.TABLES))
@pytest.mark.parametrize("hours", SHIFTS)
def test_a_shift_sold_beats_the_best_wage_by_a_copper(node_id, hours):
    best_wage = max(economy.work_pay(node_id, hours, level) for level in (0, economy.LUMBER_LEVEL_OWN_AXE))
    assert gather.expected_value(node_id, hours) >= best_wage + 1


@pytest.mark.parametrize("node_id", sorted(gather.TABLES))
def test_a_full_day_sold_beats_the_best_wage_by_the_premium(node_id):
    best_wage = max(economy.work_pay(node_id, gather.DAY_HOURS, level)
                    for level in (0, economy.LUMBER_LEVEL_OWN_AXE))
    assert gather.expected_value(node_id, gather.DAY_HOURS) >= best_wage + gather.PREMIUM


@pytest.mark.parametrize("node_id", sorted(gather.TABLES))
def test_a_licence_pays_back_in_about_thirty_days_for_three_workers(node_id):
    gain = gather.expected_value(node_id, 16) - economy.work_pay(node_id, 16, economy.LUMBER_LEVEL_OWN_AXE)
    days = gather.licence_price(node_id) / (gather.PAYBACK_CREW * gain)
    assert gather.PAYBACK_DAYS * 0.9 <= days <= gather.PAYBACK_DAYS * 1.1


def test_a_shift_rolls_at_a_rate_per_hour():
    assert [gather.rolls(h) for h in SHIFTS] == [h / gather.HOURS_PER_ROLL for h in SHIFTS]


def test_a_haul_has_one_item_per_roll_and_comes_from_the_table():
    rng = random.Random(1)
    for node_id in gather.TABLES:
        haul = gather.roll_haul(node_id, 16, rng=rng)
        assert sum(haul.values()) in (2, 3)
        assert set(haul) <= {name for name, _ in gather.TABLES[node_id]}


def test_the_delvers_bonus_adds_rolls_on_average():
    rng = random.Random(2)
    plain = sum(sum(gather.roll_haul("mine", 16, 1.0, rng).values()) for _ in range(400))
    delver = sum(sum(gather.roll_haul("mine", 16, 1.5, rng).values()) for _ in range(400))
    per_shift = gather.rolls(16)
    assert abs(plain - 400 * per_shift) < 40 and abs(delver - 400 * per_shift * 1.5) < 60


def test_the_odds_of_a_haul_follow_the_table():
    rng = random.Random(3)
    total = {}
    for _ in range(3000):
        for name, n in gather.roll_haul("mine", 16, rng=rng).items():
            total[name] = total.get(name, 0) + n
    order = ["Stone Brick", "1kg Coal", "Iron Ore", items.GEM_ITEM, items.PRECIOUS_GEM_ITEM]
    counts = [total.get(name, 0) for name in order]
    assert counts == sorted(counts, reverse=True) and counts[-1] > 0


def test_a_mine_is_riskier_than_a_yard():
    assert gather.RISK_PER_HOUR["mine"] > gather.RISK_PER_HOUR["lumber_yard"]
    rng = random.Random(4)
    hits = {n: sum(gather.ambushed(n, 16, rng=rng) for _ in range(4000)) for n in gather.TABLES}
    assert 0 < hits["lumber_yard"] < hits["mine"]


def test_who_finds_a_crew_gathering():
    random.seed(5)
    yard = {u.race["name"] for _ in range(60) for u in gather.ambush_pack("lumber_yard")}
    mine = {u.race["name"] for _ in range(60) for u in gather.ambush_pack("mine")}
    assert yard == {"Wolf", "Snake", "Giant Spider"}
    assert mine == {"Giant Spider", "Skeleton"}


def test_a_licence_is_bought_once_by_the_richest_first():
    guild, group = _crew("mine", 2, licensed=False)
    a, b = group.members
    price = gather.licence_price("mine")
    a.money, b.money = price + 75, 100
    assert guild.licence_shortfall("mine", group.members) == 0
    assert guild.buy_licence("mine", group.members)
    assert guild.has_licence("mine") and (a.money, b.money) == (75, 100)
    assert not guild.buy_licence("mine", group.members)
    assert a.money + b.money == 175


def test_a_licence_the_crew_cannot_afford_is_not_sold():
    guild, group = _crew("lumber_yard", 2, licensed=False, money=50)
    assert guild.licence_shortfall("lumber_yard", group.members) == gather.licence_price("lumber_yard") - 100
    assert not guild.buy_licence("lumber_yard", group.members)
    assert not guild.has_licence("lumber_yard") and sum(u.money for u in group.members) == 100


def test_no_licence_is_sold_where_nothing_is_gathered():
    guild, group = _crew("market", licensed=False, money=999)
    assert not guild.buy_licence("market", group.members)
    assert not guild.licences


def test_a_gather_order_needs_the_licence():
    guild, group = _crew("mine", licensed=False)
    with pytest.raises(ValueError):
        orders.work(guild, group, 8, gather=True)


def test_a_gathering_shift_fills_each_pack_instead_of_paying_the_wage(monkeypatch):
    monkeypatch.setattr(gather, "ambushed", lambda *a, **k: False)
    random.seed(6)
    guild, group = _crew("mine", 2)
    group.order = orders.work(guild, group, 16, gather=True)
    result = campaign.advance(guild)
    for u in group.members:
        assert u.money == 0
        assert sum(u.count_of(name) for name, _ in gather.TABLES["mine"]) in (2, 3)
        assert u.work_hours == 16
    assert any("gathered 16 h" in e for e in result.events)
    assert group.order is None and not result.pending


def test_a_wage_shift_at_a_licensed_node_still_pays():
    guild, group = _crew("lumber_yard")
    group.order = orders.work(guild, group, 16)
    campaign.advance(guild)
    assert group.members[0].money == economy.work_pay("lumber_yard", 16)
    assert group.members[0].count_of("Lumber") == 0


def test_a_pack_that_finds_the_crew_is_a_forced_fight_and_holds_the_haul(monkeypatch):
    monkeypatch.setattr(gather, "ambushed", lambda *a, **k: True)
    guild, group = _crew("lumber_yard")
    group.order = orders.work(guild, group, 16, gather=True)
    result = campaign.advance(guild)
    (g, ambush), = result.pending
    assert g is group and ambush.kind == "gather_ambush" and ambush.kind in forced.EVENTS
    assert ambush.pack and ambush.hours == 16
    assert group.pending is ambush and group.locked
    assert group.members[0].count_of("Lumber") + group.members[0].count_of("Fruit") == 0


def _outcome(group, won):
    return campaign.BattleOutcome(won=won, survivors=list(group.members) if won else [], fallen=[])


@pytest.mark.parametrize("won", (True, False))
def test_winning_the_ambush_banks_the_haul_and_losing_it_does_not(monkeypatch, won):
    monkeypatch.setattr(gather, "ambushed", lambda *a, **k: True)
    random.seed(7)
    guild, group = _crew("lumber_yard", 2)
    group.order = orders.work(guild, group, 16, gather=True)
    (g, ambush), = campaign.advance(guild).pending
    events = forced.resolve_gather_ambush(guild, g, ambush, _outcome(group, won))
    held = sum(u.count_of("Lumber") + u.count_of("Fruit") for u in group.members)
    assert group.pending is None and group.order.kind == "idle" and events
    if won:
        assert 4 <= held <= 6 and sum(u.work_hours for u in group.members) == 32
    else:
        assert held == 0 and sum(u.work_hours for u in group.members) == 0


def test_the_ai_plays_out_the_fight_a_gathering_crew_gets_into():
    random.seed(8)
    for node_id in gather.TABLES:
        battle = Battle([_worker(), _worker()], gather.ambush_pack(node_id), lethal=True, aggressor="enemy")
        for _ in range(600):
            if battle.winner is not None:
                break
            ai.take_turn(battle, battle.active)
        assert battle.winner is not None


def test_the_licences_and_a_gather_order_survive_a_save():
    guild, group = _crew("mine")
    group.order = orders.work(guild, group, 8, gather=True)
    d = persist.order_to_dict(group.order)
    assert persist.order_from_dict(d).gather is True
    del d["gather"]
    assert persist.order_from_dict(d).gather is False
    assert persist.PAYLOAD_DEFAULTS["licences"] == []


def _blocks(guild, node_id):
    ms = MapScreen(ui_fonts(), guild, lambda: None, lambda: None, lambda: None, lambda grp: None)
    return ms, ms._inspector_content(guild.groups[0], world.node(node_id))


def test_the_map_offers_the_licence_until_it_is_held_then_the_shifts():
    guild, group = _crew("mine", licensed=False, money=100)
    ms, blocks = _blocks(guild, "mine")
    buy = next(b for b in blocks if b.get("key") == "buy_licence")
    assert not buy["enabled"] and any("short" in b.get("text", "") for b in blocks)
    group.members[0].money = gather.licence_price("mine") + 175
    ms, blocks = _blocks(guild, "mine")
    assert next(b for b in blocks if b.get("key") == "buy_licence")["enabled"]
    ms.selected = group
    ms._handle_button("buy_licence")
    assert guild.has_licence("mine") and group.members[0].money == 175
    ms, blocks = _blocks(guild, "mine")
    row = next(b for b in blocks if b["type"] == "button_row" and b["items"][0]["key"].startswith("gather:"))
    assert [i["key"] for i in row["items"]] == [f"gather:{h}" for h in SHIFTS]
    assert not any(b.get("key") == "buy_licence" for b in blocks)


def test_a_gather_button_issues_a_gathering_order_the_map_names():
    guild, group = _crew("lumber_yard")
    ms, _ = _blocks(guild, "lumber_yard")
    ms.selected = group
    ms._handle_button("gather:8")
    assert group.order.kind == "work" and group.order.gather and group.order.hours == 8
    assert ms._order_status(group).startswith("gathering")
    assert ms._state(group)[0] == "GATHER"


def test_gather_screen_interaction():
    import pygame

    from gartok import world
    from gartok.gather_screen import GatherScreen
    from gartok.ui.tokens import fonts as ui_fonts

    guild, group = _crew("lumber_yard", licensed=False, money=500)
    node = world.node("lumber_yard")
    done = []
    gs = GatherScreen(ui_fonts(), guild, group, node, on_done=lambda: done.append(True))
    surf = pygame.Surface((1280, 720))
    gs.draw(surf)

    assert gs.tutorial_key() == "gathering"
    assert any(k == "buy_licence" for k, _ in gs.buttons)
    gs._on_button("buy_licence")
    assert guild.has_licence("lumber_yard")

    gs.draw(surf)
    assert any(k == "gather:8" for k, _ in gs.buttons)
    gs._on_button("gather:8")
    assert group.order.kind == "work" and group.order.gather and group.order.hours == 8
    assert done == [True]

