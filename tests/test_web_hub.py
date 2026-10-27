"""A place's hub in the browser: its tabs and keeper, and the shop's trades through the same session the
server routes to."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from gartok import economy, gather, items, medic, orders, persist, recorder
from gartok.group import Group
from gartok.guild import Guild
from gartok.unit import Unit
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
    assert "away" in st and "shop" not in st
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


def test_a_place_with_no_hub_in_the_browser_still_opens_the_away_card():
    guild = _guild("city")
    game = Game(MapSession(guild))
    assert game.session.act(guild.groups[0].gid, "bank") == {"screen": "away"}
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
