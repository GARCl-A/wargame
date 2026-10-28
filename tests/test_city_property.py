"""The City property: buying it from the Bankers, the recurring tax, the
repossession/squat choice, debt escalating to the guard, and a squat drawing
periodic guard raids. See [[gartok-property-two-paths]] and
`gartok/vault.py` / `gartok/campaign.py`'s "eviction" pause -- same shape as
`test_bank.py` (the counter) and `test_justice_integration.py` /
`test_road_ambush.py` (the pause/resolve seam)."""

import random

from gartok import campaign, forced, orders
from gartok.group import Group
from gartok.guild import Guild
from gartok.vault import BankVault, HouseVault
from tests.helpers import Unit, economy, packed


def _at_gate(gold=economy.CITY_PROPERTY_PRICE):
    """A single-member guild past the reputation gate, with `gold` to spend."""
    p = Unit("player")
    p.money = gold
    guild = Guild([p], reputation={"bankers": economy.CITY_PROPERTY_REP_GATE})
    return guild, p


# --------------------------------------------------------------------------- #
# buying                                                                       #
# --------------------------------------------------------------------------- #

def test_buying_debits_the_pooled_purse_and_starts_the_tax_clock():
    random.seed(1)
    guild, p = _at_gate(gold=economy.CITY_PROPERTY_PRICE + 20)
    s = HouseVault(guild, [p])

    s._run_service("buy")
    assert guild.house.owned
    assert s.purse == 20 and p.money == 20                                 # debited at once
    assert guild.house.tax_due_day == guild.clock.day + economy.CITY_PROPERTY_TAX_PERIOD_DAYS

    assert p.money == 20


def test_buying_is_refused_below_the_reputation_gate():
    random.seed(1)
    p = Unit("player")
    p.money = economy.CITY_PROPERTY_PRICE
    guild = Guild([p], reputation={"bankers": economy.CITY_PROPERTY_REP_GATE - 1})
    s = HouseVault(guild, [p])

    s._run_service("buy")
    assert not guild.house.owned and s.purse == economy.CITY_PROPERTY_PRICE


def test_buying_is_refused_when_the_party_is_short():
    random.seed(1)
    guild, p = _at_gate(gold=economy.CITY_PROPERTY_PRICE - 1)
    s = HouseVault(guild, [p])

    s._run_service("buy")
    assert not guild.house.owned and "$" in s.notice


def test_buying_is_refused_while_bankers_debt_is_outstanding():
    random.seed(1)
    guild, p = _at_gate(gold=economy.CITY_PROPERTY_PRICE + 20)
    guild.bankers_debt = 10
    s = HouseVault(guild, [p])

    s._run_service("buy")
    assert not guild.house.owned and s.purse == economy.CITY_PROPERTY_PRICE + 20


def test_deposit_is_capped_by_the_property_and_withdraw_by_the_members_load():
    random.seed(1)
    guild, p = _at_gate()
    guild.buy_city_property()
    p._base_inventory = packed(["Chainmail"])              # 10.0 kg
    s = HouseVault(guild, [p])

    s._deposit([(p, 0)])
    assert guild.house.stash.items == [("Chainmail", 1)] and p._base_inventory == []

    p.carry_max = 0.5
    s.selected = [("house", 0)]
    s._give_many(p, "pack")
    assert guild.house.stash.items == [("Chainmail", 1)] and "fit" in s.notice


# --------------------------------------------------------------------------- #
# the recurring tax + missed payments                                         #
# --------------------------------------------------------------------------- #

def test_the_tax_is_charged_automatically_when_it_falls_due():
    random.seed(1)
    p = Unit("player")
    p.money = 1000
    guild = Guild([p])
    guild.buy_city_property()
    due = guild.house.tax_due_day

    guild.pass_time((due - guild.clock.day) * 24)
    assert guild.clock.day >= due
    assert p.money == 1000 - economy.CITY_PROPERTY_TAX
    assert guild.house.missed_payments == 0
    assert guild.house.tax_due_day == due + economy.CITY_PROPERTY_TAX_PERIOD_DAYS


def test_a_missed_cycle_is_tallied_instead_of_going_into_debt():
    random.seed(1)
    p = Unit("player")
    p.money = 0
    guild = Guild([p])
    guild.buy_city_property()
    due = guild.house.tax_due_day

    guild.pass_time((due - guild.clock.day) * 24)
    assert p.money == 0 and guild.house.missed_payments == 1
    assert not guild.house.repossession_due


def test_enough_missed_cycles_trip_the_repossession_offer():
    random.seed(1)
    p = Unit("player")
    p.money = 0
    guild = Guild([p])
    guild.buy_city_property()

    for _ in range(economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT):
        due = guild.house.tax_due_day
        guild.pass_time((due - guild.clock.day) * 24)
    assert guild.house.missed_payments == economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT
    assert guild.house.repossession_due


# --------------------------------------------------------------------------- #
# the repossession choice: return (debt) or squat                             #
# --------------------------------------------------------------------------- #

def test_returning_the_property_banks_debt_and_blocks_bankers_services():
    random.seed(1)
    p = Unit("player")
    guild = Guild([p])
    guild.buy_city_property()
    guild.house.missed_payments = economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT

    guild.repossess_city_property()
    assert not guild.house.owned
    assert guild.bankers_debt == economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT * economy.CITY_PROPERTY_TAX
    assert guild.bankers_services_blocked
    assert guild.bankers_debt_since == guild.clock.day


