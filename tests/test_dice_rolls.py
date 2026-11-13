"""A battle queues one record per d20 for the dice tray."""
from gartok import actions
from gartok.actions.combat import execute_demoralize
from tests.helpers import _melee_battle, fixed_d20


def _attack(nat):
    batt, a, d = _melee_battle()
    a.ap = 2
    with fixed_d20(nat):
        actions.ATTACK.execute(batt, a, d)
    return batt, a, d


def test_a_hit_carries_the_roll_and_its_damage():
    batt, a, d = _attack(15)
    (rec,) = batt.rolls
    assert rec["actor"] is a and rec["target"] is d
    assert rec["nat"] == 15 and rec["total"] == rec["nat"] + rec["mod"]
    assert rec["vs"] == "ac" and rec["outcome"] == "hit"
    assert rec["damage"]["total"] >= 0 and rec["damage"]["rolls"]


def test_an_unread_foe_has_an_unknown_difficulty():
    batt, _, _ = _attack(15)
    assert batt.rolls[0]["dc"] == "?"


def test_a_known_foe_shows_its_armor_class():
    batt, a, d = _melee_battle()
    a.ap = 2
    batt.intel.margin["player"][d] = 99
    with fixed_d20(15):
        actions.ATTACK.execute(batt, a, d)
    assert batt.rolls[0]["dc"] == str(d.ac_vs(a))


def test_natural_twenty_is_a_crit_and_natural_one_a_fumble():
    assert _attack(20)[0].rolls[0]["outcome"] == "crit"
    fumble = _attack(1)[0].rolls[0]
    assert fumble["outcome"] == "fumble" and fumble["damage"] is None


def test_a_miss_has_no_damage():
    rec = _attack(2)[0].rolls[0]
    assert rec["outcome"] == "miss" and rec["damage"] is None


def test_every_function_that_rolls_a_d20_shows_it():
    import ast
    import pathlib
    shown = {"_resolve_hit", "rolled", "_spell_roll"}
    exempt = {}
    missing = []
    for path in sorted(pathlib.Path("gartok/actions").glob("*.py")):
        for fn in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            calls = {c.func.id if isinstance(c.func, ast.Name) else getattr(c.func, "attr", "")
                     for c in ast.walk(fn) if isinstance(c, ast.Call)}
            if "d20" in calls and not calls & shown and f"{path.name}:{fn.name}" not in exempt:
                missing.append(f"{path.name}:{fn.name}")
    assert not missing, missing


def _session(batt):
    from gartok.web.battle_session import BattleSession
    return BattleSession(batt, {}, {"player": "human", "enemy": "ai"})


def test_the_session_sends_a_roll_with_its_actor_and_target_ids():
    batt, a, d = _attack(15)
    sess = _session(batt)
    (roll,) = sess._events(visible={tuple(a.pos), tuple(d.pos)})["rolls"]
    assert roll["actor"] == sess.uid(a) and roll["target"] == sess.uid(d)
    assert roll["nat"] == 15 and not batt.rolls


def test_a_roll_by_an_unseen_actor_hides_its_id_and_one_out_of_sight_is_not_sent():
    batt, a, d = _melee_battle()
    d.ap = 2
    with fixed_d20(15):
        actions.ATTACK.execute(batt, d, a)
    sess = _session(batt)
    seen_target = sess._events(visible={tuple(a.pos)})["rolls"]
    assert len(seen_target) == 1 and seen_target[0]["actor"] is None

    with fixed_d20(15):
        actions.ATTACK.execute(batt, d, a)
    assert sess._events(visible=set())["rolls"] == []


def test_demoralize_and_a_takedown_contest_each_emit_one_roll():
    batt, a, d = _melee_battle()
    with fixed_d20(15):
        actions.Takedown.knock_down(batt, a, d)
    contests = [r for r in batt.rolls if r["vs"] == "contest"]
    assert len(contests) == 1 and contests[0]["theirs"]["nat"] == 15
    batt.rolls.clear()
    with fixed_d20(12):
        execute_demoralize(batt, a, d, free=True)
    assert [r["vs"] for r in batt.rolls] == ["md"]


def test_damage_carries_each_die_on_its_own():
    batt, a, d = _attack(15)
    dmg = batt.rolls[0]["damage"]
    assert [sum(group) for group in dmg["each"]] == dmg["rolls"]
    assert all(1 <= x <= dmg["faces"] for group in dmg["each"] for x in group)


def test_assess_emits_one_roll_against_the_read_difficulty():
    batt, a, d = _melee_battle()
    a.ap = 2
    actions.ASSESS.execute(batt, a, d)
    (rec,) = batt.rolls
    assert rec["vs"] == "dc" and rec["total"] == rec["nat"] + rec["mod"] and rec["actor"] is a


def _hit(nat, bonus, applied, read=True):
    from gartok.actions.base import _resolve_hit
    batt, a, d = _melee_battle()
    a.ap = 2
    if read:
        batt.intel.margin["player"][d] = 99
    ac = d.ac_vs(a)
    _resolve_hit(batt, a, d, nat, ac - nat + bonus, applied, "x")
    return batt.rolls[0], batt


def test_a_hit_by_exactly_the_flank_bonus_names_it():
    rec, batt = _hit(10, 0, [(2, "Flank"), (1, "Bless")])
    assert rec["outcome"] == "hit" and rec["decisive"] == {"n": 2, "why": "Flank"}
    assert any("[Flank +2 decided it]" in ln for ln in batt.log_lines)


def test_a_hit_with_room_to_spare_names_none():
    rec, batt = _hit(10, 5, [(2, "Flank")])
    assert rec["outcome"] == "hit" and "decisive" not in rec
    assert not any("decided it" in ln for ln in batt.log_lines)


def test_a_miss_by_a_penalty_names_it():
    rec, _ = _hit(10, -1, [(-3, "Dazzled")])
    assert rec["outcome"] == "miss" and rec["decisive"] == {"n": -3, "why": "Dazzled"}


def test_a_foe_not_yet_read_never_leaks_through_the_clause():
    rec, batt = _hit(10, 0, [(2, "Flank")], read=False)
    assert "decisive" not in rec and not any("decided it" in ln for ln in batt.log_lines)


def test_a_natural_twenty_needs_no_bonus_to_be_named():
    rec, _ = _hit(20, 0, [(2, "Flank")])
    assert rec["outcome"] == "crit" and "decisive" not in rec


def test_the_fight_is_named_before_a_condition_and_a_condition_before_the_attribute():
    from gartok.data import resolve_bonus
    _, applied = resolve_bonus([(3, None, "STR"), (2, "circumstance", "Flank"), (1, None, "Bless")])
    rec, _ = _hit(10, 0, applied)
    assert rec["decisive"]["why"].startswith("Flank")
    _, applied = resolve_bonus([(3, None, "STR"), (-2, "status", "Prone")])
    rec, _ = _hit(10, 0, [(3, "STR"), (-1, "Prone")])
    assert rec["decisive"]["why"] == "STR"


def test_a_tie_in_the_same_group_is_drawn_from_its_own_stream():
    from gartok.actions.base import _decisive
    seen = {_decisive([(2, "Flank"), (2, "Bless")], 10, 12, 12, True, False, 0)[1] for _ in range(60)}
    assert seen == {"Flank", "Bless"}
