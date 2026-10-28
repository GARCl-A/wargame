"""The Bankers' strongbox: renting it, moving gear in and out under the cap,
and the pooled/proportional purse the visit settles back out on the way out."""

import random

from gartok.guild import Guild
from gartok.holdings import Stash
from gartok.vault import BankVault
from tests.helpers import Unit, economy, packed


def test_renting_debits_the_pooled_purse_and_flips_the_capacity_on():
    random.seed(1)
    party = [Unit("player") for _ in range(2)]
    for m in party:
        m.money = 60
    guild = Guild(list(party))
    s = BankVault(guild, party)

    s._run_service("rent")
    assert guild.bank.open and guild.bank.capacity == economy.BANK_CHEST_CAPACITY
    assert s.purse == 120 - economy.BANK_CHEST_PRICE
    assert sum(m.money for m in party) == s.purse      # debited at once, not only on _leave


def test_a_payment_comes_out_in_proportion_to_what_each_member_brought():
    random.seed(9)
    rich, broke = Unit("player"), Unit("player")
    rich.money, broke.money = 90, 30
    guild = Guild([rich, broke])
    s = BankVault(guild, [rich, broke])

    s.purse -= 40
    assert rich.money + broke.money == 80
    assert rich.money == 3 * broke.money      # 90:30 == 3:1, preserved exactly


def test_deposit_is_capped_by_the_chest():
    random.seed(3)
    p = Unit("player")
    p._base_inventory = packed(["Chainmail", "Rope"])        # 10.0 kg + 2.0 kg
    guild = Guild([p], bank=Stash(10))
    s = BankVault(guild, [p])

    s._deposit([(p, 0)])              # Chainmail -- exactly fills the chest
    assert guild.bank.items == [("Chainmail", 1)] and p._base_inventory == packed(["Rope"])

    s._deposit([(p, 0)])              # Rope -- no room left
    assert guild.bank.items == [("Chainmail", 1)] and "fit" in s.notice


def test_withdraw_is_capped_by_the_members_load():
    random.seed(4)
    p = Unit("player")
    p._base_inventory = []
    guild = Guild([p], bank=Stash(30, packed(["Rope"])))
    s = BankVault(guild, [p])

    p.carry_max = 0.5                                 # can't take on even a rope
    s.selected = [("bank", 0)]
    s._give_many(p, "pack")
    assert guild.bank.items == [("Rope", 1)] and "fit" in s.notice

    p.carry_max = 999
    s.selected = [("bank", 0)]
    s._give_many(p, "pack")
    assert guild.bank.items == [] and p._base_inventory == packed(["Rope"])


def test_equip_straight_out_of_the_chest():
    """Taking a weapon out of the chest can land it straight in a member's hand."""
    random.seed(2)
    p = Unit("player")
    p._base_inventory = []
    guild = Guild([p], bank=Stash(30, packed(["Dagger"])))
    s = BankVault(guild, [p])

    s.selected = [("bank", 0)]
    s._give_many(p, "hand")
    assert p.equipped_weapon == "Dagger" and guild.bank.items == []


def test_stashing_an_equipped_weapon_unequips_it():
    random.seed(11)
    p = Unit("player")
    p.give_to_hand("Dagger")
    guild = Guild([p], bank=Stash(30))
    s = BankVault(guild, [p])

    s._deposit([(p, "hand")])
    assert p.equipped_weapon is None and guild.bank.items == [("Dagger", 1)]


def test_multi_select_stashes_several_stacks_in_one_move():
    random.seed(6)
    p = Unit("player")
    p._base_inventory = packed(["Rope", "Rope", "Torch"])     # merges to [("Rope", 2), ("Torch", 1)]
    guild = Guild([p], bank=Stash(30))
    s = BankVault(guild, [p])

    picks = [(p, i) for i in range(len(p._base_inventory))]
    s._deposit(picks)
    assert sorted(guild.bank.items) == [("Rope", 2), ("Torch", 1)]
    assert p._base_inventory == []
    assert "3 items" in s.notice          # 2 stacks, 3 copies total (2 rope + 1 torch)


def test_multi_select_deposit_is_all_or_nothing():
    """If the batch doesn't fit, nothing moves and the picks are handed back
    (so the caller keeps carrying them) -- no partial stash."""
    random.seed(7)
    p = Unit("player")
    p._base_inventory = packed(["Chainmail", "Rope"])        # 10.0 kg + 2.0 kg -- 12 kg total
    guild = Guild([p], bank=Stash(10))
    s = BankVault(guild, [p])

    picks = [(p, 0), (p, 1)]
    s._deposit(picks)
    assert guild.bank.items == [] and p._base_inventory == packed(["Chainmail", "Rope"])
    assert "fit" in s.notice
    assert s.selected == picks


def test_partial_qty_deposit_via_the_chest_stepper():
    """A member's pack always moves as a whole stack, but a chest pick's
    quantity is stepper-adjustable -- taking 2 of a 3-stack back out leaves
    the rest behind."""
    random.seed(12)
    p = Unit("player")
    p._base_inventory = []
    guild = Guild([p], bank=Stash(30, packed(["Rope"] * 3)))
    s = BankVault(guild, [p])

    s.selected = [("bank", 0)]
    s._sel_qty[("bank", 0)] = 2
    s._give_many(p, "pack")
    assert guild.bank.items == [("Rope", 1)] and p._base_inventory == [("Rope", 2)]


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
    s = BankVault(guild, [a, b])

    unit_module.distribute_load([a, b])
    assert a._base_inventory == packed(["Rope"]) and b._base_inventory == []   # stayed put

    s.selected = [(a, 0)]
    s._give_many(b, "pack")                           # still movable by hand
    assert a._base_inventory == [] and b._base_inventory == packed(["Rope"])
