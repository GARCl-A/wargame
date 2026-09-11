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
