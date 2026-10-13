import pytest

from gartok import items, weapon_traits


def test_weapon_traits_registry():
    fin = weapon_traits.get("finesse")
    assert fin is not None
    assert fin.name == "Finesse"
    assert fin.finesse is True
    assert "Dexterity" in fin.desc

    thr = weapon_traits.get("thrown")
    assert thr is not None
    assert thr.name == "Thrown"
    assert thr.thrown is True

    assert weapon_traits.get("nonexistent") is None
    all_t = weapon_traits.all_traits()
    assert fin in all_t
    assert thr in all_t


def test_items_weapon_traits_integration():
    dagger = items.get("dagger")
    assert dagger is not None
    assert dagger.has_trait("finesse")
    assert dagger.has_trait("thrown")
    assert "finesse" in dagger.traits
    assert "thrown" in dagger.traits

    axe = items.get("axe")
    assert axe is not None
    assert not axe.has_trait("finesse")
    assert not axe.has_trait("thrown")
    assert len(axe.traits) == 0

    rapier = items.get("rapier")
    assert rapier is not None
    assert rapier.has_trait("finesse")
    assert not rapier.has_trait("thrown")


def test_describe_item_includes_traits():
    name, text = items.item_tooltip("Dagger")
    assert name == "Dagger"
    assert "Finesse:" in text
    assert "Thrown:" in text

    _, axe_text = items.item_tooltip("Axe")
    assert "Finesse:" not in axe_text
    assert "Thrown:" not in axe_text
