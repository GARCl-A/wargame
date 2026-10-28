"""The talk before a fight in the browser: the guard, the ambushes, the Wildfire and an arena boss's
lines, through the same session the server routes to."""

import random

import pytest

from gartok import arena, dialogue, justice, missions, orders, persist, recorder
from gartok.clock import Clock
from gartok.group import Group
from gartok.guild import Guild
from gartok.unit import Unit
from gartok.web.battle_session import BattleSession
from gartok.web.dialogue_session import DialogueSession, _roll, boss_talk
from gartok.web.map_session import MapSession
from gartok.web.server import Game


@pytest.fixture
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    yield tmp_path
    recorder.detach()


def _die(monkeypatch, value):
    monkeypatch.setattr(random, "randint", lambda a, b: value)


def _band(n=3, lang="Common", money=0):
    random.seed(4)
    units = [Unit("Fighter") for _ in range(n)]
    for u in units:
        u.languages = [lang]
        u.money = money
        u.give_to_pack("Potato", 6)
    return units


def _pack(n=3, lang="Common"):
    random.seed(5)
    pack = [Unit("enemy") for _ in range(n)]
    for u in pack:
        u.languages = [lang] if lang else []
    return tuple(pack)


def _ambushed(kind="ambush", node="road", money=0, pack=None, **order):
    units = _band(money=money)
    g = Group(units, node=node, leader=units[0])
    guild = Guild(None, groups=[g], name="Ink Hands")
    g.pending = orders.Order(kind, pack=_pack() if pack is None else pack, **order)
    game = Game(MapSession(guild))
    return game, guild, g


def _open(game, g):
    return game.session.act(g.gid, "resolve_event")


def test_the_maps_fight_opens_the_talk_with_the_leader_the_pack_and_the_first_speakers_answers():
    game, _, g = _ambushed()
    assert _open(game, g) == {"screen": "talk"}
    s = game.session
    assert isinstance(s, DialogueSession) and s.verb("choose", True) and s.verb("state", False)
    st = s.state()
    assert st["kind"] == "ambush" and st["title"] == "AMBUSHED ON THE ROAD" and st["band"] == g.display_name
    assert st["leader"]["uid"] in {f["uid"] for f in st["foes"]} and st["leader"]["languages"] == ["Common"]
    assert sum(f["speaks"] for f in st["foes"]) == 1 and len(st["foes"]) == 3
    assert [o["verb"] for o in st["options"]] == ["persuade", "bluff", "intimidate", "bribe", "attack"]
    persuade = st["options"][0]
    assert persuade["pass"] and persuade["miss"] and 1 <= persuade["need"] <= 21
    assert persuade["need"] == round(21 - persuade["odds"] * 20)
    assert st["speaker"] in {u.uid for u in g.members}
    assert all(m["understood"] and m["languages"] == [{"name": "Common", "shared": True}] for m in st["members"])


def test_a_member_with_no_shared_tongue_can_answer_only_with_coin_or_steel():
    game, _, g = _ambushed()
    mute = g.members[1]
    mute.languages = ["Dwarvish"]
    _open(game, g)
    st = game.session.pick(mute.uid)
    assert st["speaker"] == mute.uid
    blocked = {o["verb"]: o["block"] for o in st["options"]}
    assert blocked["persuade"] == "needs Common" and blocked["attack"] == ""
    assert next(m for m in st["members"] if m["uid"] == mute.uid)["understood"] is False
    with pytest.raises(ValueError):
        game.session.choose("persuade")
    with pytest.raises(ValueError):
        game.session.pick("nobody")


def test_a_bribe_pays_the_pack_and_the_band_walks_on_back_on_the_map():
    game, _, g = _ambushed(money=500)
    _open(game, g)
    st = game.session.choose("bribe")
    r = st["result"]
    assert r["kind"] == "peace" and r["paid"] > 0 and r["roll"] is None and r["button"] == "GO ON"
    assert r["played"]["verb"] == "bribe" and r["opening"] == []
    assert sum(u.money for u in g.members) == 1500 - r["paid"]
    with pytest.raises(ValueError):
        game.session.choose("attack")
    back = game.session.go_on()
    assert back["screen"] == "map" and isinstance(game.session, MapSession)
    assert any("counts out" in n for n in back["notices"])
    assert not g.fight_due and g.order is not None


def test_bribe_is_closed_for_an_empty_purse():
    game, _, g = _ambushed(money=0)
    _open(game, g)
    bribe = next(o for o in game.session.state()["options"] if o["verb"] == "bribe")
    assert bribe["block"] == "not enough coin"
    with pytest.raises(ValueError):
        game.session.choose("bribe")


