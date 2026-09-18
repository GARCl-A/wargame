import pytest
import pygame
from gartok.loot_screen import LootScreen
from gartok.unit import Unit
from gartok.guild import Guild
from gartok.ui.tokens import fonts as Fonts

def test_loot_screen_interactions():
    pygame.init()
    surf = pygame.Surface((1280, 800))
    F = Fonts()

    u = Unit("player")
    # Equip and pack
    u.equipped_weapon = "Dagger"
    u._base_inventory = [("Torch", 1), ("Rope", 2)]
    g = Guild([u])
    
    # Mock pool with 2 axes to show plus/minus buttons
    pool = ["Axe", "Axe", "Rope"]
    
    done_called = False
    def on_done():
        nonlocal done_called
        done_called = True

    ls = LootScreen(F, g, [u], pool, on_done)
    
    # Draw screen to populate interactable zones
    ls.mouse = (100, 100)
    ls.draw(surf)

    def sim_click(screen, pos):
        screen.mouse = pos
        screen.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": 1}))
        screen.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, {"pos": pos, "button": 1}))

    # 1. Take from pool
    # Find the plus button for the "Axe" (index 0) in the pool
    plus_btn = None
    for rect, key, delta in ls._chest_steppers:
        if key == 0 and delta == 1:
            plus_btn = rect
            break
            
    assert plus_btn is not None
    # Simulate clicking plus
    sim_click(ls, plus_btn.center)
    assert ls._sel_qty[("pool", 0)] == 2
    
    # 2. Drop into unit's pack
    # Find the pack zone
    pack_zone = None
    for rect, owner, kind in ls.zones:
        if owner == u and kind == "pack":
            pack_zone = rect
            break
            
    assert pack_zone is not None
    ls._drop(pack_zone.center, dragging=True, src=("pool", 0))
    # It should have transferred
    assert u.has_item("Axe")
    # Axe is no longer in pool
    assert "Axe" not in ls.pool

    # 3. Test clicking Done
    done_btn = None
    for rect, key in ls._service_hits:
        if key == "done":
            done_btn = rect
            break
            
    assert done_btn is not None
    sim_click(ls, done_btn.center)
    assert done_called
