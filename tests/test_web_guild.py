"""The guild's sheet in the browser: its four tabs (members, bands, the charter, reputations) through the
same session the server routes to."""

import pytest

from gartok import orders, persist, recorder
from gartok.animals import HARNESS, Animal
from gartok.captives import Captive
from gartok.group import Group
from gartok.guild import Guild
from gartok.guild_screen import _needs_attention
from gartok.unit import Unit
from gartok.wagon import Wagon
from gartok.web.away_session import AwaySession
from gartok.web.guild_session import GuildSession
from gartok.web.map_session import MapSession
from gartok.web.server import Game


def _units(n):
    units = [Unit("Fighter") for _ in range(n)]
    for u in units:
        u.give_to_pack("Potato", 4 - u.count_of("Potato"))
    return units


def _guild():
    a, b = _units(3), _units(2)
    return Guild(None, groups=[Group(a, node="city", leader=a[0]), Group(b, node="tavern", leader=b[0])],
                 name="Ink Hands")


@pytest.fixture
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    yield tmp_path
    recorder.detach()


def _sheet(key="guild", which=0):
    guild = _guild()
    game = Game(MapSession(guild))
    g = guild.groups[which]
    assert game.session.act(g.gid, key) == {"screen": "guild"}
    return game.session, guild, g


def _col(st, unit):
    return next(p for p in st["bands"]["packs"] if p["id"] == unit.uid)


def _row(st, unit, name):
    return next((r for r in _col(st, unit)["pack"] if r["name"] == name), None)


def test_the_maps_guild_button_opens_the_sheet_on_members_and_gear_opens_that_band():
    sheet, guild, _ = _sheet("guild")
    assert isinstance(sheet, GuildSession)
    st = sheet.state()
    assert st["tab"] == "members" and [t["key"] for t in st["tabs"]] == ["members", "bands", "guild", "reputations"]
    assert st["count"] == 5 and st["band_count"] == 2
    gear, guild, g = _sheet("manage_group", which=1)
    st = gear.state()
    assert st["tab"] == "bands" and st["bands"]["gid"] == g.gid
    assert {p["id"] for p in st["bands"]["packs"]} == {u.uid for u in g.members}


def test_the_roster_lists_each_band_and_the_sheet_reads_the_picked_member():
    sheet, guild, g = _sheet()
    m = sheet.state()["members"]
    assert [b["gid"] for b in m["roster"]] == [gr.gid for gr in guild.groups]
    u = guild.groups[1].members[1]
    st = sheet.pick_member(u.uid)["members"]["sheet"]
    assert st["name"] == u.name and st["band"] == guild.groups[1].display_name
    assert [a["k"] for a in st["attrs"]] == ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
    assert {s["k"] for s in st["stats"]} == {"AC", "MD", "SPD", "INIT"} and "= " in st["stats"][0]["tip"]
    assert [t["label"] for t in st["tracks"]][:3] == ["Combat career", "Base labor & work", "Racial maturity"]
    assert {r["key"] for r in st["roles"]} == {"guild_leader", "group_leader", "share_food", "distribute"}
    with pytest.raises(ValueError):
        sheet.pick_member("nobody")


def test_a_member_is_hungry_from_the_first_hunger_level():
    sheet, guild, g = _sheet()
    u = g.members[1]
    u.unfed_days = 1
    assert u.hunger_level == 1 and _needs_attention(u)
    rows = {r["uid"]: r for b in sheet.state()["members"]["roster"] for r in b["rows"]}
    assert "hungry" in {b["text"] for b in rows[u.uid]["badges"]}
    st = sheet.set_filter("alerts")
    shown = {r["uid"] for b in st["members"]["roster"] for r in b["rows"]}
    assert u.uid in shown and g.members[2].uid not in shown
    assert st["alerts"] >= 1


def test_a_band_folds_and_the_filters_keep_to_their_bands():
    sheet, guild, g = _sheet()
    st = sheet.fold(g.gid)
    band = next(b for b in st["members"]["roster"] if b["gid"] == g.gid)
    assert band["folded"]
    g.order = orders.rest(8)
    st = sheet.set_filter("idle")
    assert [b["gid"] for b in st["members"]["roster"]] == [guild.groups[1].gid]
    with pytest.raises(ValueError):
        sheet.set_filter("nonsense")


