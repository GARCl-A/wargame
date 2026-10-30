"""Tokens on the board: the side plate (disc for friends, diamond for foes) and the mark of the dead."""

import pygame
from editor.ui import banner, board_render
from editor.ui.board_style import CORPSE_INK, ENEMY_C, PLAYER_C, BoardView
from editor.ui.tokens import fonts
from tests.helpers import _melee_battle

def _tok(team, **kw):
    return {"team": team, "active": False, "race": "Human", "portrait_id": None, "token": "H",
            "hp_frac": 1.0, "hp_steps": None, "torch": False, "defending": False, "ferocity": False,
            "demoralized": False, "flag": None, "focus": None, "downed": False, "dying": None,
            "broken": False, **kw}

def _draw(team, **kw):
    pygame.init()
    surf = pygame.Surface((64, 64))
    surf.fill((0, 0, 0))
    board_render.draw_unit(surf, fonts(), pygame.Rect(0, 0, 64, 64), _tok(team, **kw))
    return surf

def _near(c, ref, tol=40):
    return all(abs(a - b) <= tol for a, b in zip(c[:3], ref))

def _screen():
    from editor.battle_screen import BattleScreen
    pygame.init()
    batt, a, d = _melee_battle()
    scr = BattleScreen(fonts(), batt, on_battle_end=lambda *x: None)
    return scr, batt, a, d


def test_a_foe_stands_on_a_diamond_and_the_squad_on_a_disc():
    pygame.init()
    foe, mine = _draw("enemy"), _draw("player")
    # the diamond's tip reaches the top edge at the centre; the disc leaves the corner empty
    assert _near(foe.get_at((32, 2)), ENEMY_C)
    assert _near(mine.get_at((32, 2)), PLAYER_C)
    assert tuple(foe.get_at((4, 4)))[:3] == (0, 0, 0)


def test_the_banner_colour_never_paints_the_side():
    pygame.init()
    banner.set_player_color(ENEMY_C)
    try:
        mine = _draw("player")
        assert _near(mine.get_at((32, 2)), PLAYER_C)
    finally:
        banner.set_player_color(PLAYER_C)


def test_the_dead_leave_a_grey_cross():
    pygame.init()
    surf = pygame.Surface((64, 64))
    view = BoardView(1, 1)
    view.fit(pygame.Rect(0, 0, 64, 64))
    board_render.draw_props(surf, fonts(), view, [{"kind": "corpse", "pos": (0, 0), "size": 1}])
    r = view.cell_rect(0, 0)
    assert _near(surf.get_at(r.center), CORPSE_INK, tol=12)


def test_a_corpse_is_a_ground_mark_the_fog_remembers():
    scr, batt, a, d = _screen()
    d.status = "dead"
    corpses = [p for p in scr._ground_props() if p["kind"] == "corpse"]
    assert corpses == [{"kind": "corpse", "pos": d.pos, "size": d.footprint}]


def test_sides_follow_the_seat_in_a_hot_seat_fight():
    scr, batt, a, d = _screen()
    scr.controllers = {"player": "human", "enemy": "human"}
    batt.order, batt.turn_idx = [a, d], 0
    assert (scr._side(a), scr._side(d)) == ("player", "enemy")
    batt.turn_idx = 1
    assert scr.me == "enemy"
    assert (scr._side(a), scr._side(d)) == ("enemy", "player")
