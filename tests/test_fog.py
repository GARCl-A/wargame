"""Fog of war: the side's memory of the cells it has seen and how the board draws it."""

import os

import pygame

from gartok.fog import SEEN, UNSEEN, VISIBLE, FogMemory
from gartok.ground import GroundObject
from tests.helpers import _melee_battle

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


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


def _screen(daylight):
    from gartok.battle_screen import BattleScreen
    from gartok.ui.tokens import fonts
    pygame.init()
    surf = pygame.display.set_mode((1280, 800))
    batt, a, d = _melee_battle()
    batt.daylight = batt.ambient_light = daylight
    batt.board.walls = set()
    batt.ground = []
    a.pos, d.pos = (2, 5), (14, 5)
    batt.order = [a, d]
    batt.turn_idx = 0
    batt.trap_setup_queue = []
    scr = BattleScreen(fonts(), batt, on_battle_end=lambda *x: None)
    return scr, batt, surf, a


def test_the_screen_remembers_where_the_squad_walked():
    scr, batt, surf, a = _screen(daylight=False)
    scr.draw(surf)
    start = set(scr._visible)
    a.pos = (5, 5)
    scr.draw(surf)
    assert (2, 5) not in scr._visible
    assert start <= scr.fog.seen("player")
    assert (13, 1) not in scr.fog.seen("player")


def test_a_cell_never_seen_is_black_and_a_remembered_one_shows_through():
    scr, batt, surf, a = _screen(daylight=True)
    batt.board.walls = {(6, y) for y in range(batt.board.rows)}      # the right side is out of sight
    scr.draw(surf)
    a.pos = (3, 5)
    scr.draw(surf)
    scr.fog._seen["player"].discard((10, 5))
    scr.fog.reveal("player", [(10, 6)])
    scr.draw(surf)
    unseen = surf.get_at(scr.view.cell_rect(10, 5).center)
    remembered = surf.get_at(scr.view.cell_rect(10, 6).center)
    assert max(tuple(unseen)[:3]) < 16
    assert max(tuple(remembered)[:3]) > max(tuple(unseen)[:3])


def test_a_torch_seen_once_is_still_drawn_after_the_squad_walks_away():
    scr, batt, surf, a = _screen(daylight=False)
    batt.ground = [GroundObject(GroundObject.TORCH, (3, 5))]
    scr.draw(surf)
    assert (3, 5) in scr._visible
    batt.ground = []                       # picked up out of sight: the squad still thinks it is there
    a.pos = (2, 1)
    scr.draw(surf)
    assert (3, 5) not in scr._visible
    assert [p["pos"] for p in scr.fog.remembered_props("player", scr._visible)] == [(3, 5)]


def test_flag_placement_reveals_the_squads_own_half():
    scr, batt, surf, a = _screen(daylight=False)
    batt.flags = {"player": None, "enemy": None}
    batt.flag_carrier = {"player": None, "enemy": None}
    assert batt.awaiting_flag
    scr.draw(surf)
    assert (0, 0) in scr.fog.seen("player")
    assert (batt.board.cols - 1, 0) not in scr.fog.seen("player")
