"""The tanner's third job: Aurochs, the immortal ox. The Country Roads hide the
Ox Fields until the job is out; at the Fields the party tracks him by daylight
(a Wisdom check an hour, harder every time the trail was found); a found trail
opens a big daylight map where he runs from anyone near until he is pinned or
winded, and the herd answers his call. His hide (+1 Strength worn) closes the
chain and teaches the Signal Horn."""

import os
import random

import pygame

from gartok import (
    ai,
    data,
    encounters,
    factions,
    items,
    loot,
    missions,
    ox,
    ox_fields,
    persist,
    world,
)
from gartok.battle import Battle
from gartok.clock import Clock
from gartok.guild import Guild
from gartok.hunt import HuntState
from gartok.unit import Unit
from tests.helpers import fixed_d20


def _guild(hour=9, node="country_roads"):
    random.seed(3)
    members = [Unit("player"), Unit("player")]
    return Guild(members, node=node, clock=Clock(hour * 3600)), members


def _job(guild, signer):
    missions.accept(guild, signer, missions.TANNER_HIDES).state = "done"
    missions.accept(guild, signer, missions.TANNER_BIWOLF).state = "done"
    return missions.accept(guild, signer, missions.TANNER_OX)


# --- the job ------------------------------------------------------------- #

def test_the_ox_job_is_offered_only_after_the_biwolf_is_in():
    guild, (signer, _) = _guild()
    offered = lambda: {t.id for t in missions.offers_at(guild, "city")}
    missions.accept(guild, signer, missions.TANNER_HIDES).state = "done"
    assert missions.TANNER_OX.id not in offered()
    biwolf = missions.accept(guild, signer, missions.TANNER_BIWOLF)
    assert missions.TANNER_OX.id not in offered()
    biwolf.state = "done"
    assert missions.TANNER_OX.id in offered()


def test_it_pays_twice_the_hides_and_has_no_deadline():
    guild, (signer, _) = _guild()
    m = _job(guild, signer)
    assert missions.TANNER_OX.reward == 2 * missions.TANNER_HIDES.reward
    assert m.deadline_day is None and missions.days_left(guild, m) is None


def test_the_hide_pays_teaches_the_recipe_and_makes_three_reputation():
    guild, (signer, mate) = _guild()
    m = _job(guild, signer)
    guild.reputation["tanners"] = 2
    guild.deeds_done += ["tanners_hides", "tanners_biwolf"]
    mate.give_to_pack(items.THUNDERHIDE_ITEM)
    before = signer.money + mate.money
    earned = missions.turn_in(guild, m)
    assert m.state == "done"
    assert signer.money + mate.money - before == missions.TANNER_OX.reward
    assert guild.reputation["tanners"] == 3
    assert any(d.id == "tanners_ox" for d in earned)
    for u in (signer, mate):
        assert "Signal Horn" in u.recipes
    assert mate.count_of(items.THUNDERHIDE_ITEM) == 0


def test_the_ox_deed_waits_for_the_biwolf_deed():
    guild, _ = _guild()
    assert "tanners_ox" not in {d.id for d in factions.open_deeds(guild)}
    guild.deeds_done.append("tanners_biwolf")
    assert "tanners_ox" in {d.id for d in factions.open_deeds(guild)}


def test_a_worn_hide_counts_for_the_turn_in():
    guild, (signer, _) = _guild()
    m = _job(guild, signer)
    signer.give_to_artifact(items.THUNDERHIDE_ITEM)
    assert missions.progress(guild, m) == 1
    missions.turn_in(guild, m)
    assert signer.equipped_artifact is None


def test_losing_the_hide_after_the_kill_fails_the_job_for_good():
    guild, (signer, mate) = _guild()
    m = _job(guild, signer)
    assert missions.fail_if_hide_lost(guild) is None             # he still walks: nothing lost
    missions.slay_ox(guild)
    assert missions.pending_ox(guild) is None
    mate.give_to_pack(items.THUNDERHIDE_ITEM)
    assert missions.fail_if_hide_lost(guild) is None
    mate.remove_named(items.THUNDERHIDE_ITEM)
    assert missions.fail_if_hide_lost(guild) is m
    assert m.state == "failed"
    assert missions.TANNER_OX.id not in {t.id for t in missions.offers_at(guild, "city")}
    assert missions.retry_in(guild, missions.TANNER_OX) is None


