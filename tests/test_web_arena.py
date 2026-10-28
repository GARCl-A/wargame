"""The arena in the browser: the bouts, who fights and the stake, the boss's lines, the bout on the board, the
purse on the report, the offer to recruit the fallen, and the champion's title defense."""

import json
import random
import threading
import urllib.request

import pytest

from gartok import persist, recorder
from gartok.group import Group
from gartok.guild import Guild
from gartok.unit import Unit
from gartok.web.arena_session import ArenaSession
from gartok.web.battle_session import BattleSession
from gartok.web.dialogue_session import DialogueSession
from gartok.web.hub_session import HubSession
from gartok.web.map_session import MapSession
from gartok.web.report_session import ReportSession
from gartok.web.server import Game, serve


@pytest.fixture(autouse=True)
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    yield tmp_path
    recorder.detach()


def _guild(n=3, money=50):
    random.seed(4)
    units = [Unit("Fighter") for _ in range(n)]
    for u in units:
        u.money = money
        u.give_to_pack("Potato", 6)
    g = Group(units, node="arena", leader=units[0])
    return Guild(None, groups=[g], name="Ink Hands"), g


def _arena(guild, g, world_id=None):
    game = Game(MapSession(guild, world_id))
    assert game.session.act(g.gid, "arena") == {"screen": "arena"}
    return game, game.session


def _end(session, won=True):
    b = session.battle
    for c in (b.foe_units if won else b.player_units):
        c.hp, c.status = 0, "dead"
    b.winner = "player" if won else "enemy"
    return session.done()


def _through_report(game, payee=None):
    report = game.session
    assert isinstance(report, ReportSession)
    while game.session is report:
        if report.stage[0] == "purse":
            report.give(payee.uid)
        report.next()


def test_the_bouts_follow_the_arenas_story():
    guild, g = _guild()
    _, s = _arena(guild, g)
    assert [b["name"] for b in s.state()["bouts"]] == ["The Pit: Scrapper", "Challenge the Champion"]
    guild.deeds_done.append("arena_dethrone")
    names = [b["name"] for b in ArenaSession(s.map, g).state()["bouts"]]
    assert names == ["The Pit: Scrapper", "Games: Brawl", "Games: Capture the Flag", "Games: The Ribbit Brothers"]
    guild.deeds_done.append("arena_ribbit_brothers")
    assert "Games: The Ribbit Brothers" not in [b["name"] for b in ArenaSession(s.map, g).state()["bouts"]]


def test_a_band_that_fits_the_bout_is_picked_whole_and_the_stake_is_a_head():
    guild, g = _guild()
    _, s = _arena(guild, g)
    st = s.state()
    assert all(m["picked"] for m in st["members"]) and st["why"] is None
    assert st["stake"]["cost"] == 3 * 3 and st["stake"]["cap"] == 3
    s.toggle(g.members[0].uid)
    assert s.state()["stake"]["cost"] == 2 * 3


def test_the_cap_the_trim_and_the_unfit():
    guild, g = _guild(n=4)
    _, s = _arena(guild, g)
    assert s.state()["why"] == "Pick who fights"
    for u in g.members[:3]:
        s.toggle(u.uid)
    with pytest.raises(ValueError, match="at most 3"):
        s.toggle(g.members[3].uid)
    guild.deeds_done.append("arena_dethrone")
    s = ArenaSession(s.map, g)
    s.pick_bout(3)                                   # the Ribbit Brothers: six a side
    for u in g.members:
        s.toggle(u.uid)
    assert len(s.picked) == 4
    s.pick_bout(1)                                   # the Brawl: three a side drops the fourth
    assert len(s.picked) == 3
    g.members[3].unfed_days = 3
    s.toggle(g.members[0].uid)
    with pytest.raises(ValueError, match="hunger"):
        s.toggle(g.members[3].uid)
    assert any(m["unfit"] for m in s.state()["members"])


def test_a_stake_the_band_cannot_pay_is_refused():
    guild, g = _guild(money=1)
    _, s = _arena(guild, g)
    assert "of the $9 stake" in s.state()["why"]
    with pytest.raises(ValueError, match="stake"):
        s.fight()


