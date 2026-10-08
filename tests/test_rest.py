"""Rest as one group's order: it heals, leaves the other groups playable, and
the "until full" plan is what the clock then actually does."""

import random

import pytest

from gartok import campaign, orders, rest
from gartok.clock import Clock
from gartok.group import Group
from gartok.guild import Guild
from gartok.guild_upkeep import rest_heal
from tests.helpers import Unit, packed

FOUR_AM = 4 * 3600


def _hurt(missing=3, meals=0, food="Jerky"):
    random.seed(3)
    u = Unit("player")
    u.hp = u.hp_max - missing
    assert 0 < u.hp < u.hp_max
    u._base_inventory = packed([food] * meals) if meals else []
    u._derive_combat()
    return u


def _guild(*units, at=FOUR_AM):
    g = Group(list(units), node="market")
    return Guild(None, groups=[g], clock=Clock(at)), g


def _run_to_idle(guild, g):
    while g.busy:
        campaign.advance(guild)


def test_a_rest_order_heals_and_goes_idle_when_done():
    u = _hurt(1)
    guild, g = _guild(u)
    g.order = orders.rest(8)
    campaign.advance(guild)
    assert u.hp == u.hp_max and not g.busy
    assert guild.clock.hour_of_day == 12


def test_resting_leaves_the_other_groups_to_their_own_orders():
    a, b = _hurt(1), Unit("player")
    ga, gb = Group([a], node="market"), Group([b], node="market")
    guild = Guild(None, groups=[ga, gb], clock=Clock(FOUR_AM))
    ga.order = orders.rest(8)
    gb.order = orders.work(guild, gb, 4)
    campaign.advance(guild)
    assert not gb.busy and ga.busy and ga.order.remaining == pytest.approx(4)
    assert guild.clock.hour_of_day == 8
    campaign.advance(guild)
    assert not ga.busy and a.hp == a.hp_max


def test_a_group_on_another_order_does_not_rest():
    u = _hurt(1)
    guild, g = _guild(u)
    g.order = orders.Order("travel", eta=16, remaining=16, dest="road", path=())
    guild.pass_time(16)
    assert u.hp == u.hp_max - 1


def test_the_end_of_a_rest_feeds_only_its_own_hungry_group():
    random.seed(3)
    a, b = Unit("player"), Unit("player")
    for u in (a, b):
        u.unfed_days = 1
        u._base_inventory = packed(["Meat"])
        u._derive_combat()
    ga, gb = Group([a], node="market"), Group([b], node="market")
    guild = Guild(None, groups=[ga, gb], clock=Clock(FOUR_AM))
    ga.order = orders.rest(1)
    campaign.advance(guild)
    assert a.unfed_days == 0 and b.unfed_days == 1


def test_a_stopped_rest_keeps_the_hours_already_spent():
    u = _hurt(3)
    guild, g = _guild(u)
    g.order = orders.rest(24)
    guild.pass_time(8)
    g.order.remaining -= 8
    g.order = orders.idle()
    assert u.hp == u.hp_max - 3 + rest_heal(u)


def test_fixed_rows_count_the_midnights_they_cross():
    u = _hurt()
    guild, _ = _guild(u, at=23 * 3600)
    assert rest.fixed(guild, 1).meals == 1          # 23:00 + 1 h reaches midnight
    assert rest.fixed(guild, 0.5).meals == 0
    guild.clock = Clock(8 * 3600)
    assert rest.fixed(guild, 8).meals == 0
    assert rest.fixed(guild, 16).meals == 1
    assert rest.fixed(guild, 40).meals == 2


# --------------------------------------------------------------------------- #
# until full                                                                  #
# --------------------------------------------------------------------------- #

def test_until_full_is_refused_with_a_reason():
    u = Unit("player")
    guild, g = _guild(u)
    assert rest.until_full(guild, g).reason == "nobody is hurt"

    u = _hurt()
    u.poisons = {"x": {"level": 1, "hours": 5, "dc": 10}}
    guild, g = _guild(u)
    assert "poisoned" in rest.until_full(guild, g).reason

    u = _hurt()
    u.unfed_days = 1
    guild, g = _guild(u)
    assert "hungry and has nothing to eat" in rest.until_full(guild, g).reason

    u = _hurt(meals=0)
    guild, g = _guild(u)
    assert "last day of rations" in rest.until_full(guild, g).reason


