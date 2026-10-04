from gartok import economy
from gartok.guild import Guild
from gartok.holdings import CityProperty, Stash
from tests.helpers import Unit


def test_stash_tracks_load_and_free_room():
    s = Stash(10, [("Rope", 2)])
    assert s.open and s.load > 0 and s.free == 10 - s.load
    assert s.fits(s.free) and not s.fits(s.free + 0.1)


def test_an_unrented_stash_is_closed_and_holds_nothing():
    s = Stash()
    assert not s.open and s.load == 0 and not s.fits(1)


def test_stash_put_merges_and_take_drops_an_emptied_row():
    s = Stash(30)
    s.put("Rope", 2)
    s.put("Rope")
    assert s.items == [("Rope", 3)]
    assert s.take(0, 2) == ("Rope", 2) and s.items == [("Rope", 1)]
    assert s.take(0, 5) == ("Rope", 1) and s.items == []


def test_house_capacity_is_the_economy_constant():
    assert CityProperty().stash.capacity == economy.CITY_PROPERTY_CAPACITY


def test_house_lifecycle_buy_squat_abandon():
    h = CityProperty()
    h.buy(10)
    assert h.owned and h.tax_due_day == 10 + economy.CITY_PROPERTY_TAX_PERIOD_DAYS
    h.stash.put("Rope")
    h.missed_payments = economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT
    assert h.repossession_due
    h.squat()
    assert h.owned and h.squatting and h.tax_due_day is None and not h.repossession_due
    h.abandon()
    assert not h.owned and not h.squatting and h.stash.items == []


def test_repossess_returns_the_owed_rent_and_empties_the_house():
    h = CityProperty()
    h.buy(0)
    h.stash.put("Rope")
    h.missed_payments = 2
    assert h.repossess() == 2 * economy.CITY_PROPERTY_TAX
    assert not h.owned and h.stash.items == [] and h.missed_payments == 0


def test_a_squatter_is_not_taxed():
    p = Unit("player")
    p.gold = 1000
    guild = Guild([p])
    guild.buy_city_property()
    guild.house.squat()
    guild.pass_time(economy.CITY_PROPERTY_TAX_PERIOD_DAYS * 24 * 2)
    assert p.gold == 1000 and guild.house.missed_payments == 0


def test_food_rots_in_the_bank_and_in_the_house():
    guild = Guild([Unit("player")], bank=Stash(30, [("Fruit", 2)]))
    guild.buy_city_property()
    guild.house.stash.put("Fruit", 3)
    guild.pass_time(24 * 3)
    for stash in (guild.bank, guild.house.stash):
        assert [n for n, _ in stash.items] == ["Rotten Food"]