def test_paying_off_the_debt_unblocks_bankers_services():
    random.seed(1)
    p = Unit("player")
    p.money = 1000
    guild = Guild([p])
    guild.bankers_debt = 120
    guild.bankers_debt_since = guild.clock.day
    s = HouseVault(guild, [p])

    s._run_service("pay_debt")
    assert guild.bankers_debt == 0 and not guild.bankers_services_blocked
    assert guild.bankers_debt_since is None
    assert s.purse == 1000 - 120
    assert p.money == 1000 - 120


def test_the_debt_and_the_tax_show_in_the_hub_header_and_the_debt_is_a_service():
    random.seed(1)
    p = Unit("player")
    p.money = 1000
    guild = Guild([p])
    guild.buy_city_property()
    guild.house.missed_payments = 1
    guild.bankers_debt = 120
    s = HouseVault(guild, [p])
    s.on_cook = s.on_garage = None

    cards = {c["label"]: c for c in s.hub_cards()}
    assert cards["owed to the bankers"]["tone"] == "bad"
    assert cards["next tax"]["value"] == f"day {guild.house.tax_due_day}"
    assert "1 missed" in cards["next tax"]["sub"]
    assert ("pay_debt", True) in [(key, enabled) for key, _l, _s, enabled in s._services()]

    guild.bankers_debt = 0
    guild.house.missed_payments = 0
    assert "owed to the bankers" not in {c["label"] for c in s.hub_cards()}
    assert "pay_debt" not in [key for key, *_ in s._services()]


def test_paying_off_the_debt_never_overpays():
    random.seed(1)
    p = Unit("player")
    p.money = 1000
    guild = Guild([p])
    guild.bankers_debt = 30
    s = HouseVault(guild, [p])

    s._run_service("pay_debt")
    assert guild.bankers_debt == 0 and s.purse == 1000 - 30


def test_squatting_keeps_the_property_with_no_more_tax_due():
    random.seed(1)
    p = Unit("player")
    guild = Guild([p])
    guild.buy_city_property()
    guild.house.missed_payments = economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT

    guild.house.squat()
    assert guild.house.owned and guild.house.squatting
    assert guild.house.tax_due_day is None
    assert guild.bankers_debt == 0


def test_ignored_debt_eventually_reaches_the_guard():
    random.seed(1)
    p = Unit("player")
    guild = Guild([p], leader=p)
    guild.bankers_debt = 40
    guild.bankers_debt_since = guild.clock.day

    guild.pass_time(economy.CITY_PROPERTY_DEBT_GRACE_DAYS * 24)
    assert p.crime == 1


# --------------------------------------------------------------------------- #
# squatting draws a guard raid on arrival ("eviction" pause)                  #
# --------------------------------------------------------------------------- #

def _forced_raid_chance(value):
    orig = forced.CITY_RAID_CHANCE
    forced.CITY_RAID_CHANCE = value
    return orig


def test_squatting_can_pause_an_arrival_on_an_eviction_raid():
    random.seed(1)
    orig = _forced_raid_chance(1.0)
    try:
        p = Unit("player")
        g = Group([p], node="market")
        guild = Guild(None, groups=[g])
        guild.buy_city_property()
        guild.house.squat()
        g.order = orders.travel(g, "city")
        result = campaign.advance(guild)
    finally:
        forced.CITY_RAID_CHANCE = orig

    assert g.node == "city" and g.order is None
    order = next(o for grp, o in result.pending if grp is g)
    assert order.kind == "eviction" and len(order.pack) > 0


def test_a_non_squatted_property_never_draws_a_raid():
    random.seed(1)
    orig = _forced_raid_chance(1.0)
    try:
        p = Unit("player")
        g = Group([p], node="market")
        guild = Guild(None, groups=[g])
        g.order = orders.travel(g, "city")
        result = campaign.advance(guild)
    finally:
        forced.CITY_RAID_CHANCE = orig

    assert g.node == "city" and g.order is None and not result.pending


def test_winning_the_raid_keeps_the_squat_losing_ends_it_for_good():
    random.seed(1)
    p = Unit("player")
    g = Group([p], node="city")
    guild = Guild(None, groups=[g])
    guild.buy_city_property()
    guild.house.squat()
    order = orders.Order("eviction", pack=(Unit("enemy"),))

    won = campaign.BattleOutcome(won=True, survivors=[p], fallen=[])
    events = forced.resolve_property_raid(guild, g, order, won)
    assert guild.house.squatting and guild.house.owned
    assert any("drive off" in e for e in events)

    lost = campaign.BattleOutcome(won=False, survivors=[p], fallen=[])
    events = forced.resolve_property_raid(guild, g, order, lost)
    assert not guild.house.squatting and not guild.house.owned
    assert any("gone for good" in e for e in events)


# --------------------------------------------------------------------------- #
# bankers_services_blocked gates property purchase at the bank                #
# --------------------------------------------------------------------------- #

def test_bankers_debt_blocks_buying_the_property():
    """After a repossession the guild owes a debt; that flag must prevent
    re-buying the property at the bank."""
    p = Unit("player")
    p.money = economy.CITY_PROPERTY_PRICE + 100
    g = Group([p], node="city")
    guild = Guild(None, groups=[g],
                  reputation={"bankers": economy.CITY_PROPERTY_REP_GATE})
    guild.bankers_debt = 50
    assert guild.bankers_services_blocked

    s = BankVault(guild, [p])
    assert not guild.house.owned
    assert "buy_property" not in [key for key, *_ in s._services()]


def test_buying_the_house_debits_the_party_at_once():
    guild, p = _at_gate(gold=economy.CITY_PROPERTY_PRICE + 40)
    s = HouseVault(guild, [p])
    s._run_service("buy")
    assert guild.house.owned and p.money == 40
