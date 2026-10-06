"""The pack row's ⋮ button: it opens a menu in the market and in the stash
screens (it used to be drawn there with nothing behind it), and the party's
coin there is real items in real packs."""

import os
import random

import pygame

from gartok import economy, items, world
from gartok.bank_screen import BankScreen
from gartok.guild import Guild
from gartok.market_screen import MarketScreen
from tests.helpers import Unit


def _surface():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((1, 1))
    return pygame.Surface((1400, 900))


def _unit(*stacks, gold=0):
    u = Unit("player")
    u._base_inventory = []
    for name, qty in stacks:
        u.give_to_pack(name, qty)
    u.gold = gold
    return u


def _market(*units):
    random.seed(2)
    s = MarketScreen(None, Guild(list(units)), list(units), world.node("city"), lambda: None)
    s.mouse = (0, 0)
    surf = _surface()
    s.draw(surf)
    return s, surf


def _click(s, surf, pos):
    s.mouse = pos
    s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
    s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos))
    s.draw(surf)


def _idx(u, name):
    return next(i for i, (n, _) in enumerate(u._base_inventory) if n == name)


def _count(u, name):
    return sum(q for n, q in u._base_inventory if n == name)


def _dots_of(s, u, name):
    return next(r for r, owner, i in s._dots_hits if owner is u and u._base_inventory[i][0] == name)


def test_market_dots_open_a_sell_menu_and_sell_one():
    u = _unit(("Rope", 3))
    s, surf = _market(u)
    _click(s, surf, _dots_of(s, u, "Rope").center)
    labels = [lbl for _, lbl, _ in s.menu["rows"]]
    assert labels[0].startswith("sell 1") and labels[1].startswith("sell all x3")
    _click(s, surf, s.menu["hits"][0][0].center)
    assert s.menu is None
    assert _count(u, "Rope") == 2 and u.gold == economy.sell_price("Rope")


def test_market_menu_sell_all_empties_the_stack():
    u = _unit(("Rope", 3))
    s, surf = _market(u)
    _click(s, surf, _dots_of(s, u, "Rope").center)
    _click(s, surf, s.menu["hits"][1][0].center)
    assert _count(u, "Rope") == 0 and u.gold == economy.sell_price("Rope") * 3


def test_a_sale_pays_the_seller_not_the_whole_party():
    seller, other = _unit(("Rope", 1), gold=10), _unit(gold=90)
    s, surf = _market(seller, other)
    _click(s, surf, _dots_of(s, seller, "Rope").center)
    _click(s, surf, s.menu["hits"][0][0].center)
    assert seller.gold == 10 + economy.sell_price("Rope") and other.gold == 90


def test_the_coin_stack_has_a_menu_that_moves_it_but_never_sells_it():
    a, b = _unit(gold=50), _unit()
    s, surf = _market(a, b)
    _click(s, surf, _dots_of(s, a, items.COIN_ITEM).center)
    assert [kind for _, kind, _ in s.menu["hits"]] == ["member"]
    _click(s, surf, s.menu["hits"][0][0].center)
    assert a.gold == 0 and b.gold == 50


def test_selling_a_selection_that_holds_coins_skips_the_coins():
    u = _unit(("Rope", 1), gold=30)
    s, surf = _market(u)
    s.sel = [(u, _idx(u, items.COIN_ITEM)), (u, _idx(u, "Rope"))]
    s._sell()
    assert u.gold == 30 + economy.sell_price("Rope")


def test_clicking_elsewhere_dismisses_the_menu_without_selling():
    u = _unit(("Rope", 1))
    s, surf = _market(u)
    _click(s, surf, _dots_of(s, u, "Rope").center)
    assert s.menu is not None
    _click(s, surf, (2, 2))
    assert s.menu is None and _count(u, "Rope") == 1


def test_buying_is_paid_out_of_real_coin_in_proportion_to_what_each_carries():
    rich, poor = _unit(gold=300), _unit(gold=100)
    s, _ = _market(rich, poor)
    assert s.purse == 400
    s.purse -= 40
    assert (rich.gold, poor.gold) == (270, 90)
    assert s.purse == 360


def _bank(party):
    s = BankScreen(None, Guild(list(party)), party, on_done=lambda: None)
    s.mouse = (0, 0)
    surf = _surface()
    s.draw(surf)
    return s, surf


