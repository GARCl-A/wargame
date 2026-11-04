"""Routines: the blocks, the pointer, the pauses, and the order they hand the clock on `campaign.advance`."""

import random

from gartok import campaign, forced, orders, persist, world
from gartok import routines as r
from gartok.clock import Clock
from gartok.group import Group
from gartok.guild import Guild
from tests.helpers import standard_unit


def _band(node, name, potatoes=3, money=0):
    u = standard_unit()
    u.money = money
    u.give_to_pack("Potato", potatoes)
    return Group([u], node=node, name=name, leader=u)


def _guild(*groups):
    return Guild(None, groups=list(groups), clock=Clock(6 * 3600))


def _quiet(monkeypatch):
    random.seed(1)
    monkeypatch.setattr(world, "ROAD_AMBUSH_CHANCE", 0.0)


def test_a_routine_walks_its_blocks_and_ends(monkeypatch):
    _quiet(monkeypatch)
    g = _band("city", "Runners")
    guild = _guild(g)
    r.assign(guild, g, r.Routine([r.Travel("market"), r.Rest(2)]))
    assert g.order.kind == "travel"

    campaign.advance(guild)
    assert g.node == "market" and g.order.kind == "rest"

    campaign.advance(guild)
    assert g.order is None and g.routine is None


def test_repeat_checks_its_condition_before_each_pass(monkeypatch):
    _quiet(monkeypatch)
    g = _band("lumber_yard", "Hands")
    guild = _guild(g)
    r.assign(guild, g, r.Routine([r.Repeat(r.coins(r.own()) >= 6, [r.Work(8)], until=True)]))
    shifts = 0
    while g.routine is not None:
        campaign.advance(guild)
        shifts += 1
        assert shifts < 50
    assert g.members[0].money == 6 and shifts == 3


def test_a_repeat_whose_condition_already_holds_is_skipped():
    g = _band("city", "Idle", money=100)
    guild = _guild(g)
    r.assign(guild, g, r.Routine([r.Repeat(r.coins(r.own()) >= 40, [r.Rest(8)], until=True), r.Rest(1)]))
    assert g.order.kind == "rest" and g.order.hours == 1


def test_a_wait_polls_until_another_group_has_enough(monkeypatch):
    _quiet(monkeypatch)
    mill, trader = _band("lumber_yard", "Mill", potatoes=0), _band("lumber_yard", "Trader")
    guild = _guild(mill, trader)
    mill.order = orders.rest(48)
    r.assign(guild, trader, r.Routine([r.Wait(r.items(r.group("Mill"), "Lumber") >= 4), r.Rest(1)]))
    assert trader.order.kind == "wait"

    campaign.advance(guild)
    assert trader.order.kind == "wait"
    mill.members[0].give_to_pack("Lumber", 4)
    campaign.advance(guild)
    assert trader.order.kind == "rest"


def test_a_group_can_be_named_by_what_it_does_or_by_being_here():
    a, b = _band("city", "A"), _band("city", "B")
    far = _band("farm", "Far")
    guild = _guild(a, b, far)
    b.order = orders.rest(4)
    assert r.find(guild, a, r.doing("rest")) is b
    assert r.find(guild, a, r.doing("gather")) is None
    assert r.find(guild, a, r.anyone_here()) is b
    assert r.find(guild, a, r.group("Far")) is far
    assert r.find(guild, a, r.own()) is a


def test_take_and_hand_over_move_goods_between_groups_at_the_same_node():
    a, b = _band("city", "A", potatoes=5), _band("city", "B", potatoes=0)
    guild = _guild(a, b)
    r.assign(guild, b, r.Routine([r.Take(r.group("A"), "Potato", 2), r.HandOver(r.group("A"), "Potato", 1)]))
    assert b.routine is None
    assert a.members[0].count_of("Potato") == 4 and b.members[0].count_of("Potato") == 1


def test_take_until_days_picks_just_enough_food():
    a, b = _band("city", "A", potatoes=9), _band("city", "B", potatoes=1)
    guild = _guild(a, b)
    r.assign(guild, b, r.Routine([r.Take(r.group("A"), "Potato", until_days=4)]))
    assert b.members[0].count_of("Potato") == 4 and a.members[0].count_of("Potato") == 6


def test_a_hand_over_with_nobody_there_waits_a_day_then_stops_the_routine(monkeypatch):
    _quiet(monkeypatch)
    sender, away = _band("city", "Sender"), _band("farm", "Away")
    guild = _guild(sender, away)
    r.assign(guild, sender, r.Routine([r.HandOver(r.group("Away"), "Potato")]))
    assert sender.order.kind == "wait" and sender.order.hours == 24

    campaign.advance(guild)
    assert sender.routine.paused == "the receiving group is not here"
    assert sender.order is None and isinstance(sender.routine.current(), r.HandOver)


def test_a_hand_over_without_the_fallback_stops_at_once():
    sender, away = _band("city", "Sender"), _band("farm", "Away")
    guild = _guild(sender, away)
    r.assign(guild, sender, r.Routine([r.HandOver(r.group("Away"), "Potato", fallback=False)]))
    assert sender.order is None and sender.routine.paused


def test_the_receiver_arriving_during_the_wait_gets_the_goods(monkeypatch):
    _quiet(monkeypatch)
    sender, away = _band("city", "Sender"), _band("farm", "Away", potatoes=0)
    guild = _guild(sender, away)
    r.assign(guild, sender, r.Routine([r.HandOver(r.group("Away"), "Potato", 2)]))
    away.node = "city"
    campaign.advance(guild)
    assert sender.routine is None and away.members[0].count_of("Potato") == 2


