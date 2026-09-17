"""The Bankers' strongbox: renting it, and moving gear in and out under the cap."""

import os
import random

from tests.helpers import economy, packed, Unit
from gartok.bank_screen import BankScreen
from gartok.guild import Guild


def _screen(guild, party):
    """A BankScreen with just the state the move logic needs (no draw)."""
    s = BankScreen.__new__(BankScreen)
    s.guild = guild
    s.party = party
    s.sel = []
    s._sel_qty = {}
    s.notice = None
    s.on_done = lambda: None
    return s


def _idx_of(inv, name):
    return next(i for i, (n, _) in enumerate(inv) if n == name)


def test_renting_charges_the_party_evenly_and_flips_the_capacity_on():
    random.seed(1)
    party = [Unit("player") for _ in range(2)]
    for m in party:
        m.gold = 60
    guild = Guild(list(party))
    s = _screen(guild, party)

    s._rent()
    assert guild.bank_unlocked and guild.bank_capacity == economy.BANK_CHEST_CAPACITY
    assert [m.gold for m in party] == [10, 10]        # 100 split evenly
    assert sum(m.gold for m in party) == 120 - economy.BANK_CHEST_PRICE


def test_stashing_never_moves_coin_between_members():
    random.seed(9)
    rich, broke = Unit("player"), Unit("player")
    rich.gold, broke.gold = 60, 0
    rich._base_inventory = packed(["Broadsword"])
    guild = Guild([rich, broke], bank_capacity=10)
    s = _screen(guild, [rich, broke])

    s._drop_on_chest([(rich, 0)])
    s._leave()
    assert rich.gold == 60 and broke.gold == 0        # only the rent ever spends


def test_deposit_is_capped_by_the_chest():
    random.seed(3)
    p = Unit("player")
    p._base_inventory = packed(["Chainmail", "Rope"])        # 10.0 kg + 2.0 kg
    guild = Guild([p], bank_capacity=10)
    s = _screen(guild, [p])

    s._drop_on_chest([(p, _idx_of(p._base_inventory, "Chainmail"))])  # exactly fills the chest
    assert guild.bank_items == ["Chainmail"] and p._base_inventory == packed(["Rope"])

    s._drop_on_chest([(p, _idx_of(p._base_inventory, "Rope"))])       # no room left
    assert guild.bank_items == ["Chainmail"] and "fit" in s.notice


def test_withdraw_is_capped_by_the_members_load():
    random.seed(4)
    p = Unit("player")
    p._base_inventory = []
    guild = Guild([p], bank_capacity=30, bank_items=["Rope"])
    s = _screen(guild, [p])

    p.carry_max = 0.5                                 # can't take on even a rope
    s._drop_on_member(p, [("bank", 0)])
    assert guild.bank_items == ["Rope"] and "fit" in s.notice

    p.carry_max = 999
    s._drop_on_member(p, [("bank", 0)])
    assert guild.bank_items == [] and p._base_inventory == packed(["Rope"])


def test_multi_select_stashes_several_items_in_one_move():
    """Shift/ctrl-click (or the per-stack stepper) gathers more than one pick;
    a single drop on the chest moves the whole batch, all-or-nothing."""
    random.seed(6)
    p = Unit("player")
    p._base_inventory = packed(["Rope", "Rope", "Torch"])
    guild = Guild([p], bank_capacity=30)
    s = _screen(guild, [p])

    picks = [(p, i) for i in range(len(p._base_inventory))]
    s._drop_on_chest(picks)
    assert sorted(guild.bank_items) == ["Rope", "Rope", "Torch"]
    assert p._base_inventory == []
    assert "3 items" in s.notice


def test_multi_select_deposit_is_all_or_nothing():
    """If the batch doesn't fit, nothing moves and the picks are handed back
    (so the caller keeps carrying them) -- no partial stash."""
    random.seed(7)
    p = Unit("player")
    p._base_inventory = packed(["Chainmail", "Rope"])        # 10.0 kg + 2.0 kg -- 12 kg total
    guild = Guild([p], bank_capacity=10)
    s = _screen(guild, [p])

    picks = [(p, 0), (p, 1)]
    s._drop_on_chest(picks)
    assert guild.bank_items == [] and p._base_inventory == packed(["Chainmail", "Rope"])
    assert "fit" in s.notice
    assert s.sel == picks


def test_locked_item_stays_selectable_but_distribute_load_leaves_it():
    """The padlock only exempts an item from distribute_load -- it can still be
    moved by hand (dropped on the chest) at any time."""
    from gartok import unit as unit_module

    random.seed(8)
    a, b = Unit("player"), Unit("player")
    a._base_inventory = packed(["Rope"])
    b._base_inventory = []
    a.toggle_lock("Rope")
    guild = Guild([a, b])
    s = _screen(guild, [a, b])

    unit_module.distribute_load([a, b])
    assert a._base_inventory == packed(["Rope"]) and b._base_inventory == []   # stayed put

    s._drop_on_member(b, [(a, 0)])                    # still movable by hand
    assert a._base_inventory == [] and b._base_inventory == packed(["Rope"])


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
    p._base_inventory = packed(["Rope"])
    guild = Guild([p])
    s = BankScreen(Fonts(), guild, [p], on_done=lambda: None)
    surf = pygame.Surface((1280, 800))
    s.mouse = (0, 0)

    s.draw(surf)
    rent = next(r for k, r in s.buttons if k == "rent")
    s._drop(rent.center, False, None)
    assert guild.bank_unlocked

    s.draw(surf)                                      # chest is now the stash view
    s.sel = [(p, 0)]
    chest = next(r for k, r in s.buttons if k == "chest")
    assert s._resolve(chest.center) and guild.bank_items == ["Rope"]
