"""The wiki's RACES tab (wiki_races.py): every playable race, off the live tables, and no beast."""

import pygame

from gartok import abilities, data, talents, wiki_races
from gartok.ui.tokens import fonts as ui_fonts
from gartok.wiki_screen import WikiScreen


def test_every_playable_race_and_no_beast_is_listed():
    names = [e["name"] for e in wiki_races.entries()]
    assert sorted(names) == sorted(data.RACE_NAMES) and names == sorted(names)
    assert not set(names) & set(data.BEAST_NAMES)


def test_a_race_reads_its_mods_ability_language_and_racial_track():
    dwarf = next(e for e in wiki_races.entries() if e["name"] == "Dwarf")
    assert dwarf["mods"].startswith("STR +1  DEX +0  CON +2")
    assert dwarf["abilities"] == [f"Darkvision: {abilities.get('darkvision').effect}"]
    assert "Dwarvish" in dwarf["meta"] and "d10" in dwarf["meta"]
    assert dwarf["talents"] == [t.name for t in talents.racial_tree("Dwarf")]


def test_the_filter_finds_a_race_by_its_ability():
    assert [e["name"] for e in wiki_races.matching("darkvision")] == ["Dwarf"]
    assert len(wiki_races.matching("")) == len(data.RACE_NAMES)


def test_the_races_tab_draws_and_scrolls():
    pygame.init()
    scr = WikiScreen(ui_fonts(), lambda: None)
    scr.mouse = (0, 0)
    scr.draw(pygame.Surface((1280, 720)))
    rect = next(r for key, r in scr.tab_buttons if key == "races")
    scr._click(rect.center)
    assert scr.tab == "races"
    scr.draw(pygame.Surface((1280, 720)))
    assert scr._max_scroll > 0
