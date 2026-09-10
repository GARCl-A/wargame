"""REFERENCE.md stays regenerated from the registries."""

from tests.helpers import abilities, data, talents


def test_reference_doc_is_regenerated_from_the_registries():
    from gartok import reference
    assert reference.is_current(), (
        "REFERENCE.md is stale -- run `python -m gartok.reference` and commit it")


def test_every_race_ability_and_starting_gear_is_a_real_catalog_entry():
    for name in data.RACE_NAMES:
        race = data.race_by_name(name)
        assert race["ability"] in abilities.ABILITIES, (name, race["ability"])
        assert race["size"] in data.SIZES
        assert race["language"] in data.LANGUAGES
    for _thr, _name, weapon, item in data.OCCUPATIONS:
        assert weapon in data.WEAPONS, weapon
        assert data.item_weight(item) > 0, item


def test_every_talent_requires_a_talent_that_exists():
    for t in talents.TALENTS.values():
        assert t.track in talents.TRACKS
        assert t.requires is None or t.requires in talents.TALENTS, t.id
