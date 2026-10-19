"""The Faith Order's errand (missions.FAITH_BATTLEFIELD) and the Battlefield's skirmish
(battlefield.py): allied soldiers played by the AI, the trenches, the potions, the fail rule."""

import random
from types import SimpleNamespace

from gartok import actions, ai, battlefield, factions, missions, world
from gartok.battle_screen import BattleScreen
from gartok.clock import Clock
from gartok.guild import Guild
from tests.helpers import Battle, Unit

POTION = "Minor Healing Potion"


def _guild(node="faith_cathedral"):
    random.seed(5)
    members = [Unit("player"), Unit("player")]
    guild = Guild(members, node=node, clock=Clock(10 * 3600))
    guild.missions.append(missions.Mission(missions.LIBRARY_ANCIENT_CODEX.id, members[0].uid, 0, None,
                                           state="done"))
    return guild, members


def _skirmish(squad, rng=None):
    sc = battlefield.BattlefieldScenario(squad, rng or random.Random(2))
    return Battle(squad, sc.enemies, scenario=sc, allies=sc.allies, aggressor="enemy"), sc


# --- the world --------------------------------------------------------------- #

def test_the_battlefield_lies_past_the_frontier_outpost_and_is_known_from_the_start():
    for nid in ("frontier_outpost", "battlefield"):
        assert not world.node(nid).hidden
    assert "frontier_outpost" in [v for v, _ in world.neighbors("ledger_hold")]
    assert "battlefield" in [v for v, _ in world.neighbors("frontier_outpost")]
    assert world.node("battlefield").has("skirmish")
    assert world.node("frontier_outpost").functions == ()


# --- the mission ------------------------------------------------------------- #

def test_the_cathedral_offers_the_errand_once_the_sanctuaries_are_open():
    guild, _ = _guild()
    assert missions.FAITH_BATTLEFIELD in missions.offers_at(guild, "faith_cathedral")
    assert missions.FAITH_BATTLEFIELD not in missions.offers_at(Guild([Unit("player")]), "faith_cathedral")


def test_accepting_hands_over_six_potions_the_first_time_only():
    guild, (signer, _) = _guild()
    m = missions.accept(guild, signer, missions.FAITH_BATTLEFIELD)
    assert signer.count_of(POTION) == 6
    assert m.deadline_day == guild.clock.day + 7
    m.state, m.failed_day = "failed", guild.clock.day
    guild.clock.advance_hours(14 * 24)
    assert missions.retry_in(guild, missions.FAITH_BATTLEFIELD) == 0
    missions.accept(guild, signer, missions.FAITH_BATTLEFIELD)
    assert signer.count_of(POTION) == 6


def test_a_missed_week_fails_it_and_it_comes_back_in_two():
    guild, (signer, _) = _guild()
    m = missions.accept(guild, signer, missions.FAITH_BATTLEFIELD)
    guild.clock.advance_hours(8 * 24)
    assert m in missions.expire_overdue(guild)
    assert missions.retry_in(guild, missions.FAITH_BATTLEFIELD) == 14


def test_the_skirmish_is_open_only_to_the_group_carrying_the_errand():
    guild, (signer, _) = _guild()
    other = guild.groups[0]
    assert missions.pending_battlefield(guild, other) is None
    missions.accept(guild, signer, missions.FAITH_BATTLEFIELD)
    assert missions.pending_battlefield(guild, other) is not None
    assert missions.pending_battlefield(guild, SimpleNamespace(members=[Unit("player")])) is None


def test_a_win_with_every_soldier_alive_is_the_faith_deed():
    guild, (signer, _) = _guild()
    m = missions.accept(guild, signer, missions.FAITH_BATTLEFIELD)
    notice, deeds = missions.settle_battlefield(guild, m, won=True, lost=[])
    assert m.state == "done" and [d.id for d in deeds] == ["faith_battlefield"]
    assert factions.DEEDS["faith_battlefield"].faction == "faith_order"
    assert "Faith Order" in notice


