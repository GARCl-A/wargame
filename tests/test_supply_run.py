import pytest
from gartok import campaign, economy, encounters, factions, orders
from gartok.group import Group
from gartok.guild import Guild
from gartok.ledger_screen import LedgerScreen
from tests.helpers import Unit


def _make_guild(node="ledger_hold", deeds=()):
    u1 = Unit("Fighter")
    u2 = Unit("Ranger")
    u3 = Unit("Cleric")
    for u in (u1, u2, u3):
        u.strength = 18
        u._derive_carry()
    grp = Group([u1, u2, u3], node=node)
    g = Guild(None, groups=[grp], deeds_done=list(deeds))
    return g, grp, u1, u2, u3


def test_supply_run_requires_ledger_hold_and_cargo():
    g, grp, u1, u2, u3 = _make_guild(node="city")
    with pytest.raises(ValueError, match="ledger_hold"):
        orders.supply_run(g, grp)

    grp.node = "ledger_hold"
    # Artificially overload characters so free capacity < 20 kg
    for u in (u1, u2, u3):
        u.give_to_pack("Iron Ingot", 50)
    assert grp.free_cargo_capacity < economy.SUPPLY_RUN_CARGO_KG

    with pytest.raises(ValueError, match="free cargo capacity"):
        orders.supply_run(g, grp)

    # Remove overloaded weight
    for u in (u1, u2, u3):
        u.remove_named("Iron Ingot", 50)
    assert grp.free_cargo_capacity >= economy.SUPPLY_RUN_CARGO_KG
    order = orders.supply_run(g, grp)
    assert order.kind == "work"
    assert order.task == "supply_run"
    assert order.hours == economy.SUPPLY_RUN_HOURS


def test_supply_run_peaceful_completion(monkeypatch):
    g, grp, u1, u2, u3 = _make_guild()
    order = orders.supply_run(g, grp)
    grp.order = order

    # Ensure no ambush
    monkeypatch.setattr("random.random", lambda: 0.99)

    m1_before = u1.money
    m2_before = u2.money
    res = campaign.advance(g, economy.SUPPLY_RUN_HOURS)

    assert grp.order is None
    assert u1.money == m1_before + economy.SUPPLY_RUN_PAY
    assert u2.money == m2_before + economy.SUPPLY_RUN_PAY
    assert "ledger_hold_supply_run" in g.deeds_done
    assert u1.work_xp > 0
    assert any("completed the frontier supply run" in ev for ev in res.events)


def test_supply_run_ambush_and_resolution(monkeypatch):
    g, grp, u1, u2, u3 = _make_guild()
    order = orders.supply_run(g, grp)
    grp.order = order

    # Force ambush
    monkeypatch.setattr("random.random", lambda: 0.0)
    res = campaign.advance(g, economy.SUPPLY_RUN_HOURS)

    assert grp.pending is not None
    assert grp.pending.kind == "supply_ambush"
    assert len(grp.pending.pack) > 0

    saved_order = grp.pending

    # Test loss resolution
    class MockOutcomeLoss:
        won = False
        survivors = [u1, u2, u3]

    events_loss = campaign.resolve_supply_ambush(g, grp, saved_order, MockOutcomeLoss())
    assert any("overrun and routed" in ev for ev in events_loss)
    assert "ledger_hold_supply_run" not in g.deeds_done

    # Test win resolution
    class MockOutcomeWin:
        won = True
        survivors = [u1, u2, u3]

    events_win = campaign.resolve_supply_ambush(g, grp, saved_order, MockOutcomeWin())
    assert any("fought off the frontier warband" in ev for ev in events_win)
    assert "ledger_hold_supply_run" in g.deeds_done


def test_ledger_screen_supply_run_card():
    g, grp, u1, u2, u3 = _make_guild(deeds=["bankers_trust"])
    done_called = False

    def on_done():
        nonlocal done_called
        done_called = True

    screen = LedgerScreen(None, g, grp, on_done)
    import pygame
    surf = pygame.Surface((1000, 700))
    screen.draw(surf)

    # Check supply_run button is registered
    btn_keys = [k for k, _ in screen.buttons]
    assert "supply_run" in btn_keys

    # Click supply_run button
    supply_rect = next(r for k, r in screen.buttons if k == "supply_run")
    screen._click(supply_rect.center)

    assert grp.order is not None
    assert grp.order.task == "supply_run"
    assert done_called is True
