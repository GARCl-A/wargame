"""Each place's floor on the battle board (`ui/floors.py`): what paints it and who picks it."""

import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

from gartok import map_lib, world
from gartok.battlefield import BattlefieldScenario
from gartok.lair import LairScenario
from gartok.scenario import (
    WALL_KIND,
    ArenaScenario,
    CustomScenario,
    Scenario,
    StreetScenario,
    WildsScenario,
    scenario_for,
    wall_kind,
)
from gartok.serpent_nest import NestScenario
from gartok.ui import board_render, floors
from gartok.ui.board_style import BoardView
from gartok.ui.tokens import fonts
from gartok.unit import Unit

WALLS = {(3, 3), (4, 3), (8, 6)}


def _mean(surf):
    return tuple(round(c) for c in pygame.transform.average_color(surf)[:3])


def test_every_floor_paints_the_whole_board_the_same_way_twice_without_touching_the_dice():
    pygame.init()
    random.seed(1)
    before = random.random()
    random.seed(1)
    for floor in floors.FLOORS:
        tex = floors.texture(floor, 12, 8, WALLS)
        assert tex.get_size() == (12 * floors.TEX, 8 * floors.TEX)
        floors._textures.clear()
        again = floors.texture(floor, 12, 8, WALLS)
        assert pygame.image.tobytes(tex, "RGB") == pygame.image.tobytes(again, "RGB")
    assert random.random() == before


def test_opening_a_wall_repaints_only_around_that_cell():
    pygame.init()
    before = floors.texture("stone", 12, 8, WALLS)
    after = floors.texture("stone", 12, 8, WALLS - {(8, 6)})
    t = floors.TEX
    far = pygame.Rect(10 * t, 0, 2 * t, 3 * t)               # painted after (8, 6), away from its shadow
    assert pygame.image.tobytes(before.subsurface(far), "RGB") == pygame.image.tobytes(after.subsurface(far), "RGB")
    near = pygame.Rect(8 * t, 6 * t, t, t)
    assert pygame.image.tobytes(before.subsurface(near), "RGB") != pygame.image.tobytes(after.subsurface(near), "RGB")


def test_the_floors_look_apart():
    pygame.init()
    looks = {_mean(floors.texture(floor, 12, 8, set())) for floor in floors.FLOORS}
    assert len(looks) == len(floors.FLOORS)
    sand, grass = _mean(floors.texture("arena", 12, 8, set())), _mean(floors.texture("grass", 12, 8, set()))
    assert sand[0] > sand[2] and grass[1] > grass[0]


def test_an_unknown_floor_falls_back_to_the_flagstones():
    pygame.init()
    assert floors.style("marble") is floors.style(floors.DEFAULT)
    floors.texture("marble", 4, 4, set())


def test_every_floor_has_its_wall_and_an_unknown_one_has_the_flagstones():
    assert set(WALL_KIND) == set(floors.FLOORS)
    assert wall_kind("grass") == "tree" and wall_kind("marble") == wall_kind(floors.DEFAULT) == "block"


def test_the_board_draws_the_scenarios_floor_at_the_views_zoom():
    pygame.init()
    view = BoardView(12, 8)
    view.fit(pygame.Rect(0, 0, 12 * 30, 8 * 30))
    terrain = {"cols": 12, "rows": 8, "walls": set(), "elevation": {}, "water": set(), "ropes": set()}
    looks = {}
    for floor in ("grass", "cobble"):
        surf = pygame.Surface((12 * 30, 8 * 30))
        board_render.draw_terrain(surf, fonts(), view, {**terrain, "floor": floor})
        looks[floor] = _mean(surf)
        tex = pygame.transform.smoothscale(floors.texture(floor, 12, 8, set()), (12 * 30, 8 * 30))
        assert max(abs(a - b) for a, b in zip(looks[floor], _mean(tex))) <= 3
    assert looks["grass"] != looks["cobble"]


def test_each_place_brings_its_own_floor():
    assert Scenario.floor == floors.DEFAULT
    assert ArenaScenario.floor == "arena"
    assert WildsScenario.floor == "grass"
    assert StreetScenario.floor == "cobble"
    assert LairScenario.floor == NestScenario.floor == "cave"
    assert BattlefieldScenario.floor == "earth"
    for scen in (ArenaScenario, WildsScenario, StreetScenario, LairScenario, BattlefieldScenario):
        assert scen.floor in floors.FLOORS


def test_a_road_fights_on_packed_earth_and_the_city_on_cobbles():
    assert scenario_for(world.node("road")).floor == "earth"
    assert scenario_for(world.node("country_roads")).floor == "earth"
    assert scenario_for(world.node("prison")).floor == "cobble"
    assert scenario_for(world.node("wilds")).floor == "grass"
    assert WildsScenario().floor == "grass"                  # the road's floor rides on its own copy


def test_a_hand_laid_map_keeps_the_floor_its_author_picked():
    assert CustomScenario(map_lib.load_map("the-pit")).floor == "arena"
    assert CustomScenario(map_lib.load_map("capture-the-flag-the-gamers")).floor == "arena"
    blank = map_lib.new_map()
    assert CustomScenario({**blank, "floor": "cave"}).floor == "cave"
    assert CustomScenario({k: v for k, v in blank.items() if k != "floor"}).floor == floors.DEFAULT
    assert CustomScenario({k: v for k, v in blank.items() if k != "floor"} | {"outdoor": True}).floor == "grass"


def test_the_map_editor_cycles_the_floor_and_saves_it(tmp_path, monkeypatch):
    pygame.init()
    from gartok.map_editor_screen import MapEditorScreen
    monkeypatch.setattr(map_lib, "MAP_DIR", str(tmp_path))
    ed = MapEditorScreen(fonts(), lambda: None)
    assert ed.floor == floors.DEFAULT
    ed._do(("floor", 1))
    assert ed.floor == floors.FLOORS[1]
    ed._do(("floor", -1))
    ed._do(("floor", -1))
    assert ed.floor == floors.FLOORS[-1]
    ed.name = "Somewhere"
    ed._save()
    assert map_lib.load_map(ed.slug)["floor"] == floors.FLOORS[-1]
    ed.draw(pygame.Surface((1600, 900)))
    assert any(action == ("floor", 1) for _r, action in ed.hits)


def test_a_battle_screen_draws_its_floor():
    pygame.init()
    from gartok.battle import Battle
    from gartok.battle_screen import BattleScreen
    random.seed(4)
    b = Battle([Unit("player")], [Unit("enemy")], scenario=WildsScenario(), daylight=True)
    b.trap_setup_queue = []
    BattleScreen(fonts(), b, on_battle_end=lambda *a: None).draw(pygame.Surface((1600, 900)))
    assert any(key[0] == "grass" for key in floors._textures)
