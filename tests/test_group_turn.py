"""The group hand-over card: whose turn it is when the clock moves the player between groups."""

import random

import pygame

from gartok import forced, orders
from gartok.app import App
from gartok.group import Group
from gartok.group_turn_screen import GroupTurnScreen
from gartok.guild import Guild
from gartok.map_screen import MapScreen
from gartok.ui.tokens import fonts
from gartok.ui.turn_card import draw_turn_card
from tests.helpers import Unit, make_app, walker


def _patch_market(monkeypatch, opened):
    from gartok import app_nodes
    monkeypatch.setattr(app_nodes, "MarketScreen",
                        lambda fonts_, guild_, shoppers, node, on_done: opened.append(shoppers) or object())


def test_a_lone_group_opens_its_screen_with_no_card(monkeypatch):
    random.seed(1)
    g = Group([Unit("player")], node="market")
    app = make_app(Guild(None, groups=[g]))
    opened = []
    _patch_market(monkeypatch, opened)
    g.order = orders.interactive("market")
    app._advance()
    assert opened == [list(g.members)]
    assert not isinstance(app.scene, GroupTurnScreen)


def test_another_groups_screen_waits_behind_the_card(monkeypatch):
    random.seed(1)
    shoppers = Group([Unit("player")], node="market")
    walkers = Group([walker()], node="city")
    app = make_app(Guild(None, groups=[shoppers, walkers]))
    opened = []
    _patch_market(monkeypatch, opened)
    shoppers.order = orders.interactive("market")
    walkers.order = orders.travel(walkers, "lumber_yard")
    app._focus_gid = walkers.gid                     # the player just ordered the walkers away
    app._advance()

    card = app.scene
    assert isinstance(card, GroupTurnScreen) and card.group is shoppers
    assert opened == []
    d = card.card()
    assert d["name"] == shoppers.display_name and d["action"] == "ENTER THE SHOP"
    assert d["band"].startswith("BAND 1 OF 2") and not d["danger"]
    card.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert opened == [list(shoppers.members)]
    assert app._focus_gid == shoppers.gid


def test_no_card_when_the_group_is_already_in_view(monkeypatch):
    random.seed(1)
    shoppers = Group([Unit("player")], node="market")
    idle = Group([Unit("player")], node="city")
    app = make_app(Guild(None, groups=[shoppers, idle]))
    opened = []
    _patch_market(monkeypatch, opened)
    shoppers.order = orders.interactive("market")
    app._focus_gid = shoppers.gid
    app._pending = [(shoppers, shoppers.order)]
    app._after_activity()
    assert opened == [list(shoppers.members)]


def test_the_map_landing_on_another_band_says_so():
    random.seed(1)
    away = Group([walker()], node="city")
    idle = Group([Unit("player")], node="market")
    away.order = orders.travel(away, "lumber_yard")
    app = make_app(Guild(None, groups=[away, idle]))
    app._focus_gid = away.gid
    app._start_map()

    card = app.scene
    assert isinstance(card, GroupTurnScreen) and card.group is idle
    assert card.card()["action"] == "AWAITS ORDERS"
    assert isinstance(card.resume_to, MapScreen)
    card.handle_escape()
    assert app.scene is card.resume_to
    app._start_map()                                 # same band again: no second card
    assert isinstance(app.scene, MapScreen)


def test_the_first_map_of_a_session_shows_no_card():
    random.seed(1)
    app = make_app(Guild(None, groups=[Group([Unit("player")], node="city"),
                                       Group([Unit("player")], node="market")]))
    app._start_map()
    assert isinstance(app.scene, MapScreen)


def test_every_forced_event_has_a_headline():
    for kind, event in forced.EVENTS.items():
        assert event.label, kind
        assert App._activity_label(orders.Order(kind=kind, remaining=0)) == event.label
    assert App._activity_label(orders.interactive("recruit")) == "ENTER THE TAVERN"
    assert App._activity_label(orders.Order(kind="arena", remaining=0)) == "ENTER THE ARENA"


def test_the_card_draws_inside_any_window():
    pygame.init()
    F = fonts()
    d = {"band": "BAND 2 OF 3  ·  ITS TURN", "name": "Water Team", "node": "The Wilds",
         "action": "AMBUSHED ON THE ROAD", "members": ["Ana", "Bruno", "Caio"] * 6,
         "color": (180, 40, 40), "danger": True, "button": "GO ON"}
    for size in ((1000, 640), (1920, 1080), (480, 640)):
        surf = pygame.Surface(size)
        card, button = draw_turn_card(surf, F, d)
        assert surf.get_rect().contains(card)
        assert card.contains(button)