def test_a_role_changes_the_band_and_one_the_sheet_greys_out_is_refused():
    sheet, guild, g = _sheet()
    u = g.members[2]
    sheet.pick_member(u.uid)
    sheet.role("group_leader")
    assert g.leader is u
    shared = u.share_food
    st = sheet.role("share_food")
    assert u.share_food is not shared
    g.pending = orders.Order("ambush", pack=(Unit("Fighter"),))
    sheet.pick_member(g.members[0].uid)
    with pytest.raises(ValueError):
        sheet.role("group_leader")
    assert st["members"]["sheet"]["uid"] == u.uid


def test_the_talent_tree_is_an_away_card_that_comes_back_to_the_sheet():
    sheet, guild, g = _sheet()
    game = sheet.map.game
    assert sheet.talents() == {"screen": "away"}
    assert isinstance(game.session, AwaySession) and "talent tree" in game.session.state()["line"]
    back = game.session.resume()
    assert back["screen"] == "guild" and game.session is sheet


def test_an_item_moves_between_two_members_of_the_band_and_onto_a_hand():
    sheet, guild, g = _sheet("manage_group")
    a, b = g.members[0], g.members[1]
    a.give_to_pack("Rope", 1)
    st = sheet.state()
    loc = _row(st, a, "Rope")["loc"]
    st = sheet.move([{"from": a.uid, "loc": loc}], b.uid)
    assert _row(st, a, "Rope") is None and _row(st, b, "Rope")["qty"] >= 1
    b.give_to_pack("Dagger", 1)
    old = b.equipped_weapon
    st = sheet.state()
    st = sheet.move([{"from": b.uid, "loc": _row(st, b, "Dagger")["loc"]}], b.uid, "hand")
    assert b.equipped_weapon == "Dagger" and (old is None or b.count_of(old) >= 1)
    with pytest.raises(ValueError):
        sheet.move([{"from": a.uid, "loc": 99}], b.uid)


def test_a_member_of_another_band_is_not_on_the_table():
    sheet, guild, g = _sheet("manage_group")
    other = guild.groups[1].members[0]
    st = sheet.state()
    with pytest.raises(ValueError):
        sheet.move([{"from": g.members[0].uid, "loc": 0}], other.uid)
    assert other.uid not in {p["id"] for p in st["bands"]["packs"]}
    st = sheet.pick_band(guild.groups[1].gid)
    assert other.uid in {p["id"] for p in st["bands"]["packs"]}


def test_the_item_menu_offers_the_band_and_runs_the_pick():
    sheet, guild, g = _sheet("manage_group")
    a, c = g.members[0], g.members[2]
    for u in (a, c):
        u.remove_named("Rope", u.count_of("Rope"))
    a.give_to_pack("Rope", 3)
    loc = _row(sheet.state(), a, "Rope")["loc"]
    menu = sheet.menu({"from": a.uid, "loc": loc})
    to = {r["label"]: r for r in menu["rows"] if r["kind"] == "member"}
    assert f"to {c.name}" in to and f"to {a.name}" not in to and menu["held"] >= 3
    sheet.menu_run({"from": a.uid, "loc": loc}, to[f"to {c.name}"]["row"])
    assert c.count_of("Rope") == 3 and a.count_of("Rope") == 0
    with pytest.raises(ValueError):
        sheet.menu_run({"from": c.uid, "loc": 0}, 99)


def test_a_stack_splits_and_locks_by_name():
    sheet, guild, g = _sheet("manage_group")
    a = g.members[0]
    st = sheet.state()
    loc = _row(st, a, "Potato")["loc"]
    st = sheet.split({"from": a.uid, "loc": loc}, 1)
    assert sorted(r["qty"] for r in _col(st, a)["pack"] if r["name"] == "Potato") == [1, 3]
    with pytest.raises(ValueError):
        sheet.split({"from": a.uid, "loc": loc}, 9)
    st = sheet.lock(a.uid, "Potato")
    assert all(r["locked"] for r in _col(st, a)["pack"] if r["name"] == "Potato")
    assert st["notice"] is None or "split" not in st["notice"]


