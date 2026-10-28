"""The errands' fights in the browser: the Faith Order's skirmish at the Battlefield (and the necromancer's
night), the Wildfire's camps, the Great Focus and the hostile fortress, each behind the wagon's watch,
fought as a campaign fight and settled as pygame settles them."""

import pytest

from gartok import missions, orders, persist, recorder, wildfire, world
from gartok.battlefield import BattlefieldScenario
from gartok.clock import Clock
from gartok.fortress_scenario import FortressScenario
from gartok.guild import Guild
from gartok.necromancer import NecromancerScenario
from gartok.scenario import ErmosScenario
from gartok.wagon import Wagon
from gartok.web.battle_session import BattleSession
from gartok.web.hub_session import HUB_KINDS
from gartok.web.map_session import MapSession
from gartok.web.report_session import ReportSession
from gartok.web.server import Game
from gartok.web.watch_session import WatchSession
from tests.helpers import standard_unit


@pytest.fixture(autouse=True)
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    yield tmp_path
    recorder.detach()


def _guild(node, *done, n=3):
    members = [standard_unit() for _ in range(n)]
    for i, u in enumerate(members):
        u.name = f"Pilgrim {i}"
        u.give_to_pack("Meat", 30)
    guild = Guild(members, node=node, clock=Clock(10 * 3600))
    for t in (missions.LIBRARY_ANCIENT_CODEX, *done):
        guild.missions.append(missions.Mission(t.id, members[0].uid, 0, None, state="done"))
    guild.reveal_node(node)
    return guild, guild.groups[0]


def _front(template=missions.FAITH_BATTLEFIELD):
    done = (missions.FAITH_BATTLEFIELD,) if template is missions.FAITH_NECROMANCER else ()
    guild, g = _guild("faith_cathedral", *done)
    m = missions.accept(guild, g.members[0], template)
    g.node = "battlefield"
    return guild, g, m


def _wildfire():
    guild, g = _guild("nature_grove")
    m = missions.accept(guild, g.members[0], missions.NATURE_WILDFIRE)
    return guild, g, m


def _end(game, won=True, dead=()):
    b = game.session.battle
    for c in [*(b.foe_units if won else b.player_units), *dead]:
        c.hp, c.status = 0, "dead"
    b.winner = "player" if won else "enemy"
    game.session.done()
    report = game.session
    assert isinstance(report, ReportSession)
    while game.session is report:
        st = report.next()
    return st


def test_every_activity_the_campaign_reaches_has_a_screen_in_the_browser():
    played = {"arena", "hunt", "ox_hunt", "ancient_ruins", "serpents_nest", "dragon_lair",
              "skirmish", "camp_fight", "ogre_fight"}
    assert orders.INTERACTIVE_KINDS <= HUB_KINDS | played
    guild, g = _guild("city")
    with pytest.raises(ValueError):
        MapSession(guild)._enter(g, type("O", (), {"kind": "nowhere"})())


def test_the_skirmish_opens_the_trenches_with_the_soldiers_at_the_bands_side():
    guild, g, _m = _front()
    game = Game(MapSession(guild, "w1"))
    assert game.session.act(g.gid, "skirmish") == {"screen": "battle"}
    s = game.session
    assert isinstance(s, BattleSession) and isinstance(s.battle.scenario, BattlefieldScenario)
    b = s.battle
    assert b.aggressor == "enemy" and b.daylight == guild.clock.is_daylight
    assert {c.char for c in b.player_units if not c.ai_ally} == set(g.members)
    assert len([c for c in b.player_units if c.ai_ally]) == 4
    assert s.state()["campaign"] and s.state()["meta"]["sub"].startswith("Mercy at the Front")
    assert any(x["kind"] == "auto" for x in persist.list_saves("w1"))


def test_every_soldier_home_settles_the_errand_with_the_faith_orders_deed():
    guild, g, m = _front()
    game = Game(MapSession(guild))
    game.session.act(g.gid, "skirmish")
    st = _end(game)
    assert st["screen"] == "map" and m.state == "done"
    assert any("Every soldier came through" in n for n in st["notices"])
    assert any("faith" in n.lower() for n in st["notices"][1:])


def test_a_soldier_lost_fails_the_errand_even_on_a_win():
    guild, g, m = _front()
    game = Game(MapSession(guild))
    game.session.act(g.gid, "skirmish")
    soldier = next(c for c in game.session.battle.player_units if c.ai_ally)
    st = _end(game, dead=[soldier])
    assert m.state == "failed" and any("did not come home" in n for n in st["notices"])


