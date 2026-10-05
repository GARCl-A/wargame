"""The sandbox character/map creators and their git-tracked libraries."""

import random

from gartok import persist
from tests.helpers import COLS, Battle, CustomScenario, Unit, _unit


def test_map_npc_units_pins_a_library_character_to_its_cell():
    import shutil
    import tempfile

    from gartok import map_lib, npc_lib
    o1, npc_lib.NPC_DIR = npc_lib.NPC_DIR, tempfile.mkdtemp()
    o2, map_lib.MAP_DIR = map_lib.MAP_DIR, tempfile.mkdtemp()
    try:
        boss = _unit(seed=2)
        boss.set_name("Adelio")
        slug = npc_lib.save_npc(boss)
        m = map_lib.new_map("Ambush")
        m["deploy_npc"] = [[9, 7, slug]]
        m["deploy_enemy"] = [[14, 2]]
        map_lib.save_map(m)

        data_ = map_lib.load_map("ambush")
        npcs = map_lib.npc_units(data_)
        assert len(npcs) == 1
        assert npcs[0].name == "Adelio" and npcs[0].map_cell == (9, 7)

        random.seed(0)
        batt = Battle([Unit("player")], npcs + [Unit("enemy")],
                      scenario=CustomScenario(data_))
        adelio = next(c for c in batt.enemy_units if c.name == "Adelio")
        other = next(c for c in batt.enemy_units if c.name != "Adelio")
        assert adelio.pos == (9, 7)                     # pinned to its cell
        assert other.pos[0] >= COLS - 3                 # generic enemy: edge columns
    finally:
        shutil.rmtree(npc_lib.NPC_DIR, ignore_errors=True)
        npc_lib.NPC_DIR = o1
        shutil.rmtree(map_lib.MAP_DIR, ignore_errors=True)
        map_lib.MAP_DIR = o2


def test_map_library_round_trips_a_laid_out_map():
    import shutil
    import tempfile

    from gartok import map_lib
    old, map_lib.MAP_DIR = map_lib.MAP_DIR, tempfile.mkdtemp()
    try:
        m = map_lib.new_map("Pit of Grix")
        m["walls"] = {(8, 5), (8, 4)}
        m["deploy_player"] = {(1, 1)}
        m["elevation"] = [[6, 5, -2], [7, 5, -3]]
        m["ropes"] = [[6, 5]]
        slug = map_lib.save_map(m)
        assert slug == "pit-of-grix"
        assert [r["slug"] for r in map_lib.list_maps()] == ["pit-of-grix"]
        back = map_lib.load_map(slug)
        assert back["walls"] == [[8, 4], [8, 5]]        # sorted on write
        assert back["name"] == "Pit of Grix"
        assert back["elevation"] == [[6, 5, -2], [7, 5, -3]] and back["ropes"] == [[6, 5]]
        random.seed(0)
        batt = Battle([Unit("player")], [Unit("enemy")],
                      scenario=CustomScenario(back))
        assert (8, 5) in batt.board.walls
        assert batt.board.elevation_at((7, 5)) == -3
        assert batt.board.surface_dc((6, 5)) == 10      # a rope drops the climb DC
        map_lib.delete_map(slug)
        assert map_lib.list_maps() == []
    finally:
        shutil.rmtree(map_lib.MAP_DIR, ignore_errors=True)
        map_lib.MAP_DIR = old


def test_map_library_round_trips_size_and_water():
    import shutil
    import tempfile

    from gartok import map_lib
    old, map_lib.MAP_DIR = map_lib.MAP_DIR, tempfile.mkdtemp()
    try:
        m = map_lib.new_map("Marsh", cols=24, rows=18)
        m["elevation"] = [[10, 9, -3]]
        m["water"] = [[10, 9], [11, 9], [12, 9]]     # one flooded pit cell + two puddles
        slug = map_lib.save_map(m)
        back = map_lib.load_map(slug)
        assert back["cols"] == 24 and back["rows"] == 18
        assert back["water"] == [[10, 9], [11, 9], [12, 9]]

        random.seed(0)
        batt = Battle([Unit("player")], [Unit("enemy")],
                      scenario=CustomScenario(back))
        assert batt.board.cols == 24 and batt.board.rows == 18
        assert batt.board.is_deep_water((10, 9))          # over the pit
        assert (11, 9) in batt.board.difficult            # ground-level puddle
        assert (11, 9) not in batt.board.deep_water
    finally:
        shutil.rmtree(map_lib.MAP_DIR, ignore_errors=True)
        map_lib.MAP_DIR = old


