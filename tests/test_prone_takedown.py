from unittest.mock import patch

from gartok import actions, ai
from gartok.ai.attack import _should_takedown
from gartok.battle import Battle
from gartok.conditions import Prone
from tests.helpers import standard_unit


def _fight(str_a=10, dex_b=10, gap=1):
    a, b = standard_unit("player"), standard_unit("enemy")
    a.strength, b.dexterity = str_a, dex_b
    a._derive_combat()
    b._derive_combat()
    battle = Battle([a], [b])
    ca, cb = battle.player_units[0], battle.enemy_units[0]
    ca.pos, cb.pos = (1, 1), (1, 1 + gap)
    return battle, ca, cb


def _roll(battle, actor, target, mine, theirs):
    with patch("gartok.actions.combat.d20", side_effect=[mine, theirs]):
        actions.TAKEDOWN.execute(battle, actor, target)


def test_takedown_wins_the_contest_and_the_foe_goes_prone():
    battle, a, b = _fight()
    _roll(battle, a, b, 12, 8)
    assert b.has_condition("prone")
    assert a.ap == 1


def test_takedown_matching_the_roll_is_enough():
    battle, a, b = _fight()
    _roll(battle, a, b, 10, 10)
    assert b.has_condition("prone")


def test_takedown_loss_leaves_the_foe_standing_but_still_costs_the_point():
    battle, a, b = _fight()
    _roll(battle, a, b, 9, 10)
    assert not b.has_condition("prone")
    assert a.ap == 1


def test_takedown_natural_20_always_lands():
    battle, a, b = _fight(dex_b=20)
    _roll(battle, a, b, 20, 20)
    assert b.has_condition("prone")


def test_takedown_uses_strength_against_dexterity():
    battle, a, b = _fight(str_a=10, dex_b=14)
    _roll(battle, a, b, 10, 10)
    assert not b.has_condition("prone")
    battle, a, b = _fight(str_a=14, dex_b=10)
    _roll(battle, a, b, 10, 10)
    assert b.has_condition("prone")


def test_takedown_needs_melee_reach_a_standing_foe_and_a_walker():
    battle, a, b = _fight(gap=3)
    assert not actions.TAKEDOWN.can(battle, a, b)
    battle, a, b = _fight()
    assert actions.TAKEDOWN.can(battle, a, b)
    b.add_condition(Prone())
    assert not actions.TAKEDOWN.can(battle, a, b)
    battle, a, b = _fight()
    a.ap = 0
    assert not actions.TAKEDOWN.can(battle, a, b)


def test_prone_cannot_move_and_attacks_at_minus_two():
    battle, a, b = _fight()
    assert battle.reachable(b)
    plain = sum(m[0] for m in b.attack_mods(a))
    b.add_condition(Prone())
    assert battle.reachable(b) == {}
    assert sum(m[0] for m in b.attack_mods(a)) == plain - 2
    assert not actions.MOVE.available(battle, b)
    assert not actions.JUMP.available(battle, b)
    assert not actions.FLEE.available(battle, b)
    assert actions.FLEE.blocked_reason(battle, b) == "on the ground"


def test_a_held_fighter_cannot_jump_out():
    from gartok.conditions import Entangled, Grappled
    for held in (Entangled(), Grappled()):
        battle, _, b = _fight()
        assert actions.JUMP.available(battle, b)
        b.add_condition(held)
        assert not actions.JUMP.available(battle, b)
        assert not actions.JUMP.can(battle, b, (1, 5))


def test_stand_up_costs_one_point_and_only_works_while_prone():
    battle, a, b = _fight()
    assert not actions.STAND_UP.available(battle, b)
    b.add_condition(Prone())
    assert actions.STAND_UP.available(battle, b)
    actions.STAND_UP.execute(battle, b)
    assert not b.has_condition("prone")
    assert b.ap == 1
    assert battle.reachable(b)
    actions.STAND_UP.execute(battle, b)
    assert b.ap == 1


def test_both_actions_are_on_the_panel():
    assert actions.TAKEDOWN in actions.PANEL_ACTIONS
    assert actions.STAND_UP in actions.PANEL_ACTIONS


def test_takedown_and_stand_up_are_logged():
    battle, a, b = _fight()
    _roll(battle, a, b, 15, 5)
    actions.STAND_UP.execute(battle, b)
    text = "\n".join(battle.log_lines)
    assert "on the ground" in text and "back on their feet" in text


def test_ai_stands_up_before_anything_else():
    battle, a, b = _fight()
    b.add_condition(Prone())
    ai.take_turn(battle, b)
    assert not b.has_condition("prone")


def test_ai_leaves_an_ordinary_foe_standing():
    battle, a, b = _fight(str_a=18)
    assert not _should_takedown(battle, a, b)


def test_ai_takes_down_a_fleeing_foe():
    battle, a, b = _fight()
    b.fleeing = True
    assert _should_takedown(battle, a, b)


def test_ai_takes_down_the_flag_runner(monkeypatch):
    battle, a, b = _fight()
    monkeypatch.setattr("gartok.ai.attack._runs_flag", lambda battle, target: target is b)
    assert _should_takedown(battle, a, b)
