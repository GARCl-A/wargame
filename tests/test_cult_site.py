"""The Demon Cult's site (`cult_site.py`): the hidden node that joins the map only once found, the Country
Roads search that finds it, and its place in the save."""

import pytest

from gartok import campaign, cult_site, investigation, map_view, missions, persist, world
from gartok.group import Group
from gartok.guild import Guild
from gartok.web.map_session import MapSession
from tests.helpers import fixed_d20, standard_unit

JOB = missions.FARMER_DAUGHTER.id


@pytest.fixture(autouse=True)
def clean_world():
    world.clear_runtime()
    yield
    world.clear_runtime()


def _guild(node="country_roads", job=True, wis=0):
    u = standard_unit()
    u.mod_wisdom = wis
    guild = Guild([u])
    guild.groups = [Group([u], node)]
    if job:
        guild.missions.append(missions.Mission(JOB, u.uid, guild.clock.day, guild.clock.day + 20))
    return guild


def test_the_site_is_off_the_map_until_found():
    guild = _guild()
    cult_site.sync_world(guild)
    assert not world.exists(cult_site.NODE)
    assert cult_site.NODE not in {n.id for n in world.known(guild)}


def test_finding_it_puts_it_on_the_map_with_its_two_roads():
    guild = _guild()
    assert cult_site.reveal(guild)
    assert cult_site.NODE in {n.id for n in world.known(guild)}
    assert dict(world.neighbors(cult_site.NODE)) == dict(cult_site.LINKS)


def test_the_site_is_a_shortcut_from_the_farm_to_the_cathedral_once_found():
    guild = _guild()
    before = world.route("farm", "faith_cathedral")
    cult_site.reveal(guild)
    path, dist = world.route("farm", "faith_cathedral")
    assert path == ["farm", "country_roads", cult_site.NODE, "faith_cathedral"] and dist == 5 < before[1]


def test_an_unfound_site_is_never_on_a_route():
    guild = _guild()
    cult_site.sync_world(guild)
    assert cult_site.NODE not in world.route("farm", "faith_cathedral")[0]


def test_the_search_finds_nothing_without_the_job():
    guild = _guild(job=False, wis=10)
    with fixed_d20(20):
        found, _ = cult_site.search(guild, guild.groups[0])
    assert not found and not guild.is_node_revealed(cult_site.NODE)


def test_the_dc_is_hard_and_wisdom_alone_can_reach_it():
    guild = _guild(wis=2)
    with fixed_d20(cult_site.SEARCH_DC - 3):
        assert not cult_site.search(guild, guild.groups[0])[0]
    with fixed_d20(20):
        found, msg = cult_site.search(guild, guild.groups[0])
    assert found and guild.is_node_revealed(cult_site.NODE) and "smoke" in msg


def test_a_plain_20_with_no_wisdom_and_no_clues_is_not_enough():
    guild = _guild(wis=0)
    with fixed_d20(20):
        assert not cult_site.search(guild, guild.groups[0])[0]


def test_each_clue_adds_two_to_the_search():
    guild = _guild(wis=0)
    guild.investigation[JOB] = {"clues": 1, "asked": []}
    with fixed_d20(cult_site.SEARCH_DC - 3):
        assert not cult_site.search(guild, guild.groups[0])[0]
    guild.investigation[JOB]["clues"] = 2
    with fixed_d20(cult_site.SEARCH_DC - 4):
        assert cult_site.search(guild, guild.groups[0])[0]
    assert investigation.bonus(guild, JOB, cult_site.SEARCH_PER_CLUE) == 4


def test_the_search_is_a_two_hour_order_with_its_button_on_the_country_roads():
    assert campaign.SEARCHES["search_cult"] == (2, cult_site.search)
    guild = _guild()
    ins = MapSession(guild).state()["groups"][0]["inspector"]
    assert any(b["t"] == "button" and b["key"] == "search_cult" for b in ins["blocks"])
    guild.missions.clear()
    ins = MapSession(guild).state()["groups"][0]["inspector"]
    assert not any(b["t"] == "button" and b["key"] == "search_cult" for b in ins["blocks"])
    guild = _guild("farm")
    ins = MapSession(guild).state()["groups"][0]["inspector"]
    assert not any(b["t"] == "button" and b["key"] == "search_cult" for b in ins["blocks"])


def test_the_button_goes_once_the_site_is_found():
    guild = _guild()
    cult_site.reveal(guild)
    ins = MapSession(guild).state()["groups"][0]["inspector"]
    assert not any(b["t"] == "button" and b["key"] == "search_cult" for b in ins["blocks"])


def test_the_site_has_a_glyph_and_a_name():
    from pathlib import Path
    cat, name = map_view.node_icon(cult_site.NODE)
    assert list((Path(world.__file__).parent / "assets" / "icons" / cat).rglob(f"{name}.svg"))
    guild = _guild()
    cult_site.reveal(guild)
    assert world.node(cult_site.NODE).name and world.node(cult_site.NODE).blurb


def test_the_site_comes_back_on_the_map_when_the_save_is_loaded(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    guild = _guild()
    cult_site.reveal(guild)
    world_id = persist.new_world_id()
    persist.save_game(world_id, guild)
    world.clear_runtime()
    assert not world.exists(cult_site.NODE)
    persist.load_game(world_id)
    assert world.exists(cult_site.NODE)