def test_sandbox_attribute_edits_clamp_to_a_3d6_score():
    u = _unit(seed=3)
    u.set_base_attribute("strength", 25)
    assert u.base_attributes["strength"] == 18
    u.set_base_attribute("strength", 1)
    assert u.base_attributes["strength"] == 3
    u.set_gold(-5)
    assert u.gold == 0
    u.set_language("Elvish", True)
    assert "Elvish" in u.languages
    while len(u.languages) > 1:
        u.set_language(u.languages[-1], False)
    assert len(u.languages) == 1                 # never drops the last tongue


def test_set_track_level_grants_picks_and_resyncs_on_the_way_down():
    u = _unit(seed=1)
    u.set_track_level("combat", 3)
    assert u.combat_level == 3 and u.picks_available("combat") == 3
    assert u.choose_talent("combat", "strong")
    assert u.choose_talent("combat", "sure_strike")
    u.set_track_level("combat", 1)
    assert u.combat_level == 1
    assert u.talents["combat"] == ["strong"]      # the valid prefix survives
    assert len(u._level_hp_rolls) <= u.mean_level


def test_drop_talent_cascades_to_its_dependents():
    u = _unit(seed=1)
    u.set_track_level("combat", 3)
    u.choose_talent("combat", "strong")
    u.choose_talent("combat", "sure_strike")
    u.drop_talent("combat", "strong")
    assert u.talents["combat"] == []


def test_npc_library_round_trips_a_hand_built_character():
    import shutil
    import tempfile

    from gartok import npc_lib
    old, npc_lib.NPC_DIR = npc_lib.NPC_DIR, tempfile.mkdtemp()
    try:
        u = _unit(seed=2)
        u.set_name("Old Grix")
        u.set_alignment("Lawful and Evil")
        u.set_age(300)
        u.set_track_level("combat", 2)
        slug = npc_lib.save_npc(u)
        assert slug == "old-grix"
        assert [r["slug"] for r in npc_lib.list_npcs()] == ["old-grix"]
        back = npc_lib.load_npc(slug)
        assert back.name == "Old Grix"
        assert back.alignment == "Lawful and Evil"
        assert back.age == 300                        # creator-set age, not age_base x mult
        assert back.combat_level == 2
        assert back.uid == u.uid
        npc_lib.delete_npc(slug)
        assert npc_lib.list_npcs() == []
    finally:
        shutil.rmtree(npc_lib.NPC_DIR, ignore_errors=True)
        npc_lib.NPC_DIR = old


def test_map_library_round_trips_traps_and_custom_scenario_spawns_them():
    import shutil
    import tempfile

    from gartok import map_lib
    old, map_lib.MAP_DIR = map_lib.MAP_DIR, tempfile.mkdtemp()
    try:
        m = map_lib.new_map("Trap Gauntlet")
        m["traps"] = [[5, 4, "bear trap"], [6, 4, "alarm trap"]]
        slug = map_lib.save_map(m)
        back = map_lib.load_map(slug)
        assert back["traps"] == [[5, 4, "bear trap"], [6, 4, "alarm trap"]]

        batt = Battle([Unit("player")], [Unit("enemy")],
                      scenario=CustomScenario(back))
        traps = [o for o in batt.ground if o.is_trap]
        assert len(traps) == 2
        assert any(o.trap_type == "bear trap" and o.pos == (5, 4) for o in traps)
        assert any(o.trap_type == "alarm trap" and o.pos == (6, 4) for o in traps)
    finally:
        shutil.rmtree(map_lib.MAP_DIR, ignore_errors=True)
        map_lib.MAP_DIR = old


def test_map_editor_trap_tool():
    import pygame
    from gartok.map_editor_screen import MapEditorScreen
    from gartok.ui.tokens import fonts as ui_fonts

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


def test_ancient_ruins_map_and_npcs_in_library():
    from gartok import map_lib, npc_lib
    from gartok.scenario import AncientRuinsScenario

    npc_slugs = [r["slug"] for r in npc_lib.list_npcs()]
    assert "ruin-sentry" in npc_slugs
    assert "the-ancient-archivist" in npc_slugs

    map_slugs = [r["slug"] for r in map_lib.list_maps()]
    assert "ancient-ruins" in map_slugs

    sc = AncientRuinsScenario()
    assert sc._cols == 30 and sc._rows == 18
    assert len(sc.enemies) == 5
    boss = next(e for e in sc.enemies if "Archivist" in e.name)
    assert boss.dormant
    assert boss.awareness_radius == 8


