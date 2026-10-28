"""The keepers of the places and the haggling at their counters: who speaks for the band, in which
tongue, and what the deal is worth."""

from gartok import economy, items, world
from gartok.guild import Guild
from gartok.trade import Counter
from gartok.unit import Unit


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


def test_every_keeper_has_a_line_of_their_own():
    keepers = {v.name: v for n in world.NODES for v in n.vendors.values()}
    assert all(v.line for v in keepers.values()), [n for n, v in keepers.items() if not v.line]
    assert len({v.line for v in keepers.values()}) == len(keepers)


def test_every_shop_keeper_haggles_in_a_tongue_with_a_bent():
    for n in world.NODES:
        if n.has("shop"):
            assert n.language and n.alignment, n.id


def test_the_deal_names_who_speaks_and_matches_the_prices():
    units = _shoppers(["Ankarin"], ["Ankarin", "Dwarvish"])
    s = Counter(Guild(units), units, world.node("smith"))
    deal = s._deal_card()
    assert deal["why"][0] == f"{units[1].name} speaks for the group"
    pct = round(economy.deal_value(s.deal, None, "buy") * 100)
    assert deal["headline"] == (f"{pct}% off" if pct > 0 else f"{-pct}% markup" if pct < 0 else "list price")


def test_nobody_speaking_the_tongue_means_no_haggling():
    units = _shoppers(["Ankarin"])
    deal = Counter(Guild(units), units, world.node("smith"))._deal_card()
    assert deal["headline"] == "no haggling" and "no one speaks Dwarvish" in deal["why"]


def test_the_lumber_yard_and_the_mine_haggle():
    orc = _shoppers(["Orcish"])
    assert economy.haggle_voice(orc, "Orcish", world.node("lumber_yard").alignment)[0] is orc[0]


def test_the_voice_is_the_leader_when_they_speak_the_tongue():
    a, b = _shoppers(["Dwarvish"], ["Dwarvish"])
    assert economy.haggle_voice([a, b], "Dwarvish", "Lawful and Neutral", leader=b)[0] is b
