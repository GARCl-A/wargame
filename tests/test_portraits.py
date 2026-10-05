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


def test_gnoll_portraits():
    # 11 curated Gnoll portraits
    for idx in range(11):
        p = artwork.portrait("Gnoll", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    gn = unit.Unit("player", race=data.race_by_name("Gnoll"))
    assert hasattr(gn, "portrait_id")
    p_gn = artwork.portrait(gn.race["name"], gn.portrait_id, 24)
    assert p_gn is not None
    assert p_gn.get_size() == (24, 24)


def test_grippli_portraits():
    # 11 curated Grippli portraits
    for idx in range(11):
        p = artwork.portrait("Grippli", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    gr = unit.Unit("player", race=data.race_by_name("Grippli"))
    assert hasattr(gr, "portrait_id")
    p_gr = artwork.portrait(gr.race["name"], gr.portrait_id, 24)
    assert p_gr is not None
    assert p_gr.get_size() == (24, 24)


def test_sprite_portraits():
    # 11 curated Sprite portraits
    for idx in range(11):
        p = artwork.portrait("Sprite", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    sp = unit.Unit("player", race=data.race_by_name("Sprite"))
    assert hasattr(sp, "portrait_id")
    p_sp = artwork.portrait(sp.race["name"], sp.portrait_id, 24)
    assert p_sp is not None
    assert p_sp.get_size() == (24, 24)


def test_kenku_portraits():
    # 8 curated Kenku portraits
    for idx in range(8):
        p = artwork.portrait("Kenku", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    kk = unit.Unit("player", race=data.race_by_name("Kenku"))
    assert hasattr(kk, "portrait_id")
    p_kk = artwork.portrait(kk.race["name"], kk.portrait_id, 24)
    assert p_kk is not None
    assert p_kk.get_size() == (24, 24)


def test_goliath_portraits():
    # 8 curated Goliath portraits
    for idx in range(8):
        p = artwork.portrait("Goliath", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    gl = unit.Unit("player", race=data.race_by_name("Goliath"))
    assert hasattr(gl, "portrait_id")
    p_gl = artwork.portrait(gl.race["name"], gl.portrait_id, 24)
    assert p_gl is not None
    assert p_gl.get_size() == (24, 24)


def test_creature_portraits():
    # 4 Wolf portraits
    for idx in range(4):
        p = artwork.portrait("Wolf", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    # 4 Skeleton portraits
    for idx in range(4):
        p = artwork.portrait("Skeleton", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    # 4 Giant Spider portraits
    for idx in range(4):
        p = artwork.portrait("Giant Spider", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)
        p_under = artwork.portrait("giant_spider", idx, 32)
        assert p_under is not None










def test_portrait_id_survives_a_save_round_trip():
    u = unit.Unit("player")
    v = unit.Unit.from_save(persist.unit_to_dict(u))
    assert v.portrait_id == u.portrait_id


def test_a_save_without_portrait_id_derives_it_from_the_uid_not_hash():
    u = unit.Unit("player")
    d = persist.unit_to_dict(u)
    del d["portrait_id"]
    v = unit.Unit.from_save(d)
    assert v.portrait_id == u.portrait_id == int(u.uid[:8], 16)


def test_squad_and_prison_cards_carry_the_units_portrait():
    from unittest.mock import patch

    from gartok import world
    from gartok.guild import Guild
    from gartok.prison_screen import PrisonScreen
    from gartok.ui.tokens import fonts as ui_fonts

    pygame.init()
    u = unit.Unit("player")
    guild = Guild([u], node="prison")
    screen = PrisonScreen(ui_fonts(), guild, [u], world.node("prison"), on_done=lambda: None)
    seen = []
    real = artwork.portrait

    def spy(race, pid, px):
        seen.append(pid)
        return real(race, pid, px)

    with patch.object(artwork, "portrait", spy):
        screen.draw(pygame.Surface((1280, 800)))
    assert u.portrait_id in seen
