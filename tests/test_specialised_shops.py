"""The Smithy, the Tannery and the Apothecary are nodes of their own, each with its shop beside its trade."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from gartok import economy, missions, node_functions, world
from gartok.apothecary_hub_screen import ApothecaryHubScreen
from gartok.forge_hub_screen import ForgeHubScreen
from gartok.guild import Guild
from gartok.hub_screen import TabbedHubScreen
from gartok.tanner_hub_screen import TannerHubScreen
from gartok.ui.tokens import fonts as ui_fonts
from gartok.unit import Unit

HUBS = {"smith": ("forge", ForgeHubScreen), "tanner": ("tanner", TannerHubScreen),
        "apothecary": ("apothecary", ApothecaryHubScreen)}


def _hub(node_id):
    pygame.init()
    guild = Guild([Unit("player")], node=node_id)
    node = world.node(node_id)
    cls = HUBS[node_id][1]
    args = (ui_fonts(), guild, guild.groups[0])
    return guild, (cls(*args, lambda: None, node=node) if node_id == "apothecary"
                   else cls(*args, node, lambda: None))


def test_the_city_no_longer_holds_the_trades():
    assert not {"tanner", "forge", "apothecary", "shop"} & set(world.node("city").functions)


@pytest.mark.parametrize("node_id", HUBS)
def test_each_trade_has_its_own_node_with_a_shop_a_shelf_and_a_walk_from_the_city(node_id):
    node = world.node(node_id)
    assert node.has(HUBS[node_id][0]) and node.has("shop")
    assert [f.id for f in node_functions.offered(node)] == [HUBS[node_id][0]]
    assert economy.targets_of(node_id)
    path, distance = world.route("city", node_id)
    assert path[0] == "city" and path[-1] == node_id and distance == 0.5


def test_the_trades_are_a_short_walk_from_each_other_and_speak_their_keepers_tongue():
    assert world.route("smith", "tanner") == (["smith", "tanner"], 0.3)
    assert world.route("apothecary", "smith")[1] == 0.3
    assert world.node("smith").language == "Dwarvish" and world.node("tanner").language == "Orcish"


def test_every_shops_tongue_is_its_keepers_race_tongue():
    from gartok import data
    native = {name: data.race_by_name(name)["language"] for name in data.RACE_NAMES}
    expected = {"smith": "Dwarf", "tanner": "Gnoll", "library": "Kobold", "apothecary": "Gnome", "tavern": "Halfling"}
    for node_id, race in expected.items():
        assert economy.vendor_tongues(world.node(node_id).language)[0] == native[race], node_id
    assert economy.vendor_tongues(world.node("farm").language) == ("Ankarin", "Sylvan")


def test_a_vendor_with_two_tongues_haggles_with_whoever_speaks_either():
    only_sylvan, only_dwarvish = Unit("player"), Unit("player")
    only_sylvan.languages, only_dwarvish.languages = ["Sylvan"], ["Dwarvish"]
    farm = world.node("farm")
    assert economy.speaks_with(farm.language, only_sylvan)
    assert not economy.speaks_with(farm.language, only_dwarvish)
    assert economy.speaks_with(world.node("smith").language, only_dwarvish)


def test_the_shelves_are_split_between_the_shops():
    assert "Axe" in economy.targets_of("smith") and "Axe" not in economy.targets_of("market")
    assert "Cloak" in economy.targets_of("tanner")
    assert "Minor Healing Potion" in economy.targets_of("apothecary")
    assert "Potato" in economy.targets_of("farm") and "Jerky" in economy.targets_of("tavern")
    assert economy.shop_of("Axe") == "smith" and economy.shop_of("Stone Brick") is None


def test_a_shop_only_lists_the_tabs_it_has_something_on():
    tabs = lambda node_id: [key for _label, key, _names in economy.market_categories(node_id)]
    assert tabs("apothecary") == ["kit"]
    assert tabs("market") == ["kit"]


@pytest.mark.parametrize("node_id", HUBS)
def test_the_hub_opens_on_a_tab_and_switches_when_clicked(node_id):
    _guild, hub = _hub(node_id)
    assert isinstance(hub, TabbedHubScreen)
    surf = pygame.Surface((1280, 800))
    hub.mouse = (0, 0)
    hub.draw(surf)
    others = [key for key, _rect in hub.buttons]
    assert others and hub.tab not in others
    key, rect = hub.buttons[0]
    hub.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
    assert hub.tab == key
    hub.draw(surf)


@pytest.mark.parametrize("node_id", ["smith", "tanner"])
def test_the_shop_tab_buys_from_the_nodes_own_till(node_id):
    guild, hub = _hub(node_id)
    shop_screen = {k: s for k, _l, s in hub.tabs}["shop"]
    assert shop_screen.node.id == node_id
    assert shop_screen._shop() is guild.shop(node_id)
    assert shop_screen.header_reserve > 0


def test_the_tanners_job_is_offered_at_the_tannery_not_the_city():
    guild = Guild([Unit("player")])
    assert missions.TANNER_HIDES.id in {t.id for t in missions.offers_at(guild, "tanner")}
    assert missions.TANNER_HIDES.id not in {t.id for t in missions.offers_at(guild, "city")}
    assert missions.APOTHECARY_MUSHROOMS.id in {t.id for t in missions.offers_at(guild, "apothecary")}


def test_every_shop_node_is_refilled_each_day():
    guild = Guild([Unit("player")])
    for node_id in HUBS:
        guild.shop(node_id).stock[next(iter(economy.targets_of(node_id)))] = 0
    guild._daily_upkeep()
    for node_id in HUBS:
        assert guild.shop(node_id).cash > 0


def test_the_trades_group_stands_at_their_node_when_the_order_resolves():
    from gartok import campaign, orders
    guild = Guild([Unit("player")], node="city")
    group = guild.groups[0]
    group.order = orders.travel(group, "smith")
    for _ in range(200):
        if group.node == "smith":
            break
        campaign.advance(guild)
    assert group.node == "smith"


def test_shops_without_a_trade_beside_them_name_the_place():
    labels = {n.id: n.shop_label for n in world.NODES if n.shop_label}
    assert labels == {"lumber_yard": "BROWSE THE YARD", "mine": "BROWSE THE MINE", "market": "ENTER THE MARKET",
                      "tavern": "BUY FOOD AND DRINK", "farm": "BROWSE THE FARM"}
    assert all(n.has("shop") for n in world.NODES if n.shop_label)
