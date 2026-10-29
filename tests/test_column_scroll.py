"""Sideways scroll over a row of member columns, shared by the Loot, Market, Group Gear and
Bank screens, and the pack screens that show the group's animals and wagons beside the members."""

import pygame

from gartok.animals import PACK_SADDLE, Animal
from gartok.group import Group
from gartok.guild import Guild
from gartok.holdings import Stash
from gartok.ui.hscroll import ColumnScroll
from gartok.vault import BankVault
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


def _crew_with_gear():
    crew = [Unit("player") for _ in range(3)]
    for u, gear in zip(crew, (["Rope"], ["Torch", "Torch"], [])):
        u._base_inventory = packed(gear)
    return crew


def _bank(crew, group, items=()):
    guild = Guild(None, groups=[group], bank=Stash(50, packed(list(items))))
    return BankVault(guild, list(crew))


def test_the_bank_holds_the_groups_animals_and_wagons_and_moves_cargo_into_them():
    crew = _crew_with_gear()
    donkey = Animal("Donkey", tack=PACK_SADDLE)
    cart = Wagon("Cart")
    s = _bank(crew, Group(crew, node="city", herd=[donkey], wagons=[cart]), ["Rope"])
    assert s.stores == [donkey, cart]

    s.selected = [(crew[0], 0)]
    s._give_many(donkey, "pack")
    assert donkey.stash.items and not crew[0].has_item("Rope")


def test_an_animal_at_the_bank_refuses_more_than_it_can_carry():
    crew = _crew_with_gear()
    bare = Animal("Donkey")
    s = _bank(crew, Group(crew, node="city", herd=[bare]))
    s.selected = [(crew[0], 0)]
    s._give_many(bare, "pack")
    assert crew[0].has_item("Rope") and "won't fit" in s.notice
