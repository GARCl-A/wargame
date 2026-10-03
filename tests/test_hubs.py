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


def test_taverna_hub_screen_flow():
    from gartok.taverna_screen import TavernaScreen
    from gartok import orders
    pygame.init()
    surf = pygame.Surface((1280, 800))
    F = Fonts()

    u1 = Unit("player")
    u1.name = "Garrick"
    u1.languages = ["Ankarin"]
    u1.magic_source = "sorcery"
    u1.spells_known = []

    u2 = Unit("player")
    u2.name = "Lyra"
    u2.languages = ["Ankarin"]
    u2.give_to_pack("Scroll of Magic Missile")
    u2.give_to_pack("Dictionary of Dwarvish")

    g = Guild([u1, u2])
    group = Group(list(g.roster), "city")

    done_called = False
    def on_done():
        nonlocal done_called
        done_called = True

    screen = TavernaScreen(F, g, list(group.members), "city", on_done, group=group)
    assert screen.tab == "recruits"
    screen.mouse = (100, 100)
    screen.draw(surf)

    # 1. Switch to study/rooms tab
    tab_rooms_btn = next((r for key, r in screen.buttons if key == "tab_rooms"), None)
    assert tab_rooms_btn is not None
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": tab_rooms_btn.center})
    screen.handle_event(ev)
    assert screen.tab == "rooms"

    screen.draw(surf)

    # 2. Rent study rooms
    rent_btn = next((r for key, r in screen.buttons if key == "rent_study"), None)
    assert rent_btn is not None
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": rent_btn.center})
    screen.handle_event(ev)
    assert group.order is not None
    assert group.order.kind == "garrison" and group.order.job == "study"

    # Redraw and cancel study rooms
    screen.draw(surf)
    cancel_btn = next((r for key, r in screen.buttons if key == "cancel_study"), None)
    assert cancel_btn is not None
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": cancel_btn.center})
    screen.handle_event(ev)
    assert group.order is None

    # 3. Open study target picker for u1 (carried items are held by u2!)
    screen.draw(surf)
    choose_u1_btn = next((r for key, r in screen.buttons if key == "choose_target_0"), None)
    assert choose_u1_btn is not None
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": choose_u1_btn.center})
    screen.handle_event(ev)
    assert screen.study_modal_member is u1

    # In modal, u1 can pick either Scroll of Magic Missile or Dictionary of Dwarvish
    screen.draw(surf)
    set_target_btns = [btn for btn in screen.modal_buttons if btn[0] == "set_target"]
    assert len(set_target_btns) >= 2

    # Click first target (Magic Missile)
    target_opt = set_target_btns[0]
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": target_opt[1].center})
    screen.handle_event(ev)
    assert screen.study_modal_member is None
    assert u1.study_target == target_opt[2]["id"]

    # 4. Stop studying
    screen.draw(surf)
    stop_u1_btn = next((r for key, r in screen.buttons if key == "stop_study_0"), None)
    assert stop_u1_btn is not None
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": stop_u1_btn.center})
    screen.handle_event(ev)
    assert u1.study_target is None

    # 5. Switch back to recruits tab and test candidate pitch
    tab_recruits_btn = next((r for key, r in screen.buttons if key == "tab_recruits"), None)
    assert tab_recruits_btn is not None
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": tab_recruits_btn.center})
    screen.handle_event(ev)
    assert screen.tab == "recruits"

    # Select candidate and recruiter
    if screen.candidates:
        screen.draw(surf)
        assert screen.sel is not None
        convince_btn = next((r for key, r in screen.buttons if key == "convince"), None)
        assert convince_btn is not None

