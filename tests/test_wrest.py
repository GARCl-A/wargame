"""Wrest: the 2 AP action of bare hands. Seize the weapon of an armed foe, then strike with it."""

from gartok import ai, data
from tests.helpers import Battle, Unit, actions, fixed_d20, standard_unit


def _scene(foe_weapon="Broadsword", foe_strength=10, bare="player"):
    """A bare-handed fighter (the `bare` side) next to an armed foe, two points to spend."""
    batt = Battle([standard_unit("player")], [standard_unit("enemy")])
    p, e = (batt.player_units[0], batt.enemy_units[0]) if bare == "player" \
        else (batt.enemy_units[0], batt.player_units[0])
    batt.board.walls = set()
    batt.board.elevation = {}
    batt.ambient_light = True
    p.disarm()
    e.equip_weapon(foe_weapon)
    e.char.strength = foe_strength
    e.char._derive_combat()
    p.pos, e.pos = (5, 5), (6, 5)
    p.ap = 2
    e.hp = e.char.hp_max = 40
    return batt, p, e


def test_a_pass_takes_the_weapon_and_strikes_with_it_at_once():
    batt, p, e = _scene()
    hp = e.hp
    with fixed_d20(20):
        actions.WREST.execute(batt, p, e)
    assert p.armed and p.weapon_name == "Broadsword"
    assert e.unarmed and e.weapon.name == "Unarmed"
    assert p.ap == 0
    assert e.hp < hp


def test_a_fail_costs_the_points_and_nothing_else():
    batt, p, e = _scene()
    hp = e.hp
    with fixed_d20(1):
        actions.WREST.execute(batt, p, e)
    assert p.unarmed and e.armed and e.weapon_name == "Broadsword"
    assert p.ap == 0 and e.hp == hp


def test_the_dc_is_15_plus_the_foes_strength():
    batt, p, e = _scene(foe_strength=18)
    assert actions.WREST.dc(e) == 15 + e.mod_strength
    p.char.dexterity = 10
    p.char._derive_combat()
    need = actions.WREST.dc(e) - p.mod_dexterity
    with fixed_d20(need - 1):
        actions.WREST.execute(batt, p, e)
    assert e.armed
    batt, p, e = _scene(foe_strength=18)
    with fixed_d20(actions.WREST.dc(e) - p.mod_dexterity):
        actions.WREST.execute(batt, p, e)
    assert p.armed


def test_it_is_the_action_of_bare_hands_only():
    batt, p, e = _scene()
    assert actions.WREST.applicable(batt, p)[0]
    p.equip_weapon("Dagger")
    assert not actions.WREST.applicable(batt, p)[0]
    wolf = Battle([standard_unit()], [Unit("enemy", race=data.race_by_name("Wolf"))]).enemy_units[0]
    assert not actions.WREST.applicable(batt, wolf)[0]


def test_it_needs_an_armed_foe_in_reach_that_the_actor_can_wield():
    batt, p, e = _scene()
    assert actions.WREST.can(batt, p, e)
    e.disarm()
    assert not actions.WREST.can(batt, p, e)
    batt, p, e = _scene()
    e.pos = (9, 5)
    assert not actions.WREST.can(batt, p, e)


def test_a_two_handed_weapon_needs_both_hands_free():
    batt, p, e = _scene(foe_weapon="Longbow")
    assert actions.WREST.can(batt, p, e)
    p.torch_hand = True
    assert not actions.WREST.can(batt, p, e)


def test_a_weapon_that_cannot_be_wielded_stays_put():
    batt, p, e = _scene()
    p.char.can_wield = lambda name: False
    assert not actions.WREST.can(batt, p, e)


def test_the_ai_wrests_a_strong_weapon_off_a_weak_hand():
    batt, p, e = _scene(foe_weapon="Dwarf Axe", foe_strength=6, bare="enemy")
    p.char.dexterity = 18
    p.char._derive_combat()
    assert ai.attack._pick_attack(batt, p, e) is actions.WREST
    with fixed_d20(15):
        actions.WREST.execute(batt, p, e)
    assert p.armed and p.weapon_name == "Dwarf Axe"


def test_a_bare_handed_ai_turn_ends_with_the_foes_weapon_in_its_hand():
    from gartok.conditions import Demoralized
    batt, p, e = _scene(foe_weapon="Dwarf Axe", foe_strength=6, bare="enemy")
    p.char.dexterity = 18
    p.char._derive_combat()
    e.add_condition(Demoralized())
    with fixed_d20(15):
        ai.take_turn(batt, p)
    assert p.armed and p.weapon_name == "Dwarf Axe" and e.unarmed


def test_the_ai_does_not_wrest_what_a_plain_blow_beats():
    batt, p, e = _scene(foe_weapon="Dagger", foe_strength=20)
    assert ai.reckon._wrest_worth(batt, p, e) < ai._two_points(batt, p, e)
    assert ai.attack._pick_attack(batt, p, e) is actions.ATTACK
