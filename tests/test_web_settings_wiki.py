"""The settings and the wiki in the browser, opened from the title or the map's menu (pygame's pause
menu: resume, save as, settings, wiki, main menu, quit), and back to where they were opened."""

import json
import os
import re
import threading
import urllib.request
from pathlib import Path

import pytest

from gartok import (
    actions,
    items,
    keywords,
    persist,
    recorder,
    settings,
    talents,
    weapon_traits,
    wiki_rules,
    wiki_terms,
)
from gartok.group import Group
from gartok.guild import Guild
from gartok.web.map_session import MapSession
from gartok.web.server import Game, serve
from gartok.web.settings_session import SettingsSession
from gartok.web.title_session import TitleSession
from gartok.web.wiki_session import WikiSession
from tests.helpers import standard_unit


@pytest.fixture
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path / "saves"))
    monkeypatch.setattr(settings, "PATH", str(tmp_path / "settings.json"))
    settings.reload()
    yield tmp_path
    settings.reload()
    recorder.detach()


def _map():
    units = [standard_unit() for _ in range(2)]
    guild = Guild(None, groups=[Group(units, node="lumber_yard", leader=units[0])], name="Ink Hands",
                  vocation="caravan")
    persist.save_game("ink", guild)
    return Game(MapSession(guild, "ink"))


def _title_menu(title):
    return {m["key"]: m for m in title.state()["menu"] if m}


# ---------------------------------------------------------------- the title
def test_the_title_opens_the_wiki_and_the_settings_and_they_come_back(saves):
    title = Game.title().session
    menu = _title_menu(title)
    assert menu["wiki"]["enabled"] and menu["settings"]["enabled"]
    assert TitleSession.POST["wiki"](title, {}) == {"screen": "wiki"}
    wiki = title.game.session
    assert isinstance(wiki, WikiSession) and wiki.state()["back"] == "Back to the title"
    assert wiki.back_to() == {"screen": "title"} and title.game.session is title
    assert TitleSession.POST["settings"](title, {}) == {"screen": "settings"}
    st = title.game.session.state()
    assert st["tutorial"] is None, "with no guild open there is no tutorial to set"
    assert title.game.session.back_to() == {"screen": "title"} and title.game.session is title


# ---------------------------------------------------------------- the settings
def test_a_setting_keeps_the_choice_pressed_and_saves_it(saves):
    s = SettingsSession(lambda: {"screen": "title"})
    rows = {r["key"]: r for r in s.state()["rows"]}
    assert set(rows) == set(settings.SPEC)
    assert [c["value"] for c in rows["volume"]["choices"]] == list(settings.SPEC["volume"][1])
    assert rows["volume"]["choices"][0]["label"] == "Off"
    assert "choices" not in rows["log_lines"] and rows["log_lines"]["number"] == {"min": 200, "max": 50000}
    st = s.set("log_lines", " 3000 ")
    assert next(r for r in st["rows"] if r["key"] == "log_lines")["value"] == 3000
    for bad in (50, "many", 99999):
        with pytest.raises(ValueError, match="cannot be"):
            s.set("log_lines", bad)
    st = s.set("volume", 25)
    assert st["volume"] == 25 and next(r for r in st["rows"] if r["key"] == "volume")["value"] == 25
    s.set("record_play", "ON")
    settings.reload()
    assert settings.get("volume") == 25 and settings.get("record_play") == "ON"


def test_a_setting_refuses_what_it_does_not_offer(saves):
    s = SettingsSession(lambda: {"screen": "title"})
    with pytest.raises(ValueError, match="cannot be 30"):
        s.set("volume", 30)
    with pytest.raises(ValueError, match="no setting"):
        s.set("brightness", 1)
    with pytest.raises(ValueError, match="belong to a guild"):
        s.toggle_tutorial()


def test_from_the_map_the_settings_carry_the_guilds_tutorial_and_save_it(saves):
    game = _map()
    m = game.session
    assert MapSession.POST["settings"](m, {}) == {"screen": "settings"}
    s = game.session
    assert s.state()["tutorial"] == {"enabled": True, "reset": False} and s.state()["guild"] == "Ink Hands"
    assert s.toggle_tutorial()["tutorial"]["enabled"] is False
    assert persist.load_game("ink").tutorial.enabled is False
    m.guild.tutorial.dismiss("map")
    m._save()
    assert "map" in persist.load_game("ink").tutorial.seen
    assert s.reset_tutorial()["tutorial"]["reset"] is True
    assert "map" not in persist.load_game("ink").tutorial.seen
    s.back_to()
    assert game.session is m


