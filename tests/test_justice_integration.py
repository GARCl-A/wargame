"""The guard, end to end: `campaign.advance` pausing a group at a jurisdiction
node, the three `forced.resolve_guard_*` outcomes, and the app wiring that
opens the patrol's dialogue / runs the patrol fight (same monkeypatch technique as
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

from gartok import campaign, forced, orders
from gartok.group import Group
from gartok.guild import Guild
from tests.helpers import Unit, fixed_d20


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

    events = forced.resolve_guard_prison(guild, g, order)
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

    events = forced.resolve_guard_prison(guild, g, order)

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
        events, pause = forced.resolve_guard_flee(guild, g, order)
    assert g.node == "city" and g.order is None   # idle -- same convention as advance()'s own catch
    assert pause is not None and pause.kind == "guard"   # re-caught, no further node to flee to
    assert pause.prev_node is None             # RUN is off the table now (the patrol's dialogue drops it)
    assert any("fall back" in e for e in events)
    assert forced.resolve_guard_flee(guild, g, pause) == ([], None)   # a no-op if reached anyway


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
        events, pause = forced.resolve_guard_flee(guild, g, order)
    assert g.node == "city" and g.order.kind == "idle" and pause is None


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
    forced.resolve_guard_fight_aftermath(guild, g, order, outcome)

    assert culprit.crime == 3 + 1 + 1          # brawled + 1 guard downed
    assert mate.crime == 0                     # bystander, untouched
    assert g.order.kind == "idle"
