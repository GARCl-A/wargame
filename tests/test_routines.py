"""Routines: the blocks, the pointer, the pauses, and the order they hand the clock on `campaign.advance`."""

import random

from gartok import (
    campaign,
    data,
    economy,
    forced,
    gather,
    orders,
    persist,
    trade,
    unit_loadout,
    world,
)
from gartok import routines as r
from gartok.clock import Clock
from gartok.group import Group
from gartok.guild import Guild
from gartok.wagon import Wagon
from tests.helpers import standard_unit
from tests.test_solo import RECIPE, _crafter


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


def test_a_trade_with_a_spending_limit_buys_only_what_the_limit_pays_for():
    g = _band("farm", "Frugal", potatoes=0, money=1000)
    guild = _guild(g)
    price = economy.buy_price("Potato", trade.Counter(guild, list(g.members), world.node("farm")).deal)
    r.assign(guild, g, r.Routine([r.Trade(buy=(("Potato", 10),), max_spend=price * 3)]))
    assert g.routine is None and g.members[0].count_of("Potato") == 3


def test_a_gather_block_does_not_ask_for_the_economic_licence(monkeypatch):
    _quiet(monkeypatch)
    g = _band("lumber_yard", "Choppers")
    g.members[0].give_to_pack(gather.tool("lumber_yard"))
    guild = _guild(g)
    assert not guild.has_licence("lumber_yard")
    r.assign(guild, g, r.Routine([r.Gather(8)]))
    assert g.order.kind == "work" and g.order.gather
    campaign.advance(guild)
    assert g.members[0].count_of("Lumber") > 0 and g.routine is None


def test_a_craft_block_makes_the_recipe_and_stops_when_it_cannot(monkeypatch):
    monkeypatch.setattr(unit_loadout, "roll", lambda n, d: 9999)
    u = _crafter()
    g = Group([u], node="smith", name="Smiths", leader=u)
    guild = _guild(g)
    r.assign(guild, g, r.Routine([r.Craft(RECIPE, 4), r.Rest(1)]))
    assert g.order.kind == "solo" and g.order.recipe == RECIPE
    campaign.advance(guild)
    assert u.has_item(RECIPE) and g.order.kind == "rest"

    bare = _crafter(material=False)
    broke = Group([bare], node="smith", name="Bare", leader=bare)
    r.assign(_guild(broke), broke, r.Routine([r.Craft(RECIPE, 4)]))
    assert broke.routine.paused and broke.order is None


def _cook(node, **setup):
    u = standard_unit()
    u.give_to_pack("Meat")
    g = Group([u], node=node, name="Cooks", leader=u)
    guild = _guild(g)
    if setup.pop("house_oven", False):
        guild.house.owned, guild.house.oven = True, True
    for key, value in setup.items():
        setattr(guild, key, value)
    return guild, g, u


def test_a_craft_block_needs_the_station_a_player_would_use(monkeypatch):
    monkeypatch.setattr(unit_loadout, "roll", lambda n, d: 9999)
    u = _crafter()
    g = Group([u], node="city", name="Smiths", leader=u)
    r.assign(_guild(g), g, r.Routine([r.Craft(RECIPE, 4)]))
    assert g.order is None and "no forge station here" in g.routine.paused


def test_a_craft_block_cooks_only_where_there_is_a_hearth(monkeypatch):
    monkeypatch.setattr(unit_loadout, "roll", lambda n, d: 9999)
    for node, setup in (("city", {}), ("wilds_territory", {}), ("farm", {"claim_oven": True})):
        guild, g, _ = _cook(node, **setup)
        r.assign(guild, g, r.Routine([r.Craft("Roast Meat", 4)]))
        assert g.order is None and "no cooking station here" in g.routine.paused, node
    for node, setup in (("city", {"house_oven": True}), ("wilds_territory", {"claim_oven": True}),
                        ("wilds_territory", {"wilds_claim_campfire": True})):
        guild, g, u = _cook(node, **setup)
        r.assign(guild, g, r.Routine([r.Craft("Roast Meat", 4)]))
        assert g.order.kind == "solo", (node, setup)
        campaign.advance(guild)
        assert u.count_of("Roast Meat") == 1


def test_a_craft_block_uses_a_burning_field_campfire(monkeypatch):
    monkeypatch.setattr(unit_loadout, "roll", lambda n, d: 9999)
    guild, g, u = _cook("farm")
    g.campfire_node, g.campfire_expires = "farm", guild.clock.seconds + 4 * 3600
    r.assign(guild, g, r.Routine([r.Craft("Roast Meat", 4)]))
    assert g.order.kind == "solo"