# ---------------------------------------------------------------- the wiki
def test_the_wiki_opens_on_items_and_every_chapter_reads_the_catalogs(saves):
    w = WikiSession(lambda: {"screen": "title"})
    st = w.state()
    assert st["chapter"] == "items" and len(st["chapters"]) == 10
    plain = [i for i in items.all_items().values() if i.base is None]
    assert st["total"] == len(plain) and len(st["entries"]) == st["total"]
    sword = next(e for e in st["entries"] if e["name"] == "Broadsword")
    assert "1d12" in sword["tags"] and "Two-handed" in sword["tags"] and sword["glyph"].startswith("item/")
    assert all("_find" not in e for e in st["entries"])
    for c in st["chapters"]:
        assert w.chapter(c["id"])["entries"], c["id"]
    assert w.chapter("talents")["total"] == sum(len(t) for t in talents.TREE.values())
    rules = w.chapter("rules")
    assert [e["name"] for e in rules["entries"]] == [t for _, t, _ in wiki_rules.sections()]
    assert [e["id"] for e in rules["entries"]] == [k for k, _, _ in wiki_rules.sections()]
    with pytest.raises(ValueError, match="no chapter"):
        w.chapter("nothing")


def test_the_wiki_spells_chapter_lists_every_spell_with_level_cost_and_schools(saves):
    from gartok import magic

    w = WikiSession(lambda: {"screen": "title"})
    st = w.chapter("spells")
    assert st["total"] == len(magic.SPELLS)
    hex_ = next(e for e in st["entries"] if e["id"] == "hex")
    assert hex_["kind"] == "Spell · level 0" and hex_["tags"] == ["Blood"] and hex_["body"][0]
    assert "1 AP" in hex_["meta"]
    assert next(e for e in st["entries"] if e["id"] == "sleep")["tags"] == ["Any school"]
    assert {"hex", "dragonfire"} <= {e["id"] for e in w.find("blood")["entries"]}


def test_the_wiki_filter_reads_more_than_the_name_and_holds_across_chapters(saves):
    w = WikiSession(lambda: {"screen": "title"})
    w.chapter("recipes")
    st = w.find("IRON BAR")
    assert st["query"] == "iron bar" and st["entries"] and len(st["entries"]) < st["total"]
    assert all("Iron Bar" in e["body"][0] or "iron bar" in e["name"].lower() for e in st["entries"])
    st = w.chapter("rules")
    assert st["query"] == "iron bar" and st["entries"] == []
    assert w.find("flank")["entries"][0]["name"] == "Off-guard and flanking"
    w.find("nature")
    races = w.chapter("races")["entries"]
    assert "Gnome" in [e["name"] for e in races] and all("nature" in json.dumps(e).lower() for e in races)
    assert len(w.find("x" * 40)["query"]) == 24
    assert w.find("")["entries"]


def test_every_trait_and_action_an_item_names_opens_its_entry_and_shows_it_on_hover(saves):
    w = WikiSession(lambda: {"screen": "title"})
    pages = w.state()["entries"]
    named = 0
    for it in (i for i in items.all_items().values() if i.base is None):
        page = next(e for e in pages if e["name"] == it.name)
        for tid in it.traits:
            if weapon_traits.get(tid):
                assert f"actions:{tid}" in [x["ref"] for x in page["links"]], (it.name, tid)
        for link in page["links"]:
            named += 1
            st = w.open(link["ref"])
            entry = next(e for e in st["entries"] if e["id"] == st["focus"])
            assert st["chapter"] == link["ref"].split(":")[0] and link["tip"].startswith(entry["name"] + "\n")
            assert entry["body"] == [] or entry["body"][0] in link["tip"]
        w.chapter("items")
    assert named > 30


