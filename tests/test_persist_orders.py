"""Orders survive a save: what a group is doing (`Group.order`) and the forced
fight that came due and awaits its click (`Group.pending`, enemy pack included).
A group with a fight pending is locked -- the squad must stay as it is -- and
neither a battle nor a hunt is ever saved."""

import random
from types import SimpleNamespace

import pytest

from gartok import campaign, economy, encounters, orders, persist, world
from gartok.group import Group
from gartok.guild import Guild
from tests.helpers import Unit, fixed_d20, make_app


def _reload(group):
    return persist.group_from_dict(persist.group_to_dict(group))


def _fields(order):
    d = persist.order_to_dict(order)
    d.pop("pack")
    return d


def _ambushed(node="city", dest="road", members=1):
    """A group the road just ambushed: `campaign.advance` leaves it idle with the fight in `pending`."""
    random.seed(1)
    orig = world.ROAD_AMBUSH_CHANCE
    world.ROAD_AMBUSH_CHANCE = 1.0
    try:
        g = Group([Unit("player") for _ in range(members)], node=node)
        guild = Guild(None, groups=[g])
        g.order = orders.travel(g, dest)
        campaign.advance(guild)
    finally:
        world.ROAD_AMBUSH_CHANCE = orig
    assert g.pending is not None and g.pending.kind == "ambush"
    return guild, g


# --------------------------------------------------------------------------- #
# the order itself                                                            #
# --------------------------------------------------------------------------- #

def test_a_multi_leg_travel_order_round_trips_with_its_waypoints():
    g = Group([Unit("player")], node="tavern")
    g.order = orders.travel(g, "wilds")
    g.order.remaining -= 0.5

    loaded = _reload(g)

    assert _fields(loaded.order) == _fields(g.order)
    assert isinstance(loaded.order.path, tuple) and loaded.order.path == g.order.path
    assert loaded.order.final_dest == "wilds"


@pytest.mark.parametrize("make", [
    lambda g: orders.rest(8),
    lambda g: orders.garrison("lumber"),
    lambda g: orders.interactive("market"),
    lambda g: orders.idle(),
])
def test_every_kind_of_standing_order_round_trips(make):
    g = Group([Unit("player")], node="city")
    g.order = make(g)

    loaded = _reload(g)

    assert _fields(loaded.order) == _fields(g.order)
    assert loaded.pending is None


def test_a_rest_in_flight_survives_next_to_an_idle_group():
    resting, idle = Group([Unit("player")], node="city"), Group([Unit("player")], node="market")
    resting.order = orders.rest(8)
    resting.order.remaining = 3

    loaded = [_reload(g) for g in (resting, idle)]

    assert loaded[0].order.kind == "rest" and loaded[0].order.remaining == 3
    assert loaded[0].busy
    assert loaded[1].order is None and not loaded[1].busy


def test_a_save_from_before_orders_loads_every_group_idle():
    g = Group([Unit("player")], node="city")
    g.order = orders.rest(8)
    d = persist.group_to_dict(g)
    del d["order"], d["pending"]

    loaded = persist.group_from_dict(d)

    assert loaded.order is None and loaded.pending is None


def test_a_pending_fight_round_trips_with_the_same_enemy_pack():
    pack = tuple(encounters.build_enemy(2) for _ in range(3))
    g = Group([Unit("player")], node="road")
    g.pending = orders.Order("ambush", pack=pack, resume_path=("wilds",))

    loaded = _reload(g)

    assert loaded.order is None
    assert loaded.pending.kind == "ambush" and loaded.pending.resume_path == ("wilds",)
    assert [(u.name, u.hp_max, u.combat_level, u.alignment) for u in loaded.pending.pack] == \
           [(u.name, u.hp_max, u.combat_level, u.alignment) for u in pack]
    assert all(isinstance(u, Unit) for u in loaded.pending.pack)


def test_a_pending_guard_catch_keeps_who_was_caught():
    culprit = Unit("player")
    g = Group([culprit, Unit("player")], node="city")
    g.pending = orders.Order("guard", caught=(culprit.uid,), prev_node="road")

    loaded = _reload(g)

    assert loaded.pending.caught == (culprit.uid,) and loaded.pending.prev_node == "road"


