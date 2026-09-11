"""End-to-end (headless) tests for the tick -> app drain-queue wiring:
`app._advance()` calls `campaign.advance` and, for every interactive order that
comes due, opens the matching screen scoped to that group's own members --
draining one at a time via `_after_activity` (the shared on_done/on_back target)
until the queue is empty. Screen classes are monkey-patched in `gartok.app`'s
namespace (same technique as `test_arena_games.py`) so no real pygame/font
objects are needed."""

import random

from tests.helpers import Unit, world
from gartok import orders
from gartok.app import App
from gartok.group import Group
from gartok.guild import Guild
from gartok.map_screen import MapScreen


def _app(guild):
    app = App.__new__(App)
    app.fonts = None
    app.guild = guild
    app._battle_squad = []
    app._battle_node = None
    app._arena_offer = None
    app._hunt = None
    app._map_notices = []
    app._pending = []
    app._save = lambda: None            # no disk I/O in these tests
    return app


def test_a_travel_order_resolves_silently_and_returns_to_the_map():
    random.seed(1)
    g = Group([Unit("player")], node="city")
    guild = Guild(None, groups=[g])
    app = _app(guild)
    g.order = orders.travel(g, "market")
    app._advance()
    assert g.node == "market" and g.order is None
    assert isinstance(app.scene, MapScreen)
    assert not app._pending


def test_advance_chases_a_multi_hop_travel_through_every_waypoint_in_one_call():
    """city -> wilds has no direct edge (the route goes through 'road'); one
    call to `_advance()` should chase both legs silently -- no fresh click
    needed at the intermediate waypoint -- landing the group at the final
    stop, not just the first one."""
    random.seed(1)
    g = Group([Unit("player")], node="city")
    guild = Guild(None, groups=[g])
    app = _app(guild)
    g.order = orders.travel(g, "wilds")
    app._advance()
    assert g.node == "wilds" and g.order is None
    assert isinstance(app.scene, MapScreen)


def test_advance_stops_chasing_as_soon_as_any_group_goes_idle():
    """`mover`'s route needs two legs (city->road 4h, road->wilds 6h); `quick`
    finishes in 1h. The soonest-completion jump is 1h, so `quick` resolves and
    goes idle -- the chase must stop right there instead of also plowing
    through `mover`'s first waypoint on the same click."""
    random.seed(1)
    mover = Group([Unit("player")], node="city")
    quick = Group([Unit("player")], node="city")
    guild = Guild(None, groups=[mover, quick])
    app = _app(guild)
    mover.order = orders.travel(mover, "wilds")
    quick.order = orders.travel(quick, "market")
    app._advance()
    assert quick.node == "market" and quick.order is None
    assert mover.node == "city" and mover.order is not None and mover.order.remaining == 3


def test_a_lone_group_auto_advances_without_a_click():
    """A one-group guild has no one else to coordinate with: the moment its
    order is set, MapScreen fires `on_advance` itself instead of waiting on
    the ADVANCE button."""
    random.seed(1)
    g = Group([Unit("player")], node="city")
    guild = Guild(None, groups=[g])
    scr = MapScreen.__new__(MapScreen)
    scr.guild = guild
    scr.selected = g
    fired = []
    scr.on_advance = lambda: fired.append(True)
    scr._go(world.node("market"))
    assert g.busy and fired == [True]


def test_a_second_group_does_not_auto_advance():
    random.seed(1)
    a = Group([Unit("player")], node="city")
    b = Group([Unit("player")], node="city")
    guild = Guild(None, groups=[a, b])
    scr = MapScreen.__new__(MapScreen)
    scr.guild = guild
    scr.selected = a
    fired = []
    scr.on_advance = lambda: fired.append(True)
    scr._go(world.node("market"))
    assert a.busy and fired == []


def test_market_order_opens_the_market_screen_scoped_to_the_group():
    import gartok.app as app_mod
    random.seed(1)
    a, b = Unit("player"), Unit("player")
    g = Group([a, b], node="market")
    guild = Guild(None, groups=[g])
    app = _app(guild)
    g.order = orders.interactive("market")

    saved = {}
    orig = app_mod.MarketScreen
    app_mod.MarketScreen = lambda fonts, guild_, shoppers, node, on_done: saved.update(
        shoppers=shoppers, node=node, on_done=on_done) or object()
    try:
        app._advance()
    finally:
        app_mod.MarketScreen = orig
    assert saved["shoppers"] == [a, b]
    assert saved["node"].id == "market"
    assert saved["on_done"] == app._after_activity
    assert g.order is None