def test_the_wiki_links_what_an_item_brings_besides_its_traits(saves):
    w = WikiSession(lambda: {"screen": "title"})
    links = {e["name"]: [x["label"] for x in e["links"]] for e in w.state()["entries"]}
    assert links["Axe"] == ["Cleave"]
    assert links[items.FIRST_AID_ITEM] == ["First Aid", "Stabilize"]
    assert links[items.SIGNAL_HORN_ITEM] == ["Signal Horn"]
    dagger = next(it for it in items.all_items().values() if it.finesse and it.thrown)
    assert "Finesse" in links[dagger.name] and f"Thrown {dagger.thrown} sq" in links[dagger.name]
    assert "Throw" in links[dagger.name]
    sword = next(e for e in w.state()["entries"] if e["name"] == "Broadsword")
    assert links["Broadsword"] == ["Parry & Strike"] and "Parry & Strike" not in sword["tags"]
    assert w.find("cleave")["entries"] and all("Cleave" in json.dumps(e) for e in w.state()["entries"])


def test_the_wiki_names_a_melee_reach_and_a_shot_distance(saves):
    w = WikiSession(lambda: {"screen": "title"})
    links = {e["name"]: [x["label"] for x in e["links"]] for e in w.state()["entries"]}
    assert "Reach 2" in links["Glaive"]
    assert not any(x.startswith("Reach") for x in links["Broadsword"])
    assert "Distance 18 sq" in links["Crossbow"]
    assert not any(x.startswith("Distance") for x in links["Glaive"])
    assert not any("Range" in t for e in w.state()["entries"] for t in e["tags"])
    kw = {e["name"]: e["body"][0] for e in w.chapter("keywords")["entries"]}
    assert "melee" in kw["Reach"] and "shot" in kw["Distance"]


def test_opening_an_entry_turns_to_it_with_the_filter_cleared(saves):
    w = WikiSession(lambda: {"screen": "title"})
    w.find("axe")
    st = w.open("actions:cleave")
    assert (st["chapter"], st["query"], st["focus"]) == ("actions", "", "cleave")
    assert st["focus"] in [e["id"] for e in st["entries"]]
    assert w.chapter("items")["focus"] is None
    for bad in ("actions:nothing", "spells:cleave", "cleave"):
        with pytest.raises(ValueError, match="no entry"):
            w.open(bad)
    assert w.state()["chapter"] == "items"


def test_a_sheet_names_its_weapon_action_with_the_entry_on_hover():
    assert wiki_terms.action_tip("Cleave") == wiki_terms.tip("cleave")
    assert wiki_terms.action_tip(None) == "" and wiki_terms.action_tip("Nothing") == ""


# ---------------------------------------------------------------- the map's menu
def test_the_maps_menu_saves_under_a_name_and_comes_back_from_the_wiki(saves):
    game = _map()
    m = game.session
    assert m.save_as("  before the mine ") == {"saved": "before the mine"}
    assert m.save_as("") == {"saved": "Manual save"}
    labels = [s["label"] for s in persist.list_saves("ink") if s["kind"] == "manual"]
    assert sorted(labels) == ["Manual save", "before the mine"]
    assert MapSession.POST["wiki"](m, {}) == {"screen": "wiki"}
    assert game.session.state()["back"] == "Back to the map"
    back = game.session.back_to()
    assert game.session is m and "groups" in back
    m.wiped = True
    with pytest.raises(ValueError, match="nothing to save"):
        m.save_as("too late")


def test_quit_from_the_map_saves_and_stops_the_window(saves):
    game = _map()
    stopped = []
    game.quit = lambda: stopped.append(True)
    game.session.guild.groups[0].node = "market"
    assert MapSession.POST["quit"](game.session, {}) == {"quit": True} and stopped
    assert persist.load_game("ink").groups[0].node == "market"


def test_the_router_serves_both_screens(saves):
    game = Game.title()
    srv = serve(game)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"

    def post(path, body):
        req = urllib.request.Request(url + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req).read())

    try:
        for f in ("wiki/screen.html", "wiki/wiki.css", "wiki/wiki.js",
                  "settings/screen.html", "settings/settings.css", "settings/settings.js"):
            assert urllib.request.urlopen(f"{url}/client/screens/{f}").status == 200
        assert post("/api/title/wiki", {}) == {"screen": "wiki"}
        assert post("/api/wiki/chapter", {"chapter": "beasts"})["chapter"] == "beasts"
        assert post("/api/wiki/open", {"ref": "actions:cleave"})["focus"] == "cleave"
        assert post("/api/wiki/back", {}) == {"screen": "title"}
        assert post("/api/title/settings", {}) == {"screen": "settings"}
        assert post("/api/settings/set", {"key": "volume", "value": 50})["volume"] == 50
        info = json.loads(urllib.request.urlopen(url + "/api/screen").read())
        assert info["screen"] == "settings" and info["volume"] == 50
    finally:
        srv.shutdown()
        srv.server_close()


