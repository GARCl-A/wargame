"""The wiki's RULES tab (wiki_rules.py): the numbers are the live ones and the filter finds a rule."""

import pygame

from gartok import dialogue, recruit, wiki_rules
from gartok.ui.tokens import fonts as ui_fonts
from gartok.wiki_screen import WikiScreen


def test_the_rules_quote_the_live_constants():
    body = " ".join(" ".join(lines) for _, lines in wiki_rules.sections())
    assert f"against {dialogue.BASE_DC} +" in body
    assert f"-{recruit.SIZE_PENALTY} for every member of the whole guild past {recruit.FREE_SLOTS}" in body


def test_the_filter_finds_the_crowd_penalty():
    titles = [t for t, _ in wiki_rules.matching("crowd")]
    assert titles == ["RECRUITING"]
    assert len(wiki_rules.matching("")) == len(wiki_rules.sections())


def test_the_rules_tab_draws_and_wraps_in_a_narrow_window():
    pygame.init()
    scr = WikiScreen(ui_fonts(), lambda: None)
    scr.mouse, scr.tab = (0, 0), "rules"
    scr.draw(pygame.Surface((800, 600)))
    assert scr._max_scroll > 0
