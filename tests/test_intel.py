"""What a side knows of a foe: the opening read, the bands it opens, Assess, the bestiary."""

import pytest
from gartok import actions, ai, conditions, intel
from gartok.battle import Battle
from tests.helpers import Unit

def _fight(foes=1, hidden=False):
    """A hero and `foes` enemies in daylight; `hidden` puts a wall between them."""
    batt = Battle([Unit("player")], [Unit("enemy") for _ in range(foes)])
    batt.ambient_light = True
    batt.board.walls = {(5, y) for y in range(batt.board.rows)} if hidden else set()
    hero = batt.player_units[0]
    hero.pos = (2, 5)
    for i, e in enumerate(batt.enemy_units):
        e.pos = (8, 5 + i)
    return batt, hero, batt.enemy_units

def _read(batt, team, foe, margin):
    """Pin `team`'s margin on `foe`."""
    batt.intel.margin[team][foe] = margin

def _stand_off(aggressor, foes=1):
    """A hero hiding at (2, 0) behind a wall, `foes` enemies on the far side, a gap at the bottom."""
    batt = Battle([Unit("player")], [Unit("enemy") for _ in range(foes)], aggressor=aggressor)
    batt.ambient_light = True
    batt.board.walls = {(5, y) for y in range(10)}
    hero = batt.player_units[0]
    hero.pos = (2, 0)
    hero.hp = max(hero.hp, 10)
    hero.status = "up"
    for i, e in enumerate(batt.enemy_units):
        e.pos = (10, 2 + 4 * i)
        e.hp = max(e.hp, 10)
        e.status = "up"
    batt.intel = intel.Intel(batt)
    return batt, hero, batt.enemy_units

def _act(batt, unit):
    batt.turn_idx = batt.order.index(unit)
    unit.ap = 2
    ai.take_turn(batt, unit)