def test_stash_menu_sends_a_stack_to_the_chest_or_a_pinned_member():
    random.seed(4)
    a, b = _unit(("Rope", 1), gold=200), _unit(gold=200)
    s, surf = _bank([a, b])
    s._run_service("rent")
    s.draw(surf)

    pick = next((o, i) for _, o, i in s._dots_hits if o is a and a._base_inventory[i][0] == "Rope")
    s._open_menu((100, 100), [pick])
    assert [lbl for _, lbl, _ in s.menu["rows"]] == [f"to {s.LABEL}", f"to {b.name}"]

    s.draw(surf)
    _click(s, surf, s.menu["hits"][1][0].center)
    assert _count(b, "Rope") == 1 and _count(a, "Rope") == 0

    pick = next((o, i) for _, o, i in s._dots_hits if o is b and b._base_inventory[i][0] == "Rope")
    s._open_menu((100, 100), [pick])
    s.draw(surf)
    _click(s, surf, s.menu["hits"][0][0].center)
    assert s.guild.bank.items == [("Rope", 1)]


def test_stash_coins_move_like_any_item_and_the_rent_comes_out_of_the_packs():
    a, b = _unit(gold=300), _unit(gold=300)
    s, surf = _bank([a, b])
    s._run_service("rent")
    assert a.gold + b.gold == 600 - economy.BANK_CHEST_PRICE
    s.draw(surf)
    pick = next((o, i) for _, o, i in s._dots_hits if o is a and a._base_inventory[i][0] == items.COIN_ITEM)
    s._open_menu((100, 100), [pick])
    s.draw(surf)
    before = a.gold + b.gold
    _click(s, surf, s.menu["hits"][0][0].center)
    assert any(n == items.COIN_ITEM for n, _ in s.guild.bank.items)
    assert a.gold + b.gold + sum(q for n, q in s.guild.bank.items if n == items.COIN_ITEM) == before


def test_stash_menu_is_empty_for_nothing_pickable():
    s, _ = _bank([_unit()])
    assert s._menu_rows([]) == []


def test_spread_coin_is_exact_and_capped_at_what_the_party_holds():
    a, b, c = _unit(gold=7), _unit(gold=5), _unit(gold=1)
    economy.spread_coin([a, b, c], -6)
    assert a.gold + b.gold + c.gold == 7
    economy.spread_coin([a, b, c], -100)
    assert a.gold + b.gold + c.gold == 0
    economy.spread_coin([a, b, c], 10)
    assert a.gold + b.gold + c.gold == 10


def test_market_menu_acts_on_the_whole_selection_when_the_row_is_in_it():
    a, b = _unit(("Rope", 2), ("Torch", 1)), _unit()
    s, surf = _market(a, b)
    rope, torch = (a, _idx(a, "Rope")), (a, _idx(a, "Torch"))
    s.sel, s._sel_qty = [rope, torch], {rope: 2, torch: 1}
    s.draw(surf)
    _click(s, surf, _dots_of(s, a, "Rope").center)
    labels = [lbl for _, lbl, _ in s.menu["rows"]]
    assert labels[0].startswith("sell selected") and labels[1] == f"to {b.name}"
    _click(s, surf, s.menu["hits"][0][0].center)
    assert _count(a, "Rope") == 0 and _count(a, "Torch") == 0
    assert a.gold == economy.sell_price("Rope") * 2 + economy.sell_price("Torch")


def test_market_menu_sends_the_whole_selection_to_another_member():
    a, b = _unit(("Rope", 1), ("Torch", 1)), _unit()
    s, surf = _market(a, b)
    rope, torch = (a, _idx(a, "Rope")), (a, _idx(a, "Torch"))
    s.sel, s._sel_qty = [rope, torch], {rope: 1, torch: 1}
    s.draw(surf)
    _click(s, surf, _dots_of(s, a, "Torch").center)
    _click(s, surf, next(r for r, k, arg in s.menu["hits"] if k == "member"
                         ).center)
    assert _count(b, "Rope") == 1 and _count(b, "Torch") == 1 and _count(a, "Rope") == 0


def test_market_menu_on_an_unselected_row_ignores_the_selection():
    a = _unit(("Rope", 1), ("Torch", 1))
    s, surf = _market(a)
    s.sel, s._sel_qty = [(a, _idx(a, "Torch"))], {}
    s.draw(surf)
    _click(s, surf, _dots_of(s, a, "Rope").center)
    assert s.menu["rows"][0][0] == "sell"
