"""The random starting kit (starter_kit.py): one base weapon and one cheap item per recruit."""

import random

from gartok import economy, items, persist, starter_kit
from tests.helpers import Unit, data, standard_unit


def test_weapon_pool_is_base_weapons_up_to_the_cap():
    pool = starter_kit.weapon_pool()
    assert {"Axe", "Pick", "Dagger", "Quarterstaff"} <= set(pool)
    for name in pool:
        weapon = items.get(name)
        assert 0 < weapon.price <= starter_kit.WEAPON_PRICE_CAP
        assert weapon.size not in (items.WeaponSize.LARGE, items.WeaponSize.HUGE)


def test_item_pool_leaves_out_weapons_quest_items_and_money():
    pool = starter_kit.item_pool()
    assert pool
    for name in pool:
        definition = items.get(name)
        assert definition.type not in (items.ItemType.WEAPON, items.ItemType.QUEST, items.ItemType.CURRENCY)
        assert 0 < definition.price <= starter_kit.ITEM_PRICE_CAP
    assert {data.MISSION_CHEST_ITEM, data.BOX_OF_GEMS_ITEM, items.COIN_ITEM}.isdisjoint(pool)


def test_a_recruit_starts_with_a_pool_weapon_and_a_pool_item():
    random.seed(7)
    for _ in range(50):
        u = Unit("player", race=data.race_by_name("Human"))
        assert u.equipped_weapon in starter_kit.weapon_pool()
        packed = {entry.name for entry in u._base_inventory}
        assert packed & set(starter_kit.item_pool())


def test_the_purse_is_three_d_four_copper():
    random.seed(8)
    purses = {Unit("player", race=data.race_by_name("Human")).money for _ in range(200)}
    assert min(purses) >= 3 and max(purses) <= 12
    assert economy.STARTING_WEALTH_DICE == (3, 4)


def test_a_beast_starts_with_no_kit():
    wolf = Unit("enemy", race=data.race_by_name("Wolf"))
    assert wolf.equipped_weapon is None and wolf._base_inventory == []


def test_the_save_does_not_write_an_occupation_and_an_old_one_still_loads():
    u = standard_unit()
    payload = persist.unit_to_dict(u)
    assert "occupation" not in payload
    back = Unit.from_save({**payload, "occupation": "Guard"})
    assert back.equipped_weapon == u.equipped_weapon


def test_set_kit_swaps_the_weapon_and_the_item():
    u = standard_unit()
    u.set_kit("Axe", "Torch")
    assert u.equipped_weapon == "Axe" and u.count_of("Torch") == 1
    u.set_kit(None, None)
    assert u.equipped_weapon is None and u._base_inventory == []
