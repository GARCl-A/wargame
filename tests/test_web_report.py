"""After a fight in the browser: the fallen, the report, the level-ups, the field and the purse, in
the order `app_battle` plays them, through the same session the server routes to."""

import pytest

from gartok import campaign, economy, items, orders, persist, progression, recorder
from gartok.clock import Clock
from gartok.group import Group
from gartok.guild import Guild
from gartok.web.map_session import MapSession
from gartok.web.report_session import ReportSession
from gartok.web.server import Game
from tests.helpers import Battle, _unit, standard_unit, world

NODE = "wilds"


@pytest.fixture(autouse=True)
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    yield tmp_path
    recorder.detach()


def _fight(n=2, foes=2, *, death=False, level=False, loot=(), lethal=True, seed=0):
    squad = [_unit(seed=seed + i) for i in range(n)]
    enemies = [_unit(team="enemy", seed=100 + seed + i) for i in range(foes)]
    guild = Guild(squad, node=NODE)
    guild.clock = Clock(24 * 9 * 3600)
    battle = Battle(squad, enemies, lethal=lethal)
    hand = battle.player_units[0]
    if death:
        victim = battle.player_units[-1]
        victim.hp, victim.status = 0, "dead"
        victim.downed_by = battle.enemy_units[0]
    for c in battle.enemy_units:
        c.hp, c.status = 0, "dead"
        hand.credit_kill(c)
    for name in loot:
        battle.enemy_units[0].inventory.append(name)
    if level:
        hand.combat_xp_earned = 50
    battle.winner = "player"
    battle.round_no = 4
    outcome = campaign.absorb_battle(guild, squad, battle, node=world.node(NODE))
    return guild, squad, battle, outcome


def _open(guild, battle, outcome, group=None, **kw):
    game = Game(MapSession(guild))
    s = ReportSession(game.session, group if group is not None else guild.groups[0], battle, outcome, place="The Wilds", **kw)
    game.open(s)
    return game, s


# --------------------------------------------------------------------------- #
# the chain                                                                    #
# --------------------------------------------------------------------------- #
def test_the_chain_runs_fallen_report_level_field_then_the_map():
    guild, _squad, battle, outcome = _fight(death=True, level=True, loot=["Axe"])
    game, s = _open(guild, battle, outcome)
    st = s.state()
    assert st["stage"] == "memorial" and st["result"] == "VICTORY" and st["rounds"] == 4
    assert [c["id"] for c in st["chain"]] == ["memorial", "report", "level", "loot", "map"]
    assert [c["at"] for c in st["chain"]] == ["now", "later", "later", "later", "later"]
    assert [x["stage"] for x in (s.next(), s.next(), s.next())] == ["report", "level", "loot"]
    assert [c["at"] for c in s.state()["chain"]] == ["done", "done", "done", "now", "later"]
    assert s.next()["screen"] == "map" and game.session.screen == "map"


def test_a_quiet_win_opens_on_the_report_and_goes_back_to_the_map():
    guild, _, battle, outcome = _fight(lethal=False)
    _game, s = _open(guild, battle, outcome)
    assert s.state()["stage"] == "report"
    assert [c["id"] for c in s.state()["chain"]] == ["report", "map"]
    assert s.next()["screen"] == "map"


def test_a_full_wipe_shows_only_the_fallen_then_hands_on():
    squad = [_unit(seed=7)]
    guild = Guild(squad, node=NODE)
    battle = Battle(squad, [_unit(team="enemy", seed=8)], lethal=True)
    band = guild.groups[0]
    me = battle.player_units[0]
    me.hp, me.status, me.downed_by = 0, "dead", battle.enemy_units[0]
    battle.winner = "enemy"
    outcome = campaign.absorb_battle(guild, squad, battle, node=world.node(NODE))
    assert outcome.campaign_over
    ended = []
    _, s = _open(guild, battle, outcome, group=band, then=lambda: ended.append(1) or {"screen": "over"})
    assert [c["id"] for c in s.state()["chain"]] == ["memorial", "map"]
    assert s.next() == {"screen": "over"} and ended


# --------------------------------------------------------------------------- #
# the pages                                                                    #
# --------------------------------------------------------------------------- #
def test_the_fallen_page_names_the_killer_with_their_face_and_the_days():
    guild, squad, battle, outcome = _fight(death=True)
    _, s = _open(guild, battle, outcome)
    [m] = s.state()["memorial"]
    foe = battle.enemy_units[0]
    assert m["name"] == squad[-1].name and m["killer"]["name"] == foe.name and m["killer"]["foe"]
    assert m["killer"]["caption"] == f"{foe.char.race['name']} {foe.char.occupation['name']}"
    assert m["days_n"] == guild.clock.day and m["founder"] and m["cause"] == "Killed in combat"


