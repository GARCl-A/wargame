"""Wordless Menace: Demoralize across a language gap, within 6 squares and in mutual sight, at -2 (Menacing's +2 spent)."""

from gartok import actions
from gartok.actions.combat import UNSPOKEN_PENALTY, demoralize_language_penalty
from gartok.ai.reckon import _demoralize_worth
from tests.helpers import Battle, fixed_d20, standard_unit

PATH = ("imposing", "menacing", "wordless_menace")


def _duel(*talents, gap=3):
    a, d = standard_unit("player"), standard_unit("enemy")
    for i, t in enumerate(talents, 1):
        a.set_track_level("combat", i)
        assert a.choose_talent("combat", t), t
    a._derive_combat()
    d.languages = ["Orcish"]
    b = Battle([a], [d])
    ca, cd = b.units
    b.board.walls.clear()
    b.ambient_light = True
    ca.pos, cd.pos = (5, 5), (5 + gap, 5)
    ca.ap = 3
    return b, ca, cd


def test_without_the_talent_a_language_gap_blocks_demoralize():
    b, a, d = _duel("imposing", "menacing")
    assert not actions.DEMORALIZE.can(b, a, d)


def test_with_the_talent_the_gap_is_crossed_within_six_squares():
    b, a, d = _duel(*PATH, gap=6)
    assert actions.DEMORALIZE.can(b, a, d)


def test_beyond_six_squares_the_threat_needs_words():
    b, a, d = _duel(*PATH, gap=7)
    assert not actions.DEMORALIZE.can(b, a, d)


def test_a_shared_tongue_still_carries_the_full_range():
    b, a, d = _duel(*PATH, gap=10)
    d.languages = list(a.languages)
    assert actions.DEMORALIZE.can(b, a, d)


def test_no_line_of_sight_no_threat():
    b, a, d = _duel(*PATH)
    b.board.walls.add((6, 5))
    assert not actions.DEMORALIZE.can(b, a, d)


def test_the_penalty_only_applies_across_the_gap():
    _b, a, d = _duel(*PATH)
    assert demoralize_language_penalty(a, d) == UNSPOKEN_PENALTY == -2
    d.languages = list(a.languages)
    assert demoralize_language_penalty(a, d) == 0


def test_the_roll_spends_the_menacing_bonus_across_the_gap():
    b, a, d = _duel(*PATH)
    with fixed_d20(10):
        actions.DEMORALIZE.execute(b, a, d)
    text = " ".join(b.log_lines)
    assert "+2(Menacing" in text and "-2(Wordless Menace)" in text


def test_the_ai_prices_the_penalty_into_the_worth_of_the_threat():
    b, a, d = _duel(*PATH)
    across = _demoralize_worth(b, a, d)
    d.languages = list(a.languages)
    assert 0 < across < _demoralize_worth(b, a, d)