def test_a_worn_hide_is_not_lost():
    guild, (signer, _) = _guild()
    _job(guild, signer)
    missions.slay_ox(guild)
    signer.give_to_artifact(items.THUNDERHIDE_ITEM)
    assert missions.fail_if_hide_lost(guild) is None


# --- the hide and the horn ----------------------------------------------- #

def test_the_hide_adds_a_point_of_strength_while_worn_and_survives_a_save():
    u = Unit("player")
    base = u.strength
    u.give_to_pack(items.THUNDERHIDE_ITEM)
    u.give_to_artifact(items.THUNDERHIDE_ITEM)
    assert u.strength == base + 1
    back = Unit.from_save(persist.unit_to_dict(u))
    assert back.strength == base + 1 and back.equipped_artifact == items.THUNDERHIDE_ITEM
    u.take_from_artifact()
    assert u.strength == base


def test_aurochs_always_drops_the_hide_and_the_horn_and_an_ox_does_not():
    batt = Battle([Unit("player")], ox.aurochs_pack(), lethal=True)
    batt.enemy_units[0].status = "dead"
    pool = loot.field_loot(batt, [])
    assert items.THUNDERHIDE_ITEM in pool and items.LEGENDARY_HORN_ITEM in pool

    calf = encounters.build_enemy(1, race_pool=data.OX_POOL)
    batt = Battle([Unit("player")], [calf], lethal=True)
    batt.enemy_units[0].status = "dead"
    pool = loot.field_loot(batt, [])
    assert items.THUNDERHIDE_ITEM not in pool


def test_the_signal_horn_recipe_needs_the_horn_and_a_chisel():
    r = items.CRAFTING_RECIPES["Signal Horn"]
    assert items.LEGENDARY_HORN_ITEM in r.materials and "Chisel" in r.tools
    assert items.get(items.LEGENDARY_HORN_ITEM) and items.get(items.THUNDERHIDE_ITEM)


# --- finding the fields -------------------------------------------------- #

def test_the_fields_are_hidden_until_found_and_two_hours_from_the_farm():
    guild, _ = _guild()
    assert "ox_fields" not in {n.id for n in world.known(guild)}
    guild.ox_fields_discovered = True
    assert "ox_fields" in {n.id for n in world.known(guild)}
    path, dist = world.route("farm", "ox_fields")
    assert path == ["farm", "country_roads", "ox_fields"] and dist == 2
    assert world.route("farm", "country_roads")[1] == 1


def test_the_search_finds_nothing_without_the_job_and_costs_the_hours():
    guild, (signer, _) = _guild()
    signer.mod_wisdom = 10
    before = guild.clock.seconds
    with fixed_d20(20):
        found, _msg = ox.scout_country_roads(guild, guild.groups[0])
    assert not found and not guild.ox_fields_discovered
    assert guild.clock.seconds - before == ox.SCOUT_HOURS * 3600


def test_the_search_finds_them_with_the_job_out_and_a_good_roll_only():
    guild, (signer, mate) = _guild()
    signer.mod_wisdom = mate.mod_wisdom = 0
    _job(guild, signer)
    with fixed_d20(ox.SCOUT_DC - 1):
        found, _msg = ox.scout_country_roads(guild, guild.groups[0])
    assert not found and not guild.ox_fields_discovered
    with fixed_d20(ox.SCOUT_DC):
        found, msg = ox.scout_country_roads(guild, guild.groups[0])
    assert found and guild.ox_fields_discovered and "Fields" in msg


def test_a_found_field_and_the_trail_count_survive_a_save():
    slot = "oxtestworld"
    if os.path.exists(persist.save_path(slot)):
        return                                        # never clobber a real save
    guild, _ = _guild()
    guild.ox_fields_discovered = True
    guild.ox_trails = 2
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot)
        assert back.ox_fields_discovered and back.ox_trails == 2
    finally:
        persist.delete_world(slot)


# --- tracking ------------------------------------------------------------ #

class _Rolls:
    def __init__(self, *values):
        self.values = list(values)

    def randint(self, a, b):
        return self.values.pop(0)


def test_each_found_trail_makes_the_next_two_harder():
    guild, (signer, mate) = _guild()
    assert ox.track_dc(guild) == ox.TRACK_DC
    state = HuntState([signer, mate], world.node("ox_fields"), hours_left=4, target="ox")
    elapsed, found = ox.track(state, guild, _Rolls(20))
    assert found and elapsed == 1 and guild.ox_trails == 1
    assert ox.track_dc(guild) == ox.TRACK_DC + ox.TRACK_DC_STEP
    assert state.hours_left == 3 and state.hours_hunted == 1


