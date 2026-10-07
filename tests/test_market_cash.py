"""The market pays out of its own cash: spending fills it, selling drains it, a day refills it."""

import os

from gartok import economy, items, persist, world
from gartok.guild import Guild
from gartok.market_screen import MarketScreen
from gartok.unit import Unit

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

COPPER = items.COIN_ITEM
NODE = world.node("market")


def _shopper(copper=0, *goods):
    u = Unit("player")
    u._base_inventory = []
    if copper:
        u.give_to_pack(COPPER, copper)
    for g in goods:
        u.give_to_pack(g)
    return u


def _screen(u, cash=None):
    guild = Guild([u])
    if cash is not None:
        guild.market_cash[NODE.id] = cash
    return MarketScreen(None, guild, [u], NODE, lambda: None)


def _pick(s, u, name):
    return [(u, i) for i, (n, _q) in enumerate(u._base_inventory) if n == name]


def test_a_fresh_market_starts_with_its_opening_cash():
    assert Guild([_shopper()]).market_cash_at(NODE.id) == economy.MARKET_CASH_START


def test_the_daily_refill_stops_at_the_cap_and_never_takes_cash_away():
    cap, step = economy.MARKET_CASH_CAP, economy.MARKET_CASH_REGEN
    assert economy.regen_market_cash(100) == 100 + step
    assert economy.regen_market_cash(cap - 1) == cap
    assert economy.regen_market_cash(cap + 200) == cap + 200


def test_a_day_refills_every_market():
    guild = Guild([_shopper()])
    guild.market_cash[NODE.id] = 0
    guild._daily_upkeep()
    assert guild.market_cash_at(NODE.id) == economy.MARKET_CASH_REGEN


def test_spending_at_the_market_fills_its_cash():
    u = _shopper(500)
    s = _screen(u, cash=0)
    s.selected = [("stock", "Dagger")]
    s._buy(u, ["Dagger"])
    assert s.guild.market_cash_at(NODE.id) == economy.buy_price("Dagger", s.deal)


def test_selling_drains_the_market_cash_by_what_it_paid():
    u = _shopper(0, "Rope")
    s = _screen(u, cash=500)
    s.selected = _pick(s, u, "Rope")
    paid = economy.sell_price("Rope", s.deal)
    s._sell()
    assert u.money == paid
    assert s.guild.market_cash_at(NODE.id) == 500 - paid


def test_a_sale_above_what_the_market_holds_is_refused_whole():
    u = _shopper(0, "Rope")
    price = economy.sell_price("Rope", [])
    s = _screen(u, cash=price - 1)
    s.selected = _pick(s, u, "Rope")
    s._sell()
    assert u.money == 0 and u.has_item("Rope")
    assert s.guild.market_cash_at(NODE.id) == price - 1
    assert "only has" in s.notice


def test_the_market_cash_survives_a_save_round_trip():
    slot = "testworld"
    if os.path.exists(persist.save_path(slot)):
        return
    guild = Guild([_shopper()], node="city")
    guild.market_cash[NODE.id] = 321
    try:
        persist.save_game(slot, guild)
        assert persist.load_game(slot).market_cash_at(NODE.id) == 321
    finally:
        persist.delete_world(slot)


def test_an_old_save_without_market_cash_loads_with_the_opening_cash():
    assert Guild([_shopper()], node="city").market_cash == {}
