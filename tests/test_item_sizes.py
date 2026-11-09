"""Gear cut to the body: Tiny and Small variants beside the Medium and Large ones (items.py), who can wield and
wear what (unit_loadout.py), the kit a recruit starts with, and what the shops put on the shelf."""

import random
from itertools import pairwise

import pytest

from gartok import ai, archetypes, economy, i18n, items, starter_kit
from gartok.ground import GroundObject
from tests.helpers import Battle, Unit, data, fitted, standard_unit


def _of(race, **over):
    u = standard_unit()
    u.set_race(race)
    for k, v in over.items():
        setattr(u, k, v)
    u._derive_combat()
    return u


# --------------------------------------------------------------------------- #
# the registry                                                                 #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name,table", [
    ("Sword", {"Tiny": (9, 0.75, (1, 4)), "Small": (18, 1.5, (1, 6)), "Medium": (35, 3.0, (1, 8)), "Large": (70, 6.0, (1, 10))}),
    ("Dagger", {"Tiny": (2, 0.13, (1, 2)), "Small": (4, 0.25, (1, 3)), "Medium": (8, 0.5, (1, 4)), "Large": (16, 1.0, (1, 6))}),
])
def test_a_weapon_halves_or_doubles_its_weight_price_and_die_per_size(name, table):
    for size, (price, weight, die) in table.items():
        w = items.sized(name, size)
        assert (w.price, w.weight, w.damage, w.size) == (price, weight, die, size)


def test_every_weapon_comes_in_every_size_with_the_same_reach_and_traits():
    for plain in (d for d in items.weapons().values() if d.base is None):
        cuts = items.sizes_of(plain.name)
        assert [c.size for c in cuts] == ["Tiny", "Small", "Medium", "Large", "Huge"]
        assert all((c.range, c.reach, c.hands, c.traits) == (plain.range, plain.reach, plain.hands, plain.traits) for c in cuts)
        assert all(a.damage[1] <= b.damage[1] or a.damage[0] < b.damage[0] for a, b in pairwise(cuts))
        assert all(c.price >= 1 for c in cuts)


def test_armor_and_shields_change_weight_and_price_only():
    for plain in (d for d in (*items.armor().values(), *items.shields().values()) if d.base is None):
        cuts = items.sizes_of(plain.name)
        assert [c.size for c in cuts] == ["Tiny", "Small", "Medium", "Large"]
        assert {(c.ac, c.max_dex, c.speed_penalty, c.guard_bonus) for c in cuts} == {
            (plain.ac, plain.max_dex, plain.speed_penalty, plain.guard_bonus)}
        assert items.sized(plain.name, "Large").weight == plain.weight * 2
        assert items.sized(plain.name, "Large").price == plain.price * 2


def test_a_size_variant_belongs_to_its_plain_items_family():
    crossbow = items.get("Small Crossbow")
    assert (crossbow.family, crossbow.base_name) == ("crossbow", "Crossbow")
    assert items.get("Large Plate Armor").family == "plate_armor" and items.get("Sword").family == "sword"
    assert items.is_kind("Tiny Axe", "Axe") and not items.is_kind("Tiny Axe", "Pick")
    assert items.sized("Torch", "Small") is None


def test_the_names_read_in_portuguese_with_the_noun_s_gender():
    i18n.set_language("pt-br")
    try:
        assert i18n.name("item", "Small Dagger") == "Adaga Pequena"
        assert i18n.name("item", "Tiny Sword") == "Espada Minúscula"
        assert i18n.name("item", "Large Club") == "Clava Grande"
    finally:
        i18n.set_language("en")


# --------------------------------------------------------------------------- #
# who wields and wears what                                                    #
# --------------------------------------------------------------------------- #

def test_a_body_wields_its_own_size_or_smaller_and_giants_grip_one_more():
    goblin, human, centaur, goliath = _of("Goblin"), _of("Human"), _of("Centaur"), _of("Goliath")
    assert not goblin.can_wield("Sword") and goblin.can_wield("Small Sword") and goblin.can_wield("Tiny Sword")
    assert human.can_wield("Sword") and human.can_wield("Small Sword") and not human.can_wield("Large Sword")
    assert centaur.can_wield("Large Sword") and not centaur.can_wield("Huge Sword")
    assert not goliath.can_wield("Large Sword")
    goliath.talents["racial"].append("giant_grip")
    assert goliath.can_wield("Large Sword") and not goliath.can_wield("Huge Sword")


def test_armor_and_shields_fit_one_size_only():
    goblin, centaur = _of("Goblin"), _of("Centaur")
    assert goblin.fits_armor("Small Chainmail") and not goblin.fits_armor("Chainmail")
    assert not goblin.fits_armor("Tiny Chainmail")
    assert not centaur.fits_armor("Chainmail") and centaur.fits_armor("Large Chainmail")
    assert goblin.fits_offhand("Small Dwarf Shield") and not goblin.fits_offhand("Dwarf Shield")
    assert goblin.fits_offhand(items.TORCH_ITEM)


