"""The City property: buying it from the Bankers, the recurring tax, the
repossession/squat choice, debt escalating to the guard, and a squat drawing
periodic guard raids. See [[gartok-property-two-paths]] and
`gartok/city_property_screen.py`/`gartok/campaign.py`'s "eviction" pause --
same shape as `test_bank.py` (the screen) and `test_justice_integration.py` /
`test_road_ambush.py` (the pause/resolve seam)."""

import random

from tests.helpers import economy, Unit, world
from gartok import campaign, orders
from gartok.app import App
from gartok.city_property_screen import CityPropertyScreen, RepossessionScreen
from gartok.group import Group
from gartok.guild import Guild


def _app(guild):
    app = App.__new__(App)
    app.scene = None
    app.fonts = None
    app.guild = guild
    app._battle_squad = []
    app._battle_node = None
    app._arena_offer = None
    app._hunt = None
    app._pause_order = None
    app._pause_group = None
    app._claim_stage_pending = None
    app._map_notices = []
    app._pending = []
    app._save = lambda: None
    return app


def _screen(guild, party):
    s = CityPropertyScreen.__new__(CityPropertyScreen)
    s.guild = guild
    s.party = party
    s.sel = None
    s.notice = None
    s.on_done = lambda: None
    return s


def _at_gate(gold=economy.CITY_PROPERTY_PRICE):
    """A single-member guild past the reputation gate, with `gold` to spend."""
    p = Unit("player")
    p.gold = gold
    guild = Guild([p], reputation={"bankers": economy.CITY_PROPERTY_REP_GATE})
    return guild, p


# --------------------------------------------------------------------------- #
# buying                                                                       #
# --------------------------------------------------------------------------- #

def test_buying_charges_the_party_and_starts_the_tax_clock():
    random.seed(1)
    guild, p = _at_gate(gold=economy.CITY_PROPERTY_PRICE + 20)
    s = _screen(guild, [p])

    s._buy()
    assert guild.property_city_unlocked
    assert p.gold == 20
    assert guild.property_city_tax_due_day == guild.clock.day + economy.CITY_PROPERTY_TAX_PERIOD_DAYS


def test_buying_is_refused_below_the_reputation_gate():
    random.seed(1)
    p = Unit("player")
    p.gold = economy.CITY_PROPERTY_PRICE
    guild = Guild([p], reputation={"bankers": economy.CITY_PROPERTY_REP_GATE - 1})
    s = _screen(guild, [p])

    s._buy()
    assert not guild.property_city_unlocked and p.gold == economy.CITY_PROPERTY_PRICE


def test_buying_is_refused_when_the_party_is_short():
    random.seed(1)
    guild, p = _at_gate(gold=economy.CITY_PROPERTY_PRICE - 1)
    s = _screen(guild, [p])

    s._buy()
    assert not guild.property_city_unlocked and "copper" in s.notice


def test_buying_is_refused_while_bankers_debt_is_outstanding():
    random.seed(1)
    guild, p = _at_gate(gold=economy.CITY_PROPERTY_PRICE + 20)
    guild.bankers_debt = 10
    s = _screen(guild, [p])

    s._buy()
    assert not guild.property_city_unlocked and p.gold == economy.CITY_PROPERTY_PRICE + 20


def test_deposit_is_capped_by_the_property_and_withdraw_by_the_members_load():
    random.seed(1)
    guild, p = _at_gate()
    guild.buy_city_property()
    p._base_inventory = ["Chainmail"]              # 10.0 kg
    s = _screen(guild, [p])

    s.sel = (p, 0)
    s._deposit()
    assert guild.property_city_items == ["Chainmail"] and p._base_inventory == []

    p.carry_max = 0.5
    s.sel = ("house", 0)
    s._withdraw(p)
    assert guild.property_city_items == ["Chainmail"] and "fit" in s.notice


# --------------------------------------------------------------------------- #
# the recurring tax + missed payments                                         #
# --------------------------------------------------------------------------- #

def test_the_tax_is_charged_automatically_when_it_falls_due():
    random.seed(1)
    p = Unit("player")
    p.gold = 1000
    guild = Guild([p])
    guild.buy_city_property()
    due = guild.property_city_tax_due_day

    guild.pass_time((due - guild.clock.day) * 24)
    assert guild.clock.day >= due
    assert p.gold == 1000 - economy.CITY_PROPERTY_TAX
    assert guild.property_city_missed_payments == 0
    assert guild.property_city_tax_due_day == due + economy.CITY_PROPERTY_TAX_PERIOD_DAYS


