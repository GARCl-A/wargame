"""The Demon Cult's authored NPCs (`scripts/make_cult_npcs.py`): the levels the design fixes, the
Demon's race and its Holy Symbol drop."""

import pytest

from gartok import data, items, loot, npc_lib

SLUGS = ("cult-leader", "cult-fighter-1", "cult-fighter-2", "cult-channeler-blood",
         "cult-channeler-nature", "cult-channeler-faith", "farmers-daughter", "the-demon")


@pytest.mark.parametrize("slug,level", [("cult-leader", 10), ("cult-fighter-1", 7), ("cult-fighter-2", 7),
                                        ("cult-channeler-blood", 7), ("cult-channeler-nature", 7),
                                        ("cult-channeler-faith", 7), ("the-demon", 22)])
def test_racial_levels_follow_the_design(slug, level):
    assert npc_lib.load_npc(slug).racial_level == level


def test_every_npc_loads():
    for slug in SLUGS:
        assert npc_lib.load_npc(slug).hp_max > 0


def test_channelers_cast_from_different_schools():
    schools = {tuple(npc_lib.load_npc(s).magic_sources) for s in SLUGS if "channeler" in s}
    assert schools == {("blood",), ("nature",), ("faith",)}
    assert all(npc_lib.load_npc(s).spells_known for s in SLUGS if "channeler" in s)


def test_leader_is_a_caster_and_fighters_are_not():
    assert npc_lib.load_npc("cult-leader").magic_sources
    assert not any(npc_lib.load_npc(s).spells_known for s in ("cult-fighter-1", "cult-fighter-2"))
    assert npc_lib.load_npc("cult-fighter-1").weapon.name != npc_lib.load_npc("cult-fighter-2").weapon.name


def test_demon_is_the_strongest_body_in_the_game():
    demon = npc_lib.load_npc("the-demon")
    dragon_hp = 227
    assert demon.hp_max > dragon_hp and demon.race["kind"] == "demon"


def test_demon_race_is_placed_by_hand_not_drawn():
    assert "Demon" in data.ALL_RACE_NAMES and "Demon" not in data.RACE_NAMES
    assert all(r["name"] != "Demon" for r in data.BEAST_POOL + data.WILD_POOL + data.RACE_POOL)


def test_demon_drops_the_holy_symbol():
    assert items.HOLY_SYMBOL_ITEM in loot.UNIQUE_DROPS["the-demon"]
