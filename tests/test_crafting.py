"""Test crafting progression and resolution."""

import random

import gartok.unit_loadout as _unit_mod
from gartok import data, items
from gartok.guild import Guild
from gartok.unit import Unit


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
    assert u.has_item("Bear Trap")
    assert u.crafting_target is None
    assert u.crafting_progress == 0


def test_crafting_shift_consumes_materials_and_progresses():
    random.seed(42)
    u = Unit("player")
    guild = Guild(roster=[u], node="city")
    u.recipes.append("Bear Trap")
    u.give_to_pack("Iron Bar")

    notices, _ = guild.crafting_shift(u, "Bear Trap", hours=1)
    assert u.crafting_target == "Bear Trap"
    assert not u.has_item("Iron Bar")

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


def test_crafter_talent_boosts_progress_roll():
    random.seed(42)
    u = Unit("player")
    u.set_track_level("work", 1)
    assert u.choose_talent("work", "crafter")

    u.recipes.append("Bear Trap")
    u.crafting_target = "Bear Trap"

    saved = _unit_mod.roll
    _unit_mod.roll = lambda n, d: 10
    try:
        prog, _ = u.progress_crafting()
        # 10 + INT + 1 (crafter)
        assert prog == max(1, 10 + u.mod_intelligence + 1)
    finally:
        _unit_mod.roll = saved


def test_apothecary_talent_learns_potion_and_mastery():
    u = Unit("player")
    u.set_track_level("work", 2)
    assert u.choose_talent("work", "crafter")
    assert not any(r in u.recipes for r in items.APOTHECARY_RECIPES)

    assert u.choose_talent("work", "apothecary")
    learned = [r for r in items.APOTHECARY_RECIPES if r in u.recipes]
    assert len(learned) == 1
    assert u.craft_bonuses.get("apothecary", 0) == 0

    # Another unit that already knows all apothecary recipes
    u2 = Unit("player")
    u2.set_track_level("work", 2)
    u2.recipes.extend(items.APOTHECARY_RECIPES)
    assert u2.choose_talent("work", "crafter")
    assert u2.choose_talent("work", "apothecary")
    assert u2.craft_bonuses.get("apothecary") == 1

    u2.crafting_target = "Minor Healing Potion"
    saved = _unit_mod.roll
    _unit_mod.roll = lambda n, d: 10
    try:
        prog, _ = u2.progress_crafting()
        # 10 + INT + 1 (crafter) + 1 (apothecary mastery)
        assert prog == max(1, 10 + u2.mod_intelligence + 2)
    finally:
        _unit_mod.roll = saved


def test_blacksmith_talent_learns_forge_recipe_and_mastery():
    u = Unit("player")
    u.set_track_level("work", 2)
    assert u.choose_talent("work", "crafter")
    assert u.choose_talent("work", "blacksmith")
    assert any(r in u.recipes for r in data.BLACKSMITH_RECIPES)

    # Unit that already knows all blacksmith recipes (e.g. Kobold trapper)
    u2 = Unit("player")
    u2.set_track_level("work", 2)
    for r in data.BLACKSMITH_RECIPES:
        u2.recipes.append(r)
    assert u2.choose_talent("work", "crafter")
    assert u2.choose_talent("work", "blacksmith")
    assert u2.craft_bonuses.get("forge") == 1


def test_crafting_shift_awards_work_xp():
    u = Unit("player")
    guild = Guild(roster=[u], node="city")
    u.recipes.append("Minor Healing Potion")
    for mat in data.CRAFTING_RECIPES["Minor Healing Potion"]["materials"]:
        u.give_to_pack(mat)

    assert u.work_hours == 0
    assert u.work_level == 0
    t0 = guild.clock.seconds
    guild.crafting_shift(u, "Minor Healing Potion", hours=16)
    spent = (guild.clock.seconds - t0) / 3600
    assert u.work_hours == spent and 0 < spent <= 16


def test_crafting_screen_station_filtering():
    import os

    import pygame
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.font.init()
    from gartok.crafting_screen import CraftingScreen
    from gartok.group import Group

    u1 = Unit("player")
    u1.recipes.append("Minor Healing Potion")
    u2 = Unit("player")
    u2.recipes.append("Bear Trap")

    group = Group([u1, u2], node="city")
    guild = Guild(roster=[u1, u2], node="city")

    # Apothecary screen should only pick up u1 as crafter
    apoth_screen = CraftingScreen(None, guild, group, on_done=lambda: None, station="apothecary")
    assert u1 in apoth_screen.crafters
    assert u2 not in apoth_screen.crafters

    # Forge screen should only pick up u2 as crafter
    forge_screen = CraftingScreen(None, guild, group, on_done=lambda: None, station="forge")
    assert u2 in forge_screen.crafters
    assert u1 not in forge_screen.crafters
