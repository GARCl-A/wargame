"""The proof of concept of programmable orders (docs/plans/programmable_orders.md).

A strict xfail until routines exist: once the build makes it pass, the test fails and the mark goes.
`_program` is the one place that speaks the routine vocabulary."""

import random

import pytest

from gartok import campaign, forced, gather
from gartok.clock import Clock
from gartok.group import Group
from gartok.guild import Guild
from tests.helpers import standard_unit

DAYS = 24
WINDOW_DAYS = 3
LUMBER_BATCH = 8
POTATOES_BOUGHT = 4
POTATOES_HANDED = 3


def _band(node, name, n, potatoes, money=0):
    members = [standard_unit() for _ in range(n)]
    for u in members:
        u.money = money
        u.give_to_pack("Potato", potatoes)
    return Group(members, node=node, name=name, leader=members[0])


def _stage():
    hunters = _band("wilds", "Hunters", 2, 3)
    b = _band("lumber_yard", "Gatherers", 2, 3)
    c = _band("lumber_yard", "Trader", 1, 3, money=30)
    for u in b.members:
        u.give_to_pack(gather.tool("lumber_yard"))
    guild = Guild(list(hunters.members), clock=Clock(6 * 3600), node="wilds")
    a = guild.groups[0]
    a.name = "Hunters"
    guild.groups.extend([b, c])
    guild.licences.add("lumber_yard")
    return guild, a, b, c


def _program(b, c):
    from gartok import routines as r
    mill = r.group("Gatherers")
    b.routine = r.Routine([
        r.repeat_until(r.coins(r.group("Trader")) >= 500, [r.gather(hours=16)]),
    ])
    c.routine = r.Routine([
        r.repeat_while(r.coins(r.own()) < 500, [
            r.wait_until(r.items(mill, "Lumber") >= LUMBER_BATCH),
            r.take(mill, "Lumber"),
            r.travel("farm"),
            r.trade(sell="Lumber", buy={"Potato": POTATOES_BOUGHT}),
            r.travel("lumber_yard"),
            r.hand_over(mill, "Potato", POTATOES_HANDED),
        ]),
    ])


def _lumber_made(guild, b, c):
    packs = sum(u.count_of("Lumber") for g in (b, c) for u in g.members)
    return packs + guild.shop("farm").stock.get("Lumber", 0)


def _lumber_at_farm(guild):
    return guild.shop("farm").stock.get("Lumber", 0)


def _hunt_by_hand(a):
    for u in a.members:
        have = u.count_of("Potato")
        if have < 3:
            u.give_to_pack("Potato", 3 - have)


@pytest.mark.xfail(strict=True, reason="routines are not built yet (programmable_orders.md)")
def test_a_hunter_played_by_hand_while_a_gatherer_and_a_trader_run_on_routines(monkeypatch):
    random.seed(7)
    monkeypatch.setattr(forced, "arrival_pause", lambda *args, **kwargs: None)
    monkeypatch.setattr(gather, "ambushed", lambda *args, **kwargs: False)
    guild, a, b, c = _stage()
    _program(b, c)
    roster = len(guild.roster)
    steps = [16, 8, 24, None]
    made = sold = 0
    window_start = guild.clock.day
    last_day = window_start + DAYS

    i = 0
    while guild.clock.day < last_day:
        _hunt_by_hand(a)
        dt = steps[i % len(steps)]
        i += 1
        before = guild.clock.seconds
        result = campaign.advance(guild, dt=dt)
        if dt is not None:
            assert guild.clock.seconds - before == dt * 3600

        assert not result.wiped and len(guild.roster) == roster
        assert all(u.hunger_level == 0 for g in (b, c) for u in g.members)
        assert b.order is not None and c.order is not None
        assert not {g.gid for g, _ in result.pending} & {b.gid, c.gid}
        assert a.node == "wilds" and a.order is None

        if guild.clock.day - window_start >= WINDOW_DAYS:
            now_made, now_sold = _lumber_made(guild, b, c), _lumber_at_farm(guild)
            assert now_made > made and now_sold > sold
            made, sold, window_start = now_made, now_sold, guild.clock.day
