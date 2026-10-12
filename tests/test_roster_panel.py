"""Tests for gartok.ui.roster_panel and MapScreen group roster money display."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from gartok import world
from gartok.constants import fmt_money
from gartok.group import Group
from gartok.guild import Guild
from gartok.map_screen import MapScreen
from gartok.ui.roster_panel import CARD_H, draw_roster
from gartok.ui.tokens import T
from gartok.ui.tokens import fonts as ui_fonts
from tests.helpers import Unit


@pytest.fixture(scope="module", autouse=True)
def _init_pygame():
    pygame.init()
    if not pygame.display.get_surface():
        pygame.display.set_mode((1, 1))


def _sample_group(**kw):
    g = {
        "key": "g-1",
        "name": "Alpha Squad",
        "lead": "Leader",
        "state_label": "IDLE",
        "state_color": T.GREEN,
        "needs_orders": False,
        "detail": "At Crossroad",
        "rations_label": "RATIONS: 5",
        "money_label": "MONEY: $150",
        "party": [("Hero", "Fighter", 1.0, "Human", "")],
        "roster_members": [("u1", "Hero", "LVL 1")],
        "mates": [],
    }
    g.update(kw)
    return g


def test_draw_roster_renders_with_money_label():
    F = ui_fonts()
    surf = pygame.Surface((300, 400))
    groups = [_sample_group()]
    rects, split_rects, confirm_rect, merge_rects = draw_roster(
        surf, F, pygame.Rect(0, 0, 300, 400), groups, [], selected="g-1"
    )
    assert len(rects) == 1
    # Card surface should have rendered non-black pixels in the card area
    card_rect, key, gear_rect = rects[0]
    assert key == "g-1"
    assert card_rect.h == CARD_H
    # Verify pixels are drawn on the surface
    drawn_pixels = sum(
        1 for x in range(card_rect.x, card_rect.right, 4)
        for y in range(card_rect.y, card_rect.bottom, 4)
        if surf.get_at((x, y))[:3] != (0, 0, 0)
    )
    assert drawn_pixels > 0


def test_draw_roster_backward_compatible_without_money_label():
    F = ui_fonts()
    surf = pygame.Surface((300, 400))
    g = _sample_group()
    del g["money_label"]
    rects, _, _, _ = draw_roster(
        surf, F, pygame.Rect(0, 0, 300, 400), [g], [], selected="g-1"
    )
    assert len(rects) == 1


def test_draw_roster_without_rations_label():
    F = ui_fonts()
    surf = pygame.Surface((300, 400))
    g = _sample_group(rations_label="")
    rects, _, _, _ = draw_roster(
        surf, F, pygame.Rect(0, 0, 300, 400), [g], [], selected="g-1"
    )
    assert len(rects) == 1


def test_map_screen_group_dict_includes_money_label():
    F = ui_fonts()
    u1 = Unit("player")
    u2 = Unit("player")
    u1.money = 75
    u2.money = 125
    group = Group([u1, u2], node=world.START_NODE)
    guild = Guild(None, groups=[group])

    ms = MapScreen(F, guild, lambda: None, lambda: None, lambda: None, lambda: None)
    gd = ms._group_dict(group)

    assert "money_label" in gd
    assert gd["money_label"] == f"MONEY: {fmt_money(200)}"
    assert gd["rations_label"] == f"RATIONS: {group.rations}"


def test_map_screen_group_dict_zero_money():
    F = ui_fonts()
    u = Unit("player")
    u.money = 0
    group = Group([u], node=world.START_NODE)
    guild = Guild(None, groups=[group])

    ms = MapScreen(F, guild, lambda: None, lambda: None, lambda: None, lambda: None)
    gd = ms._group_dict(group)

    assert gd["money_label"] == "MONEY: $0"
