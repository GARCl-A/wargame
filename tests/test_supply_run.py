"""The Ledger Hold supply run is a walk: out to the Frontier Outpost and back at the group's pace,
one ambush roll a leg, a fight stopping the caravan part-way along the road, the fixed pay on the
return to Ledger Hold."""

import random
from types import SimpleNamespace

import pytest

from gartok import campaign, economy, encounters, forced, orders, persist, world
from gartok.group import Group
from gartok.guild import Guild
from gartok.ledger_screen import LedgerScreen
from gartok.map_screen import _position
from tests.helpers import Unit


class _Rolls:
    """An rng whose `random()` answers come from a list (the ambush rolls); `uniform` is the midpoint."""

    def __init__(self, *rolls):
        self.rolls = list(rolls)

    def random(self):
        return self.rolls.pop(0)

    def uniform(self, a, b):
        return (a + b) / 2


HIT, MISS = 0.0, 0.99


def _make_guild(node="ledger_hold", deeds=()):
    units = [Unit("Fighter"), Unit("Ranger"), Unit("Cleric")]
    for u in units:
        u.strength = 18
        u._derive_carry()
    grp = Group(units, node=node)
    return Guild(None, groups=[grp], deeds_done=list(deeds)), grp, units


def _walk(guild, grp):
    """Advance the clock until the group stops: home, or held by an ambush."""
    res = None
    for _ in range(10):
        if grp.order is None:
            break
        res = campaign.advance(guild)
    return res


def _won(units):
    return SimpleNamespace(won=True, survivors=list(units), fallen=[], player_kos=0)


def _lost():
    return SimpleNamespace(won=False, survivors=[], fallen=[], player_kos=0)


def test_supply_run_requires_ledger_hold_and_cargo():
    g, grp, units = _make_guild(node="city")
    with pytest.raises(ValueError, match="ledger_hold"):
        orders.supply_run(g, grp)
    grp.node = "ledger_hold"
    for u in units:
        u.give_to_pack("Lumber", 40)            # past even a Large race's carry
    with pytest.raises(ValueError, match="free cargo capacity"):
        orders.supply_run(g, grp)


def test_the_run_is_a_walk_out_to_the_outpost_and_back():
    g, grp, _ = _make_guild()
    order = g.supply_leg(grp, grp.node, orders.supply_route(), rng=_Rolls(MISS))
    assert order.kind == "travel" and order.task == "supply_run"
    assert order.dest == "frontier_outpost" and order.final_dest == "ledger_hold"
    assert order.owed == 0
    assert orders.supply_hours(g, grp) == pytest.approx(
        2 * world.hours(5, grp.speed))


def test_a_quiet_run_pays_the_fixed_wage_back_at_ledger_hold(monkeypatch):
    g, grp, units = _make_guild()
    monkeypatch.setattr(random, "random", lambda: MISS)
    before = [u.money for u in units]
    grp.order = orders.supply_run(g, grp)
    campaign.advance(g)
    assert grp.node == "frontier_outpost" and grp.order.dest == "ledger_hold"
    assert grp.order.task == "supply_run" and all(u.money == m for u, m in zip(units, before))
    res = _walk(g, grp)
    assert grp.node == "ledger_hold" and grp.order is None
    assert [u.money - m for u, m in zip(units, before)] == [economy.SUPPLY_RUN_PAY] * 3
    assert g.supply_runs_completed == 1 and units[0].work_xp > 0
    assert any("completed the frontier supply run" in ev for ev in res.events)


def test_the_tenth_run_earns_the_deed(monkeypatch):
    g, grp, _ = _make_guild()
    monkeypatch.setattr(random, "random", lambda: MISS)
    g.supply_runs_completed = 9
    grp.order = orders.supply_run(g, grp)
    _walk(g, grp)
    assert g.supply_runs_completed == 10 and "ledger_hold_supply_run" in g.deeds_done


def test_each_leg_rolls_the_ambush_once():
    g, grp, _ = _make_guild()
    chance = economy.SUPPLY_RUN_AMBUSH_CHANCE
    assert g.supply_leg(grp, grp.node, orders.supply_route(), rng=_Rolls(chance - 0.01)).owed > 0
    assert g.supply_leg(grp, grp.node, orders.supply_route(), rng=_Rolls(chance + 0.01)).owed == 0


