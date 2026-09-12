"""The guard, end to end: `campaign.advance` pausing a group at a jurisdiction
node, the three `campaign.resolve_guard_*` outcomes, and the app wiring that
opens `GuardScreen` / runs the patrol fight (same monkeypatch technique as
`test_map_orders_integration.py`).

A caught group goes idle (`group.order is None`) the moment the catch fires --
same convention an interactive order (market/arena/...) already uses -- so the
paused state lives only in the `(group, order)` pair `campaign.advance`
returns via `TickResult.pending`, never on `group.order` itself. That is what
keeps a *second*, unrelated `advance()` call (e.g. another group's hunt tick)
from mistaking a still-unresolved catch for a busy group and silently
discarding it -- see the regression test below.
"""

import random

from tests.helpers import fixed_d20, Battle, Unit, world
from gartok import campaign, orders
from gartok.app import App
from gartok.group import Group
from gartok.guild import Guild


def _app(guild):
    app = App.__new__(App)
    app.fonts = None
    app.guild = guild
    app._battle_squad = []
    app._battle_node = None
    app._arena_offer = None
    app._hunt = None
    app._guard_order = None
    app._guard_group = None
    app._map_notices = []
    app._pending = []
    app._save = lambda: None
    return app


def _caught(guild, g):
    """Advance until a guard order comes back pending; return it. Callers wrap
    this in `fixed_d20` to control whether the test roll into that node."""
    result = campaign.advance(guild)
    order = next(o for grp, o in result.pending if grp is g)
    return result, order


def test_a_clean_group_travels_through_the_city_untouched():
    random.seed(1)
    g = Group([Unit("player")], node="city")
    guild = Guild(None, groups=[g])
    g.order = orders.travel(g, "market")
    result = campaign.advance(guild)
    assert g.node == "market" and g.order is None
    assert not result.pending


def test_arriving_at_a_jurisdiction_node_with_crime_can_pause_the_group():
    random.seed(1)
    culprit = Unit("player")
    culprit.crime = 5
    g = Group([culprit], node="city")
    guild = Guild(None, groups=[g])
    g.order = orders.travel(g, "market")

    with fixed_d20(20):                       # guarantees the catch
        result, order = _caught(guild, g)

    assert g.node == "market"                 # still moved -- the guard meets it there
    assert g.order is None                    # idle, same as any due interactive order
    assert order.kind == "guard"
    assert order.caught == (culprit.uid,)
    assert order.prev_node == "city"
    assert order.resume_path == ()            # this WAS the final stop


def test_a_second_advance_call_does_not_wipe_an_unresolved_catch():
    """Regression: a guard order used to live on `group.order`, which made it
    look "busy" to a later, unrelated `advance()` call (e.g. another group's
    hunt tick) -- that call would resolve it into oblivion (no kind branch
    matches "guard") without ever re-queuing it. Since the catch went idle
    instead, a second `advance()` with nothing else in flight is simply a
    no-op for this group."""
    random.seed(1)
    culprit = Unit("player")
    culprit.crime = 5
    g = Group([culprit], node="city")
    guild = Guild(None, groups=[g])
    g.order = orders.travel(g, "market")
    with fixed_d20(20):
        _result, order = _caught(guild, g)
    assert g.node == "market" and g.order is None

    again = campaign.advance(guild)           # nothing left in flight -- must be a no-op
    assert again.pending == [] and not again.events
    assert g.node == "market" and g.order is None
    assert order.caught == (culprit.uid,)     # the original catch is still intact


def test_the_pause_survives_a_waypoint_and_resumes_the_rest_of_the_route():
    """tavern -> arena routes through 'city' -- a real jurisdiction waypoint,
    not the final stop -- so the catch has to pause mid-route and later
    resume the leg still owed."""
    random.seed(1)
    culprit, mate = Unit("player"), Unit("player")   # mate: crime 0, stays free and keeps the group alive
    culprit.crime = 5
    g = Group([culprit, mate], node="tavern")
    guild = Guild(None, groups=[g])
    g.order = orders.travel(g, "arena")        # tavern -> city -> arena

    with fixed_d20(20):
        result, order = _caught(guild, g)

    assert g.node == "city"                    # paused at the waypoint, not the final stop
    assert g.order is None
    assert order.resume_path == ("arena",)

    events = campaign.resolve_guard_prison(guild, g, order)
    assert any("cells" in e for e in events)
    assert g.order.kind == "travel" and g.order.dest == "arena"

    with fixed_d20(1):                         # a clean record now (jailed) never re-catches
        campaign.advance(guild)
    assert g.node == "arena" and g.order is None


