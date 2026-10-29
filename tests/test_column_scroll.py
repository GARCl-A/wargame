"""The group's animals and wagons as packs beside the members at the bank."""

from gartok.animals import PACK_SADDLE, Animal
from gartok.group import Group
from gartok.guild import Guild
from gartok.holdings import Stash
from gartok.vault import BankVault
from gartok.wagon import Wagon
from tests.helpers import Unit, packed


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
