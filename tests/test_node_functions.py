from pathlib import Path

import pytest

from gartok import node_functions, orders, persist, world
from gartok.guild import Guild
from gartok.shop import Shop
from gartok.unit import Unit


def test_every_function_has_an_opener_and_its_order_kind_is_interactive():
    assert node_functions.order_kinds() <= orders.INTERACTIVE_KINDS
    assert orders.INTERACTIVE_KINDS - node_functions.order_kinds() == {"arena"}


def test_every_node_lists_only_functions_that_exist():
    for n in world.NODES:
        assert set(n.functions) <= set(node_functions.FUNCTIONS), n.id


def test_a_function_that_hosts_another_hides_its_button():
    library = world.node("library")
    assert library.has("shop") and library.has("library")
    assert [f.id for f in node_functions.offered(library)] == ["library"]
    assert [f.id for f in node_functions.offered(world.node("market"))] == ["shop"]


def test_a_node_with_independent_functions_gets_both_buttons():
    node = world.Node("t", "T", "town", (0, 0), "x", functions=("prison", "hunt"))
    assert [f.id for f in node_functions.offered(node)] == ["prison", "hunt"]


def test_a_nodes_hub_lists_a_tab_per_function():
    from gartok.web.hub_session import tabs_for

    def keys(node_id):
        return [k for k, _ in tabs_for("market", world.node(node_id))]
    assert keys("tavern") == ["shop", "recruits", "rooms", "perform"]
    assert keys("farm") == ["shop", "stable"]
    assert keys("lumber_yard") == ["shop", "work", "gather"]


def test_every_shop_node_has_its_till_refilled_each_day():
    guild = Guild([Unit("player")])
    shop_nodes = [n.id for n in world.NODES if n.has("shop")]
    assert {"market", "library"} <= set(shop_nodes)
    for node_id in shop_nodes:
        guild.shop(node_id).cash = 0
    guild._daily_upkeep()
    for node_id in shop_nodes:
        assert guild.shop(node_id).cash > 0, node_id


def test_each_shop_keeps_its_own_cash_and_shelf():
    guild = Guild([Unit("player")])
    guild.shop("market").cash = 7
    guild.shop("market").stock["Torch"] = 0
    assert guild.shop("library").cash != 7
    assert guild.shop("library").stock["Paper"] > 0 and "Torch" not in guild.shop("library").stock


def test_a_shop_round_trips_through_a_save():
    shop = Shop(cash=42, stock={"Vial": 1})
    back = Shop.from_dict(shop.to_dict())
    assert (back.cash, back.stock) == (42, {"Vial": 1})


def test_shops_survive_a_save_round_trip():
    slot = "testworld_shops"
    guild = Guild([Unit("player")], node="city")
    guild.shop("library").cash = 321
    guild.shop("library").stock["Vial"] = 4
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot)
    finally:
        persist.delete_world(slot)
    assert back.shop("library").cash == 321 and back.shop("library").stock["Vial"] == 4


def test_a_save_of_the_old_shape_does_not_load():
    slot = "testworld_old_shops"
    try:
        persist.save_game(slot, Guild([Unit("player")], node="city"))
        path = Path(persist.save_path(slot))
        path.write_text(path.read_text(encoding="utf-8").replace(
            f'"save_version": {persist.SAVE_VERSION}', '"save_version": 1'), encoding="utf-8")
        with pytest.raises(persist.SaveVersionError):
            persist.load_game(slot)
    finally:
        persist.delete_world(slot)


def test_shop_stock_reaches_the_market_screen():
    from gartok.trade import Counter
    shopper = Unit("player")
    guild = Guild([shopper])
    node = world.node("library")
    guild.shop(node.id).stock["Vial"] = 0
    screen = Counter(guild, [shopper], node)
    assert screen._stock_of("Vial") == 0
    assert Counter(guild, [shopper], world.node("apothecary"))._stock_of("Vial") > 0
