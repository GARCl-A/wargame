from gartok import economy, world
from gartok.guild import Guild
from gartok.shop import Shop
from gartok.unit import Unit

TOWN_SHOPS = economy.TOWN_SHOPS


def test_every_item_the_town_sells_is_on_the_shelf_of_one_of_its_shops():
    on_shelves = {n for shop in TOWN_SHOPS for n in economy.targets_of(shop)}
    assert set(economy.MARKET_STOCK) == on_shelves


def test_each_shop_is_a_node_that_offers_it():
    for shop in TOWN_SHOPS:
        assert world.node(shop).has("shop"), shop
        assert economy.targets_of(shop), shop


def test_a_shelf_item_belongs_to_one_shop_and_each_work_node_has_its_own_shelf():
    assert set(economy.targets_of("mine")) == set(economy.MINE_SUPPLIES)
    assert set(economy.targets_of("lumber_yard")) == set(economy.YARD_SUPPLIES)
    assert set(economy.targets_of("library")) == set(economy.LIBRARY_SUPPLIES)
    town = [n for shelf in TOWN_SHOPS for n in economy.SHELVES[shelf]]
    assert len(town) == len(set(town))


def test_the_scarce_items_open_at_their_target():
    for name, count in economy.STOCK.items():
        shop = next(Shop(node_id=n) for n in TOWN_SHOPS if name in economy.targets_of(n))
        assert shop.stock[name] == count == shop.targets[name][0]


def test_a_shelf_walks_back_to_its_target_by_the_rate():
    shop = Shop(node_id="smith")
    shop.stock["Axe"] = 0
    shop.refill()
    assert shop.stock["Axe"] == 1
    farm = Shop(node_id="farm")
    farm.stock["Potato"] = 0
    farm.refill()
    assert farm.stock["Potato"] == 10


def test_a_slow_item_earns_a_unit_over_several_days():
    shop = Shop(node_id="smith")
    shop.stock["Rapier"] = 0
    days = 0
    while shop.stock["Rapier"] == 0:
        shop.refill()
        days += 1
    assert days == 4 and shop.stock["Rapier"] == 1     # 0.3 a day: 0.3 0.6 0.9 1.2
    for _ in range(30):
        shop.refill()
    assert shop.stock["Rapier"] == 2                   # never past the target


def test_a_surplus_the_player_sold_walks_back_down_and_hide_stays():
    smith, tanner = Shop(node_id="smith"), Shop(node_id="tanner")
    smith.stock["Dagger"] = 20
    tanner.stock["1sqm Hide"] = 5
    smith.refill()
    tanner.refill()
    assert smith.stock["Dagger"] == 18 and tanner.stock["1sqm Hide"] == 5


def test_progress_and_stock_survive_a_save():
    shop = Shop(node_id="smith")
    shop.stock["Rapier"] = 0
    shop.refill()
    back = Shop.from_dict(shop.to_dict(), "smith")
    assert back.stock == shop.stock and back.progress == shop.progress


def test_a_saved_shop_with_a_short_shelf_fills_the_rest_at_target():
    back = Shop.from_dict({"cash": 5, "stock": {"Vial": 1}}, "apothecary")
    assert back.stock["Vial"] == 1 and back.stock["First Aid Kit"] == 5


def test_the_guild_makes_each_shop_with_its_own_shelf():
    guild = Guild([Unit("player")])
    assert "Iron Ore" in guild.shop("mine").stock and "Iron Ore" not in guild.shop("market").stock


def test_an_item_sold_to_a_shop_off_its_shelf_is_listed_and_resold():
    from gartok import world
    from gartok.market_screen import MarketScreen
    seller = Unit("player")
    guild = Guild([seller])
    seller.give_to_pack("Iron Ore")
    node = world.node("lumber_yard")
    screen = MarketScreen(None, guild, [seller], node, lambda: None)
    assert "Iron Ore" not in [n for _, _, names in screen.get_categories() for n in names]
    screen.selected = [(seller, i) for i, (n, _q) in enumerate(seller._base_inventory) if n == "Iron Ore"]
    screen._sell()
    shop = guild.shop("lumber_yard")
    assert shop.stock["Iron Ore"] == 1 and shop.strays() == ["Iron Ore"]
    assert "Iron Ore" in [n for _, _, names in screen.get_categories() for n in names]
    assert screen._stock_of("Iron Ore") == 1


def test_a_stray_stays_on_the_shelf_and_the_library_lists_it():
    from gartok import world
    from gartok.library_screen import LibraryScreen
    seller = Unit("player")
    guild = Guild([seller])
    shop = guild.shop("library")
    shop.add("Dagger", 2)
    for _ in range(5):
        shop.refill()
    assert shop.stock["Dagger"] == 2
    screen = LibraryScreen(None, guild, [seller], world.node("library"), lambda: None)
    assert ("RESALE", "resale", ["Dagger"]) in screen.get_categories()
