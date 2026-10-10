"""Vocations: the founding trade, its six races and its perk (vocations.py)."""

import os
import random
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from gartok import (
    campaign,
    cohesion,
    data,
    hunt,
    items,
    orders,
    persist,
    vocations,
    world,
)
from gartok.clock import Clock
from gartok.draft_screen import DraftScreen
from gartok.group import BASE_CAPACITY, CAUTIOUS, NORMAL, Group
from gartok.guild import Guild
from gartok.map_screen import MapScreen
from gartok.tutorial import TutorialState
from gartok.ui.tokens import fonts as ui_fonts
from gartok.unit import Unit
from gartok.vocation_screen import VocationScreen

SIZE = (1280, 800)


def _guild(vocation=None, n=1, **kw):
    units = [Unit("player") for _ in range(n)]
    return Guild(units, node="city", vocation=vocation, **kw)


# ---- the registry -------------------------------------------------------- #

def test_six_vocations_of_six_playable_races_each():
    assert list(vocations.VOCATIONS) == ["warband", "delvers", "wilds", "scholars", "caravan", "marsh"]
    for v in vocations.VOCATIONS.values():
        assert len(v.races) == 6 and len(set(v.races)) == 6
        assert set(v.races) <= set(data.RACE_NAMES)


def test_every_playable_race_belongs_to_a_vocation():
    covered = {r for v in vocations.VOCATIONS.values() for r in v.races}
    assert covered == set(data.RACE_NAMES)


def test_only_scholars_is_dormant():
    assert [v.id for v in vocations.VOCATIONS.values() if not v.active] == ["scholars"]


# ---- the draft pool ------------------------------------------------------ #

def test_the_pool_holds_one_of_each_race_of_the_vocation_and_three_more():
    for vid, voc in vocations.VOCATIONS.items():
        ds = DraftScreen(ui_fonts(), lambda *a: None, vocation=vid)
        names = [u.race["name"] for u in ds.pool]
        assert len(ds.pool) == 9
        for race in voc.races:
            assert race in names


def test_a_draft_without_a_vocation_is_the_plain_natural_pool():
    ds = DraftScreen(ui_fonts(), lambda *a: None)
    assert len(ds.pool) == 9 and ds.vocation is None


def test_a_commission_replaces_the_card_from_the_natural_table():
    ds = DraftScreen(ui_fonts(), lambda *a: None, vocation="marsh")
    ds.pending_labels = ["STRONG"]
    target = ds.pool[0]
    ds._replace(target)
    assert target not in ds.pool and len(ds.pool) == 9
    assert ds.pool[0].mod_strength >= 2


def test_the_draft_hands_the_vocation_to_on_done():
    pygame.init()
    got = {}
    ds = DraftScreen(ui_fonts(), lambda *a: got.update(args=a), vocation="caravan")
    surf = pygame.Surface(SIZE)
    ds.draw(surf)
    for rect, _u in ds.card_rects[:3]:
        ds._click(rect.center)
    ds.draw(surf)
    ds._click(ds.continue_rect.center)
    ds.draw(surf)
    ds.leader_pick = ds.picks[0]
    ds._click(ds.continue_rect.center)
    assert got["args"][-1] == "caravan"


# ---- the picker screen --------------------------------------------------- #

def test_the_vocation_screen_needs_a_pick_before_it_goes_on():
    pygame.init()
    chosen = []
    vs = VocationScreen(ui_fonts(), chosen.append)
    surf = pygame.Surface(SIZE)
    vs.draw(surf)
    vs._click(vs.continue_rect.center)
    assert chosen == []
    assert len(vs.card_rects) == 6
    rect, vid = vs.card_rects[2]
    vs._click(rect.center)
    vs.draw(surf)
    assert vs.selected == vid == "wilds"
    vs._click(vs.continue_rect.center)
    assert chosen == ["wilds"]


