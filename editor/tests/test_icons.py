"""Every node on the map and every occupation has a glyph of its own that exists on disk."""

import os
from gartok import data, world
from editor import artwork
from gartok.map_view import NODE_ICON

def _exists(slug):
    return os.path.isfile(os.path.join(artwork._ICONS, slug[0], slug[1] + ".svg"))


def test_every_node_has_its_own_map_icon():
    ids = {n.id for n in world.NODES}
    assert set(NODE_ICON) == ids
    assert all(_exists(s) for s in NODE_ICON.values())
    assert len(set(NODE_ICON.values())) == len(ids), "two nodes share a glyph"


def test_every_occupation_has_an_icon():
    names = {o[1] for o in data.OCCUPATIONS} | {data.BEAST_OCCUPATION["name"]}
    assert set(artwork.OCCUPATION_ICON) == names
    assert all(_exists(s) for s in artwork.OCCUPATION_ICON.values())


def test_every_weapon_action_has_a_glyph():
    import pygame
    from gartok import actions
    from editor import icons
    surf = pygame.Surface((32, 32))
    rect = pygame.Rect(0, 0, 32, 32)
    color = (255, 255, 255)
    for act in actions.WEAPON_ACTIONS:
        assert act.id in icons.NAMES
        assert act.id in icons._GLYPHS
        icons.icon(surf, act.id, rect, color)