def test_a_craft_block_needs_someone_who_knows_the_recipe():
    u = standard_unit()
    g = Group([u], node="smith", name="Smiths", leader=u)
    r.assign(_guild(g), g, r.Routine([r.Craft(RECIPE, 4)]))
    assert g.order is None and "nobody in the group knows" in g.routine.paused


def _hauler(node="city", lumber=5):
    u = standard_unit()
    u.give_to_pack("Potato", 3)
    if lumber:
        u.give_to_pack("Lumber", lumber)
    g = Group([u], node=node, name="Haulers", leader=u)
    return _guild(g), g, u


def test_a_repair_block_mends_the_named_wagon_with_the_desks_rules(monkeypatch):
    monkeypatch.setattr(data, "d20", lambda: 20)
    guild, g, u = _hauler()
    cart = Wagon("Cart", hp=1, nickname="Ironside")
    g.add_wagon(cart)
    r.assign(guild, g, r.Routine([r.Repair("ironside"), r.Rest(1)]))
    assert g.order.kind == "work" and g.order.task == "repair" and u.count_of("Lumber") == 5 - cart.repair_cost
    campaign.advance(guild)
    assert cart.hp > 1 and g.order.kind == "rest"


def test_a_repair_block_reaches_a_wagon_parked_in_the_garage_here(monkeypatch):
    monkeypatch.setattr(data, "d20", lambda: 20)
    guild, g, u = _hauler()
    guild.house.owned = True
    parked = Wagon("Cart", hp=1, nickname="Spare")
    guild.house.garage.tier, guild.house.garage.wagons = 1, [parked]
    r.assign(guild, g, r.Routine([r.Repair("Spare")]))
    campaign.advance(guild)
    assert parked.hp > 1 and g.routine is None
    elsewhere, e, _ = _hauler(node="smith")
    e.add_wagon(Wagon("Cart", hp=1, nickname="Spare"))
    r.assign(elsewhere, e, r.Routine([r.Repair("Nobody")]))
    assert "no wagon called Nobody" in e.routine.paused


def test_a_repair_block_stops_short_of_lumber_and_passes_a_sound_wagon():
    guild, g, u = _hauler(lumber=0)
    g.add_wagon(Wagon("Cart", hp=1, nickname="Ironside"))
    r.assign(guild, g, r.Routine([r.Repair("Ironside")]))
    assert "Lumber" in g.routine.paused and g.order is None
    sound, s, _ = _hauler()
    s.add_wagon(Wagon("Cart", nickname="Ironside"))
    r.assign(sound, s, r.Routine([r.Repair("Ironside"), r.Rest(1)]))
    assert s.order.kind == "rest"


def test_store_and_fetch_move_goods_between_the_packs_and_the_house():
    guild, g, u = _hauler()
    guild.house.owned = True
    r.assign(guild, g, r.Routine([r.Store("house", "Lumber", 3), r.Rest(1)]))
    assert u.count_of("Lumber") == 2 and guild.house.stash.count_of("Lumber") == 3
    g.order, g.routine = None, None
    r.assign(guild, g, r.Routine([r.Fetch("house", "Lumber"), r.Rest(1)]))
    assert u.count_of("Lumber") == 5 and guild.house.stash.count_of("Lumber") == 0


def test_store_and_fetch_stop_where_there_is_no_stash_or_no_room():
    guild, g, u = _hauler()
    r.assign(guild, g, r.Routine([r.Store("house", "Lumber")]))
    assert "no house here" in g.routine.paused
    guild.house.owned = True
    guild.house.stash.capacity = 0
    r.resume(guild, g)
    assert "no room" in g.routine.paused and u.count_of("Lumber") == 5
    g.routine = None
    r.assign(guild, g, r.Routine([r.Fetch("house", "Lumber")]))
    assert "no Lumber in the house" in g.routine.paused
    g.routine = None
    r.assign(guild, g, r.Routine([r.Store("bank", "Lumber")]))
    assert "no bank here" in g.routine.paused


def test_a_fetch_is_cut_to_what_the_packs_carry():
    guild, g, u = _hauler(lumber=0)
    guild.house.owned = True
    guild.house.stash.put("Lumber", 400)
    r.assign(guild, g, r.Routine([r.Fetch("house", "Lumber"), r.Rest(1)]))
    got = u.count_of("Lumber")
    assert 0 < got < 400 and guild.house.stash.count_of("Lumber") == 400 - got