def test_hunt_stretch_keeps_another_groups_work_order_in_lockstep_with_the_clock():
    """A hunt plays out its hours through `HuntScreen`, outside the normal
    tick/orders loop -- it must still cost every OTHER busy group its share
    of the clock (here: a lumber-yard shift), not just the 1 h approach that
    got it to `HuntScreen` in the first place."""
    import gartok.app as app_mod
    random.seed(1)
    lumber = Group([Unit("player")], node="lumber_yard")
    hunters = Group([Unit("player")], node="wilds")
    guild = Guild(None, groups=[lumber, hunters])
    app = _app(guild)
    lumber.order = orders.work(guild, lumber, 8)          # 8 h shift, no speedup -> remaining 8
    hunters.order = orders.interactive("hunt")

    app._advance()                                         # chases the 1 h approach
    assert lumber.order.remaining == 7
    assert isinstance(app.scene, app_mod.HuntScreen)

    from gartok import hunt
    orig = hunt.hunt_stretch
    hunt.hunt_stretch = lambda state, rng=None: (4, False)  # a clean 4 h stretch, no ambush
    try:
        app.scene.hours = 4                                  # the setup-screen's chosen shift
        app.scene.state.hours_left = app.scene.hours          # what CONFIRM does before the stretch
        app.scene._do_stretch()
    finally:
        hunt.hunt_stretch = orig

    assert lumber.order.remaining == 3                     # 7 - 4, not stuck at 7
    assert app.scene.phase == "done"


def test_arena_order_opens_squad_screen_with_offers_scoped_to_the_group():
    import gartok.app as app_mod
    random.seed(1)
    a, b = Unit("player"), Unit("player")
    g = Group([a, b], node="arena")
    guild = Guild(None, groups=[g])
    app = _app(guild)
    g.order = orders.interactive("arena")

    saved = {}
    orig = app_mod.SquadScreen
    app_mod.SquadScreen = lambda fonts, roster, node, **kw: saved.update(
        roster=roster, kw=kw) or object()
    try:
        app._advance()
    finally:
        app_mod.SquadScreen = orig
    assert saved["roster"] == [a, b]
    assert saved["kw"]["confirm_label"] == "STAKE AND FIGHT"
    assert any(o.rep == 0 for o in saved["kw"]["arena_offers"])   # Rookie pit is open


def test_two_interactive_orders_drain_one_screen_at_a_time():
    import gartok.app as app_mod
    random.seed(1)
    a, b = Unit("player"), Unit("player")
    g1 = Group([a], node="market")
    g2 = Group([b], node="tavern")
    guild = Guild(None, groups=[g1, g2])
    app = _app(guild)
    g1.order = orders.interactive("market")
    g2.order = orders.interactive("recruit")
    assert g1.order.remaining == g2.order.remaining          # both due on the same tick

    opened = []
    orig_market, orig_taverna = app_mod.MarketScreen, app_mod.TavernaScreen
    app_mod.MarketScreen = lambda fonts, guild_, shoppers, node, on_done: (
        opened.append("market"), object())[1]
    app_mod.TavernaScreen = lambda fonts, guild_, party, node, on_done: (
        opened.append("recruit"), object())[1]
    try:
        app._advance()
        assert opened == ["market"]                # only the first one opened so far
        assert len(app._pending) == 1
        app._after_activity()                       # simulate the market screen finishing
        assert opened == ["market", "recruit"]
        assert not app._pending
    finally:
        app_mod.MarketScreen, app_mod.TavernaScreen = orig_market, orig_taverna


def test_a_group_that_starves_out_before_resolution_is_skipped():
    """A pending order can outlive its group: `campaign.advance` snapshots the
    active groups before running upkeep, so a group that starves out entirely
    during that same tick must not surface as a "screen to open" -- there's no
    one left to open it for. A second, well-fed group confirms this is the
    partial-wipe path, not the whole-guild wipe short-circuit."""
    random.seed(1)
    doomed = Unit("player")
    doomed._base_inventory = []
    doomed.share_food = False
    survivor = Unit("player")
    survivor._base_inventory = ["Meat"] * 20
    g1 = Group([doomed], node="market")
    g2 = Group([survivor], node="market")
    guild = Guild(None, groups=[g1, g2])
    app = _app(guild)
    g1.order = orders.interactive("market", hours=24 * 6)    # long enough to starve doomed
    g2.order = orders.interactive("market", hours=24 * 6)    # same ETA -- survivor has food

    opened = []
    import gartok.app as app_mod
    orig = app_mod.MarketScreen
    app_mod.MarketScreen = lambda *a, **k: (opened.append("market"), object())[1]
    try:
        app._advance()
    finally:
        app_mod.MarketScreen = orig
    assert not guild.empty and doomed not in guild.roster    # partial wipe, not a full one
    assert opened == ["market"]                              # only the survivor's order surfaced
