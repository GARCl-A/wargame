"""The Old Road as an `unsafe` node (world.py/encounters.OLD_ROAD_TABLE): a
per-leg-arrival ambush chance that pauses a group's travel on a lethal fight,
same pause/resume seam `campaign.advance` already uses for the guard
(test_justice_integration.py). `world.ROAD_AMBUSH_CHANCE` is forced to 0.0 or
1.0 in every test here instead of seeding around it -- the real probability
is a tuning knob, not something worth making tests fight over."""

import random

from tests.helpers import Battle, Unit, world
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
    app._pause_order = None
    app._pause_group = None
    app._map_notices = []
    app._pending = []
    app._save = lambda: None
    return app


def _forced_chance(value):
    orig = world.ROAD_AMBUSH_CHANCE
    world.ROAD_AMBUSH_CHANCE = value
    return orig


def test_an_unsafe_arrival_can_pause_the_group_on_an_ambush():
    random.seed(1)
    orig = _forced_chance(1.0)                # guarantees the roll
    try:
        g = Group([Unit("player")], node="city")
        guild = Guild(None, groups=[g])
        g.order = orders.travel(g, "road")
        result = campaign.advance(guild)
    finally:
        world.ROAD_AMBUSH_CHANCE = orig

    assert g.node == "road" and g.order is None       # idle, same convention as "guard"
    order = next(o for grp, o in result.pending if grp is g)
    assert order.kind == "ambush"
    assert len(order.pack) > 0
    assert order.resume_path == ()                     # this was the final stop


def test_the_ambush_never_fires_when_the_chance_is_zero():
    random.seed(1)
    orig = _forced_chance(0.0)
    try:
        g = Group([Unit("player")], node="city")
        guild = Guild(None, groups=[g])
        g.order = orders.travel(g, "road")
        result = campaign.advance(guild)
    finally:
        world.ROAD_AMBUSH_CHANCE = orig

    assert g.node == "road" and g.order is None and not result.pending


def test_a_safe_node_never_rolls_an_ambush_even_at_full_chance():
    random.seed(1)
    orig = _forced_chance(1.0)                # would guarantee it, if "market" rolled at all
    try:
        g = Group([Unit("player")], node="city")
        guild = Guild(None, groups=[g])
        g.order = orders.travel(g, "market")
        result = campaign.advance(guild)
    finally:
        world.ROAD_AMBUSH_CHANCE = orig

    assert g.node == "market" and g.order is None and not result.pending


def test_the_pause_survives_a_waypoint_and_resumes_the_rest_of_the_route():
    """tavern -> wilds routes through 'road' as a waypoint, not the final
    stop -- the ambush has to pause mid-route and later resume the leg still
    owed, same as a guard catch at a waypoint. `campaign.advance` only chases
    ONE leg per call (that's `app._advance`'s job, not this module's) -- the
    first call just carries the group tavern -> city (a safe waypoint), the
    second is the city -> road leg the ambush actually interrupts."""
    random.seed(1)
    orig = _forced_chance(1.0)
    try:
        g = Group([Unit("player")], node="tavern")
        guild = Guild(None, groups=[g])
        g.order = orders.travel(g, "wilds")        # tavern -> city -> road -> wilds
        campaign.advance(guild)                     # tavern -> city (no ambush there)
        assert g.node == "city" and g.busy
        result = campaign.advance(guild)             # city -> road: the ambush hits
    finally:
        world.ROAD_AMBUSH_CHANCE = orig

    assert g.node == "road" and g.order is None
    order = next(o for grp, o in result.pending if grp is g)
    assert order.kind == "ambush" and order.resume_path == ("wilds",)

    fought = Battle(list(g.members), list(order.pack))
    fought.winner = "player"
    fought.round_no = 1
    for c in fought.player_units:
        c.status = "up"
    outcome = campaign.absorb_battle(guild, list(g.members), fought, node=world.node("road"))
    events = campaign.resolve_road_ambush(guild, g, order)

    assert g.order.kind == "travel" and g.order.dest == "wilds"
    assert outcome.won and not events                 # no notices -- just the fight itself


def test_a_wiped_group_after_the_ambush_leaves_nothing_to_resume():
    random.seed(1)
    orig = _forced_chance(1.0)
    try:
        victim = Unit("player")
        g = Group([victim], node="city")
        guild = Guild(None, groups=[g, Group([Unit("player")], node="market")])
        g.order = orders.travel(g, "road")
        result = campaign.advance(guild)
    finally:
        world.ROAD_AMBUSH_CHANCE = orig
    order = next(o for grp, o in result.pending if grp is g)

    fought = Battle([victim], list(order.pack))
    fought.winner = "enemy"
    fought.round_no = 1
    fought.player_units[0].status = "dead"
    campaign.absorb_battle(guild, [victim], fought, node=world.node("road"))

    assert g not in guild.groups                       # the lone member fell, group pruned
    assert campaign.resolve_road_ambush(guild, g, order) == []   # no-op, nothing left to resume


def test_fleeing_a_guard_catch_back_onto_an_unsafe_node_can_ambush():
    """A guard catch's RUN falls back to `order.prev_node` -- if that node
    happens to be unsafe (the Old Road, say), it gets the same arrival check
    as any other, not a free pass. Regression: this used to skip straight to
    a re-catch-or-idle check that never looked at `unsafe` at all."""
    from tests.helpers import fixed_d20
    from gartok import justice

    random.seed(1)
    culprit = Unit("player")
    culprit.crime = 5
    g = Group([culprit], node="road")
    guild = Guild(None, groups=[g])
    g.order = orders.travel(g, "city")           # road -> city: caught on arrival
    with fixed_d20(20):
        result = campaign.advance(guild)
    order = next(o for grp, o in result.pending if grp is g)
    assert order.kind == "guard" and order.prev_node == "road"

    orig = _forced_chance(1.0)
    try:
        with fixed_d20(1):                       # the guard test itself misses this time
            events, pause = campaign.resolve_guard_flee(guild, g, order)
    finally:
        world.ROAD_AMBUSH_CHANCE = orig

    assert g.node == "road" and g.order is None
    assert pause is not None and pause.kind == "ambush" and len(pause.pack) > 0


def test_app_starts_the_ambush_battle_with_the_whole_group_then_resolves_it():
    random.seed(1)
    orig = _forced_chance(1.0)
    try:
        a, b = Unit("player"), Unit("player")
        g = Group([a, b], node="city")
        guild = Guild(None, groups=[g])
        app = _app(guild)
        g.order = orders.travel(g, "road")
        app._advance()
    finally:
        world.ROAD_AMBUSH_CHANCE = orig

    assert app._pause_order is not None and app._pause_group is g
    battle = app.scene.battle
    assert [u for u in battle.player_units] and battle.player_units[0].team == "player"
    assert len(battle.enemy_units) == len(app._pause_order.pack)

    battle.winner = "player"
    battle.round_no = 1
    for c in battle.player_units:
        c.status = "up"
    app._battle_squad = [a, b]
    app._battle_node = world.node("road")
    app._battle_end(battle)

    assert app._pause_order is None and app._pause_group is None
    assert g.order.kind == "idle"
