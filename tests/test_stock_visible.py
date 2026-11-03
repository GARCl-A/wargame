"""What a stack hides is shown where the decision is made: a food's days left, a quiver's charges, the
shelf life in the shop, the rations a trip takes and the arrows the sheet names."""

from gartok import data, items
from gartok.animals import Animal
from gartok.combatant import Combatant
from gartok.group import Group
from gartok.guild import Guild
from gartok.guild_sheet import GuildSheet
from gartok.sheet import unit_to_ch
from gartok.web.map_session import MapSession
from gartok.web.server import Game
from tests.helpers import standard_unit


def _band(node="lumber_yard", size=2):
    units = [standard_unit() for _ in range(size)]
    return Guild(None, groups=[Group(units, node=node, leader=units[0])], name="Ink Hands")


def test_a_stack_note_gives_a_foods_days_left_and_a_quivers_charges():
    u = standard_unit()
    for days in (0, 6, 7):
        u.give_to_pack("Potato", 1, days_old=days)
    u.give_to_pack("Rotten Food", 1)
    u.give_to_pack(data.AMMO_ITEM, 1, charges=12)
    notes = [(e.name, e.days_old, items.stack_note(e)) for e in u._base_inventory]
    assert notes == [("Potato", 0, "7 days left"), ("Potato", 6, "1 day left"), ("Potato", 7, "last day"),
                     ("Rotten Food", 0, ""), ("Quiver", 0, "12/20")]
    assert items.stack_note(items.create_instance("Potato", days_old=8)) == "rotten"


def test_the_shelf_names_how_long_a_food_keeps():
    assert items.shelf_life("Potato") == "keeps 7 days"
    assert items.shelf_life("Fruit") == "keeps 1 day"
    assert items.shelf_life("Dagger") == ""


def test_the_pack_rows_carry_the_note_in_the_guild_and_the_shop():
    guild = _band("tavern")
    game = Game(MapSession(guild))
    g = guild.groups[0]
    a = g.members[0]
    a.give_to_pack("Potato", 2, days_old=6)
    a.give_to_pack(data.AMMO_ITEM, 1, charges=3)
    game.session.act(g.gid, "recruit")
    st = game.session.state()["shop"]
    row = next(r for p in st["packs"] if p["id"] == a.uid for r in p["pack"] if r["name"] == "Potato")
    assert row["note"] == "1 day left"
    foods = [r for c in st["shelf"] for r in c["rows"] if items.is_food(r["name"])]
    assert foods and all(r["use"].endswith(items.shelf_life(r["name"])) for r in foods)


def test_a_trip_previews_the_rations_it_takes_and_warns_when_the_band_is_short():
    guild = _band("lumber_yard", size=2)
    g = guild.groups[0]
    g.herd.append(Animal("Donkey"))
    assert g.meals_a_day == 3 and g.rations_for(4) == 12
    session = MapSession(guild)
    f = session.preview(g.gid, "market")["food"]
    assert f["need"] == g.rations_for(f["days"]) and f["have"] == 0 and f["short"] == bool(f["need"])
    for u in g.members:
        u.give_to_pack("Potato", 20)
    f = session.preview(g.gid, "market")["food"]
    assert f["have"] == 40 and not f["short"]


def test_the_quivers_add_up_and_spending_drains_them_in_order_keeping_the_empty_ones():
    u = standard_unit()
    u.set_kit("Shortbow", None)
    u.give_to_pack(data.AMMO_ITEM, 1, charges=0)
    u.give_to_pack(data.AMMO_ITEM, 2, charges=20)
    assert u.quiver_charges == 40 and Combatant(u).ammo == 40
    u.quiver_charges = 15
    assert [e.charges for e in u._base_inventory] == [0, 0, 15]
    assert u.count_of(data.AMMO_ITEM) == 3
    u.quiver_charges = 0
    assert [e.charges for e in u._base_inventory] == [0, 0, 0] and u.count_of(data.AMMO_ITEM) == 3


def test_a_refill_tops_up_the_quivers_carried():
    u = standard_unit()
    u.give_to_pack(data.AMMO_ITEM, 1, charges=0)
    u.give_to_pack(data.AMMO_ITEM, 1, charges=5)
    u.quiver_charges = 30
    assert sorted(e.charges for e in u._base_inventory) == [10, 20] and u.count_of(data.AMMO_ITEM) == 2


def test_the_sheet_names_the_arrows_left_across_the_quivers():
    u = standard_unit()
    u.set_kit("Shortbow", None)
    u.give_to_pack(data.AMMO_ITEM, 1, charges=0)
    u.give_to_pack(data.AMMO_ITEM, 1, charges=19)
    c = Combatant(u)
    chips = {k: v for k, v, _ in GuildSheet._weapon_data(u, c, unit_to_ch(c))["chips"]}
    assert chips["AMMO"] == "19"


def test_the_fletcher_refills_an_emptied_quiver_instead_of_adding_one():
    from gartok import campaign, economy, orders
    archer = standard_unit()
    archer.equipped_weapon = "Shortbow"
    archer.give_to_pack(data.AMMO_ITEM, 1, charges=0)
    crafter = standard_unit()
    crafter.work_hours = economy.LUMBER_XP_HOURS * 12
    crafter._derive_combat()
    for t in ("nimble_fingers", "woodcarver", "fletcher"):
        assert crafter.choose_talent("work", t)
    crafter.give_to_pack("Lumber")
    guild = Guild(None, groups=[Group([archer, crafter], node="lumber_yard", leader=archer)], name="Ink Hands")
    guild.groups[0].order = orders.rest(8)
    campaign.advance(guild)
    assert archer.count_of(data.AMMO_ITEM) == 1 and archer.quiver_charges == data.QUIVER_AMMO
