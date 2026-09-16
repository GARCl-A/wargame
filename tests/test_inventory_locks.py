"""Item locks: exempting a pack item from distribute_load, and nothing else."""

import random

from tests.helpers import Unit
from gartok import data, unit as unit_module
from gartok.group import Group

_HUMAN = data.race_by_name("Human")


def _bare(**kw):
    """A Human with STR 10 and nothing equipped -- so `load` is just the pack,
    and two such units always start with equal free capacity."""
    u = Unit("player", race=_HUMAN)
    u.set_base_attribute("strength", 10)
    u.equipped_weapon = None
    u.equipped_offhand = None
    u.equipped_armor = None
    return u


def test_toggle_lock_locks_and_unlocks_a_whole_stack():
    u = Unit("player")
    u._base_inventory = ["Rope", "Rope", "Rope"]
    assert u.locked_of("Rope") == 0

    u.toggle_lock("Rope")
    assert u.locked_of("Rope") == 3

    u.toggle_lock("Rope")                             # fully locked -> unlocks
    assert u.locked_of("Rope") == 0


def test_toggle_lock_on_an_item_not_held_is_a_no_op():
    u = Unit("player")
    u._base_inventory = []
    u.toggle_lock("Rope")
    assert u.locked_of("Rope") == 0 and u.locked_items == {}


def test_take_from_pack_clamps_the_lock_count_down():
    u = Unit("player")
    u._base_inventory = ["Rope", "Rope"]
    u.toggle_lock("Rope")
    assert u.locked_of("Rope") == 2

    idx = u._base_inventory.index("Rope")
    u.take_from_pack(idx)
    assert u._base_inventory == ["Rope"]
    assert u.locked_of("Rope") == 1                   # clamped, not left dangling at 2

    u.take_from_pack(0)
    assert u._base_inventory == []
    assert u.locked_of("Rope") == 0 and "Rope" not in u.locked_items


def test_distribute_load_moves_unlocked_items_by_free_capacity():
    random.seed(1)
    a, b = _bare(), _bare()
    a._base_inventory = ["Stone Brick", "Stone Brick"]
    b._base_inventory = []

    unit_module.distribute_load([a, b])
    assert len(a._base_inventory) == 1
    assert len(b._base_inventory) == 1


def test_distribute_load_leaves_locked_items_on_their_owner():
    random.seed(2)
    a, b = _bare(), _bare()
    a._base_inventory = ["Stone Brick", "Stone Brick", "Rope"]
    b._base_inventory = []
    a.toggle_lock("Rope")

    unit_module.distribute_load([a, b])
    assert "Rope" in a._base_inventory                # stayed with its locked owner
    assert a.locked_of("Rope") == 1                    # lock itself survives the pass
    assert sorted(a._base_inventory + b._base_inventory).count("Stone Brick") == 2
    assert len(b._base_inventory) >= 1                 # the unlocked brick(s) still spread


def test_distribute_load_with_everything_locked_moves_nothing():
    random.seed(3)
    a, b = _bare(), _bare()
    a._base_inventory = ["Rope", "Rope"]
    b._base_inventory = []
    a.toggle_lock("Rope")

    unit_module.distribute_load([a, b])
    assert a._base_inventory == ["Rope", "Rope"]
    assert b._base_inventory == []


def test_group_distribute_load_delegates_and_respects_locks():
    random.seed(4)
    a, b = _bare(), _bare()
    a._base_inventory = ["Stone Brick", "Stone Brick", "Torch"]
    b._base_inventory = []
    a.toggle_lock("Torch")
    g = Group([a, b])

    g.distribute_load()
    assert "Torch" in a._base_inventory
    assert len(b._base_inventory) >= 1
