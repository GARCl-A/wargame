"""The Ogre's Wildfire (wildfire.py, missions.NATURE_WILDFIRE): the ethereal nodes, the burning and
spreading clock, the talk chain, the fights' aftermath, putting a fire out, the end of the event and
what it leaves on The Wilds."""

import random
from unittest.mock import patch

from gartok import campaign, dialogue, factions, hunt, missions, orders, wildfire, world
from gartok.clock import Clock
from gartok.guild import Guild
from gartok.map_screen import MapScreen, node_icon
from gartok.ui.tokens import fonts as ui_fonts

from tests.helpers import Unit, _FixedRNG

DAY = 24 * 3600


def _guild(node="nature_grove", n=2):
    random.seed(7)
    members = [Unit("player") for _ in range(n)]
    for u in members:
        u.give_to_pack("Meat", 30)
    guild = Guild(members, node=node, clock=Clock(10 * 3600))
    guild.missions.append(missions.Mission(missions.LIBRARY_ANCIENT_CODEX.id, members[0].uid, 0, None,
                                           state="done"))
    guild.reveal_node("nature_grove")
    return guild, members


def _started():
    guild, members = _guild()
    m = missions.accept(guild, members[0], missions.NATURE_WILDFIRE)
    return guild, members, m, guild.wildfire


def _days(guild, n):
    events = []
    for _ in range(n):
        e, _ = guild.pass_time(24)
        events += e
    return events


def _small(state):
    return [f for f in state.foci if not f.great]


# --- the ethereal nodes ------------------------------------------------------- #

def test_an_ethereal_node_joins_the_map_and_leaves_it_whole():
    v = world.VERSION
    world.add_node(world.Node("ghost", "Ghost", "town", (0.5, 0.5), "x"), [("wilds", 1)])
    assert world.exists("ghost") and world.is_ethereal("ghost") and world.VERSION > v
    assert world.route("road", "ghost") == (["road", "wilds", "ghost"], 7)
    world.remove_node("ghost")
    assert not world.exists("ghost")
    assert all("ghost" not in e[:2] for e in world.EDGES)
    assert all(v != "ghost" for v, _ in world.neighbors("wilds"))


def test_the_coven_offers_the_errand_once_the_sanctuaries_are_open():
    guild, _ = _guild()
    assert missions.NATURE_WILDFIRE in missions.offers_at(guild, "nature_grove")
    assert missions.NATURE_WILDFIRE not in missions.offers_at(Guild([Unit("player")]), "nature_grove")


def test_taking_it_lights_three_foci_and_the_great_focus_an_hour_off_the_wilds():
    guild, _, m, state = _started()
    assert m.deadline_day == guild.clock.day + wildfire.DAYS
    small = _small(state)
    assert len(small) == 3 and state.great is not None
    for f in small:
        assert dict(world.neighbors(f.id)) == {"wilds": 1, wildfire.GREAT_ID: 1}
        assert world.node(f.id).has("camp_fight") and node_icon(f.id) is not None
    assert world.node(wildfire.GREAT_ID).has("ogre_fight") and node_icon(wildfire.GREAT_ID) is not None
    known = {n.id for n in world.known(guild)}
    assert {f.id for f in state.foci} <= known
    spots = [world.node(n).pos for n in [f.id for f in state.foci]]
    assert all(min(abs(p[0] - q[0]) + abs(p[1] - q[1]) for q in spots if q != p) > 0.05 for p in spots)


def test_the_shrine_board_tells_the_errand_and_never_hands_it_in():
    from gartok.shrine_screen import ShrineMissionScreen
    guild, _, m, _ = _started()
    scr = ShrineMissionScreen(ui_fonts(), guild, guild.groups[0], on_done=lambda: None)
    t = missions.NATURE_WILDFIRE
    assert "Ogre" in scr.get_req_str(t) and wildfire.REWARD in scr.get_req_str(t)
    assert "day(s) left" in scr.get_status_str(t, 0, False, missions.days_left(guild, m))
    guild.groups[0].members[0].give_to_pack(wildfire.REWARD)
    assert not missions.can_turn_in(guild, m)


# --- the clock ----------------------------------------------------------------- #

