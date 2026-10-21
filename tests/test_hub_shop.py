"""The hub frame (keeper header, tab row, back) and its shop tab: the cart, BUY, drop to sell."""

import os

import pygame

from gartok import economy, items, world
from gartok.guild import Guild
from gartok.hub_screen import TabbedHubScreen
from gartok.market_screen import MarketScreen
from gartok.ui.tokens import fonts as ui_fonts
from gartok.unit import Unit

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def _shoppers(*tongues, alignment="Lawful and Neutral"):
    units = []
    for t in tongues:
        u = Unit("player")
        u.languages = list(t)
        u.alignment = alignment
        u._base_inventory = []
        u.give_to_pack(items.COIN_ITEM, 200)
        units.append(u)
    return units


def _hub(node_id, units, first="shop"):
    pygame.init()
    g = Guild(units)
    hub = TabbedHubScreen.for_node(ui_fonts(), g, g.groups[0], world.node(node_id), lambda *a: None, first=first)
    return hub, g


def _draw(hub):
    surf = pygame.display.set_mode((1920, 1080))
    hub.mouse = (0, 0)
    hub.draw(surf)
    return surf


def test_every_keeper_has_a_line_of_their_own():
    keepers = {v.name: v for n in world.NODES for v in n.vendors.values()}
    assert all(v.line for v in keepers.values()), [n for n, v in keepers.items() if not v.line]
    assert len({v.line for v in keepers.values()}) == len(keepers)


def test_every_shop_keeper_haggles_in_a_tongue_with_a_bent():
    for n in world.NODES:
        if n.has("shop"):
            assert n.language and n.alignment, n.id


def test_the_header_shows_the_keeper_of_the_place():
    hub, _ = _hub("farm", _shoppers(["Ankarin"]))
    k = hub.keeper()
    assert (k["place"], k["name"], k["caption"], k["bent"]) == ("The Farm", "Edric Ashvale", "Human farmer",
                                                                "Lawful Good")
    assert k["line"]


def test_a_shop_alone_still_opens_in_a_hub():
    hub, _ = _hub("market", _shoppers(["Ankarin"]))
    assert isinstance(hub, TabbedHubScreen) and [k for k, _l, _s in hub.tabs] == ["shop"]


def test_the_shop_tab_gives_the_header_its_deal_purse_and_till():
    hub, _ = _hub("smith", _shoppers(["Ankarin"], ["Ankarin", "Dwarvish"]))
    labels = [c["label"] for c in hub.active_screen().hub_cards()]
    assert labels == ["your deal", "party purse", "shop can pay"]


def test_the_deal_names_who_speaks_and_matches_the_prices():
    units = _shoppers(["Ankarin"], ["Ankarin", "Dwarvish"])
    s = MarketScreen(None, Guild(units), units, world.node("smith"), lambda: None)
    deal = s._deal_card()
    assert deal["why"][0] == f"{units[1].name} speaks for the group"
    pct = round(economy.deal_value(s.deal, None, "buy") * 100)
    assert deal["headline"] == (f"{pct}% off" if pct > 0 else f"{-pct}% markup" if pct < 0 else "list price")


def test_nobody_speaking_the_tongue_means_no_haggling():
    units = _shoppers(["Ankarin"])
    deal = MarketScreen(None, Guild(units), units, world.node("smith"), lambda: None)._deal_card()
    assert deal["headline"] == "no haggling" and "no one speaks Dwarvish" in deal["why"]


def test_the_lumber_yard_and_the_mine_haggle():
    orc = _shoppers(["Orcish"])
    assert economy.haggle_voice(orc, "Orcish", world.node("lumber_yard").alignment)[0] is orc[0]


def test_the_voice_is_the_leader_when_they_speak_the_tongue():
    a, b = _shoppers(["Dwarvish"], ["Dwarvish"])
    assert economy.haggle_voice([a, b], "Dwarvish", "Lawful and Neutral", leader=b)[0] is b


def test_tabs_click_and_tab_key_switch_and_back_leaves():
    left = []
    units = _shoppers(["Ankarin"])
    g = Guild(units)
    hub = TabbedHubScreen.for_node(ui_fonts(), g, g.groups[0], world.node("smith"), lambda *a: left.append(1),
                                   first="shop")
    _draw(hub)
    forge = next(r for r, k in hub._tab_hits if k == "forge")
    hub.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=forge.center))
    assert hub.tab == "forge"
    hub.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB, mod=0))
    assert hub.tab == "shop"
    _draw(hub)
    hub.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=hub._back.center))
    assert left == [1]


