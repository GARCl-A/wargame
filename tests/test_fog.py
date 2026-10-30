"""Fog of war: the side's memory of the cells it has seen and how the board draws it."""

from gartok.fog import SEEN, UNSEEN, VISIBLE, FogMemory

def _torch(pos):
    return {"kind": "torch", "pos": pos, "trap_type": "", "elevation": 0}


def test_a_cell_is_unseen_then_visible_then_remembered():
    fog = FogMemory()
    assert fog.state("player", (3, 3), set()) == UNSEEN
    fog.remember("player", {(3, 3)})
    assert fog.state("player", (3, 3), {(3, 3)}) == VISIBLE
    assert fog.state("player", (3, 3), set()) == SEEN


def test_the_memory_is_the_sides_not_shared_with_the_foe():
    fog = FogMemory()
    fog.remember("player", {(1, 1)})
    assert fog.state("enemy", (1, 1), set()) == UNSEEN


def test_a_ground_object_stays_where_it_was_last_seen():
    fog = FogMemory()
    fog.remember("player", {(2, 2)}, [_torch((2, 2)), _torch((8, 8))])
    assert fog.remembered_props("player", set()) == [_torch((2, 2))]
    assert fog.remembered_props("player", {(2, 2)}) == []     # in sight: drawn live, not from memory
    fog.remember("player", {(2, 2)}, [])                       # seen again, picked up meanwhile
    assert fog.remembered_props("player", set()) == []


def test_reveal_marks_cells_seen_without_seeing_them():
    fog = FogMemory()
    fog.reveal("player", [(0, 0), (0, 1)])
    assert fog.state("player", (0, 1), set()) == SEEN
