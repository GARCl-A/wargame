"""Light per cell: one level for each cell in sight, darkness outright for any cell the rules hide."""

import os

import pygame

from gartok import lighting
from gartok.ground import GroundObject
from gartok.lighting import LightRenderer, cell_levels
from gartok.ui.board_style import BoardView
from tests.helpers import _melee_battle

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


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


def test_a_cell_in_sight_never_reads_as_remembered():
    batt, a = _night()
    levels = cell_levels(batt, {(9, 4)}, [a])
    assert 255 * (1 - levels[(9, 4)]) < lighting._NIGHT_SEEN


def test_by_day_every_cell_in_sight_is_in_full_light():
    batt, a = _night()
    batt.ambient_light = True
    assert set(cell_levels(batt, {(1, 1), (9, 9)}, [a]).values()) == {1.0}


def _draw(batt, visible, observers, seen):
    pygame.init()
    surf = pygame.display.set_mode((640, 480))
    surf.fill((255, 255, 255))
    view = BoardView(batt.board.cols, batt.board.rows)
    view.fit(pygame.Rect(0, 0, 640, 480))
    LightRenderer().draw(surf, batt, visible, observers, view, seen)
    return surf, view


def test_a_hidden_cell_inside_the_torchlight_stays_black():
    batt, a = _night(walls={(6, 4)})
    surf, view = _draw(batt, {(5, 4), (5, 5)}, [a], seen=set())
    hidden = surf.get_at(view.cell_rect(7, 4).center)          # lit by the torch, but not in sight
    assert max(tuple(hidden)[:3]) < 16


def test_a_remembered_cell_shows_dimmer_than_one_in_sight():
    batt, a = _night()
    surf, view = _draw(batt, {(5, 5)}, [a], seen={(5, 5), (2, 2)})
    now = max(tuple(surf.get_at(view.cell_rect(5, 5).center))[:3])
    remembered = max(tuple(surf.get_at(view.cell_rect(2, 2).center))[:3])
    never = max(tuple(surf.get_at(view.cell_rect(12, 2).center))[:3])
    assert now > remembered > never


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