def test_a_pending_fight_survives_the_save_file_and_a_wilds_raid_job_with_it():
    g = Group([Unit("player")], node="wilds")
    g.pending = orders.Order("wilds_raid", job="lumber",
                             pack=tuple(encounters.build_enemy(economy.WILDS_RAID_LEVEL) for _ in range(2)))
    guild = Guild(None, groups=[g])
    world_id = persist.new_world_id()

    persist.save_game(world_id, guild)
    loaded = persist.load_game(world_id).groups[0]

    assert loaded.pending.kind == "wilds_raid" and loaded.pending.job == "lumber"
    assert len(loaded.pending.pack) == 2


# --------------------------------------------------------------------------- #
# a fight pending locks the group                                             #
# --------------------------------------------------------------------------- #

def test_advance_parks_a_forced_order_on_the_group_and_locks_it():
    _, g = _ambushed()

    assert g.order is None and not g.busy        # advance still sees an idle group
    assert g.locked


def test_an_interactive_arrival_is_not_parked():
    g = Group([Unit("player")], node="city")
    guild = Guild(None, groups=[g])
    g.order = orders.interactive("market")

    result = campaign.advance(guild)

    assert result.pending and g.pending is None and not g.locked


def test_an_ambushed_group_cannot_be_split_merged_or_given_a_new_leader():
    guild, g = _ambushed(members=3)
    mate = Group([Unit("player")], node=g.node)
    guild.groups.append(mate)
    guild.reputation = {"x": 99}                 # plenty of group slots

    with pytest.raises(ValueError):
        guild.split_group(g, [g.members[0]])
    with pytest.raises(ValueError):
        guild.merge_groups(g, mate)
    with pytest.raises(ValueError):
        guild.merge_groups(mate, g)
    with pytest.raises(ValueError):
        guild.set_group_leader(g, g.members[1])


def test_the_cohesion_sweep_does_not_peel_anyone_off_an_ambushed_group():
    from gartok import cohesion
    from gartok.group import BASE_CAPACITY

    members = [Unit("player") for _ in range(BASE_CAPACITY + 3)]
    for u in members:
        u.set_base_attribute("charisma", 6)
    g = Group(members, node="city")
    guild = Guild(None, groups=[g])
    guild.reputation = {"arena": 99}
    assert g.overextension > 0
    g.pending = orders.Order("ambush", pack=(encounters.build_enemy(1),))

    assert cohesion.daily(guild, lambda: 20) == []
    assert len(g.members) == len(members) and len(guild.groups) == 1


def test_resolving_the_ambush_unlocks_the_group():
    guild, g = _ambushed()
    order = g.pending

    campaign.resolve_road_ambush(guild, g, order)

    assert g.pending is None and not g.locked


def test_a_guard_prison_choice_clears_the_pending_order():
    culprit = Unit("player")
    culprit.crime = 5
    g = Group([culprit], node="road")
    guild = Guild(None, groups=[g])
    g.order = orders.travel(g, "city")
    with fixed_d20(20):
        result = campaign.advance(guild)
    order = next(o for grp, o in result.pending if grp is g)
    assert g.pending is order and g.locked

    campaign.resolve_guard_prison(guild, g, order)
    assert g.pending is None


def test_fleeing_into_a_second_ambush_parks_the_new_one():
    culprit = Unit("player")
    culprit.crime = 5
    g = Group([culprit], node="road")
    guild = Guild(None, groups=[g])
    g.order = orders.travel(g, "city")
    with fixed_d20(20):
        result = campaign.advance(guild)
    guard = next(o for grp, o in result.pending if grp is g)

    orig = world.ROAD_AMBUSH_CHANCE
    world.ROAD_AMBUSH_CHANCE = 1.0
    try:
        with fixed_d20(1):
            _, pause = campaign.resolve_guard_flee(guild, g, guard)
    finally:
        world.ROAD_AMBUSH_CHANCE = orig

    assert pause.kind == "ambush" and g.pending is pause