def test_a_bad_stretch_finds_nothing_and_leaves_the_dc_alone():
    guild, (signer, _) = _guild()
    state = HuntState([signer], world.node("ox_fields"), hours_left=3, target="ox")
    elapsed, found = ox.track(state, guild, _Rolls(1, 1, 1))
    assert not found and elapsed == 3 and state.hours_left == 0
    assert guild.ox_trails == 0


def test_the_best_trackers_wisdom_counts():
    guild, (signer, mate) = _guild()
    signer.mod_wisdom, mate.mod_wisdom = 0, 6
    state = HuntState([signer, mate], world.node("ox_fields"), hours_left=1, target="ox")
    _, found = ox.track(state, guild, _Rolls(ox.TRACK_DC - 6))
    assert found


def test_the_trail_is_only_read_by_day():
    assert ox.daylight_hours(6) == 12
    assert ox.daylight_hours(15) == 3
    assert ox.daylight_hours(19) == 0


def test_the_hunt_screen_tracks_then_hands_over_aurochs():
    from gartok.hunt_screen import HuntScreen
    from gartok.ui.tokens import fonts as ui_fonts
    guild, (signer, mate) = _guild(hour=8, node="ox_fields")
    guild.ox_fields_discovered = True
    _job(guild, signer)
    st = HuntState([signer, mate], world.node("ox_fields"), hours_left=0, target="ox")
    scr = HuntScreen(ui_fonts(), guild, st, phase="setup",
                     on_ambush=lambda *_: None, on_done=lambda: None)
    surf = pygame.Surface((1100, 700))
    scr.draw(surf)
    st.hours_left = 4
    random.seed(1)
    signer.mod_wisdom = 30                                     # any roll finds the trail
    scr._do_stretch()
    assert scr.phase == "ambush" and scr.ambush_pack[0].name == "Aurochs"
    assert st.fights == 1 and guild.ox_trails == 1
    scr.draw(surf)


def test_the_hunt_screen_will_not_start_a_search_after_dark():
    from gartok.hunt_screen import HuntScreen
    from gartok.ui.tokens import fonts as ui_fonts
    guild, (signer, _) = _guild(hour=21, node="ox_fields")
    st = HuntState([signer], world.node("ox_fields"), hours_left=0, target="ox")
    scr = HuntScreen(ui_fonts(), guild, st, phase="setup",
                     on_ambush=lambda *_: None, on_done=lambda: None)
    scr.draw(pygame.Surface((1100, 700)))
    assert "confirm" not in {k for k, _r in scr.buttons}


def test_a_lost_search_wraps_up_without_a_fight():
    from gartok.hunt_screen import HuntScreen
    from gartok.ui.tokens import fonts as ui_fonts
    guild, (signer, _) = _guild(hour=8, node="ox_fields")
    st = HuntState([signer], world.node("ox_fields"), hours_left=2, target="ox")
    scr = HuntScreen(ui_fonts(), guild, st, phase="setup",
                     on_ambush=lambda *_: None, on_done=lambda: None)
    signer.mod_wisdom = -30
    scr._do_stretch()
    assert scr.phase == "done" and any("trail of the ox" in ln for ln in scr.result)


# --- the field ----------------------------------------------------------- #

def _fight(level=5, size=4, seed=1):
    random.seed(seed)
    squad = []
    for _ in range(size):
        u = Unit("player")
        u.set_track_level("combat", level)
        u.set_track_level("racial", level)
        u.hp = u.hp_max
        squad.append(u)
    return Battle(squad, ox.aurochs_pack(), scenario=ox_fields.OxFieldsScenario(),
                  daylight=False, lethal=True)


