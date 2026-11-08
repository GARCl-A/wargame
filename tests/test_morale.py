"""Morale: the start value, what moves it, the rout at 0 and who sees it."""

from gartok import ai, intel, morale, wiki_rules
from gartok.actions import Flee
from gartok.conditions import Demoralized
from gartok.web.battle_session import BattleSession
from tests.helpers import Battle, standard_unit


def _fight(allies=2, foes=2, lethal=True):
    batt = Battle([standard_unit("player") for _ in range(allies)], [standard_unit("enemy") for _ in range(foes)],
                  lethal=lethal)
    batt.board.walls = set()
    batt.ambient_light = True
    for i, u in enumerate(batt.units):
        u.pos = (3 + i, 5) if u.team == "player" else (12 + i, 5)
    morale.baseline(batt)
    return batt, batt.player_units, batt.enemy_units


def _down(batt, u):
    u.take_damage(u.hp, batt.log)
    batt.settle_morale()


def test_start_follows_attributes_racial_level_and_alignment():
    u = standard_unit()
    assert morale.start_value(u) == morale.BASE + u.racial_level * morale.PER_RACIAL_LEVEL
    u.base_attributes["wisdom"] = 14
    u._apply_attributes()
    u._derive_combat()
    assert morale.start_value(u) == morale.BASE + 2 + u.racial_level * morale.PER_RACIAL_LEVEL
    lawful, chaotic = standard_unit(), standard_unit()
    lawful.alignment, chaotic.alignment = "Lawful and Neutral", "Chaotic and Neutral"
    assert morale.start_value(lawful) - morale.start_value(chaotic) == morale.LAWFUL - morale.CHAOTIC


def test_nobody_starts_below_the_minimum():
    u = standard_unit()
    for a in ("wisdom", "charisma"):
        u.base_attributes[a] = 1
    u.alignment = "Chaotic and Neutral"
    u._apply_attributes()
    u._derive_combat()
    assert morale.start_value(u) == morale.START_MIN


def test_a_fall_in_sight_costs_one_and_the_death_one_more():
    batt, (a, b), _ = _fight()
    top = a.morale
    _down(batt, b)
    assert a.morale == top + morale.ALLY_DOWN
    b.status = "dead"
    batt.settle_morale()
    assert a.morale == top + morale.ALLY_DOWN + morale.ALLY_DEAD


def test_settle_twice_changes_nothing():
    batt, (a, b), _ = _fight()
    _down(batt, b)
    now = (a.morale, [f.morale for f in batt.enemy_units])
    batt.settle_morale()
    batt.settle_morale()
    assert (a.morale, [f.morale for f in batt.enemy_units]) == now


def test_a_fall_out_of_sight_costs_nothing():
    batt, (a, b), _ = _fight()
    batt.ambient_light = False
    for u in batt.units:
        u.torch_hand = False
    a.pos, b.pos = (0, 0), (29, 12)
    top = a.morale
    _down(batt, b)
    assert a.morale == top


def test_health_marks_fire_once_and_the_last_one_again_after_a_heal():
    batt, (a, _), _ = _fight()
    a.hp_max = a.hp = 20
    morale.watch(a)
    top = a.morale
    a.hp = 10
    batt.settle_morale()
    assert a.morale == top + morale.HP_MARK
    a.hp = 10
    batt.settle_morale()
    assert a.morale == top + morale.HP_MARK
    a.hp = 5
    batt.settle_morale()
    assert a.morale == top + 2 * morale.HP_MARK
    a.hp = 1
    batt.settle_morale()
    assert a.morale == top + 3 * morale.HP_MARK
    a.hp = 15
    batt.settle_morale()
    a.hp = 1
    batt.settle_morale()
    assert a.morale == top + 4 * morale.HP_MARK


def test_each_demoralize_costs_one_even_in_the_same_turn():
    batt, _, (f, _) = _fight()
    top = f.morale
    f.add_condition(Demoralized())
    f.add_condition(Demoralized())
    batt.settle_morale()
    assert f.morale == top + 2 * morale.DEMORALIZED


def test_a_downed_foe_lifts_the_other_side_but_not_over_the_ceiling():
    batt, (a, b), (f, g) = _fight()
    a.morale = 2
    _down(batt, f)
    assert a.morale == 2 + morale.FOE_DOWN
    b.morale = b.morale_max
    _down(batt, g)
    assert b.morale == b.morale_max


def test_at_zero_the_unit_is_routed_and_needs_more_than_zero_to_rally():
    batt, (a, b), (f, g, _) = _fight(foes=3)
    a.morale = 1
    b.status = "dying"
    batt.settle_morale()
    assert a.morale == 0 and a.routed
    a.morale = -1
    _down(batt, f)
    assert a.morale == 0 and a.routed
    _down(batt, g)
    assert a.morale == 1 and not a.routed


def test_a_routed_player_unit_is_out_of_the_players_hands():
    batt, (a, _), _ = _fight()
    a.morale = 0
    batt.settle_morale()
    session = BattleSession.__new__(BattleSession)
    session.controllers = {"player": "human", "enemy": "ai"}
    assert not session.plays(a)
    assert session.plays(batt.player_units[1])


def test_non_lethal_and_mindless_fights_have_no_morale():
    batt, (a, _), _ = _fight(lethal=False)
    a.morale = 0
    batt.settle_morale()
    assert not a.routed
    batt, (a, _), (f, _) = _fight()
    f.raised = True
    assert not morale.has_morale(batt, f)
    top = a.morale
    _down(batt, f)
    assert a.morale == top


def test_a_routed_unit_runs_to_the_map_exit_when_there_is_one():
    batt, (a, _), _ = _fight()
    batt.escape_cells = [(0, 0)]
    a.morale = 0
    batt.settle_morale()
    assert ai.flee._exit_cells(batt) == [(0, 0)]
    a.pos = (0, 0)
    assert Flee._at_edge(batt, a)
    a.pos = (0, 5)
    assert not Flee._at_edge(batt, a)


def test_without_an_exit_the_whole_border_counts():
    batt, (a, _), _ = _fight()
    batt.escape_cells = []
    a.pos = (0, 5)
    assert Flee._at_edge(batt, a)


def test_a_foes_morale_is_a_medium_intel_field_and_routed_is_always_seen():
    assert intel.FIELDS["morale"] == intel.MEDIUM
    batt, (_, _), (f, _) = _fight()
    f.morale = 0
    batt.settle_morale()
    known = intel.known_fields(batt, "player", f)
    assert known.visible["conditions"] == ["routed"]


def test_the_wiki_reads_the_constants(monkeypatch):
    text = " ".join(" ".join(lines) for _, lines in wiki_rules.sections())
    assert f"{morale.BASE} +" in text
    monkeypatch.setattr(morale, "BASE", 11)
    text = " ".join(" ".join(lines) for _, lines in wiki_rules.sections())
    assert "11 +" in text


def test_the_combat_log_row_carries_morale():
    from gartok import combat_log
    assert "morale" in combat_log.UNIT_FIELDS
