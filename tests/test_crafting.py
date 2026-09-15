"""Test crafting progression and resolution."""

import random
import gartok.unit as _unit_mod
from gartok.unit import Unit
from gartok.guild import Guild
from gartok import data


def test_crafting_requires_recipe():
    u = Unit("player")
    prog, is_done = u.progress_crafting()
    assert prog == 0
    assert not is_done


def test_crafting_progress():
    random.seed(42)
    u = Unit("player")
    u.recipes.append("Bear Trap")
    u.crafting_target = "Bear Trap"

    saved = _unit_mod.roll
    _unit_mod.roll = lambda n, d: 10
    try:
        prog, is_done = u.progress_crafting()
        assert prog == max(1, 10 + u.mod_intelligence)
        assert u.crafting_progress == prog
    finally:
        _unit_mod.roll = saved


def test_crafting_completion():
    random.seed(42)
    u = Unit("player")
    u.recipes.append("Bear Trap")
    u.crafting_target = "Bear Trap"
    u.crafting_progress = 9999

    prog, is_done = u.progress_crafting()
    assert is_done
    assert "Bear Trap" in u._base_inventory
    assert u.crafting_target is None
    assert u.crafting_progress == 0


def test_crafting_shift_consumes_materials_and_progresses():
    random.seed(42)
    u = Unit("player")
    guild = Guild(roster=[u], node="city")
    u.recipes.append("Bear Trap")
    u._base_inventory.append("Iron Bar")

    notices, _ = guild.crafting_shift(u, "Bear Trap", hours=1)
    assert u.crafting_target == "Bear Trap"
    assert "Iron Bar" not in u._base_inventory

    saved = _unit_mod.roll
    _unit_mod.roll = lambda n, d: 9999
    try:
        notices, _ = guild.crafting_shift(u, "Bear Trap", hours=1)
        assert any("finished crafting" in n for n in notices)
        assert u.crafting_target is None
    finally:
        _unit_mod.roll = saved


def test_crafting_shift_missing_materials():
    random.seed(42)
    u = Unit("player")
    guild = Guild(roster=[u], node="city")
    u.recipes.append("Bear Trap")

    notices, _ = guild.crafting_shift(u, "Bear Trap", hours=1)
    assert any("missing materials" in n for n in notices)
    assert u.crafting_target is None
