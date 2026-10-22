"""One load reading on every screen: the bar runs to the most a body takes, the tick marks where it slows."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from gartok.ui import load_meter as lm
from gartok.ui.tokens import T


def test_state_reads_both_limits():
    assert lm.state(10, 15, 35) == lm.FREE
    assert lm.state(20, 15, 35) == lm.SLOWED
    assert lm.state(35, 15, 35) == lm.FULL
    assert lm.state(50, 15, 35) == lm.FULL


def test_the_figure_is_always_against_the_most():
    assert lm.figure(18, 15, 35) == "18 / 35 kg"
    assert lm.figure(17.25, 15, 35) == "17.2 / 35 kg"


def test_a_single_limit_has_no_slowed_zone():
    assert lm.state(9, 10, 10) == lm.FREE
    assert lm.note(9, 10, 10) == ""
    assert lm.note(10, 15, 35) == "slows past 15"
    assert lm.note(20, 15, 35) == "slowed past 15"


def _colors_along(kg, normal, most):
    surf = pygame.Surface((102, 6))
    lm.draw_bar(surf, pygame.Rect(0, 0, 102, 6), kg, normal, most)
    return [tuple(surf.get_at((x, 3))[:3]) for x in range(1, 101)]


def test_the_bar_is_green_to_the_tick_then_amber():
    row = _colors_along(25, 15, 35)
    assert row[10] == T.GREEN[:3]
    assert row[55] == lm.AMBER
    assert row[90] == T.TABLE[:3]


def test_a_full_bar_is_blood():
    assert set(_colors_along(40, 15, 35)[50:]) == {T.BLOOD[:3]}
