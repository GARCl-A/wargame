"""Sideways scroll over a row of member columns, shared by the Loot, Market, Group Gear and
Bank screens, and the pack screens that show the group's animals and wagons beside the members."""

import pygame

from gartok import world
from gartok.animals import PACK_SADDLE, Animal
from gartok.bank_screen import BankScreen
from gartok.group import Group
from gartok.guild import Guild
from gartok.holdings import Stash
from gartok.loot_screen import LootScreen
from gartok.market_screen import MarketScreen
from gartok.ui.hscroll import ColumnScroll
from gartok.ui.tokens import fonts as ui_fonts
from gartok.wagon import Wagon
from tests.helpers import Unit, packed


def _wheel(screen, x=0, y=0):
    screen.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, {"x": x, "y": y}))


def test_fit_shows_what_the_width_allows_and_the_rest_scrolls():
    cs = ColumnScroll()
    window, col_w = cs.fit(6, 1000, 16, 300, 420)
    assert (window.start, window.stop) == (0, 3) and cs.max == 3
    assert 300 <= col_w <= 420
    cs.pos = 99
    window, _ = cs.fit(6, 1000, 16, 300, 420)
    assert window.start == 3 and cs.pos == 3
    window, _ = cs.fit(2, 1000, 16, 300, 420)
    assert (window.start, window.stop, cs.max, cs.pos) == (0, 2, 0, 0)


def test_a_sideways_wheel_moves_the_row_and_a_plain_one_only_where_asked():
    pygame.init()
    pygame.display.set_mode((1, 1))
    cs = ColumnScroll()
    cs.fit(6, 1000, 16, 300, 420)
    assert cs.wheel(pygame.event.Event(pygame.MOUSEWHEEL, {"x": 1, "y": 0})) and cs.pos == 1
    assert not cs.wheel(pygame.event.Event(pygame.MOUSEWHEEL, {"x": 0, "y": 1}), over=False)
    assert cs.wheel(pygame.event.Event(pygame.MOUSEWHEEL, {"x": 0, "y": 1})) and cs.pos == 0
    one = ColumnScroll()
    one.fit(2, 1000, 16, 300, 420)
    assert not one.wheel(pygame.event.Event(pygame.MOUSEWHEEL, {"x": 1, "y": 0}))


def test_the_loot_screen_reaches_members_past_the_window_edge():
    pygame.init()
    pygame.display.set_mode((1, 1))
    crew = [Unit("player") for _ in range(7)]
    ls = LootScreen(ui_fonts(), Guild(list(crew)), crew, ["Axe"], lambda: None)
    surf = pygame.Surface((1280, 800))
    ls.mouse = (0, 0)
    ls.draw(surf)
    seen = {u for _, u, _ in ls.zones if isinstance(u, Unit)}
    assert crew[0] in seen and crew[-1] not in seen and ls._cols.max > 0

    for _ in range(ls._cols.max):
        _wheel(ls, x=1)
    ls.draw(surf)
    seen = {u for _, u, _ in ls.zones if isinstance(u, Unit)}
    assert crew[-1] in seen and crew[0] not in seen


def _market(crew, group):
    guild = Guild(None, groups=[group])
    return MarketScreen(None, guild, list(crew), world.node("city"), lambda: None)


def _crew_with_gear():
    crew = [Unit("player") for _ in range(3)]
    for u, gear in zip(crew, (["Rope"], ["Torch", "Torch"], [])):
        u._base_inventory = packed(gear)
    return crew


def test_the_market_can_list_the_whole_groups_items_in_one_table():
    pygame.init()
    crew = _crew_with_gear()
    donkey = Animal("Donkey", tack=PACK_SADDLE)
    donkey.stash.put("Rope")
    s = _market(crew, Group(crew, node="city", herd=[donkey]))
    surf = pygame.Surface((1900, 900))
    s.mouse = (0, 0)
    s.draw(surf)
    assert ("group_view" in {k for k, _ in s.buttons}) and not s.group_view

    s._drop((0, 0), False, None)
    rect = dict(s.buttons)["group_view"]
    s._drop(rect.center, False, None)
    assert s.group_view
    s.draw(surf)
    owners = {id(o) for _, o, _ in s.item_rows}
    assert {id(crew[0]), id(crew[1]), id(donkey)} <= owners
    assert not any(zone == "pack" for _, _, zone in s.zones)


def test_selling_from_the_group_table_pays_for_the_picked_stack():
    pygame.init()
    crew = _crew_with_gear()
    s = _market(crew, Group(crew, node="city"))
    s.group_view = True
    surf = pygame.Surface((1900, 900))
    s.mouse = (0, 0)
    s.draw(surf)
    _rect, owner, loc = next(r for r in s.item_rows if r[1] is crew[1])
    before = crew[1].money
    s.selected = [(owner, loc)]
    s._sell()
    assert crew[1].money > before and not crew[1].has_item("Torch")


def test_buying_brings_the_member_columns_back_to_drop_on():
    pygame.init()
    crew = _crew_with_gear()
    s = _market(crew, Group(crew, node="city"))
    s.group_view = True
    s.selected = [("stock", "Rope")]
    s.mouse = (0, 0)
    s.draw(pygame.Surface((1900, 900)))
    assert any(zone == "pack" for _, o, zone in s.zones if o in crew)


def _bank(crew, group, items=()):
    guild = Guild(None, groups=[group], bank=Stash(50, packed(list(items))))
    return BankScreen(None, guild, list(crew), on_done=lambda: None)


def test_the_bank_shows_the_groups_animals_and_wagons_and_moves_cargo_into_them():
    pygame.init()
    crew = _crew_with_gear()
    donkey = Animal("Donkey", tack=PACK_SADDLE)
    cart = Wagon("Cart")
    s = _bank(crew, Group(crew, node="city", herd=[donkey], wagons=[cart]), ["Rope"])
    surf = pygame.Surface((2600, 900))
    s.mouse = (0, 0)
    s.draw(surf)
    stores = {id(o) for _, o, zone in s.zones if zone == "pack"}
    assert id(donkey) in stores and id(cart) in stores

    s.selected = [(crew[0], 0)]
    s._give_many(donkey, "pack")
    assert donkey.stash.items and not crew[0].has_item("Rope")


def test_an_animal_at_the_bank_refuses_more_than_it_can_carry():
    pygame.init()
    crew = _crew_with_gear()
    bare = Animal("Donkey")
    s = _bank(crew, Group(crew, node="city", herd=[bare]))
    s.selected = [(crew[0], 0)]
    s._give_many(bare, "pack")
    assert crew[0].has_item("Rope") and "won't fit" in s.notice


def test_a_narrow_bank_window_scrolls_to_the_wagon():
    pygame.init()
    pygame.display.set_mode((1, 1))
    crew = _crew_with_gear()
    cart = Wagon("Cart")
    s = _bank(crew, Group(crew, node="city", wagons=[cart]))
    surf = pygame.Surface((1500, 900))
    s.mouse = (0, 0)
    s.draw(surf)
    assert s._cols.max > 0 and id(cart) not in {id(o) for _, o, _ in s.zones}
    for _ in range(s._cols.max):
        _wheel(s, x=1)
    s.draw(surf)
    assert id(cart) in {id(o) for _, o, _ in s.zones}
