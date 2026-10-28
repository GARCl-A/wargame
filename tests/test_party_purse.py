"""The party's coin at a counter is real items in real packs: a price comes out in proportion to what
each member carries, a sale skips the coins, and a stash rent comes out of the packs."""

import random

from gartok import economy, items, world
from gartok.guild import Guild
from gartok.trade import Counter
from gartok.vault import BankVault
from tests.helpers import Unit


def _unit(*stacks, gold=0):
    u = Unit("player")
    u._base_inventory = []
    for name, qty in stacks:
        u.give_to_pack(name, qty)
    u.money = gold
    return u


def _market(*units):
    random.seed(2)
    return Counter(Guild(list(units)), list(units), world.node("city"))


def _idx(u, name):
    return next(i for i, (n, _) in enumerate(u._base_inventory) if n == name)


def test_selling_a_selection_that_holds_coins_skips_the_coins():
    u = _unit(("Rope", 1), gold=30)
    s = _market(u)
    s.selected = [(u, _idx(u, items.COIN_ITEM)), (u, _idx(u, "Rope"))]
    s._sell()
    assert u.money == 30 + economy.sell_price("Rope")


def test_buying_is_paid_out_of_real_coin_in_proportion_to_what_each_carries():
    rich, poor = _unit(gold=300), _unit(gold=100)
    s = _market(rich, poor)
    assert s.purse == 400
    s.purse -= 40
    assert (rich.money, poor.money) == (270, 90)
    assert s.purse == 360


def test_stash_coins_move_like_any_item_and_the_rent_comes_out_of_the_packs():
    a, b = _unit(gold=300), _unit(gold=300)
    s = BankVault(Guild([a, b]), [a, b])
    s._run_service("rent")
    assert a.money + b.money == 600 - economy.BANK_CHEST_PRICE
    before = a.money + b.money
    s.selected = [(a, _idx(a, items.COIN_ITEM))]
    s._give_many(s.OWNER, s.OWNER)
    assert any(n == items.COIN_ITEM for n, _ in s.guild.bank.items)
    assert a.money + b.money + sum(q for n, q in s.guild.bank.items if n == items.COIN_ITEM) == before


def test_spread_coin_is_exact_and_capped_at_what_the_party_holds():
    a, b, c = _unit(gold=7), _unit(gold=5), _unit(gold=1)
    economy.spread_coin([a, b, c], -6)
    assert a.money + b.money + c.money == 7
    economy.spread_coin([a, b, c], -100)
    assert a.money + b.money + c.money == 0
    economy.spread_coin([a, b, c], 10)
    assert a.money + b.money + c.money == 10