def test_until_full_with_plenty_of_food_runs_to_full_health():
    u = _hurt(missing=3, meals=20)
    guild, g = _guild(u)
    plan = rest.until_full(guild, g)
    assert plan.available and not plan.capped
    assert plan.hours == pytest.approx(8 * -(-3 // rest_heal(u)))


def test_the_floor_keeps_a_day_of_rations_and_names_who_is_still_hurt():
    u = _hurt(missing=8, meals=2)
    guild, g = _guild(u)
    plan = rest.until_full(guild, g)
    assert plan.capped and plan.worst[0] == u.name
    assert plan.worst[1] < plan.worst[2]
    guild_after, g_after = _guild(u)
    g_after.order = orders.rest(plan.hours)
    _run_to_idle(guild_after, g_after)
    assert u.rations >= 1                              # tomorrow's meal is still in the pack


def _plan_vs_actual(units, share=True):
    random.seed(11)
    guild, g = _guild(*units)
    for u in units:
        u.share_food = share
    plan = rest.until_full(guild, g)
    assert plan.available, plan.reason
    snapshot = guild.clock.seconds
    g.order = orders.rest(plan.hours)
    _run_to_idle(guild, g)
    assert guild.clock.seconds - snapshot == round(plan.hours * 3600)
    return plan, units


def test_the_plan_is_what_the_clock_then_does_when_health_is_the_limit():
    u = _hurt(missing=5, meals=12)
    plan, _ = _plan_vs_actual([u])
    assert not plan.capped and u.hp == u.hp_max
    assert plan.worst == (u.name, u.hp_max, u.hp_max)


def test_the_plan_is_what_the_clock_then_does_when_the_floor_is_the_limit():
    u = _hurt(missing=8, meals=2)
    plan, _ = _plan_vs_actual([u])
    assert plan.capped
    assert plan.worst == (u.name, u.hp, u.hp_max)
    assert u.hp < u.hp_max and u.rations == 1


def test_the_plan_for_two_members_follows_the_slowest_and_the_shared_larder():
    a, b = _hurt(missing=2, meals=1), _hurt(missing=6, meals=7)
    for u in (a, b):
        u.name = u.name + str(id(u))
    plan, _ = _plan_vs_actual([a, b])
    assert not plan.capped
    assert a.hp == a.hp_max and b.hp == b.hp_max
    assert a.unfed_days == 0 and b.unfed_days == 0


def test_without_sharing_a_member_with_no_ration_blocks_the_plan():
    a, b = _hurt(missing=2, meals=5), _hurt(missing=2, meals=0)
    guild, g = _guild(a, b)
    a.share_food = b.share_food = False
    assert "last day of rations" in rest.until_full(guild, g).reason


def test_meat_lasts_two_midnights_before_it_spoils():
    u = _hurt(missing=8, meals=6, food="Meat")
    guild, g = _guild(u)
    plan = rest.until_full(guild, g)
    assert plan.capped and 24 < plan.hours < 48


def test_food_that_will_have_rotted_by_tomorrow_does_not_count_toward_the_floor():
    u = _hurt(missing=8, meals=6, food="Fruit")      # Fruit spoils after 1 day
    guild, g = _guild(u)
    plan = rest.until_full(guild, g)
    assert plan.capped and plan.hours < 24
    g.order = orders.rest(plan.hours)
    _run_to_idle(guild, g)
    assert u.unfed_days == 0 and not u.sick


def test_format_hours():
    assert rest.format_hours(0.5) == "30 min"
    assert rest.format_hours(8) == "8 h"
    assert rest.format_hours(80) == "3 d 8 h"
    assert rest.format_hours(71.98) == "3 d"


# --------------------------------------------------------------------------- #
# the map's REST button                                                       #
# --------------------------------------------------------------------------- #

def _map(*groups):
    import os

    import pygame

    from gartok.map_screen import MapScreen
    from gartok.ui.tokens import fonts as ui_fonts
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((1, 1))
    guild = Guild(None, groups=list(groups), clock=Clock(FOUR_AM))
    calls = []
    ms = MapScreen(ui_fonts(), guild, lambda: None, lambda: None,
                   lambda dt=None: calls.append(dt), lambda grp: None)
    ms.selected = groups[0]
    return ms, calls


def _bottom(ms, g):
    return {b.get("key"): b for b in ms._inspector_bottom(g)}


def test_rest_opens_a_menu_of_1_h_8_h_and_until_full_each_with_its_cost():
    u = _hurt(missing=3, meals=6)
    g = Group([u], node="market")
    ms, _ = _map(g)
    assert "rest:8" not in _bottom(ms, g) and "rest_menu" in _bottom(ms, g)
    ms._handle_button("rest_menu")
    rows = _bottom(ms, g)
    assert rows["rest:1"]["label"].endswith("no meal")
    assert "8 h" in rows["rest:8"]["label"]
    full = rows["rest:full"]
    assert "UNTIL FULL" in full["label"] and "1 d" in full["label"] and full.get("enabled", True)
    assert u.name in full["sub"]
    ms._handle_button("rest_menu")
    assert "rest:8" not in _bottom(ms, g)


def test_until_full_shows_why_it_is_off():
    g = Group([Unit("player")], node="market")
    ms, _ = _map(g)
    ms._handle_button("rest_menu")
    row = _bottom(ms, g)["rest:full"]
    assert row["enabled"] is False and row["sub"] == "nobody is hurt"
    ms._handle_button("rest:full")
    assert not g.busy


def test_a_floor_limited_row_says_so():
    u = _hurt(missing=8, meals=2)
    g = Group([u], node="market")
    ms, _ = _map(g)
    ms._handle_button("rest_menu")
    assert _bottom(ms, g)["rest:full"]["label"].startswith("UNTIL RATIONS HIT THE FLOOR")


def test_picking_a_row_sits_the_group_down_to_eat_then_rests_and_runs_the_clock():
    u = _hurt(missing=3, meals=3)
    u.unfed_days = 1
    u._derive_combat()
    g = Group([u], node="market")
    ms, calls = _map(g)
    ms._handle_button("rest_menu")
    ms._handle_button("rest:8")
    assert g.order.kind == "rest" and g.order.hours == 8
    assert u.unfed_days == 0 and u.rations == 2
    assert calls == [None]                                   # nothing left idle: the clock chases it
    assert ms._rest_open is False


def test_resting_one_group_does_not_stop_the_map_for_the_idle_one():
    a, b = _hurt(), Unit("player")
    ga, gb = Group([a], node="market"), Group([b], node="market")
    ms, calls = _map(ga, gb)
    ms._handle_button("rest:8")
    assert ga.busy and not gb.busy and calls == []
    assert ms._is_idle(gb)


def test_a_resting_group_can_be_stopped_and_keeps_the_hours_it_rested():
    u = _hurt(missing=3)
    g = Group([u], node="market")
    ms, _ = _map(g)
    g.order = orders.rest(24)
    keys = [b.get("key") for b in ms._inspector_content(g, ms._here())]
    assert "stop_rest" in keys
    ms._handle_button("stop_rest")
    assert not g.busy


def test_rest_carries_the_hunger_highlight():
    u = _hurt(meals=2)
    u.unfed_days = 1
    g = Group([u], node="market")
    ms, _ = _map(g)
    assert _bottom(ms, g)["rest_menu"]["primary"] and not _bottom(ms, g)["rest_menu"]["danger"]
    u._base_inventory = []
    row = _bottom(ms, g)["rest_menu"]
    assert row["danger"] and not row["primary"]


def test_the_map_draws_with_the_rest_menu_open():
    import pygame
    u = _hurt(missing=3, meals=6)
    g = Group([u], node="market")
    ms, _ = _map(g)
    ms._handle_button("rest_menu")
    ms.mouse = (0, 0)
    ms.draw(pygame.Surface((1400, 900)))
