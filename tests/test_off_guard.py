"""Off-guard: a unit that has not begun a turn this fight, or is flanked, loses 2 AC against every attack."""

from gartok import ai
from gartok.actions.base import _resolve_hit
from gartok.web import condition_marks
from tests.helpers import (
    _combatant,
    _melee_battle,
    _recruit,
    actions,
    fitted,
    fixed_d20,
)


def _flanked_pair(batt, a, d):
    """`a` and a mate on opposite sides of `d`."""
    mate = _recruit(batt, team="player")
    mate.turns_taken = 1
    d.pos, a.pos, mate.pos = (5, 5), (4, 5), (6, 5)
    return mate


def test_a_unit_that_has_not_acted_loses_two_ac_until_its_turn_begins():
    batt, a, d = _melee_battle()
    d.turns_taken = 0
    assert actions._off_guard_penalty(batt, a, d) == 2
    d.start_turn(batt.log)
    assert actions._off_guard_penalty(batt, a, d) == 0


def test_the_penalty_holds_against_a_shot_from_afar():
    batt, a, d = _melee_battle()
    d.turns_taken = 0
    d.pos = (12, 5)
    assert actions._off_guard_penalty(batt, a, d) == 2
    _resolve_hit(batt, a, d, 10, 0, "", "shot", thrown=True)
    assert any("[Off-guard -2: has not acted]" in ln for ln in batt.log_lines)


def test_the_reasons_name_every_source_and_the_log_lists_them():
    batt, a, d = _melee_battle()
    assert actions.off_guard_reasons(batt, a, d) == []
    d.turns_taken = 0
    assert actions.off_guard_reasons(batt, a, d) == ["unacted"]
    _flanked_pair(batt, a, d)
    assert actions.off_guard_reasons(batt, a, d) == ["unacted", "flanked"]
    _resolve_hit(batt, a, d, 10, 0, "", "blow")
    assert any("[Off-guard -2: has not acted, flanked]" in ln for ln in batt.log_lines)


def test_flank_and_not_having_acted_do_not_add_up():
    batt, a, d = _melee_battle()
    _flanked_pair(batt, a, d)
    d.turns_taken = 1
    assert actions._flanked(batt, a, d) and actions._off_guard_penalty(batt, a, d) == 2
    d.turns_taken = 0
    assert actions._off_guard_penalty(batt, a, d) == 2


def test_peripheral_vision_halves_both_reasons(monkeypatch):
    batt, a, d = _melee_battle()
    monkeypatch.setattr(d.char, "talent_bonus", lambda key, *args: 1 if key == "off_guard_defense" else 0)
    d.turns_taken = 0
    assert actions._off_guard_penalty(batt, a, d) == 1
    _flanked_pair(batt, a, d)
    d.turns_taken = 1
    assert actions._off_guard_penalty(batt, a, d) == 1


def test_a_unit_that_joins_the_fight_is_off_guard_until_its_first_turn():
    batt, a, _d = _melee_battle()
    newcomer = _recruit(batt, team="enemy")
    assert actions.off_guard(batt, a, newcomer)
    newcomer.start_turn(batt.log)
    assert not actions.off_guard(batt, a, newcomer)


def test_sneak_attack_and_precise_thrust_work_on_a_foe_that_has_not_acted():
    batt, a, d = _melee_battle()
    a.equip_weapon(fitted(a, "Dagger"))
    a.ap = 2
    d.turns_taken = 1
    assert actions.SNEAK_ATTACK.can(batt, a, d) is False
    d.turns_taken = 0
    assert actions.SNEAK_ATTACK.can(batt, a, d) is True
    assert actions.SNEAK_ATTACK.favoured(batt, a, d) is True
    a.equip_weapon(fitted(a, "Rapier"))
    assert actions.PRECISE_THRUST.can(batt, a, d) is True


def test_the_off_guard_actions_still_need_reach():
    batt, a, d = _melee_battle()
    a.equip_weapon(fitted(a, "Dagger"))
    a.ap = 2
    d.turns_taken = 0
    d.pos = (9, 5)
    assert actions.SNEAK_ATTACK.can(batt, a, d) is False


def test_a_thrown_weapon_at_a_flanked_foe_gets_no_extra_bonus_to_hit():
    batt, a, d = _melee_battle()
    a.equip_weapon(fitted(a, "Dagger"))
    _flanked_pair(batt, a, d)
    d.turns_taken = 1
    with fixed_d20(10):
        actions.THROW.execute(batt, a, d)
    line = next(ln for ln in batt.log_lines if "vs AC" in ln)
    assert "[Off-guard -2: flanked]" in line and "+2(Flank" not in line


def test_ambush_predator_reads_off_guard(monkeypatch):
    batt, a, d = _melee_battle()
    monkeypatch.setattr(a.char, "talent_bonus", lambda key, *args: 2 if key == "ambush_predator" else 0)
    d.turns_taken = 1
    assert all(m[2] != "Ambush Predator" for m in a.racial_hit_mods(batt, d))
    _flanked_pair(batt, a, d)
    assert (2, None, "Ambush Predator") in a.racial_hit_mods(batt, d)


def test_the_ai_reckons_better_odds_against_a_foe_that_has_not_acted():
    batt, a, d = _melee_battle()
    d.turns_taken = 1
    acted = ai.reckon._hit_odds(batt, a, d)
    d.turns_taken = 0
    assert ai.reckon._hit_odds(batt, a, d) > acted


def test_the_ai_gains_nothing_by_flanking_a_foe_that_has_not_acted():
    batt, a, d = _melee_battle()
    _flanked_pair(batt, a, d)
    a.ap = 2
    d.turns_taken = 1
    assert ai.reckon._flank_step_worth(batt, a, d, free=True) is not None
    d.turns_taken = 0
    assert ai.reckon._flank_step_worth(batt, a, d, free=True) is None


def test_the_board_marks_a_unit_off_guard_only_until_its_first_turn():
    u = _combatant()
    assert "off_guard" in [m["id"] for m in condition_marks.marks(u)]
    u.start_turn(lambda *args, **kw: None)
    assert "off_guard" not in [m["id"] for m in condition_marks.marks(u)]