def test_a_missed_cycle_is_tallied_instead_of_going_into_debt():
    random.seed(1)
    p = Unit("player")
    p.gold = 0
    guild = Guild([p])
    guild.buy_city_property()
    due = guild.property_city_tax_due_day

    guild.pass_time((due - guild.clock.day) * 24)
    assert p.gold == 0 and guild.property_city_missed_payments == 1
    assert not guild.property_city_repossession_due


def test_enough_missed_cycles_trip_the_repossession_offer():
    random.seed(1)
    p = Unit("player")
    p.gold = 0
    guild = Guild([p])
    guild.buy_city_property()

    for _ in range(economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT):
        due = guild.property_city_tax_due_day
        guild.pass_time((due - guild.clock.day) * 24)
    assert guild.property_city_missed_payments == economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT
    assert guild.property_city_repossession_due


# --------------------------------------------------------------------------- #
# the repossession choice: return (debt) or squat                             #
# --------------------------------------------------------------------------- #

def test_returning_the_property_banks_debt_and_blocks_bankers_services():
    random.seed(1)
    p = Unit("player")
    guild = Guild([p])
    guild.buy_city_property()
    guild.property_city_missed_payments = economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT

    guild.repossess_city_property()
    assert not guild.property_city_unlocked
    assert guild.bankers_debt == economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT * economy.CITY_PROPERTY_TAX
    assert guild.bankers_services_blocked
    assert guild.property_city_debt_since == guild.clock.day


def test_paying_off_the_debt_unblocks_bankers_services():
    random.seed(1)
    p = Unit("player")
    p.gold = 1000
    guild = Guild([p])
    guild.bankers_debt = 120
    guild.property_city_debt_since = guild.clock.day
    s = _screen(guild, [p])

    s._pay_debt()
    assert guild.bankers_debt == 0 and not guild.bankers_services_blocked
    assert guild.property_city_debt_since is None
    assert p.gold == 1000 - 120


def test_paying_off_the_debt_never_overpays():
    random.seed(1)
    p = Unit("player")
    p.gold = 1000
    guild = Guild([p])
    guild.bankers_debt = 30
    s = _screen(guild, [p])

    s._pay_debt()
    assert guild.bankers_debt == 0 and p.gold == 1000 - 30


def test_squatting_keeps_the_property_with_no_more_tax_due():
    random.seed(1)
    p = Unit("player")
    guild = Guild([p])
    guild.buy_city_property()
    guild.property_city_missed_payments = economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT

    guild.squat_city_property()
    assert guild.property_city_unlocked and guild.property_city_squatting
    assert guild.property_city_tax_due_day is None
    assert guild.bankers_debt == 0


def test_ignored_debt_eventually_reaches_the_guard():
    random.seed(1)
    p = Unit("player")
    guild = Guild([p], leader=p)
    guild.bankers_debt = 40
    guild.property_city_debt_since = guild.clock.day

    guild.pass_time(economy.CITY_PROPERTY_DEBT_GRACE_DAYS * 24)
    assert p.crime == 1


# --------------------------------------------------------------------------- #
# app wiring: RepossessionScreen pre-empts the normal property screen         #
# --------------------------------------------------------------------------- #

def test_app_opens_repossession_screen_once_it_is_due():
    random.seed(1)
    p = Unit("player")
    g = Group([p], node="city")
    guild = Guild(None, groups=[g])
    guild.buy_city_property()
    guild.property_city_missed_payments = economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT
    app = _app(guild)

    app._open_city_property(g, world.node("city"))
    assert isinstance(app.scene, RepossessionScreen)

    app.scene.on_return()
    assert not guild.property_city_unlocked and guild.bankers_debt > 0
    assert isinstance(app.scene, CityPropertyScreen) or app._pending == []


def test_app_opens_the_normal_property_screen_otherwise():
    random.seed(1)
    p = Unit("player")
    g = Group([p], node="city")
    guild = Guild(None, groups=[g])
    app = _app(guild)

    app._open_city_property(g, world.node("city"))
    assert isinstance(app.scene, CityPropertyScreen)


