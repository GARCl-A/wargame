"""Map labels: every node's name is placed clear of the other names and marks, and the camera
frames a big region whole."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from gartok import world
from gartok.ui import map_panel
from gartok.ui.camera import MapCamera
from gartok.ui.tokens import fonts


def _setup():
    pygame.init()
    pygame.display.set_mode((1, 1))
    return fonts()


def test_labels_of_a_crowded_map_do_not_overlap_each_other_or_other_marks():
    F = _setup()
    bounds = pygame.Rect(0, 0, 1200, 800)
    centers = {n.id: (150 + n.pos[0] * 900, 100 + n.pos[1] * 600) for n in world.NODES}
    names = {n.id: n.name for n in world.NODES}
    spots = map_panel.place_labels(F, centers, names, bounds)
    assert set(spots) == set(centers)
    ids = list(spots)
    for i, a in enumerate(ids):
        assert bounds.contains(spots[a]), a
        for b in ids[i + 1:]:
            assert not spots[a].colliderect(spots[b]), (a, b)


def test_a_label_sits_below_its_mark_when_nothing_is_near():
    F = _setup()
    spots = map_panel.place_labels(F, {"a": (300, 200)}, {"a": "Alone"}, pygame.Rect(0, 0, 600, 400))
    assert spots["a"].top > 200 and spots["a"].centerx == 300


def test_autofit_keeps_a_regions_terrain_inside_the_frame():
    nodes = {"a": {"pos": (0.2, 0.1)}, "b": {"pos": (0.8, 0.9)}}
    cam = MapCamera(nodes, min_zoom=1, max_zoom=5000)
    cam.set_rect(pygame.Rect(0, 0, 800, 600))
    cam.autofit(nodes, pad=(0, 0), radii={"a": 0.1, "b": 0.0})
    assert cam.world_to_screen((0.2, 0.0))[1] >= 0


def test_a_name_with_no_room_is_left_for_the_hover_but_a_kept_node_always_shows():
    F = _setup()
    bounds = pygame.Rect(0, 0, 400, 400)
    centers = {n.id: (60 + n.pos[0] * 280, 60 + n.pos[1] * 280) for n in world.NODES}
    names = {n.id: n.name for n in world.NODES}
    spots = map_panel.place_labels(F, centers, names, bounds, keep={"city", "smith"})
    assert {"city", "smith"} <= set(spots) and len(spots) < len(centers)
    shown = [k for k in spots if k not in ("city", "smith")]
    for i, a in enumerate(shown):
        for b in shown[i + 1:]:
            assert not spots[a].colliderect(spots[b]), (a, b)


def test_map_node_alert_indicator_for_unaccepted_faction_jobs():
    from gartok import missions
    from gartok.guild import Guild
    from gartok.group import Group
    from gartok.unit import Unit
    from gartok.map_screen import MapScreen
    F = _setup()
    u = Unit("player")
    g = Group([u], node="tanner")
    guild = Guild([u], groups=[g])
    offers = missions.offers_at(guild, "tanner")
    assert any(t.id == "tanner_hides" for t in offers)
    m = MapScreen(F, guild, lambda: None, lambda: None, lambda **k: None, lambda g: None)
    assert m._nodes["tanner"]["alert"] is True
    blocks = m._inspector_content(g, world.node("tanner"))
    assert any("mission" in b.get("text", "").lower() for b in blocks)
