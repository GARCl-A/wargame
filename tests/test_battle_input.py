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


def test_clicking_a_cell_with_a_downed_body_walks_onto_it_and_takes_the_flag_under_it():
    from gartok import combat_lab
    from gartok.battle_screen import BattleScreen
    pygame.init()
    battle, _ = combat_lab.build("ctf", 1, 3, seed=2)
    battle.plant_flag((2, 5))
    actor = battle.player_units[0]
    foe = battle.enemy_units[0]
    battle.board.walls = set()
    actor.pos, foe.pos = (8, 5), (9, 5)
    for u in battle.units:
        if u not in (actor, foe):
            u.pos = (0, battle.units.index(u))
    battle._pf_cache.clear()
    battle.trap_setup_queue.clear()
    battle.order = [actor] + [u for u in battle.units if u is not actor]
    battle.turn_idx = 0
    actor.ap = 2
    foe.status = "dying"
    battle.flags["enemy"] = foe.pos
    screen = BattleScreen(None, battle, on_battle_end=lambda *x: None)
    screen.view.fit(pygame.Rect(0, 0, 800, 600))
    assert battle.unit_at(foe.pos, include_downed=True) is foe
    screen._click(screen.view.cell_rect(*foe.pos).center)
    assert actor.pos == foe.pos
    assert battle.flag_carrier["enemy"] is actor


def _kill_setup():
    scr, batt = _screen()
    me, foe = batt.player_units[0], batt.enemy_units[0]
    foe.pos = (6, 5)
    foe.hp = 1
    me.ap = 2
    batt._pf_cache.clear()
    return scr, batt, me, foe


def _fell_the_foe(scr, foe):
    pos = scr.view.cell_rect(*foe.pos).center
    scr._click(pos)
    scr._click(pos)
    assert not foe.alive
    return pos


def test_clicks_that_outlive_the_target_do_not_walk_onto_its_body(monkeypatch):
    from gartok import battle_screen
    now = [100.0]
    monkeypatch.setattr(battle_screen.time, "monotonic", lambda: now[0])
    scr, _, me, foe = _kill_setup()
    pos = _fell_the_foe(scr, foe)
    for _ in range(3):
        now[0] += 0.3
        scr._click(pos)
    assert me.pos == (5, 5) and me.ap == 1


def test_a_deliberate_click_on_the_body_after_a_pause_still_walks_onto_it(monkeypatch):
    from gartok import battle_screen
    now = [100.0]
    monkeypatch.setattr(battle_screen.time, "monotonic", lambda: now[0])
    scr, _, me, foe = _kill_setup()
    pos = _fell_the_foe(scr, foe)
    now[0] += battle_screen.FELLED_STREAK_SECONDS + 0.1
    scr._click(pos)
    assert me.pos == foe.pos


def test_the_next_character_can_walk_onto_the_body_at_once(monkeypatch):
    from gartok import battle_screen, combat_lab
    now = [100.0]
    monkeypatch.setattr(battle_screen.time, "monotonic", lambda: now[0])
    pygame.init()
    battle, _ = combat_lab.build("ctf", 1, 3, seed=2)
    battle.plant_flag((2, 5))
    battle.board.walls = set()
    first, second = battle.player_units[:2]
    foe = battle.enemy_units[0]
    for i, u in enumerate(battle.units):
        u.pos = (0, i)
    first.pos, foe.pos, second.pos = (5, 5), (6, 5), (7, 5)
    foe.hp = 1
    battle._pf_cache.clear()
    battle.trap_setup_queue.clear()
    battle.order = [first, second] + [u for u in battle.units if u not in (first, second)]
    battle.turn_idx = 0
    first.ap = second.ap = 2
    scr = battle_screen.BattleScreen(None, battle, on_battle_end=lambda *x: None)
    scr.view.fit(pygame.Rect(0, 0, 800, 600))
    foe.hp, foe.status = 0, "dying"
    scr._note_felled(first, foe)
    pos = scr.view.cell_rect(*foe.pos).center
    battle.turn_idx = 1
    assert battle.active is second
    now[0] += 0.1
    scr._click(pos)
    assert second.pos == foe.pos


def test_space_defends_with_the_points_left_then_ends_the_turn():
    scr, batt = _screen()
    me = batt.player_units[0]
    scr.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    assert me.defending and batt.active is not me


def test_space_just_ends_the_turn_when_defend_is_not_possible():
    scr, batt = _screen()
    me = batt.player_units[0]
    me.ap = 0
    scr.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    assert not me.defending and batt.active is not me
