"""The magic track (talents.py / progression.py), composite races, and Dragon racial talents."""

import random
from unittest.mock import patch

from gartok import ai, campaign, data, magic, progression, talents
from gartok.board import cone_cells
from tests.helpers import Battle, Combatant, Unit, actions, persist, standard_unit


def _mage(level=3, *picks):
    u = standard_unit()
    u.add_magic_source("blood")
    u.add_magic_source("faith")
    u.set_track_level("magic", level)
    for tid in picks:
        assert u.choose_talent("magic", tid)
    return u


def _dragon_breather():
    u = Unit("enemy", race=data.race_by_name(["Snake", "Dragon"]))
    u.set_track_level("racial", 10)
    assert u.choose_talent("racial", "dragon")
    assert u.choose_talent("racial", "dragon_breath")
    return u


def test_magic_tree_is_school_agnostic_and_gated_by_arcane_mind():
    u = Unit("player")
    u.set_track_level("magic", 3)
    assert "magic" in u.pending_picks
    assert not u.choose_talent("magic", "spell_focus")
    assert not u.choose_talent("magic", "far_cast")
    int_before = u.intelligence
    md_before = u.mental_defense
    assert u.choose_talent("magic", "arcane_mind")
    assert u.intelligence == int_before + 1
    assert u.choose_talent("magic", "focused_will")
    assert u.mental_defense >= md_before + 1
    assert not u.choose_talent("magic", "far_cast")
    assert u.choose_talent("magic", "spell_focus")


def test_spell_focus_destructive_casting_blessed_hands_and_far_cast():
    caster = _mage(4, "arcane_mind", "spell_focus", "destructive_casting", "far_cast")
    caster.set_spell_known("magic_missile", True)
    caster.set_spell_known("healing_touch", True)
    foe = standard_unit("enemy")
    batt = Battle([caster], [foe])
    batt.board.walls.clear()
    me, target = batt.player_units[0], batt.enemy_units[0]
    me.pos, target.pos = (2, 2), (9, 2)               # distance 7: base 6 + Far Cast 1
    mm = actions.CastSpellAction("magic_missile")
    assert mm.can(batt, me, target)
    target.pos = (10, 2)
    assert not mm.can(batt, me, target)
    target.pos = (9, 2)
    target.hp = 30
    with patch("gartok.actions.spells.d20", return_value=10), \
            patch("gartok.actions.spells.data.roll", return_value=3):
        mm.execute(batt, me, target)
    assert target.hp == 30 - 4                        # 3 rolled + 1 Destructive Casting

    # Blessed Hands adds +1 HP to Healing Touch, and Far Cast does not extend touch range
    caster.drop_talent("magic", "far_cast")
    assert caster.choose_talent("magic", "blessed_hands")
    heal = actions.CastSpellAction("healing_touch")
    me.hp = 1
    me.ap = 2
    with patch("gartok.actions.spells.data.roll", return_value=4):
        heal.execute(batt, me, me)
    assert me.hp == 1 + 5                             # 4 rolled + 1 Blessed Hands


