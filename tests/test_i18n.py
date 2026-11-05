"""The translation framework (i18n.py, the language setting) and the rule that every `pt-br` key has an `en` twin."""

import pytest

from gartok import i18n, settings
from gartok.web.settings_session import SettingsSession

# Phases 2-6 of docs/plans/translation_pt_br.md fill pt-br.json; while they are open an `en` key may lack its
# twin. Flip to True when the last phase lands.
STRICT = True


@pytest.fixture
def catalogs(monkeypatch):
    monkeypatch.setattr(i18n, "_cache", {
        "en": {"a.hello": "Hello {who}", "a.day.one": "{n} day", "a.day.other": "{n} days",
               "a.lines": ["one {x}", "two"], "name.item.sword": "Long Sword",
               "name.item.cloak": "Cloak"},
        "pt-br": {"a.hello": "Olá, {who}", "a.day.one": "{n} dia", "a.day.other": "{n} dias",
                  "name.item.sword": "Espada Longa", "name.item.sword.gender": "f"}})


def test_t_fills_placeholders_and_falls_back_to_en_then_the_key(catalogs):
    assert i18n.t("a.hello", who="Ana") == "Hello Ana"
    i18n.set_language("pt-br")
    assert i18n.t("a.hello", who="Ana") == "Olá, Ana"
    assert i18n.t("a.lines", x=3) == ["one 3", "two"], "a gap in pt-br shows the en text"
    assert i18n.t("a.nothing") == "a.nothing"


def test_plural_picks_one_or_other_in_each_language(catalogs):
    assert [i18n.plural("a.day", n) for n in (0, 1, 2)] == ["0 days", "1 day", "2 days"]
    i18n.set_language("pt-br")
    assert [i18n.plural("a.day", n) for n in (0, 1, 2)] == ["0 dias", "1 dia", "2 dias"]


def test_name_and_gender_come_from_the_catalog_and_fall_back_to_the_id(catalogs):
    assert i18n.name("item", "sword") == "Long Sword" and i18n.gender("item", "sword") == "m"
    i18n.set_language("pt-br")
    assert i18n.name("item", "sword") == "Espada Longa" and i18n.gender("item", "sword") == "f"
    assert i18n.name("item", "cloak") == "Cloak", "no pt-br entry: the en name"
    assert i18n.name("item", "unknown_thing") == "unknown_thing"


def test_a_language_the_game_does_not_know_is_refused():
    with pytest.raises(ValueError, match="no language"):
        i18n.set_language("xx")


def test_the_language_setting_offers_every_language_and_applies_on_choice(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PATH", str(tmp_path / "settings.json"))
    settings.reload()
    s = SettingsSession(lambda: {"screen": "title"})
    row = next(r for r in s.state()["rows"] if r["key"] == "language")
    assert [c["value"] for c in row["choices"]] == list(i18n.LANGUAGES)
    assert [c["label"] for c in row["choices"]] == ["English", "Português (Brasil)"]
    assert row["value"] == "en" and i18n.language() == "en"
    s.set("language", "pt-br")
    assert i18n.language() == "pt-br"
    settings.reload()
    assert settings.get("language") == "pt-br"
    settings.reload()


def test_every_catalog_key_has_its_en_twin_with_the_same_placeholders():
    en = i18n.catalog("en")
    for lang in i18n.LANGUAGES:
        if lang == "en":
            continue
        cat = i18n.catalog(lang)
        orphans = sorted(k for k in set(cat) - set(en) if not (k.endswith(".gender") and k[:-7] in en) and not (k.endswith(".f") and k[:-2] in en))
        assert not orphans, f"{lang} keys with no en twin: {orphans}"
        wrong = sorted(k for k, v in cat.items() if k in en and i18n.placeholders(v) != i18n.placeholders(en[k]))
        assert not wrong, f"{lang} keys whose placeholders differ from en: {wrong}"
        if STRICT:
            gaps = sorted(set(en) - set(cat))
            assert not gaps, f"{lang} lacks: {gaps}"


def test_a_battle_log_line_keeps_its_key_and_reads_again_in_another_language(catalogs):
    from gartok.battle import Battle
    from tests.helpers import _melee_battle
    batt = _melee_battle()[0]
    assert isinstance(batt, Battle)
    batt.log("a.hello", who=i18n.Ref("item", "sword", "Sword"))
    line = batt.log_lines[-1]
    assert line == "Hello Long Sword" and line.msg.to_json() == {"k": "a.hello", "p": {"who": {"ref": ["item", "sword", "Sword", False]}}}
    i18n.set_language("pt-br")
    assert i18n.from_json(line.msg.to_json()) == "Olá, Espada Longa", "the stored row reads in the language of the moment"
    batt.log("a plain literal that is no key")
    assert getattr(batt.log_lines[-1], "msg", None) is None


def test_every_key_the_code_asks_of_the_catalog_exists():
    import ast
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1] / "gartok"
    en = i18n.catalog("en")
    groups = {k.split(".")[0] for k in en} - {"ui", "tutorial", "credits", "arena_talk", "name"}
    prefixes = tuple(f"{g}." for g in groups)
    missing = []
    for path in root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith(prefixes) \
                    and " " not in node.value and "{" not in node.value and not node.value.endswith((".", ".json")):
                key = node.value
                if key not in en and f"{key}.one" not in en and not any(k.startswith(key + ".") for k in en):
                    missing.append(f"{path.name}: {key}")
    assert not missing, f"keys with no en text: {sorted(set(missing))}"