def test_a_parked_wagons_cargo_can_be_fetched_and_stored_back():
    guild, g, u = _hauler(lumber=0)
    guild.house.owned = True
    parked = Wagon("Cart", nickname="Spare")
    parked.stash.put("Lumber", 4)
    guild.house.garage.tier, guild.house.garage.wagons = 1, [parked]
    r.assign(guild, g, r.Routine([r.Fetch("garage", "Lumber"), r.Rest(1)]))
    assert u.count_of("Lumber") == 4 and parked.stash.count_of("Lumber") == 0


def test_the_new_blocks_survive_the_save():
    blocks = (r.Repair("Ironside"), r.Store("house", "Lumber", 2), r.Fetch("bank", "Lumber"))
    assert r.load(r.dump(r.Routine(blocks))).blocks == blocks


SPELL = "light_globe"
SCROLL = "Scroll of Light Globe"


def _student(node="tavern", money=300, scroll=True, name="Scholars"):
    u = standard_unit()
    u.money = money
    u.magic_sources = ["nature"]
    u.give_to_pack("Potato", 1)
    if scroll:
        u.give_to_pack(SCROLL)
    return Group([u], node=node, name=name, leader=u)


def test_a_study_block_boards_the_group_for_its_days_and_pays_the_rent(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(data, "roll", lambda n, d: 10)
    g = _student()
    guild = _guild(g)
    u = g.members[0]
    r.assign(guild, g, r.Routine([r.Study(SPELL, 3)]))
    assert g.order.kind == "garrison" and g.order.job == "study" and u.study_target == SPELL

    campaign.advance(guild)
    assert g.routine is None and g.order is None
    assert u.money == 300 - 3 * economy.TAVERN_STUDY_COST_PER_DAY
    assert u.study_progress == {SPELL: 30} and u.count_of("Potato") == 1           # the rooms include the meal


def test_study_passes_one_after_another_keep_their_progress_until_the_spell_is_mastered(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(data, "roll", lambda n, d: 20)
    g = _student()
    guild = _guild(g)
    u = g.members[0]
    r.assign(guild, g, r.Routine([r.Study(SPELL, 1)] * 8))
    while g.routine is not None and not g.routine.paused:
        campaign.advance(guild)

    assert SPELL in u.spells_known and u.study_target is None
    assert g.routine.paused == "nobody can study that"


def test_a_study_block_stops_where_there_are_no_rooms_nothing_to_learn_or_no_coin(monkeypatch):
    _quiet(monkeypatch)
    for band, why in ((_student("market"), "there are no rooms to study in here"),
                      (_student(scroll=False), "nobody can study that"),
                      (_student(money=10), "no one can pay for the rooms")):
        guild = _guild(band)
        r.assign(guild, band, r.Routine([r.Study(SPELL, 2)]))
        assert band.routine.paused == why and band.order is None


def test_the_book_refuses_a_study_of_what_does_not_exist_or_for_no_days():
    from gartok import routine_book
    guild = _guild(_student())
    for block in (r.Study("not_a_spell", 1), r.Study(SPELL, 0)):
        try:
            routine_book.check(guild, (block,))
            assert False, "expected a ValueError"
        except ValueError:
            pass
    routine_book.check(guild, (r.Study(SPELL, 2), r.Study("Dwarvish", 1)))


def test_the_group_studies_earns_and_comes_back_to_study(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(data, "roll", lambda n, d: 20)
    monkeypatch.setattr(economy, "LUMBER_WAGE", 10)       # the loop is what is tested, not the day labour's balance
    g = _student(money=60)
    guild = _guild(g)
    u = g.members[0]
    r.assign(guild, g, r.Routine([r.Repeat(r.coins(r.own()) >= 0, [
        r.Repeat(r.coins(r.own()) >= 30, [r.Study(SPELL, 1)]),
        r.Trade(food_days=6),
        r.Travel("lumber_yard"),
        r.Repeat(r.coins(r.own()) < 60, [r.Work(8)]),
        r.Travel("tavern"),
    ])]))
    seen_at = set()
    for _ in range(4000):
        if g.routine is None or g.routine.paused:
            break
        campaign.advance(guild)
        seen_at.add(g.node)
        assert u.hunger_level == 0

    assert {"tavern", "lumber_yard"} <= seen_at                      # it went to earn and came back
    assert SPELL in u.spells_known
    assert g.routine.paused == "nobody can study that"