def test_a_lost_soldier_fails_it_even_on_a_win():
    guild, (signer, _) = _guild()
    m = missions.accept(guild, signer, missions.FAITH_BATTLEFIELD)
    notice, deeds = missions.settle_battlefield(guild, m, won=True, lost=[SimpleNamespace(name="Brakk")])
    assert m.state == "failed" and m.failed_day == guild.clock.day and not deeds
    assert "Brakk" in notice and "faith_battlefield" not in guild.deeds_done


def test_a_lost_fight_fails_it():
    guild, (signer, _) = _guild()
    m = missions.accept(guild, signer, missions.FAITH_BATTLEFIELD)
    missions.settle_battlefield(guild, m, won=False, lost=[])
    assert m.state == "failed"


# --- the field --------------------------------------------------------------- #

def test_soldiers_two_under_the_squad_and_the_warband_one_over():
    squad = [Unit("player") for _ in range(2)]
    for u in squad:
        u.set_track_level("combat", 6)
        u.set_track_level("work", 4)
    sc = battlefield.BattlefieldScenario(squad, random.Random(1))
    assert len(sc.allies) == battlefield.SOLDIERS and len(sc.enemies) == battlefield.WARBAND
    assert {u.mean_level for u in sc.allies} == {3}
    assert {u.mean_level for u in sc.enemies} == {6}
    assert all(u.alignment == "Lawful and Good" for u in sc.allies)


def test_a_fresh_squad_still_gets_soldiers_at_level_zero():
    sc = battlefield.BattlefieldScenario([Unit("player")], random.Random(1))
    assert {u.mean_level for u in sc.allies} == {0}


def test_the_soldiers_start_in_the_guilds_trench_beside_the_squad():
    batt, _ = _skirmish([Unit("player"), Unit("player")])
    near, far = battlefield.PARAPET_X
    assert all(c.pos[0] < near for c in batt.player_units)
    assert all(c.pos[0] > far for c in batt.enemy_units)
    assert [c.ai_ally for c in batt.player_units] == [False, False] + [True] * battlefield.SOLDIERS
    assert all(c.team == "player" for c in batt.player_units)


def test_each_trench_has_gaps_to_climb_out_through():
    for x in battlefield.PARAPET_X:
        wall = battlefield.parapet(x)
        gaps = [y for y in range(battlefield.ROWS) if (x, y) not in wall]
        assert gaps and len(wall) >= battlefield.ROWS // 2


def test_the_soldiers_are_not_the_guilds_after_the_fight():
    from gartok import campaign
    guild, squad = _guild(node="battlefield")
    batt, _ = _skirmish(squad)
    for c in batt.enemy_units:
        c.hp, c.status = 0, "dead"
    soldier = batt.player_units[-1]
    soldier.hp, soldier.status = 0, "dead"
    batt.winner = "player"
    outcome = campaign.absorb_battle(guild, squad, batt, node=world.node("battlefield"))
    assert outcome.survivors == squad and outcome.fallen == []
    assert battlefield.soldiers_lost(batt) == [soldier]
    assert len(guild.roster) == 2


# --- who plays the soldiers ---------------------------------------------------- #

def test_the_screen_hands_a_soldiers_turn_to_the_ai():
    batt, _ = _skirmish([Unit("player")])
    screen = BattleScreen.__new__(BattleScreen)
    screen.controllers = {"player": "human", "enemy": "ai"}
    me, soldier = batt.player_units[0], batt.player_units[1]
    assert screen._plays(me) and not screen._plays(soldier)
    assert not screen._plays(batt.enemy_units[0])


def test_a_soldier_stops_to_save_a_dying_comrade():
    batt, _ = _skirmish([Unit("player")])
    soldier, comrade = batt.player_units[1], batt.player_units[2]
    batt.board.walls.clear()
    soldier.pos, comrade.pos = (3, 3), (3, 4)
    for c in batt.enemy_units:
        c.pos = (30, c.pos[1])
    comrade.hp, comrade.status = 0, "dying"
    batt.turn_idx, soldier.ap = batt.order.index(soldier), 2
    ai.take_turn(batt, soldier)
    assert any(f"tries to stabilize {comrade.name}" in ln for ln in batt.log_lines)


