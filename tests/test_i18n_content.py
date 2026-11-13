"""Phase 5 of the translation: authored content (missions, deeds, objectives, keepers, node text, NPC backstories)
lives in the catalog, and every record has its `en` entry."""

import glob
import json
import os

from gartok import (
    factions,
    i18n,
    missions,
    node_functions,
    npc_lib,
    objectives,
    persist,
    world,
)
from gartok.unit import Unit
from gartok.web import sheet_view

EN = i18n.catalog("en")


def test_every_authored_record_has_its_en_text():
    for t in missions.TEMPLATES.values():
        assert f"name.mission.{t.id}" in EN and f"desc.mission.{t.id}" in EN, t.id
    for d in factions.DEEDS.values():
        assert f"name.deed.{d.id}" in EN and f"desc.deed.{d.id}" in EN, d.id
    for f in factions.FACTIONS.values():
        assert f"desc.faction.{f.id}" in EN, f.id
    for o in objectives.OBJECTIVES:
        assert f"name.objective.{o.id}" in EN and f"desc.objective.{o.id}" in EN, o.id
    for fn in node_functions.FUNCTIONS.values():
        assert (fn.label is None) == (fn.id in ("work", "trust", "farmer", "innkeeper")), fn.id
    for n in world.NODES:
        assert f"desc.node.{n.id}" in EN, n.id
        for v in n.vendors.values():
            assert f"desc.vendor.{v.key}" in EN and f"name.role.{v.role}" in EN, v.name


def test_the_unlocks_read_their_text_from_the_catalog():
    for fid in factions.FACTIONS:
        for u in factions.get_unlocks(fid):
            assert f"factions.unlock.{u.id}.title" in EN and not u.title.startswith("factions."), u.id


def _in_language(monkeypatch, entries):
    """Play as a language `xx` whose catalog is `entries` (the `en` fallback fills the rest)."""
    monkeypatch.setattr(i18n, "_cache", {**i18n._cache, "xx": entries})
    monkeypatch.setitem(i18n.LANGUAGES, "xx", "xx")
    monkeypatch.setattr(i18n, "_lang", "xx")


def test_a_keepers_role_is_shown_through_the_catalog(monkeypatch):
    _in_language(monkeypatch, {"name.role.banker": "banqueira"})
    elysia = next(v for n in world.NODES for v in n.vendors.values() if v.name == "Elysia")
    assert elysia.caption.endswith("banqueira")


def test_an_npc_backstory_has_one_english_source_the_npc_file():
    with open(os.path.join(i18n.LOCALES_DIR, "en.json"), encoding="utf-8") as fh:
        copies = json.load(fh).get("desc", {}).get("npc", {})
    assert not copies, "the en backstory is the file's bio, not a copy in en.json"
    for path in glob.glob(os.path.join(npc_lib.NPC_DIR, "*.json")):
        slug = os.path.basename(path)[:-5]
        with open(path, encoding="utf-8") as fh:
            bio = json.load(fh).get("bio", "")
        assert i18n.catalog("en").get(f"desc.npc.{slug}", "") == bio, slug


def test_every_keeper_line_in_the_catalog_belongs_to_a_keeper():
    """A keeper's line is keyed by the slug of their name: renaming a keeper in `world.py` would leave the
    line behind (and the keeper without one), so the keys and the keepers must be the same set."""
    keepers = {v.key for n in world.NODES for v in n.vendors.values()}
    keyed = {k.split(".", 2)[2] for k in EN if k.startswith("desc.vendor.")}
    assert keyed == keepers, (sorted(keyed - keepers), sorted(keepers - keyed))
    roles = {v.role for n in world.NODES for v in n.vendors.values()}
    assert roles <= {k.split(".", 2)[2] for k in EN if k.startswith("name.role.")}


