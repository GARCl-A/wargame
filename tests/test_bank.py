"""The Bankers' strongbox: renting it, moving gear in and out under the cap,
and the pooled/proportional purse the visit settles back out on the way out."""

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
    s.selected = []
    s._sel_qty = {}
    s.notice = None
    s.on_done = lambda: None
    return s


def test_renting_debits_the_pooled_purse_and_flips_the_capacity_on():
    random.seed(1)
    party = [Unit("player") for _ in range(2)]
    for m in party:
        m.gold = 60
    guild = Guild(list(party))
    s = BankScreen(None, guild, party, on_done=lambda: None)

    s._run_service("rent")
    assert guild.bank_unlocked and guild.bank_capacity == economy.BANK_CHEST_CAPACITY
    assert s.purse == 120 - economy.BANK_CHEST_PRICE
    assert [m.gold for m in party] == [60, 60]        # not settled until _leave


def test_leaving_settles_the_purse_proportional_to_what_each_member_brought():
    random.seed(9)
    rich, broke = Unit("player"), Unit("player")
    rich.gold, broke.gold = 90, 30
    guild = Guild([rich, broke])
    s = BankScreen(None, guild, [rich, broke], on_done=lambda: None)

    s.purse -= 40                     # simulate 40 copper spent during the visit
    s._leave()
    assert rich.gold + broke.gold == 80
    assert rich.gold == 3 * broke.gold      # 90:30 == 3:1, preserved exactly


def test_deposit_is_capped_by_the_chest():
    random.seed(3)
    p = Unit("player")
    p._base_inventory = packed(["Chainmail", "Rope"])        # 10.0 kg + 2.0 kg
    guild = Guild([p], bank_capacity=10)
    s = _screen(guild, [p])

    s._deposit([(p, 0)])              # Chainmail -- exactly fills the chest
    assert guild.bank_items == [("Chainmail", 1)] and p._base_inventory == packed(["Rope"])

    s._deposit([(p, 0)])              # Rope -- no room left
    assert guild.bank_items == [("Chainmail", 1)] and "fit" in s.notice


def test_withdraw_is_capped_by_the_members_load():
    random.seed(4)
    p = Unit("player")
    p._base_inventory = []
    guild = Guild([p], bank_capacity=30, bank_items=[("Rope", 1)])
    s = _screen(guild, [p])

    p.carry_max = 0.5                                 # can't take on even a rope
    s.selected = [("bank", 0)]
    s._give_many(p, "pack")
    assert guild.bank_items == [("Rope", 1)] and "fit" in s.notice

    p.carry_max = 999
    s.selected = [("bank", 0)]
    s._give_many(p, "pack")
    assert guild.bank_items == [] and p._base_inventory == packed(["Rope"])


def test_equip_straight_out_of_the_chest():
    """The equip slots are live drop zones on this screen too now -- taking a
    weapon out of the chest can land it straight in a member's hand instead
    of always going through the pack first."""
    random.seed(2)
    p = Unit("player")
    p._base_inventory = []
    guild = Guild([p], bank_capacity=30, bank_items=[("Dagger", 1)])
    s = _screen(guild, [p])

    s.selected = [("bank", 0)]
    s._give_many(p, "hand")
    assert p.equipped_weapon == "Dagger" and guild.bank_items == []


def test_stashing_an_equipped_weapon_unequips_it():
    random.seed(11)
    p = Unit("player")
    p.give_to_hand("Dagger")
    guild = Guild([p], bank_capacity=30)
    s = _screen(guild, [p])

    s._deposit([(p, "hand")])
    assert p.equipped_weapon is None and guild.bank_items == [("Dagger", 1)]


def test_multi_select_stashes_several_stacks_in_one_move():
    random.seed(6)
    p = Unit("player")
    p._base_inventory = packed(["Rope", "Rope", "Torch"])     # merges to [("Rope", 2), ("Torch", 1)]
    guild = Guild([p], bank_capacity=30)
    s = _screen(guild, [p])

    picks = [(p, i) for i in range(len(p._base_inventory))]
    s._deposit(picks)
    assert sorted(guild.bank_items) == [("Rope", 2), ("Torch", 1)]
    assert p._base_inventory == []
    assert "3 items" in s.notice          # 2 stacks, 3 copies total (2 rope + 1 torch)


def test_multi_select_deposit_is_all_or_nothing():
    """If the batch doesn't fit, nothing moves and the picks are handed back
    (so the caller keeps carrying them) -- no partial stash."""
    random.seed(7)
    p = Unit("player")
    p._base_inventory = packed(["Chainmail", "Rope"])        # 10.0 kg + 2.0 kg -- 12 kg total
    guild = Guild([p], bank_capacity=10)
    s = _screen(guild, [p])

    picks = [(p, 0), (p, 1)]
    s._deposit(picks)
    assert guild.bank_items == [] and p._base_inventory == packed(["Chainmail", "Rope"])
    assert "fit" in s.notice
    assert s.selected == picks


def test_partial_qty_deposit_via_the_chest_stepper():
    """A member's pack always moves as a whole stack, but a chest pick's
    quantity is stepper-adjustable -- taking 2 of a 3-stack back out leaves
    the rest behind."""
    random.seed(12)
    p = Unit("player")
    p._base_inventory = []
    guild = Guild([p], bank_capacity=30, bank_items=[("Rope", 3)])
    s = _screen(guild, [p])

    s.selected = [("bank", 0)]
    s._sel_qty[("bank", 0)] = 2
    s._give_many(p, "pack")
    assert guild.bank_items == [("Rope", 1)] and p._base_inventory == [("Rope", 2)]


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

    s.selected = [(a, 0)]
    s._give_many(b, "pack")                           # still movable by hand
    assert a._base_inventory == [] and b._base_inventory == packed(["Rope"])


def test_clicking_rent_then_a_pack_item_onto_the_chest_stashes_it():
    """End to end through draw + click: the RENT service and the chest as a
    drop target, not just the move helpers."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.display.set_mode((1, 1))

    random.seed(5)
    p = Unit("player")
    p.gold = 200
    p._base_inventory = packed(["Rope"])
    guild = Guild([p])
    s = BankScreen(None, guild, [p], on_done=lambda: None)
    surf = pygame.Surface((1280, 800))
    s.mouse = (0, 0)

    s.draw(surf)
    rent_r = next(r for r, key in s._service_hits if key == "rent")
    s._drop(rent_r.center, False, None)
    assert guild.bank_unlocked

    s.draw(surf)                                      # chest is now the stash view
    s.selected = [(p, 0)]
    chest_zone = next(r for r, owner, zone in s.zones if zone == "chest")
    s._drop(chest_zone.center, True, (p, 0))
    assert guild.bank_items == [("Rope", 1)]