def test_a_new_game_opens_the_vocation_screen_then_the_draft_with_that_pool():
    from tests.helpers import make_app
    app = make_app(None)
    app.ui_fonts = ui_fonts()
    app._new_game()
    assert isinstance(app.scene, VocationScreen)
    app.scene.on_done("scholars")
    assert isinstance(app.scene, DraftScreen) and app.scene.vocation == "scholars"


def test_the_founded_guild_keeps_the_vocation():
    from tests.helpers import make_app
    app = make_app(None)
    app.ui_fonts = ui_fonts()
    app._draft_tutorial = TutorialState()
    app._start_map = lambda: None
    app._record_play = lambda: None
    units = [Unit("player") for _ in range(3)]
    app._draft_done(units, units[0], "Crew", (1, 2, 3), "shield-bash", "delvers")
    assert app.guild.vocation == "delvers"


def test_the_guild_tab_shows_the_vocation_and_flags_a_dormant_one():
    from gartok.guild_screen import GuildScreen
    pygame.init()
    for vid, dormant in (("marsh", False), ("scholars", True), (None, False)):
        guild = _guild(vid)
        gs = GuildScreen(ui_fonts(), guild, lambda: None)
        v = gs._vocation()
        if vid is None:
            assert v is None
        else:
            assert v["name"] == vocations.get(vid).name and v["dormant"] is dormant
        gs.tab = "guild"
        gs.draw(pygame.Surface(SIZE))


# ---- the perks ----------------------------------------------------------- #

def test_no_vocation_changes_nothing():
    g = _guild()
    assert vocations.cohesion_bonus(g) == 0 and vocations.gather_mult(g) == 1.0
    assert vocations.travel_mult(g) == 1.0 and not vocations.food_pauses(g)
    assert vocations.ambush_mult(g, CAUTIOUS) == 1.0


def test_warband_adds_one_to_the_cohesion_roll_only():
    members = [Unit("player") for _ in range(BASE_CAPACITY + 2)]
    for u in members:
        u.set_base_attribute("charisma", 10)
        u._racial_override = 0                    # capacity is exactly BASE_CAPACITY
    for vid, walks in ((None, True), ("warband", False)):
        guild = Guild(None, groups=[Group(members, node="city", leader=members[0])], vocation=vid)
        group = guild.groups[0]
        assert group.overextension
        roll = cohesion.weakest(guild, group).mental_defense    # a walk-out only without the bonus
        events = cohesion._roll_groups(guild, lambda roll=roll: roll)
        assert bool(events) is walks
        members[:] = [u for g in guild.groups for u in g.members]
        assert len(members) == BASE_CAPACITY + 2


def test_delvers_gather_fifteen_percent_more_from_a_work_shift_on_average():
    u = Unit("player")
    u._base_inventory = []
    u.set_base_attribute("charisma", 10)
    u.talents["racial"] = []
    plain = Guild([u], clock=Clock(6 * 3600))
    plain._pay_shift([u], 16, 16, "lumber_yard")
    base = u.money
    assert base > 0
    delvers = Guild([u], clock=Clock(6 * 3600), vocation="delvers")
    rng = random.Random(5)
    total = sum(vocations.gather_pay(delvers, base, rng) for _ in range(4000))
    assert abs(total / 4000 / base - 1.15) < 0.02
    assert vocations.gather_pay(plain, base) == base


def test_the_leftover_fraction_of_a_coin_is_paid_by_chance():
    delvers = _guild("delvers")

    class Roll:
        def __init__(self, value):
            self.value = value

        def random(self):
            return self.value

    assert vocations.gather_pay(delvers, 4, Roll(0.0)) == 5      # 0.6 of a coin left over
    assert vocations.gather_pay(delvers, 4, Roll(0.9)) == 4
    assert vocations.gather_pay(delvers, 20, Roll(0.9)) == 23     # 3 whole coins, no leftover


