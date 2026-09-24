import pytest
import pygame
from gartok.library_hub_screen import LibraryHubScreen
from gartok.apothecary_hub_screen import ApothecaryHubScreen
from gartok.unit import Unit
from gartok.guild import Guild
from gartok.group import Group
from gartok.ui.tokens import fonts as Fonts
from gartok import world

def test_apothecary_hub_screen_loads():
    pygame.init()
    surf = pygame.Surface((1280, 800))
    F = Fonts()

    u = Unit("player")
    g = Guild([u])
    group = Group(list(g.roster), "city")
    
    done_called = False
    def on_done():
        nonlocal done_called
        done_called = True

    screen = ApothecaryHubScreen(F, g, group, on_done)
    screen.mouse = (100, 100)
    screen.draw(surf)

def test_library_hub_screen_loads():
    pygame.init()
    surf = pygame.Surface((1280, 800))
    F = Fonts()

    u = Unit("player")
    g = Guild([u])
    group = Group(list(g.roster), "city")
    
    done_called = False
    def on_done():
        nonlocal done_called
        done_called = True

    node = world.node("library")
    screen = LibraryHubScreen(F, g, group, node, on_done)
    screen.mouse = (100, 100)
    screen.draw(surf)
