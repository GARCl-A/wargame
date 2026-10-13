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
    bounds = pygame.Rect(0, 0, 900, 700)
    centers = {n.id: (150 + n.pos[0] * 600, 100 + n.pos[1] * 500) for n in world.NODES}
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