def test_the_field_is_big_open_to_the_sun_and_walkable_from_end_to_end():
    b = _fight()
    assert (b.board.cols, b.board.rows) == (ox_fields.COLS, ox_fields.ROWS)
    assert b.ambient_light and not b.ground
    assert ox_fields._connected(b.board.walls, b.board.cols, b.board.rows, (1, ox_fields.ROWS // 2),
                                (ox_fields.COLS - 2, ox_fields.ROWS // 2))
    assert b.board.difficult                                      # mud somewhere
    assert all(p.pos[0] <= 2 for p in b.player_units)
    boss = b.enemy_units[0]
    assert boss.pos[0] >= ox_fields.COLS * 2 // 3


def test_the_fight_is_won_the_moment_aurochs_falls():
    b = _fight()
    assert b.scenario.win_check(b) is None
    b.enemy_units[0].hp, b.enemy_units[0].status = 0, "dead"
    assert b.scenario.win_check(b) == "player"


def test_the_herd_answers_every_few_rounds_up_to_a_limit():
    b = _fight()
    for rnd in range(1, 80):
        b.round_no = rnd
        b.scenario.on_round(b)
    assert b.scenario.calls == ox_fields.CALL_MAX
    assert len(b.enemy_units) == 1 + ox_fields.CALL_MAX
    assert any("answering call" in ln for ln in b.log_lines)


def test_a_hint_names_the_way_to_a_beast_out_of_sight():
    b = _fight()
    b.round_no = 2
    b.scenario.on_round(b)
    assert any("Hooves drum somewhere to the" in ln for ln in b.log_lines) or all(
        b.can_see_unit(p, b.enemy_units[0]) for p in b.player_units)
    assert ox_fields.direction_name((0, 0), (10, 0)) == "east"
    assert ox_fields.direction_name((10, 10), (10, 0)) == "north"


def test_aurochs_runs_from_anyone_near_and_does_not_when_nobody_is():
    b = _fight()
    boss = b.enemy_units[0]
    boss_start = boss.pos
    foe = b.player_units[0]
    # nobody near: idle
    assert ai._skitter(b, boss) == "idle"
    # drag a hunter right up to him
    foe.pos = (max(0, boss.pos[0] - 6), boss.pos[1])
    b.order = [boss] + [u for u in b.order if u is not boss]
    b.turn_idx = 0
    boss.ap = 2
    before = min(ai.grid_distance(boss.pos, p.pos) for p in b.player_units)
    assert ai._skitter(b, boss) == "moved"
    after = min(ai.grid_distance(boss.pos, p.pos) for p in b.player_units)
    assert after > before and boss.pos != boss_start


def test_aurochs_turns_and_fights_when_cornered_or_winded():
    b = _fight()
    boss = b.enemy_units[0]
    for u in b.player_units:
        u.pos = (boss.pos[0] - 3, boss.pos[1])
    boss.fled_turns = ai.SKITTISH_STAMINA
    boss.flee_round = None
    assert ai._skitter(b, boss) == "fight"
    assert boss.charging_until >= b.round_no
    assert ai._skitter(b, boss) == "fight"                          # stays on it for the charge
    assert any("winded" in ln for ln in b.log_lines)


def test_the_ai_plays_the_chase_to_a_result():
    b = _fight(level=8, size=6, seed=2)
    guard = 0
    while b.winner is None and guard < 3000 and b.round_no < 90:
        guard += 1
        ai.take_turn(b, b.active)
    assert guard < 3000
    assert any("Aurochs" in ln for ln in b.log_lines)


def test_reinforce_places_a_fresh_enemy_and_gives_it_a_turn():
    b = _fight()
    calf = encounters.build_enemy(1, race_pool=data.OX_POOL)
    n = len(b.order)
    free = [(x, y) for x in range(ox_fields.COLS - 2) for y in range(ox_fields.ROWS - 1)]
    c = b.reinforce(calf, free)
    assert c is not None and c in b.enemy_units and c in b.units and len(b.order) == n + 1
    assert b.reinforce(encounters.build_enemy(1, race_pool=data.OX_POOL), []) is None


# --- the app wiring ------------------------------------------------------ #

def _app(guild):
    from gartok.app import App
    app = App.__new__(App)
    app.world = "testworld"
    app.scene = None
    app.fonts = None
    app.ui_fonts = None
    app.guild = guild
    app._battle_squad = []
    app._battle_node = None
    app._arena_offer = None
    app._hunt = None
    app._pause_order = None
    app._pause_group = None
    app._claim_stage_pending = None
    app._left_outside = None
    app._map_notices = []
    app._pending = []
    app._pending_event = None
    app._save = lambda: None
    app._autosave = lambda *_a, **_k: None
    return app


def test_the_ox_node_order_opens_the_tracking_screen():
    import gartok.app as app_mod
    from gartok import orders
    from gartok.group import Group
    random.seed(1)
    g = Group([Unit("player")], node="ox_fields")
    guild = Guild(None, groups=[g])
    app = _app(guild)
    g.order = orders.interactive("ox_hunt")
    app._advance()
    assert isinstance(app.scene, app_mod.TrackScreen)
    assert app._hunt.target == "ox" and app.scene.tutorial_key() == "ox_hunt"


def test_killing_aurochs_closes_the_trail_and_losing_the_hide_fails_the_job():
    import gartok.app as app_mod
    guild, (signer, mate) = _guild(hour=10, node="ox_fields")
    m = _job(guild, signer)
    app = _app(guild)
    app._hunt = HuntState([signer, mate], world.node("ox_fields"), hours_left=4, target="ox")
    app._battle_squad = [signer, mate]
    app._battle_node = world.node("ox_fields")
    battle = Battle([signer, mate], ox.aurochs_pack(), scenario=ox_fields.OxFieldsScenario(),
                    daylight=True, lethal=True)
    boss = battle.enemy_units[0]
    boss.hp, boss.status = 0, "dead"
    battle.winner = "player"
    app._battle_end(battle)
    assert missions.pending_ox(guild) is None and m.ambush_done
    assert app._hunt.hours_left == 0
    assert isinstance(app.scene, app_mod.LootScreen)             # the hide and the horn on the field
    app.scene.on_done()                                          # ...left lying
    assert m.state == "failed"
    assert any("hide is lost" in n for n in app._map_notices)
    assert isinstance(app.scene, app_mod.TrackScreen) and app.scene.phase == "done"


def test_a_lost_chase_leaves_the_trail_open_and_the_next_one_harder():
    guild, (signer, mate) = _guild(hour=10, node="ox_fields")
    m = _job(guild, signer)
    app = _app(guild)
    app._hunt = HuntState([signer, mate], world.node("ox_fields"), hours_left=4, target="ox")
    guild.ox_trails = 1
    app._battle_squad = [signer, mate]
    app._battle_node = world.node("ox_fields")
    battle = Battle([signer, mate], ox.aurochs_pack(), scenario=ox_fields.OxFieldsScenario(),
                    daylight=True, lethal=True)
    for c in battle.player_units:
        c.hp, c.status = 0, "dead"
    battle.winner = "enemy"
    app._battle_end(battle)
    assert m.state == "active" and not m.ambush_done and missions.pending_ox(guild) is m
    assert ox.track_dc(guild) == ox.TRACK_DC + ox.TRACK_DC_STEP


# --- the map ------------------------------------------------------------- #

def _inspect(guild, node_id):
    from gartok.map_screen import MapScreen
    from gartok.ui.tokens import fonts as ui_fonts
    ms = MapScreen(ui_fonts(), guild, lambda: None, lambda: None, lambda: None, lambda grp: None)
    return ms, ms._inspector_content(guild.groups[0], world.node(node_id))


def test_the_country_roads_offer_a_search_until_the_fields_are_found():
    guild, _ = _guild(node="country_roads")
    _, blocks = _inspect(guild, "country_roads")
    assert "scout_fields" in [b.get("key") for b in blocks]
    guild.ox_fields_discovered = True
    _, blocks = _inspect(guild, "country_roads")
    assert "scout_fields" not in [b.get("key") for b in blocks]


def test_the_search_button_reveals_the_fields_on_the_map():
    guild, (signer, mate) = _guild(node="country_roads")
    signer.mod_wisdom = mate.mod_wisdom = 10
    _job(guild, signer)
    ms, _ = _inspect(guild, "country_roads")
    ms.selected = guild.groups[0]
    assert "ox_fields" not in ms._nodes
    with fixed_d20(20):
        ms._handle_button("scout_fields")
    assert "ox_fields" in ms._nodes and guild.ox_fields_discovered


def test_the_fields_offer_the_track_button_only_with_the_job_out():
    guild, (signer, _) = _guild(node="ox_fields")
    guild.ox_fields_discovered = True
    _, blocks = _inspect(guild, "ox_fields")
    assert "ox_hunt" not in [b.get("key") for b in blocks]
    assert any("trail is cold" in b.get("text", "") for b in blocks)
    _job(guild, signer)
    _, blocks = _inspect(guild, "ox_fields")
    assert "ox_hunt" in [b.get("key") for b in blocks]
    missions.slay_ox(guild)
    _, blocks = _inspect(guild, "ox_fields")
    assert "ox_hunt" not in [b.get("key") for b in blocks]
