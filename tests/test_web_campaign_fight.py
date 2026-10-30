"""A campaign fight in the browser: entered from the map, the talk or the Claim, played on the board,
settled as `app_battle` settles it and handed to the report, which ends on the map."""

import random

import pytest

from gartok import ai, economy, orders, persist, recorder, vocations, world
from gartok.group import Group
from gartok.guild import Guild
from gartok.unit import Unit
from gartok.web.battle_session import BattleSession
from gartok.web.map_session import MapSession
from gartok.web.report_session import ReportSession
from gartok.web.server import Game, Lab


@pytest.fixture(autouse=True)
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    yield tmp_path
    recorder.detach()


def _band(node, n=3, lang="Common"):
    random.seed(4)
    units = [Unit("Fighter") for _ in range(n)]
    for u in units:
        u.languages = [lang]
        u.give_to_pack("Potato", 6)
    return Group(units, node=node, leader=units[0])


def _ambushed(world_id=None, lang=None):
    g = _band("road")
    guild = Guild(None, groups=[g], name="Ink Hands")
    random.seed(5)
    pack = [Unit("enemy") for _ in range(2)]
    for u in pack:
        u.languages = [lang] if lang else []
    g.pending = orders.Order("ambush", pack=tuple(pack))
    return Game(MapSession(guild, world_id)), guild, g


def _win(session):
    b = session.battle
    for c in b.foe_units:
        c.hp, c.status = 0, "dead"
    b.winner = "player"


def test_a_fight_with_nobody_to_talk_to_opens_the_board_and_the_report_ends_on_the_map():
    game, _, g = _ambushed("w1")
    assert game.session.act(g.gid, "resolve_event") == {"screen": "battle"}
    s = game.session
    assert isinstance(s, BattleSession) and s.state()["campaign"] and s.state()["meta"]["name"] == "Old Road"
    assert any(x["kind"] == "auto" for x in persist.list_saves("w1"))
    with pytest.raises(ValueError):
        s.done()
    _win(s)
    assert s.done() == {"screen": "report"}
    report = game.session
    assert isinstance(report, ReportSession) and report.state()["result"] == "VICTORY"
    assert not g.fight_due and g.pending is None
    while game.session is report:
        report.next()
    assert game.session.screen == "map" and not persist.load_game("w1").groups[0].fight_due


def test_a_campaign_fight_binds_the_guilds_bestiary_and_the_scholars_bonus():
    game, guild, g = _ambushed()
    guild.vocation = vocations.SCHOLARS
    game.session.act(g.gid, "resolve_event")
    intel = game.session.battle.intel
    assert intel.bestiary["player"] is guild.bestiary and intel.bonus["player"] == vocations.INFO_BONUS
    assert intel.bestiary["enemy"] is None and intel.bonus["enemy"] == 0


def test_a_fight_played_out_by_the_ai_on_both_sides_is_settled():
    game, _, g = _ambushed()
    game.session.act(g.gid, "resolve_event")
    s = game.session
    b = s.battle
    for _ in range(400):
        if b.winner is not None:
            break
        if s._setup() == "trap":
            s.act("skip_traps")
        elif s.my_turn():
            s._stepped(lambda: ai.take_turn(b, b.active), None)     # a stand-in player
        else:
            s.advance()
    assert s.battle.winner is not None
    assert s.done() == {"screen": "report"} and not g.fight_due


def test_a_talk_that_ends_in_a_fight_opens_the_board_with_how_it_ended(monkeypatch):
    game, _, g = _ambushed(lang="Common")
    assert game.session.act(g.gid, "resolve_event") == {"screen": "talk"}
    monkeypatch.setattr(random, "randint", lambda a, b: 1)
    assert game.session.choose("bluff")["result"]["kind"] == "fight"
    assert game.session.go_on() == {"screen": "battle"}
    b = game.session.battle
    assert b.opening["surprised"] == "player"


def test_the_claims_fight_won_moves_the_claim_a_stage():
    g = _band(world.WILDS_TERRITORY_NODE)
    for u in g.members:
        u.money = 200
    guild = Guild(None, groups=[g], name="Ink Hands")
    guild.wilds_claim_stage = "SCOUTED"
    game = Game(MapSession(guild))
    game.session.act(g.gid, "visit_claim")
    hub = game.session
    assert hub.verb("claim_fight", True)(hub, {"verb": "fight_clear"}) == {"screen": "battle"}
    s = game.session
    assert len(s.battle.foe_units) == economy.WILDS_CLAIM_CLEAR_SIZE
    _win(s)
    s.done()
    assert guild.wilds_claim_stage == "CLEARED"
    assert any("now Cleared" in n for n in game.session.map.notices)


def test_a_lab_fight_has_nothing_after_it():
    s = Lab().fight("wilds", 1, 2, seed=3)
    with pytest.raises(ValueError):
        s.done()
    assert not s.state()["campaign"]


def _stomp(session, eligible=True):
    """Settle the fight's estimate without running it: the map's `Look` answers as if it had finished."""
    from gartok import autowin
    session.look.estimator.result = autowin.AutoWinResult(
        eligible=eligible, iterations=5, win_rate=1.0, stomp_rate=1.0 if eligible else 0.4,
        avg_damage={u.uid: 2.0 for u in session.guild.roster}, avg_rounds=3.0)


def test_a_clean_stomp_settles_the_ambush_unplayed_with_no_xp_and_the_band_worn():
    game, guild, g = _ambushed("w1")
    s = game.session
    cta = s.state()["cta"]
    assert cta["swift"]["computing"] or cta["swift"]["eligible"] is not None
    hp = {u.uid: u.hp for u in g.members}
    xp = {u.uid: u.combat_xp for u in g.members}
    _stomp(s)
    assert s.state()["cta"]["swift"]["eligible"]
    assert s.act(g.gid, "swift_win") == {"screen": "report"}
    report = game.session
    assert isinstance(report, ReportSession) and report.state()["result"] == "VICTORY"
    assert all(u.hp == max(1, hp[u.uid] - 2) for u in g.members)
    assert all(u.combat_xp == xp[u.uid] for u in g.members)
    assert not g.fight_due and g.pending is None
    assert any("auto-resolved" in x["label"] for x in persist.list_saves("w1"))


def test_a_fight_that_is_not_a_clean_stomp_cannot_be_settled_unplayed():
    game, _, g = _ambushed()
    s = game.session
    _stomp(s, eligible=False)
    assert not s.state()["cta"]["swift"]["eligible"]
    with pytest.raises(ValueError):
        s.act(g.gid, "swift_win")
    assert g.fight_due


def test_a_band_with_no_fight_due_has_no_swift_win():
    guild = Guild(None, groups=[_band("road")], name="Ink Hands")
    s = MapSession(guild)
    with pytest.raises(ValueError):
        s.act(guild.groups[0].gid, "swift_win")
