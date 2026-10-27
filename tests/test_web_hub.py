"""A place's hub in the browser: its tabs and keeper, and the shop's trades through the same session the
server routes to."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from gartok import (
    data,
    economy,
    gather,
    items,
    medic,
    orders,
    persist,
    recorder,
    recruit,
    world,
)
from gartok.animals import HARNESS, PACK_SADDLE
from gartok.data import LIVESTOCK
from gartok.group import Group
from gartok.guild import Guild
from gartok.unit import Unit
from gartok.wagon import VEHICLES, Wagon
from gartok.web.away_session import AwaySession
from gartok.web.hub_session import HubSession
from gartok.web.map_session import MapSession
from gartok.web.server import Game, serve


def _guild(node, coins=200):
    units = [Unit("Fighter") for _ in range(2)]
    for u in units:
        u.money = coins
        u.give_to_pack("Potato", 4 - u.count_of("Potato"))
    return Guild(None, groups=[Group(units, node=node, leader=units[0])], name="Ink Hands")


@pytest.fixture
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    yield tmp_path
    recorder.detach()


def _hub(node, key, coins=200):
    guild = _guild(node, coins)
    game = Game(MapSession(guild))
    g = guild.groups[0]
    assert game.session.act(g.gid, key) == {"screen": "hub"}
    return game.session, guild, g


def _ware(st, kind=None):
    rows = [r for c in st["shop"]["shelf"] for r in c["rows"] if r["stock"]]
    return next(r for r in rows if kind is None or kind(r["name"]))


def _pack(st, owner, name):
    p = next(p for p in st["shop"]["packs"] if p["id"] == owner.uid)
    return next((r for r in p["pack"] if r["name"] == name), None)


def test_a_shop_opens_as_a_hub_with_the_tabs_and_keeper_of_its_place():
    hub, _, _ = _hub("smith", "forge")
    assert isinstance(hub, HubSession)
    st = hub.state()
    assert [t["key"] for t in st["tabs"]] == ["shop", "craft"] and st["tab"] == "craft"
    assert st["keeper"]["name"] and st["keeper"]["portrait"].startswith("/assets/portraits/npc/")
    assert "craft" in st and "shop" not in st
    st = hub.pick_tab("shop")
    assert st["tab"] == "shop" and {c["key"] for c in st["shop"]["shelf"]} >= {"weapons", "armor"}
    with pytest.raises(ValueError):
        hub.pick_tab("stable")


def test_the_market_opens_on_its_shop_and_a_work_node_lists_its_shifts_beside_it():
    hub, _, _ = _hub("market", "market")
    assert hub.state()["tab"] == "shop" and [t["key"] for t in hub.state()["tabs"]] == ["shop"]
    hub, _, _ = _hub("lumber_yard", "market")
    tabs = hub.state()["tabs"]
    assert [t["key"] for t in tabs] == ["shop", "work", "gather"] and all(t["live"] for t in tabs)


def test_buying_into_a_pack_pays_from_the_purse_into_the_till_and_takes_one_off_the_shelf():
    hub, guild, g = _hub("market", "market")
    st = hub.state()
    r = _ware(st)
    shop = guild.shop("market")
    purse, till, stock = st["shop"]["purse"], shop.cash, shop.stock[r["name"]]
    buyer = g.members[1]
    st = hub.verb("buy", True)(hub, {"name": r["name"], "qty": 2, "to": buyer.uid})
    assert st["shop"]["purse"] == purse - 2 * r["price"] and shop.cash == till + 2 * r["price"]
    assert shop.stock[r["name"]] == stock - 2 and buyer.count_of(r["name"]) == 2
    assert st["shop"]["notice"]


def test_buying_with_no_pack_named_shares_it_out_by_room():
    hub, _, g = _hub("market", "market")
    r = _ware(hub.state())
    hub.verb("buy", True)(hub, {"name": r["name"], "qty": 3})
    assert sum(u.count_of(r["name"]) for u in g.members) == 3


def test_a_weapon_bought_onto_a_hand_is_worn_and_one_no_one_can_afford_is_refused():
    hub, _, g = _hub("smith", "forge")
    hub.pick_tab("shop")
    r = _ware(hub.state(), lambda n: items.is_weapon(n) and items.get(n).hands == 1)
    hub.verb("buy", True)(hub, {"name": r["name"], "to": g.members[0].uid, "zone": "hand"})
    assert g.members[0].equipped_weapon == r["name"]
    poor, _, pg = _hub("smith", "forge", coins=0)
    poor.pick_tab("shop")
    dear = _ware(poor.state(), lambda n: economy.buy_price(n) > 10)
    st = poor.verb("buy", True)(poor, {"name": dear["name"], "to": pg.members[0].uid})
    assert st["shop"]["notice"] and pg.members[0].count_of(dear["name"]) == 0
    with pytest.raises(ValueError):
        poor.shop.buy("Dragon Egg", 1, pg.members[0].uid)


def test_an_item_handed_over_moves_packs_and_part_of_a_stack_can_go():
    hub, _, g = _hub("market", "market")
    a, b = g.members
    loc = _pack(hub.state(), a, "Potato")["loc"]
    hub.verb("move", True)(hub, {"picks": [{"from": a.uid, "loc": loc, "qty": 1}], "to": b.uid})
    assert a.count_of("Potato") == 3 and b.count_of("Potato") == 5
    with pytest.raises(ValueError):
        hub.shop.move([{"from": a.uid, "loc": 99}], b.uid)
    with pytest.raises(ValueError):
        hub.shop.move([{"from": a.uid, "loc": loc}], "nobody")


def test_selling_pays_the_seller_out_of_the_till_and_puts_it_on_the_shelf():
    hub, guild, g = _hub("market", "market")
    a = g.members[0]
    shop = guild.shop("market")
    till, money = shop.cash, a.money
    row = _pack(hub.state(), a, "Potato")
    st = hub.verb("sell", True)(hub, {"picks": [{"from": a.uid, "loc": row["loc"], "qty": 3}]})
    assert a.count_of("Potato") == 1 and a.money == money + 3 * row["sell"]
    assert shop.cash == till - 3 * row["sell"] and shop.stock["Potato"] >= 3 and st["shop"]["notice"]
    coin = _pack(st, a, "Copper Coin")
    with pytest.raises(ValueError):
        hub.shop.sell([{"from": a.uid, "loc": coin["loc"]}])


def test_a_sale_above_what_the_till_holds_is_refused():
    hub, guild, g = _hub("market", "market")
    guild.shop("market").cash = 1
    a = g.members[0]
    row = _pack(hub.state(), a, "Potato")
    st = hub.verb("sell", True)(hub, {"picks": [{"from": a.uid, "loc": row["loc"]}]})
    assert a.count_of("Potato") == 4 and "only has" in st["shop"]["notice"]


def test_a_locked_stack_stays_out_of_the_auto_sell_and_a_marked_kind_sells_in_one_go():
    hub, _, g = _hub("market", "market")
    a, b = g.members
    hub.verb("lock", True)(hub, {"owner": a.uid, "name": "Potato"})
    assert _pack(hub.state(), a, "Potato")["locked"]
    st = hub.verb("mark", True)(hub, {"name": "Potato"})
    assert st["shop"]["marked"] == ["Potato"] and st["shop"]["marked_total"] > 0
    hub.verb("sell_marked", True)(hub, {})
    assert a.count_of("Potato") == 4 and b.count_of("Potato") == 0


def test_leaving_the_hub_lands_on_the_map_and_saves_what_was_bought(saves):
    guild = _guild("market")
    game = Game(MapSession(guild, "w1"))
    g = guild.groups[0]
    game.session.act(g.gid, "market")
    hub = game.session
    r = _ware(hub.state())
    hub.verb("buy", True)(hub, {"name": r["name"], "to": g.members[0].uid})
    st = hub.verb("back", True)(hub, {})
    assert st["screen"] == "map" and isinstance(game.session, MapSession)
    assert persist.load_game("w1").groups[0].members[0].count_of(r["name"]) == g.members[0].count_of(r["name"])


def test_the_work_tab_lists_the_crew_with_their_tool_and_the_shifts_with_the_bands_wage():
    hub, _, g = _hub("lumber_yard", "market")
    st = hub.pick_tab("work")
    w = st["work"]
    assert [u["name"] for u in w["crew"]] == [u.name for u in g.members] and w["tool"] == "Axe"
    assert [s["hours"] for s in w["shifts"]] == [4, 8, 12, 16] and w["glyph"].startswith("item/")
    assert w["shifts"][-1]["wage"] == sum(u["pay"] for u in w["crew"])
    assert {c["label"] for c in w["cards"]} >= {"party purse", "rations"} and w["report"] == []


def test_a_paid_shift_runs_the_clock_pays_the_crew_and_keeps_the_tab_up_with_what_it_paid():
    hub, guild, g = _hub("lumber_yard", "market")
    wage = hub.pick_tab("work")["work"]["shifts"][1]["wage"]
    money, start = sum(u.money for u in g.members), guild.clock.seconds
    st = hub.verb("work", True)(hub, {"hours": 8})
    assert hub.game.session is hub and st["tab"] == "work" and st["work"]["report"]
    assert (guild.clock.seconds - start) / 3600 == 8 and not g.busy
    assert sum(u.money for u in g.members) == money + wage
    with pytest.raises(ValueError):
        hub.work(5)


def test_a_shift_lands_on_the_map_when_another_band_needs_the_person():
    units = [Unit("Fighter") for _ in range(2)]
    guild = Guild(None, groups=[Group(units[:1], node="lumber_yard", leader=units[0]),
                                Group(units[1:], node="city", leader=units[1])], name="Ink Hands")
    game = Game(MapSession(guild))
    yard, other = guild.groups
    other.order = orders.rest(2)
    game.session.act(yard.gid, "market")
    st = game.session.work(8)
    assert st["screen"] == "map" and isinstance(game.session, MapSession)
    assert yard.order.kind == "work" and not other.busy


def test_the_licence_is_bought_from_the_bands_purse_and_refused_when_it_is_short():
    poor, guild, _ = _hub("lumber_yard", "market", coins=0)
    st = poor.pick_tab("gather")
    assert not st["gather"]["held"] and st["gather"]["short"] == gather.licence_price("lumber_yard")
    st = poor.verb("licence", True)(poor, {})
    assert st["gather"]["notice"] and not guild.has_licence("lumber_yard")
    with pytest.raises(ValueError):
        poor.gather(4)
    hub, guild, g = _hub("lumber_yard", "market")
    money = sum(u.money for u in g.members)
    st = hub.verb("licence", True)(hub, {})
    assert st["gather"]["held"] and guild.has_licence("lumber_yard")
    assert sum(u.money for u in g.members) == money - gather.licence_price("lumber_yard")
    assert [d["name"] for d in st["gather"]["drops"]] == [n for n, _ in gather.drops("lumber_yard")]
    crew = st["gather"]["crew"]
    assert [u["name"] for u in crew] == [u.name for u in g.members]
    assert sum(u["haul"] for u in crew) == round(guild.shift_worth(g, "lumber_yard", gather.DAY_HOURS)[0])


def test_a_gathering_shift_goes_back_to_the_map_and_runs_the_clock_there():
    hub, guild, g = _hub("lumber_yard", "market")
    hub.gathering.buy_licence()
    start = guild.clock.seconds
    st = hub.verb("gather", True)(hub, {"hours": 4})
    assert st["screen"] == "map" and isinstance(hub.game.session, MapSession)
    assert guild.clock.seconds - start == 4 * 3600 or g.fight_due


def _ward(missing=(3, 0), stacks=0, coins=200):
    hub, guild, g = _hub("apothecary", "apothecary", coins)
    for u, m in zip(g.members, missing):
        u.hp = u.hp_max - m
    for _ in range(stacks):
        g.members[1].add_poison("giant_spider_venom", 12)
    assert hub.state()["tab"] == "shop"
    hub.pick_tab("medic")
    return hub, guild, g


def test_the_medic_tab_lists_who_needs_treating_and_bills_the_picked_ones():
    hub, _, g = _ward()
    hurt, fine = g.members
    st = hub.state()
    assert [t["key"] for t in st["tabs"]] == ["shop", "medic", "craft", "jobs"] and st["tabs"][1]["live"]
    m = st["medic"]
    assert [u["uid"] for u in m["ward"]] == [hurt.uid] and m["fine"] == [fine.name]
    assert m["ward"][0]["parts"][0]["label"] == "3 HP" and m["cost"] == 0
    with pytest.raises(ValueError):
        hub.patient(fine.uid)
    m = hub.verb("patient", True)(hub, {"uid": hurt.uid})["medic"]
    q = medic.quote(hurt)
    assert m["ward"][0]["picked"] and (m["cost"], m["hours"]) == (q.cost, q.hours) and m["can_pay"]
    assert m["stay"] is None
    assert not hub.patient(hurt.uid)["medic"]["ward"][0]["picked"]


def test_a_treatment_pays_passes_the_hours_cures_and_stays_on_the_tab(saves):
    hub, guild, g = _ward()
    hurt = g.members[0]
    hub.patient(hurt.uid)
    q, money, start = medic.quote(hurt), sum(u.money for u in g.members), guild.clock.seconds
    st = hub.verb("treat", True)(hub, {})
    assert hub.game.session is hub and st["tab"] == "medic" and st["medic"]["report"]
    assert hurt.hp == hurt.hp_max and st["medic"]["ward"] == []
    assert sum(u.money for u in g.members) == money - q.cost
    assert (guild.clock.seconds - start) / 3600 == q.hours


def test_a_treatment_the_band_cannot_pay_is_refused_with_a_notice():
    hub, _, g = _ward(coins=0)
    hub.patient(g.members[0].uid)
    st = hub.treat()
    assert not st["medic"]["can_pay"] and st["medic"]["notice"] and g.members[0].hp < g.members[0].hp_max


def test_a_hospital_stay_is_picked_alone_and_splits_the_patient_off_while_the_tab_stays_up():
    hub, guild, g = _ward(stacks=4)
    hurt, sick = g.members
    hub.patient(hurt.uid)
    m = hub.patient(sick.uid)["medic"]
    assert [u["uid"] for u in m["ward"] if u["picked"]] == [sick.uid] and m["stay"]
    st = hub.treat()
    assert hub.game.session is hub and st["tab"] == "medic"
    assert g.members == [hurt] and any(x.order and x.order.task == "hospital" for x in guild.groups)


def test_a_stay_the_whole_band_waits_goes_back_to_the_map(monkeypatch):
    hub, guild, g = _ward(stacks=4)
    monkeypatch.setattr(Guild, "free_slots", property(lambda self: 0))
    hub.patient(g.members[1].uid)
    m = hub.state()["medic"]
    assert "waits" in m["stay"]
    st = hub.treat()
    assert st["screen"] == "map" and isinstance(hub.game.session, MapSession)
    assert len(guild.groups) == 1 and (g.busy or g.members[1].poisons == {})


def _board(node="tanner", kind="tanner", coins=200):
    hub, guild, g = _hub(node, kind, coins)
    for u in g.members:
        u.remove_named("1sqm Hide", u.count_of("1sqm Hide"))
    return hub, guild, g, hub.pick_tab("jobs")["jobs"]


def test_a_givers_jobs_tab_shows_the_board_the_signer_and_what_the_packs_carry():
    hub, _, g, j = _board()
    assert next(t for t in hub.state()["tabs"] if t["key"] == "jobs")["live"]
    job = j["jobs"][0]
    assert job["id"] == "tanner_hides" and job["button"] == {"verb": "accept", "label": "ACCEPT THE JOB", "on": True}
    assert job["detail"][0] == "15x 1sqm Hide" and not job["taken"]
    assert j["signer"]["name"] == g.leader.name and j["egg"] is None
    g.members[1].give_to_pack("1sqm Hide", 4)
    c = hub.state()["jobs"]["carried"][0]
    assert (c["item"], c["have"], c["goal"]) == ("1sqm Hide", 4, 15) and c["who"] == [f"{g.members[1].name} 4"]


def test_accepting_a_job_signs_it_to_the_leader_and_turns_its_button_into_the_turn_in(saves):
    hub, guild, g, _ = _board()
    job = hub.verb("accept", True)(hub, {"id": "tanner_hides"})["jobs"]["jobs"][0]
    assert [(m.template_id, m.unit_uid) for m in guild.missions] == [("tanner_hides", g.leader.uid)]
    assert job["taken"] and job["button"]["verb"] == "turn_in" and not job["button"]["on"]
    assert job["button"]["label"] == "NEED 15 MORE" and job["detail"][0] == "0 / 15 1sqm Hide"
    st = hub.on_board(type(hub.board).accept, "tanner_hides")
    assert st["jobs"]["notice"] and len(guild.missions) == 1


def test_turning_a_job_in_takes_the_goal_and_pays_the_band():
    hub, guild, g, _ = _board()
    hub.on_board(type(hub.board).accept, "tanner_hides")
    g.members[0].give_to_pack("1sqm Hide", 15)
    assert hub.state()["jobs"]["jobs"][0]["button"]["on"]
    money = sum(u.money for u in g.members)
    st = hub.verb("turn_in", True)(hub, {"id": "tanner_hides"})
    assert guild.missions[0].state == "done" and g.members[0].count_of("1sqm Hide") == 0
    assert sum(u.money for u in g.members) == money + 200 and st["jobs"]["notice"]


def test_a_turn_in_the_band_cannot_make_is_refused_and_a_job_off_the_board_is_an_error():
    hub, guild, _, _ = _board()
    assert hub.on_board(type(hub.board).turn_in, "tanner_hides")["jobs"]["notice"]
    assert guild.missions == []
    with pytest.raises(ValueError):
        hub.on_board(type(hub.board).accept, "apothecary_mushrooms")


def test_a_sanctuary_opens_on_its_board_and_buys_a_dragon_egg():
    from gartok import lair
    guild = _guild("nature_grove")
    guild.reveal_node("nature_grove")
    game = Game(MapSession(guild))
    g = guild.groups[0]
    assert game.session.act(g.gid, "shrine") == {"screen": "hub"}
    hub = game.session
    st = hub.state()
    assert st["tab"] == "jobs" and st["jobs"]["egg"] is None
    g.members[1].give_to_pack(lair.EGG, 1)
    assert hub.state()["jobs"]["egg"]["on"]
    money = g.members[1].money
    st = hub.on_board(type(hub.board).sell_egg)
    assert g.members[1].count_of(lair.EGG) == 0 and g.members[1].money == money + lair.SHRINE_EGG_PRICE
    assert st["jobs"]["egg"] is None and st["jobs"]["notice"]


def _rite(node="nature_grove", rep=2, members=2):
    from gartok import rite
    guild = _guild(node)
    del guild.groups[0].members[members:]
    guild.reveal_node(node)
    guild.reputation[rite.FACTION[rite.school_at(node)]] = rep
    for u in guild.groups[0].members:
        u.magic_sources = []
    game = Game(MapSession(guild))
    g = guild.groups[0]
    assert game.session.act(g.gid, "shrine") == {"screen": "hub"}
    hub = game.session
    return hub, guild, g, hub.verb("tab", True)(hub, {"key": "initiation"})["initiation"]


def test_the_initiation_tab_shows_the_schools_terms_and_who_may_stay():
    hub, _, g, i = _rite()
    assert next(t for t in hub.state()["tabs"] if t["key"] == "initiation")["live"]
    assert i["school"] == "Nature" and i["terms"][0]["ok"] and i["action"] is None
    assert [m["uid"] for m in i["members"]] == [u.uid for u in g.members] and all(m["on"] for m in i["members"])
    i = hub.verb("novice", True)(hub, {"uid": g.members[1].uid})["initiation"]
    assert i["picked"] == g.members[1].name and i["action"] == "BEGIN THE RITE"
    assert hub.novice(g.members[1].uid)["initiation"]["picked"] is None
    with pytest.raises(ValueError):
        hub.begin_rite()


def test_a_school_the_guild_has_no_standing_with_takes_nobody_and_says_why():
    hub, _, g, i = _rite(rep=1)
    assert not i["terms"][0]["ok"] and not any(m["on"] for m in i["members"])
    i = hub.novice(g.members[0].uid)["initiation"]
    assert i["picked"] is None and "reputation" in i["notice"]


def test_the_faith_rite_asks_for_a_holy_symbol():
    hub, _, g, _ = _rite("faith_cathedral")
    for u in g.members:
        u.remove_named("Holy Symbol", u.count_of("Holy Symbol"))
    i = hub.state()["initiation"]
    assert all("Holy Symbol" in m["note"] for m in i["members"])
    g.members[1].give_to_pack("Holy Symbol", 1)
    assert all(m["on"] for m in hub.state()["initiation"]["members"])


def test_beginning_the_rite_splits_the_novice_off_to_board_and_keeps_the_tab_up(saves):
    from gartok import rite
    hub, guild, g, _ = _rite()
    a, b = g.members
    hub.novice(b.uid)
    st = hub.verb("begin_rite", True)(hub, {})
    assert hub.game.session is hub and st["tab"] == "initiation" and st["initiation"]["report"]
    assert g.members == [a] and b.rite_school == "nature"
    ward = next(x for x in guild.groups if b in x.members)
    assert ward.order.kind == "garrison" and ward.order.job == rite.JOB
    assert next(m for m in st["initiation"]["members"] if m["uid"] == a.uid)["on"]


def test_a_band_that_boards_whole_goes_back_to_the_map(monkeypatch):
    hub, guild, g, _ = _rite()
    monkeypatch.setattr(Guild, "free_slots", property(lambda self: 0))
    hub.novice(g.members[0].uid)
    st = hub.begin_rite()
    assert st["screen"] == "map" and isinstance(hub.game.session, MapSession)
    assert len(guild.groups) == 1 and g.order.job == "rite"


def test_a_job_won_by_a_fight_is_taken_here_and_met_on_the_map(monkeypatch):
    from gartok import missions
    from gartok.web.jobs_tab import JobsTab
    guild = _guild("faith_cathedral")
    tab = JobsTab(guild, guild.groups[0], world.node("faith_cathedral"))
    monkeypatch.setattr(tab.b, "get_templates", lambda: [missions.FAITH_BATTLEFIELD])
    monkeypatch.setattr(missions, "offers_at", lambda g, n: [missions.FAITH_BATTLEFIELD])
    assert tab.state()["jobs"][0]["button"]["on"]
    tab.accept(missions.FAITH_BATTLEFIELD.id)
    b = tab.state()["jobs"][0]["button"]
    assert b["verb"] == "turn_in" and not b["on"] and "BATTLEFIELD" in b["label"]


def _bench(node="carpenter", kind="carpenter", lumber=3):
    hub, guild, g = _hub(node, kind)
    g.members[0].recipes.append("Club")
    for u in g.members:
        u.remove_named("Lumber", u.count_of("Lumber"))
    g.members[0].give_to_pack("Lumber", lumber)
    return hub, guild, g


def test_a_workbench_lists_who_works_here_and_the_picked_ones_recipes_with_what_they_use():
    hub, _, g = _bench(lumber=0)
    st = hub.state()
    assert st["tab"] == "carpenter" and next(t for t in st["tabs"] if t["key"] == "carpenter")["live"]
    c = st["craft"]
    crafters = [u["uid"] for u in c["crafters"]]
    assert g.members[0].uid == crafters[0] and c["crafters"][0]["picked"] and c["who"] == g.members[0].name
    club = next(r for r in c["recipes"] if r["id"] == "Club")
    assert club["uses"] == [{"name": "Lumber", "need": 1, "have": 0}] and not club["can"] and club["makes"] == 2
    assert all(items.get_recipe(r["id"]).station == "carpenter" for r in c["recipes"])
    g.members[1].give_to_pack("Lumber", 2)
    club = next(r for r in hub.state()["craft"]["recipes"] if r["id"] == "Club")
    assert club["can"] and club["uses"][0]["have"] == 2 and club["alone"] == "not in their own pack"
    with pytest.raises(ValueError):
        hub.crafter("nobody")


def test_a_stint_the_group_waits_rolls_the_craft_passes_the_clock_and_stays_on_the_tab(saves):
    hub, guild, g = _bench()
    smith = g.members[0]
    start = guild.clock.seconds
    st = hub.verb("craft", True)(hub, {"recipe": "Club", "hours": 8})
    assert hub.game.session is hub and st["tab"] == "carpenter" and st["craft"]["report"]
    assert smith.count_of("Club") >= 2 and smith.count_of("Lumber") < 3
    assert guild.clock.seconds > start
    with pytest.raises(ValueError):
        hub.craft("Club", 16, False)
    with pytest.raises(ValueError):
        hub.craft("Longsword", 4, False)


def test_a_stint_alone_splits_the_crafter_off_and_goes_back_to_the_map():
    hub, guild, g = _bench()
    smith = g.members[0]
    st = hub.craft("Club", 8, True)
    assert st["screen"] == "map" and isinstance(hub.game.session, MapSession)
    assert smith not in g.members and any(x.order and x.order.task == "craft" for x in guild.groups)


def test_a_stint_alone_with_no_free_slot_is_refused_on_the_tab(monkeypatch):
    hub, guild, _ = _bench()
    monkeypatch.setattr(Guild, "free_slots", property(lambda self: 0))
    club = next(r for r in hub.state()["craft"]["recipes"] if r["id"] == "Club")
    assert club["alone"] == "no free group slot"
    st = hub.craft("Club", 8, True)
    assert st["tab"] == "carpenter" and st["craft"]["notice"] and len(guild.groups) == 1


def test_the_forge_apothecary_and_library_benches_work_at_their_own_station():
    from gartok.web.craft_tab import CraftTab
    for node, key, station in (("smith", "craft", "forge"), ("apothecary", "craft", "apothecary"),
                               ("library", "craft", "scriptorium"), ("carpenter", "carpenter", "carpenter")):
        guild = _guild(node)
        assert CraftTab(guild, guild.groups[0], world.node(node), key).station == station


def _purse(g):
    return sum(u.money for u in (*g.members, *g.stores))


def test_the_farm_opens_on_its_shop_beside_the_stables_which_list_the_animals_and_the_herd():
    hub, _, g = _hub("farm", "stable")
    st = hub.state()
    assert st["tab"] == "shop" and [t["key"] for t in st["tabs"]] == ["shop", "stable"] and all(t["live"] for t in st["tabs"])
    s = hub.pick_tab("stable")["stable"]
    assert [o["name"] for o in s["offers"]] == list(LIVESTOCK) and s["herd"] == []
    assert s["capacity"] == g.herd_capacity and s["purse"] == _purse(g)
    assert all(o["portrait"].startswith("/assets/portraits/") for o in s["offers"])
    horse = next(o for o in s["offers"] if o["name"] == "Horse")
    assert horse["can"] == (_purse(g) >= horse["price"])


def test_buying_an_animal_pays_from_the_purse_and_the_shop_tab_carries_it_as_a_pack():
    hub, _, g = _hub("farm", "stable")
    hub.pick_tab("shop")
    purse = _purse(g)
    st = hub.verb("buy_animal", True)(hub, {"species": "Donkey"})
    donkey = g.herd[0]
    assert st["tab"] == "stable" and st["stable"]["herd"][0]["uid"] == donkey.uid and st["stable"]["notice"]
    assert _purse(g) == purse - donkey.price
    assert any(p["id"] == donkey.uid for p in hub.pick_tab("shop")["shop"]["packs"])
    with pytest.raises(ValueError):
        hub.verb("buy_animal", True)(hub, {"species": "Dragon"})


def test_a_full_herd_or_a_short_purse_refuses_the_animal_with_a_notice(monkeypatch):
    hub, _, g = _hub("farm", "stable", coins=1000)
    monkeypatch.setattr(Group, "herd_capacity", property(lambda self: 1))
    hub.verb("buy_animal", True)(hub, {"species": "Donkey"})
    st = hub.verb("buy_animal", True)(hub, {"species": "Ox"})
    assert len(g.herd) == 1 and st["stable"]["full"] and "herd" in st["stable"]["notice"]
    assert all(o["why"] == "the herd is full" and not o["can"] for o in st["stable"]["offers"])
    hub, _, g = _hub("farm", "stable", coins=10)
    st = hub.verb("buy_animal", True)(hub, {"species": "Horse"})
    assert not g.herd and "costs" in st["stable"]["notice"]


def test_tack_is_fitted_once_and_an_animal_sells_back_to_the_leader_only_unloaded():
    hub, _, g = _hub("farm", "stable")
    uid = hub.verb("buy_animal", True)(hub, {"species": "Donkey"})["stable"]["herd"][0]["uid"]
    a = g.herd[0]
    purse = _purse(g)
    st = hub.verb("fit", True)(hub, {"uid": uid, "tack": PACK_SADDLE})
    kept = st["stable"]["herd"][0]
    assert a.tack == PACK_SADDLE and kept["fits"] == [] and kept["job"] == "carries cargo"
    assert _purse(g) == purse - items.get(PACK_SADDLE).price
    with pytest.raises(ValueError):
        hub.verb("fit", True)(hub, {"uid": uid, "tack": HARNESS})
    a.give_to_pack("Potato", 1)
    st = hub.verb("sell_animal", True)(hub, {"uid": uid})
    assert g.herd == [a] and st["stable"]["herd"][0]["loaded"] and "unload" in st["stable"]["notice"]
    a.remove_named("Potato", 1)
    before = g.leader.money
    st = hub.verb("sell_animal", True)(hub, {"uid": uid})
    assert not g.herd and g.leader.money == before + economy.SELL_FACTOR * a.price
    assert g.leader.count_of(PACK_SADDLE) == 1
    with pytest.raises(ValueError):
        hub.verb("sell_animal", True)(hub, {"uid": uid})


def test_the_wagon_yard_sells_a_wagon_and_buys_back_only_an_empty_one():
    hub, _, g = _hub("carpenter", "carpenter")
    assert next(t for t in hub.state()["tabs"] if t["key"] == "wagons")["live"]
    w = hub.pick_tab("wagons")["wagons"]
    assert [o["name"] for o in w["offers"]] == list(VEHICLES) and w["wagons"] == []
    purse = _purse(g)
    st = hub.verb("buy_wagon", True)(hub, {"kind": "Cart"})
    cart = g.wagons[0]
    assert st["tab"] == "wagons" and st["wagons"]["wagons"][0]["uid"] == cart.uid
    assert _purse(g) == purse - cart.price and not st["wagons"]["wagons"][0]["pulled"]
    cart.give_to_pack("Potato", 1)
    st = hub.verb("sell_wagon", True)(hub, {"uid": cart.uid})
    assert g.wagons == [cart] and "unload" in st["wagons"]["notice"]
    cart.remove_named("Potato", 1)
    st = hub.verb("sell_wagon", True)(hub, {"uid": cart.uid})
    assert not g.wagons and st["wagons"]["wagons"] == []
    with pytest.raises(ValueError):
        hub.verb("buy_wagon", True)(hub, {"kind": "Chariot"})


def _tavern(coins=200):
    hub, guild, g = _hub("tavern", "recruit", coins)
    guild.leader = g.leader
    pool = hub.tavern.s.candidates      # rolled on the first visit
    for u in g.members:
        u.languages = sorted({*u.languages, *(lang for c in pool for lang in c.languages)})
    return hub, guild, g


def _roll(monkeypatch, ours, theirs):
    """Every pitch rolls `ours` against `theirs` (a Halfling's luck rerolls `ours`), with a slot to spare."""
    rolls = [ours, theirs]
    monkeypatch.setattr(recruit.random, "randint", lambda a, b: rolls.pop(0) if rolls else ours)
    monkeypatch.setattr(recruit, "capacity", lambda guild, u: 3)


def test_the_tavern_opens_on_its_recruits_with_the_strangers_and_the_picked_ones_dossier():
    hub, guild, g = _tavern()
    st = hub.state()
    assert st["tab"] == "recruits" and [t["key"] for t in st["tabs"]] == ["shop", "recruits", "rooms", "perform"]
    assert all(t["live"] for t in st["tabs"])
    t = st["tavern"]
    assert [c["uid"] for c in t["strangers"]] == [c.uid for c in guild.taverna_pool]
    assert t["strangers"][0]["picked"] and t["dossier"]["uid"] == guild.taverna_pool[0].uid
    assert {m["uid"] for m in t["dossier"]["pitchers"]} == {u.uid for u in g.members}
    assert [c["label"] for c in t["cards"]][:3] == ["guild size", "crowd penalty", "new faces in"]
    second = guild.taverna_pool[1]
    t = hub.verb("candidate", True)(hub, {"uid": second.uid})["tavern"]
    assert t["dossier"]["uid"] == second.uid and t["strangers"][1]["picked"]
    with pytest.raises(ValueError):
        hub.verb("candidate", True)(hub, {"uid": "nobody"})


def test_a_pitch_won_signs_the_stranger_into_the_band_and_saves(saves, monkeypatch):
    hub, guild, g = _tavern()
    hub.map.world_id = "w1"
    cand = guild.taverna_pool[0]
    hub.verb("recruiter", True)(hub, {"uid": g.leader.uid})
    _roll(monkeypatch, 20, 1)
    t = hub.verb("convince", True)(hub, {})["tavern"]
    assert cand in g.members and cand.recruited_by == g.leader.uid and cand not in guild.taverna_pool
    assert t["signed"]["name"] == cand.name and t["signed"]["by"] == g.leader.name
    assert cand.uid not in [c["uid"] for c in t["strangers"]]
    assert any(p["id"] == cand.uid for p in hub.pick_tab("shop")["shop"]["packs"])
    assert len(persist.load_game("w1").roster) == 3


def test_a_pitch_lost_bars_that_recruiter_from_the_stranger_until_the_crowd_changes(monkeypatch):
    hub, guild, g = _tavern()
    cand = guild.taverna_pool[0]
    hub.verb("recruiter", True)(hub, {"uid": g.leader.uid})
    _roll(monkeypatch, 1, 20)
    t = hub.verb("convince", True)(hub, {})["tavern"]
    assert cand not in g.members and "turns" in t["notice"]
    d = t["dossier"]
    assert d["last"]["ok"] is False and d["last"]["ours_total"] < d["last"]["theirs_total"]
    me = next(m for m in d["pitchers"] if m["uid"] == g.leader.uid)
    assert me["status"]["text"] == "already tried this week" and not d["button"]["on"]
    assert t["strangers"][0]["status"]["tone"] == "bad"


def test_a_study_target_is_set_from_what_the_band_carries_and_the_rooms_rent_and_cancel(saves):
    hub, _, g = _tavern()
    u = g.members[1]
    lang = next(lang for lang in sorted(data.LANGUAGES) if lang not in u.languages)
    st = hub.pick_tab("rooms")["tavern"]
    assert not st["studying"] and st["studiers"] == 0
    st = hub.verb("rent_study", True)(hub, {})
    assert g.order is None and "target" in st["tavern"]["notice"]
    g.leader.give_to_pack(f"Dictionary of {lang}", 1)
    me = next(m for m in hub.state()["tavern"]["students"] if m["uid"] == u.uid)
    assert lang in [o["id"] for o in me["options"]]
    st = hub.verb("study_target", True)(hub, {"uid": u.uid, "id": lang})["tavern"]
    assert u.study_target == lang and st["studiers"] == 1 and st["today"] == st["cost"]
    with pytest.raises(ValueError):
        hub.verb("study_target", True)(hub, {"uid": u.uid, "id": "Nothing"})
    st = hub.verb("rent_study", True)(hub, {})["tavern"]
    assert g.order.kind == "garrison" and g.order.job == "study" and st["studying"]
    st = hub.verb("cancel_study", True)(hub, {})["tavern"]
    assert g.order is None and not st["studying"]
    st = hub.verb("stop_study", True)(hub, {"uid": u.uid})["tavern"]
    assert not u.study_target and st["studiers"] == 0


def test_a_show_seats_who_carries_an_instrument_pays_the_tips_and_passes_the_clock(monkeypatch):
    hub, guild, g = _tavern()
    player, other = g.members
    player.give_to_pack(economy.PERFORM_ITEM, 1)
    if other.count_of(economy.PERFORM_ITEM):
        other.remove_named(economy.PERFORM_ITEM, other.count_of(economy.PERFORM_ITEM))
    st = hub.pick_tab("perform")["tavern"]
    seat = {m["uid"]: m for m in st["players"]}
    assert seat[player.uid]["on"] and not seat[other.uid]["has"] and st["can"]
    with pytest.raises(ValueError):
        hub.verb("seat", True)(hub, {"uid": other.uid})
    st = hub.verb("show_hours", True)(hub, {"hours": 2})["tavern"]
    assert st["hours"] == 2
    monkeypatch.setattr(economy, "perform_pay", lambda hours, mod: 5)
    before, then = player.money, guild.clock.seconds
    st = hub.verb("perform", True)(hub, {})
    assert st["tab"] == "perform" and st["tavern"]["report"] and player.money == before + 5
    assert guild.clock.seconds > then
    st = hub.verb("seat", True)(hub, {"uid": player.uid})["tavern"]
    assert not st["can"] and not next(m for m in st["players"] if m["uid"] == player.uid)["on"]
    with pytest.raises(ValueError):
        hub.verb("show_hours", True)(hub, {"hours": 3})


def test_a_band_studying_at_the_tavern_enters_it_from_the_map():
    guild = _guild("tavern")
    game = Game(MapSession(guild))
    g = guild.groups[0]
    g.order = orders.garrison("study")
    assert game.session.act(g.gid, "visit_tavern") == {"screen": "hub"}
    assert game.session.state()["tab"] == "recruits" and game.session.tavern.s._studying()


def _cells(monkeypatch, coins=1000):
    monkeypatch.setattr(recruit, "capacity", lambda guild, u: 3)
    hub, guild, g = _hub("prison", "prison", coins)
    guild.leader = g.leader
    for u in g.members:
        u.languages = sorted({*u.languages, *(lang for c in hub.tavern.s.candidates for lang in c.languages)})
    return hub, guild, g


def test_the_prison_opens_on_its_cells_with_each_prisoners_bail(monkeypatch):
    hub, guild, _ = _cells(monkeypatch)
    st = hub.state()
    assert [t["key"] for t in st["tabs"]] == ["prison"] and st["tab"] == "prison" and st["tabs"][0]["live"]
    assert st["keeper"]["name"] == world.vendor("prison", "prison").name
    t = st["tavern"]
    assert t["prison"] and [c["uid"] for c in t["strangers"]] == [c.uid for c in guild.prison_pool]
    cand = guild.prison_pool[0]
    bail = recruit.bail_cost(cand)
    assert t["strangers"][0]["note"].endswith(f"bail ${bail:,}")
    assert t["dossier"]["bail"] == {"cost": f"${bail:,}", "held": f"${2000:,}", "ok": True}
    assert t["dossier"]["button"]["label"] == f"Pay the ${bail:,} bail and convince"
    st = hub.verb("candidate", True)(hub, {"uid": guild.prison_pool[1].uid})
    assert st["tab"] == "prison" and st["tavern"]["dossier"]["uid"] == guild.prison_pool[1].uid


def test_bailing_a_prisoner_pays_before_the_pitch_and_a_won_pitch_signs_them(saves, monkeypatch):
    hub, guild, g = _cells(monkeypatch)
    hub.map.world_id = "w1"
    cand = guild.prison_pool[0]
    bail = recruit.bail_cost(cand)
    _roll(monkeypatch, 20, 1)
    t = hub.verb("convince", True)(hub, {})["tavern"]
    assert cand in g.members and cand not in guild.prison_pool and t["signed"]["name"] == cand.name
    assert sum(u.money for u in g.members if u is not cand) == 2000 - bail
    assert "obj_recruit_prison" in guild.objectives_done
    assert len(persist.load_game("w1").roster) == 3


def test_a_lost_pitch_keeps_the_bail_and_a_short_purse_cannot_pay_it(monkeypatch):
    hub, guild, g = _cells(monkeypatch)
    cand = guild.prison_pool[0]
    bail = recruit.bail_cost(cand)
    _roll(monkeypatch, 1, 20)
    t = hub.verb("convince", True)(hub, {})["tavern"]
    assert cand not in g.members and "walks away free" in t["notice"]
    assert sum(u.money for u in g.members) == 2000 - bail
    hub, guild, g = _cells(monkeypatch, coins=0)
    d = hub.state()["tavern"]["dossier"]
    assert not d["bail"]["ok"] and not d["button"]["on"] and d["button"]["label"].startswith("Cannot afford")


def _vault(coins=300, rent=True):
    hub, guild, g = _hub("city", "bank", coins)
    if rent:
        hub.verb("vault_service", True)(hub, {"key": "rent"})
    return hub, guild, g


def _row(rows, name):
    return next((r for r in rows if r["name"] == name), None)


def test_the_bank_opens_on_its_vault_beside_the_bankers_jobs():
    hub, _, g = _vault(rent=False)
    st = hub.state()
    assert [t["key"] for t in st["tabs"]] == ["vault", "jobs"] and st["tab"] == "vault"
    assert st["keeper"]["name"] == world.vendor("city", "bank").name
    v = st["vault"]
    assert not v["chest"]["open"] and [p["id"] for p in v["packs"]] == [u.uid for u in g.members]
    rent = next(s for s in v["services"] if s["key"] == "rent")
    assert rent["on"] and not next(s for s in v["services"] if s["key"] == "buy_property")["on"]
    with pytest.raises(ValueError):
        hub.verb("vault_service", True)(hub, {"key": "buy_property"})
    u = g.members[0]
    st = hub.verb("vault_move", True)(hub, {"picks": [{"from": u.uid, "loc": 0}], "to": "bank"})
    assert "rent a strongbox first" in st["vault"]["notice"]
    jobs = hub.pick_tab("jobs")["jobs"]["jobs"]
    assert [j["id"] for j in jobs] == ["bankers_trust_chest"]


def test_renting_the_strongbox_pays_the_bankers_and_a_short_purse_cannot():
    hub, _, _ = _vault(rent=False)
    v = hub.verb("vault_service", True)(hub, {"key": "rent"})["vault"]
    assert v["chest"]["open"] and v["chest"]["capacity"] == economy.BANK_CHEST_CAPACITY
    assert v["purse"] == 600 - economy.BANK_CHEST_PRICE
    assert not any(s["key"] == "rent" for s in v["services"])
    hub, guild, _ = _vault(coins=10, rent=False)
    assert not next(s for s in hub.state()["vault"]["services"] if s["key"] == "rent")["on"]
    with pytest.raises(ValueError):
        hub.verb("vault_service", True)(hub, {"key": "rent"})
    assert not guild.bank.open


def test_items_go_into_the_chest_part_of_a_stack_at_a_time_and_come_back_out():
    hub, _, g = _vault()
    u, v = g.members
    loc = next(i for i, e in enumerate(u._base_inventory) if e[0] == "Potato")
    st = hub.verb("vault_move", True)(hub, {"picks": [{"from": u.uid, "loc": loc, "qty": 3}], "to": "bank"})["vault"]
    assert _row(st["chest"]["rows"], "Potato")["qty"] == 3 and u.count_of("Potato") == 1
    st = hub.verb("vault_move", True)(hub, {"picks": [{"from": "bank", "loc": 0, "qty": 2}], "to": v.uid})["vault"]
    assert _row(st["chest"]["rows"], "Potato")["qty"] == 1 and v.count_of("Potato") == 6
    with pytest.raises(ValueError):
        hub.verb("vault_move", True)(hub, {"picks": [{"from": "bank", "loc": 9}], "to": v.uid})


def test_the_chest_refuses_what_it_cannot_hold_and_a_pack_what_it_cannot_carry():
    hub, guild, g = _vault()
    u = g.members[0]
    u.give_to_pack("Lumber", 40)
    loc = next(i for i, e in enumerate(u._base_inventory) if e[0] == "Lumber")
    st = hub.verb("vault_move", True)(hub, {"picks": [{"from": u.uid, "loc": loc}], "to": "bank"})["vault"]
    assert "won't fit" in st["notice"] and not st["chest"]["rows"] and u.count_of("Lumber") == 40
    guild.bank.put("Lumber", 10)
    u.give_to_pack("Lumber", 200)
    st = hub.verb("vault_move", True)(hub, {"picks": [{"from": "bank", "loc": 0}], "to": u.uid})["vault"]
    assert "won't fit" in st["notice"] and _row(st["chest"]["rows"], "Lumber")["qty"] == 10


def test_a_weapon_from_the_chest_goes_straight_into_a_hand():
    hub, guild, g = _vault()
    u = g.members[0]
    u.take_from_hand()
    guild.bank.put("Dagger")
    st = hub.verb("vault_move", True)(hub, {"picks": [{"from": "bank", "loc": 0}], "to": u.uid, "zone": "hand"})["vault"]
    assert u.equipped_weapon == "Dagger" and not st["chest"]["rows"]
    hand = next(w for w in next(p for p in st["packs"] if p["id"] == u.uid)["worn"] if w["zone"] == "hand")
    assert hand["name"] == "Dagger"
    hub.verb("vault_move", True)(hub, {"picks": [{"from": u.uid, "loc": "hand"}], "to": "bank"})
    assert u.equipped_weapon is None and guild.bank.count_of("Dagger") == 1


def test_copper_mints_gold_at_the_fee_and_gold_melts_back():
    hub, guild, g = _vault()
    u = g.members[0]
    before = u.money
    st = hub.verb("vault_gold", True)(hub, {"from": u.uid, "n": 1})["vault"]
    assert u.count_of(items.GOLD_ITEM) == 1 and u.money == before - economy.GOLD_FEE
    assert "minted 1 gold" in st["notice"]
    assert _row(next(p for p in st["packs"] if p["id"] == u.uid)["pack"], items.GOLD_ITEM)["melt"] == 1
    hub.verb("vault_gold", True)(hub, {"from": u.uid, "n": 1, "melt": True})
    assert u.count_of(items.GOLD_ITEM) == 0 and u.money == before - 2 * economy.GOLD_FEE
    with pytest.raises(ValueError):
        hub.verb("vault_gold", True)(hub, {"from": u.uid, "n": 50})
    guild.bank.put(items.COIN_ITEM, economy.gold_price(1))
    hub.verb("vault_gold", True)(hub, {"from": "bank", "n": 1})
    assert guild.bank.count_of(items.GOLD_ITEM) == 1 and guild.bank.count_of(items.COIN_ITEM) == 0


def test_the_bankers_test_of_trust_is_taken_on_the_jobs_tab():
    hub, _, g = _vault()
    hub.pick_tab("jobs")
    st = hub.verb("accept", True)(hub, {"id": "bankers_trust_chest"})
    job = st["jobs"]["jobs"][0]
    assert job["taken"] and g.leader.count_of(data.MISSION_CHEST_ITEM) == 1


def _house(coins=1000, owned=True, oven=False, rep=economy.CITY_PROPERTY_REP_GATE):
    guild = _guild("city", coins)
    guild.reputation["bankers"] = rep
    if owned:
        guild.buy_city_property()
    if oven:
        guild.buy_oven()
    game = Game(MapSession(guild))
    g = guild.groups[0]
    assert game.session.act(g.gid, "property") == {"screen": "hub"}
    return game.session, guild, g


def test_the_house_before_it_is_bought_is_one_tab_that_sells_it_once_the_bankers_trust_the_guild():
    hub, _, _ = _house(owned=False, rep=0)
    st = hub.state()
    assert [t["key"] for t in st["tabs"]] == ["property"] and st["tab"] == "property"
    v = st["vault"]
    assert not v["chest"]["open"] and v["chest"]["owner"] == "house" and v["gold"] is None and not v["distribute"]
    assert not next(s for s in v["services"] if s["key"] == "buy")["on"]
    with pytest.raises(ValueError):
        hub.verb("vault_service", True)(hub, {"key": "buy"})
    hub, guild, _ = _house(owned=False)
    st = hub.verb("vault_service", True)(hub, {"key": "buy"})
    assert guild.house.owned and "bought a house" in st["vault"]["notice"]
    assert [t["key"] for t in st["tabs"]] == ["property", "garage"]
    assert st["vault"]["purse"] == 2000 - economy.CITY_PROPERTY_PRICE and st["vault"]["cards"][0]["label"] == "next tax"
    assert any(s["key"] == "oven" for s in st["vault"]["services"])


def test_the_house_stows_and_gives_back_but_mints_no_gold():
    hub, guild, g = _house()
    u, v = g.members
    loc = next(i for i, e in enumerate(u._base_inventory) if e[0] == "Potato")
    st = hub.verb("vault_move", True)(hub, {"picks": [{"from": u.uid, "loc": loc, "qty": 3}], "to": "house"})["vault"]
    assert _row(st["chest"]["rows"], "Potato")["qty"] == 3 and guild.house.stash.count_of("Potato") == 3
    assert "mint" not in _row(next(p for p in st["packs"] if p["id"] == u.uid)["pack"], items.COIN_ITEM)
    hub.verb("vault_move", True)(hub, {"picks": [{"from": "house", "loc": 0}], "to": v.uid})
    assert guild.house.stash.count_of("Potato") == 0 and v.count_of("Potato") == 7
    with pytest.raises(ValueError):
        hub.verb("vault_gold", True)(hub, {"from": u.uid, "n": 1})
    with pytest.raises(ValueError):
        hub.verb("vault_distribute", True)(hub, {})


def test_an_oven_opens_the_kitchen_where_the_band_cooks_jerky():
    hub, guild, g = _house()
    st = hub.verb("vault_service", True)(hub, {"key": "oven"})
    assert guild.house.oven and [t["key"] for t in st["tabs"]] == ["property", "kitchen", "garage"]
    assert st["vault"]["purse"] == 2000 - economy.OVEN_PRICE
    cook = g.members[0]
    cook.give_to_pack("Meat", 2)
    cook.give_to_pack("Salt", 1)
    k = hub.pick_tab("kitchen")["craft"]
    jerky = next(r for r in k["recipes"] if r["id"] == "Jerky")
    assert k["what"] == "cook what the pack carries" and jerky["can"]
    t0 = guild.clock.seconds
    st = hub.verb("craft", True)(hub, {"recipe": "Jerky", "hours": 8})
    assert st["tab"] == "kitchen" and guild.clock.seconds > t0 and st["craft"]["report"]


def test_paying_the_debt_to_the_bankers_comes_out_of_the_purse():
    hub, guild, _ = _house(owned=False)
    guild.bankers_debt = 90
    st = hub.state()
    assert st["vault"]["cards"][0]["label"] == "owed to the bankers"
    st = hub.verb("vault_service", True)(hub, {"key": "pay_debt"})["vault"]
    assert guild.bankers_debt == 0 and st["purse"] == 2000 - 90 and "debt cleared" in st["notice"]


def test_the_garage_builds_bays_and_parks_a_wagon_and_an_animal_and_takes_them_out():
    hub, guild, g = _house(coins=2000)
    cart = Wagon("Cart")
    g.add_wagon(cart)
    st = hub.pick_tab("garage")["garage"]
    assert not st["open"] and st["kept"][0]["uid"] == cart.uid and not st["kept"][0]["can"]
    st = hub.verb("garage_bay", True)(hub, {})["garage"]
    assert st["open"] and st["tier"] == 1 and st["purse"] == 4000 - economy.GARAGE_PRICE
    st = hub.verb("garage_park", True)(hub, {"uid": cart.uid})["garage"]
    assert guild.house.garage.wagons == [cart] and not g.wagons and st["parked"][0]["uid"] == cart.uid
    g.add_wagon(Wagon("Cart"))
    st = hub.state()["garage"]
    assert not st["kept"][0]["can"] and st["kept"][0]["why"] == "every bay holds a wagon"
    st = hub.verb("garage_take", True)(hub, {"uid": cart.uid})["garage"]
    assert cart in g.wagons and not guild.house.garage.wagons and "rejoins" in st["notice"]
    with pytest.raises(ValueError):
        hub.verb("garage_take", True)(hub, {"uid": "nobody"})


def test_a_wagon_mended_in_the_garage_takes_lumber_and_an_hour_of_the_clock():
    hub, guild, g = _house()
    cart = Wagon("Cart")
    cart.hp = 0
    g.add_wagon(cart)
    st = hub.pick_tab("garage")["garage"]
    assert st["kept"][0]["broken"] and not st["kept"][0]["repair"]["can"]
    g.members[0].give_to_pack("Lumber", cart.repair_cost)
    t0 = guild.clock.seconds
    st = hub.verb("garage_repair", True)(hub, {"uid": cart.uid})
    assert st["tab"] == "garage" and guild.clock.seconds > t0 and g.members[0].count_of("Lumber") == 0
    assert st["garage"]["notice"]


def test_a_house_too_far_behind_on_the_tax_meets_the_bankers_notice_first():
    hub, guild, _ = _house()
    guild.house.missed_payments = economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT
    st = hub.state()
    assert st["repossession"]["owed"] == economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT * economy.CITY_PROPERTY_TAX
    assert "vault" not in st
    with pytest.raises(ValueError):
        hub.verb("vault_service", True)(hub, {"key": "oven"})
    st = hub.verb("repossess", True)(hub, {"choice": "return"})
    assert st["screen"] == "map" and not guild.house.owned and guild.bankers_debt > 0
    assert any("returned to the Bankers" in n for n in st["notices"])
    hub, guild, _ = _house()
    guild.house.missed_payments = economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT
    st = hub.verb("repossess", True)(hub, {"choice": "squat"})
    assert st["screen"] == "map" and guild.house.squatting and guild.bankers_debt == 0
    with pytest.raises(ValueError):
        hub.verb("repossess", True)(hub, {"choice": "squat"})


def test_a_place_with_no_hub_in_the_browser_still_opens_the_away_card():
    guild = _guild("city")
    game = Game(MapSession(guild))
    assert game.session.act(guild.groups[0].gid, "trust") == {"screen": "away"}
    assert isinstance(game.session, AwaySession)


def test_the_server_routes_the_hub_verbs(saves):
    guild = _guild("market")
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
        assert post("/api/map/act", {"gid": gid, "key": "market"}) == {"screen": "hub"}
        st = json.loads(urllib.request.urlopen(url + "/api/hub/state").read())
        r = _ware(st)
        uid = st["shop"]["packs"][0]["id"]
        st = post("/api/hub/buy", {"name": r["name"], "to": uid})
        assert any(p["name"] == r["name"] for p in st["shop"]["packs"][0]["pack"])
        with pytest.raises(urllib.error.HTTPError) as e:
            post("/api/hub/sell", {"picks": [{"from": uid, "loc": 99}]})
        assert e.value.code == 409
        with pytest.raises(urllib.error.HTTPError) as e:
            post("/api/map/travel", {"gid": gid, "node": "city"})
        assert e.value.code == 409
        assert post("/api/hub/back", {})["screen"] == "map"
    finally:
        srv.shutdown()
        srv.server_close()