def test_a_failed_bluff_reads_the_roll_keeps_it_on_the_order_and_a_reopen_does_not_roll_again(monkeypatch, saves):
    game, _, g = _ambushed()
    m = game.session
    m.world_id = "w1"
    _open(game, g)
    _die(monkeypatch, 1)
    r = game.session.choose("bluff")["result"]
    assert r["kind"] == "fight" and not r["won"] and r["button"] == "FIGHT"
    assert r["roll"]["nat"] == 1 and r["roll"]["total"] == 1 + r["roll"]["mod"]
    assert "d20" not in r["text"] and "d20(1)" in r["full"]
    assert [o["title"] for o in r["opening"]] == ["Caught off guard"]
    assert g.pending.parley["kind"] == "fight"
    assert persist.load_game("w1").groups[0].pending.parley["opening"]["surprised"] == "player"
    assert game.session.go_on() == {"screen": "battle"}
    assert isinstance(game.session, BattleSession)
    game.open(m)                         # the window closed mid-fight: the fight is still due
    assert g.fight_due
    _die(monkeypatch, 20)
    _open(game, g)
    again = game.session.state()
    assert again["result"]["kind"] == "fight" and again["result"]["played"] is None
    assert again["options"] == []


def test_intimidate_that_lands_shakes_them_and_one_that_misses_gives_them_the_jump(monkeypatch):
    game, _, g = _ambushed()
    _open(game, g)
    dc = game.session.enc.dc("intimidate")
    mod = game.session.enc.mod("intimidate", game.session.talk.speaker)
    assert 1 <= dc - mod <= 20
    _die(monkeypatch, dc - mod)                              # passes by less than the rout margin
    r = game.session.choose("intimidate")["result"]
    assert r["kind"] == "fight" and r["won"]
    assert [o["title"] for o in r["opening"]] == ["They come on shaken"]
    game2, _, g2 = _ambushed()
    _open(game2, g2)
    _die(monkeypatch, 1)
    r = game2.session.choose("intimidate")["result"]
    assert r["opening"][0]["title"] == "They get the jump" and "+5" in r["opening"][0]["line"]


def test_a_pack_with_nobody_who_speaks_goes_straight_to_the_fight():
    game, _, g = _ambushed(pack=_pack(lang=None))
    assert _open(game, g) == {"screen": "battle"}
    assert game.session.state()["campaign"]


def test_a_band_with_no_fight_due_has_nothing_to_face():
    game, _, g = _ambushed()
    g.pending = None
    with pytest.raises(ValueError):
        _open(game, g)


def _wanted(prev_node="market", crime=6):
    game, guild, g = _ambushed("guard", node="city", pack=(), caught=(), prev_node=prev_node)
    culprit = g.members[0]
    culprit.crime = crime
    g.pending = orders.Order("guard", caught=(culprit.uid,), prev_node=prev_node)
    return game, guild, g, culprit


def test_the_guard_names_the_wanted_and_offers_the_cells_and_a_way_back():
    game, _, g, culprit = _wanted()
    _open(game, g)
    st = game.session.state()
    assert st["kind"] == "guard" and st["seal"] == "action/arrest"
    assert st["wanted"] == [{"name": culprit.name, "crime": 6}]
    assert next(m for m in st["members"] if m["uid"] == culprit.uid)["crime"] == 6
    assert all(m["crime"] is None for m in st["members"] if m["uid"] != culprit.uid)
    verbs = [o["verb"] for o in st["options"]]
    assert verbs[0] == "surrender" and "leave" in verbs
    bribe = next(o for o in st["options"] if o["verb"] == "bribe")
    assert bribe["check"] == f"${dialogue.GUARD_BRIBE_PER_CRIME * 6}"


def test_surrender_sends_the_wanted_to_the_cells_and_the_rest_back_to_the_map():
    game, guild, g, culprit = _wanted()
    _open(game, g)
    game.session.choose("surrender")
    back = game.session.go_on()
    assert back["screen"] == "map"
    assert culprit in [u for u, _ in guild.jailed] and culprit not in g.members and not g.fight_due
    assert any("accepts arrest" in n for n in back["notices"])