def test_a_focus_left_a_week_burns_and_starts_two_more_an_hour_farther():
    guild, _, _, state = _started()
    first = {f.id for f in _small(state)}
    events = _days(guild, wildfire.BURN_DAYS - 1)
    assert {f.id for f in _small(state)} == first
    events = _days(guild, 1)
    assert not first & {f.id for f in _small(state)}
    assert not any(world.exists(i) for i in first)
    assert len(_small(state)) == 6 and state.burned == 3
    for f in _small(state):
        assert dict(world.neighbors(f.id)) == {"wilds": 2, wildfire.GREAT_ID: 2}
    assert any("burned through" in e for e in events) and any("jumps on" in e for e in events)
    assert wildfire.meat_mult(guild) == 1 - 3 * wildfire.MEAT_LOSS


def test_on_the_last_day_every_fire_is_lost_and_the_fortress_stands_hostile():
    guild, _, m, state = _started()
    _days(guild, wildfire.DAYS)
    assert state.over and m.state == "failed"
    assert not state.foci and state.burned == 3 + 6 + 1
    assert wildfire.meat_mult(guild) == 0.5
    assert state.fortress == "hostile" and world.node(wildfire.FORTRESS_ID).has("ogre_fight")
    assert not any(world.exists(i) for i in (wildfire.GREAT_ID, "wildfire_focus_1"))
    assert missions.NATURE_WILDFIRE not in missions.offers_at(guild, "nature_grove")
    _days(guild, 3)
    assert state.burned == 10


def test_a_group_on_a_node_that_burns_walks_back_to_the_wilds_and_one_on_the_way_stops():
    guild, members, _, state = _started()
    f1, f2 = _small(state)[:2]
    here = guild.groups[0]
    walker = guild.split_group(here, [members[1]])
    here.node, walker.node = f1.id, "wilds"
    walker.order = orders.travel(walker, f2.id)
    _days(guild, wildfire.BURN_DAYS)
    assert here.node == "wilds" and here.order is None
    assert walker.order is None and walker.node == "wilds"


# --- the talk chain ------------------------------------------------------------- #

def test_teaching_a_crew_is_charisma_then_intelligence_and_puts_the_fire_out():
    guild, (a, b), _, state = _started()
    f = _small(state)[0]
    assert wildfire.next_check(f) == "charisma" and wildfire.talk_dc(guild, f) == wildfire.FOCUS_DC
    ok, msg = wildfire.talk(guild, f, a, _FixedRNG(20))
    assert ok and wildfire.next_check(f) == "intelligence" and "hearing" in msg
    ok, msg = wildfire.talk(guild, f, b, _FixedRNG(20))
    assert ok and state.taught == 1 and not world.exists(f.id) and f not in state.foci
    assert wildfire.talk_dc(guild, state.great) == wildfire.OGRE_DC - 1


def test_a_missed_check_sets_the_camp_on_you():
    guild, (a, _), _, state = _started()
    f = _small(state)[0]
    ok, msg = wildfire.talk(guild, f, a, _FixedRNG(1))
    assert not ok and f.hostile and not wildfire.can_talk(f) and "weapons" in msg


def test_talking_the_ogre_round_ends_the_errand_with_a_friendly_fortress():
    guild, (a, b), m, state = _started()
    wildfire.talk(guild, state.great, a, _FixedRNG(20))
    ok, msg = wildfire.talk(guild, state.great, b, _FixedRNG(20))
    assert ok and m.state == "done" and "nature_wildfire" in guild.deeds_done
    assert guild.reputation["nature_coven"] == 1
    assert a.count_of(wildfire.REWARD) == 1 and wildfire.REWARD in msg
    assert state.fortress == "friendly" and world.node(wildfire.FORTRESS_ID).functions == ()
    assert not world.exists(wildfire.GREAT_ID)
    assert factions.DEEDS["nature_wildfire"].faction == "nature_coven"
    _days(guild, wildfire.DAYS)
    assert state.fortress == "friendly" and m.state == "done"


# --- the fights' aftermath and the put-out --------------------------------------- #

