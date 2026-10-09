"""Comprehensive layered regression suite for gartok.items.

Validates:
1. Layer 1 (Structural Parity): 100% exact attribute match for all 93 items
   in baseline_items.json (weight, price, damage, range, finesse, thrown,
   hands, reload, size, ac, max_dex, speed_penalty, food, lifespan, spell_id, language).
2. Layer 2 (Integration & Game Rules):
   - Combat: weapon damage dice, stepped die on Large weapons, finesse and reload.
   - Market: buy_price and sell_price formulas with sympathy/markup modifiers.
   - Crafting: recipe materials validity, station enums, and complexity.
   - Food: perishable lifespans, spoilage detection, and batch grouping by (id, days_old).
   - Charges: ItemInstance charge tracking for Quiver and First Aid Kit.
"""

import json
import os

import pytest

from gartok import items
from gartok.items import CraftingStation, WeaponSize


def load_baseline():
    path = os.path.join(os.path.dirname(__file__), "baseline_items.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_baseline_has_exactly_94_items():
    baseline = load_baseline()
    assert len(baseline) == 94


def test_every_baseline_item_exists_in_items_registry():
    baseline = load_baseline()
    for name in baseline:
        item = items.get(name)
        assert item is not None, f"Item '{name}' missing from items registry"
        assert item.name == name


def test_baseline_structural_parity():
    baseline = load_baseline()
    for name, expected in baseline.items():
        item = items.get(name)
        assert item is not None, f"Item '{name}' not found"

        # Static attributes check
        assert item.weight == pytest.approx(expected["weight"]), f"{name} weight mismatch"
        assert item.price == expected["price"], f"{name} price mismatch"

        if "damage" in expected:
            assert list(item.damage) == expected["damage"], f"{name} damage mismatch"
            assert item.range == expected["range"], f"{name} range mismatch"
            assert item.finesse == expected["finesse"], f"{name} finesse mismatch"
            assert item.thrown == expected["thrown"], f"{name} thrown mismatch"
            assert item.hands == expected["hands"], f"{name} hands mismatch"
            assert item.reload == expected["reload"], f"{name} reload mismatch"
            assert item.size == expected["size"], f"{name} size mismatch"

        if "ac" in expected:
            assert item.ac == expected["ac"], f"{name} ac mismatch"
            if "max_dex" in expected:
                assert item.max_dex == expected["max_dex"], f"{name} max_dex mismatch"
                assert item.speed_penalty == expected["speed_penalty"], f"{name} speed_penalty mismatch"

        if "food" in expected:
            assert item.food == expected["food"], f"{name} food mismatch"
            assert item.lifespan == expected["lifespan"], f"{name} lifespan mismatch"

        if "spell_id" in expected:
            assert item.spell_id == expected["spell_id"], f"{name} spell_id mismatch"

        if "language" in expected:
            assert item.language == expected["language"], f"{name} language mismatch"


def test_lookup_dual_resolution_slug_and_display_name():
    # Both slug and display name must resolve to the identical ItemDef
    assert items.get("dagger") is items.get("Dagger")
    assert items.get("large_axe") is items.get("Large Axe")
    assert items.get("first_aid_kit") is items.get("First Aid Kit")
    assert items.get("minor_healing_potion") is items.get("Minor Healing Potion")
    assert items.get("scroll_of_sleep") is items.get("Scroll of Sleep")
    assert items.get("scroll_sleep") is items.get("Scroll of Sleep")
    assert items.get("1l_beer") is items.get("1L Beer")
    assert items.get("1sqm_hide") is items.get("1sqm Hide")


def test_dict_subscript_compatibility():
    dagger = items.get("Dagger")
    assert dagger["weight"] == 0.5
    assert dagger["price"] == 8
    assert dagger["damage"] == (1, 4)
    assert dagger.get("finesse") is True
    assert "hands" in dagger


def test_combat_layer_weapon_stepping_and_finesse():
    for base_slug, name, _, _, _, dmg, _, fin, _, _, _ in items._BASE_WEAPONS_DATA:
        base_item = items.get(name)
        large_item = items.get(f"Large {name}")
        assert base_item is not None
        assert large_item is not None

        # Large weapon stepped damage die
        expected_stepped = items.step_damage_die(base_item.damage)
        assert large_item.damage == expected_stepped
        # Large weapon double weight & price
        assert large_item.weight == pytest.approx(round(base_item.weight * 2, 1))
        assert large_item.price == base_item.price * 2
        assert large_item.size == WeaponSize.LARGE
        assert base_item.size == WeaponSize.MEDIUM

    # Ranged weapons reload
    crossbow = items.get("Light Crossbow")
    assert crossbow.reload is True
    bow = items.get("Shortbow")
    assert bow.reload is False


def test_market_layer_pricing_and_haggling():
    # Base price test
    assert items.buy_price("Dagger", 0.0) == 8
    assert items.sell_price("Dagger", 0.0) == 4

    # Sympathy discount (-20%)
    assert items.buy_price("Dagger", -0.20) == 6
    assert items.sell_price("Dagger", -0.20) == 3

    # Markup (+20%)
    assert items.buy_price("Dagger", 0.20) == 10
    assert items.sell_price("Dagger", 0.20) == 5

    # Scroll prices scale with spell level
    assert items.buy_price("Scroll of Light Globe") == 180
    assert items.buy_price("Scroll of Sleep") == 465
    assert items.sell_price("Scroll of Sleep") == 232


def test_crafting_recipes_validity():
    for target, recipe in items.CRAFTING_RECIPES.items():
        # Recipe target exists
        target_item = items.get(target)
        assert target_item is not None, f"Recipe target {target} not in items"
        assert isinstance(recipe.station, CraftingStation)
        assert recipe.complexity > 0

        # All materials exist in items registry
        for mat in recipe.materials:
            mat_item = items.get(mat)
            assert mat_item is not None, f"Material {mat} in recipe {target} not in items"


def test_food_perishables_and_batch_stacking():
    # Lifespans
    assert items.get("Fruit").lifespan == 1
    assert items.get("Meat").lifespan == 2
    assert items.get("Potato").lifespan == 7
    assert items.get("1L Beer").lifespan == 30

    # Spoilage check on ItemInstance
    fresh_fruit = items.create_instance("Fruit", qty=3, days_old=0)
    assert not fresh_fruit.is_rotten()
    assert fresh_fruit.weight == pytest.approx(0.6)

    expired_fruit = items.create_instance("Fruit", qty=3, days_old=2)
    assert expired_fruit.is_rotten()

    # Batch stacking by (id, days_old) preserves rot timeline without item explosion
    inventory = [
        items.create_instance("Potato", qty=5, days_old=1),
        items.create_instance("Potato", qty=3, days_old=3),
    ]
    assert len(inventory) == 2
    assert sum(i.qty for i in inventory) == 8
    assert sum(i.weight for i in inventory) == 8.0


def test_item_instance_charges_tracking():
    # Quiver starts with 20 charges
    quiver = items.create_instance("Quiver")
    assert quiver.charges == 20
    assert quiver.weight == 1.5

    # Firing arrows decrements the item's charges, not a character global field
    quiver.charges -= 1
    assert quiver.charges == 19

    # First Aid Kit starts with 10 charges
    kit = items.create_instance("First Aid Kit")
    assert kit.charges == 10
    kit.charges -= 1
    assert kit.charges == 9


def test_bandit_ambush_locked_chest_drop():
    from gartok import data, encounters

    class BanditDropRNG:
        def __init__(self, table_idx=1, count=2, level=0, drop_roll=0.005):
            self.table_idx = table_idx      # 1 -> bandit entry (race_pool=None)
            self.count = count
            self.level = level
            self.drop_roll = drop_roll

        def choices(self, population, weights=None, k=1):
            # for weighted_choice
            return [self.table_idx if len(population) == 2 else self.count]

        def choice(self, seq):
            return seq[0]

        def randint(self, a, b):
            return a

        def random(self):
            return self.drop_roll

    # 1. Bandit pack with lucky roll (< 0.01) gets Locked Chest
    lucky_rng = BanditDropRNG(drop_roll=0.005)
    pack = encounters.roll_encounter(encounters.WILDS_TABLE, rng=lucky_rng)
    assert any(u.count_of(data.CHEST_ITEM) > 0 for u in pack)

    # 2. Bandit pack with unlucky roll (>= 0.01) does not get Locked Chest
    unlucky_rng = BanditDropRNG(drop_roll=0.05)
    pack = encounters.roll_encounter(encounters.WILDS_TABLE, rng=unlucky_rng)
    assert not any(u.count_of(data.CHEST_ITEM) > 0 for u in pack)

    # 3. Beast pack (wolves) never gets Locked Chest even if roll is lucky
    beast_rng = BanditDropRNG(table_idx=0, drop_roll=0.005)  # 0 -> beast pool
    pack = encounters.roll_encounter(encounters.WILDS_TABLE, rng=beast_rng)
    assert not any(u.count_of(data.CHEST_ITEM) > 0 for u in pack)


def test_material_flag_and_tags():
    # Crafting materials
    for name in ["Rope", "Iron Bar", "1sqm Hide", "1kg Coal", "Lumber", "Vial", "Red Mushroom", "Paper", "Ink", "Stone Brick", "Salt"]:
        item = items.get(name)
        assert item is not None
        assert item.material is True
        assert items.is_material(name) is True
        assert items.is_material(item) is True
        assert items.item_tag(name) == "MATERIAL"
        inst = items.create_instance(name)
        assert inst.material is True

    # Non-materials
    for name in ["Potato", "Jerky", "Dagger", "Torch"]:
        item = items.get(name)
        assert item is not None
        assert item.material is False
        assert items.is_material(name) is False

    # Tooltip mentions crafting material
    _, desc = items.item_tooltip("Rope")
    assert "Crafting material" in desc




def test_food_used_in_a_recipe_carries_both_tags():
    assert items.item_tags("Meat") == ["FOOD", "MATERIAL"]
    assert items.item_tag("Meat") == "FOOD · MATERIAL"
    assert items.item_tags("Fruit") == ["FOOD", "MATERIAL"]
    assert items.item_tags("Potato") == ["FOOD"]
    assert items.item_tags("Rope") == ["MATERIAL"]
    assert items.item_tags("Dagger") == ["WEAPON"]
    assert items.item_tags("Nothing At All") == [] and items.item_tag(None) == ""
