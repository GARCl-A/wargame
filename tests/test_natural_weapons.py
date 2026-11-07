"""The body as a weapon: Unarmed and the beasts' natural weapons, one variant per body size."""

from gartok import data, intel, items, natural_weapons
from gartok.ground import GroundObject
from tests.helpers import Battle, Unit, _melee_battle, actions, standard_unit


def test_every_beast_names_its_weapon():
    for beast in data.BEASTS:
        assert beast[1] in natural_weapons.RACE_WEAPON, beast[1]


def test_every_named_weapon_exists_at_every_size():
    for name in natural_weapons.RACE_WEAPON.values():
        for size in data.SIZE_ORDER:
            assert natural_weapons.get(name, size) is not None


def test_dice_follow_the_size_ladder():
    ladder = {"Tiny": (1, 2), "Small": (1, 2), "Medium": (1, 3), "Large": (1, 4), "Huge": (1, 6)}
    for size, die in ladder.items():
        assert natural_weapons.get("Unarmed", size).damage == die
        assert natural_weapons.get("Bite", size).damage == die


def test_a_wolf_bites_and_a_large_wolf_has_a_large_bite():
    wolf = Unit("enemy", race=data.race_by_name("Wolf"))
    assert (wolf.natural_weapon.name, wolf.natural_weapon.damage) == ("Bite", (1, 3))
    wolf.talents["racial"].append("dire_growth")
    wolf._derive_combat()
    assert wolf.size == "Large"
    assert (wolf.natural_weapon.name, wolf.natural_weapon.damage) == ("Bite", (1, 4))


def test_natural_weapons_stay_out_of_the_item_registry():
    for name in natural_weapons.NAMES:
        assert items.get(name) is None
        assert name not in items.weapons()


def test_a_humanoid_fights_with_unarmed_at_its_size():
    u = standard_unit()
    assert u.natural_weapon.name == "Unarmed"
    assert u.natural_weapon.size == u.size


def test_a_humanoid_with_a_weapon_is_armed_and_without_one_unarmed():
    batt, _, fighter = _melee_battle()
    fighter.equip_weapon("Broadsword")
    assert fighter.armed and not fighter.unarmed and not fighter.natural
    fighter.disarm()
    assert fighter.unarmed and not fighter.armed and not fighter.natural
    assert fighter.weapon.name == "Unarmed"


def test_a_beast_is_natural_never_unarmed():
    wolf = Unit("enemy", race=data.race_by_name("Wolf"))
    batt = Battle([standard_unit()], [wolf])
    cw = batt.enemy_units[0]
    assert cw.natural and not cw.unarmed and not cw.armed
    assert cw.weapon.name == "Bite"
    assert actions.ATTACK.label(batt, cw) == "Bite"
    assert not cw.weapon.has_trait("cleave")


def test_only_bare_hands_pick_up_a_weapon():
    batt, _, fighter = _melee_battle()
    fighter.equip_weapon("Broadsword")
    obj = GroundObject.weapon((0, 0), "Dagger")
    assert not actions.base._pickable(fighter, obj)
    fighter.disarm()
    assert actions.base._pickable(fighter, obj)
    wolf = Battle([standard_unit()], [Unit("enemy", race=data.race_by_name("Wolf"))]).enemy_units[0]
    assert not actions.base._pickable(wolf, obj)


def test_a_talent_grants_a_trait_to_the_body_weapon_only():
    dragon = Unit("player", race=data.race_by_name("Dragon"))
    assert not dragon.natural_weapon.has_trait("cleave")
    dragon.talents["racial"] += ["dragon", "sweeping_claws"]
    assert dragon.natural_weapon.has_trait("cleave")
    skeleton = standard_unit()
    skeleton.talents["racial"].append("deft_bones")
    assert skeleton.natural_weapon.is_finesse
    assert not items.get("Dagger").has_trait("cleave")


def test_a_crossbow_swung_empty_hits_with_the_body_die():
    batt, _, fighter = _melee_battle()
    fighter.equip_weapon("Crossbow")
    fighter.ammo = 0
    assert fighter.improvised
    assert fighter.hand_die == fighter.char.natural_weapon.damage


def test_a_foe_shows_the_name_of_its_natural_weapon():
    wolf = Unit("enemy", race=data.race_by_name("Wolf"))
    batt = Battle([standard_unit()], [wolf])
    known = intel.known_fields(batt, "player", batt.enemy_units[0])
    assert known.visible["weapon"] == "Bite" and known.visible["weapon_action"] is None
