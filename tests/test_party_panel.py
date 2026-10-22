"""The Wilds party rows: HP / AC / load / rations and the work-XP bar."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from gartok.ui.party_panel import draw_party_stats, party_load
from gartok.ui.tokens import T
from gartok.ui.tokens import fonts as ui_fonts


def _row(**kw):
    row = {"hp": (4, 7), "ac": 12, "load": (3.0, 10.0, 25.0), "rations": 2, "work": (1, 5, 30)}
    row.update(kw)
    return row


def test_party_load_sums_weight_and_both_limits():
    assert party_load([_row(), _row(load=(7.5, 20.0, 40.0))]) == (10.5, 30.0, 65.0)


def test_stats_draw_for_a_normal_and_a_maxed_worker():
    pygame.init()
    F = ui_fonts()
    for row in (_row(), _row(work=(15, 0, 0)), _row(load=(12.0, 10.0, 25.0), hp=(0, 7))):
        surf = pygame.Surface((400, 74))
        draw_party_stats(surf, F, pygame.Rect(0, 0, 400, 74), row)
        assert any(surf.get_at((x, y))[:3] != (0, 0, 0) for x in range(0, 400, 4) for y in range(0, 74, 4))


def test_work_bar_fills_with_progress():
    pygame.init()
    F = ui_fonts()

    def filled(into):
        surf = pygame.Surface((400, 74))
        draw_party_stats(surf, F, pygame.Rect(0, 0, 400, 74), _row(work=(1, into, 30)))
        bar_y = 8 + (16 + 2) * 2 + 3 + 3
        return sum(1 for x in range(400 - 16 - 96, 400 - 16) if surf.get_at((x, bar_y))[:3] == tuple(T.BRASS[:3]))

    assert filled(0) == 0 and filled(15) > filled(3) > 0
