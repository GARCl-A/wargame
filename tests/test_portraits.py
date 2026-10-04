import os
import pygame
from gartok import artwork, data, persist, unit

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_hobgoblin_portraits():
    # 9 curated Hobgoblin portraits
    for idx in range(9):
        p = artwork.portrait("Hobgoblin", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    hob = unit.Unit("player", race=data.race_by_name("Hobgoblin"))
    assert hasattr(hob, "portrait_id")
    p_hob = artwork.portrait(hob.race["name"], hob.portrait_id, 24)
    assert p_hob is not None
    assert p_hob.get_size() == (24, 24)


def test_orc_portraits():
    # 12 complete Orc portraits
    for idx in range(12):
        p = artwork.portrait("Orc", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    orc = unit.Unit("player", race=data.race_by_name("Orc"))
    assert hasattr(orc, "portrait_id")
    p_orc = artwork.portrait(orc.race["name"], orc.portrait_id, 24)
    assert p_orc is not None
    assert p_orc.get_size() == (24, 24)
