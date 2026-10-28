"""The shop's counter (`trade.py`): the rules both front-ends trade through, with no window."""

import subprocess
import sys

from gartok import economy, items, trade, world
from gartok.group import Group
from gartok.guild import Guild
from gartok.library_screen import LibraryScreen
from gartok.market_screen import MarketScreen
from tests.helpers import standard_unit


def _band(node_id, copper=0):
    u = standard_unit()
    if copper:
        u.give_to_pack(items.COIN_ITEM, copper)
    guild = Guild([u])
    guild.groups = [Group([u], node_id)]
    return guild, u


def test_the_counter_loads_without_pygame():
    code = "import sys; sys.modules['pygame'] = None; import gartok.trade"
    subprocess.run([sys.executable, "-c", code], check=True)


def test_a_counter_buys_into_the_roomiest_pack_and_pays_from_the_purse():
    guild, u = _band("market", copper=50)
    c = trade.counter_for(guild, [u], world.node("market"))
    name = next(n for _l, key, names in c.get_categories() if key == "kit" for n in names
                if c._stock_of(n) and economy.buy_price(n, c.deal) <= 50)
    price = economy.buy_price(name, c.deal)
    c.selected = [("stock", name)]
    c._buy_cart()
    assert u.count_of(name) == 1
    assert c.purse == 50 - price
    assert guild.total_spent == price


def test_a_counter_sells_a_pack_stack_into_the_sellers_purse():
    guild, u = _band("market")
    u.give_to_pack("Torch", 2)
    c = trade.counter_for(guild, [u], world.node("market"))
    loc = next(i for i, (n, _q) in enumerate(u._base_inventory) if n == "Torch")
    c.selected, c._sel_qty = [(u, loc)], {(u, loc): 1}
    c._sell()
    assert u.count_of("Torch") == 1
    assert u.money == economy.sell_price("Torch", c.deal)


def test_the_library_keeps_its_own_counter():
    guild, u = _band("library")
    c = trade.counter_for(guild, [u], world.node("library"))
    assert isinstance(c, trade.LibraryCounter)
    assert [key for _l, key, _n in c.get_categories()] == ["supplies"]
    guild.reputation["library"] = 1
    c.sync_group()
    assert [key for _l, key, _n in c.get_categories()] == ["supplies", "dictionaries"]


def test_the_pygame_screens_are_the_same_counter():
    guild, u = _band("library")
    assert isinstance(MarketScreen(None, guild, [u], world.node("market"), lambda: None), trade.Counter)
    assert isinstance(LibraryScreen(None, guild, [u], world.node("library"), lambda: None), trade.LibraryCounter)
