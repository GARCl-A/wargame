"""The sandbox character/map creators and their git-tracked libraries."""

from tests.helpers import Unit

def test_map_editor_trap_tool():
    import pygame
    from editor.map_editor_screen import MapEditorScreen
    from editor.ui.tokens import fonts as ui_fonts

    ed = MapEditorScreen(ui_fonts(), lambda: None)
    ed.tool = "trap"

    # Fake cell click at (4, 4)
    # Event button 1: place bear trap
    ev1 = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (0, 0), "button": 1})
    ed._cell_at = lambda p: (4, 4)
    ed.handle_event(ev1)
    assert ed.traps.get((4, 4)) == "bear trap"

    # Click again: toggle to alarm trap
    ed.handle_event(ev1)
    assert ed.traps.get((4, 4)) == "alarm trap"

    # Event button 3: right click clears
    ev3 = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (0, 0), "button": 3})
    ed.handle_event(ev3)
    assert (4, 4) not in ed.traps

    # Add back and verify _to_dict
    ed.handle_event(ev1)
    d = ed._to_dict()
    assert d["traps"] == [[4, 4, "bear trap"]]


def test_map_editor_secret_wall_and_escape_tools():
    import pygame
    from editor.map_editor_screen import MapEditorScreen
    from editor.ui.tokens import fonts as ui_fonts

    ed = MapEditorScreen(ui_fonts(), lambda: None)
    ed._cell_at = lambda p: (5, 5)

    # Paint secret wall
    ed.tool = "secret_wall"
    ev1 = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (0, 0), "button": 1})
    ed.handle_event(ev1)
    assert (5, 5) in ed.walls
    assert (5, 5) in ed.secret_walls

    # Erase secret wall
    ev3 = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (0, 0), "button": 3})
    ed.handle_event(ev3)
    assert (5, 5) not in ed.walls
    assert (5, 5) not in ed.secret_walls

    # Paint escape zone
    ed.tool = "escape"
    ed.handle_event(ev1)
    assert (5, 5) in ed.escape_cells
    assert ed._to_dict()["escape_cells"] == [[5, 5]]

    # Erase escape zone
    ed.handle_event(ev3)
    assert (5, 5) not in ed.escape_cells


def test_map_editor_container_and_item_tools():
    import pygame
    from editor.map_editor_screen import MapEditorScreen
    from editor.ui.tokens import fonts as ui_fonts

    ed = MapEditorScreen(ui_fonts(), lambda: None)
    ed._cell_at = lambda p: (7, 3)

    # Click with chest tool: creates chest and opens ("chest", (7, 3)) modal
    ed.tool = "chest"
    ev1 = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (0, 0), "button": 1})
    ed.handle_event(ev1)
    assert (7, 3) in ed.chests
    assert ed.picking == ("chest", (7, 3))

    # Add item to chest: simulate button click to open add picker
    ed._picker_box = pygame.Rect(0, 0, 800, 600)
    ed.picker_hits = [(pygame.Rect(10, 10, 50, 50), ("open_chest_add", None))]
    ed._picker_click((20, 20))
    assert ed.picking == ("chest_add", (7, 3))

    # Select item to add
    ed.picker_hits = [(pygame.Rect(10, 10, 50, 50), ("chest_add_item", "Scroll of Sleep"))]
    ed._picker_click((20, 20))
    assert ed.chests[(7, 3)] == ["Scroll of Sleep"]
    assert ed.picking == ("chest", (7, 3))

    # Add a second item
    ed.picker_hits = [(pygame.Rect(10, 10, 50, 50), ("open_chest_add", None))]
    ed._picker_click((20, 20))
    ed.picker_hits = [(pygame.Rect(10, 10, 50, 50), ("chest_add_item", "Semi-precious Gemstone"))]
    ed._picker_click((20, 20))
    assert ed.chests[(7, 3)] == ["Scroll of Sleep", "Semi-precious Gemstone"]

    # Remove the first item
    ed.picker_hits = [(pygame.Rect(10, 10, 50, 50), ("chest_remove_item", 0))]
    ed._picker_click((20, 20))
    assert ed.chests[(7, 3)] == ["Semi-precious Gemstone"]

    # Close modal
    ed.picker_hits = [(pygame.Rect(10, 10, 50, 50), ("close", None))]
    ed._picker_click((20, 20))
    assert ed.picking is None

    # Serialization contains chest
    d = ed._to_dict()
    assert d["chests"] == [[7, 3, ["Semi-precious Gemstone"]]]

    # Right-click removes chest
    ev3 = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (0, 0), "button": 3})
    ed.handle_event(ev3)
    assert (7, 3) not in ed.chests

    # Test item tool: click cell (8, 4)
    ed._cell_at = lambda p: (8, 4)
    ed.tool = "item"
    ed.handle_event(ev1)
    assert ed.picking == ("item", (8, 4))

    # Pick item
    ed.picker_hits = [(pygame.Rect(10, 10, 50, 50), ("set_relic", "Ancient Codex"))]
    ed._picker_click((20, 20))
    assert ed.relics.get((8, 4)) == "Ancient Codex"
    assert ed.picking is None
    assert ed._to_dict()["relics"] == [[8, 4, "Ancient Codex"]]

    # Right-click clears relic
    ed.handle_event(ev3)
    assert (8, 4) not in ed.relics


def test_sheet_hides_the_magic_block_until_initiated():
    from gartok.combatant import Combatant
    from gartok.sheet import unit_to_ch
    from editor.ui.sheet_card import sheet_height
    u = Unit("player")
    plain = sheet_height("normal", ch=unit_to_ch(Combatant(u)))
    u.set_magic_source("faith")
    assert sheet_height("normal", ch=unit_to_ch(Combatant(u))) > plain
    assert sheet_height("normal") == sheet_height("normal", ch=unit_to_ch(Combatant(u)))
