import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
from unittest.mock import MagicMock

import pygame

from gartok import arena, world
from gartok.squad_screen import SquadScreen
from gartok.unit import Unit


def test_squad_screen_init_and_properties():
    if hasattr(pygame, "font") and hasattr(pygame.font, "init") and not pygame.font.get_init():
        pygame.font.init()

    u0 = Unit("player", name="Unit0")
    u1 = Unit("player", name="Unit1")
    u2 = Unit("player", name="Unit2")
    u0.money = 50
    u1.money = 10
    u2.money = 5

    # Disabled unit (e.g. starving)
    scr = SquadScreen(None, [u0, u1, u2], world.node("arena"),
                      on_confirm=lambda *a: None, on_back=lambda: None,
                      max_pick=2, disabled={u2})
    assert u2 not in scr.picked
    assert len(scr.picked) == 2
    assert scr.picked_gold == 60
    assert scr.ok
    assert scr.tutorial_key() == "squad"


def test_squad_screen_arena_tiers_and_trimmed_pick():
    u0 = Unit("player", name="Unit0")
    u1 = Unit("player", name="Unit1")
    u2 = Unit("player", name="Unit2")
    u0.money = 100
    u1.money = 100
    u2.money = 100

    scr = SquadScreen(None, [u0, u1, u2], world.node("arena"),
                      on_confirm=lambda *a: None, on_back=lambda: None,
                      arena_offers=[arena.defense_bout(), arena.brawl_bout()])
    # defense bout has player_cap == 1; since roster (3) > max_pick (1), picked starts empty
    assert scr.max_pick == 1
    assert len(scr.picked) == 0
    scr._toggle(u0)
    assert len(scr.picked) == 1
    assert scr.picked == [u0]

    # Switch to brawl (player_cap == 3)
    scr.offer_idx = 1
    assert scr.max_pick == 3
    scr._toggle(u1)
    scr._toggle(u2)
    assert len(scr.picked) == 3

    # Switch back to scrapper: excess members are trimmed
    scr._click(scr.tiers[0][0].center if scr.tiers else (0, 0))
    scr.offer_idx = 0
    del scr.picked[scr.max_pick:]
    assert len(scr.picked) == 1


def test_squad_screen_draw_and_callbacks():
    u = Unit("player", name="Unit0")
    u.money = 50
    confirmed = []
    backed = []

    scr = SquadScreen(None, [u], world.node("arena"),
                      on_confirm=lambda p, loc, off: confirmed.append((p, loc, off)),
                      on_back=lambda: backed.append(True))
    surf = pygame.Surface((1280, 800))
    scr.draw(surf)

    # Click confirm
    confirm_rect = next(r for k, r in scr.buttons if k == "confirm")
    scr._click(confirm_rect.center)
    assert len(confirmed) == 1

    # Click back
    back_rect = next(r for k, r in scr.buttons if k == "back")
    scr._click(back_rect.center)
    assert backed == [True]


def test_squad_screen_scrolling():
    # Large roster that overflows vertical card area
    roster = [Unit("player", name=f"Unit{i}") for i in range(12)]
    scr = SquadScreen(None, roster, world.node("arena"),
                      on_confirm=lambda *a: None, on_back=lambda: None)
    surf_small = pygame.Surface((1280, 500))
    scr.draw(surf_small)
    assert scr._max_scroll > 0

    # Mouse wheel down
    evt_wheel = MagicMock(type=pygame.MOUSEWHEEL, y=-1)
    scr.handle_event(evt_wheel)
    assert scr._scroll == 36

    # Mouse wheel up
    evt_up = MagicMock(type=pygame.MOUSEWHEEL, y=1)
    scr.handle_event(evt_up)
    assert scr._scroll == 0

    # Key down
    evt_dn = MagicMock(type=pygame.KEYDOWN, key=pygame.K_DOWN)
    scr.handle_event(evt_dn)
    assert scr._scroll == 36
