"""Vocations: the founding trade, its six races and its perk (vocations.py)."""

import os
import random
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


from gartok import (
    campaign,
    cohesion,
    data,
    forced,
    hunt,
    items,
    morale,
    orders,
    persist,
    vocations,
    world,
)
from gartok.clock import Clock
from gartok.draft import Draft
from gartok.group import BASE_CAPACITY, CAUTIOUS, NORMAL, Group
from gartok.guild import Guild
from gartok.unit import Unit
from tests.helpers import standard_unit


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


def test_no_vocation_is_dormant_now_that_the_info_modal_exists():
    assert all(v.active for v in vocations.VOCATIONS.values())


def test_only_the_scholars_add_to_the_info_roll():
    assert vocations.info_bonus(_guild("scholars")) == vocations.INFO_BONUS > 0
    assert vocations.info_bonus(_guild("marsh")) == vocations.info_bonus(_guild(None)) == 0


# ---- the draft pool ------------------------------------------------------ #

def test_the_pool_holds_one_of_each_race_of_the_vocation_and_three_more():
    for vid, voc in vocations.VOCATIONS.items():
        ds = Draft(vid)
        names = [u.race["name"] for u in ds.pool]
        assert len(ds.pool) == 9
        for race in voc.races:
            assert race in names


def test_a_draft_without_a_vocation_is_the_plain_natural_pool():
    ds = Draft()
    assert len(ds.pool) == 9 and ds.vocation is None


def test_a_commission_replaces_the_card_from_the_natural_table():
    ds = Draft("marsh")
    ds.pending_labels = ["STRONG"]
    target = ds.pool[0]
    ds.replace(target)
    assert target not in ds.pool and len(ds.pool) == 9
    assert ds.pool[0].mod_strength >= 2


# ---- the picker screen --------------------------------------------------- #


def test_the_charter_shows_the_vocation_and_carries_its_dormant_flag():
    from gartok.guild_sheet import GuildSheet
    for vid, dormant in (("marsh", False), ("scholars", False), (None, False)):
        v = GuildSheet(_guild(vid))._vocation()
        if vid is None:
            assert v is None
        else:
            assert v["name"] == vocations.get(vid).name and v["dormant"] is dormant


# ---- the perks ----------------------------------------------------------- #

def test_no_vocation_changes_nothing():
    g = _guild()
    u = g.roster[0]
    assert vocations.morale_bonus(u) == 0 and vocations.hunger_relief(u) == 0
    assert vocations.gather_mult(g) == 1.0 and vocations.travel_mult(g) == 1.0
    assert vocations.ambush_mult(g, CAUTIOUS) == 1.0


def test_warband_adds_one_to_every_members_starting_morale():
    u = standard_unit()
    base = morale.start_value(u)
    Guild([u], clock=Clock(0), vocation="warband")
    assert u.vocation == "warband" and morale.start_value(u) == base + 1
    Guild([u], clock=Clock(0), vocation="delvers")
    assert morale.start_value(u) == base


def test_warband_no_longer_touches_the_cohesion_roll():
    members = [Unit("player") for _ in range(BASE_CAPACITY + 2)]
    for u in members:
        u.set_base_attribute("charisma", 10)
        u._racial_override = 0                    # capacity is exactly BASE_CAPACITY
    guild = Guild(None, groups=[Group(members, node="city", leader=members[0])], vocation="warband")
    group = guild.groups[0]
    roll = cohesion.weakest(guild, group).mental_defense
    assert cohesion._roll_groups(guild, lambda roll=roll: roll)


def test_a_recruit_joining_later_is_stamped_with_the_vocation():
    guild = _guild("warband")
    late = Unit("player")
    guild.add_member(late, guild.groups[0])
    assert late.vocation == "warband"


def test_delvers_work_shifts_pay_the_same_as_any_guild():
    pay = {}
    for vid in (None, "delvers"):
        u = standard_unit()
        u._base_inventory = []
        Guild([u], clock=Clock(6 * 3600), vocation=vid)._pay_shift([u], 16, 16, "lumber_yard")
        pay[vid] = u.money
    assert pay["delvers"] == pay[None] > 0


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
        with patch("gartok.forced.arrival_pause", return_value=None):
            while group.order is not None and group.order.kind == "travel":
                campaign.advance(guild, dt=group.order.remaining)
                if group.order is not None and group.order.kind == "travel":
                    etas.append(group.order.eta)
        legs[vid] = etas
    assert len(legs[None]) == len(legs["caravan"]) == 2
    for plain, fast in zip(legs[None], legs["caravan"]):
        assert abs(fast - plain * vocations.TRAVEL_FACTOR) < 1e-9


def test_marsh_softens_the_hunger_penalty_of_the_first_two_days_only():
    penalties = {}
    for vid in (None, "marsh"):
        u = standard_unit()
        Guild([u], clock=Clock(0), vocation=vid)
        row = []
        for days in range(5):
            u.unfed_days = days
            row.append(u.hunger_attribute_penalty)
        penalties[vid] = row
    assert penalties[None] == [0, -2, -4, -4, -4]
    assert penalties["marsh"] == [0, 0, -2, -4, -4]


def test_marsh_starving_member_still_has_one_hit_point():
    u = standard_unit()
    Guild([u], clock=Clock(0), vocation="marsh")
    u.unfed_days = 2
    u._derive_combat()
    assert u.hunger_level == 2 and u.hp_max == 1


def test_food_ages_on_every_day_for_every_vocation():
    for vid in (None, "marsh"):
        u = Unit("player")
        stack = items.create_instance("Potato", qty=9)
        stack.days_old = 0
        u._base_inventory = [stack]
        Guild([u], clock=Clock(9 * 86400), vocation=vid)._daily_upkeep()
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
    with patch("gartok.forced.random.random", return_value=roll), \
            patch("gartok.forced.encounters.roll_encounter", return_value=[standard_unit("enemy")] * 4):
        group.stance = NORMAL
        assert forced.road_ambush_catch(guild, group, None, ["road"]) is not None
        group.stance = CAUTIOUS
        assert forced.road_ambush_catch(guild, group, None, ["road"]) is None


def test_the_stance_does_not_touch_the_guards_or_the_claim_raids():
    guild = _guild("wilds")
    group = guild.groups[0]
    group.stance = CAUTIOUS
    guild.house.squatting = True
    group.node = "city"
    with patch("gartok.forced.random.random", return_value=forced.CITY_RAID_CHANCE - 0.001):
        order = forced.property_raid_catch(guild, group, None, [])
    assert order is not None and order.kind == "eviction"


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


def test_every_vocation_has_a_motto():
    assert all(v.motto for v in vocations.VOCATIONS.values())
