"""Market haggling: language, Charisma and alignment on the price."""

import random

from tests.helpers import Unit, _unit, data, economy


def test_alignment_distance_axes():
    assert data.alignment_distance("Lawful and Good", "Lawful and Good") == 0
    assert data.alignment_distance("Lawful and Good", "Chaotic and Evil") == 4
    assert data.alignment_distance("Lawful and Neutral", "Neutral and Neutral") == 1


def test_no_shared_language_means_no_deal():
    m = _unit(seed=1)
    m.languages = ["Orcish"]
    assert economy.market_deal([m], "Ankarin", "Lawful and Neutral") == 0.0
    assert economy.buy_price("Dagger", 0.0) == economy.PRICES["Dagger"]


def test_charisma_and_alignment_bend_the_price_but_resale_stays_a_loss():
    good = _unit(seed=1)
    good.languages = ["Ankarin"]
    good.charisma = 18
    good.alignment = "Lawful and Neutral"                        # same as the vendor
    good._derive_combat()
    deal = economy.market_deal([good], "Ankarin", "Lawful and Neutral")
    assert deal > 0
    assert economy.buy_price("Axe", deal) < economy.buy_price("Axe", 0.0)
    assert economy.sell_price("Axe", deal) > economy.sell_price("Axe", 0.0)
    assert economy.sell_price("Axe", deal) < economy.buy_price("Axe", deal)

    hostile = _unit(seed=1)
    hostile.languages = ["Ankarin"]
    hostile.charisma = 6
    hostile.alignment = "Chaotic and Evil"                     # opposed -> premium
    hostile._derive_combat()
    bad = economy.market_deal([hostile], "Ankarin", "Lawful and Neutral")
    assert bad < 0 and economy.buy_price("Axe", bad) > economy.buy_price("Axe", 0.0)


def test_market_deal_picks_the_best_speaker():
    from gartok import world
    from gartok.market_screen import MarketScreen
    random.seed(1)
    loud = Unit("player"); loud.languages = ["Ankarin"]; loud.charisma = 17
    loud.alignment = "Lawful and Neutral"; loud._derive_combat()
    mute = Unit("player"); mute.languages = ["Orcish"]; mute.charisma = 20
    ms = MarketScreen.__new__(MarketScreen)
    ms.shoppers = [loud, mute]
    ms.node = world.node("market")
    ms.deal = economy.market_deal(ms.shoppers, ms.node.language, ms.node.alignment)
    assert ms.deal > 0                                      # the Orc's 20 CHA is wasted


def test_the_group_leader_speaks_over_a_better_charisma_when_eligible():
    """A leader with lower Charisma than a group-mate still does the haggling,
    as long as they share the vendor's language -- see RULES.md "Leadership"."""
    random.seed(1)
    leader = _unit(seed=1); leader.languages = ["Ankarin"]; leader.charisma = 8
    leader.alignment = "Lawful and Neutral"; leader._derive_combat()
    silver_tongue = _unit(seed=2); silver_tongue.languages = ["Ankarin"]
    silver_tongue.charisma = 18; silver_tongue.alignment = "Lawful and Neutral"
    silver_tongue._derive_combat()

    without_leader = economy.market_deal([leader, silver_tongue], "Ankarin", "Lawful and Neutral")
    with_leader = economy.market_deal([leader, silver_tongue], "Ankarin", "Lawful and Neutral",
                                      leader=leader)
    assert with_leader < without_leader          # the weaker haggler now speaks for the group


def test_leader_who_cannot_speak_the_vendors_tongue_does_not_block_the_pitch():
    leader = _unit(seed=1); leader.languages = ["Orcish"]; leader.charisma = 8
    speaker = _unit(seed=2); speaker.languages = ["Ankarin"]; speaker.charisma = 18
    speaker.alignment = "Lawful and Neutral"; speaker._derive_combat()
    deal = economy.market_deal([leader, speaker], "Ankarin", "Lawful and Neutral", leader=leader)
    assert deal > 0                              # falls back to the eligible speaker


def test_scroll_pricing_scales_with_level():
    # Formula: 180 * (level + 1) + 105 * level
    # Level 0 (e.g. Magic Missile, Light Globe): 180 cp
    assert economy.scroll_price(0) == 180
    assert economy.buy_price("Scroll of Magic Missile", 0.0) == 180
    assert economy.sell_price("Scroll of Magic Missile", 0.0) == 90
    assert economy.buy_price("Scroll of Light Globe", 0.0) == 180

    # Level 1 (e.g. Sleep): 180 * 2 + 105 * 1 = 465 cp
    assert economy.scroll_price(1) == 465
    assert economy.buy_price("Scroll of Sleep", 0.0) == 465
    assert economy.sell_price("Scroll of Sleep", 0.0) == 232


def test_fruit_price_and_market_stock():
    # Fruit must be cheaper than Meat (5 cp) and more expensive than Potato (3 cp)
    assert economy.PRICES["Fruit"] == 4
    assert economy.PRICES["Potato"] < economy.PRICES["Fruit"] < economy.PRICES["Meat"]
    assert "Fruit" in economy.MARKET_STOCK
    assert economy.buy_price("Fruit", 0.0) == 4
    assert economy.sell_price("Fruit", 0.0) == 2


def test_dwarf_items_not_in_market_stock():
    # Dwarven weapons/armor/shield are crafted via the Dwarf racial talent and not sold in the market
    for dwarf_item in ("Dwarf Axe", "Large Dwarf Axe", "Dwarf Armor", "Dwarf Shield"):
        assert dwarf_item not in economy.MARKET_STOCK


def test_market_stock_has_no_duplicate_large_weapon_rows():
    # Large weapons are toggled when buying, not duplicated as separate stock rows
    large_weapons = [item for item in economy.MARKET_STOCK if item.startswith("Large ")]
    assert large_weapons == []




def test_a_used_quiver_sells_for_the_share_of_its_charges_left():
    from gartok import items
    full = economy.sell_price("Quiver")
    half = economy.sell_price(items.ChargedName("Quiver", items.get("Quiver").max_charges // 2))
    assert half == max(1, round(full / 2))
    assert economy.sell_price(items.ChargedName("Quiver", 0)) == 1
    assert economy.sell_price(items.ChargedName("Quiver", 99)) == full


def test_selling_a_used_quiver_at_the_market_pays_pro_rata():
    from gartok import items
    from gartok.guild import Guild
    from gartok.market_screen import MarketScreen
    u = Unit("player")
    u._base_inventory = []
    u.give_to_pack("Quiver")
    u.quiver_charges = 5
    s = MarketScreen.__new__(MarketScreen)
    s.guild, s.shoppers, s.deal = Guild([u]), [u], []
    s.purse = 0
    s.selected, s._sel_qty, s.notice = [(u, 0)], {}, None
    s.qty = {}
    s._settle_market = lambda: None
    s._sell()
    assert s.purse == economy.sell_price(items.ChargedName("Quiver", 5))
    assert 1 <= s.purse < economy.sell_price("Quiver")


def test_the_sell_total_multiplies_by_the_quantity_picked():
    from gartok.guild import Guild
    from gartok.market_screen import MarketScreen
    u = Unit("player")
    u._base_inventory = []
    u.give_to_pack("Rope", 3)
    s = MarketScreen.__new__(MarketScreen)
    s.guild, s.shoppers, s.deal = Guild([u]), [u], []
    s.selected, s._sel_qty = [(u, 0)], {}
    assert s._sell_total() == economy.sell_price("Rope") * 3