def test_the_warband_goes_after_the_soldiers_too():
    batt, _ = _skirmish([Unit("player")])
    raider = batt.enemy_units[0]
    assert batt.player_units[1] in [u for u in batt.units if u.team != raider.team]


# --- the potions ----------------------------------------------------------------- #

def test_a_potion_fed_to_a_dying_ally_puts_them_back_on_their_feet():
    medic, soldier = Unit("player"), Unit("player")
    medic.give_to_pack(POTION, 2)
    batt = Battle([medic], [Unit("enemy")], allies=[soldier])
    me, him = batt.player_units
    batt.board.walls.clear()
    me.pos, him.pos = (2, 2), (2, 3)
    him.hp, him.status = 0, "dying"
    me.ap = 2
    assert actions.DRINK_POTION.can(batt, me, him)
    actions.DRINK_POTION.execute(batt, me, him)
    assert him.alive and him.hp >= 1 and him.death_clock == 0


def test_a_good_unit_with_a_potion_feeds_it_to_a_dying_neighbour():
    medic, friend = Unit("player"), Unit("player")
    medic.alignment = "Lawful and Good"
    medic.give_to_pack(POTION)
    batt = Battle([friend], [Unit("enemy")], allies=[medic])
    him, me = batt.player_units
    batt.board.walls.clear()
    me.pos, him.pos = (2, 2), (2, 3)
    batt.enemy_units[0].pos = (14, 10)
    him.hp, him.status = 0, "dying"
    batt.turn_idx, me.ap = batt.order.index(me), 2
    ai.take_turn(batt, me)
    assert him.alive


# --- the app ----------------------------------------------------------------------- #

def _app(guild):
    from gartok.app import App
    app = App.__new__(App)
    app.world, app.scene, app.fonts, app.ui_fonts = "testworld", None, None, None
    app.guild = guild
    app._battle_squad, app._battle_node, app._arena_offer = [], None, None
    app._hunt = app._pause_order = app._pause_group = app._claim_stage_pending = None
    app._left_outside = None
    app._map_notices = []
    app._after_activity = lambda: None
    app._save = lambda: None
    app._autosave = lambda label: None
    return app


def test_the_app_fights_the_skirmish_with_the_soldiers_and_settles_the_errand():
    guild, squad = _guild(node="battlefield")
    m = missions.accept(guild, squad[0], missions.FAITH_BATTLEFIELD)
    app = _app(guild)
    entered = SimpleNamespace(battle=None)
    app._enter_battle = lambda battle, node: setattr(entered, "battle", battle)
    app._enter_skirmish(guild.groups[0], world.node("battlefield"))
    batt = entered.battle
    assert sum(c.ai_ally for c in batt.player_units) == battlefield.SOLDIERS
    assert batt.lethal and app._skirmish is m
    for c in batt.enemy_units:
        c.hp, c.status = 0, "dead"
    batt.winner = "player"
    app._battle_end(batt)
    assert m.state == "done" and "faith_battlefield" in guild.deeds_done
    assert app._skirmish is None
    assert any("Faith Order" in n for n in app._map_notices)


def test_without_the_errand_the_skirmish_does_not_open():
    guild, _ = _guild(node="battlefield")
    app = _app(guild)
    app._enter_battle = lambda battle, node: (_ for _ in ()).throw(AssertionError("no fight"))
    app._enter_skirmish(guild.groups[0], world.node("battlefield"))
    assert app._skirmish is None


def test_battlefield_defeated_enemies_can_drop_scroll_of_spare_the_dying():
    from gartok import loot
    _guild_obj, squad = _guild(node="battlefield")
    batt, _sc = _skirmish(squad)
    for foe in batt.enemy_units:
        foe.hp, foe.status = 0, "dead"

    class AlwaysRoll:
        def random(self):
            return 0.0005

    class NeverRoll:
        def random(self):
            return 0.5

    drop_pool = loot.field_loot(batt, [], rng=AlwaysRoll())
    assert loot.SPARE_THE_DYING_SCROLL in drop_pool

    no_drop_pool = loot.field_loot(batt, [], rng=NeverRoll())
    assert loot.SPARE_THE_DYING_SCROLL not in no_drop_pool
