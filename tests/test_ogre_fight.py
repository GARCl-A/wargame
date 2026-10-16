"""The Ogre and the fight at his fortress: the race, Reach, Huge weapons and Giant's Grip, Mighty
Shove, fire on the board, the Water Jet spell, the fortress scenario and how the AI plays them."""

import random
from unittest.mock import patch

from gartok import ai, combat_lab, magic, npc_lib, progression, talents, wildfire
from gartok.fortress_scenario import BONFIRE, GATE, OGRE_CELL, FortressScenario, walls
from tests.helpers import Battle, Unit, abilities, actions, data, fixed_d20


def _ogre_unit():
    return npc_lib.load_npc(wildfire.OGRE_SLUG)


def _open(player_units, enemy_units):
    """A battle on an open board (no walls), positions to be set by the test."""
    random.seed(3)
    batt = Battle(player_units, enemy_units)
    batt.board.walls = set()
    batt.board.refresh_terrain()
    for u in batt.units:
        u.ap = 2
        u.hp_max = u.hp = 200                      # nobody drops before the test reads them
    return batt


def _stats(c, **scores):
    for k, v in scores.items():
        setattr(c.char, k, v)
    c.char._derive_combat()


# --- the race and the NPC --------------------------------------------------------- #

def test_the_ogre_is_a_large_d12_giant_with_reach_never_rolled_as_a_player():
    ogre = data.race_by_name("Ogre")
    assert ogre["size"] == "Large" and ogre["hd"] == 12 and ogre["mods"] == (4, -2, 2, -2, 2, -2)
    assert "Ogre" in data.ALL_RACE_NAMES and "Ogre" not in data.RACE_NAMES
    assert abilities.get(ogre["ability"]).melee_reach == 1


def test_the_authored_ogre_follows_the_racial_rule_and_holds_his_two_picks():
    u = _ogre_unit()
    assert u._racial_override is None
    assert (u.combat_level, u.work_level, u.racial_level) == (10, 10, 10)
    assert u.racial_level == progression.racial_level(u.racial_xp)
    assert u.talents["racial"] == ["giant_grip", "mighty_shove"]
    assert u.equipped_weapon == "Huge Club" and u.can_wield("Huge Club")
    assert u.equipped_armor == "Plate Armor" and not u.encumbered
    assert len(u._level_hp_rolls) == 10


def test_reach_lets_a_melee_swing_land_two_squares_off():
    batt = _open([Unit("player")], [_ogre_unit()])
    p, o = batt.units
    p.pos, o.pos = (2, 5), (5, 5)                  # the Ogre covers (5..6, 5..6): 3 squares off
    assert o.attack_range == 2
    assert not actions.ATTACK.can(batt, o, p)
    p.pos = (3, 5)                                 # two squares from his body
    assert actions.ATTACK.can(batt, o, p)
    assert ai._approach_reach(o) == 2


# --- Huge weapons and Giant's Grip ------------------------------------------------- #

def test_a_huge_weapon_steps_the_die_twice_and_needs_a_huge_hand():
    from gartok import items
    assert items.get("Huge Hammer").damage == items.step_damage_die(items.get("Large Hammer").damage)
    assert items.get("Huge Hammer").size == "Huge"
    goliath = Unit("player", race=data.race_by_name("Goliath"))
    centaur = Unit("player", race=data.race_by_name("Centaur"))
    ogre = Unit("enemy", race=data.race_by_name("Ogre"))
    assert not goliath.can_wield("Large Hammer")
    goliath.talents["racial"].append("giant_grip")
    assert goliath.can_wield("Large Hammer") and not goliath.can_wield("Huge Hammer")
    assert centaur.can_wield("Large Hammer") and not centaur.can_wield("Huge Hammer")
    assert ogre.can_wield("Large Hammer") and not ogre.can_wield("Huge Hammer")
    ogre.talents["racial"].append("giant_grip")
    assert ogre.can_wield("Huge Hammer")
    assert all(u.can_wield("Hammer") for u in (goliath, centaur, ogre))


def test_shared_racial_talents_are_offered_to_each_of_their_races():
    grip = talents.get("giant_grip")
    assert grip.races == ("Goliath", "Ogre") and grip.for_race("Ogre") and not grip.for_race("Elf")
    assert talents.get("intimidating_presence").for_race("Ogre")
    ogre_tree = {t.id for t in talents.racial_tree("Ogre")}
    assert ogre_tree == {"giant_grip", "intimidating_presence", "mighty_shove"}
    assert "mighty_shove" not in {t.id for t in talents.racial_tree("Goliath")}


# --- Mighty Shove ------------------------------------------------------------------ #

def _shove_battle():
    batt = _open([Unit("player"), Unit("player")], [_ogre_unit()])
    p, q, o = batt.units
    for c in (p, q, o):
        c._ability = abilities.get("none")
    o.pos, p.pos, q.pos = (2, 5), (4, 5), (14, 10)
    _stats(p, constitution=10)
    return batt, p, q, o