def test_a_wilds_raid_on_a_garrison_is_parked_too():
    g = Group([Unit("player")], node=world.WILDS_TERRITORY_NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_stage = "SUSTAINING"
    g.order = orders.garrison("lumber")
    orig = economy.WILDS_RAID_CHANCE
    economy.WILDS_RAID_CHANCE = 1.0
    try:
        campaign.advance(guild, dt=1)
    finally:
        economy.WILDS_RAID_CHANCE = orig

    assert g.pending is not None and g.pending.kind == "wilds_raid" and g.pending.job == "lumber"
    assert g.locked

    campaign.resolve_wilds_raid(guild, g, g.pending, SimpleNamespace(won=True))
    assert g.pending is None and g.order.kind == "garrison"


# --------------------------------------------------------------------------- #
# the app: loading picks the fight back up, nothing mid-battle is saved       #
# --------------------------------------------------------------------------- #

def test_loading_a_save_with_an_ambush_pending_lands_on_the_map_with_the_cta():
    guild, _ = _ambushed()
    world_id = persist.new_world_id()
    persist.save_game(world_id, guild)
    app = make_app(persist.load_game(world_id))

    app._resume_pending()

    assert app.scene.__class__.__name__ == "MapScreen"
    loaded = app.guild.groups[0]
    assert app._pending_event == (loaded, loaded.pending)
    assert loaded.locked and loaded.pending.kind == "ambush"


def test_loading_a_save_with_a_guard_pending_reopens_the_guard_screen():
    culprit = Unit("player")
    culprit.crime = 5
    g = Group([culprit], node="city")
    g.pending = orders.Order("guard", caught=(culprit.uid,), prev_node="road")
    app = make_app(Guild(None, groups=[g]))

    app._resume_pending()

    assert app.scene.__class__.__name__ == "GuardScreen"


def test_loading_a_save_with_nothing_pending_just_lands_on_the_map():
    g = Group([Unit("player")], node="city")
    g.order = orders.rest(8)
    app = make_app(Guild(None, groups=[g]))

    app._resume_pending()

    assert app.scene.__class__.__name__ == "MapScreen" and app._pending_event is None


def test_the_fight_is_no_longer_pending_once_the_battle_is_over():
    """Death alerts play before the aftermath is resolved -- a save taken there
    must not replay a fight that already happened."""
    guild, g = _ambushed(members=2)
    app = make_app(guild)
    app._pending_event = (g, g.pending)
    app._resolve_pending_event()
    battle = app.scene.battle
    battle.winner = "player"
    battle.round_no = 1
    for c in battle.player_units:
        c.status = "up"
    battle.player_units[1].status = "dead"
    app._battle_squad = list(g.members)
    app._battle_node = world.node("road")

    app._battle_end(battle)

    assert app.scene.__class__.__name__ == "AlertScreen"
    assert g.pending is None


def test_no_save_is_allowed_in_a_battle_or_a_hunt_but_is_on_the_map():
    guild, g = _ambushed()
    app = make_app(guild)
    app._start_map()
    assert app._can_save()

    app._pending_event = (g, g.pending)
    app._resolve_pending_event()
    assert app.scene.__class__.__name__ == "BattleScreen" and not app._can_save()

    app._hunt = object()
    app.scene = None
    assert not app._can_save()


def test_leaving_to_the_menu_mid_battle_writes_nothing():
    guild, g = _ambushed()
    app = make_app(guild)
    saves = []
    app._save = lambda: saves.append(1)
    app._start_menu = lambda: None
    app._pending_event = (g, g.pending)
    app._resolve_pending_event()

    app._pause_to_menu()
    assert saves == []

    app.scene = None
    app._pause_to_menu()
    assert saves == [1]


# --------------------------------------------------------------------------- #
# the kit is frozen while a fight is due                                      #
# --------------------------------------------------------------------------- #

def _draw_guild_screen(guild, member):
    from unittest.mock import MagicMock

    import pygame

    from gartok.guild_screen import GuildScreen

    pygame.font.init()
    gs = GuildScreen(MagicMock(), guild, on_back=lambda: None, on_manage=lambda g: None)
    gs.member = member
    gs.draw(pygame.Surface((1920, 1080)))
    return {key for key, _ in gs.buttons}


def test_the_guild_screen_freezes_gear_leader_and_load_for_a_group_with_a_fight_due():
    a, b = Unit("player"), Unit("player")
    g = Group([a, b], node="city", leader=a)
    guild = Guild(None, groups=[g])

    free = _draw_guild_screen(guild, b)
    assert {"manage", "distribute", "group_leader"} <= free

    g.pending = orders.Order("ambush", pack=(encounters.build_enemy(1),))
    frozen = _draw_guild_screen(guild, b)
    assert not {"manage", "distribute", "group_leader"} & frozen


def test_the_app_will_not_open_gear_or_group_screens_for_a_group_with_a_fight_due():
    guild, g = _ambushed()
    app = make_app(guild)
    app.scene = "untouched"

    app._open_gear(g)
    app._open_group(g)

    assert app.scene == "untouched"
