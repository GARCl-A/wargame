"""The Mine: a work node past the Old Road with its own shelf (stone, ore, coal)."""

from gartok import campaign, economy, orders, progression, world
from gartok.clock import Clock
from gartok.guild import Guild
from gartok.map_screen import MapScreen
from gartok.ui.tokens import fonts as ui_fonts
from gartok.unit import Unit
from tests.helpers import packed


def _worker():
    u = Unit("player")
    u._base_inventory = []
    u.money = 0
    u._derive_combat()
    return u


def test_the_mine_sits_six_hours_past_the_old_road_and_two_from_the_claim():
    n = world.node("mine")
    assert n.kind == "town" and n.has("work") and n.has("shop") and not n.unsafe
    assert dict(world.neighbors("mine")) == {"road": 6, "wilds_territory": 2}


def test_the_claim_is_still_eight_hours_from_the_road_by_either_way():
    assert world.route("road", "wilds_territory")[1] == 8


def test_the_mine_pays_a_dollar_more_per_block_than_the_yard():
    assert economy.work_pay("mine", 4) == economy.lumber_pay(4) + economy.MINE_WAGE_PREMIUM
    assert economy.work_pay("mine", 3) == 0
    assert economy.work_pay("mine", 16) == 8


def test_an_own_pick_pays_at_the_axes_ratio():
    assert economy.work_pay("mine", 16, level=1) == 8 * economy.LUMBER_AXE_RATIO[0] // economy.LUMBER_AXE_RATIO[1]


def test_each_node_counts_only_its_own_tool():
    u = _worker()
    u._base_inventory = packed(["Pick"])
    assert economy.work_level(u, "mine") == 1 and economy.work_level(u, "lumber_yard") == 0
    u._base_inventory = packed(["Axe"])
    assert economy.work_level(u, "lumber_yard") == 1 and economy.work_level(u, "mine") == 0
    u._base_inventory = []
    u.equipped_weapon = "Pick"
    assert economy.work_level(u, "mine") == 1


def test_a_work_order_at_the_mine_pays_the_mine_wage():
    a = _worker()
    guild = Guild([a], clock=Clock(6 * 3600))
    group = guild.groups[0]
    group.node = "mine"
    group.order = orders.work(guild, group, 8)
    result = campaign.advance(guild)
    assert a.money == economy.work_pay("mine", 8) == 4
    assert any("The Mine" in e for e in result.events)


def test_a_work_shift_names_the_node_it_was_worked_at():
    a = _worker()
    guild = Guild([a], clock=Clock(6 * 3600))
    events, _ = guild.work_shift([a], 8, "mine")
    assert a.money == 4 and a.work_hours == 8
    assert any("The Mine" in e for e in events)


def test_stone_ore_and_coal_are_sold_only_at_the_mine():
    assert economy.MINE_SUPPLIES == ("Stone Brick", "Iron Ore", "1kg Coal")
    shelf = [n for _, _, names in economy.market_categories("mine") for n in names]
    assert shelf == list(economy.MINE_SUPPLIES)
    market = [n for _, _, names in economy.market_categories("market") for n in names]
    assert not set(economy.MINE_SUPPLIES) & set(market)
    assert all(economy.freely_buyable(n) for n in economy.MINE_SUPPLIES)


def test_a_pick_is_sold_at_the_market():
    assert "Pick" in economy.MARKET_STOCK


def test_the_mine_has_a_till_of_its_own():
    guild = Guild([_worker()])
    guild.shop("mine").move_cash(-50)
    assert guild.shop("mine").cash != guild.shop("market").cash


def test_the_mine_screen_shows_the_foreman_pick_and_a_shop_button():
    g = Guild([_worker()], node="mine")
    ms = MapScreen(ui_fonts(), g, lambda: None, lambda: None, lambda: None, lambda grp: None)
    blocks = ms._inspector_content(g.groups[0], world.node("mine"))
    texts = [b["text"] for b in blocks if b["type"] == "text"]
    assert any("foreman's pick" in t for t in texts)
    assert [b["key"] for b in blocks if b["type"] == "button"] == ["market"]
    assert any(b["type"] == "button_row" for b in blocks)


def test_work_xp_lists_the_mine_beside_the_yard():
    jobs = progression.eligible_work_activities(0)
    assert any("Mine" in j for j in jobs) and any("Lumber Yard" in j for j in jobs)
    u = Unit("player")
    assert any("requires owning a Pick" in j for j in progression.eligible_work_activities(1, u))
    u.equipped_weapon = "Pick"
    assert any("Mine (with your Pick)" in j for j in progression.eligible_work_activities(1, u))