def test_esc_on_a_framed_tab_goes_back():
    left = []
    units = _shoppers(["Ankarin"])
    g = Guild(units)
    hub = TabbedHubScreen.for_node(ui_fonts(), g, g.groups[0], world.node("market"), lambda *a: left.append(1))
    assert hub.handle_escape() and left == [1]


def _shop(node_id="tavern"):
    units = _shoppers(["Ankarin"], ["Ankarin"])
    hub, _g = _hub(node_id, units)
    _draw(hub)
    return hub, hub.active_screen(), units


def _click(hub, pos, ms):
    """A click on the shop body at `pos` (body coordinates), sent through the hub."""
    p = (pos[0] + hub._body.x, pos[1] + hub._body.y)
    hub.mouse = p
    hub.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=p))
    hub.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=p))
    _draw(hub)


def test_a_click_on_a_shelf_row_fills_the_cart_and_a_second_takes_it_out():
    hub, ms, _units = _shop()
    (r1, beer), (r2, jerky) = ms.stock_rows[:2]
    _click(hub, r1.center, ms)
    _click(hub, r2.center, ms)
    assert [n for _k, n in ms.selected] == [beer, jerky]
    assert ms._shelf_foot()["button"].startswith("buy for")
    _click(hub, r1.center, ms)
    assert [n for _k, n in ms.selected] == [jerky]


def test_buy_shares_the_cart_out_by_room():
    _hub, ms, units = _shop()
    beer = ms.stock_rows[0][1]
    ms.selected = [("stock", beer)]
    ms.qty[beer] = 2
    roomiest = max(units, key=lambda u: u.carry_max - u.load)
    purse = ms.purse
    ms._buy_cart()
    assert sum(u.count_of(beer) for u in units) == 2 and roomiest.count_of(beer) >= 1
    assert ms.purse == purse - 2 * economy.buy_price(beer, ms.deal)
    assert ms.selected == []


def test_dropping_pack_items_on_the_shelf_sells_them():
    hub, ms, units = _shop()
    units[0].give_to_pack("Potato", 3)
    loc = next(i for i, (n, _q) in enumerate(units[0]._base_inventory) if n == "Potato")
    ms.selected, ms._sel_qty = [(units[0], loc)], {(units[0], loc): 3}
    _draw(hub)
    assert ms._shelf_foot()["button"].startswith("sell for")
    purse = ms.purse
    ms._drop(ms._shelf_rect.center, True, (units[0], loc))
    assert units[0].count_of("Potato") == 0 and ms.purse > purse


def test_with_nothing_picked_the_footer_is_the_auto_sell():
    _hub, ms, units = _shop()
    ms.guild.autosell = {"Potato"}
    units[1].give_to_pack("Potato", 2)
    foot = ms._shelf_foot()
    assert foot["left"].startswith("Auto-sell · Potato") and foot["enabled"]
    ms.guild.autosell = set()
    assert not ms._shelf_foot()["enabled"]


def test_the_tavern_tabs_sit_in_the_frame_and_give_the_recruit_facts_as_cards():
    hub, _ = _hub("tavern", _shoppers(["Halfling"]), first="recruits")
    _draw(hub)
    assert hub._back is not None                              # the hub's back, not the tavern's own
    labels = [c["label"] for c in hub.active_screen().hub_cards()]
    assert labels == ["guild size", "crowd penalty", "new faces in", "party purse"]
    hub.tab = "rooms"
    assert [c["label"] for c in hub.active_screen().hub_cards()] == ["party purse"]


def test_an_unframed_tab_keeps_its_own_footer_under_the_tab_row():
    hub, _ = _hub("smith", _shoppers(["Ankarin"]), first="forge")
    _draw(hub)
    assert hub._back is None and hub._body.y == hub._tab_hits[0][0].bottom + 1


def test_the_weapon_note_is_short():
    units = _shoppers(["Ankarin"])
    units[0].equipped_weapon = "Axe"
    units[0]._derive_combat()
    note = MarketScreen(None, Guild(units), units, world.node("smith"), lambda: None)._hand_note(units[0])
    assert "hit" not in note and "dmg" not in note and "1d8" in note