def test_a_recruited_npc_keeps_the_catalog_backstory_through_a_save(monkeypatch):
    adelio = npc_lib.load_npc("adelio-small-knife")
    back = Unit.from_save(persist.unit_to_dict(adelio))
    assert back.bio_slug == "adelio-small-knife"
    _in_language(monkeypatch, {"desc.npc.adelio-small-knife": "Um batedor de carteiras."})
    assert sheet_view.bio(back) == "Um batedor de carteiras."


def test_an_npc_name_follows_the_language_but_the_save_keeps_the_file_name(monkeypatch):
    adelio = npc_lib.load_npc("adelio-small-knife")
    _in_language(monkeypatch, {"name.npc.adelio-small-knife": "Adelio Facadinha"})
    assert adelio.name == "Adelio Facadinha"
    saved = persist.unit_to_dict(adelio)
    assert saved["name"] == "Adelio Small-Knife", "the save holds the file's name, not the shown one"
    monkeypatch.setattr(i18n, "_lang", "en")
    assert Unit.from_save(saved).name == "Adelio Small-Knife"


def test_a_renamed_npc_shows_the_typed_name(monkeypatch):
    adelio = npc_lib.load_npc("adelio-small-knife")
    adelio.name = "Bob"
    _in_language(monkeypatch, {"name.npc.adelio-small-knife": "Adelio Facadinha"})
    assert adelio.name == "Bob"


def test_every_authored_npc_has_its_english_name_in_the_catalog():
    en = i18n.catalog("en")
    for path in glob.glob(os.path.join(npc_lib.NPC_DIR, "*.json")):
        slug = os.path.basename(path)[:-5]
        assert en.get(f"name.npc.{slug}"), slug


class _FirstPick:
    def random(self):
        return 0

    def choice(self, options):
        return options[0]


def test_the_recruit_checks_read_the_npc_not_the_shown_name(monkeypatch):
    from gartok import arena
    from tests.helpers import standard_unit
    adelio = npc_lib.load_npc(arena.CHAMPION_SLUG)
    guild = type("G", (), {"roster": [adelio]})()
    _in_language(monkeypatch, {"name.npc.adelio-small-knife": "Adelio Facadinha"})
    assert arena.cameo_enemy(guild) is None
    guild.roster = [standard_unit()]
    assert arena.ribbit_cameo_enemy(guild, rng=_FirstPick()) is not None


def test_a_pack_beast_is_named_from_its_epithet_in_the_language_of_the_moment(monkeypatch):
    from gartok import data, encounters, names
    from gartok.battle import Battle
    from tests.helpers import standard_unit
    spider = next(r for r in data.BEAST_POOL if r["name"] == "Wolf")
    pack = [encounters.build_enemy(1, race_pool=[spider]) for _ in range(2)]
    battle = Battle([standard_unit()], pack)
    first = battle.enemy_units[0].char
    assert first.epithet in names.EPITHETS and first.name == f"{first.epithet} Wolf"
    _in_language(monkeypatch, {"name.race.Wolf": "Loba", "name.race.Wolf.gender": "f",
                               f"name.epithet.{first.epithet}": "Velho", f"name.epithet_f.{first.epithet}": "Velha",
                               "name.compose.beast": "{species} {epithet}"})
    assert first.name == "Loba Velha"
    saved = persist.unit_to_dict(first)
    assert saved["name"] == "Wolf" and saved["epithet"] == first.epithet
    monkeypatch.setattr(i18n, "_lang", "en")
    assert Unit.from_save(saved).name == f"{first.epithet} Wolf"


def test_the_pt_br_npc_names_show_and_a_feminine_one_carries_its_gender():
    i18n.set_language("pt-br")
    try:
        assert npc_lib.load_npc("adelio-small-knife").name == "Adelio Facadinha"
        assert npc_lib.load_npc("snake_dragon").name == "A Dragobra"
        assert i18n.gender("npc", "snake_dragon") == "f" and i18n.gender("npc", "ogre") == "m"
    finally:
        i18n.set_language("en")
