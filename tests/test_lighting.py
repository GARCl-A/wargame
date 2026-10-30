"""Light per cell: one level for each cell in sight, darkness outright for any cell the rules hide."""

import pytest
from gartok.ground import GroundObject
from gartok.lighting import cell_levels
from tests.helpers import _melee_battle

def _night(walls=()):
    batt, a, d = _melee_battle()
    batt.ambient_light = False
    batt.board.walls = set(walls)
    batt.ground = [GroundObject(GroundObject.TORCH, (5, 4))]
    a.pos, d.pos = (5, 5), (14, 10)
    return batt, a


def test_a_cell_near_the_torch_is_brighter_than_one_at_its_edge():
    batt, a = _night()
    levels = cell_levels(batt, {(5, 4), (5, 7), (9, 4)}, [a])
    assert levels[(5, 4)] > levels[(9, 4)]


def test_by_day_every_cell_in_sight_is_in_full_light():
    batt, a = _night()
    batt.ambient_light = True
    assert set(cell_levels(batt, {(1, 1), (9, 9)}, [a]).values()) == {1.0}


@pytest.mark.slow
def test_the_fast_sight_matches_the_rule_cell_by_cell():
    from gartok import ai, combat_lab, vision
    for fight in ("dungeon", "necromancer"):
        b, _ = combat_lab.build(fight, 2, 4, seed=7)
        for _ in range(6):
            for team in ("player", "enemy"):
                obs = vision.observers(b, True, team)
                fast = vision.visible_cells(b, obs)
                rule = {(x, y) for x in range(b.board.cols) for y in range(b.board.rows)
                        if (x, y) not in b.board.walls and any(vision.can_see(b, o, (x, y)) for o in obs)}
                assert fast - b.board.walls == rule
                assert vision.lit_cells(b) == {(x, y) for x in range(b.board.cols) for y in range(b.board.rows)
                                               if vision.cell_lit(b, (x, y))}
            ai.take_turn(b, b.active)
