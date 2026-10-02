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
    group = Group(list(g.roster), "library")
    
    done_called = False
    def on_done():
        nonlocal done_called
        done_called = True

    node = world.node("library")
    screen = LibraryHubScreen(F, g, group, node, on_done)
    screen.mouse = (100, 100)
    screen.draw(surf)


def test_library_dictionary_mission_flow():
    from gartok import missions
    u = Unit("player")
    u.languages = ["Ankarin", "Elvish"]
    g = Guild([u])
    group = Group(list(g.roster), "library")

    offers = missions.offers_at(g, "library")
    assert any(t.id == "library_dictionary" for t in offers)

    template = next(t for t in offers if t.id == "library_dictionary")
    m = missions.accept(g, u, template)
    assert m.state == "active"
    assert missions.progress(g, m) == 0
    assert not missions.can_turn_in(g, m)

    u.give_to_pack("Dictionary of Elvish")
    assert missions.progress(g, m) == 1
    assert missions.can_turn_in(g, m)

    u.gold = 0
    earned_deeds = missions.turn_in(g, m)
    assert m.state == "done"
    assert not u.has_item("Dictionary of Elvish")
    assert u.gold == 250
    assert "library_initiate" in g.deeds_done
    assert g.reputation["library"] == 1


def test_map_screen_library_button_label():
    from gartok.map_screen import MapScreen
    from gartok.theme import Fonts
    u = Unit("player")
    g = Guild([u])
    grp = Group(list(g.roster), "library")
    g.active_group = grp
    ms = MapScreen(Fonts(), g, lambda: None, lambda: None, lambda: None, lambda g: None)
    blocks = ms._inspector_content(grp, world.node("library"))
    btn = next((b for b in blocks if b.get("key") == "library"), None)
    assert btn is not None
    assert btn["label"] == "VISIT THE LIBRARY"