# ---------------------------------------------------------------- the playtest export
def test_the_export_zips_the_saves_the_combat_logs_and_names_the_build(saves):
    import io
    import json
    import urllib.request
    import zipfile

    from gartok.version import GAME_VERSION
    game = _map()
    logs = os.path.join(persist.world_dir("ink"), "combat_logs")
    os.makedirs(logs)
    with open(os.path.join(logs, "fight.jsonl"), "w") as fh:
        fh.write("{}\n")
    game.open(SettingsSession(lambda: None))
    srv = serve(game)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/api/settings/export")
        assert "attachment" in r.headers["Content-Disposition"]
        z = zipfile.ZipFile(io.BytesIO(r.read()))
    finally:
        srv.shutdown()
        srv.server_close()
    names = set(z.namelist())
    assert {"playtest.json", "saves/ink/current.json", "saves/ink/combat_logs/fight.jsonl"} <= names
    assert json.loads(z.read("playtest.json"))["game_version"] == GAME_VERSION


# ---------------------------------------------------------------- the credits
def test_the_title_opens_the_credits_which_name_the_authors_the_licence_and_the_source(saves):
    from gartok.web.credits_session import CreditsSession
    title = Game.title().session
    assert _title_menu(title)["credits"]["enabled"]
    assert TitleSession.POST["credits"](title, {}) == {"screen": "credits"}
    credits = title.game.session
    assert isinstance(credits, CreditsSession) and credits.tutorial_key() is None
    st = credits.state()
    icons, sounds, music = st["sections"]
    names = {p["name"] for p in icons["people"]}
    assert {"Lorc", "Delapouite"} <= names, "the authors come from the icons' LICENSE.txt"
    assert [x["url"] for x in icons["links"]] == ["https://creativecommons.org/licenses/by/3.0/",
                                                  "https://game-icons.net/"]
    assert "CC BY 3.0" in icons["intro"] and "CC0" in sounds["intro"]
    assert sounds["people"][0]["name"] == "Kenney Vleugels" and sounds["links"][0]["url"].endswith("/zero/1.0/")
    assert {p["name"] for p in music["people"]} >= {"RandomMind", "Emma_MA"} and music["links"][0]["url"].endswith("/zero/1.0/")
    assert "StarNinjas" in {p["name"] for p in sounds["people"]}
    assert st["back"] == "Back to the title"
    assert credits.back_to() == {"screen": "title"} and title.game.session is title


def test_every_author_the_icons_license_lists_reaches_the_credits():
    from gartok.web import credits_session
    listed = credits_session.authors(credits_session._read("icons"))
    assert len(listed) >= 12 and all(a["name"] for a in listed)
    assert [a["name"] for a in listed][:2] == ["Lorc", "Delapouite"]


# ---------------------------------------------------------------- keywords
def test_a_keyword_has_its_own_chapter_and_the_actions_that_name_it_link_to_it(saves):
    w = WikiSession(lambda: {"screen": "title"})
    st = w.chapter("keywords")
    assert [e["name"] for e in st["entries"]] == sorted(k.name for k in keywords.all_keywords())
    brutal = st["entries"][0]
    assert brutal["kind"] == "Keyword" and brutal["body"] == [keywords.get("brutal").text]
    dagger = next(e for e in w.chapter("actions")["entries"] if e["id"] == "sneak_attack")
    link = next(x for x in dagger["links"] if x["label"] == "Brutal")
    assert link["ref"] == "keywords:brutal" and link["tip"].startswith("Brutal\nKeyword")
    st = w.open(link["ref"])
    assert (st["chapter"], st["focus"]) == ("keywords", "brutal")
    assert "brutal" not in [e["id"] for e in w.chapter("actions")["entries"]]


