"""Tests for the Floating Disk spell and 3D elevation traversal."""

from gartok import ai
from gartok.ground import GroundObject
from tests.helpers import Battle, Unit, actions, data


def _caster():
    u = Unit("player", race=data.race_by_name("Human"))
    u.magic_source = "nature"
    u.spells_known = ["floating_disk"]
    return u


def _setup_battle():
    u1 = _caster()
    u2 = Unit("enemy", race=data.race_by_name("Human"))
    batt = Battle([u1], [u2])
    batt.board.walls.clear()
    c1, c2 = batt.player_units[0], batt.enemy_units[0]
    c1.pos, c2.pos = (0, 0), (2, 0)
    c1.z, c2.z = 0, 0
    c1.ap, c2.ap = 2, 2
    c1.speed = 4
    return batt, c1, c2


def test_floating_disk_creation_with_elevation():
    batt, c1, _ = _setup_battle()
    fd = actions.CastSpellAction("floating_disk")
    assert fd.can(batt, c1, (1, 0))

    fd.execute(batt, c1, (1, 0), elevation=0)

    disks = [o for o in batt.ground if o.is_disk]
    assert len(disks) == 1
    disk = disks[0]
    assert disk.pos == (1, 0)
    assert disk.elevation == 0


def test_floating_disk_bridges_pit_for_walking():
    batt, c1, c2 = _setup_battle()
    # (1, 0) and (1, 1) are pits at elevation -2
    batt.board.elevation = {(1, 0): -2, (1, 1): -2}
    batt.board.refresh_terrain()

    # Move target away so (2, 0) is an empty cell to walk onto
    c2.pos = (4, 0)

    # Without disk, (2, 0) is unreachable straight across because (1, 0) and (1, 1) are pits.
    # Place Floating Disk at (1, 0) at elevation 0
    batt.ground.append(GroundObject.disk((1, 0), elevation=0))
    batt.clear_pf_cache()

    reachable = batt.reachable(c1)
    assert (1, 0) in reachable
    assert (2, 0) in reachable

    path = batt.path_to(c1, (2, 0))
    assert path == [(0, 0), (1, 0), (2, 0)]

    # Move unit across the disk
    moved = batt.move_unit(c1, (2, 0))
    assert moved is True
    assert c1.pos == (2, 0)
    assert c1.z == 0
    assert batt.elevation(c1) == 0


def test_unit_can_walk_underneath_floating_disk_in_pit():
    batt, c1, c2 = _setup_battle()
    batt.board.elevation = {(1, 0): -2, (1, 1): -2}
    batt.board.refresh_terrain()

    # Place disk at (1, 0) at elevation 0
    batt.ground.append(GroundObject.disk((1, 0), elevation=0))
    batt.clear_pf_cache()

    # Pit creature starts at (1, 1) at floor height -2
    c2.pos = (1, 1)
    c2.z = -2
    c2.speed = 3

    # (1, 0) is also at pit floor -2 underneath the disk.
    # c2 should be able to step to (1, 0) at floor level -2.
    reachable = batt.reachable(c2)
    assert (1, 0) in reachable

    batt.move_unit(c2, (1, 0))
    assert c2.pos == (1, 0)
    assert c2.z == -2
    assert batt.elevation(c2) == -2


def test_floating_disk_bridges_deep_water_dry():
    batt, c1, c2 = _setup_battle()
    c2.pos = (4, 0)
    # (1, 0) is a pit at -2 flooded with water (deep water)
    batt.board.elevation = {(1, 0): -2}
    batt.board.water = {(1, 0)}
    batt.board.refresh_terrain()

    # Deep water at (1, 0) blocks walking without disk
    assert (1, 0) in batt.board.deep_water
    assert (1, 0) in batt._impassable_water(c1)

    # Place disk at (1, 0) at elevation 0
    batt.ground.append(GroundObject.disk((1, 0), elevation=0))
    batt.clear_pf_cache()

    # Now (1, 0) is bridged and NOT in impassable water
    assert (1, 0) not in batt._impassable_water(c1)
    reachable = batt.reachable(c1)
    assert (1, 0) in reachable
    assert (2, 0) in reachable

    # Cost of stepping on the disk over water is 1 (normal dry ground, not difficult)
    cost, _ = batt.board.path_cost([(0, 0), (1, 0)], platforms=batt._platforms(), z_start=0)
    assert cost == 1


def test_ai_casts_floating_disk_at_own_elevation_to_bridge_path():
    batt, c1, c2 = _setup_battle()
    batt.ambient_light = True
    batt.ground.clear()
    # Give caster spell to AI unit c2
    c2.spells_known = ["floating_disk"]
    c2.char.spells_known = ["floating_disk"]
    c2.pos = (0, 0)
    c2.z = 0
    c2.ap = 2
    c2.speed = 3

    # Player target is at (2, 0). Different languages so demoralize is inapplicable
    c1.pos = (2, 0)
    c1.z = 0
    c1.languages = ["Elvish"]
    c2.languages = ["Goblin"]

    # Trench across the entire board at x=1
    batt.board.elevation = {(1, y): -2 for y in range(batt.board.rows)}
    batt.board.refresh_terrain()

    # AI is at (0, 0), column x=1 is a pit. AI path is blocked.
    # Run AI turn: AI should cast floating_disk at (1, 0) with elevation 0.
    ai.take_turn(batt, c2)

    disks = [o for o in batt.ground if o.is_disk and o.pos == (1, 0)]
    assert len(disks) == 1
    assert disks[0].elevation == 0


def test_disk_height_options_computation():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    from gartok.battle_screen import BattleScreen
    batt, c1, _ = _setup_battle()
    batt.board.elevation = {(1, 0): -2}
    batt.board.refresh_terrain()

    screen = BattleScreen(None, batt, on_battle_end=lambda b: None)
    # For pit cell at (1, 0) with elevation -2
    opts = screen._disk_height_options(c1, (1, 0))
    # Should contain 0 and -2
    elevations = [z for z, _ in opts]
    assert elevations == [0, -2]
    # First option is Ground/Caster z=0, second is Pit floor z=-2
    assert "Ground" in opts[0][1] or "Caster" in opts[0][1]
    assert "Pit floor" in opts[1][1]