def test_mighty_shove_throws_three_squares_for_a_d6():
    batt, p, _, o = _shove_battle()
    hp = p.hp
    with fixed_d20(15), patch("gartok.actions.combat.roll", return_value=4):
        actions.PUSH.execute(batt, o, p)
    assert p.pos == (7, 5) and p.hp == hp - 4
    assert "Mighty Shove" in actions.PUSH.label(batt, o)


def test_a_wall_in_the_way_stops_the_throw_and_hits_again():
    batt, p, _, o = _shove_battle()
    batt.board.walls = {(6, 5)}
    hp = p.hp
    with fixed_d20(15), patch("gartok.actions.combat.roll", return_value=3):
        actions.PUSH.execute(batt, o, p)
    assert p.pos == (5, 5) and p.hp == hp - 6


def test_a_body_in_the_way_stops_the_throw_and_takes_the_blow_too():
    batt, p, q, o = _shove_battle()
    q.pos = (6, 5)
    hp_p, hp_q = p.hp, q.hp
    with fixed_d20(15), patch("gartok.actions.combat.roll", return_value=2):
        actions.PUSH.execute(batt, o, p)
    assert p.pos == (5, 5) and p.hp == hp_p - 4 and q.hp == hp_q - 2


def test_a_downed_body_stops_a_mighty_shove_but_not_a_plain_one():
    batt, p, q, o = _shove_battle()
    q.pos, q.status = (5, 5), "stable"
    with fixed_d20(15), patch("gartok.actions.combat.roll", return_value=1):
        actions.PUSH.execute(batt, o, p)
    assert p.pos == (4, 5)
    o.char.talents["racial"].remove("mighty_shove")
    o.ap = 2
    with fixed_d20(15):
        actions.PUSH.execute(batt, o, p)
    assert p.pos == (5, 5)


def test_a_plain_push_is_unchanged_one_square_and_no_damage():
    batt, p, _, o = _shove_battle()
    o.char.talents["racial"].remove("mighty_shove")
    hp = p.hp
    with fixed_d20(15):
        actions.PUSH.execute(batt, o, p)
    assert p.pos == (5, 5) and p.hp == hp
    batt.board.walls = {(6, 5)}
    o.ap = 2
    with fixed_d20(15):
        actions.PUSH.execute(batt, o, p)
    assert p.pos == (5, 5) and p.hp == hp


# --- fire on the board ------------------------------------------------------------- #

def test_starting_a_turn_in_the_flames_burns_two_d6_a_burning_cell():
    batt = _open([Unit("player")], [_ogre_unit()])
    p, o = batt.units
    p.pos, o.pos = (2, 2), (8, 8)
    batt.fire = {(8, 8), (9, 8), (8, 9), (9, 9)}
    with patch("gartok.data.roll", return_value=10) as roll:
        batt._apply_fire(o)
        batt._apply_fire(p)
    roll.assert_called_once_with(8, 6)                  # 4 cells under a Large body
    assert o.hp == 190


def test_walking_into_fire_burns_and_a_walk_goes_round_when_it_can():
    batt = _open([Unit("player")], [Unit("enemy")])
    p, e = batt.units
    p.pos, e.pos = (2, 5), (14, 10)
    batt.fire = {(3, 5)}
    hp = p.hp
    batt.move_unit(p, (4, 4))
    assert p.hp == hp and p.pos == (4, 4)               # the same cost round the flames
    p.ap, p.walking = 2, False
    batt.fire = {(5, y) for y in range(batt.board.rows)}
    with patch("gartok.data.roll", return_value=7):
        batt.move_unit(p, (6, 5))
    assert p.hp == hp - 7


def test_fire_spreads_onto_open_floor_and_lights_the_dark():
    from gartok import vision
    batt = _open([Unit("player")], [Unit("enemy")])
    batt.fire = {(5, 5)}
    batt.board.walls = {(4, 5), (6, 5), (5, 4)}
    batt.spread_fire(10, random.Random(1))
    assert batt.fire > {(5, 5)} and not batt.fire & batt.board.walls
    batt.ambient_light = False
    assert vision.cell_lit(batt, (5, 6))


def test_a_shove_into_the_flames_burns():
    batt, p, _, o = _shove_battle()
    batt.fire = {(6, 5)}
    hp = p.hp
    with fixed_d20(15), patch("gartok.actions.combat.roll", return_value=1), \
            patch("gartok.data.roll", return_value=9):
        actions.PUSH.execute(batt, o, p)
    assert p.pos == (7, 5) and p.hp == hp - 1 - 9


# --- the fortress --------------------------------------------------------------------- #

def test_the_fortress_puts_the_ogre_by_his_bonfire_and_falls_with_him():
    random.seed(4)
    squad = [Unit("player") for _ in range(4)]
    foes = wildfire.ogre_band(5)
    sc = FortressScenario(foes)
    batt = Battle(squad, foes, scenario=sc, aggressor="player")
    ogre = wildfire.ogre_of(batt)
    assert ogre.pos == OGRE_CELL and batt.fire == set(BONFIRE)
    assert len(batt.enemy_units) == 1 + wildfire.ESCORT
    assert all(u.race["name"] in ("Goblin", "Hobgoblin") for u in foes[1:])
    assert not any(c in batt.fire for u in batt.units for c in batt.cells_of(u))
    sc.on_round(batt)
    assert len(batt.fire) > len(BONFIRE)
    assert sc.win_check(batt) is None
    ogre.status = "dying"
    assert sc.win_check(batt) == "player"