def test_a_band_with_a_fight_due_is_read_only():
    sheet, guild, g = _sheet("manage_group")
    a, b = g.members[0], g.members[1]
    g.pending = orders.Order("ambush", pack=(Unit("Fighter"),))
    st = sheet.state()["bands"]
    assert st["locked"] and st["lock_tip"]
    for verb in (lambda: sheet.move([{"from": a.uid, "loc": 0}], b.uid),
                 lambda: sheet.menu({"from": a.uid, "loc": 0}),
                 lambda: sheet.split({"from": a.uid, "loc": 0}, 1),
                 lambda: sheet.button("distribute")):
        with pytest.raises(ValueError):
            verb()


def test_the_wagon_takes_cargo_up_to_its_room_and_an_animal_hitches_by_its_portrait():
    sheet, guild, g = _sheet("manage_group")
    a = g.members[0]
    beast = Animal("Donkey")
    beast.give_to_tack(HARNESS)
    g.herd.append(beast)
    cart = Wagon("Cart")
    g.add_wagon(cart)
    sheet._set_band(g.gid)
    st = sheet.move([{"from": beast.uid, "loc": "hitch"}], cart.uid, "hitch")
    assert g.pulling(beast) is cart and st["bands"]["wagons"][0]["drawn"][0]["uid"] == beast.uid
    a.give_to_pack("Rope", 1)
    st = sheet.state()
    st = sheet.move([{"from": a.uid, "loc": _row(st, a, "Rope")["loc"]}], cart.uid)
    assert any(r["name"] == "Rope" for r in st["bands"]["wagons"][0]["pack"])
    a.give_to_pack("Lumber", 400)
    st = sheet.state()
    st = sheet.move([{"from": a.uid, "loc": _row(st, a, "Lumber")["loc"]}], cart.uid)
    assert a.count_of("Lumber") == 400 and "fit" in st["notice"]


def test_a_band_is_renamed_and_a_captive_released():
    sheet, guild, g = _sheet("manage_group")
    st = sheet.rename("  The Quiet Ones ")
    assert g.name == "The Quiet Ones" and st["bands"]["name"] == "The Quiet Ones"
    sheet.rename("")
    assert g.name is None
    prisoner = Unit("Fighter")
    g.captives.append(Captive(prisoner, guild.clock.day))
    st = sheet.state()
    assert st["bands"]["captives"][0]["uid"] == prisoner.uid
    st = sheet.button(f"release:{prisoner.uid}")
    assert not g.captives and st["bands"]["captives"] == []
    with pytest.raises(ValueError):
        sheet.button("release:nobody")


def test_the_charter_reads_the_bands_the_slots_and_the_strongbox_inside():
    sheet, guild, g = _sheet()
    guild.bank.capacity = 30
    guild.bank.put("Rope", 2)
    st = sheet.pick_tab("guild")["guild"]
    assert [r["gid"] for r in st["groups"]] == [gr.gid for gr in guild.groups]
    assert st["slots"] == [2, guild.group_slots]
    box = next(h for h in st["holdings"] if h["name"] == "Strongbox")
    assert box["inside"] == [{"name": "Rope", "qty": 2, "glyph": box["inside"][0]["glyph"]}]
    assert {h["name"] for h in st["holdings"]} == {"City house", "The Claim", "Strongbox"}


def test_the_reputations_list_the_objectives_and_each_known_faction():
    sheet, guild, g = _sheet()
    st = sheet.pick_tab("reputations")["reputations"]
    assert st["objectives"]["total"] == len(st["objectives"]["rows"]) > 0
    assert all({"name", "rep", "deeds", "unlocks"} <= f.keys() for f in st["factions"])
    with pytest.raises(ValueError):
        sheet.pick_tab("nowhere")


def test_leaving_the_sheet_lands_on_the_map_and_saves_the_rename(saves):
    guild = _guild()
    game = Game(MapSession(guild, "w1"))
    g = guild.groups[0]
    game.session.act(g.gid, "manage_group")
    sheet = game.session
    sheet.rename("Lantern Crew")
    st = sheet.map.back()
    assert st["screen"] == "map" and game.session is sheet.map
    assert persist.load_game("w1").groups[0].name == "Lantern Crew"
