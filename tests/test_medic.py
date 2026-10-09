"""The Medic: priced as the expected potions and doses, one clock for the group."""

import random

import pytest

from gartok import economy, items, medic
from gartok.clock import Clock
from gartok.group import Group
from gartok.guild import Guild
from gartok.medic_screen import MedicScreen
from gartok.ui.tokens import fonts
from tests.helpers import Unit

VENOM = "giant_spider_venom"
NOON = 12 * 3600


def _unit(missing=0, money=1000):
    random.seed(3)
    u = Unit("player")
    u.hp = u.hp_max - missing
    u.money = money
    return u


def _setup(*units):
    g = Group(list(units), node="city")
    return Guild(None, groups=[g], clock=Clock(NOON)), g


def _potion_cost(hp):
    n = -(-hp * 2 // 7)
    return round(n * items.get("Minor Healing Potion").price * economy.MEDIC_PRICE_FACTOR)


def test_a_healthy_unit_needs_nothing():
    q = medic.quote(_unit())
    assert not q.needs_care and q.cost == 0 and q.hours == 0


def test_hp_costs_the_potions_it_would_take_for_an_hour():
    u = _unit(missing=1)
    q = medic.quote(u)
    assert q.cost == _potion_cost(1) and q.hours == economy.MEDIC_HP_HOURS
    assert medic.quote(_unit(missing=1)).cost < _potion_cost(1) / economy.MEDIC_PRICE_FACTOR + 1
    big = u.hp_max - 1
    u.hp = 1
    assert medic.quote(u).cost == _potion_cost(big)


def test_sickness_is_one_first_aid_charge_and_eight_hours():
    u = _unit()
    u.sick = True
    kit = items.get(items.FIRST_AID_ITEM)
    q = medic.quote(u)
    assert q.cost == round(kit.price / kit.max_charges * economy.MEDIC_PRICE_FACTOR)
    assert q.hours == economy.MEDIC_SICKNESS_HOURS


@pytest.mark.parametrize("stacks, doses, hours", [(1, 1, 1), (2, 1, 24), (3, 2, 24), (4, 2, 48), (5, 3, 48)])
def test_poison_costs_half_the_stacks_in_doses(stacks, doses, hours):
    u = _unit()
    for _ in range(stacks):
        u.add_poison(VENOM, 12)
    q = medic.quote(u)
    assert q.cost == round(doses * items.get(items.ANTIDOTE_ITEM).price * economy.MEDIC_PRICE_FACTOR)
    assert q.hours == hours
    assert q.offered == (hours <= economy.MEDIC_MAX_HOURS)


def test_a_patient_pays_every_ailment_and_waits_the_longest():
    u = _unit(missing=2)
    u.sick = True
    q = medic.quote(u)
    assert q.cost == sum(c for _, c, _ in q.parts) and q.hours == economy.MEDIC_SICKNESS_HOURS


def test_treat_pays_advances_the_clock_and_cures():
    u = _unit(missing=2)
    u.sick = True
    u.add_poison(VENOM, 12)
    guild, g = _setup(u)
    q = medic.quote(u)
    ok, _ = medic.treat(guild, g, [u])
    assert ok
    assert u.hp == u.hp_max and not u.sick and not u.poisoned
    assert u.money == 1000 - q.cost
    assert guild.clock.hour_of_day == (12 + q.hours) % 24


def test_the_group_waits_for_the_longest_pick():
    a, b = _unit(missing=1), _unit()
    b.sick = True
    guild, g = _setup(a, b)
    ok, _ = medic.treat(guild, g, [a, b])
    assert ok and guild.clock.hour_of_day == 12 + economy.MEDIC_SICKNESS_HOURS


def test_only_the_picked_are_treated():
    a, b = _unit(missing=1), _unit(missing=1)
    guild, g = _setup(a, b)
    medic.treat(guild, g, [a])
    assert a.hp == a.hp_max and b.hp < b.hp_max


def test_the_richest_member_pays_first():
    a, b = _unit(missing=1, money=50), _unit(money=900)
    guild, g = _setup(a, b)
    cost = medic.quote(a).cost
    medic.treat(guild, g, [a])
    assert b.money == 900 - cost and a.money == 50


def test_an_unaffordable_treatment_changes_nothing():
    u = _unit(missing=1, money=0)
    guild, g = _setup(u)
    before = guild.clock.hour_of_day
    ok, lines = medic.treat(guild, g, [u])
    assert not ok and "pay" in lines[0]
    assert u.hp < u.hp_max and guild.clock.hour_of_day == before


def test_a_long_poison_is_refused():
    u = _unit()
    for _ in range(4):
        u.add_poison(VENOM, 12)
    guild, g = _setup(u)
    ok, _ = medic.treat(guild, g, [u])
    assert not ok and u.poisoned


def test_treating_nobody_does_nothing():
    guild, g = _setup(_unit())
    assert medic.treat(guild, g, [g.members[0]])[0] is False
    assert medic.treat(guild, g, [])[0] is False


def test_screen_picks_and_treats():
    u = _unit(missing=2)
    guild, g = _setup(u)
    done = []
    scr = MedicScreen(fonts(), guild, g, lambda: done.append(1))
    import pygame
    surf = pygame.Surface((1280, 720))
    scr.draw(surf)
    (uid, rect), = scr.row_rects
    scr._click(rect.center)
    assert scr.picked == {uid}
    scr.draw(surf)
    scr._click(scr.treat_rect.center)
    assert u.hp == u.hp_max and not scr.picked
    assert scr.tutorial_key() == "medic"
    assert scr.handle_escape() and done


def test_the_sim_prices_the_same_hp_the_same():
    import sys
    sys.path.insert(0, "scripts")
    import economy_activities as act
    for missing in (1, 4, 9):
        u = _unit(missing=missing)
        assert round(act.medic_cost(u.hp_max - u.hp)) == medic.quote(u).cost


def test_the_sim_treats_with_the_same_quotes_for_sickness_and_poison():
    import sys
    sys.path.insert(0, "scripts")
    import economy_guild as sim_mod
    sim = sim_mod.Sim(sim_mod.Lumber(), seed=1, library=sim_mod.FightLibrary(samples=1), medic=True)
    u = sim.members[0]
    u.money = 1000
    u.hp = max(1, u.hp_max - 2)
    u.sick = True
    for _ in range(2):
        u.add_poison(VENOM, 12)
    cost = medic.quote(u).cost
    before = sim.money
    assert sim.treat()
    assert before - sim.money == cost == sim.treated
    assert u.hp == u.hp_max and not u.sick and not u.poisoned
