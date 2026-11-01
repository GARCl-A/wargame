"""The body as a weapon: Unarmed and the beasts' natural weapons, one variant per body size."""

from gartok import data, natural_weapons
from tests.helpers import Unit, standard_unit


def test_every_beast_names_its_weapon():
    for beast in data.BEASTS:
        assert beast[1] in natural_weapons.RACE_WEAPON, beast[1]


def test_every_named_weapon_exists_at_every_size():
    for name in natural_weapons.RACE_WEAPON.values():
        for size in data.SIZE_ORDER:
            assert natural_weapons.get(name, size) is not None


def test_dice_follow_the_unarmed_ladder():
    for size, die in data.UNARMED_ATTACK.items():
        assert natural_weapons.get("Unarmed", size).damage == die
        assert natural_weapons.get("Bite", size).damage == die


def test_a_wolf_bites_and_a_large_wolf_has_a_large_bite():
    wolf = Unit("enemy", race=data.race_by_name("Wolf"))
    assert (wolf.natural_weapon.name, wolf.natural_weapon.damage) == ("Bite", (1, 3))
    wolf.talents["racial"].append("dire_growth")
    wolf._derive_combat()
    assert wolf.size == "Large"
    assert (wolf.natural_weapon.name, wolf.natural_weapon.damage) == ("Bite", (1, 4))
    assert wolf.natural_weapon.damage == wolf.unarmed_damage


def test_natural_weapons_stay_out_of_the_item_registry():
    from gartok import items
    for name in natural_weapons.NAMES:
        assert items.get(name) is None
        assert name not in items.weapons()


def test_a_humanoid_fights_with_unarmed_at_its_size():
    u = standard_unit()
    assert u.natural_weapon.name == "Unarmed"
    assert u.natural_weapon.size == u.size
