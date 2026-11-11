"""The Cult Site fight (`cult_site.CultSiteScenario`): the bar, the Final Rite, its interruption and the
Demon's non-lethal ending. Fights are driven by hand: no AI plays them."""


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


def _fight(game, g, verb="attack"):
    """The site's talk, ended with `verb` (a plain ATTACK: no roll), up to the battle screen."""
    assert game.session.act(g.gid, "cult_ritual") == {"screen": "talk"}
    game.session.choose(verb)
    assert game.session.go_on() == {"screen": "battle"}
    return game.session.battle


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
    _fight(game, g)
    s = game.session
    assert isinstance(s, BattleSession) and isinstance(s.battle.scenario, CultSiteScenario)
    state = s.state()
    assert state["ritual"]["max"] == BAR_MAX and "rite" in state["ritual"]["text"].lower()
    assert {"rune", "bound"} <= {p["kind"] for p in state["props"]}


def test_winning_frees_the_daughter(at_the_site):
    guild, g, _m = at_the_site
    game = Game(MapSession(guild))
    _fight(game, g)
    _finish(game, won=True)
    assert guild.cult["state"] == "won" and guild.cult["freed"]
    girl = g.captives[0]
    assert girl.ward and girl.npc_slug == "farmers_daughter"


def test_the_closed_rite_is_a_defeat_nobody_dies_from_and_the_site_is_searched_after(at_the_site):
    guild, g, _m = at_the_site
    game = Game(MapSession(guild))
    b = _fight(game, g)
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


# --- the AI ------------------------------------------------------------------------------------------

from gartok import ai


def play_enemies(battle, turns):
    """The cult's turns by the AI while the squad stands still; stops when the fight is decided."""
    for _ in range(turns):
        if battle.winner is not None:
            break
        act = battle.active
        if not act.alive:
            battle.end_turn()
        elif act.team == "player":
            battle.end_turn()
        else:
            ai.take_turn(battle, act)


def far_squad(battle):
    for i, c in enumerate(battle.player_units):
        c.pos = (1, 1 + 3 * i)


def test_left_alone_the_cult_fills_the_bar_and_closes_the_rite_without_killing_anyone():
    battle, scenario = fight()
    far_squad(battle)
    for slug in cult_site.FIGHTERS:
        who(battle, slug).status = "stable"           # the blades would walk over and end the squad first
    play_enemies(battle, 400)
    assert battle.winner == "enemy" and scenario.demon_came
    assert all(c.status == "stable" for c in battle.player_units)


def test_a_channeler_pushed_off_its_point_walks_back_before_anything_else():
    battle, scenario = fight()
    far_squad(battle)
    blood = who(battle, cult_site.CHANNELERS[0])
    who(battle, cult_site.LEADER).status = "stable"           # else he takes the empty point first
    blood.pos = (POINTS[0][0] + 2, POINTS[0][1])
    while battle.active is not blood:
        battle.end_turn() if battle.active.team == "player" or not battle.active.alive else ai.take_turn(battle, battle.active)
    battle.active.ap = 2
    ai.take_turn(battle, blood)
    assert blood.pos == POINTS[0]


def test_with_a_channeler_down_the_leader_takes_the_empty_point():
    battle, scenario = fight()
    far_squad(battle)
    downed = who(battle, cult_site.CHANNELERS[1])
    downed.status = "stable"
    leader = who(battle, cult_site.LEADER)
    assert scenario.ai_post(battle, leader) == POINTS[1]
    leader.pos = (POINTS[1][0], POINTS[1][1] - 2)
    leader.ap = 2
    ai.take_turn(battle, leader) if battle.active is leader else None
    assert scenario.ai_post(battle, leader) == POINTS[1]


def test_a_full_bar_sends_the_leader_to_the_centre_and_he_spends_the_turn_there():
    battle, scenario = fight()
    far_squad(battle)
    scenario.bar = BAR_MAX
    leader = who(battle, cult_site.LEADER)
    assert scenario.ai_post(battle, leader) == CENTRE
    leader.pos = CENTRE
    assert scenario.ai_must_stay(battle, leader)


def test_a_channeler_with_no_foe_in_reach_holds_its_point_and_ends_the_turn():
    from gartok.ai.scripted import _channel
    battle, scenario = fight()
    far_squad(battle)
    blood = who(battle, cult_site.CHANNELERS[0])
    assert _channel(battle, blood) == "hold"
    battle.player_units[0].pos = (blood.pos[0] + 1, blood.pos[1])
    assert _channel(battle, blood) is None


# --- the talk before the fight ----------------------------------------------------------------------

from gartok import dialogue


def test_persuade_is_closed_and_the_rest_are_offered(at_the_site):
    guild, g, _m = at_the_site
    game = Game(MapSession(guild))
    game.session.act(g.gid, "cult_ritual")
    st = game.session.state()
    assert st["kind"] == "cult"
    options = {o["verb"]: o for o in st["options"]}
    assert set(options) == {"persuade", "bluff", "intimidate", "let_proceed", "attack"}
    assert options["persuade"]["block"]


def test_letting_the_rite_run_is_no_fight_and_the_girl_is_lost(at_the_site):
    guild, g, _m = at_the_site
    game = Game(MapSession(guild))
    game.session.act(g.gid, "cult_ritual")
    game.session.choose("let_proceed")
    assert game.session.go_on()["screen"] == "map"
    assert guild.cult["state"] == "failed" and guild.cult["remains"] == [items.HOLY_SYMBOL_ITEM]
    assert len(guild.roster) == 3


def test_a_won_bluff_surprises_and_a_won_intimidate_demoralizes():
    enc = dialogue.CultTalk(cult_site.cultists())
    speaker = standard_unit()
    bluff = enc._checked("bluff", speaker, True, 3, "x")
    assert bluff.kind == "fight" and bluff.opening.surprised == "enemy"
    scare = enc._checked("intimidate", speaker, True, 3, "x")
    assert scare.opening.demoralized == "enemy"
    assert not cult_site.head_start(bluff.opening) and not cult_site.head_start(scare.opening)


def test_a_missed_talk_gives_the_rite_its_head_start():
    enc = dialogue.CultTalk(cult_site.cultists())
    miss = enc._checked("bluff", standard_unit(), False, -3, "x")
    assert miss.kind == "fight" and cult_site.head_start(miss.opening)
    assert CultSiteScenario(head_start=True).bar == STEP
    assert CultSiteScenario().bar == 0
    assert not cult_site.head_start(None)


def test_the_ward_row_shows_in_the_bands_sheet(at_the_site):
    guild, g, _m = at_the_site
    guild.cult["state"] = "won"
    cult_site.free_daughter(guild, g)
    assert cult_site.free_daughter(guild, g) is None and len(g.captives) == 1
    from gartok.web.guild_session import GuildSession
    state = GuildSession(MapSession(guild), "bands", g.gid).state()
    rows = [c for band in str(state).split("'captives': ")[1:] for c in [band]]
    assert "'ward': True" in rows[0] and "'days': None" in rows[0]
