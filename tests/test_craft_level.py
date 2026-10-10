"""A recipe's level is worked out from its difficulty (craft_level), never set by hand."""

import dataclasses

import pytest

from gartok import craft_level, economy, items, progression
from gartok.unit import Unit


def _recipe(materials, complexity=5, target="Broadsword"):
    return items.CraftingRecipe(target=target, materials=materials, complexity=complexity,
                                station=items.CraftingStation.FORGE)


def test_the_levels_the_difficulty_works_out_for_every_recipe():
    levels = {name: r.level for name, r in items.CRAFTING_RECIPES.items()
              if not name.startswith("Dictionary of ") or name == "Dictionary of Ankarin"}
    assert levels == {
        "Jerky": 1, "Bear Trap": 1, "Alarm Trap": 2, "Dwarf Shield": 2, "Dictionary of Ankarin": 2,
        "Dwarf Axe": 3, "Dwarf Armor": 3, "Minor Healing Potion": 3, "Antidote": 3, "Signal Horn": 4,
    }


def test_the_level_is_a_property_nobody_can_set():
    recipe = items.CRAFTING_RECIPES["Jerky"]
    assert "level" not in {f.name for f in dataclasses.fields(recipe)}
    with pytest.raises(dataclasses.FrozenInstanceError):
        recipe.level = 9


def test_who_may_start_a_recipe_follows_the_talents():
    assert craft_level.breakdown(items.CRAFTING_RECIPES["Jerky"])["entry"] == "open"
    assert craft_level.entry_of("Bear Trap") == "talent"
    assert craft_level.entry_of("Dwarf Axe") == "race"
    assert craft_level.entry_of("Dictionary of Ankarin") == "open"


def test_scarce_reagents_raise_the_level(monkeypatch):
    monkeypatch.setattr(craft_level, "entry_of", lambda name: "open")
    plain = craft_level.level_of(_recipe(["Iron Bar"]))
    scarce = craft_level.level_of(_recipe(["Venom Gland", "Red Mushroom", "Iron Bar"]))
    assert scarce > plain


def test_a_longer_batch_raises_the_level(monkeypatch):
    monkeypatch.setattr(craft_level, "entry_of", lambda name: "open")
    quick = craft_level.level_of(_recipe(["Iron Bar"], complexity=5))
    slow = craft_level.level_of(_recipe(["Iron Bar"], complexity=80))
    assert slow > quick


def test_what_the_shops_stop_selling_freely_makes_a_reagent_scarce():
    assert economy.freely_buyable("Iron Bar") and economy.freely_buyable("Ink")
    assert not economy.freely_buyable("1sqm Hide")          # a finite count
    assert not economy.freely_buyable("Red Mushroom")       # no shop sells it
    assert craft_level.scarce_inputs(items.CRAFTING_RECIPES["Dictionary of Ankarin"]) == ["1sqm Hide"]


def test_the_level_scales_the_work_xp_of_a_worker_below_it():
    level = items.CRAFTING_RECIPES["Dwarf Axe"].level
    assert progression.work_xp_hours(10, level, 0) == 10 * (level + 1)
    assert progression.work_xp_hours(10, level, level + 1) == 0


def test_the_game_reads_the_level_where_a_shift_banks_its_xp():
    u = Unit("player")
    assert u.bank_work(4, items.CRAFTING_RECIPES["Antidote"].level)
    assert u.work_hours == 4 * (items.CRAFTING_RECIPES["Antidote"].level + 1)
