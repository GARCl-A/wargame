"""The Cult Site fight (`cult_site.CultSiteScenario`): the bar, the Final Rite, its interruption and the
Demon's non-lethal ending. Fights are driven by hand: no AI plays them."""

import random

import pytest

from gartok import cult_site, items, world
from gartok.battle import Battle
from gartok.cult_site import BAR_MAX, CENTRE, POINTS, STEP, CultSiteScenario
from tests.helpers import standard_unit


def fight(squad_size=3):
    squad = [standard_unit() for _ in range(squad_size)]
    for i, u in enumerate(squad):
        u._name = f"Hero{i}"
    scenario = CultSiteScenario(squad)
    battle = Battle(squad, scenario.enemies, scenario=scenario, daylight=True, lethal=True, aggressor="player")
    scenario.bar = 0                    # the first turn of the fight may already have fed the rite
    return battle, scenario


def who(battle, slug):
    return next(u for u in battle.enemy_units if cult_site.slug_of(u) == slug)


def test_the_six_cultists_stand_where_the_design_puts_them():
    battle, scenario = fight()
    assert len(battle.enemy_units) == 6
    for slug, point in zip(cult_site.CHANNELERS, POINTS):
        assert who(battle, slug).pos == point
    assert who(battle, cult_site.LEADER).pos not in POINTS
    assert scenario.bar == 0 and scenario.daughter_alive
    assert {p["kind"] for p in scenario.props(battle)} == {"rune", "bound"}


def test_a_channeler_on_a_point_adds_one_a_turn_without_an_action():
    battle, scenario = fight()
    blood = who(battle, cult_site.CHANNELERS[0])
    scenario.on_turn_start(battle, blood)
    assert scenario.bar == 1
    blood.pos = (0, 0)
    scenario.on_turn_start(battle, blood)
    assert scenario.bar == 1


@pytest.mark.parametrize("cond", ["sleeping", "routed"])
def test_a_sleeping_or_routed_channeler_adds_nothing(cond):
    from gartok import conditions
    battle, scenario = fight()
    c = who(battle, cult_site.CHANNELERS[1])
    c.add_condition({"sleeping": conditions.Sleeping, "routed": conditions.Routed}[cond]())
    scenario.on_turn_start(battle, c)
    assert scenario.bar == 0


def test_a_downed_channeler_adds_nothing_but_a_demoralized_one_does():
    from gartok import conditions
    battle, scenario = fight()
    c = who(battle, cult_site.CHANNELERS[2])
    c.add_condition(conditions.Demoralized())
    scenario.on_turn_start(battle, c)
    assert scenario.bar == 1
    c.status = "stable"
    scenario.on_turn_start(battle, c)
    assert scenario.bar == 1


def fill(battle, scenario):
    scenario.bar = BAR_MAX
    leader = who(battle, cult_site.LEADER)
    leader.pos = CENTRE
    return leader


def test_the_leader_begins_the_rite_at_the_end_of_a_turn_at_the_centre_and_closes_it_on_the_next():
    battle, scenario = fight()
    leader = fill(battle, scenario)
    scenario.on_turn_end(battle, leader)
    assert scenario.rite_began and not scenario.demon_came
    assert scenario.hud(battle)["closing"]
    scenario.on_turn_start(battle, leader)
    assert scenario.demon_came and battle.winner == "enemy"


def test_a_rite_stopped_before_it_closes_falls_back_one_step():
    battle, scenario = fight()
    leader = fill(battle, scenario)
    scenario.on_turn_end(battle, leader)
    leader.status = "stable"
    assert scenario.win_check(battle) is None
    assert scenario.bar == BAR_MAX - STEP and not scenario.rite_began


def test_a_leader_pushed_off_the_centre_also_breaks_it():
    battle, scenario = fight()
    leader = fill(battle, scenario)
    scenario.on_turn_end(battle, leader)
    leader.pos = (CENTRE[0] + 1, CENTRE[1])
    scenario.win_check(battle)
    assert scenario.bar == BAR_MAX - STEP


def test_a_broken_rite_can_be_closed_again_after_the_bar_refills():
    battle, scenario = fight()
    leader = fill(battle, scenario)
    scenario.on_turn_end(battle, leader)
    leader.pos = (0, 0)
    scenario.win_check(battle)
    assert scenario.bar == 12
    for _ in range(STEP):
        scenario.on_turn_start(battle, who(battle, cult_site.CHANNELERS[0]))
    assert scenario.bar == BAR_MAX


def test_the_demon_ends_the_fight_with_nobody_dead_and_the_daughter_lost():
    battle, scenario = fight()
    hero = battle.player_units[0]
    fallen = battle.player_units[1]
    fallen.status = "dead"
    leader = fill(battle, scenario)
    scenario.on_turn_end(battle, leader)
    scenario.on_turn_start(battle, leader)
    assert battle.winner == "enemy"
    assert hero.status == "stable" and hero.survived
    assert fallen.status == "dead"
    assert not scenario.daughter_alive
    assert all(u.status != "dying" for u in battle.units)


