"""The catalog text (docs/plans/translation_pt_br.md, phase 4): a registry's shown name and description are read from
`name.<kind>.<id>` / `desc.<kind>.<id>` when asked, never cached, and no rule reads a shown name as an id."""

import pytest

from gartok import (
    abilities,
    archetypes,
    data,
    factions,
    i18n,
    items,
    magic,
    poisons,
    talents,
    vocations,
    weapon_traits,
    world,
)
from tests.test_web_first_days import (
    test_a_hunt_in_the_wilds_comes_home_or_ends_on_the_title as hunt_days,
)
from tests.test_web_first_days import (
    test_a_new_guild_lives_its_first_ten_days_in_the_browser as first_days,
)


@pytest.fixture
def pseudo(monkeypatch):
    """A `pt-br` where every catalog name and description is altered, items, races, nodes, sizes and alignments
    included: whatever breaks under it read a shown name as an id."""
    en = i18n.catalog("en")
    cat = {k: ("~" + v if isinstance(v, str) else ["~" + x for x in v]) for k, v in en.items()
           if k.startswith(("name.", "desc."))}
    kinds = {"item": list(items.all_items()), "race": data.ALL_RACE_NAMES, "size": data.SIZE_ORDER,
             "alignment": [a for _, a in data.ALIGNMENTS], "node": [n.id for n in world.NODES]}
    for kind, ids in kinds.items():
        for ident in ids:
            cat[f"name.{kind}.{ident}"] = "~" + ident
    cats = dict(i18n._cache)
    cats["pt-br"] = cat
    monkeypatch.setattr(i18n, "_cache", cats)
    i18n.set_language("pt-br")


def test_a_registry_name_and_description_follow_the_language(monkeypatch):
    monkeypatch.setattr(i18n, "_cache", {
        **i18n._cache,
        "pt-br": {"name.talent.strong": "Forte", "desc.talent.strong": "+1 Força.",
                  "name.ability.darkvision": "Visão no Escuro",
                  "desc.ability.darkvision": "enxerga {darkvision} quadrados no escuro.",
                  "name.trait.finesse": "Acuidade", "desc.trait.finesse": "Usa Destreza.",
                  "name.faction.arena": "Os Fossos"}})
    assert talents.get("strong").name == "Strong" and talents.get("strong").desc == "Strong: +1 Strength."
    i18n.set_language("pt-br")
    assert talents.get("strong").desc == "Forte: +1 Força."
    assert abilities.get("darkvision").effect == f"enxerga {data.DARKVISION} quadrados no escuro."
    assert weapon_traits.get("finesse").name == "Acuidade"
    assert factions.faction("arena").name == "Os Fossos"
    assert abilities.get(("darkvision", "climber")).name == "Visão no Escuro, Climber", "a gap shows the en text"


def test_an_item_tooltip_reads_its_name_and_lines_from_the_catalog(monkeypatch):
    monkeypatch.setattr(i18n, "_cache", {
        **i18n._cache,
        "pt-br": {"name.item.Dagger": "Adaga", "item.tip.weight": "Peso: {kg} kg."}})
    i18n.set_language("pt-br")
    title, text = items.item_tooltip("Dagger")
    assert title == "Adaga" and text.endswith(f"Peso: {items.get('Dagger').weight:g} kg.")


def test_every_registry_entry_has_its_en_name_and_description():
    en = i18n.catalog("en")
    for t in talents.TALENTS.values():
        assert f"name.talent.{t.id}" in en and f"desc.talent.{t.id}" in en, t.id
    for a in abilities.ABILITIES.values():
        assert f"name.ability.{a.id}" in en and f"desc.ability.{a.id}" in en, a.id
    for t in weapon_traits.TRAITS.values():
        assert f"name.trait.{t.id}" in en and f"desc.trait.{t.id}" in en, t.id
    for f in factions.FACTIONS.values():
        assert f"name.faction.{f.id}" in en, f.id
    for s in magic.SPELLS.values():
        assert f"name.spell.{s.id}" in en, s.id
    for p in poisons.POISONS.values():
        assert f"name.poison.{p.id}" in en, p.id
    for v in vocations.VOCATIONS.values():
        assert f"name.vocation.{v.id}" in en and f"desc.vocation.{v.id}" in en and f"desc.vocation_motto.{v.id}" in en, v.id
    for a in archetypes.ARCHETYPES.values():
        assert f"desc.archetype.{a.key}" in en, a.key


def test_the_altered_names_reach_the_screens_the_log_and_the_registries(pseudo, monkeypatch):
    import json
    import sys

    from gartok import vocations
    from gartok.actions.base import item_ref
    from gartok.web.server import Game
    monkeypatch.setitem(sys.modules, "pygame", None)
    assert i18n.language() == "pt-br"
    assert talents.get("strong").name == "~Strong" and magic.SPELLS["sleep"].name == "~Sleep"
    assert str(item_ref("Dagger")) == "~Dagger" and items.item_tooltip("Dagger")[0] == "~Dagger"
    game = Game.title()
    game.session.new_guild()
    game.session.choose_vocation(vocations.CARAVAN)
    assert "~Caravan" in json.dumps(game.session.state())
    assert i18n.language() == "pt-br", "booting a session leaves the language alone"


def test_the_game_plays_its_first_days_when_every_shown_name_is_altered(pseudo, monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "pygame", None)
    first_days()
    hunt_days()
    assert i18n.language() == "pt-br"


def test_a_scroll_is_still_the_scroll_of_its_spell_whatever_the_language_names_it(pseudo):
    spell = magic.SPELLS["sleep"]
    assert spell.name == "~Sleep" and spell.scroll_name == "Scroll of Sleep"
    assert magic.spell_for_scroll("Scroll of Sleep") is spell
    assert magic.study_item_name("sleep") == "Scroll of Sleep"
