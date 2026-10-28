import pygame

from gartok import world
from gartok.apothecary_hub_screen import ApothecaryHubScreen
from gartok.group import Group
from gartok.guild import Guild
from gartok.library_hub_screen import LibraryHubScreen
from gartok.ui.tokens import fonts as ui_fonts
from gartok.unit import Unit
from tests.helpers import packed


def test_apothecary_hub_screen_loads():
    pygame.init()
    surf = pygame.Surface((1280, 800))
    F = ui_fonts()

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
    F = ui_fonts()

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

    u.money = 0
    earned_deeds = missions.turn_in(g, m)
    assert m.state == "done"
    assert not u.has_item("Dictionary of Elvish")
    assert u.money == 250
    assert "library_initiate" in g.deeds_done
    assert g.reputation["library"] == 1


def test_library_shop_locked_before_rep_and_rejects_stocked_dictionaries():
    from gartok import missions
    from gartok.trade import library_stock_dictionaries
    u = Unit("player")
    g = Guild([u])
    group = Group(list(g.roster), "library")
    # Rep == 0: shop has no dictionaries
    assert library_stock_dictionaries(g) == []

    # Rep == 1: shop sells 1 dictionary
    g.reputation["library"] = 1
    stocked = library_stock_dictionaries(g)
    assert len(stocked) == 1
    stocked_dict = stocked[0]

    # Accepting mission and having the stocked dictionary does NOT count
    template = missions.LIBRARY_DICTIONARY
    m = missions.accept(g, u, template)
    u.give_to_pack(stocked_dict)
    assert missions.progress(g, m) == 0
    assert not missions.can_turn_in(g, m)



def test_map_screen_library_button_label():
    from gartok.map_screen import MapScreen
    from gartok.ui.tokens import fonts as ui_fonts
    u = Unit("player")
    g = Guild([u])
    grp = Group(list(g.roster), "library")
    g.active_group = grp
    ms = MapScreen(ui_fonts(), g, lambda: None, lambda: None, lambda: None, lambda g: None)
    blocks = ms._inspector_content(grp, world.node("library"))
    btn = next((b for b in blocks if b.get("key") == "library"), None)
    assert btn is not None
    assert btn["label"] == "VISIT THE LIBRARY"


def test_taverna_hub_screen_flow():
    from gartok.taverna_screen import TavernaScreen
    pygame.init()
    surf = pygame.Surface((1280, 800))
    F = ui_fonts()

    u1 = Unit("player")
    u1.name = "Garrick"
    u1.languages = ["Ankarin"]
    u1.magic_sources = ["nature"]
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
    assert group.order is None                      # nobody has a target yet
    u2.study_target = "Dwarvish"
    screen.draw(surf)
    rent_btn = next(r for key, r in screen.buttons if key == "rent_study")
    screen.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": rent_btn.center}))
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



