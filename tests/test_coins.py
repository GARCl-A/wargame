"""Money as an item: `Unit.money` is the count of "Copper Coin" in the pack."""

import os
import random

import pygame

from gartok import items, persist, unit_loadout
from gartok.group_screen import GroupScreen
from gartok.group import Group
from gartok.guild import Guild
from gartok.unit import Unit, distribute_load, flatten_pack

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def _bare(gold=0):
    u = Unit("player")
    u._base_inventory = []
    u.money = gold
    return u


def test_gold_is_the_coin_stack_in_the_pack():
    u = _bare(120)
    assert u.money == 120
    assert [(n, q) for n, q in u._base_inventory] == [(items.COIN_ITEM, 120)]
    u.money += 30
    u.money -= 50
    assert u.money == 100 and len(u._base_inventory) == 1       # one merged stack


def test_gold_never_goes_below_zero_and_zero_leaves_no_row():
    u = _bare(10)
    u.money = -5
    assert u.money == 0 and u._base_inventory == []


def test_a_split_purse_is_still_one_balance():
    u = _bare(100)
    u.split_pack(0, 30)
    assert len(u._base_inventory) == 2 and u.money == 100
    u.money -= 85                                               # spans both stacks
    assert u.money == 15
    u.money = 0
    assert u._base_inventory == []


def test_two_hundred_coins_weigh_one_kilo():
    u = _bare(0)
    base = u.load
    u.money = 200
    assert u.load == base + 1.0
    u.money = 1000
    assert u.load == base + 5.0


def test_coins_stay_out_of_the_battle_inventory():
    u = _bare(500)
    u.give_to_pack("Rope")
    assert flatten_pack(u) == ["Rope"]


def _ratio(u):
    return u.load / max(1.0, u.carry_normal)


def _balanced(a, b):
    """No handful moved from one to the other would even them up further (`load`
    is rounded to 0.1 kg, so allow that much slack on top of the handful)."""
    slack = (unit_loadout.COIN_HANDFUL / 200 + 0.1) / min(a.carry_normal, b.carry_normal)
    return abs(_ratio(a) - _ratio(b)) <= slack + 1e-9


def test_distribute_load_spreads_coins_by_free_capacity():
    rich, poor = _bare(4001), _bare(0)
    distribute_load([rich, poor])
    assert rich.money + poor.money == 4001
    assert _balanced(rich, poor)


def test_distribute_load_offsets_a_pinned_load_with_coins_on_the_other_side():
    laden, light = _bare(0), _bare(0)
    laden.give_to_pack("Rope", 6)
    laden.toggle_lock("Rope")
    light.money = 4000
    distribute_load([laden, light])
    assert laden.count_of("Rope") == 6
    assert laden.money + light.money == 4000
    assert _balanced(laden, light) or laden.money == 0


def test_distribute_load_keeps_a_locked_purse_with_its_owner():
    rich, poor = _bare(400), _bare(100)
    rich.toggle_lock(items.COIN_ITEM)
    distribute_load([rich, poor])
    assert rich.money >= 400 and rich.money + poor.money == 500


def test_purse_survives_a_save_round_trip_inside_the_pack():
    random.seed(3)
    u = _bare(321)
    u.give_to_pack("Rope")
    d = persist.unit_to_dict(u)
    assert "gold" not in d
    v = Unit.from_save(d)
    assert v.money == 321 and v.count_of("Rope") == 1


def test_a_beast_carries_no_purse():
    from gartok import data
    beast = Unit("enemy", race=data.BEAST_POOL[0])
    assert beast.money == 0 and beast._base_inventory == []


def test_coins_are_not_for_sale_at_the_market_or_the_stash():
    from gartok import economy
    assert items.COIN_ITEM not in economy.MARKET_STOCK


def test_gear_screen_splits_a_purse_and_hands_part_of_it_to_a_mate():
    pygame.init()
    a, b = _bare(100), _bare(0)
    g = Group([a, b], node="city")
    guild = Guild(None, groups=[g])
    s = GroupScreen(None, guild, g, lambda: None)
    s.draw(pygame.Surface((1400, 900)))

    s.selected = [(a, 0)]
    s._open_menu((10, 10), picks=[(a, 0)])
    assert any(kind == "split" for kind, _, _ in s.menu["rows"])
    s._open_split_prompt()
    s.split_prompt["amount"] = 40
    s.draw(pygame.Surface((1400, 900)))
    confirm = next(r for r, key in s.split_prompt["hits"] if key == "confirm")
    s._split_prompt_click(confirm.center)
    assert sorted(q for _, q in a._base_inventory) == [40, 60]

    idx = next(i for i, (_, q) in enumerate(a._base_inventory) if q == 40)
    s.selected = [(a, idx)]
    s._give_many(b, "pack")
    assert (a.money, b.money) == (60, 40)


def test_a_purse_weighs_on_a_weak_carrier():
    u = _bare(0)
    u.equipped_armor = None
    base = u.load
    u.money = 2000
    assert u.load == base + 10.0
    assert u.encumbered == (u.load > u.carry_normal)