def test_a_scrapper_bout_won_pays_the_purse_and_ends_on_the_map():
    guild, g = _guild()
    game, s = _arena(guild, g, "w1")
    held = g.money
    assert s.fight() == {"screen": "battle"}
    b = game.session
    assert isinstance(b, BattleSession) and b.battle.arena and len(b.battle.foe_units) == 3
    assert b.state()["meta"]["sub"].startswith("The Pit: Scrapper")
    assert g.money == held - 9
    assert any(x["kind"] == "auto" for x in persist.list_saves("w1"))
    assert _end(b) == {"screen": "report"}
    assert game.session.stages[-2][0] == "purse"
    _through_report(game, g.members[1])
    assert game.session.screen == "map"
    assert g.money == held - 9 + 11 and "obj_arena_bout" in guild.objectives_done


def test_a_bout_lost_has_no_purse_and_ends_on_the_map():
    guild, g = _guild()
    game, s = _arena(guild, g)
    s.fight()
    _end(game.session, won=False)
    report = game.session
    assert all(k != "purse" for k, _ in report.stages)
    _through_report(game)
    assert game.session.screen == "map"


def test_the_champion_speaks_once_then_falls_and_may_be_recruited():
    guild, g = _guild()
    game, s = _arena(guild, g)
    s.pick_bout(1)
    assert s.fight() == {"screen": "talk"}
    talk = game.session
    assert isinstance(talk, DialogueSession) and talk.state()["kind"] == "boss"
    assert "champion" in guild.boss_talks_seen
    while game.session is talk:
        talk.go_on()
    b = game.session
    assert isinstance(b, BattleSession) and any(c.name.startswith("Adelio") for c in b.battle.foe_units)
    _end(b)
    _through_report(game, g.members[0])
    offer = game.session
    assert isinstance(offer, ArenaSession) and offer.state()["recruit"]["who"] == "adelio"
    with pytest.raises(ValueError):
        offer.fight()
    assert offer.recruit() == {"screen": "hub"}
    hub = game.session
    assert isinstance(hub, HubSession) and [t["key"] for t in hub.state()["tabs"]] == ["recruits"]
    strangers = hub.state()["tavern"]["strangers"]
    assert [x["name"] for x in strangers] == ["Adelio Small-Knife"]
    assert hub.verb("back", True)(hub, {})["screen"] == "map"
    assert "arena_dethrone" in guild.deeds_done


def test_the_offer_can_be_turned_down():
    guild, g = _guild()
    game, s = _arena(guild, g)
    guild.boss_talks_seen.add("champion")
    s.pick_bout(1)
    assert s.fight() == {"screen": "battle"}       # the lines were heard before
    _end(game.session)
    _through_report(game, g.members[0])
    assert game.session.leave()["screen"] == "map"


def test_a_due_defense_with_the_champion_here_goes_straight_to_the_board():
    guild, g = _guild()
    champ = g.members[1]
    champ.arena_title = True
    guild.arena_challenge_day = guild.clock.day
    game = Game(MapSession(guild))
    assert game.session.act(g.gid, "arena") == {"screen": "battle"}
    b = game.session.battle
    assert [c.char for c in b.player_units] == [champ] and len(b.foe_units) == 1 and not b.lethal


def test_a_due_defense_with_the_champion_elsewhere_shows_the_bouts_and_says_so():
    guild, g = _guild()
    away = Unit("Fighter")
    away.arena_title = True
    guild.groups.append(Group([away], node="city", leader=away))
    guild.arena_challenge_day = guild.clock.day
    _, s = _arena(guild, g)
    assert away.name in s.state()["defense"]["line"]


def test_the_server_routes_the_arena(saves):
    guild, _ = _guild()
    persist.save_game("w1", guild)
    srv = serve(Game.from_save("w1"))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"

    def post(verb, body):
        req = urllib.request.Request(url + verb, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    try:
        gid = json.loads(urllib.request.urlopen(url + "/api/map/state").read())["groups"][0]["gid"]
        assert post("/api/map/act", {"gid": gid, "key": "arena"}) == {"screen": "arena"}
        st = json.loads(urllib.request.urlopen(url + "/api/arena/state").read())
        assert st["bouts"][0]["picked"]
        assert post("/api/arena/bout", {"i": 1})["bouts"][1]["picked"]
        assert post("/api/arena/back", {})["screen"] == "map"
    finally:
        srv.shutdown()
