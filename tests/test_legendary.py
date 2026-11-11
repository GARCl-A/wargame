"""Legendary creatures roll initiative twice and take two turns a round (`Battle._roll_initiative`)."""

import random

from gartok import npc_lib, persist
from gartok.unit import Unit as RealUnit
from tests.helpers import Battle, Unit

LEGENDS = ("aurochs", "biwolf", "the-demon", "dragon", "snake_dragon", "the-ancient-archivist")


def _fight(legend=True):
    random.seed(3)
    boss = Unit("enemy")
    boss.legendary = legend
    batt = Battle([Unit("player"), Unit("player")], [boss])
    return batt, batt.enemy_units[0]


def test_the_named_creatures_are_legendary_and_the_ogre_is_not():
    assert all(npc_lib.load_npc(s).legendary for s in LEGENDS)
    assert not npc_lib.load_npc("ogre").legendary and not npc_lib.load_npc("necromancer").legendary


def test_a_legendary_unit_holds_two_slots_and_the_higher_roll_comes_first():
    batt, boss = _fight()
    assert batt.order.count(boss) == 2 and len(batt.order) == 4
    assert boss.extra_initiative is not None and boss.initiative >= boss.extra_initiative
    slots = [batt._slot_initiative(i) for i in range(len(batt.order))]
    assert slots == sorted(slots, reverse=True)


def test_an_ordinary_unit_holds_one_slot():
    batt, boss = _fight(legend=False)
    assert batt.order.count(boss) == 1 and boss.extra_initiative is None


def test_it_acts_twice_a_round_with_full_points_each_time():
    batt, boss = _fight()
    turns = 0
    start = batt.round_no
    while batt.round_no == start:
        if batt.active is boss:
            turns += 1
            assert boss.ap == 2
            boss.ap = 0
        batt.end_turn()
    assert turns == 2


def test_it_cannot_delay():
    batt, boss = _fight()
    while batt.active is not boss:
        batt.end_turn()
    assert not batt.can_delay(boss)


def test_the_tracker_shows_both_slots_and_marks_the_one_acting():
    from gartok.web.battle_session import BattleSession
    batt, boss = _fight()
    coins = BattleSession(batt, {}, {"player": "human", "enemy": "ai"})._initiative(batt.player_units)
    assert len(coins) == 4 and sum(c["active"] for c in coins) == 1


def test_a_boost_moves_both_slots():
    batt, boss = _fight()
    before = (boss.initiative, boss.extra_initiative)
    batt.raise_initiative([boss], 3)
    assert (boss.initiative, boss.extra_initiative) == (before[0] + 3, before[1] + 3)


def test_the_flag_survives_a_save():
    boss = npc_lib.load_npc("dragon")
    assert RealUnit.from_save(persist.unit_to_dict(boss)).legendary