def test_an_ambush_stops_the_caravan_part_way_and_a_win_walks_on(monkeypatch):
    g, grp, units = _make_guild()
    grp.order = g.supply_leg(grp, grp.node, orders.supply_route(), rng=_Rolls(HIT))
    leg = grp.order.eta
    assert grp.order.remaining == pytest.approx(leg / 2) and grp.order.owed == pytest.approx(leg / 2)
    assert grp.order.remaining + grp.order.owed == pytest.approx(world.hours(5, grp.speed))

    res = campaign.advance(g)
    ambush = grp.pending
    assert ambush.kind == "supply_ambush" and (grp, ambush) in res.pending
    assert grp.node == "ledger_hold" and grp.order is None
    assert _position(grp) == ("ledger_hold", "frontier_outpost", pytest.approx(0.5))

    events = forced.resolve_supply_ambush(g, grp, ambush, _won(units))
    assert "rolls on" in events[0]
    assert grp.order.task == "supply_run" and grp.order.dest == "frontier_outpost"
    assert grp.order.remaining == pytest.approx(leg / 2) and grp.order.owed == 0
    assert g.supply_runs_completed == 0

    monkeypatch.setattr(random, "random", lambda: MISS)
    _walk(g, grp)
    assert grp.node == "ledger_hold" and g.supply_runs_completed == 1


def test_a_bribe_or_a_bluff_walks_on_like_a_win():
    g, grp, _ = _make_guild()
    grp.order = g.supply_leg(grp, grp.node, orders.supply_route(), rng=_Rolls(HIT))
    campaign.advance(g)
    forced.settle_talk(g, grp, grp.pending)
    assert grp.pending is None and grp.order.task == "supply_run" and grp.order.owed == 0


def test_routed_on_the_way_out_the_escort_is_back_at_ledger_hold():
    g, grp, units = _make_guild()
    before = [u.money for u in units]
    grp.order = g.supply_leg(grp, grp.node, orders.supply_route(), rng=_Rolls(HIT))
    campaign.advance(g)
    events = forced.resolve_supply_ambush(g, grp, grp.pending, _lost())
    assert grp.node == "ledger_hold" and grp.order.kind == "idle"
    assert "Ledger Hold" in events[0] and g.supply_runs_completed == 0
    assert [u.money for u in units] == before


def test_routed_on_the_way_back_the_escort_is_at_the_outpost():
    g, grp, _ = _make_guild(node="frontier_outpost")
    grp.order = g.supply_leg(grp, grp.node, ["ledger_hold"], rng=_Rolls(HIT))
    campaign.advance(g)
    events = forced.resolve_supply_ambush(g, grp, grp.pending, _lost())
    assert grp.node == "frontier_outpost" and "Frontier Outpost" in events[0]


def test_the_ambush_is_four_to_ten_soldiers_of_level_three_to_eight_mostly_low():
    rng = random.Random(7)
    packs = [encounters.roll_supply_ambush(rng) for _ in range(60)]
    sizes = [len(p) for p in packs]
    levels = [u.mean_level for p in packs for u in p]
    assert 4 <= min(sizes) and max(sizes) <= 10
    assert 3 <= min(levels) and max(levels) <= 8 and max(levels) >= 7
    assert sum(levels) / len(levels) < 5.5
    assert all(u.race.get("kind") == "humanoid" for p in packs for u in p)


def test_level_weights_lean_to_the_peak_and_stay_in_range():
    w = encounters.level_weights(3, 8, peak=4, spread=2)
    assert list(w) == [3, 4, 5, 6, 7, 8]
    assert max(w, key=w.get) == 4 and w[3] > w[8]


def test_a_table_may_ask_past_the_enemy_caps_but_a_scaled_fight_may_not():
    u = encounters.build_enemy(8, random.Random(1))
    assert (u.combat_level, u.work_level) == (8, 8)
    assert encounters.clamp_level(15) == 6


def test_a_held_caravan_survives_a_save():
    g, grp, _ = _make_guild()
    grp.order = g.supply_leg(grp, grp.node, orders.supply_route(), rng=_Rolls(HIT))
    campaign.advance(g)
    loaded = persist.group_from_dict(persist.group_to_dict(grp)).pending
    assert loaded.kind == "supply_ambush" and loaded.dest == "frontier_outpost"
    assert loaded.owed == pytest.approx(grp.pending.owed) and loaded.resume_path == ("ledger_hold",)
    assert len(loaded.pack) == len(grp.pending.pack)


def test_ledger_screen_sends_the_caravan_out():
    import pygame
    g, grp, _ = _make_guild(deeds=["bankers_trust"])
    done = []
    screen = LedgerScreen(None, g, grp, lambda: done.append(1))
    screen.draw(pygame.Surface((1000, 700)))
    supply_rect = next(r for k, r in screen.buttons if k == "supply_run")
    screen._click(supply_rect.center)
    assert grp.order.kind == "travel" and grp.order.task == "supply_run" and done == [1]


def test_supply_run_count_survives_a_save(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    g, _, _ = _make_guild()
    g.supply_runs_completed = 7
    persist.save_game("test_world_supply", g)
    assert persist.load_game("test_world_supply").supply_runs_completed == 7