def test_composite_race_averages_mods_floors_hd_ceils_size_and_merges_racial_trees():
    hybrid = data.race_by_name(["Snake", "Dragon"])
    snake, dragon = data.race_by_name("Snake"), data.race_by_name("Dragon")
    assert hybrid["name"] == "Snake, Dragon"
    assert hybrid["races"] == ("Snake", "Dragon")
    assert hybrid["mods"] == tuple((a + b) // 2 for a, b in zip(snake["mods"], dragon["mods"]))
    assert hybrid["hd"] == 8                          # (6 + 12) / 2 = 9 -> floored to d8
    assert hybrid["size"] == "Large"                  # ceil((Small + Huge) / 2) -> Large
    tree_ids = {t.id for t in talents.racial_tree(hybrid["name"])}
    assert {"serpent_growth", "snake_venom", "dragon", "dragon_breath"} <= tree_ids

    u = Unit("enemy", race=hybrid)
    ac = u.ac
    u.set_track_level("racial", 10)
    assert u.choose_talent("racial", "dragon")
    assert u.choose_talent("racial", "dragon_breath")
    assert u.ac == ac + 1
    back = Unit.from_save(persist.unit_to_dict(u))
    assert back.race["races"] == ("Snake", "Dragon") and back.size == "Large"


def test_magic_levels_feed_the_racial_track():
    u = Unit("player")
    u.set_track_level("combat", 2)
    u.set_track_level("work", 2)
    before = u.racial_xp
    u.set_track_level("magic", 3)
    assert u.racial_xp == before + 3


def test_a_magic_kill_banks_magic_xp_not_combat_xp():
    batt = Battle([Unit("player")], [Unit("enemy")])
    mage, foe = batt.units
    mage.credit_kill(foe, magic=True)
    assert mage.magic_xp_earned == progression.xp_award(0, foe.combat_level)
    assert mage.combat_xp_earned == 0


def test_absorbing_a_battle_banks_the_magic_xp():
    from gartok.guild import Guild
    p = Unit("player")
    guild = Guild([p])
    batt = Battle([p], [Unit("enemy")])
    mage, foe = batt.player_units[0], batt.enemy_units[0]
    mage.magic_xp_earned = 3
    foe.status, foe.hp = "dead", 0
    batt.winner = "player"
    out = campaign.absorb_battle(guild, [p], batt)
    assert p.magic_xp == 3 and out.xp_awards[p.name] == 3


def test_finishing_a_spell_study_banks_magic_xp():
    u = Unit("player")
    u.money = 50                     # the day's rent; a rolled purse can fall short of it
    u.add_magic_source("nature")
    u.give_to_pack("Scroll of Light Globe")
    magic.begin_study(u, "light_globe")
    u.study_progress = magic.points_to_learn(0)
    magic.progress_study(u)
    assert "light_globe" in u.spells_known
    assert u.magic_xp == magic.study_xp(magic.SPELLS["light_globe"])


def test_magic_xp_and_picks_survive_a_save():
    u = _mage(2, "arcane_mind", "spell_focus")
    back = Unit.from_save(persist.unit_to_dict(u))
    assert back.magic_xp == u.magic_xp and back.talents["magic"] == ["arcane_mind", "spell_focus"]


def test_a_save_without_a_magic_track_still_loads():
    d = persist.unit_to_dict(Unit("player"))
    del d["talents"]["magic"]
    del d["magic_xp"]
    assert Unit.from_save(d).talents["magic"] == []


def test_a_cone_is_one_three_and_five_cells_wide():
    east = cone_cells((5, 5), (1, 0), 3)
    assert sorted(east) == sorted([(6, 5), (7, 4), (7, 5), (7, 6),
                                   (8, 3), (8, 4), (8, 5), (8, 6), (8, 7)])
    diag = cone_cells((5, 5), (1, 1), 3)
    assert len(diag) == 9 and (6, 6) in diag and (8, 8) in diag and (6, 8) in diag


def _breath_battle(players, breather_pos=(5, 5)):
    breather = _dragon_breather()
    breather.size = "Medium"
    breather.footprint = 1
    batt = Battle([Unit("player") for _ in players], [breather])
    batt.board.walls.clear()
    for u, pos in zip(batt.player_units, players):
        u.pos = pos
    dragon = batt.enemy_units[0]
    dragon.pos, dragon.ap = breather_pos, 2
    return batt, dragon


def _join(batt, team, pos):
    c = Combatant(Unit(team), team)
    c.pos = pos
    batt.units.append(c)
    (batt.player_units if team == "player" else batt.enemy_units).append(c)
    return c


def test_dragon_breath_needs_the_talent():
    batt = Battle([Unit("player")], [Unit("enemy")])
    assert not actions.DRAGON_BREATH.available(batt, batt.enemy_units[0])
    batt, dragon = _breath_battle([(6, 5)])
    assert actions.DRAGON_BREATH.available(batt, dragon)


def test_one_roll_hits_everyone_in_the_cone_allies_too():
    batt, dragon = _breath_battle([(6, 5), (7, 4)])
    ally_c = _join(batt, "enemy", (8, 5))
    far = _join(batt, "player", (5, 9))
    for u in batt.units:
        u.hp = 30
    hp = {u: u.hp for u in batt.units}
    with patch("gartok.actions.combat.d20", return_value=20), \
            patch("gartok.actions.combat.roll", return_value=5) as dice:
        actions.DRAGON_BREATH.execute(batt, dragon, (6, 5))
    assert dragon.ap == 0
    assert dice.call_count == 3
    assert all(hp[u] - u.hp == max(0, 5 - u.dr) for u in (*batt.player_units[:2], ally_c))
    assert far.hp == hp[far]


def test_a_wall_shelters_whoever_stands_behind_it():
    batt, dragon = _breath_battle([(8, 5)])
    batt.board.walls.update({(6, 5), (7, 5), (7, 4), (7, 6)})
    assert batt.player_units[0] not in actions.DRAGON_BREATH.caught(batt, dragon, (6, 4))


def test_a_breath_kill_is_magic_xp():
    batt, dragon = _breath_battle([(6, 5)])
    victim = batt.player_units[0]
    victim.hp = 1
    with patch("gartok.actions.combat.d20", return_value=20):
        actions.DRAGON_BREATH.execute(batt, dragon, (6, 5))
    assert not victim.alive and dragon.kills == 1 and dragon.combat_xp_earned == 0


def test_the_ai_breathes_only_on_three_foes_or_more():
    batt, dragon = _breath_battle([(6, 5), (7, 4), (7, 6)])
    with patch("gartok.actions.combat.d20", return_value=1):
        assert ai._try_breath(batt, dragon)
    batt, dragon = _breath_battle([(6, 5), (7, 4)])
    assert not ai._try_breath(batt, dragon)


def test_the_ai_holds_its_breath_when_its_own_side_would_take_as_much():
    batt, dragon = _breath_battle([(6, 5), (7, 4), (7, 6)])
    for pos in ((8, 3), (8, 4), (8, 5)):
        _join(batt, "enemy", pos)
    assert not ai._try_breath(batt, dragon)


def test_the_ai_walks_to_where_next_turn_s_cone_catches_three_foes_and_stays():
    random.seed(0)
    batt, dragon = _breath_battle([(9, 4), (9, 5), (9, 6)], breather_pos=(3, 5))
    batt.ambient_light = True
    assert ai._best_cone(batt, dragon) == (None, 0)
    spot = ai._breath_spot(batt, dragon, ai._target(batt, dragon))
    assert spot is not None
    ai.take_turn(batt, dragon)
    assert dragon.pos == spot
    dragon.ap = 2                             # next turn
    assert ai._best_cone(batt, dragon)[1] == 3


def test_the_ai_does_not_reposition_with_a_cone_already_there_or_without_the_talent():
    batt, dragon = _breath_battle([(6, 5), (7, 4), (7, 6)])
    assert ai._breath_spot(batt, dragon, batt.player_units[0]) is None
    batt = Battle([Unit("player") for _ in range(3)], [Unit("enemy")])
    batt.board.walls.clear()
    for u, pos in zip(batt.player_units, ((9, 4), (9, 5), (9, 6))):
        u.pos = pos
    plain = batt.enemy_units[0]
    plain.pos, plain.ap = (3, 5), 2
    assert ai._breath_spot(batt, plain, batt.player_units[1]) is None


def test_a_breather_in_reach_of_its_foe_repositions_only_within_a_blow_of_it():
    random.seed(0)
    batt, dragon = _breath_battle([(6, 5), (7, 7), (8, 7)])
    target = batt.player_units[0]
    spot = ai._breath_spot(batt, dragon, target)
    assert spot is not None
    dragon.pos = spot
    assert batt.units_distance(dragon, target) <= dragon.attack_range
    assert ai._best_cone(batt, dragon)[1] == 3
