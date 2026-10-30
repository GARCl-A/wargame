"""The Faith Order's errand (missions.FAITH_BATTLEFIELD) and the Battlefield's skirmish
(battlefield.py): allied soldiers played by the AI, the trenches, the potions, the fail rule."""

import random
from gartok import battlefield
from editor.battle_screen import BattleScreen
from tests.helpers import Battle, Unit

def _skirmish(squad, rng=None):
    sc = battlefield.BattlefieldScenario(squad, rng or random.Random(2))
    return Battle(squad, sc.enemies, scenario=sc, allies=sc.allies, aggressor="enemy"), sc


def test_the_screen_hands_a_soldiers_turn_to_the_ai():
    batt, _ = _skirmish([Unit("player")])
    screen = BattleScreen.__new__(BattleScreen)
    screen.controllers = {"player": "human", "enemy": "ai"}
    me, soldier = batt.player_units[0], batt.player_units[1]
    assert screen._plays(me) and not screen._plays(soldier)
    assert not screen._plays(batt.enemy_units[0])