def test_a_beaten_crew_leaves_a_fire_that_takes_sixteen_hours_to_put_out():
    guild, _, _, state = _started()
    f = _small(state)[0]
    group = guild.groups[0]
    group.node = f.id
    assert wildfire.settle_fight(guild, f.id, won=False) == []
    notes = wildfire.settle_fight(guild, f.id, won=True)
    assert f.cleared and "put it out" in notes[0]
    assert wildfire.put_out(guild, group, _FixedRNG(1))[0].endswith("tried again.")
    assert world.exists(f.id)
    group.order = orders.put_out(guild, group)
    assert group.order.hours == wildfire.PUT_OUT_HOURS
    random.seed(0)
    from unittest.mock import patch
    with patch("gartok.wildfire.random.randint", return_value=20):
        result = campaign.advance(guild)
    assert any("is out" in e for e in result.events)
    assert not world.exists(f.id) and group.node == "wilds"


def test_beating_the_ogre_ends_the_errand_but_the_small_fires_burn_on():
    guild, _, m, state = _started()
    notes = wildfire.settle_fight(guild, wildfire.GREAT_ID, won=True)
    assert m.state == "done" and "beaten" in notes[0] and state.fortress is None
    _days(guild, wildfire.BURN_DAYS)
    assert state.burned == 3 and len(_small(state)) == 6
    _days(guild, wildfire.DAYS - wildfire.BURN_DAYS)
    assert state.over and state.fortress is None and state.burned == 9 and m.state == "done"


def test_the_hostile_fortress_falls_to_a_won_fight():
    guild, *_ = _started()
    _days(guild, wildfire.DAYS)
    assert wildfire.hold_standing(guild)
    wildfire.settle_fight(guild, wildfire.FORTRESS_ID, won=True)
    assert not wildfire.hold_standing(guild) and not world.exists(wildfire.FORTRESS_ID)
    assert wildfire.meat_mult(guild) == 0.5


# --- the hunt -------------------------------------------------------------------- #

def test_a_burned_forest_gives_less_meat_and_a_standing_fortress_more_goblins():
    guild, members, *_ = _started()
    clean = hunt.begin(guild, members, world.node("wilds"), "Normal")
    _days(guild, wildfire.DAYS)
    burnt = hunt.begin(guild, members, world.node("wilds"), "Normal")
    assert burnt.meat_mult == 0.5 and clean.meat_mult == 1.0
    assert burnt.ambush_mult == clean.ambush_mult * wildfire.HOLD_AMBUSH_MULT
    clean.yield_hours = burnt.yield_hours = 8
    assert burnt.meat == clean.meat // 2
    rng = random.Random(1)
    packs = [hunt.wilds_pack(rng, guild=guild) for _ in range(40)]
    assert any(all(u.race["name"] in ("Goblin", "Hobgoblin") for u in p) for p in packs)
    ox = hunt.begin(guild, members, world.node("ox_fields"), "Normal", target="ox")
    assert ox.meat_mult == 1.0


# --- save and load --------------------------------------------------------------- #

def test_the_event_survives_a_save_and_its_nodes_come_back():
    guild, (a, _), _, state = _started()
    wildfire.talk(guild, _small(state)[0], a, _FixedRNG(20))
    _days(guild, wildfire.BURN_DAYS)
    d = wildfire.to_dict(state)
    ids = {f.id for f in state.foci}
    world.clear_runtime()
    assert not any(world.exists(i) for i in ids)
    guild.wildfire = wildfire.from_dict(d)
    wildfire.sync_world(guild)
    assert all(world.exists(i) for i in ids)
    assert guild.wildfire.burned == state.burned and guild.wildfire.foci[0].talk == state.foci[0].talk
    assert wildfire.from_dict(None) is None and wildfire.to_dict(None) is None


def test_a_save_on_disk_round_trips_the_wildfire(tmp_path, monkeypatch):
    from gartok import persist
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    guild, _, _, state = _started()
    persist.save_game("w", guild)
    world.clear_runtime()
    loaded = persist.load_game("w")
    assert loaded.wildfire.start_day == state.start_day
    assert all(world.exists(f.id) for f in state.foci)
    assert persist.PAYLOAD_DEFAULTS["wildfire"] is None


# --- the map's inspector --------------------------------------------------------- #

def _map(guild):
    return MapScreen(ui_fonts(), guild, lambda: None, lambda: None, lambda: None, lambda grp: None)


