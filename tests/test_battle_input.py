"""Battle-screen camera and keyboard: wheel zoom range, overscroll, arrow steps."""

import os

import pygame

from tests.helpers import _melee_battle

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def _screen():
    from gartok.battle_screen import BattleScreen
    pygame.init()
    batt, a, d = _melee_battle()
    batt.board.walls = set()
    batt.units[0].pos, batt.units[1].pos = (5, 5), (12, 9)
    batt.order = [batt.player_units[0], batt.enemy_units[0]]
    batt.turn_idx = 0
    batt.player_units[0].ap = 2
    scr = BattleScreen(None, batt, on_battle_end=lambda *x: None)
    scr.view.fit(pygame.Rect(0, 0, 800, 600))
    return scr, batt


def _press(scr, *keys):
    for k in keys:
        scr.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))
    scr.update(1000)


def test_zoom_reaches_further_in_than_before_and_stays_in_range():
    from gartok.ui.board_style import MAX_TILE, MIN_TILE, BoardView
    v = BoardView(20, 20)
    v.fit(pygame.Rect(0, 0, 800, 600))
    for _ in range(40):
        v.zoom((400, 300), 1)
    assert v.tile == MAX_TILE and MAX_TILE > 56
    for _ in range(80):
        v.zoom((400, 300), -1)
    assert v.tile == MIN_TILE


def test_every_wheel_notch_changes_the_zoom():
    from gartok.ui.board_style import BoardView
    v = BoardView(20, 20)
    v.fit(pygame.Rect(0, 0, 800, 600))
    v.zoom((400, 300), 1)
    first = v.tile
    v.zoom((400, 300), 1)
    assert v.tile > first


def test_the_camera_can_pan_past_the_board_edge_but_not_forever():
    from gartok.ui.board_style import BoardView
    v = BoardView(20, 20)
    v.fit(pygame.Rect(0, 0, 800, 600))
    for _ in range(10):
        v.zoom((400, 300), 1)
    v.pan_px(100000, 100000)                          # drag far to the top-left
    assert v.cam[0] < 0 and v.cam[1] < 0              # black margin beyond the map
    assert v.cam[0] >= -800 * 0.5 / v.tile - 1e-9
    v.pan_px(-1000000, -1000000)
    assert v.cam[0] <= 20 - 800 / v.tile + 800 * 0.5 / v.tile + 1e-9


def test_a_small_board_stays_centred():
    from gartok.ui.board_style import BoardView
    v = BoardView(4, 4)
    v.fit(pygame.Rect(0, 0, 800, 600))
    v.tile = 20
    v.pan_px(50, 50)
    assert v.cam[0] == -(800 - 4 * 20) / 2 / 20


def test_an_arrow_key_steps_one_square():
    scr, batt = _screen()
    actor = batt.active
    start = actor.pos
    _press(scr, pygame.K_RIGHT)
    assert actor.pos == (start[0] + 1, start[1])


def test_two_arrows_pressed_together_step_diagonally():
    scr, batt = _screen()
    actor = batt.active
    start = actor.pos
    _press(scr, pygame.K_UP, pygame.K_LEFT)
    assert actor.pos == (start[0] - 1, start[1] - 1)


def test_opposite_arrows_cancel_and_nothing_moves():
    scr, batt = _screen()
    actor = batt.active
    start = actor.pos
    _press(scr, pygame.K_UP, pygame.K_DOWN)
    assert actor.pos == start


def test_arrows_do_nothing_into_a_wall_or_off_the_enemy_turn():
    scr, batt = _screen()
    actor = batt.active
    batt.board.walls = {(actor.pos[0] + 1, actor.pos[1])}
    start = actor.pos
    _press(scr, pygame.K_RIGHT)
    assert actor.pos == start
    batt.turn_idx = 1
    _press(scr, pygame.K_LEFT)
    assert batt.player_units[0].pos == start


def test_arrows_are_ignored_while_aiming_an_action():
    from gartok import actions
    scr, batt = _screen()
    actor = batt.active
    scr.aim_action = actions.ATTACK
    start = actor.pos
    _press(scr, pygame.K_RIGHT)
    assert actor.pos == start