def test_delvers_gather_more_meat_and_forage_on_a_hunt():
    class Always:
        def random(self):
            return 1.0

    base = hunt.HuntState([Unit("player")] * 3, None, hours_left=16)
    boosted = hunt.HuntState([Unit("player")] * 3, None, hours_left=16,
                             yield_mult=vocations.gather_mult(_guild("delvers")))
    hunt.hunt_stretch(base, Always())
    hunt.hunt_stretch(boosted, Always())
    assert boosted.meat > base.meat
    assert boosted.yield_hours == base.yield_hours * 1.15


def test_the_hunt_the_app_starts_carries_the_vocation_and_the_group_stance():
    from tests.helpers import make_app
    guild = _guild("wilds")
    group = guild.groups[0]
    group.stance = CAUTIOUS
    app = make_app(guild)
    app._leave_outside = lambda *a: None
    app._hunt_screen = lambda phase: None
    app._begin_hunt(list(group.members), world.node("wilds"), group, True)
    assert app._hunt.ambush_mult == vocations.CAUTIOUS_AMBUSH
    group.stance = NORMAL
    app._begin_hunt(list(group.members), world.node("wilds"), group, True)
    assert app._hunt.ambush_mult == 1.0


def test_caravan_travels_fifteen_percent_faster():
    walker = Unit("player")
    slow, fast = Guild([walker], node="city"), Guild([walker], node="city", vocation="caravan")
    a = orders.travel(slow.groups[0], "market", vocations.travel_mult(slow))
    b = orders.travel(fast.groups[0], "market", vocations.travel_mult(fast))
    assert b.eta == a.eta * vocations.TRAVEL_FACTOR and b.eta < a.eta


def test_caravan_keeps_the_pace_on_every_leg_of_a_route():
    legs = {}
    walker = Unit("player")
    for vid in (None, "caravan"):
        guild = Guild([walker], node="city", vocation=vid)
        group = guild.groups[0]
        group.order = orders.travel(group, "mine", vocations.travel_mult(guild))
        etas = [group.order.eta]
        with patch("gartok.campaign._arrival_pause", return_value=None):
            while group.order is not None and group.order.kind == "travel":
                campaign.advance(guild, dt=group.order.remaining)
                if group.order is not None and group.order.kind == "travel":
                    etas.append(group.order.eta)
        legs[vid] = etas
    assert len(legs[None]) == len(legs["caravan"]) == 2
    for plain, fast in zip(legs[None], legs["caravan"]):
        assert abs(fast - plain * vocations.TRAVEL_FACTOR) < 1e-9


def test_the_map_pace_shows_the_caravan_discount():
    guild = _guild("caravan")
    ms = MapScreen(ui_fonts(), guild, lambda: None, lambda: None, lambda: None, lambda g: None)
    g = guild.groups[0]
    assert ms._group_dict(g)["pace"] == world.hours(1, g.speed) * vocations.TRAVEL_FACTOR


def test_marsh_food_does_not_age_on_every_tenth_day():
    for day, ages in ((9, True), (10, False), (11, True), (20, False)):
        u = Unit("player")
        stack = items.create_instance("Potato", qty=9)
        stack.days_old = 0
        u._base_inventory = [stack]
        guild = Guild([u], clock=Clock((day - 1) * 86400), vocation="marsh")
        assert vocations.food_pauses(guild) is (not ages)
        guild._daily_upkeep()
        assert (stack.days_old == 1) is ages


def test_other_guilds_age_their_food_on_the_tenth_day():
    u = Unit("player")
    stack = items.create_instance("Potato", qty=9)
    stack.days_old = 0
    u._base_inventory = [stack]
    Guild([u], clock=Clock(9 * 86400))._daily_upkeep()
    assert stack.days_old == 1


# ---- the travel stance --------------------------------------------------- #

def test_cautious_alone_is_a_multiplier_of_one_and_the_perks_multiply():
    plain, wilds = _guild(), _guild("wilds")
    assert vocations.ambush_mult(plain, NORMAL, scout=True) == 1.0
    assert vocations.ambush_mult(plain, CAUTIOUS) == 1.0
    assert vocations.ambush_mult(plain, CAUTIOUS, scout=True) == 0.9
    assert vocations.ambush_mult(wilds, NORMAL) == 1.0
    assert vocations.ambush_mult(wilds, CAUTIOUS) == 0.8
    assert abs(vocations.ambush_mult(wilds, CAUTIOUS, scout=True) - 0.72) < 1e-9
    assert abs(world.ROAD_AMBUSH_CHANCE * 0.72 - 0.144) < 1e-9