def test_map_editor_secret_wall_and_escape_tools():
    import pygame
    from gartok.map_editor_screen import MapEditorScreen
    from gartok.ui.tokens import fonts as ui_fonts

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
    from gartok.map_editor_screen import MapEditorScreen
    from gartok.ui.tokens import fonts as ui_fonts

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
    ed.picker_hits = [(pygame.Rect(10, 10, 50, 50), ("chest_add_item", "Amethyst"))]
    ed._picker_click((20, 20))
    assert ed.chests[(7, 3)] == ["Scroll of Sleep", "Amethyst"]

    # Remove the first item
    ed.picker_hits = [(pygame.Rect(10, 10, 50, 50), ("chest_remove_item", 0))]
    ed._picker_click((20, 20))
    assert ed.chests[(7, 3)] == ["Amethyst"]

    # Close modal
    ed.picker_hits = [(pygame.Rect(10, 10, 50, 50), ("close", None))]
    ed._picker_click((20, 20))
    assert ed.picking is None

    # Serialization contains chest
    d = ed._to_dict()
    assert d["chests"] == [[7, 3, ["Amethyst"]]]

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


def test_custom_scenario_spawns_chests_and_relics_and_pickup():
    from gartok import data, map_lib
    from gartok.actions.support import PickUp

    m = map_lib.new_map("Treasure Room")
    m["deploy_player"] = [[2, 2]]
    m["deploy_enemy"] = [[10, 10]]
    m["chests"] = [[2, 3, ["50 Copper", "Scroll of Sleep"]]]
    m["relics"] = [[3, 2, data.CODEX_ITEM]]
    m["secret_walls"] = [[5, 5]]
    m["escape_cells"] = [[1, 1]]

    batt = Battle([Unit("player")], [Unit("enemy")], scenario=CustomScenario(m))
    assert (5, 5) in batt.secret_walls
    assert (1, 1) in batt.escape_cells

    chests = [o for o in batt.ground if o.is_chest]
    assert len(chests) == 1
    assert chests[0].pos == (2, 3)
    assert chests[0].contents == ["50 Copper", "Scroll of Sleep"]

    relics = [o for o in batt.ground if o.is_relic]
    assert len(relics) == 1
    assert relics[0].pos == (3, 2)
    assert relics[0].item_name == data.CODEX_ITEM

    # Test pickup of relic
    p = batt.player_units[0]
    p.pos = (3, 3)
    p.ap = 2
    act = PickUp()
    assert act.available(batt, p)
    act.execute(batt, p)
    assert data.CODEX_ITEM in p.inventory
    assert data.CODEX_ITEM in getattr(p, "picked_up_items", [])
    assert not any(o.is_relic for o in batt.ground)


def test_sandbox_magic_source_and_spells():
    u = Unit("player")
    u.set_spell_known("sleep", True)
    assert u.spells_known == []                 # no affinity, nothing to teach
    u.set_magic_source("faith")
    u.set_spell_known("sleep", True)
    u.set_spell_known("magic_missile", True)
    assert u.spells_known == ["sleep", "magic_missile"]
    u.set_spell_known("sleep", False)
    assert u.spells_known == ["magic_missile"]
    u.set_magic_source(None)
    assert u.magic_source is None and u.spells_known == []
    u.set_magic_source("faith")
    u.set_spell_known("sleep", True)
    assert Unit.from_save(persist.unit_to_dict(u)).spells_known == ["sleep"]
    u.study_target = "light_globe"
    u.set_magic_source("faith")
    assert u.study_target == "light_globe"      # same source: a study in flight stays


def test_a_skeleton_speaks_no_language_and_no_blank_dictionary_recipe():
    from gartok import data
    u = Unit("enemy", race=data.race_by_name("Skeleton"))
    assert "" not in u.languages
    assert "Dictionary of " not in u.recipes
    back = Unit.from_save({**persist.unit_to_dict(u), "languages": ["", "Draconic"]})
    assert back.languages == ["Draconic"]


def test_sheet_hides_the_magic_block_until_initiated():
    from gartok.combatant import Combatant
    from gartok.ui.sheet_card import sheet_height, unit_to_ch
    u = Unit("player")
    plain = sheet_height("normal", ch=unit_to_ch(Combatant(u)))
    u.set_magic_source("faith")
    assert sheet_height("normal", ch=unit_to_ch(Combatant(u))) > plain
    assert sheet_height("normal") == sheet_height("normal", ch=unit_to_ch(Combatant(u)))