def test_resolve_guard_prison_jails_and_resumes_to_idle_at_the_final_stop():
    random.seed(1)
    culprit, mate = Unit("player"), Unit("player")
    culprit.crime = 2
    g = Group([culprit, mate], node="city")
    guild = Guild(None, groups=[g])
    g.order = orders.travel(g, "market")
    with fixed_d20(20):
        _result, order = _caught(guild, g)

    events = campaign.resolve_guard_prison(guild, g, order)

    assert culprit not in g.members and (culprit, guild.clock.day + 4) in guild.jailed
    assert mate in g.members                   # the rest of the group stays free
    assert g.order.kind == "idle"
    assert any("cells" in e for e in events)


def test_resolve_guard_flee_falls_back_and_can_chain_into_another_catch():
    random.seed(1)
    culprit = Unit("player")
    culprit.crime = 5
    g = Group([culprit], node="city")
    guild = Guild(None, groups=[g])
    g.order = orders.travel(g, "market")
    with fixed_d20(20):
        _result, order = _caught(guild, g)
    assert g.node == "market"

    with fixed_d20(20):                       # caught again immediately back at the city
        events = campaign.resolve_guard_flee(guild, g, order)
    assert g.node == "city"
    assert g.order.kind == "guard"             # re-caught, no further node to flee to
    assert g.order.prev_node is None           # RUN is off the table now (GuardScreen hides it)
    assert any("fall back" in e for e in events)
    assert campaign.resolve_guard_flee(guild, g, g.order) == []   # a no-op if reached anyway


def test_resolve_guard_flee_resumes_idle_when_the_fallback_node_is_clean():
    random.seed(1)
    culprit = Unit("player")
    culprit.crime = 5
    g = Group([culprit], node="city")
    guild = Guild(None, groups=[g])
    g.order = orders.travel(g, "market")
    with fixed_d20(20):
        _result, order = _caught(guild, g)
    assert g.node == "market"

    with fixed_d20(1):                        # no catch this time back at the city
        campaign.resolve_guard_flee(guild, g, order)
    assert g.node == "city" and g.order.kind == "idle"


def test_resolve_guard_fight_aftermath_only_banks_crime_for_the_caught_survivor():
    random.seed(1)
    culprit, mate = Unit("player"), Unit("player")
    culprit.crime = 3
    g = Group([culprit, mate], node="city")
    guild = Guild(None, groups=[g])
    g.order = orders.travel(g, "market")
    with fixed_d20(20):
        _result, order = _caught(guild, g)

    outcome = campaign.BattleOutcome(won=True, survivors=[culprit, mate], fallen=[], player_kos=1)
    campaign.resolve_guard_fight_aftermath(guild, g, order, outcome)

    assert culprit.crime == 3 + 1 + 1          # brawled + 1 guard downed
    assert mate.crime == 0                     # bystander, untouched
    assert g.order.kind == "idle"


def test_app_opens_guard_screen_then_the_patrol_fight_resolves_through_battle_end():
    import gartok.app as app_mod
    random.seed(1)
    culprit = Unit("player")
    culprit.crime = 4
    g = Group([culprit], node="city")
    guild = Guild(None, groups=[g])
    app = _app(guild)
    g.order = orders.travel(g, "market")

    saved = {}
    orig = app_mod.GuardScreen
    app_mod.GuardScreen = lambda fonts, guild_, group, order, caught, **kw: saved.update(
        group=group, order=order, caught=caught, kw=kw) or object()
    try:
        with fixed_d20(20):
            app._advance()
    finally:
        app_mod.GuardScreen = orig

    assert saved["caught"] == [culprit]
    guard_order = saved["order"]
    assert guard_order.kind == "guard" and g.order is None

    # FIGHT THE PATROL: the app drops the whole present squad into a real,
    # lethal fight against a scaled patrol -- resolved the same way any other
    # battle folds back into the guild (campaign.absorb_battle).
    saved["kw"]["on_fight"](g, guard_order)
    assert app._guard_order is guard_order and app._guard_group is g

    # BattleScreen isn't monkeypatched here -- build the battle result by hand,
    # same technique test_campaign.py uses for absorb_battle.
    fought = Battle([culprit], [Unit("enemy")])
    fought.winner = "player"
    fought.round_no = 1
    fought.player_units[0].status = "up"
    app._battle_squad = [culprit]
    app._battle_node = world.node("market")

    app._battle_end(fought)

    assert culprit.crime == 4 + 1              # brawled, no kills credited
    assert app._guard_order is None and app._guard_group is None
    assert g.order.kind == "idle"
