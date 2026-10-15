"""The forced-event registry (`forced.EVENTS`): a threat is one `ForcedEvent` entry, and the
tick engine, the app's dispatch and the settling all read it from there."""

import random
from types import SimpleNamespace

from gartok import campaign, forced, orders
from gartok.app import App
from gartok.app_forced import FORCED_PLAYERS
from gartok.group import Group
from gartok.guild import Guild
from tests.helpers import Unit, world


def test_every_event_has_a_way_to_be_played_and_an_opener():
    for kind, event in forced.EVENTS.items():
        assert event.kind == kind
        assert event.play in FORCED_PLAYERS
        assert kind in App._ACTIVITY_OPENERS


def test_no_forced_kind_doubles_as_a_player_order():
    assert not set(forced.EVENTS) & (orders.INTERACTIVE_KINDS | orders.AUTO_KINDS | orders.WORK_KINDS)


def _threat(monkeypatch, **hooks):
    settled = []

    def resolve(guild, group, order, outcome):
        settled.append(outcome.won)
        return forced.resume_arrival(guild, group, order)

    monkeypatch.setitem(forced.EVENTS, "test_threat",
                        forced.ForcedEvent("test_threat", "battle", resolve, **hooks))
    return settled


def test_a_new_arrival_threat_is_one_entry(monkeypatch):
    monkeypatch.setattr(world, "ROAD_AMBUSH_CHANCE", 0.0)
    catch = lambda guild, group, prev, path: (orders.Order("test_threat", pack=("x",), resume_path=tuple(path))
                                              if group.node == "road" else None)
    settled = _threat(monkeypatch, arrival=(catch,))
    g = Group([Unit("player")], node="city")
    guild = Guild(None, groups=[g])
    g.order = orders.travel(g, "road")

    result = campaign.advance(guild)

    (group, order), = result.pending
    assert group is g and order.kind == "test_threat"
    assert g.order is None and g.pending is order and g.locked
    forced.resolve(guild, g, order, SimpleNamespace(won=True))
    assert settled == [True] and g.pending is None and g.order.kind == "idle"


def test_a_new_daily_threat_is_one_entry(monkeypatch):
    g = Group([Unit("player")], node="city")
    guild = Guild(None, groups=[g])
    seen = []

    def daily(guild, days):
        seen.append(days)
        return ["Something stirs."], [(g, orders.Order("test_threat", pack=("x",)))] if days else []

    _threat(monkeypatch, daily=daily)

    result = campaign.advance(guild, dt=24)

    assert seen == [1]
    assert "Something stirs." in result.events
    assert result.pending == [(g, g.pending)] and g.pending.kind == "test_threat"


def test_arrival_catchers_run_in_registry_order_and_stop_at_the_first(monkeypatch):
    calls = []

    def first(guild, group, prev, path):
        calls.append("first")
        return orders.Order("test_threat")

    def second(guild, group, prev, path):
        calls.append("second")
        return orders.Order("test_threat")

    monkeypatch.setattr(forced, "EVENTS", {
        "a": forced.ForcedEvent("a", "battle", None, arrival=(first,)),
        "b": forced.ForcedEvent("b", "battle", None, arrival=(second,)),
    })
    g = Group([Unit("player")], node="road")
    assert forced.arrival_pause(Guild(None, groups=[g]), g, None, ()) is not None
    assert calls == ["first"]


def test_the_road_ambush_settles_through_the_registry(monkeypatch):
    random.seed(1)
    monkeypatch.setattr(world, "ROAD_AMBUSH_CHANCE", 1.0)
    g = Group([Unit("player")], node="city")
    guild = Guild(None, groups=[g])
    g.order = orders.travel(g, "road")
    (_, order), = campaign.advance(guild).pending
    assert order.kind == "ambush"

    forced.resolve(guild, g, order, SimpleNamespace(won=True, survivors=list(g.members)))

    assert g.pending is None and g.order.kind == "idle"