def test_once_the_necromancer_is_out_the_skirmish_is_his_night_and_his_fall_meets_it():
    guild, g, m = _front(missions.FAITH_NECROMANCER)
    game = Game(MapSession(guild))
    game.session.act(g.gid, "skirmish")
    b = game.session.battle
    assert isinstance(b.scenario, NecromancerScenario) and "undead" in b.teams
    assert game.session.state()["meta"]["sub"].startswith("The necromancer")
    b.scenario.caster_down = True
    _end(game)
    assert m.state == "done"


def test_a_band_with_no_errand_at_the_front_is_back_on_the_map():
    guild, g = _guild("battlefield")
    game = Game(MapSession(guild))
    t0 = guild.clock.seconds
    st = game.session.act(g.gid, "skirmish")
    assert st["screen"] == "map" and isinstance(game.session, MapSession) and guild.clock.seconds == t0


def test_the_wagon_needs_a_watch_and_the_guards_stay_out_of_the_skirmish():
    guild, g, _m = _front()
    g.add_wagon(Wagon())
    game = Game(MapSession(guild))
    assert game.session.act(g.gid, "skirmish") == {"screen": "watch"}
    s = game.session
    assert isinstance(s, WatchSession)
    assert s.state()["label"] == "Join the skirmish" and "soldiers" in s.state()["lead"]
    guard = g.members[2]
    s.toggle(guard.uid)
    assert s.go() == {"screen": "battle"}
    fighters = {c.char for c in game.session.battle.player_units if not c.ai_ally}
    assert guard not in fighters and len(fighters) == 2
    _end(game)
    assert g.wagons


def test_attacking_a_camp_opens_its_crew_and_a_win_leaves_the_fire_to_put_out():
    guild, g, _m = _wildfire()
    focus = next(f for f in guild.wildfire.foci if not f.great)
    g.node = focus.id
    game = Game(MapSession(guild))
    assert game.session.act(g.gid, "camp_fight") == {"screen": "battle"}
    b = game.session.battle
    assert isinstance(b.scenario, ErmosScenario) and b.aggressor == "player"
    assert sorted(u.race["name"] for u in b.enemy_units) == ["Goblin"] * 3 + ["Hobgoblin"]
    assert game.session.state()["meta"]["sub"].startswith("The goblin camp")
    st = _end(game)
    assert focus.cleared and any("put it out" in n for n in st["notices"])


def test_a_cleared_camp_opens_no_fight():
    guild, g, _m = _wildfire()
    focus = next(f for f in guild.wildfire.foci if not f.great)
    wildfire.settle_fight(guild, focus.id, won=True)
    g.node = focus.id
    game = Game(MapSession(guild))
    assert game.session.act(g.gid, "camp_fight")["screen"] == "map"


def test_the_great_focus_is_the_ogres_fortress_and_his_fall_ends_the_errand():
    guild, g, m = _wildfire()
    g.node = wildfire.GREAT_ID
    game = Game(MapSession(guild))
    game.session.act(g.gid, "ogre_fight")
    b = game.session.battle
    assert isinstance(b.scenario, FortressScenario) and not b.scenario.finished
    assert wildfire.ogre_of(b) is not None
    st = _end(game)
    assert m.state == "done" and any("The Ogre is beaten" in n for n in st["notices"])


def test_the_hostile_fortress_left_standing_falls_to_a_won_fight():
    guild, g, _m = _wildfire()
    for _ in range(wildfire.DAYS):
        guild.pass_time(24)
    assert wildfire.hold_standing(guild)
    g.node = wildfire.FORTRESS_ID
    game = Game(MapSession(guild))
    game.session.act(g.gid, "ogre_fight")
    assert isinstance(game.session.battle.scenario, FortressScenario) and game.session.battle.scenario.finished
    _end(game)
    assert not wildfire.hold_standing(guild) and not world.exists(wildfire.FORTRESS_ID)


def test_a_lost_fight_at_a_camp_leaves_it_burning():
    guild, g, _m = _wildfire()
    focus = next(f for f in guild.wildfire.foci if not f.great)
    g.node = focus.id
    game = Game(MapSession(guild))
    game.session.act(g.gid, "camp_fight")
    _end(game, won=False)
    assert not focus.cleared