def test_the_map_offers_one_talk_button_that_opens_the_dialogue_and_a_miss_starts_the_fight():
    guild, (a, b), _, state = _started()
    f = _small(state)[0]
    group = guild.groups[0]
    group.node = f.id
    talks = []
    ms = _map(guild)
    ms.on_dialogue = lambda g, enc, done: talks.append((g, enc, done))
    blocks = ms._inspector_content(group, world.node(f.id))
    keys = [blk.get("key") for blk in blocks]
    assert "wf_talk" in keys and "camp_fight" in keys
    assert any("burns through" in blk.get("text", "") for blk in blocks)
    ms.selected = group
    ms._handle_button("wf_talk")
    g, enc, done = talks[0]
    assert g is group and [o.verb for o in enc.options(a, [a, b])] == ["persuade", "bribe", "attack"]
    assert enc.option("bribe", a, [a, b]).block == "they want to learn, not be paid"
    with patch("gartok.wildfire.random.randint", return_value=1):
        result = enc.choose("persuade", a, [a, b], rng=_FixedRNG(1))
    done(result)
    assert f.hostile and group.order is not None and group.order.kind == "camp_fight"


def test_the_wildfire_dialogue_walks_the_two_checks_to_the_lesson():
    guild, (a, b), _, state = _started()
    f = _small(state)[0]
    enc = dialogue.WildfireTalk(guild, f, wildfire.talker(f, 1))
    first = enc.choose("persuade", a, [a, b], rng=_FixedRNG(20))
    assert first.kind == "next" and not first.over
    assert [o.verb for o in enc.options(b, [a, b])] == ["teach", "bribe", "attack"]
    assert enc.option("teach", b, [a, b]).check.startswith("INT")
    second = enc.choose("teach", b, [a, b], rng=_FixedRNG(20))
    assert second.kind == "peace" and not world.exists(f.id)


def test_the_map_offers_the_put_out_once_the_crew_is_beaten():
    guild, _, _, state = _started()
    f = _small(state)[0]
    group = guild.groups[0]
    group.node = f.id
    wildfire.settle_fight(guild, f.id, won=True)
    ms = _map(guild)
    blocks = ms._inspector_content(group, world.node(f.id))
    keys = [blk.get("key") for blk in blocks]
    assert "wf_put_out" in keys and "camp_fight" not in keys
    ms.selected = group
    ms._handle_button("wf_put_out")
    assert group.order.kind == "work" and group.order.task == "put_out"


def test_the_map_refreshes_when_a_focus_comes_or_goes():
    guild, *_ = _started()
    ms = _map(guild)
    assert wildfire.GREAT_ID in ms._nodes
    wildfire.settle_fight(guild, wildfire.GREAT_ID, won=True)
    import pygame
    ms.draw(pygame.Surface((1280, 800)))
    assert wildfire.GREAT_ID not in ms._nodes


# --- the app opens the fight ---------------------------------------------------- #

def _opened_battle(guild, node_id):
    from tests.helpers import make_app
    app = make_app(guild)
    app._wildfire_node = None
    app._left_outside = None
    seen = []
    app._enter_battle = lambda battle, node: seen.append(battle)
    group = guild.groups[0]
    group.node = node_id
    app._ACTIVITY_OPENERS[world.node(node_id).functions[0]](app, group, world.node(node_id), None)
    return app, seen


def test_attacking_a_camp_opens_its_crew_and_the_great_focus_opens_the_fortress():
    from gartok.fortress_scenario import FortressScenario
    guild, _, _, state = _started()
    f = _small(state)[0]
    app, seen = _opened_battle(guild, f.id)
    assert app._wildfire_node == f.id
    assert [u.race["name"] for u in seen[0].enemy_units] == ["Goblin"] * 3 + ["Hobgoblin"]
    app, seen = _opened_battle(guild, wildfire.GREAT_ID)
    assert isinstance(seen[0].scenario, FortressScenario) and not seen[0].scenario.finished
    assert wildfire.ogre_of(seen[0]) is not None


def test_a_cleared_camp_opens_no_fight():
    guild, _, _, state = _started()
    f = _small(state)[0]
    wildfire.settle_fight(guild, f.id, won=True)
    from tests.helpers import make_app
    app = make_app(guild)
    app._wildfire_node = None
    calls = []
    app._after_activity = lambda: calls.append("back")
    app._enter_wildfire_fight(guild.groups[0], world.node(f.id))
    assert calls == ["back"] and app._wildfire_node is None
