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
        if s._setup() in ("trap", "place"):
            s.act("skip_traps" if s._setup() == "trap" else "skip_places")
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
    assert any("advances to Cleared" in n for n in game.session.map.notices)


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


def test_the_battle_card_lists_the_bars_standing_actions_and_lights_the_bar():
    from gartok import actions
    game, _, g = _ambushed("w1")
    game.session.act(g.gid, "resolve_event")
    s = game.session
    assert s.tutorial_key() == "battle" and s.tutorial_spot("battle") == ".bar, #seal"
    rows = s.tutorial_rows("battle")
    keys = rows[-2:]
    rows = rows[:-2]
    assert [r["focus"] for r in rows] == [f'[data-action="{i}"]' for i in
                                          ("attack", "defend", "assess", "push", "takedown", "flee", "delay")]
    on_bar = {a.id for a in actions.PANEL_ACTIONS}
    assert all(r["focus"].split('"')[1] in on_bar for r in rows)
    free = next(r for r in rows if "delay" in r["focus"])
    assert free["stamp"]["style"] == "green" and next(r for r in rows if "attack" in r["focus"])["stamp"]["label"]
    assert [r["stamp"]["label"] for r in keys] == ["Space", "Double click"] and keys[0]["focus"] == "#seal"


def test_a_fallen_member_and_a_second_fight_fire_their_cards_after_the_battle_card():
    game, guild, g = _ambushed("w1")
    game.session.act(g.gid, "resolve_event")
    s = game.session
    assert s.tutorial_key() == "battle" and s.tutorial_wiki("battle") is None
    guild.tutorial.dismiss("battle")
    assert s.tutorial_key() == "battle"
    guild.battles_won = 1
    assert s.tutorial_key() == "hint.reading"
    next(u for u in s.battle.units if u.team == "player").status = "dying"
    assert s.tutorial_key() == "hint.fallen" and s.tutorial_wiki("hint.fallen") == "actions:stabilize"
    assert s.tutorial_rows("hint.fallen") == [] and s.tutorial_spot("hint.fallen") is None
    from gartok.web.server import _tutorial
    assert _tutorial(s, "wiki", True) == {"screen": "wiki"} and "hint.fallen" in guild.tutorial.seen
    assert game.session.back_to() == {"screen": "battle"} and game.session is s


def test_a_place_the_squad_walks_out_of_fires_its_card_before_the_reading_one():
    from gartok import hints
    from gartok.battle import Battle
    from gartok.scenario import AncientRuinsScenario
    _, guild, g = _ambushed("w1")
    guild.battles_won = 1
    ruins = Battle(list(g.members), AncientRuinsScenario().enemies, scenario=AncientRuinsScenario())
    assert hints.in_battle(guild, ruins, {"battle"}) == hints.DUNGEON
    assert hints.in_battle(guild, ruins, {"battle", hints.DUNGEON}) == hints.READING


def test_the_placement_card_fires_when_a_person_has_a_cell_to_pick():
    from gartok import hints
    from gartok.battle import Battle
    from gartok.scenario import Scenario
    from tests.helpers import standard_unit
    _, guild, g = _ambushed("w1")
    guild.battles_won = 1
    unit = standard_unit("player")
    unit.combat_xp = 1000
    for t in ("tactical_mind", "vantage"):
        assert unit.choose_talent("combat", t)
    batt = Battle([unit], [standard_unit("enemy")], scenario=Scenario(), lethal=True)
    assert hints.in_battle(guild, batt, {"battle"}) == hints.PLACE
    assert hints.in_battle(guild, batt, {"battle", hints.PLACE}) == hints.READING


def _line_up(battle, you, foes, *, flank):
    """Put `foes` (one or two) beside `you`, on opposite sides when `flank`, else both on the same one."""
    x, y = 6, 6
    you.pos = (x, y)
    spots = [(x - 1, y), (x + 1, y)] if flank else [(x - 1, y), (x - 1, y - 1)]
    for foe, spot in zip(foes, spots):
        foe.pos = spot
    return you


def test_the_flank_card_fires_once_when_either_side_is_flanked_and_shows_three_pictures():
    from gartok import hints
    from gartok.actions.base import _flanked
    game, guild, g = _ambushed("w1")
    game.session.act(g.gid, "resolve_event")
    s = game.session
    guild.tutorial.dismiss("battle")
    mine = [u for u in s.battle.units if u.team == "player"]
    foes = [u for u in s.battle.units if u.team != "player"]
    assert len(mine) >= 2 and len(foes) >= 2
    for u in s.battle.units:
        u.pos = (0, 0)
    for i, u in enumerate(s.battle.units):
        u.pos = (20 + 3 * i, 20)
    visible = lambda u: True
    assert hints.in_battle(guild, s.battle, {"battle"}, visible) != hints.FLANK
    _line_up(s.battle, mine[0], foes[:2], flank=False)
    assert not _flanked(s.battle, foes[0], mine[0])
    assert hints.in_battle(guild, s.battle, {"battle"}, visible) != hints.FLANK
    _line_up(s.battle, mine[0], foes[:2], flank=True)
    assert _flanked(s.battle, foes[0], mine[0])
    assert hints.in_battle(guild, s.battle, {"battle"}, visible) == hints.FLANK
    assert hints.in_battle(guild, s.battle, {"battle", hints.FLANK}, visible) != hints.FLANK
    assert hints.in_battle(guild, s.battle, {"battle"}, lambda u: u.team == "player") != hints.FLANK
    rows = s.tutorial_rows(hints.FLANK)
    assert len(rows) == 3 and all(r["big"] and r["image"].endswith(".svg") for r in rows)
    assert s.tutorial_wiki(hints.FLANK).startswith("rules:")
    _line_up(s.battle, foes[0], mine[:2], flank=True)
    assert hints.in_battle(guild, s.battle, {"battle"}, visible) == hints.FLANK


def test_the_flank_pictures_are_shipped():
    import os

    from gartok.web.session import ASSETS
    from gartok.web import server
    from gartok.web.battle_session import BattleSession
    assert "tutorial" in server.ART
    for name in ("foe", "you", "none"):
        assert os.path.isfile(os.path.join(ASSETS, "tutorial", f"flank_{name}.svg"))
    assert {r["image"].split("/")[2] for r in BattleSession._flank_rows()} <= set(server.ART)


def test_the_portrait_opens_the_sheet_of_the_side_at_the_screen_and_the_menu_goes_aside_and_back():
    game, _, g = _ambushed("w1")
    game.session.act(g.gid, "resolve_event")
    s = game.session
    mine = [u for u in s.battle.units if u.team == "player"]
    assert {u.uid for u in s.sheet_units()} == {u.char.uid for u in mine}
    state = s.state()
    assert state["active"]["sheet"] == s.battle.active.char.uid
    assert s.sheet(state["active"]["sheet"])["name"] == s.battle.active.name
    foe = next(u for u in s.battle.units if u.team != "player")
    with pytest.raises(ValueError):
        s.sheet(foe.char.uid)
    assert s.aside("settings") == {"screen": "settings"} and game.session.screen == "settings"
    assert game.session.back_to() == {"screen": "battle"} and game.session is s
    assert s.aside("wiki") == {"screen": "wiki"}
    assert game.session.back_to() == {"screen": "battle"} and game.session is s