def test_a_block_that_cannot_run_stops_the_routine_with_the_reason():
    g = _band("city", "Nobody")
    guild = _guild(g)
    r.assign(guild, g, r.Routine([r.Gather(8)]))
    assert g.order is None and g.routine.paused and isinstance(g.routine.current(), r.Gather)


def test_blocks_that_spend_no_time_forever_stop_the_routine():
    g = _band("city", "Spinner")
    guild = _guild(g)
    always = r.coins(r.own()) >= 0
    r.assign(guild, g, r.Routine([r.Repeat(always, [r.Wait(always)])]))
    assert g.routine.paused == "too many blocks in no time"


def test_an_interrupted_trip_leaves_the_pointer_and_continue_resumes_it(monkeypatch):
    _quiet(monkeypatch)
    g = _band("city", "Walkers")
    guild = _guild(g)
    ambush = orders.Order("ambush")
    stop = iter([ambush])
    monkeypatch.setattr(forced, "arrival_pause", lambda *args: next(stop, None))
    r.assign(guild, g, r.Routine([r.Travel("wilds"), r.Rest(1)]))

    result = campaign.advance(guild, dt=4)
    assert g.routine.paused == "something came up" and g.order is None
    assert [p for p, _ in result.pending] == [g] and isinstance(g.routine.current(), r.Travel)

    g.pending = None
    r.resume(guild, g)
    assert g.order.kind == "travel" and g.routine.paused is None
    campaign.advance(guild)
    assert g.node == "wilds" and g.order.kind == "rest"


def test_a_hungry_group_is_handed_back_to_the_player(monkeypatch):
    _quiet(monkeypatch)
    g = _band("city", "Starving", potatoes=0)
    guild = _guild(g)
    r.assign(guild, g, r.Routine([r.Rest(100), r.Rest(1)]))
    campaign.advance(guild)
    assert g.routine.paused == "hungry" and g.order is None


def test_a_group_with_a_fight_due_is_not_advanced_by_its_routine():
    g = _band("city", "Caught")
    guild = _guild(g)
    r.assign(guild, g, r.Routine([r.Rest(1), r.Rest(1)]))
    g.order, g.pending = None, orders.Order("ambush")
    campaign.advance(guild, dt=1)
    assert g.order is None and g.routine.path == [0]


def test_a_routine_survives_a_save_in_the_middle_of_a_repeat(monkeypatch):
    _quiet(monkeypatch)
    g = _band("lumber_yard", "Hands")
    guild = _guild(g)
    cond = r.coins(r.own()) >= 500
    r.assign(guild, g, r.Routine([r.Repeat(cond, [r.Work(8), r.Rest(1)], until=True)]))
    campaign.advance(guild)
    assert g.routine.path == [0, 1]

    back = persist.group_from_dict(persist.group_to_dict(g))
    assert back.routine == g.routine and isinstance(back.routine.blocks[0].body, tuple)
    assert persist.group_from_dict(persist.group_to_dict(_band("city", "Plain"))).routine is None


def test_a_trade_sells_what_it_carries_and_buys_the_food_it_asked_for():
    g = _band("farm", "Traders", potatoes=1)
    g.members[0].give_to_pack("Lumber", 3)
    guild = _guild(g)
    r.assign(guild, g, r.Routine([r.Trade(sell=("Lumber",), buy=(("Potato", 1),), food_days=4)]))
    u = g.members[0]
    assert g.routine is None and u.count_of("Lumber") == 0
    assert u.count_of("Potato") == 5 and guild.shop("farm").stock["Lumber"] == 3


def test_a_trade_stops_the_routine_when_it_has_nothing_to_sell_or_no_shop_to_sell_at():
    g = _band("farm", "Empty")
    guild = _guild(g)
    r.assign(guild, g, r.Routine([r.Trade(sell=("Lumber",))]))
    assert g.routine.paused == "nothing to sell"

    road = _band("wilds", "Lost")
    r.assign(_guild(road), road, r.Routine([r.Trade(sell=("Lumber",))]))
    assert road.routine.paused == "no shop here"


def test_a_trade_stops_the_routine_when_the_purse_runs_dry():
    g = _band("farm", "Broke", money=0)
    guild = _guild(g)
    r.assign(guild, g, r.Routine([r.Trade(buy=(("Potato", 5),))]))
    assert g.routine.paused == "Out of money" and g.members[0].count_of("Potato") == 3


def _farm_visit():
    g = _band("farm", "Visitors", potatoes=1)
    g.members[0].give_to_pack("Lumber", 3)
    guild = _guild(g)
    return guild, g


def _after(guild, g):
    u = g.members[0]
    shop = guild.shop("farm")
    return (u.count_of("Lumber"), u.count_of("Potato"), u.money, shop.cash, dict(shop.stock),
            guild.total_spent, sorted(guild.items_sold_kinds))


def test_a_routine_trade_is_the_same_as_the_player_working_the_counter_by_hand():
    from gartok import trade
    by_hand, hand_group = _farm_visit()
    counter = trade.Counter(by_hand, list(hand_group.members), world.node("farm"))
    by_hand.autosell = {"Lumber"}
    counter._sell_marked()
    counter.selected = [("stock", "Potato")]
    counter.qty = {"Potato": 4}
    counter._buy_cart()

    routine, routine_group = _farm_visit()
    r.assign(routine, routine_group, r.Routine([r.Trade(sell=("Lumber",), buy=(("Potato", 4),))]))

    assert routine_group.routine is None
    assert _after(routine, routine_group) == _after(by_hand, hand_group)