def test_a_unit_whose_kit_no_longer_fits_stows_it_in_the_pack():
    u = _of("Human")
    u.equipped_weapon, u.equipped_armor, u.equipped_offhand = "Sword", "Chainmail", "Dwarf Shield"
    u.set_race("Goblin")
    assert (u.equipped_weapon, u.equipped_armor, u.equipped_offhand) == (None, None, None)
    assert all(u.has_item(n) for n in ("Sword", "Chainmail", "Dwarf Shield"))
    kept = _of("Goblin", equipped_weapon="Small Sword", equipped_armor="Small Chainmail")
    assert (kept.equipped_weapon, kept.equipped_armor) == ("Small Sword", "Small Chainmail")


def test_a_small_unit_does_not_pick_up_a_fallen_medium_weapon_or_shield():
    batt = Battle([_of("Goblin")], [standard_unit("enemy")])
    goblin, human = batt.player_units[0], batt.enemy_units[0]
    for wielder in (goblin, human):
        wielder.disarm()
    from gartok.actions.base import _pickable
    assert not _pickable(goblin, GroundObject.weapon((0, 0), "Sword")) and _pickable(human, GroundObject.weapon((0, 0), "Sword"))
    assert _pickable(goblin, GroundObject.weapon((0, 0), "Small Sword"))
    assert not _pickable(goblin, GroundObject.shield((0, 0), "Dwarf Shield")) and _pickable(human, GroundObject.shield((0, 0), "Dwarf Shield"))
    assert not ai.movement._recover_shield(batt, goblin)


# --------------------------------------------------------------------------- #
# the starting kit and the RISKY warning                                       #
# --------------------------------------------------------------------------- #

def test_a_recruit_starts_with_gear_cut_for_its_body():
    random.seed(5)
    for race, size in (("Sprite", "Tiny"), ("Goblin", "Small"), ("Human", "Medium"), ("Centaur", "Large")):
        for _ in range(20):
            u = Unit("player", race=data.race_by_name(race))
            weapon = items.get(u.equipped_weapon)
            assert weapon.base_name in starter_kit.weapon_pool()
            assert weapon.size == (size if size != "Large" else "Medium")


def test_the_starting_kit_weighs_by_the_body_and_a_small_race_is_rarely_risky():
    kg = {size: archetypes.starter_kit_kg(size) for size in ("Tiny", "Small", "Medium", "Large")}
    assert kg["Tiny"] < kg["Small"] < kg["Medium"] < kg["Large"] and kg["Medium"] == 8.0
    sprite, human = _of("Sprite"), _of("Human")
    assert sprite.carry_normal < archetypes.starter_kit_kg("Medium")
    assert not any("starting kit" in r for r in archetypes.risks(sprite)) or sprite.carry_normal < kg["Tiny"]
    assert not any("starting kit" in r for r in archetypes.risks(human))


# --------------------------------------------------------------------------- #
# the shelves                                                                  #
# --------------------------------------------------------------------------- #

def test_a_town_shelf_keeps_tiny_small_and_medium_and_the_fortress_only_large():
    smith = economy.targets_of("smith")
    assert {"Tiny Sword", "Small Sword", "Sword"} <= set(smith) and "Large Sword" not in smith
    assert smith["Tiny Sword"] == smith["Small Sword"] == smith["Sword"]
    fortress = economy.targets_of("ogre_fortress")
    assert fortress and all(items.get(n).size == "Large" for n in fortress)
    assert {"Large Chainmail", "Large Club"} <= set(fortress)
    assert not any(items.get(n).size == "Large" for n in economy.MARKET_STOCK if items.get(n).size)


def test_a_small_axe_is_the_axe_that_lifts_a_worker_at_the_lumber_yard():
    goblin = _of("Goblin")
    assert not economy.owns_tool(goblin, "lumber_yard")
    goblin.give_to_pack("Small Axe")
    assert economy.owns_tool(goblin, "lumber_yard")


def test_a_shop_row_carries_its_family_and_size_for_the_toggle():
    from tests.test_web_hub import _hub
    hub, _, _ = _hub("smith", "forge")
    rows = [r for c in hub.state()["shop"]["shelf"] for r in c["rows"]]
    swords = [r for r in rows if r.get("base") == "Sword"]
    assert [r["size"] for r in swords] == ["Tiny", "Small", "Medium"]
    assert [r["name"] for r in swords] == ["Tiny Sword", "Small Sword", "Sword"]
    assert [r["price"] for r in swords] == [9, 18, 35]
    assert hub.state()["shop"]["size"] in data.SIZE_ORDER


def test_the_fitting_helper_cuts_a_name_for_a_body():
    assert fitted(_of("Goblin"), "Sword") == "Small Sword" and fitted(_of("Human"), "Sword") == "Sword"
    assert fitted(_of("Goblin"), "Torch") == "Torch"
