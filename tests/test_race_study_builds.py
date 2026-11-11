"""The race study's builds: each holds every talent it lists (a talent whose prerequisite is missing would be replaced by a
random one without a word), the Duelist keeps its hand free, the Fortress buys the armour first."""

import random

import pytest

from gartok import items, outfit
from scripts import race_study as rs
from scripts import race_study_builds as rb

LISTED = [(b, None) for b in rb.BUILD_IDS if rb.lookup(b).role != "caster"] + [
    (b, name) for b, variants in rb.VARIANTS.items() for name in variants]
CASTERS = [b for b in rb.BUILD_IDS if rb.lookup(b).role == "caster"]


def _unit(build, race="Human", level=5, over=None, seed=1):
    return rb.make_unit("player", race, build, level, random.Random(seed), over=over)


@pytest.mark.parametrize("build,variant", LISTED)
def test_a_build_holds_every_talent_it_lists(build, variant):
    combat = rb.VARIANTS[build][variant] if variant else rb.BUILDS[build].combat
    unit, notes = _unit(build, over={"combat": combat} if variant else None)
    assert not [n for n in notes if n.startswith("talent")], notes
    assert set(combat) <= set(unit.talents["combat"])


@pytest.mark.parametrize("build", CASTERS)
def test_a_caster_holds_its_talents_and_its_spells(build):
    unit, notes = _unit(build)
    spec = rb.BUILDS[build]
    assert not [n for n in notes if n.startswith("talent")], notes
    assert set(spec.combat) <= set(unit.talents["combat"])
    assert set(spec.magic_talents) <= set(unit.talents["magic"])
    assert set(spec.spells5) <= set(unit.spells_known)


@pytest.mark.parametrize("build", rb.BUILD_IDS)
def test_the_work_roots_are_held(build):
    unit, _ = _unit(build)
    assert set(rb.BUILDS[build].work) <= set(unit.talents["work"])


def _squad(build, race="Human", over=None):
    return rs._squad("player", race, build, 5, random.Random(2), fixed=False, drop=False, over=over)[0]


@pytest.mark.parametrize("build", ("rapier_duelist", "dagger_skirmisher"))
def test_a_squad_of_duelists_has_one_torch_bearer_and_two_free_hands(build):
    over = {"combat": next(v for v in rb.VARIANTS[build].values() if "duelist" in v)}
    squad = _squad(build, over=over)
    assert [u.equipped_offhand for u in squad].count(items.TORCH_ITEM) == 1
    assert [u.equipped_offhand for u in squad].count(None) == 2


def test_a_squad_that_sees_in_the_dark_carries_no_torch():
    assert all(u.equipped_offhand is None for u in _squad("rapier_duelist", "Dwarf"))


def test_a_squad_of_two_handers_has_one_torch_bearer_with_a_one_handed_weapon():
    squad = _squad("broadsword")
    bearers = [u for u in squad if u.equipped_offhand == items.TORCH_ITEM]
    assert len(bearers) == 1 and items.get(bearers[0].equipped_weapon).hands == 1
    assert all(items.get(u.equipped_weapon).hands == 2 for u in squad if u not in bearers)


def test_a_forced_racial_talent_is_the_one_the_unit_takes():
    for race in ("Dwarf", "Orc", "Human"):
        for tid in rb.racial_options(race):
            unit, _ = _unit("sword_board", race, over={"racial": tid})
            assert unit.talents["racial"] == [tid]


def test_a_dropped_racial_talent_leaves_none():
    unit, _ = _unit("sword_board", "Orc", over={"drop_racial": True})
    assert unit.talents["racial"] == []


def test_the_fortress_buys_the_armour_before_the_weapon():
    unit, notes = _unit("fortress", level=0)
    assert unit.equipped_armor and unit.equipped_weapon is None and "unarmed" in notes


def test_the_fortress_with_more_copper_gets_a_weapon_after_the_shield():
    unit, _ = _unit("fortress")
    assert unit.equipped_armor and unit.equipped_offhand == rb.SHIELD and unit.equipped_weapon == "Hammer"


def test_each_body_takes_the_weapon_and_the_armor_cut_for_it():
    assert _unit("sword_board", "Goliath")[0].equipped_weapon == "Large Sword"
    assert _unit("sword_board", "Human")[0].equipped_weapon == "Sword"
    assert _unit("sword_board", "Goblin")[0].equipped_weapon == "Small Sword"
    assert _unit("sword_board", "Sprite")[0].equipped_weapon == "Tiny Sword"
    centaur = _unit("sword_board", "Centaur", level=5)[0]
    assert centaur.equipped_weapon == "Large Sword" and items.get(centaur.equipped_armor).size == "Large"


def test_a_two_handed_weapon_gives_the_fortress_shield_back():
    unit, notes = _unit("fortress", over={"weapon": "Broadsword"})
    assert unit.equipped_offhand is None and "shield given back" in notes


def test_a_level_0_caster_is_only_fielded_by_a_race_that_starts_with_magic():
    assert rb.fields("nature_caster", "Gnome", 0) and not rb.fields("nature_caster", "Human", 0)
    assert not any(rb.fields(b, r[1], 0) for b in ("blood_caster", "faith_caster") for r in rs.data.RACES)


def test_a_small_race_fields_every_weapon_in_its_own_size():
    assert rb.fields("glaive", "Sprite", 5)
    unit, notes = _unit("glaive", "Sprite")
    assert unit.equipped_weapon == "Tiny Glaive" and "unarmed" not in notes


def test_every_sweep_weapon_is_a_real_affordable_item():
    for build in (*rb.SWEEP_BUILDS, "thrower"):
        for weapon in rb.sweep_weapons(build, 5):
            assert items.is_weapon(weapon) and rb.affordable(weapon, 5)
    assert all(items.get(w).has_trait("thrown") for w in rb.sweep_weapons("thrower", 5))
    assert outfit.budget(5) > outfit.budget(0)


def test_the_analyst_wields_a_rapier_when_dex_beats_str_and_a_sword_otherwise():
    seen = set()
    for seed in range(40):
        unit, notes = _unit("analyst", seed=seed)
        want = "Rapier" if unit.dexterity > unit.strength else "Sword"
        assert unit.equipped_weapon.startswith(want)
        assert bool(unit.equipped_offhand) == ("no shield" not in notes)
        seen.add(want)
    assert seen == {"Rapier", "Sword"}


def test_an_explicit_weapon_overrides_the_analysts_attribute_rule():
    unit, _ = _unit("analyst", over={"weapon": "Hammer"})
    assert unit.equipped_weapon.startswith("Hammer")
