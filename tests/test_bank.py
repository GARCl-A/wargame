"""The Bankers' strongbox: renting it, and moving gear in and out under the cap."""

import os
import random

from tests.helpers import economy, Unit
from gartok.bank_screen import BankScreen
from gartok.guild import Guild


def _screen(guild, party):
    """A BankScreen with just the state the move logic needs (no draw)."""
    s = BankScreen.__new__(BankScreen)
    s.guild = guild
    s.party = party
    s.sel = None
    s.notice = None
    s.on_done = lambda: None
    return s


def test_renting_charges_the_party_evenly_and_flips_the_capacity_on():
    random.seed(1)
    party = [Unit("player") for _ in range(2)]
    for m in party:
        m.gold = 40
    guild = Guild(list(party))
    s = _screen(guild, party)

    s._rent()
    assert guild.bank_unlocked and guild.bank_capacity == economy.BANK_CHEST_CAPACITY
    assert [m.gold for m in party] == [15, 15]        # 50 split evenly
    assert sum(m.gold for m in party) == 80 - economy.BANK_CHEST_PRICE


def test_stashing_never_moves_coin_between_members():
    random.seed(9)
    rich, broke = Unit("player"), Unit("player")
    rich.gold, broke.gold = 60, 0
    rich._base_inventory = ["Broadsword"]
    guild = Guild([rich, broke], bank_capacity=10)
    s = _screen(guild, [rich, broke])

    s.sel = (rich, 0)
    s._deposit()
    s._leave()
    assert rich.gold == 60 and broke.gold == 0        # only the rent ever spends


def test_rent_is_refused_when_the_party_is_short():
    random.seed(2)
    poor = Unit("player")
    poor.gold = economy.BANK_CHEST_PRICE - 1
    guild = Guild([poor])
    s = _screen(guild, [poor])

    s._rent()
    assert not guild.bank_unlocked and "copper" in s.notice


def test_deposit_is_capped_by_the_chest():
    random.seed(3)
    p = Unit("player")
    p._base_inventory = ["Chainmail", "Rope"]        # 10.0 kg + 2.0 kg
    guild = Guild([p], bank_capacity=10)
    s = _screen(guild, [p])

    s.sel = (p, 0)                                    # Chainmail exactly fills the chest
    s._deposit()
    assert guild.bank_items == ["Chainmail"] and p._base_inventory == ["Rope"]

    s.sel = (p, 0)                                    # Rope now -- no room left
    s._deposit()
    assert guild.bank_items == ["Chainmail"] and "fit" in s.notice


def test_withdraw_is_capped_by_the_members_load():
    random.seed(4)
    p = Unit("player")
    p._base_inventory = []
    guild = Guild([p], bank_capacity=30, bank_items=["Rope"])
    s = _screen(guild, [p])

    p.carry_max = 0.5                                 # can't take on even a rope
    s.sel = ("bank", 0)
    s._withdraw(p)
    assert guild.bank_items == ["Rope"] and "fit" in s.notice

    p.carry_max = 999
    s.sel = ("bank", 0)
    s._withdraw(p)
    assert guild.bank_items == [] and p._base_inventory == ["Rope"]


def test_clicking_rent_then_a_pack_item_onto_the_chest_stashes_it():
    """End to end through draw + click: the RENT button and the chest as a drop
    target (`_drop` -> `_resolve`), not just the move helpers."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    random.seed(5)
    p = Unit("player")
    p.gold = 200
    p._base_inventory = ["Rope"]
    guild = Guild([p])
    s = BankScreen(Fonts(), guild, [p], on_done=lambda: None)
    surf = pygame.Surface((1280, 800))
    s.mouse = (0, 0)

    s.draw(surf)
    rent = next(r for k, r in s.buttons if k == "rent")
    s._drop(rent.center, False, None)
    assert guild.bank_unlocked

    s.draw(surf)                                      # chest is now the stash view
    s.sel = (p, 0)
    chest = next(r for k, r in s.buttons if k == "chest")
    assert s._resolve(chest.center) and guild.bank_items == ["Rope"]