def test_a_tooltip_that_names_a_keyword_carries_its_entry_once_and_never_chains():
    sneak = wiki_terms.tip("sneak_attack").split("\n")
    assert sneak[-1] == keywords.get("brutal").text and sneak.count(keywords.get("brutal").text) == 1
    assert wiki_terms.action_tip("Sneak Attack") == wiki_terms.tip("sneak_attack")
    assert wiki_terms.tip("brutal").split("\n") == ["Brutal", "Keyword", keywords.get("brutal").text]
    dying = wiki_terms.tip("dying").split("\n")
    assert dying[3:] == [keywords.get("knocked_out").text]


def test_the_rules_keywords_exist_and_each_names_itself_in_its_text():
    ids = [k.id for k in keywords.all_keywords()]
    assert {"critical_hit", "flanked", "shove", "dying", "knocked_out"} <= set(ids)
    assert len(set(ids)) == len(ids) and not set(ids) & {a.id for a in actions.PANEL_ACTIONS}
    for k in keywords.all_keywords():
        assert k.text.startswith(k.name) and k.id in wiki_terms.keywords_in(k.text)


def test_a_keyword_is_written_once_and_every_other_text_says_only_the_word():
    assert wiki_terms.keywords_in("the blow is Brutal, and Brutalised is not") == ["brutal"]
    root = Path(__file__).resolve().parent.parent / "gartok"
    for path in root.rglob("*.py"):
        assert "twice over" not in path.read_text(encoding="utf-8"), path
    for name in ("actions/weapon_actions.py", "weapon_traits.py"):
        assert not re.search(r"\bdouble\b", (root / name).read_text(encoding="utf-8")), name


def test_the_wiki_orders_chapters_and_entries_by_what_the_player_reads(saves, monkeypatch):
    from gartok.web import wiki_session

    w = WikiSession(lambda: {"screen": "title"})
    labels = [c["label"] for c in w.state()["chapters"]]
    assert labels == sorted(labels, key=wiki_session.alpha)
    names = [e["name"] for e in w.state()["entries"]]
    assert names == sorted(names, key=wiki_session.alpha)
    monkeypatch.setattr(wiki_session.i18n, "lab", lambda t: {"Items": "Zeta", "Rules": "Árvore"}.get(t, t))
    labels = [c["label"] for c in w.state()["chapters"]]
    assert labels[:3] == ["Actions", "Árvore", "Beasts"] and labels[-1] == "Zeta"
    assert wiki_session.alpha("Árvore") == "arvore" and wiki_session.alpha("Água") < wiki_session.alpha("Bola")


def test_a_keyword_that_names_the_routed_condition_links_to_its_conditions_entry(saves):
    w = WikiSession(lambda: {"screen": "title"})
    morale = next(e for e in w.chapter("keywords")["entries"] if e["id"] == "morale")
    link = next(x for x in morale["links"] if x["label"] == "Routed")
    assert link["ref"] == "conditions:routed" and "morale spent" in link["tip"].lower()
    assert "routed" not in {e["id"] for e in w.chapter("keywords")["entries"]}
    assert w.open(link["ref"])["focus"] == "routed"


def test_marks_name_the_keywords_and_finesse_a_description_uses_with_their_tips():
    marks = wiki_terms.marks("Your blows with finesse weapons gain Brutal 1 if the way is clear.")
    assert [m["word"] for m in marks] == ["finesse", "Brutal"]
    assert marks[1]["tip"] == wiki_terms.tip("brutal") and marks[0]["tip"] == wiki_terms.tip("finesse")
    assert wiki_terms.marks("+2 squares of Speed.") == [] and wiki_terms.marks("") == []


def test_the_music_has_its_own_volume_apart_from_the_sounds(saves):
    s = SettingsSession(lambda: {"screen": "title"})
    row = next(r for r in s.state()["rows"] if r["key"] == "music")
    assert [c["value"] for c in row["choices"]] == [0, 25, 50, 75, 100] and row["choices"][0]["label"] == "Off"
    assert row["choices"][2]["label"] == "50%" and row["label"] == "Music"
    st = s.set("music", 25)
    assert st["music"] == 25 and st["volume"] == settings.SPEC["volume"][2]
    assert settings.label("music") == "MUSIC: 25%"
