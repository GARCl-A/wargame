"""Item locks: exempting a pack item from distribute_load, and nothing else."""

import random

from tests.helpers import Unit, packed
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
    u._base_inventory = packed(["Rope", "Rope", "Rope"])
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
    u._base_inventory = packed(["Rope", "Rope"])
    u.toggle_lock("Rope")
    assert u.locked_of("Rope") == 2

    idx = next(i for i, (n, _) in enumerate(u._base_inventory) if n == "Rope")
    u.take_from_pack(idx)
    assert u._base_inventory == [("Rope", 1)]
    assert u.locked_of("Rope") == 1                   # clamped, not left dangling at 2

    u.take_from_pack(0)
    assert u._base_inventory == []
    assert u.locked_of("Rope") == 0 and "Rope" not in u.locked_items


def test_distribute_load_moves_unlocked_items_by_free_capacity():
    random.seed(1)
    a, b = _bare(), _bare()
    a._base_inventory = packed(["Stone Brick", "Stone Brick"])
    b._base_inventory = []

    unit_module.distribute_load([a, b])
    assert len(a._base_inventory) == 1
    assert len(b._base_inventory) == 1


def test_distribute_load_leaves_locked_items_on_their_owner():
    random.seed(2)
    a, b = _bare(), _bare()
    a._base_inventory = packed(["Stone Brick", "Stone Brick", "Rope"])
    b._base_inventory = []
    a.toggle_lock("Rope")

    unit_module.distribute_load([a, b])
    assert a.has_item("Rope")                          # stayed with its locked owner
    assert a.locked_of("Rope") == 1                     # lock itself survives the pass
    assert a.count_of("Stone Brick") + b.count_of("Stone Brick") == 2
    assert len(b._base_inventory) >= 1                  # the unlocked brick(s) still spread


def test_distribute_load_with_everything_locked_moves_nothing():
    random.seed(3)
    a, b = _bare(), _bare()
    a._base_inventory = packed(["Rope", "Rope"])
    b._base_inventory = []
    a.toggle_lock("Rope")

    unit_module.distribute_load([a, b])
    assert a._base_inventory == packed(["Rope", "Rope"])
    assert b._base_inventory == []


def test_split_pack_peels_a_partial_quantity_into_its_own_stack():
    u = Unit("player")
    u._base_inventory = packed(["Coal"] * 40)

    assert u.split_pack(0, 15) is True
    assert u._base_inventory == [("Coal", 25), ("Coal", 15)]


def test_split_pack_rejects_the_whole_stack_or_nothing():
    u = Unit("player")
    u._base_inventory = packed(["Rope", "Rope", "Rope"])

    assert u.split_pack(0, 0) is False
    assert u.split_pack(0, 3) is False
    assert u._base_inventory == packed(["Rope", "Rope", "Rope"])


def test_split_pack_keeps_the_lock_total_across_both_halves():
    u = Unit("player")
    u._base_inventory = packed(["Rope"] * 6)
    u.toggle_lock("Rope")
    assert u.locked_of("Rope") == 6

    u.split_pack(0, 2)
    assert u._base_inventory == [("Rope", 4), ("Rope", 2)]
    assert u.locked_of("Rope") == 6                   # a lock counts against the name, not one stack


def test_group_distribute_load_delegates_and_respects_locks():
    random.seed(4)
    a, b = _bare(), _bare()
    a._base_inventory = packed(["Stone Brick", "Stone Brick", "Torch"])
    b._base_inventory = []
    a.toggle_lock("Torch")
    g = Group([a, b])

    g.distribute_load()
    assert a.has_item("Torch")
    assert len(b._base_inventory) >= 1