def test_the_report_lists_the_band_the_pack_the_blows_and_hp_after():
    guild, squad, battle, outcome = _fight(death=True, level=True)
    _, s = _open(guild, battle, outcome)
    s.next()
    r = s.state()["report"]
    assert [row["status"] for row in r["rows"]] == ["standing", "fallen"]
    first = r["rows"][0]
    assert first["xp_gain"] >= 50 and first["level"] > first["level_before"]
    assert len(first["downed"]) == 2 and 0 <= first["bar"] <= 1
    assert [f["status"] for f in r["foes"]] == ["fallen", "fallen"]
    assert all(f["portrait"] and f["race"] for f in r["foes"])
    assert [battle.enemy_units[0].name, squad[-1].name, True] in r["takedowns"]
    assert [h["name"] for h in r["hp"]] == [squad[0].name] and r["hp"][0]["hp"] == squad[0].hp
    steps = s.state()["steps"]
    assert [x["at"] for x in steps][:3] == ["done", "now", "later"]
    assert "reaches combat level" in steps[2]["title"] and steps[2]["faces"]


def test_a_foe_left_down_reads_as_stable():
    guild, _squad, battle, outcome = _fight(lethal=False)
    battle.enemy_units[1].status = "stable"
    _, s = _open(guild, battle, outcome)
    assert [f["status"] for f in s.state()["report"]["foes"]] == ["fallen", "stable"]


def test_the_level_up_has_the_ledger_the_bar_to_next_and_the_talent_pick():
    guild, squad, battle, outcome = _fight(level=True)
    _, s = _open(guild, battle, outcome)
    lv = s.next()["level"]
    assert lv["track"] == "COMBAT" and lv["level"] == squad[0].combat_level
    assert lv["gains"][0][0] == "Combat level" and lv["gains"][0][1] < lv["gains"][0][2]
    into, span = lv["next"]
    assert 0 <= into < span and lv["xp_gain"] >= 50 and lv["tag"] == "Level up"
    assert lv["picks"] == len(squad[0].pending_picks)


def test_pick_talents_opens_the_tree_and_comes_back_to_the_same_level_up():
    guild, squad, battle, outcome = _fight(level=True)
    game, s = _open(guild, battle, outcome)
    s.next()
    if not squad[0].pending_picks:
        pytest.skip("this unit has no talent to pick at its new level")
    assert s.talents() == {"screen": "talents"}
    tree = game.session
    st = tree.state()
    assert tree.unit is squad[0] and st["back"] == "Back to the level-up"
    assert [(c["id"], c["at"]) for c in st["chain"]][:3] == [("report", "done"), ("level", "done"), ("talents", "now")]
    back = tree.back()
    assert back["screen"] == "report" and back["stage"] == "level" and game.session is s


def test_talents_refuses_off_the_level_up():
    guild, _, battle, outcome = _fight(lethal=False)
    _, s = _open(guild, battle, outcome)
    with pytest.raises(ValueError):
        s.talents()


# --------------------------------------------------------------------------- #
# the field                                                                    #
# --------------------------------------------------------------------------- #
def _field(loot=("Axe", "Axe", "Torch"), **kw):
    guild, squad, battle, outcome = _fight(loot=loot, **kw)
    game, s = _open(guild, battle, outcome)
    while s.state()["stage"] != "loot":
        s.next()
    return game, s, squad


def _stack(st, name):
    return next(r for c in st["loot"]["cats"] for r in c["rows"] if r["name"] == name)


def test_the_field_sorts_its_stacks_by_kind_and_shows_every_survivors_column():
    _, s, squad = _field()
    lt = s.state()["loot"]
    labels = [c["label"] for c in lt["cats"]]
    assert labels.index("Weapons") < labels.index("Everything else")
    assert _stack(s.state(), "Axe")["qty"] >= 2
    assert [p["uid"] for p in lt["packs"]] == [u.uid for u in squad]
    assert lt["things"] == sum(r["qty"] for c in lt["cats"] for r in c["rows"])


def test_taking_part_of_a_stack_moves_that_many_and_marks_them_new():
    _, s, squad = _field()
    me = squad[0]
    axes = _stack(s.state(), "Axe")
    had = me.count_of("Axe")
    st = s.take([{"from": "field", "loc": axes["loc"], "qty": 1}], me.uid)
    assert me.count_of("Axe") == had + 1 and _stack(st, "Axe")["qty"] == axes["qty"] - 1
    col = next(p for p in st["loot"]["packs"] if p["uid"] == me.uid)
    assert next(r for r in col["pack"] if r["name"] == "Axe")["new"] == 1
    assert st["loot"]["taken"] == [{"name": me.name, "items": [["Axe", 1]]}]


def test_a_load_past_the_hard_limit_is_refused_with_why():
    _, s, squad = _field(loot=("Plate Armor",))
    me = squad[0]
    me.give_to_pack("Lumber", int(me.carry_max - me.load))
    plate = _stack(s.state(), "Plate Armor")
    st = s.take([{"from": "field", "loc": plate["loc"]}], me.uid)
    ref = st["loot"]["refused"]
    assert ref["uid"] == me.uid and ref["item"] == "Plate Armor" and "limit" in ref["why"]
    assert me.count_of("Plate Armor") == 0 and _stack(st, "Plate Armor")["qty"] == 1