def test_the_finished_fortress_is_whole_but_for_its_gate():
    built = walls(finished=True)
    assert not set(GATE) & built and (7, 6) in built and (12, 2) in built
    assert (12, 2) not in walls()


def test_the_camp_crew_is_three_goblins_and_a_foreman_a_step_over():
    random.seed(2)
    crew = wildfire.camp_crew(4)
    assert [u.race["name"] for u in crew] == ["Goblin"] * 3 + ["Hobgoblin"]
    assert crew[-1].mean_level == 5 and all(u.mean_level == 4 for u in crew[:3])


def test_the_lab_sets_up_both_wildfire_fights():
    b, _ = combat_lab.build("fortress", 4, 4, seed=1)
    assert wildfire.ogre_of(b) is not None and b.fire
    b, _ = combat_lab.build("camp", 4, 4, seed=1)
    assert len(b.enemy_units) == wildfire.CREW + 1


# --- the Water Jet ---------------------------------------------------------------------- #

def _jet_battle():
    batt = _open([Unit("player")], [Unit("enemy")])
    p, e = batt.units
    p._ability = e._ability = abilities.get("none")
    p.pos, e.pos = (2, 5), (5, 5)
    p.char.spells_known.append("water_jet")
    p.spells_known.append("water_jet") if p.spells_known is not p.char.spells_known else None
    return batt, p, e


def test_water_jet_is_natures_own_level_one_spell_with_a_scroll():
    spell = magic.SPELLS["water_jet"]
    assert spell.level == 1 and spell.sources == ("nature",)
    assert magic.spell_for_scroll(wildfire.REWARD) is spell
    assert actions.WaterJetAction.reach() == 6


def test_water_jet_hits_for_d6_plus_int_and_throws_the_target_back():
    batt, p, e = _jet_battle()
    jet = actions.CastSpellAction("water_jet")
    assert jet.can(batt, p, e)
    hp = e.hp
    with fixed_d20(20), patch("gartok.data.roll", return_value=3):
        jet.execute(batt, p, e)
    assert e.pos == (6, 5) and e.hp == hp - max(1, 3 + p.mod_intelligence)


def test_water_jet_cannot_throw_through_a_wall_and_misses_do_nothing():
    batt, p, e = _jet_battle()
    batt.board.walls = {(6, 5)}
    jet = actions.CastSpellAction("water_jet")
    with fixed_d20(20), patch("gartok.data.roll", return_value=3):
        jet.execute(batt, p, e)
    assert e.pos == (5, 5)
    p.ap, hp = 2, e.hp
    with fixed_d20(1):
        jet.execute(batt, p, e)
    assert e.hp == hp
    e.pos = (9, 5)
    assert not jet.can(batt, p, e)


# --- the AI ------------------------------------------------------------------------------ #

def test_the_ai_casts_water_jet_when_it_beats_its_hand():
    batt, p, e = _jet_battle()
    _stats(p, intelligence=18)
    p.char.equipped_weapon = None
    p.char._derive_combat()
    assert isinstance(ai._pick_attack(batt, p, e), actions.WaterJetAction)


def test_the_ogre_shoves_a_foe_against_a_wall_instead_of_swinging():
    batt, p, _, o = _shove_battle()
    _stats(p, constitution=3)
    batt.board.walls = {(5, 5)}
    assert ai._try_shove(batt, o)
    assert o.ap == 1


def test_anyone_shoves_a_foe_into_the_flames():
    batt = _open([Unit("player")], [Unit("enemy")])
    p, e = batt.units
    p._ability = e._ability = abilities.get("none")
    e.pos, p.pos = (2, 5), (3, 5)
    _stats(e, strength=18)
    _stats(p, constitution=3)
    assert not ai._try_shove(batt, e)
    batt.fire = {(4, 5)}
    assert ai._try_shove(batt, e)
    assert p.pos == (4, 5)


def test_the_ai_walks_out_of_the_fire_and_round_it():
    batt = _open([Unit("player")], [Unit("enemy")])
    p, e = batt.units
    p.pos, e.pos = (2, 5), (10, 5)
    batt.fire = {(9, 5), (10, 5), (11, 5), (9, 4), (9, 6), (10, 4), (10, 6), (11, 4), (11, 6)}
    assert ai._leave_fire(batt, e)
    assert not batt.burning_under(e)
    e.ap, e.walking = 2, False
    e.pos = (13, 5)
    dest = ai._step_toward(batt, e, p.pos, 1)
    assert dest not in batt.fire


def test_a_whole_fortress_fight_plays_to_the_end_under_the_ai():
    b, _ = combat_lab.build("fortress", 6, 6, seed=3)
    for _ in range(6000):
        if b.winner:
            break
        ai.take_turn(b, b.active)
    assert b.winner in ("player", "enemy")
