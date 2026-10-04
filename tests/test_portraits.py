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


def test_automaton_portraits():
    # 10 curated Automaton portraits
    for idx in range(10):
        p = artwork.portrait("Automaton", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    auto = unit.Unit("player", race=data.race_by_name("Automaton"))
    assert hasattr(auto, "portrait_id")
    p_auto = artwork.portrait(auto.race["name"], auto.portrait_id, 24)
    assert p_auto is not None
    assert p_auto.get_size() == (24, 24)


def test_human_portraits():
    # 12 complete Human portraits
    for idx in range(12):
        p = artwork.portrait("Human", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    hum = unit.Unit("player", race=data.race_by_name("Human"))
    assert hasattr(hum, "portrait_id")
    p_hum = artwork.portrait(hum.race["name"], hum.portrait_id, 24)
    assert p_hum is not None
    assert p_hum.get_size() == (24, 24)


def test_elf_portraits():
    # 12 complete Elf portraits
    for idx in range(12):
        p = artwork.portrait("Elf", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    elf = unit.Unit("player", race=data.race_by_name("Elf"))
    assert hasattr(elf, "portrait_id")
    p_elf = artwork.portrait(elf.race["name"], elf.portrait_id, 24)
    assert p_elf is not None
    assert p_elf.get_size() == (24, 24)


def test_kobold_portraits():
    # 11 curated Kobold portraits
    for idx in range(11):
        p = artwork.portrait("Kobold", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    kb = unit.Unit("player", race=data.race_by_name("Kobold"))
    assert hasattr(kb, "portrait_id")
    p_kb = artwork.portrait(kb.race["name"], kb.portrait_id, 24)
    assert p_kb is not None
    assert p_kb.get_size() == (24, 24)


def test_lizardfolk_portraits():
    # 9 curated Lizardfolk portraits
    for idx in range(9):
        p = artwork.portrait("Lizardfolk", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    lz = unit.Unit("player", race=data.race_by_name("Lizardfolk"))
    assert hasattr(lz, "portrait_id")
    p_lz = artwork.portrait(lz.race["name"], lz.portrait_id, 24)
    assert p_lz is not None
    assert p_lz.get_size() == (24, 24)


def test_halfling_portraits():
    # 12 complete Halfling portraits
    for idx in range(12):
        p = artwork.portrait("Halfling", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    hf = unit.Unit("player", race=data.race_by_name("Halfling"))
    assert hasattr(hf, "portrait_id")
    p_hf = artwork.portrait(hf.race["name"], hf.portrait_id, 24)
    assert p_hf is not None
    assert p_hf.get_size() == (24, 24)


def test_gnome_portraits():
    # 12 complete Gnome portraits
    for idx in range(12):
        p = artwork.portrait("Gnome", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    gn = unit.Unit("player", race=data.race_by_name("Gnome"))
    assert hasattr(gn, "portrait_id")
    p_gn = artwork.portrait(gn.race["name"], gn.portrait_id, 24)
    assert p_gn is not None
    assert p_gn.get_size() == (24, 24)


def test_dwarf_portraits():
    # 9 curated Dwarf portraits
    for idx in range(9):
        p = artwork.portrait("Dwarf", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    dw = unit.Unit("player", race=data.race_by_name("Dwarf"))
    assert hasattr(dw, "portrait_id")
    p_dw = artwork.portrait(dw.race["name"], dw.portrait_id, 24)
    assert p_dw is not None
    assert p_dw.get_size() == (24, 24)


def test_centaur_portraits():
    # 12 complete Centaur portraits
    for idx in range(12):
        p = artwork.portrait("Centaur", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    cn = unit.Unit("player", race=data.race_by_name("Centaur"))
    assert hasattr(cn, "portrait_id")
    p_cn = artwork.portrait(cn.race["name"], cn.portrait_id, 24)
    assert p_cn is not None
    assert p_cn.get_size() == (24, 24)