def test_a_cautious_wilds_group_dodges_a_road_ambush_a_normal_one_walks_into():
    guild = _guild("wilds")
    group = guild.groups[0]
    group.node = "road"
    roll = world.ROAD_AMBUSH_CHANCE * 0.9               # under 0.2, over 0.16
    with patch("gartok.campaign.random.random", return_value=roll), \
            patch("gartok.campaign.encounters.roll_encounter", return_value=["Goblin"]):
        group.stance = NORMAL
        assert campaign._road_ambush_catch(guild, group, ["road"]) is not None
        group.stance = CAUTIOUS
        assert campaign._road_ambush_catch(guild, group, ["road"]) is None


def test_the_stance_does_not_touch_the_guards_or_the_claim_raids():
    guild = _guild("wilds")
    group = guild.groups[0]
    group.stance = CAUTIOUS
    guild.house.squatting = True
    group.node = "city"
    with patch("gartok.campaign.random.random", return_value=campaign.CITY_RAID_CHANCE - 0.001):
        order = campaign._property_raid_catch(guild, group, [])
    assert order is not None and order.kind == "eviction"


def test_the_map_button_flips_the_selected_groups_stance():
    guild = _guild()
    ms = MapScreen(ui_fonts(), guild, lambda: None, lambda: None, lambda: None, lambda g: None)
    group = guild.groups[0]
    ms.selected = group
    assert group.stance == NORMAL
    keys = [b.get("key") for b in ms._inspector_bottom(group)]
    assert "stance" in keys
    ms._handle_button("stance")
    assert group.stance == CAUTIOUS
    ms._handle_button("stance")
    assert group.stance == NORMAL


def test_a_busy_group_has_no_stance_button():
    guild = _guild()
    group = guild.groups[0]
    group.order = orders.rest(4)
    ms = MapScreen(ui_fonts(), guild, lambda: None, lambda: None, lambda: None, lambda g: None)
    assert "stance" not in [b.get("key") for b in ms._inspector_bottom(group)]


def test_the_hunt_screen_notes_a_changed_ambush_chance():
    from gartok.hunt_screen import HuntScreen
    pygame.init()
    guild = _guild("wilds", n=3)
    state = hunt.HuntState(list(guild.roster), world.node("wilds"), hours_left=0, ambush_mult=0.8)
    hs = HuntScreen(ui_fonts(), guild, state, phase="setup", on_ambush=lambda p: None,
                    on_done=lambda: None)
    hs.draw(pygame.Surface(SIZE))


# ---- the save ------------------------------------------------------------ #

def test_the_vocation_and_the_stance_survive_a_save():
    random.seed(3)
    guild = _guild("marsh", n=2)
    guild.groups[0].stance = CAUTIOUS
    world_id = persist.new_world_id()
    try:
        persist.save_game(world_id, guild)
        back = persist.load_game(world_id)
        assert back.vocation == "marsh" and back.groups[0].stance == CAUTIOUS
    finally:
        persist.delete_world(world_id)


def test_a_save_without_the_new_fields_loads_as_no_vocation_and_normal():
    random.seed(4)
    guild = _guild(n=1)
    payload = persist._payload(guild, "current", "")
    payload.pop("vocation")
    for g in payload["groups"]:
        g.pop("stance")
    world_id = persist.new_world_id()
    try:
        os.makedirs(persist.world_dir(world_id), exist_ok=True)
        import json
        with open(persist.save_path(world_id, persist.CURRENT), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        back = persist.load_game(world_id)
        assert back.vocation is None and back.groups[0].stance == NORMAL
    finally:
        persist.delete_world(world_id)