def test_a_ref_writes_its_article_by_gender_and_a_sentence_can_agree(monkeypatch):
    monkeypatch.setattr(i18n, "_cache", {
        "en": {"name.item.sword": "Long Sword", "name.item.axe": "Axe", "m.broke": "{item} broke"},
        "pt-br": {"name.item.sword": "Espada Longa", "name.item.sword.gender": "f", "name.item.axe": "Machado",
                  "m.broke": "{item:o} quebrou", "m.broken": "{item:o} está quebrado",
                  "m.broken.f": "{item:o} está quebrada"}})
    sword, axe = i18n.Ref("item", "sword"), i18n.Ref("item", "axe")
    assert f"{sword}" == "Long Sword"
    i18n.set_language("pt-br")
    assert f"{sword:do}" == "da Espada Longa" and f"{axe:no}" == "no Machado" and f"{sword:um}" == "uma Espada Longa"
    assert i18n.t("m.broken", item=sword) == "a Espada Longa está quebrada"
    assert i18n.t("m.broken", item=axe) == "o Machado está quebrado"
    assert str(i18n.Msg("m.broke", item=sword)) == "a Espada Longa quebrou"
    i18n.set_language("en")
    assert i18n.t("m.broke", item=sword) == "Long Sword broke"


def test_built_names_follow_the_language_word_order(monkeypatch):
    from gartok import items
    monkeypatch.setattr(i18n, "_cache", {})
    base = {"name.item.Dagger": "Adaga", "name.item.Dagger.gender": "f", "name.item.Dictionary": "Dicionário",
            "name.size.Large": "Grande", "name.spell.hex": "Maldição", "name.language.Elvish": "Élfico",
            "name.compose.size": "{base} {size}", "name.compose.scroll": "Pergaminho de {spell}",
            "name.compose.dictionary": "Dicionário de {language}", "name.compose.any": "Qualquer {base}"}
    built = items._composed_names(base)
    assert built["name.item.Large Dagger"] == "Adaga Grande" and built["name.item.Large Dagger.gender"] == "f"
    assert built["name.item.Scroll of Hex"] == "Pergaminho de Maldição"
    assert built["name.item.Dictionary of Elvish"] == "Dicionário de Élfico"
    assert built["name.item.Any Dictionary"] == "Qualquer Dicionário"
    assert "name.item.Huge Dagger" not in built, "a size the language has no word for yet shows the en name"


def test_the_en_built_names_are_the_old_english_names():
    assert i18n.name("item", "Large Dagger") == "Large Dagger" and i18n.name("item", "Scroll of Hex") == "Scroll of Hex"
    assert i18n.name("item", "Dictionary of Elvish") == "Dictionary of Elvish"
    assert i18n.name("item", "Any Dictionary") == "Any Dictionary"
