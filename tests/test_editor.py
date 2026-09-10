"""The sandbox character/map creators and their git-tracked libraries."""

import random

from tests.helpers import Battle, COLS, CustomScenario, Unit, _unit


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
