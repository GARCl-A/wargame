"""The shop's big keeper header: who they are, their line, and the party's deal."""

import os

import pygame

from gartok import economy, world
from gartok.guild import Guild
from gartok.market_screen import MarketScreen
from gartok.ui.tokens import fonts as ui_fonts
from gartok.ui.vendor_panel import draw_vendor_header
from gartok.unit import Unit

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def _shoppers(*tongues, alignment="Lawful and Neutral"):
    units = []
    for t in tongues:
        u = Unit("player")
        u.languages = list(t)
        u.alignment = alignment
        units.append(u)
    return units


def _screen(node_id, units):
    return MarketScreen(None, Guild(units), units, world.node(node_id), lambda: None)


def test_every_keeper_has_a_line_of_their_own():
    keepers = {v.name: v for n in world.NODES for v in n.vendors.values()}
    assert all(v.line for v in keepers.values()), [n for n, v in keepers.items() if not v.line]
    assert len({v.line for v in keepers.values()}) == len(keepers)


def test_every_shop_keeper_haggles_in_a_tongue_with_a_bent():
    for n in world.NODES:
        if n.has("shop"):
            assert n.language and n.alignment, n.id


def test_the_card_splits_the_bent_and_lists_the_tongues():
    s = _screen("farm", _shoppers(["Ankarin"]))
    card = s._vendor_card(world.vendor("farm", "shop"))
    assert card["tongues"] == ["Ankarin", "Sylvan"]
    assert card["bent"] == ["Lawful", "Good"]
    assert card["place"] == "The Farm" and card["line"]


def test_a_true_neutral_bent_is_one_chip():
    s = _screen("smith", _shoppers(["Dwarvish"]))
    s.node = type("N", (), {"name": "X", "language": "Dwarvish", "alignment": "Neutral and Neutral"})()
    assert s._vendor_card(world.vendor("smith", "shop"))["bent"] == ["Neutral"]


def test_the_deal_names_who_speaks_and_matches_the_prices():
    units = _shoppers(["Ankarin"], ["Ankarin", "Dwarvish"])
    s = _screen("smith", units)
    deal = s._deal_card()
    assert deal["why"][0] == f"{units[1].name} speaks for the group"
    pct = round(economy.deal_value(s.deal, None, "buy") * 100)
    assert deal["headline"] == (f"{pct}% off" if pct > 0 else f"{-pct}% markup" if pct < 0 else "list price")


def test_nobody_speaking_the_tongue_means_no_haggling():
    s = _screen("smith", _shoppers(["Ankarin"]))
    deal = s._deal_card()
    assert deal["headline"] == "no haggling" and deal["tone"] == "none"
    assert "no one speaks Dwarvish" in deal["why"]


def test_the_lumber_yard_and_the_mine_now_haggle():
    orc, goblin = _shoppers(["Orcish"]), _shoppers(["Goblin"])
    assert economy.haggle_voice(orc, "Orcish", world.node("lumber_yard").alignment)[0] is orc[0]
    assert _screen("mine", goblin)._deal_card()["headline"] != "no haggling"


def test_the_voice_is_the_leader_when_they_speak_the_tongue():
    a, b = _shoppers(["Dwarvish"], ["Dwarvish"])
    voice, _ = economy.haggle_voice([a, b], "Dwarvish", "Lawful and Neutral", leader=b)
    assert voice is b


def test_a_long_line_grows_the_header_below_the_portrait():
    pygame.init()
    surf = pygame.display.set_mode((640, 480))
    card = {"place": "Tavern", "name": "Tobbin", "caption": "Halfling innkeeper", "portrait": "innkeeper.png",
            "line": "word " * 60, "tongues": ["Halfling"], "bent": ["Neutral", "Good"]}
    deal = {"headline": "8% off", "tone": "good", "why": ["X speaks for the group"]}
    short = pygame.Rect(16, 16, 520, 96)
    assert draw_vendor_header(surf, ui_fonts(), short, card, deal) > short.bottom
    tall = pygame.Rect(16, 16, 520, 128)
    assert draw_vendor_header(surf, ui_fonts(), tall, {**card, "line": "Hi."}, deal) == tall.bottom


def test_the_shop_screen_draws_with_the_big_header():
    pygame.init()
    surf = pygame.display.set_mode((1280, 720))
    s = MarketScreen(ui_fonts(), Guild(_shoppers(["Ankarin"])), _shoppers(["Ankarin"]),
                     world.node("tanner"), lambda: None)
    s.draw(surf)
    assert s.tab_hits and s.tab_hits[0][0].y > 96
