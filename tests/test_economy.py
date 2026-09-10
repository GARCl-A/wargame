"""Market haggling: language, Charisma and alignment on the price."""

import random

from tests.helpers import data, economy, Unit, _unit


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
    from gartok.market_screen import MarketScreen
    from gartok import world
    random.seed(1)
    loud = Unit("player"); loud.languages = ["Ankarin"]; loud.charisma = 17
    loud.alignment = "Lawful and Neutral"; loud._derive_combat()
    mute = Unit("player"); mute.languages = ["Orcish"]; mute.charisma = 20
    ms = MarketScreen.__new__(MarketScreen)
    ms.shoppers = [loud, mute]
    ms.node = world.node("market")
    ms.deal = economy.market_deal(ms.shoppers, ms.node.language, ms.node.alignment)
    assert ms.deal > 0                                      # the Orc's 20 CHA is wasted
