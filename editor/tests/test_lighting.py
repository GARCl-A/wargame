"""Light per cell: one level for each cell in sight, darkness outright for any cell the rules hide."""

import pygame
from editor import battle_draw
from editor.battle_draw import LightRenderer
from gartok.ground import GroundObject
from gartok.lighting import cell_levels
from editor.ui.board_style import BoardView
from tests.helpers import _melee_battle

def _night(walls=()):
    batt, a, d = _melee_battle()
    batt.ambient_light = False
    batt.board.walls = set(walls)
    batt.ground = [GroundObject(GroundObject.TORCH, (5, 4))]
    a.pos, d.pos = (5, 5), (14, 10)
    return batt, a

def _draw(batt, visible, observers, seen):
    pygame.init()
    surf = pygame.display.set_mode((640, 480))
    surf.fill((255, 255, 255))
    view = BoardView(batt.board.cols, batt.board.rows)
    view.fit(pygame.Rect(0, 0, 640, 480))
    LightRenderer().draw(surf, batt, visible, observers, view, seen)
    return surf, view


def test_a_cell_in_sight_never_reads_as_remembered():
    batt, a = _night()
    levels = cell_levels(batt, {(9, 4)}, [a])
    assert 255 * (1 - levels[(9, 4)]) < battle_draw._NIGHT_SEEN


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
