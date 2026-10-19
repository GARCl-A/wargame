"""The Market's auto-sell marks: mark an item kind once, SELL MARKED takes it from every pack."""

import os

import pygame

from gartok import economy, items, persist, world
from gartok.guild import Guild
from gartok.market_screen import MarketScreen
from gartok.ui.tokens import fonts as ui_fonts
from gartok.unit import Unit

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

COPPER = items.COIN_ITEM
NODE = world.node("market")


def _unit(*goods):
    u = Unit("player")
    u._base_inventory = []
    for name, qty in goods:
        u.give_to_pack(name, qty)
    return u


def _screen(*units, marked=()):
    guild = Guild(list(units))
    guild.autosell = set(marked)
    guild.shop(NODE.id).cash = 10_000
    return MarketScreen(None, guild, list(units), NODE, lambda: None)


def _count(units, name):
    return sum(u.count_of(name) for u in units)


def test_sell_marked_takes_every_marked_stack_from_every_shopper_and_keeps_the_rest():
    a, b = _unit(("Dagger", 2), ("Club", 1)), _unit(("Dagger", 1), ("Rope", 1))
    s = _screen(a, b, marked={"Dagger"})
    before = a.money + b.money
    s._sell_marked()
    assert _count([a, b], "Dagger") == 0
    assert (a.count_of("Club"), b.count_of("Rope")) == (1, 1)
    assert a.money + b.money - before == economy.sell_price("Dagger", s.deal) * 3


def test_autosell_includes_wagons_and_pack_animals():
    from gartok.wagon import Wagon
    a = _unit(("Club", 1))
    guild = Guild([a])
    guild.autosell = {"Dagger"}
    guild.shop(NODE.id).cash = 10_000
    grp = guild.groups[0]
    cart = Wagon("Cart")
    cart.give_to_pack("Dagger", 4)
    grp.wagons.append(cart)
    s = MarketScreen(None, guild, [a], NODE, lambda: None)
    assert cart in s.stores
    assert s._marked_total() == economy.sell_price("Dagger", s.deal) * 4
    s._sell_marked()
    assert cart.count_of("Dagger") == 0


def test_a_padlocked_part_of_a_marked_stack_stays():
    u = _unit(("Dagger", 3))
    u.locked_items["Dagger"] = 1
    s = _screen(u, marked={"Dagger"})
    s._sell_marked()
    assert u.count_of("Dagger") == 1


def test_the_total_matches_what_the_sale_pays():
    u = _unit(("Dagger", 2), ("Club", 2))
    s = _screen(u, marked={"Dagger", "Club"})
    total = s._marked_total()
    before = u.money
    s._sell_marked()
    assert u.money - before == total > 0


def test_nothing_marked_in_the_packs_sells_nothing_and_says_so():
    u = _unit(("Club", 1))
    s = _screen(u, marked={"Dagger"})
    s._sell_marked()
    assert u.count_of("Club") == 1 and "nothing marked" in s.notice


def test_the_menu_marks_and_unmarks_an_item_kind():
    u = _unit(("Dagger", 1))
    s = _screen(u)
    rows = s._menu_rows([(u, 0)])
    assert ("mark", "mark to auto-sell", "Dagger") in rows
    s._menu_run([(u, 0)], "mark", "Dagger")
    assert s.guild.autosell == {"Dagger"}
    assert ("mark", "unmark auto-sell", "Dagger") in s._menu_rows([(u, 0)])
    s._menu_run([(u, 0)], "mark", "Dagger")
    assert s.guild.autosell == set()


def test_a_marked_item_wears_an_auto_sell_tag_and_the_screen_draws_the_button():
    pygame.init()
    u = _unit(("Dagger", 1))
    s = _screen(u, marked={"Dagger"})
    s.fonts = ui_fonts()
    assert s._pack_tag(u, "Dagger").endswith("AUTO-SELL")
    s.draw(pygame.Surface((1280, 720)))
    assert any(key == "sell_marked" for key, _ in s.buttons)


def test_marks_survive_a_save():
    guild = Guild([_unit(("Dagger", 1))], node="city", name="Marks")
    guild.autosell = {"Dagger", "Rotten Food"}
    wid = persist.new_world_id()
    persist.save_game(wid, guild)
    assert persist.load_game(wid).autosell == {"Dagger", "Rotten Food"}
