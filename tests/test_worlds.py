"""The world/save flow in the app and its screens: autosave before a fight,
loading a snapshot, a wipe that keeps the world, naming a save from the pause menu."""

import os

import pygame

from gartok import persist, world
from gartok.app import App
from gartok.battle import Battle
from gartok.guild import Guild
from gartok.menu_screen import MenuScreen
from gartok.pause_screen import PauseScreen
from gartok.saves_screen import SavesScreen
from gartok.ui.tokens import fonts as ui_fonts
from tests.helpers import Unit

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def _app():
    app = App.__new__(App)
    app.world = persist.new_world_id()
    app.scene = None
    app.ui_fonts = ui_fonts()
    app.guild = Guild([Unit("player")], node="road", name="Wolfbane")
    app._battle_squad, app._battle_node, app._arena_offer = [], None, None
    app._hunt = app._pause_order = app._pause_group = app._claim_stage_pending = None
    app._map_notices, app._pending, app._pending_event = [], [], None
    return app


def _kinds(w):
    return [r["kind"] for r in persist.list_saves(w)]


def test_entering_a_fight_autosaves_the_world_first():
    pygame.init()
    app = _app()
    battle = Battle(list(app.guild.roster), [Unit("enemy"), Unit("enemy")], scenario=None)
    app._enter_battle(battle, world.node("road"))

    autos = [r for r in persist.list_saves(app.world) if r["kind"] == "auto"]
    assert len(autos) == 1
    assert "The Road" in autos[0]["label"] or world.node("road").name in autos[0]["label"]
    assert "2 foes" in autos[0]["label"]
    assert autos[0]["name"] == "Wolfbane"


def test_loading_a_snapshot_makes_it_the_live_state_and_keeps_the_rest():
    pygame.init()
    app = _app()
    app.guild.battles_won = 1
    snap = persist.save_game(app.world, app.guild, kind="auto", label="before")
    app.guild.battles_won = 5
    persist.save_game(app.world, app.guild)

    app._start_map = lambda: None
    app._continue_game(app.world, snap)

    assert app.guild.battles_won == 1
    assert persist.load_game(app.world).battles_won == 1
    assert snap in {r["id"] for r in persist.list_saves(app.world)}


def test_a_wipe_keeps_the_world_and_says_so_on_the_menu():
    pygame.init()
    app = _app()
    persist.save_game(app.world, app.guild)
    w = app.world
    app._campaign_over()

    assert persist.list_saves(w)
    assert isinstance(app.scene, MenuScreen) and "wiped" in app.scene.notice
    assert app.guild is None and app.world is None


def test_save_as_from_the_pause_menu_writes_a_named_manual_save():
    pygame.init()
    app = _app()
    app._save_as("before the dragon")
    manual = [r for r in persist.list_saves(app.world) if r["kind"] == "manual"]
    assert [r["label"] for r in manual] == ["before the dragon"]


def test_pause_screen_naming_flow_types_a_name_and_saves_on_enter():
    pygame.init()
    saved = []
    p = PauseScreen(ui_fonts(), None, lambda: None, lambda: None, lambda: None, on_save_as=saved.append)
    p.draw(pygame.Surface((1280, 800)))
    p._click(dict(p._buttons)["save_as"].center)
    assert p.naming
    for ch in "Hi":
        p.handle_event(pygame.event.Event(pygame.KEYDOWN, key=ord(ch.lower()), unicode=ch))
    p.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r"))
    assert saved == ["Hi"] and not p.naming


def test_pause_escape_cancels_naming_instead_of_resuming():
    pygame.init()
    p = PauseScreen(ui_fonts(), None, lambda: None, lambda: None, lambda: None, on_save_as=lambda n: None)
    p.naming = True
    assert p.handle_escape() is True and not p.naming
    assert p.handle_escape() is False


def test_menu_lists_each_guild_and_opens_its_saves():
    pygame.init()
    w = persist.new_world_id()
    persist.save_game(w, Guild([Unit("player")], node="city", name="Iron Fists"))
    persist.save_game(w, Guild([Unit("player")], node="city", name="Iron Fists"), kind="auto", label="x")
    opened = []
    m = MenuScreen(ui_fonts(), lambda: None, lambda wd: None, opened.append, lambda wd: None)
    m.draw(pygame.Surface((1280, 800)))
    saves_btn = next(r for k, wd, r in m.buttons if k == "saves" and wd == w)
    m._click(saves_btn.center)
    assert opened == [w]
    assert m.worlds[0]["saves"] == 2


def test_saves_screen_shows_date_time_and_loads_the_picked_snapshot():
    pygame.init()
    w = persist.new_world_id()
    guild = Guild([Unit("player")], node="city", name="Iron Fists")
    persist.save_game(w, guild)
    snap = persist.save_game(w, guild, kind="manual", label="safe")
    loaded = []
    s = SavesScreen(ui_fonts(), w, lambda wd, sid: loaded.append((wd, sid)), lambda: None)
    s.draw(pygame.Surface((1280, 800)))
    assert s.title == "Iron Fists"
    manual_row = next(r for r in s.saves if r["id"] == snap)
    assert manual_row["saved_at"] > 0
    load_btn = next(r for k, sid, r in s.buttons if k == "load" and sid == snap)
    s._click(load_btn.center)
    assert loaded == [(w, snap)]


def test_deleting_a_save_asks_once():
    pygame.init()
    w = persist.new_world_id()
    guild = Guild([Unit("player")], node="city", name="G")
    persist.save_game(w, guild)
    snap = persist.save_game(w, guild, kind="manual", label="m")
    s = SavesScreen(ui_fonts(), w, lambda *a: None, lambda: None)
    s.draw(pygame.Surface((1280, 800)))
    s._click(next(r for k, sid, r in s.buttons if k == "delete" and sid == snap).center)
    s.draw(pygame.Surface((1280, 800)))
    s._click(next(r for k, sid, r in s.buttons if k == "delete_yes").center)
    assert snap not in {r["id"] for r in persist.list_saves(w)}


def test_save_as_is_greyed_out_where_there_is_no_campaign_to_save():
    pygame.init()
    saved = []
    p = PauseScreen(ui_fonts(), None, lambda: None, lambda: None, lambda: None,
                    on_save_as=saved.append, can_save=False)
    p.draw(pygame.Surface((1280, 800)))
    assert "save_as" not in dict(p._buttons)
    assert "resume" in dict(p._buttons)
    assert not saved


def test_the_pause_menu_from_the_draft_cannot_save():
    pygame.init()
    app = App()
    app._new_game()                              # DraftScreen: no guild, no world yet
    app._toggle_pause()
    assert isinstance(app.scene, PauseScreen) and app.scene.can_save is False
    app.scene.resume_to.mouse = (-1, -1)
    app.scene.draw(pygame.Surface((1280, 800)))
    assert "save_as" not in dict(app.scene._buttons)


def test_the_pause_menu_in_a_campaign_can_save():
    pygame.init()
    app = _app()
    app.scene = type("S", (), {"native": True, "mouse": (0, 0), "draw": lambda self, s: None})()
    app._toggle_pause()
    assert isinstance(app.scene, PauseScreen) and app.scene.can_save is True