# --------------------------------------------------------------------------- #
# squatting draws a guard raid on arrival ("eviction" pause)                  #
# --------------------------------------------------------------------------- #

def _forced_raid_chance(value):
    orig = campaign.CITY_RAID_CHANCE
    campaign.CITY_RAID_CHANCE = value
    return orig


def test_squatting_can_pause_an_arrival_on_an_eviction_raid():
    random.seed(1)
    orig = _forced_raid_chance(1.0)
    try:
        p = Unit("player")
        g = Group([p], node="market")
        guild = Guild(None, groups=[g])
        guild.buy_city_property()
        guild.squat_city_property()
        g.order = orders.travel(g, "city")
        result = campaign.advance(guild)
    finally:
        campaign.CITY_RAID_CHANCE = orig

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
        campaign.CITY_RAID_CHANCE = orig

    assert g.node == "city" and g.order is None and not result.pending


def test_winning_the_raid_keeps_the_squat_losing_ends_it_for_good():
    random.seed(1)
    p = Unit("player")
    g = Group([p], node="city")
    guild = Guild(None, groups=[g])
    guild.buy_city_property()
    guild.squat_city_property()
    order = orders.Order("eviction", pack=(Unit("enemy"),))

    won = campaign.BattleOutcome(won=True, survivors=[p], fallen=[])
    events = campaign.resolve_property_raid(guild, g, order, won)
    assert guild.property_city_squatting and guild.property_city_unlocked
    assert any("drive off" in e for e in events)

    lost = campaign.BattleOutcome(won=False, survivors=[p], fallen=[])
    events = campaign.resolve_property_raid(guild, g, order, lost)
    assert not guild.property_city_squatting and not guild.property_city_unlocked
    assert any("gone for good" in e for e in events)


# --------------------------------------------------------------------------- #
# real draw + click, through pygame (same technique test_bank.py uses)        #
# --------------------------------------------------------------------------- #

def test_drawing_and_clicking_buy_then_stashing_an_item():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    random.seed(1)
    guild, p = _at_gate(gold=economy.CITY_PROPERTY_PRICE + 50)
    p._base_inventory = ["Rope"]
    s = CityPropertyScreen(Fonts(), guild, [p], on_done=lambda: None)
    surf = pygame.Surface((1280, 800))
    s.mouse = (0, 0)

    s.draw(surf)                                      # buy-offer state
    buy = next(r for k, r in s.buttons if k == "buy")
    s._drop(buy.center, False, None)
    assert guild.property_city_unlocked

    s.draw(surf)                                      # now the storage view
    s.sel = (p, 0)
    house = next(r for k, r in s.buttons if k == "house")
    assert s._resolve(house.center) and guild.property_city_items == ["Rope"]


def test_drawing_the_repossession_screen_and_choosing_squat():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    random.seed(1)
    p = Unit("player")
    guild = Guild([p])
    guild.buy_city_property()
    guild.property_city_missed_payments = economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT

    chosen = []
    s = RepossessionScreen(Fonts(), guild, on_return=lambda: chosen.append("return"),
                          on_squat=lambda: chosen.append("squat"))
    s.mouse = (0, 0)
    surf = pygame.Surface((1280, 800))
    s.draw(surf)
    squat = next(r for k, r in s.buttons if k == "squat")
    s._click(squat.center)
    assert chosen == ["squat"]


def test_app_runs_the_raid_battle_and_resolves_it_through_battle_end():
    random.seed(1)
    orig = _forced_raid_chance(1.0)
    try:
        p = Unit("player")
        g = Group([p], node="market")
        guild = Guild(None, groups=[g])
        guild.buy_city_property()
        guild.squat_city_property()
        app = _app(guild)
        g.order = orders.travel(g, "city")
        app._advance()
    finally:
        campaign.CITY_RAID_CHANCE = orig

    assert app._pause_order is not None and app._pause_order.kind == "eviction"
    battle = app.scene.battle
    battle.winner = "player"
    battle.round_no = 1
    for c in battle.player_units:
        c.status = "up"
    app._battle_squad = [p]
    app._battle_node = world.node("city")
    app._battle_end(battle)

    assert app._pause_order is None and guild.property_city_squatting
    assert g.order.kind == "idle"