def test_running_falls_back_the_way_the_band_came(monkeypatch):
    game, _, g, _ = _wanted(prev_node="market")
    monkeypatch.setattr(justice, "catch", lambda *a, **k: [])
    _open(game, g)
    game.session.choose("leave")
    back = game.session.go_on()
    assert g.node == "market" and back["screen"] == "map"
    assert any("fall back" in n for n in back["notices"])


def test_a_recaught_band_cannot_run_twice():
    game, _, g, _ = _wanted(prev_node=None)
    _open(game, g)
    assert "leave" not in [o["verb"] for o in game.session.state()["options"]]


def _wildfire_guild():
    random.seed(7)
    members = [Unit("player") for _ in range(2)]
    for u in members:
        u.give_to_pack("Meat", 30)
    guild = Guild(members, node="nature_grove", clock=Clock(10 * 3600))
    guild.missions.append(missions.Mission(missions.LIBRARY_ANCIENT_CODEX.id, members[0].uid, 0, None,
                                           state="done"))
    guild.reveal_node("nature_grove")
    missions.accept(guild, members[0], missions.NATURE_WILDFIRE)
    focus = next(f for f in guild.wildfire.foci if not f.great)
    guild.groups[0].node = focus.id
    return guild, guild.groups[0], focus


def test_the_wildfire_talk_gets_a_hearing_then_teaches_and_the_fire_goes_out(monkeypatch):
    guild, g, focus = _wildfire_guild()
    game = Game(MapSession(guild))
    assert game.session.act(g.gid, "wf_talk") == {"screen": "talk"}
    st = game.session.state()
    assert st["kind"] == "wildfire" and st["seal"] == "item/torch"
    assert [o["verb"] for o in st["options"]] == ["persuade", "bribe", "attack"]
    assert next(o for o in st["options"] if o["verb"] == "bribe")["block"] == "they want to learn, not be paid"
    _die(monkeypatch, 20)
    r = game.session.choose("persuade")["result"]
    assert r["kind"] == "next" and r["roll"]["nat"] == 20 and r["button"] == "GO ON"
    st = game.session.go_on()
    assert st["result"] is None and st["options"][0]["verb"] == "teach"
    game.session.choose("teach")
    back = game.session.go_on()
    assert back["screen"] == "map" and focus not in guild.wildfire.foci


def test_a_missed_wildfire_talk_sets_the_camp_on_the_band(monkeypatch):
    guild, g, focus = _wildfire_guild()
    m = MapSession(guild)
    game = Game(m)
    game.session.act(g.gid, "wf_talk")
    _die(monkeypatch, 1)
    assert game.session.choose("persuade")["result"]["kind"] == "fight"
    assert focus.hostile
    assert game.session.go_on() == {"screen": "battle"}
    assert isinstance(game.session, BattleSession) and game.session.state()["meta"]["sub"].startswith("The goblin camp")
    with pytest.raises(ValueError):
        m.act(g.gid, "wf_talk")


def test_an_arena_boss_reads_the_lines_in_order_then_opens_the_bout():
    guild = Guild([Unit("a")], name="Ink Hands")
    talk = arena.boss_talk(guild, arena.boss_bout())
    game = Game(MapSession(guild))
    bout = []
    game.open(boss_talk(game.session, guild.groups[0], talk, lambda: bout.append(1) or {"screen": "battle"}))
    s = game.session
    st = s.state()
    assert st["kind"] == "boss" and st["options"] == [] and st["seal"] == "hat/crown"
    assert [(ln["name"], ln["at"]) for ln in st["lines"]] == [("Ribit", "now"), ("Bufo", "later"), ("Peep", "later")]
    assert st["leader"]["name"] == "Ribit" and st["result"]["kind"] == "next"
    with pytest.raises(ValueError):
        s.pick(guild.groups[0].members[0].uid)
    st = s.go_on()
    assert [ln["at"] for ln in st["lines"]] == ["said", "now", "later"] and st["leader"]["name"] == "Bufo"
    st = s.go_on()
    assert st["result"]["kind"] == "fight" and st["result"]["button"] == "FIGHT" and st["result"]["opening"] == []
    assert s.go_on() == {"screen": "battle"} and bout == [1]


def test_the_roll_is_read_off_the_line_with_or_without_the_attribute():
    assert _roll("A (d20(7) +2 = 9 vs DC 12) B.") == ({"nat": 7, "mod": 2, "total": 9, "dc": 12}, "A B.")
    assert _roll("x (d20(3) -1(INT) = 2 vs DC 15).")[0] == {"nat": 3, "mod": -1, "total": 2, "dc": 15}
    assert _roll("Steel it is.") == (None, "Steel it is.")
