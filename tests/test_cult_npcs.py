"""The Demon Cult's authored NPCs (`scripts/make_cult_npcs.py`): the levels the design fixes, the
Demon's race and its Holy Symbol drop."""

import pytest

from gartok import data, loot, npc_lib

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


def test_the_symbol_is_the_girls_not_the_demons():
    assert "the-demon" not in loot.UNIQUE_DROPS


def test_the_demon_is_a_huge_bare_clawed_intimidator():
    demon = npc_lib.load_npc("the-demon")
    assert demon.size == "Huge" and demon.race["hd"] == 10
    assert demon.equipped_weapon is None and demon.weapon.name == "Claws"
    assert set(demon.spells_known) == {"hex", "dragonfire"}
    assert {"menacing", "cull_the_broken", "merciless", "dread_voice"} <= set(demon.talents["combat"])
    assert {"demon_claws", "rending_claws", "infernal_visage"} <= set(demon.talents["racial"])


def test_claws_talent_is_for_the_demon_only():
    from gartok import talents
    assert talents.get("demon_claws").for_race("Demon") and not talents.get("demon_claws").for_race("Human")


def test_the_casters_know_their_schools_spells():
    leader = npc_lib.load_npc("cult-leader")
    assert {"blood", "faith"} <= set(leader.magic_sources) and "healing_touch" in leader.spells_known
    assert "dragonfire" in npc_lib.load_npc("cult-channeler-blood").spells_known
    assert "water_jet" in npc_lib.load_npc("cult-channeler-nature").spells_known


def test_no_one_wears_a_worse_armor_than_they_can_carry():
    for slug in ("cult-channeler-blood", "cult-channeler-nature", "cult-channeler-faith"):
        assert npc_lib.load_npc(slug).equipped_armor is not None
