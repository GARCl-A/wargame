"""What a side knows of a foe: the opening read, the bands it opens, Assess, the bestiary."""

import pygame
from gartok import foe_card, intel
from gartok.battle import Battle
from editor.ui import foe_panel
from editor.ui.board_render import hp_bar
from editor.ui.tokens import fonts as ui_fonts
from tests.helpers import Unit

def _fight(foes=1, hidden=False):
    """A hero and `foes` enemies in daylight; `hidden` puts a wall between them."""
    batt = Battle([Unit("player")], [Unit("enemy") for _ in range(foes)])
    batt.ambient_light = True
    batt.board.walls = {(5, y) for y in range(batt.board.rows)} if hidden else set()
    hero = batt.player_units[0]
    hero.pos = (2, 5)
    for i, e in enumerate(batt.enemy_units):
        e.pos = (8, 5 + i)
    return batt, hero, batt.enemy_units

def _read(batt, team, foe, margin):
    """Pin `team`'s margin on `foe`."""
    batt.intel.margin[team][foe] = margin


def test_a_stepped_bar_leaves_gaps_a_continuous_one_does_not():
    pygame.init()
    stepped, smooth = pygame.Surface((100, 6)), pygame.Surface((100, 6))
    hp_bar(stepped, pygame.Rect(0, 0, 100, 6), 0.6, 5)
    hp_bar(smooth, pygame.Rect(0, 0, 100, 6), 0.6)
    row = [stepped.get_at((x, 2))[:3] for x in range(60)]
    assert len(set(row)) == 2                  # the fill and the gap between steps
    assert len({smooth.get_at((x, 2))[:3] for x in range(60)}) == 1


def test_the_foe_card_shows_a_question_mark_for_what_it_has_not_learned():
    pygame.init()
    batt, _hero, (foe,) = _fight()
    _read(batt, "player", foe, intel.EASY)
    card = foe_card.foe_card(intel.known_fields(batt, "player", foe))
    bands = {b["label"]: b for b in card["bands"]}
    assert bands["EASY"]["open"] and not bands["MEDIUM"]["open"] and not bands["HARD"]["open"]
    assert all(r["value"] is None for r in bands["MEDIUM"]["rows"])
    surf = pygame.Surface((320, foe_panel.card_height(card)))
    foe_panel.draw_foe_card(surf, ui_fonts(), surf.get_rect(), card, (0, 0))


def test_the_foe_card_grows_as_more_of_the_foe_is_read():
    batt, _hero, (foe,) = _fight()
    heights = []
    for margin in (-1, 0, 5, 10):
        _read(batt, "player", foe, margin)
        heights.append(foe_panel.card_height(foe_card.foe_card(intel.known_fields(batt, "player", foe))))
    assert heights == sorted(heights) and heights[0] < heights[-1]


def test_the_battle_screen_inspects_a_foe_through_its_card_and_an_ally_through_the_sheet():
    from editor.battle_screen import BattleScreen
    pygame.init()
    batt, hero, (foe,) = _fight()
    scr = BattleScreen(ui_fonts(), batt, on_battle_end=lambda b: None)
    surf = pygame.Surface((1400, 800))
    for who in (foe, hero):
        scr.inspect = who
        scr.inspect_open = True
        scr.mouse = (0, 0)
        scr.draw(surf)
    assert scr._hp_bar(foe)["hp_steps"] == intel.STEPS and scr._hp_bar(hero)["hp_steps"] is None
    assert scr._inspect_body_h(foe) == foe_panel.card_height(scr._foe_card(foe))


def test_foe_card_scrolls_and_clamps_at_720p():
    from editor.battle_screen import BattleScreen
    pygame.init()
    batt, hero, (foe,) = _fight()
    _read(batt, "player", foe, intel.HARD)
    card = foe_card.foe_card(intel.known_fields(batt, "player", foe))

    # 1. Direct draw_foe_card test with constrained height and scroll
    surf = pygame.Surface((300, 150))
    rect = pygame.Rect(0, 0, 300, 150)
    tip = foe_panel.draw_foe_card(surf, ui_fonts(), rect, card, (0, 0), scroll=50)
    assert tip is None

    # 2. BattleScreen at 720p clamps inspect so actions has room and foe panel is scrollable
    scr = BattleScreen(ui_fonts(), batt, on_battle_end=lambda b: None)
    screen_720 = pygame.Surface((1280, 720))
    scr.inspect = foe
    scr.inspect_open = True
    scr.mouse = (0, 0)
    scr.draw(screen_720)
    assert getattr(scr, "_foe_max_scroll", 0) > 0
    assert getattr(scr, "_actions_scroll_rect", None) is not None
    assert scr._actions_scroll_rect.h >= 140