def test_taverna_perform_tab_plays_a_show():
    from gartok.taverna_screen import TavernaScreen
    from tests.helpers import fixed_d20
    pygame.init()
    surf = pygame.Surface((1280, 800))
    bard, mute = Unit("player"), Unit("player")
    bard.set_base_attribute("charisma", 18)
    bard._base_inventory = packed(["Musical Instrument"])
    mute._base_inventory = []
    bard.money = mute.money = 0
    g = Guild([bard, mute])
    group = Group(list(g.roster), "city")
    screen = TavernaScreen(ui_fonts(), g, list(group.members), "city", lambda: None, group=group)
    screen.mouse = (100, 100)
    screen.draw(surf)

    def click(key):
        r = next(r for k, r in screen.buttons if k == key)
        screen.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": r.center}))
        screen.draw(surf)

    click("tab_perform")
    assert screen.tab == "perform"
    click("perf_hours_2")
    assert screen.perform_hours == 2
    assert not any(k == "perf_toggle_1" for k, _ in screen.buttons)       # no instrument, no toggle
    click("perf_toggle_0")                                                # bench the bard
    assert not screen._performers()
    click("perf_toggle_0")
    with fixed_d20(20):
        click("perform_go")
    assert bard.money == 2 * ((20 + bard.mod_charisma - 16) // 2) > 0 and mute.money == 0
    assert "Tavern stage" in screen.notice


def test_every_node_builds_as_a_tabbed_hub():
    """`TabbedHubScreen.for_node` wires a screen per function; a wrong constructor call
    only surfaces when that node is entered, so build and draw one for each node."""
    from gartok.hub_screen import TabbedHubScreen
    pygame.init()
    surf = pygame.display.set_mode((1280, 720))
    guild = Guild([Unit("player") for _ in range(3)], node=world.START_NODE)
    for node in world.NODES:
        scr = TabbedHubScreen.for_node(ui_fonts(), guild, guild.groups[0], node, on_done=lambda *a: None)
        scr.mouse = (10, 10)
        scr.draw(surf)


def test_a_work_node_opened_from_the_map_shows_its_gathering_tab():
    from types import SimpleNamespace

    from gartok.app_nodes import NodeScreensMixin
    pygame.init()
    guild = Guild([Unit("player")], node="mine")
    app = SimpleNamespace(guild=guild, ui_fonts=ui_fonts(), scene=None, _after_activity=lambda: None)
    for node_id in ("mine", "lumber_yard"):
        NodeScreensMixin._open_market_stalls(app, list(guild.roster), world.node(node_id), None)
        assert [k for k, _l, _s in app.scene.tabs] == ["shop", "work", "gather"]


def test_a_work_node_opens_for_the_group_that_clicked_not_the_first_one_there():
    from types import SimpleNamespace

    from gartok.app import App
    pygame.init()
    guild = Guild([Unit("player"), Unit("player")], node="lumber_yard")
    second = guild.split_group(guild.groups[0], [guild.roster[1]])
    app = SimpleNamespace(guild=guild, ui_fonts=ui_fonts(), scene=None, _after_activity=lambda: None,
                          _work_shift=lambda *a: None)
    app._open_market_stalls = lambda *a, **k: App._open_market_stalls(app, *a, **k)
    App._FUNCTION_OPENERS["shop"](app, second, world.node("lumber_yard"), None)
    work = next(s for k, _l, s in app.scene.tabs if k == "work")
    assert work.group is second


def _work_screen(node_id="mine"):
    from gartok.group import Group
    from gartok.work_screen import WorkScreen
    pygame.init()
    u = Unit("player")
    u._base_inventory = []
    u.equipped_weapon = None
    g = Guild([u], node=node_id)
    done = []
    scr = WorkScreen(ui_fonts(), g, g.groups[0], world.node(node_id), lambda: done.append(1))
    return scr, g, u, done


def test_the_work_tab_issues_a_paid_shift_and_closes():
    scr, g, u, done = _work_screen()
    scr.draw(pygame.Surface((1600, 800)))
    assert [k for k, _ in scr.buttons] == [f"work:{h}" for h in (4, 8, 12, 16)]
    scr._on_button("work:8")
    group = g.groups[0]
    assert group.order.kind == "work" and not group.order.gather and group.order.hours == 8
    assert done == [1]


def test_the_work_tab_pays_by_each_workers_tool():
    from gartok import economy, progression
    scr, g, u, _ = _work_screen("lumber_yard")
    assert scr._wage(16) == economy.work_pay("lumber_yard", 16, economy.work_level(u, "lumber_yard"))
    assert scr._crew_note(u, "Axe") is None
    u.work_hours = economy.LUMBER_XP_HOURS * next(x for x in range(1000) if progression.work_level(x) >= 1)
    note, tone = scr._crew_note(u, "Axe")
    assert "bare-handed" in note and tone == "money"
    assert scr.hub_cards()[0]["value"] == f"${scr._wage(16)}"


def test_the_study_list_of_a_big_party_stays_inside_its_panel_and_scrolls():
    from gartok.taverna_screen import TavernaScreen
    pygame.init()
    surf = pygame.Surface((1280, 720))
    party = [Unit("player") for _ in range(10)]
    g = Guild(party)
    group = Group(list(g.roster), "city")
    screen = TavernaScreen(ui_fonts(), g, party, "city", lambda: None, group=group)
    screen.mouse = (0, 0)
    screen.tab = "rooms"
    screen.draw(surf)
    area = screen.list_area
    targets = [r for k, r in screen.buttons if k.startswith("choose_target_")]
    assert screen.list_max > 0 and targets and all(area.contains(r) for r in targets)
    assert len(targets) < len(party)

    screen.mouse = area.center
    for _ in range(20):
        screen.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, {"x": 0, "y": -1}))
    screen.draw(surf)
    assert screen.list_scroll == screen.list_max
    assert any(k == f"choose_target_{len(party) - 1}" for k, _ in screen.buttons)


def test_a_sheet_opened_in_a_shop_tab_covers_the_whole_window():
    """The tab draws on a subsurface below the header; the sheet would be cropped there."""
    from gartok.hub_screen import TabbedHubScreen
    pygame.init()
    surf = pygame.display.set_mode((1280, 720))
    guild = Guild([Unit("player") for _ in range(2)], node="city")
    node = next(n for n in world.NODES if n.has("shop"))
    scr = TabbedHubScreen.for_node(ui_fonts(), guild, guild.groups[0], node, on_done=lambda *a: None)
    shop = scr.active_screen()
    shop.open_sheet(guild.roster[0])
    scr.mouse = (10, 10)
    drawn = []
    shop.draw_sheet_modal = lambda s, fonts=None, *, host=False: drawn.append((s.get_size(), host))
    scr.draw(surf)
    assert drawn[-1] == ((1280, 720), True)
