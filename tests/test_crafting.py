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
    level = items.CRAFTING_RECIPES["Minor Healing Potion"].level
    assert u.work_hours == spent * (level + 1) and 0 < spent <= 16    # a level 0 worker gains x(level + 1)


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


def test_the_forge_card_shows_each_recipes_level_and_what_it_teaches(monkeypatch):
    import pygame

    import gartok.crafting_screen as mod
    pygame.init()
    u = Unit("player")
    u.recipes.append("Bear Trap")
    guild = Guild(roster=[u], node="city")
    shown, real_caps = [], mod.caps

    def recording_caps(surf, font, s, pos, color, **kw):
        shown.append(s)
        return real_caps(surf, font, s, pos, color, **kw)

    monkeypatch.setattr(mod, "caps", recording_caps)
    mod.CraftingScreen(None, guild, guild.group_of(u), on_done=lambda: None,
                       station="forge").draw(pygame.Surface((1280, 720)))
    level = items.CRAFTING_RECIPES["Bear Trap"].level
    assert any(f"LEVEL {level}" in s and f"x{level + 1} work XP" in s for s in shown)


def _pair():
    a, b = Unit("player"), Unit("player")
    for u in (a, b):
        u.inventory = []
    guild = Guild(roster=[a, b], node="city")
    a.recipes.append("Bear Trap")
    return guild, a, b


def test_a_craft_draws_on_the_whole_groups_packs():
    guild, a, b = _pair()
    b.give_to_pack("Iron Bar")
    notices, _ = guild.crafting_shift(a, "Bear Trap", 1, pool=guild.roster)
    assert a.crafting_target == "Bear Trap"
    assert not b.has_item("Iron Bar")


def test_a_craft_takes_the_crafters_own_materials_first():
    guild, a, b = _pair()
    a.give_to_pack("Iron Bar")
    b.give_to_pack("Iron Bar")
    guild.crafting_shift(a, "Bear Trap", 1, pool=guild.roster)
    assert not a.has_item("Iron Bar") and b.count_of("Iron Bar") == 1


def test_a_craft_splits_a_batch_across_packs_and_stays_atomic():
    guild, a, b = _pair()
    a.recipes.append("Dwarf Axe")
    mats = items.CRAFTING_RECIPES["Dwarf Axe"]["materials"]
    for i, m in enumerate(mats):
        (a, b)[i % 2].give_to_pack(m)
    guild.crafting_shift(a, "Dwarf Axe", 1, pool=guild.roster)
    assert a.crafting_target == "Dwarf Axe"
    assert sum(u.count_of(m) for u in (a, b) for m in mats) == 0

    c, d = Unit("player"), Unit("player")
    c.inventory, d.inventory = [], []
    c.recipes.append("Dwarf Axe")
    c.give_to_pack(mats[0])
    d.give_to_pack(mats[1])
    Guild(roster=[c, d], node="city").crafting_shift(c, "Dwarf Axe", 1, pool=[c, d])
    assert c.crafting_target is None and c.has_item(mats[0]) and d.has_item(mats[1])


def test_a_craft_without_the_pool_ignores_other_packs():
    guild, a, b = _pair()
    b.give_to_pack("Iron Bar")
    notices, _ = guild.crafting_shift(a, "Bear Trap", 1)
    assert "missing materials" in notices[0] and b.has_item("Iron Bar")


def test_a_padlocked_item_is_never_used_in_a_craft():
    guild, a, b = _pair()
    a.give_to_pack("Iron Bar")
    a.toggle_lock("Iron Bar")
    b.give_to_pack("Iron Bar")
    b.toggle_lock("Iron Bar")
    notices, _ = guild.crafting_shift(a, "Bear Trap", 1, pool=guild.roster)
    assert "missing materials" in notices[0]
    assert a.count_of("Iron Bar") == 1 and b.count_of("Iron Bar") == 1


def test_a_partly_locked_stack_gives_only_the_free_part():
    guild, a, b = _pair()
    a.give_to_pack("Iron Bar", 2)
    a.locked_items["Iron Bar"] = 1
    guild.crafting_shift(a, "Bear Trap", 1, pool=[a])
    assert a.count_of("Iron Bar") == 1 and a.locked_of("Iron Bar") == 1


def test_the_crafting_screen_counts_the_groups_materials():
    from gartok.crafting_screen import CraftingScreen
    guild, a, b = _pair()
    group = guild.group_of(a)
    screen = CraftingScreen(None, guild, group, on_done=lambda: None, station="forge")
    assert screen._get_missing_materials("Bear Trap")
    b.give_to_pack("Iron Bar")
    assert not screen._get_missing_materials("Bear Trap")
    b.toggle_lock("Iron Bar")
    assert screen._get_missing_materials("Bear Trap")


def _toolbox_recipe(monkeypatch, tools=("Chisel",)):
    monkeypatch.setitem(items.CRAFTING_RECIPES, "Carved Thing", items.CraftingRecipe(
        target="Bear Trap", materials=["Iron Bar"], complexity=10,
        station=items.CraftingStation.FORGE, tools=tools))


def test_missing_tools_lists_what_no_pack_holds(monkeypatch):
    _toolbox_recipe(monkeypatch, ("Chisel", "Rope"))
    a, b = Unit("player"), Unit("player")
    recipe = items.CRAFTING_RECIPES["Carved Thing"]
    assert items.missing_tools(recipe, [a, b]) == ["Chisel", "Rope"]
    b.give_to_pack("Chisel")
    assert items.missing_tools(recipe, [a, b]) == ["Rope"]
    assert items.missing_tools(items.CRAFTING_RECIPES["Bear Trap"], [a]) == []


def test_craft_refused_without_the_tool_and_materials_untouched(monkeypatch):
    _toolbox_recipe(monkeypatch)
    u = Unit("player")
    guild = Guild(roster=[u], node="city")
    u.recipes.append("Carved Thing")
    u.give_to_pack("Iron Bar")

    notices, _ = guild.crafting_shift(u, "Carved Thing", hours=1)
    assert any("needs a Chisel" in n for n in notices)
    assert u.has_item("Iron Bar") and u.crafting_target is None


def test_tool_in_another_pack_of_the_group_is_enough_and_is_kept(monkeypatch):
    _toolbox_recipe(monkeypatch)
    crafter, mate = Unit("player"), Unit("player")
    guild = Guild(roster=[crafter, mate], node="city")
    crafter.recipes.append("Carved Thing")
    crafter.give_to_pack("Iron Bar")
    mate.give_to_pack("Chisel")

    guild.crafting_shift(crafter, "Carved Thing", hours=1, pool=[crafter, mate])
    assert crafter.crafting_target == "Carved Thing"
    assert not crafter.has_item("Iron Bar")
    assert mate.has_item("Chisel")


def test_a_craft_in_progress_stops_when_the_tool_is_gone(monkeypatch):
    _toolbox_recipe(monkeypatch)
    u = Unit("player")
    guild = Guild(roster=[u], node="city")
    u.recipes.append("Carved Thing")
    u.crafting_target = "Carved Thing"

    notices, _ = guild.crafting_shift(u, "Carved Thing", hours=1)
    assert any("needs a Chisel" in n for n in notices)
    assert u.crafting_progress == 0