def test_a_worn_slot_takes_a_weapon_from_the_field_and_a_pack_item_goes_back():
    _, s, squad = _field()
    me = squad[0]
    me.equipped_weapon = None
    axes = _stack(s.state(), "Axe")
    st = s.take([{"from": "field", "loc": axes["loc"]}], me.uid, "hand")
    assert me.equipped_weapon == "Axe"
    me.give_to_pack("Rope")
    idx = next(i for i, e in enumerate(me._base_inventory) if items.stack_name(e) == "Rope")
    st = s.take([{"from": me.uid, "loc": idx}], "field")
    assert me.count_of("Rope") == 0 and _stack(st, "Rope")["qty"] == 1
    with pytest.raises(ValueError):
        s.take([{"from": "field", "loc": _stack(st, "Rope")["loc"]}], "field")


def test_take_what_fits_empties_what_the_packs_can_carry():
    _, s, squad = _field()
    st = s.auto()
    assert st["loot"]["stacks"] == 0 and any(squad[0].count_of(n) for n in ("Axe", "Torch"))
    assert st["loot"]["taken"]


def test_what_is_left_on_the_field_is_lost_when_the_band_goes_on():
    _game, s, squad = _field()
    before = sum(u.count_of("Axe") for u in squad)
    assert s.next()["screen"] == "map"
    assert sum(u.count_of("Axe") for u in squad) == before


def test_the_field_refuses_off_its_page():
    guild, _, battle, outcome = _fight(loot=["Axe"])
    _, s = _open(guild, battle, outcome)
    with pytest.raises(ValueError):
        s.auto()


# --------------------------------------------------------------------------- #
# the purse                                                                    #
# --------------------------------------------------------------------------- #
class _Bout:
    name, entry = "Games: Brawl", 30


def _purse():
    guild, squad, battle, outcome = _fight(lethal=False)
    outcome.arena_reward = 130
    outcome.loot_pool = ["Axe"]
    game, s = _open(guild, battle, outcome, offer=_Bout())
    s.next()
    return game, s, squad


def test_the_purse_comes_instead_of_the_field_and_lands_whole_on_one():
    _game, s, squad = _purse()
    st = s.state()
    assert st["stage"] == "purse" and "loot" not in [c["id"] for c in st["chain"]]
    p = st["purse"]
    assert p["amount"] == 130 and p["entry"] == 30 and p["fighters"] == 2 and p["paid_to"] is None
    with pytest.raises(ValueError):
        s.next()
    had = squad[1].money
    st = s.give(squad[1].uid)
    assert squad[1].money == had + 130 and st["purse"]["paid_to"] == squad[1].uid
    with pytest.raises(ValueError):
        s.give(squad[0].uid)
    assert s.next()["screen"] == "map"


def test_a_stranger_cannot_pocket_the_purse():
    _, s, _ = _purse()
    with pytest.raises(ValueError):
        s.give("nobody")


def test_the_server_routes_the_report_verbs():
    guild, _, battle, outcome = _fight()
    _, s = _open(guild, battle, outcome)
    assert s.verb("state", False) and s.verb("next", True) and s.verb("take", True) and s.verb("give", True)


# --------------------------------------------------------------------------- #
# the clock's level-ups                                                        #
# --------------------------------------------------------------------------- #
def _worker_on_the_edge():
    u = standard_unit()
    u.give_to_pack("Potato", 4)
    u.work_hours = progression.WORK_XP_THRESHOLDS[0] * economy.LUMBER_XP_HOURS - 1
    guild = Guild(None, groups=[Group([u], node="lumber_yard", leader=u)], name="Ink Hands")
    return guild, u


def test_a_work_level_from_the_clock_gets_its_page_then_the_map():
    guild, u = _worker_on_the_edge()
    game = Game(MapSession(guild))
    m = game.session
    g = guild.groups[0]
    g.order = orders.work(guild, g, 8)
    assert m._after_order() == {"screen": "report"}
    s = game.session
    st = s.state()
    lv = st["level"]
    assert st["stage"] == "level" and lv["track"] == "WORK" and lv["level"] == u.work_level == 1
    assert ["Work level", 0, 1] in lv["gains"] and lv["after"] == "the work at Lumber Yard"
    assert [c["id"] for c in st["chain"]] == ["level", "map"] and s.tutorial_key() == "level_up"
    assert not any("grows" in n for n in m.notices)
    back = s.next()
    assert back["screen"] == "map" and game.session is m and not m.level_ups


def test_a_work_level_on_the_work_tab_comes_back_to_the_tab():
    guild, u = _worker_on_the_edge()
    game = Game(MapSession(guild))
    hub = game.session
    hub.act(guild.groups[0].gid, "market")
    hub = game.session
    hub.pick_tab("work")
    assert hub.work(8) == {"screen": "report"}
    s = game.session
    assert s.state()["level"]["track"] == "WORK"
    if u.pending_picks:
        assert s.talents() == {"screen": "talents"}
        assert game.session.back()["stage"] == "level"
    back = s.next()
    assert back["screen"] == "hub" and game.session is hub and back["tab"] == "work" and back["work"]["report"]
