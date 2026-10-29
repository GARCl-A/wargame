"""A member's talent trees in the browser: the tracks, each talent's state, the talent in hand with what it
moves on the sheet, the pick and its save, through the same session the server routes to."""

import pytest

from gartok import orders, persist, progression, recorder, talents
from gartok.group import Group
from gartok.guild import Guild
from gartok.unit import Unit
from gartok.web.map_session import MapSession
from gartok.web.server import Game
from gartok.web.talent_session import TalentSession


@pytest.fixture(autouse=True)
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    yield tmp_path
    recorder.detach()


def _open(combat_xp=10, n=3):
    units = [Unit("Fighter") for _ in range(n)]
    units[0].combat_xp = combat_xp
    guild = Guild(None, groups=[Group(units, node="city", leader=units[0])], name="Ink Hands")
    game = Game(MapSession(guild, "w1"))
    sheet = game.session.act(guild.groups[0].gid, "guild")
    assert sheet == {"screen": "guild"}
    game.session.desk.member = units[0]
    assert game.session.talents() == {"screen": "talents"}
    return game, game.session, units


def _node(st, tid):
    return next(n for n in st["nodes"] if n["id"] == tid)


def test_the_members_sheet_opens_the_tree_on_the_track_with_a_pick():
    _game, s, units = _open()
    st = s.state()
    assert isinstance(s, TalentSession) and st["track"] == "combat"
    combat = next(t for t in st["tracks"] if t["track"] == "combat")
    assert combat["level"] == units[0].combat_level == 2 and combat["picks"] == 2
    assert [t["track"] for t in st["tracks"]] == list(talents.TRACKS)
    assert len(st["nodes"]) == len(talents.TREE["combat"])
    assert st["hand"]["id"] == "strong" and st["hand"]["status"] == "Ready to take"
    assert [b["picks"] for b in st["band"]] == [2, 0, 0] and st["back"] == "Back to the guild"


def test_each_talent_reads_open_locked_or_waiting():
    _game, s, units = _open()
    st = s.state()
    assert _node(st, "strong")["state"] == "open"
    assert _node(st, "sure_strike")["state"] == "locked"
    other = s.look(uid=units[1].uid)
    assert other["track"] == "combat" and _node(other, "strong")["state"] == "waiting"
    assert not other["can_take"] and other["hand"]["delta"] is None


def test_the_talent_in_hand_shows_what_it_moves_on_the_sheet():
    _game, s, units = _open()
    st = s.look(tid="strong")
    strength = units[0].strength
    assert ["STR", strength, strength + 1] in st["hand"]["delta"]
    assert units[0].strength == strength and "strong" not in units[0].talents["combat"]
    st = s.look(tid="sure_strike")
    assert st["hand"]["delta"] is None and st["hand"]["status"] == "Sure Strike needs Strong first"
    assert [b["id"] for b in st["hand"]["branch"]] == ["strong", "sure_strike"]
    assert [o["id"] for o in st["hand"]["opens"]] == [t.id for t in talents.TREE["combat"] if t.requires == "sure_strike"]


def test_taking_a_talent_spends_the_pick_opens_what_hangs_from_it_and_saves(saves):
    _game, s, units = _open()
    st = s.take("combat", "strong")
    assert "strong" in units[0].talents["combat"]
    assert _node(st, "strong")["state"] == "taken" and _node(st, "sure_strike")["state"] == "open"
    assert next(t for t in st["tracks"] if t["track"] == "combat")["picks"] == 1
    assert st["hand"]["id"] == "strong" and st["hand"]["status"] == "Held"
    saved = persist.load_game("w1")
    assert "strong" in saved.groups[0].members[0].talents["combat"]


def test_a_pick_is_refused_with_why():
    _game, s, units = _open()
    with pytest.raises(ValueError, match="needs Strong first"):
        s.take("combat", "sure_strike")
    with pytest.raises(ValueError, match="not on this tree"):
        s.take("work", "strong")
    s.take("combat", "strong")
    with pytest.raises(ValueError, match="holds Strong already"):
        s.take("combat", "strong")
    s.take("combat", "agile")
    with pytest.raises(ValueError, match="no combat pick"):
        s.take("combat", "tough")
    assert units[0].talents["combat"] == ["strong", "agile"]


def test_can_take_now_lists_every_open_talent_and_a_click_takes_it_in_hand():
    _game, s, units = _open()
    st = s.state()
    assert {c["id"] for c in st["can_take"]} == {t.id for t in talents.TREE["combat"] if not t.requires}
    units[0].work_hours = 10 ** 6
    st = s.look(track="work")
    work = [c for c in st["can_take"] if c["track"] == "work"]
    assert work and st["hand"]["id"] == work[0]["id"]
    assert s.look(track="combat", tid="tough")["hand"]["id"] == "tough"


def test_the_racial_track_says_when_its_next_pick_comes():
    _game, s, units = _open()
    st = s.look(track="racial")
    racial = next(t for t in st["tracks"] if t["track"] == "racial")
    assert racial["next_racial"] == (progression.racial_picks(units[0].racial_level) + 1) * progression.RACIAL_PICK_EVERY
    assert all(n["state"] in ("waiting", "locked") for n in st["nodes"])
    assert len(st["nodes"]) == len(talents.racial_tree(units[0].race["name"]))


def test_back_lands_on_the_members_sheet():
    game, s, _ = _open()
    back = s.back()
    assert back["screen"] == "guild" and game.session.screen == "guild"


def test_a_stranger_or_a_wrong_track_is_refused():
    _game, s, _ = _open()
    with pytest.raises(ValueError):
        s.look(uid="nobody")
    with pytest.raises(ValueError):
        s.look(track="cooking")
    with pytest.raises(ValueError):
        s.look(tid="arcane_mind")


def test_the_server_routes_the_talent_verbs():
    _game, s, units = _open()
    assert s.verb("state", False)(s, {})["track"] == "combat"
    assert s.verb("take", True)(s, {"track": "combat", "id": "agile"})["hand"]["status"] == "Held"
    assert s.verb("look", True)(s, {"uid": units[1].uid})["unit"]["uid"] == units[1].uid
    assert s.verb("back", True)(s, {})["screen"] == "guild"


def test_a_band_with_a_fight_due_still_reads_its_trees():
    game, s, units = _open()
    game.session.map.guild.groups[0].pending = orders.Order("ambush", pack=(Unit("Fighter"),))
    assert s.state()["unit"]["uid"] == units[0].uid


def test_the_magic_tree_without_a_school_says_it_waits_for_one():
    _game, s, units = _open()
    assert not units[0].magic_sources
    st = s.look(track="magic")
    assert st["unit"]["schools"] == [] and all(n["state"] != "open" for n in st["nodes"])
    assert "no school yet" in st["hand"]["status"]
    with pytest.raises(ValueError, match="no school yet"):
        s.take("magic", "arcane_mind")