def _dist(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def test_health_fills_one_to_five_steps_and_a_standing_unit_keeps_one():
    _, _hero, (foe,) = _fight()
    foe.hp_max = 20
    for hp, steps in ((20, 5), (17, 5), (16, 4), (10, 3), (5, 2), (1, 1), (0, 0)):
        foe.hp = hp
        assert intel.health_steps(foe) == steps, hp


def test_a_foe_nobody_sees_is_not_read():
    batt, _hero, (foe,) = _fight(hidden=True)
    intel.observe(batt, "player")
    assert foe not in batt.intel.margin["player"]
    assert intel.known_fields(batt, "player", foe).margin is None


def test_a_foe_in_sight_is_read_once_and_the_margin_is_stable():
    batt, _hero, (foe,) = _fight()
    known = intel.known_fields(batt, "player", foe)
    assert known.margin is not None
    batt.round_no += 1                      # time passes: it is not read again
    assert intel.known_fields(batt, "player", foe).margin == known.margin


def test_the_dc_is_eight_plus_the_racial_level_and_drops_for_a_race_already_fought():
    batt, _hero, (foe,) = _fight()
    batt.intel.bestiary["player"] = intel.Bestiary()
    level = foe.char.racial_level
    assert intel.dc(batt, "player", foe) == intel.BASE_DC + level
    batt.intel.bestiary["player"].races.add(foe.race["name"])
    assert intel.dc(batt, "player", foe) == intel.BASE_DC + level - intel.RACE_DISCOUNT


def test_a_side_bonus_lifts_the_roll():
    low, _hero, (foe,) = _fight()
    high, _hero2, (foe2,) = _fight()
    for b, bonus in ((low, 0), (high, 30)):
        b.intel.bind("player", None, bonus)
        b.intel.rng.seed(1)
    assert (intel.known_fields(high, "player", foe2).margin
            - intel.known_fields(low, "player", foe).margin) >= 25


def test_the_foe_side_reads_the_hero_the_same_way():
    batt, hero, (_foe,) = _fight()
    assert intel.known_fields(batt, "enemy", hero).margin is not None


@pytest.mark.parametrize("margin, opened", [
    (-1, set()),
    (0, {"damage_die", "speed", "level", "racial_ability"}),
    (5, {"damage_die", "speed", "level", "racial_ability", "to_hit", "damage_bonus", "ac", "md"}),
    (10, set(intel.FIELDS) - {"artifact"}),
])
def test_the_margin_opens_the_bands(margin, opened):
    batt, _hero, (foe,) = _fight()
    _read(batt, "player", foe, margin)
    known = intel.known_fields(batt, "player", foe)
    assert {k for k, v in known.fields.items() if v is not None} == opened


def test_a_hard_read_shows_the_real_numbers():
    batt, _hero, (foe,) = _fight()
    _read(batt, "player", foe, 12)
    f = intel.known_fields(batt, "player", foe).fields
    assert (f["ac"], f["md"], f["speed"]) == (foe.ac, foe.mental_defense, foe.speed)
    assert f["hp"] == (foe.hp, foe.hp_max)
    assert f["attrs"][0] == ("STR", foe.strength)
    assert f["racial_ability"] == (foe.ability.name, foe.ability.effect)


def test_the_artefact_effect_only_exists_for_a_foe_that_wears_one():
    batt, _hero, (foe,) = _fight()
    _read(batt, "player", foe, 12)
    assert "artifact" not in intel.known_fields(batt, "player", foe).fields
    foe.equipped_artifact = "Signal Horn"
    assert "initiative" in intel.known_fields(batt, "player", foe).fields["artifact"]


def test_your_own_side_is_fully_known():
    batt, hero, _ = _fight()
    known = intel.known_fields(batt, "player", hero)
    assert known.full
    assert all(v is not None for v in known.fields.values())


def test_every_condition_on_a_foe_shows_on_sight():
    batt, hero, (foe,) = _fight()
    for cond in (conditions.Grappled(hero), conditions.Defending(), conditions.Surprised(),
                 conditions.ShieldHooked(), conditions.Sleeping()):
        foe.add_condition(cond)
    assert {"grappled", "defending", "surprised", "shield hooked", "asleep"} <= set(
        intel.known_fields(batt, "player", foe).visible["conditions"])


def test_a_racial_ability_seen_once_is_free_on_the_next_of_the_race():
    batt, _hero, (foe,) = _fight()
    best = batt.intel.bestiary["player"] = intel.Bestiary()
    _read(batt, "player", foe, -3)
    assert not intel.knows(batt, "player", foe, "racial_ability")
    best.abilities.add(foe.ability.id)
    assert intel.knows(batt, "player", foe, "racial_ability")


def test_a_read_that_opens_the_racial_ability_files_it_in_the_bestiary():
    batt, _hero, (foe,) = _fight()
    best = batt.intel.bestiary["player"] = intel.Bestiary()
    intel._store(batt, "player", foe, 3)
    assert foe.ability.id in best.abilities


def test_first_sight_files_the_race_for_the_next_fight():
    batt, _hero, (foe,) = _fight()
    best = batt.intel.bestiary["player"] = intel.Bestiary()
    intel.observe(batt, "player")
    assert foe.race["name"] in best.races


def test_an_authored_npc_stays_known_in_the_next_fight():
    best = intel.Bestiary()
    first, _hero, (foe,) = _fight()
    foe.char.npc_slug = "ribit"
    first.intel.bestiary["player"] = best
    intel._store(first, "player", foe, 11)
    assert best.named["ribit"] == 11
    second, _hero2, (foe2,) = _fight()
    foe2.char.npc_slug = "ribit"
    second.intel.bestiary["player"] = best
    assert intel.known_fields(second, "player", foe2).margin >= 11


def test_the_bestiary_round_trips_through_a_dict():
    best = intel.Bestiary({"Orc"}, {"orc_ferocity"}, {"ribit": 7})
    again = intel.Bestiary.from_dict(best.to_dict())
    assert (again.races, again.abilities, again.named) == ({"Orc"}, {"orc_ferocity"}, {"ribit": 7})


def test_assess_costs_a_point_rolls_with_a_bonus_and_never_lowers_the_margin():
    batt, hero, (foe,) = _fight()
    _read(batt, "player", foe, 4)
    batt.turn_idx = batt.order.index(hero)
    hero.ap = 2
    actions.ASSESS.execute(batt, hero, foe)
    assert hero.ap == 1
    assert batt.intel.margin["player"][foe] >= 4
    assert any("studies" in line for line in batt.log_lines)


def test_assess_opens_what_the_better_roll_reaches_and_says_so():
    batt, hero, (foe,) = _fight()
    _read(batt, "player", foe, -1)
    batt.intel.bind("player", None, 40)
    _total, margin, opened = intel.assess(batt, hero, foe)
    assert margin >= intel.HARD and "ac" in opened and "hp" in opened


def test_assess_is_once_per_foe_a_round_and_needs_sight():
    batt, hero, (foe,) = _fight()
    assert actions.ASSESS.can(batt, hero, foe)
    batt.turn_idx = batt.order.index(hero)
    hero.ap = 2
    actions.ASSESS.execute(batt, hero, foe)
    assert not actions.ASSESS.can(batt, hero, foe)
    assert intel.assess_block(batt, hero, foe) == "already assessed this round"
    batt.round_no += 1
    assert actions.ASSESS.can(batt, hero, foe)
    dark, hero2, (foe2,) = _fight(hidden=True)
    assert intel.assess_block(dark, hero2, foe2) == "not in sight"
    assert intel.assess_block(dark, hero2, hero2) == "not a foe"


def test_assess_is_on_the_action_panel():
    assert actions.ASSESS in actions.PANEL_ACTIONS


def test_an_attack_log_says_question_mark_for_an_unread_ac_and_the_number_once_read():
    batt, hero, (foe,) = _fight()
    foe.pos = (3, 5)
    batt.turn_idx = batt.order.index(hero)
    hero.ap = 2
    _read(batt, "player", foe, -5)
    actions.ATTACK.execute(batt, hero, foe)
    assert "vs AC ?" in next(ln for ln in batt.log_lines if "vs AC" in ln)
    _read(batt, "player", foe, intel.MEDIUM)
    batt.log_lines.clear()
    hero.ap = 2
    actions.ATTACK.execute(batt, hero, foe)
    assert f"vs AC {foe.ac}" in next(ln for ln in batt.log_lines if "vs AC" in ln)


def test_an_attack_on_your_own_unit_always_shows_its_ac():
    batt, hero, (foe,) = _fight()
    foe.pos = (3, 5)
    batt.turn_idx = batt.order.index(foe)
    foe.ap = 2
    actions.ATTACK.execute(batt, foe, hero)
    assert f"vs AC {hero.ac}" in next(ln for ln in batt.log_lines if "vs AC" in ln)


def test_the_ai_ranks_foes_by_health_step_not_by_hidden_hit_points():
    batt, hero, foes = _fight(foes=2)
    near, other = foes
    for i, e in enumerate(foes):
        e.pos = (3, 4 + i)                 # both equally near
        e.hp_max = 40
    near.hp, other.hp = 39, 38             # the same step (full): hit points differ by one
    for e in foes:
        _read(batt, "player", e, -5)       # nothing learned of either
    assert ai._focus_key(batt, hero, near)[1:] == ai._focus_key(batt, hero, other)[1:] == (5, 99)
    other.hp = 8                           # a visibly wounded foe
    assert ai._focus_key(batt, hero, other) < ai._focus_key(batt, hero, near)


def test_the_ai_uses_the_exact_hit_points_once_it_has_read_them():
    batt, hero, (foe,) = _fight()
    _read(batt, "player", foe, intel.HARD)
    assert ai._focus_key(batt, hero, foe)[2] == foe.hp


def test_the_ai_assumes_a_foe_can_sleep_until_its_racial_ability_is_read():
    batt, hero, (foe,) = _fight()
    foe._ability = type("A", (), {"sleep_immunity": True, "id": "x", "name": "x", "effect": ""})()
    foe.char._ability = foe._ability
    _read(batt, "player", foe, -3)
    assert not ai._sleep_immune(batt, hero, foe)
    _read(batt, "player", foe, 0)
    assert ai._sleep_immune(batt, hero, foe)


def test_the_ai_counts_only_the_foes_it_sees_when_deciding_to_run():
    batt, _hero, (foe,) = _fight(hidden=True)
    foe.hp, foe.alignment = 1, "Chaotic and Neutral"
    assert intel.visible_foes(batt, foe) == []
    assert not ai._should_flee(batt, foe)         # nobody in sight: nothing to flee from


def test_the_ai_spends_a_spare_point_to_assess_the_foe_it_knows_least():
    batt, hero, (foe,) = _fight()
    _read(batt, "player", foe, -4)
    batt.turn_idx = batt.order.index(hero)
    hero.ap = 2
    assert ai._try_assess(batt, hero)
    assert hero.ap == 1
    assert batt.intel.assessed[("player", foe)] == batt.round_no


def test_the_ai_does_not_assess_a_foe_it_has_fully_read():
    batt, hero, (foe,) = _fight()
    _read(batt, "player", foe, intel.HARD + 3)
    hero.ap = 2
    assert not ai._try_assess(batt, hero)


def test_a_guild_starts_with_an_empty_bestiary_and_saves_it():
    from gartok import persist
    from gartok.guild import Guild
    guild = Guild([Unit("player")], node="city", name="Learned")
    assert not (guild.bestiary.races or guild.bestiary.abilities or guild.bestiary.named)
    guild.bestiary.races.add("Orc")
    guild.bestiary.named["ribit"] = 9
    wid = persist.new_world_id()
    persist.save_game(wid, guild)
    again = persist.load_game(wid).bestiary
    assert again.races == {"Orc"} and again.named == {"ribit": 9}


def test_the_side_that_brought_the_fight_remembers_where_its_prey_started():
    batt, hero, (_foe,) = _stand_off("enemy")
    assert batt.intel.last_seen["enemy"] == {hero: hero.pos}
    assert batt.intel.last_seen["player"] == {}


def test_an_attacker_with_nobody_in_sight_closes_on_the_last_place_it_saw_a_foe():
    batt, _hero, (foe,) = _stand_off("enemy")
    start = foe.pos
    _act(batt, foe)
    assert foe.pos != start and foe.pos[1] > start[1]      # heads for the gap under the wall


def test_an_attacker_forgets_a_place_it_reached_and_found_empty():
    batt, hero, (foe,) = _stand_off("enemy")
    batt.intel.last_seen["enemy"] = {hero: (9, 2)}
    foe.pos = (9, 3)
    goal, reach = ai._search_goal(batt, foe)
    assert batt.intel.last_seen["enemy"] == {}
    assert reach == 0 and goal is not None          # the sweep takes over


def test_an_attacker_that_never_saw_anyone_sweeps_the_board_waypoint_by_waypoint():
    batt, _hero, (foe,) = _stand_off("enemy")
    batt.intel.last_seen["enemy"].clear()
    first, _ = ai._search_goal(batt, foe)
    assert first[0] % ai.SEARCH_STEP == ai.SEARCH_STEP // 2
    foe.pos = first
    nxt, _ = ai._search_goal(batt, foe)
    assert first in batt.intel.visited["enemy"] and nxt != first


def test_an_attacker_finds_a_player_hiding_behind_a_wall():
    batt, hero, (foe,) = _stand_off("enemy")
    batt.intel.last_seen["enemy"].clear()
    for _ in range(80):
        if intel.visible_foes(batt, foe):
            break
        _act(batt, foe)
    assert hero in intel.visible_foes(batt, foe)


def test_a_defender_with_nobody_in_sight_groups_up_instead_of_hunting():
    batt, hero, (a, b) = _stand_off("player", foes=2)
    start = _dist(a.pos, b.pos)
    for _ in range(6):
        _act(batt, a)
        _act(batt, b)
    assert _dist(a.pos, b.pos) < start and _dist(a.pos, b.pos) <= ai.GROUP_GAP + 1
    assert hero.pos == (2, 0)


def test_a_lone_defender_holds_its_ground():
    batt, _hero, (foe,) = _stand_off("player")
    where = foe.pos
    _act(batt, foe)
    assert foe.pos == where


def test_a_defender_still_fights_what_it_sees():
    batt, hero, (foe,) = _stand_off("player")
    batt.board.walls = set()
    assert ai._target(batt, foe) is hero


def test_with_no_role_the_ai_still_advances_on_a_foe_it_cannot_see():
    batt, hero, (foe,) = _stand_off(None)
    assert ai._target(batt, foe) is hero
    start = foe.pos
    _act(batt, foe)
    assert foe.pos != start and foe.pos[1] > start[1]


def test_an_attacker_closes_on_a_foe_only_a_teammate_sees():
    batt, hero, (a, b) = _stand_off("enemy", foes=2)
    batt.board.walls = {(5, y) for y in range(10)}
    a.pos, b.pos = (7, 0), (10, 8)                       # a is at the wall, b a long way off
    batt.board.walls = set()
    hero.pos = (7, 5)
    batt.board.walls = {(8, y) for y in range(6, 12)}      # hides the hero from b, not from a
    assert hero in intel.visible_foes(batt, a)
    assert ai._target(batt, b) is hero


def test_the_fight_s_role_is_logged_and_survives_a_rebuild(tmp_path):
    from gartok import combat_lab, combat_log
    battle, meta = combat_lab.build("wilds", 1, 2, seed=4)
    assert battle.aggressor == "enemy"
    log = combat_log.CombatLog(str(tmp_path / "wilds.jsonl"), meta, {"player": "human", "enemy": "ai"})
    battle.record_to(log)
    log.end(battle)
    rows = combat_log.load(log.path)
    assert rows[0]["aggressor"] == "enemy"
    assert combat_log.rebuild(rows).aggressor == "enemy"


def test_the_lab_fights_say_who_brought_them():
    from gartok import combat_lab
    assert combat_lab.build("dungeon", 2, 2, seed=1)[0].aggressor == "player"
    assert combat_lab.build("road", 2, 2, seed=1)[0].aggressor == "enemy"
    assert combat_lab.build("scrapper", 0, 3, seed=1)[0].aggressor is None


def test_a_lab_seed_rebuilds_the_same_fight_names_and_opening_reads_included():
    from gartok import combat_lab, names

    def fight():
        names.seed(None)                        # whatever the name stream was doing before
        battle, _ = combat_lab.build("lair", 3, 4, seed=7)
        return ([(u.name, u.equipped_weapon) for u in battle.units], battle.intel.rng.random())

    assert fight() == fight()