def test_every_step_of_the_ritual_is_in_the_battle_log():
    battle, scenario = fight()
    scenario.on_turn_start(battle, who(battle, cult_site.CHANNELERS[0]))
    assert any("feeds the rite" in str(line) for line in battle.log_lines)


def test_failed_settle_leaves_the_symbol_and_the_dead_kits_to_search():
    battle, scenario = fight()
    guild = type("G", (), {"cult": {}})()
    dead = battle.player_units[1]
    dead.status = "dead"
    dead.inventory.append("Torch")
    leader = fill(battle, scenario)
    scenario.on_turn_end(battle, leader)
    scenario.on_turn_start(battle, leader)
    notice = cult_site.settle_fight(guild, battle)
    assert notice and guild.cult["state"] == "failed"
    assert items.HOLY_SYMBOL_ITEM in guild.cult["remains"] and "Torch" in guild.cult["remains"]


def test_won_settle_marks_the_daughter_freed():
    battle, scenario = fight()
    guild = type("G", (), {"cult": {}})()
    battle.winner = "player"
    cult_site.settle_fight(guild, battle)
    assert guild.cult["state"] == "won"


# --- the fight as the campaign plays it -------------------------------------------------------------

from gartok import missions, persist, recorder
from gartok.clock import SECONDS_PER_DAY
from gartok.group import Group
from gartok.guild import Guild
from gartok.web.battle_session import BattleSession
from gartok.web.map_session import MapSession
from gartok.web.report_session import ReportSession
from gartok.web.server import Game


@pytest.fixture
def at_the_site(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    monkeypatch.setattr(missions, "FARMER_QUEST_LIVE", True)
    members = [standard_unit() for _ in range(3)]
    guild = Guild(members)
    guild.groups = [Group(members, "farm")]
    guild.clock.seconds = 30 * SECONDS_PER_DAY
    guild.revealed |= {"faith_cathedral"}
    mission = missions.accept(guild, members[0], missions.FARMER_DAUGHTER)
    cult_site.reveal(guild)
    guild.groups[0].node = cult_site.NODE
    yield guild, guild.groups[0], mission
    world.remove_node(cult_site.NODE)
    recorder.detach()


def _finish(game, won):
    b = game.session.battle
    if won:
        for c in b.foe_units:
            c.hp, c.status = 0, "dead"
        b.winner = "player"
    game.session.done()
    report = game.session
    assert isinstance(report, ReportSession)
    while game.session is report:
        st = report.next()
    return st


def test_the_site_opens_the_fight_with_the_rite_hud(at_the_site):
    guild, g, _m = at_the_site
    game = Game(MapSession(guild))
    assert game.session.act(g.gid, "cult_ritual") == {"screen": "battle"}
    s = game.session
    assert isinstance(s, BattleSession) and isinstance(s.battle.scenario, CultSiteScenario)
    state = s.state()
    assert state["ritual"]["max"] == BAR_MAX and "rite" in state["ritual"]["text"].lower()
    assert {"rune", "bound"} <= {p["kind"] for p in state["props"]}


def test_winning_frees_the_daughter(at_the_site):
    guild, g, _m = at_the_site
    game = Game(MapSession(guild))
    game.session.act(g.gid, "cult_ritual")
    _finish(game, won=True)
    assert guild.cult["state"] == "won"


def test_the_closed_rite_is_a_defeat_nobody_dies_from_and_the_site_is_searched_after(at_the_site):
    guild, g, _m = at_the_site
    game = Game(MapSession(guild))
    game.session.act(g.gid, "cult_ritual")
    b = game.session.battle
    leader = fill(b, b.scenario)
    b.scenario.on_turn_end(b, leader)
    b.scenario.on_turn_start(b, leader)
    st = _finish(game, won=False)
    assert st["screen"] == "map"
    assert guild.cult["state"] == "failed" and len(guild.roster) == 3
    game = Game(MapSession(guild))
    game.session.act(g.gid, "cult_ritual")
    assert items.HOLY_SYMBOL_ITEM in g.members[0].inventory
    assert guild.cult["remains"] == []


def test_a_cold_site_holds_nothing(at_the_site):
    guild, g, _m = at_the_site
    guild.cult["state"] = "won"
    game = Game(MapSession(guild))
    assert game.session.act(g.gid, "cult_ritual")["screen"] == "map"


def test_the_guild_keeps_the_cult_state_in_its_save(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    guild = Guild([standard_unit()])
    guild.cult = {"state": "failed", "remains": ["Torch"]}
    persist.save_game("w", guild)
    assert persist.load_game("w").cult == guild.cult
