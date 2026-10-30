"""Screens draw native at any size; the shared modal and drag plumbing."""

import os
from tests.helpers import Unit, data, packed

def test_battle_export_state_writes_a_json_snapshot(tmp_path, monkeypatch):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import json

    import pygame

    from gartok.battle import Battle
    from editor.battle_screen import BattleScreen
    from editor.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    import editor.battle_screen as battle_screen_mod
    monkeypatch.setattr(battle_screen_mod, "DEBUG_EXPORT_DIR", str(tmp_path))

    batt = Battle([Unit("player")], [Unit("enemy")])
    scr = BattleScreen(ui_fonts(), batt, lambda *a, **k: None)
    scr._export_state()

    files = list(tmp_path.iterdir())
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert len(payload["units"]) == 2
    assert payload["units"][0]["name"] == batt.units[0].name
    assert "State exported to" in batt.log_lines[-1]


def test_battle_log_wheel_scroll_over_the_log_panel():
    """Scrolling with the mouse over the log well pages through history instead
    of zooming the board (the board still zooms everywhere else)."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.battle import Battle
    from editor.battle_screen import BattleScreen
    from editor.ui.tokens import fonts as ui_fonts
    pygame.init()
    surf = pygame.display.set_mode((1280, 800))

    batt = Battle([Unit("player")], [Unit("enemy")])
    for i in range(80):
        batt.log(f"line {i}")
    scr = BattleScreen(ui_fonts(), batt, lambda *a, **k: None)
    scr.draw(surf)                            # populates self._L

    log_rect = scr._L["log"]
    scr.mouse = log_rect.center
    zoom_before = tuple(scr.view.cam)
    scr.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=3, x=0))
    assert scr.log_scroll == 3
    assert tuple(scr.view.cam) == zoom_before          # scrolled the log, not the board

    scr.draw(surf)
    assert scr.log_scroll <= 3                          # clamped to what actually fits
    scroll_before = scr.log_scroll

    scr.mouse = (10, 10)                                 # off the log panel: back to zooming
    scr.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=1, x=0))
    assert scr.log_scroll == scroll_before               # untouched by the off-panel wheel
    assert tuple(scr.view.cam) != zoom_before            # the board zoomed instead


def test_daylight_fog_dims_cells_outside_los():
    """Daylight used to skip the darkness layer entirely (`ambient_light` short-
    circuited `LightRenderer.draw`), so every cell looked identically "lit" and
    there was no way to tell whether a given square was actually in the active
    character's LOS. A cell outside `visible` must render visibly dimmer than
    one inside it, even under full ambient light."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from editor.battle_draw import LightRenderer
    from editor.ui.board_style import BoardView
    pygame.init()
    surf = pygame.display.set_mode((640, 480))

    class FakeBoard:
        cols, rows = 10, 10

    class FakeBattle:
        ambient_light = True
        board = FakeBoard()

    view = BoardView(FakeBoard.cols, FakeBoard.rows)
    view.fit(pygame.Rect(0, 0, 640, 480))

    surf.fill((255, 255, 255))
    LightRenderer().draw(surf, FakeBattle(), {(2, 2)}, [], view)

    seen = surf.get_at(view.cell_rect(2, 2).center)
    unseen = surf.get_at(view.cell_rect(7, 7).center)
    assert tuple(seen)[:3] == (255, 255, 255)            # in LOS: untouched
    assert tuple(unseen)[:3] != (255, 255, 255)          # outside LOS: dimmed


def test_every_race_has_a_token_icon_that_loads():
    """`theme.token_badge` draws `artwork.RACE_ICON[race]` -> a file under
    assets/icons/head/. A missing mapping or a typo'd filename silently blanks
    the token, so pin both here."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from editor import artwork
    pygame.init()
    pygame.display.set_mode((1, 1))
    artwork.icon.cache_clear()

    for name in data.RACE_NAMES:
        assert name in artwork.RACE_ICON, f"race {name!r} has no token icon"
        surf = artwork.race_icon(name, 24, (15, 15, 20))
        assert surf is not None and surf.get_size() == (24, 24), name

    assert artwork.race_icon("Goblin", 24) is artwork.race_icon("Goblin", 24)  # cached
    assert artwork.icon("head", "no-such-glyph", 24) is None                   # graceful


def test_char_editor_duplicate_forks_an_unsaved_copy():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from editor.char_editor_screen import CharEditorScreen
    from editor.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))
    scr = CharEditorScreen(ui_fonts(), lambda: None)
    scr.unit.set_name("Ribit")
    scr.unit.set_race("Grippli")
    scr.unit.set_track_level("combat", 2)
    scr.slug = "ribit"
    original_uid = scr.unit.uid

    scr._duplicate()

    assert scr.slug is None                              # unsaved: SAVE writes a new file
    assert scr.unit.uid != original_uid
    assert scr.unit.name == "Ribit (copy)"
    assert scr.unit.race["name"] == "Grippli"
    assert scr.unit.combat_level == 2


def test_tongue_grippli_renders_in_the_editor():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from editor.char_editor_screen import CharEditorScreen
    from editor.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    u = Unit("player")
    u.set_race("Grippli")
    u.set_track_level("racial", 5)
    u.choose_talent("racial", "tongue")
    u.give_to_tongue("Dagger")
    u.equipped_weapon = "Broadsword"                     # 2-handed in the hands, dagger on the tongue

    scr = CharEditorScreen(ui_fonts(), lambda: None)
    scr._load_unit(u)
    scr.mouse = (0, 0)
    scr.draw(pygame.Surface((1600, 1000)))


def test_the_band_scroll_right_click_offers_and_toggles_study():
    """The only in-game path to set `Unit.study_target` (see the Magic section
    of RULES.md): a known scroll offers a "study" row on the item
    menu, mirroring the sandbox character editor's toggle."""
    from gartok.band_kit import BandKit
    from gartok.guild import Guild

    u = Unit("player")
    u.magic_sources = ["nature"]
    u._base_inventory = packed(["Scroll of Light Globe"])
    g = Guild([u])
    gs = BandKit(g, g.groups[0])

    def study():
        kind, _label, arg = next(r for r in gs._menu_rows([(u, 0)]) if r[0] == "study")
        gs._menu_run([(u, 0)], kind, arg)

    study()
    assert u.study_target == "light_globe"

    study()                                  # still offered, now toggles off
    assert u.study_target is None


def test_leshy_icon_asset():
    import pygame

    from editor import artwork
    assert artwork.RACE_ICON["Leshy"] == "sprout"
    assert artwork.RACE_ICON["Treefolk"] == "sprout"
    surf = artwork.race_icon("Treefolk", 24)
    assert surf is not None
    assert isinstance(surf, pygame.Surface)
    assert surf.get_size() == (24, 24)


def test_treefolk_race_and_portraits():
    import pygame

    from gartok import data, persist, unit

    from editor import artwork
    # 1. Race definition
    tf = data.race_by_name("Treefolk")
    assert tf is not None
    assert tf["name"] == "Treefolk"
    assert tf["size"] == "Medium"
    assert tf["hd"] == 6
    assert tf["language"] == "Verdant"
    assert tf["ability"] == "autotroph"

    # Backward compatibility alias
    leshy_alias = data.race_by_name("Leshy")
    assert leshy_alias is not None
    assert leshy_alias["name"] == "Treefolk"

    # 2. Portrait loader
    port = artwork.portrait("Treefolk", 0, 48)
    assert port is not None
    assert isinstance(port, pygame.Surface)
    assert port.get_size() == (48, 48)

    # All 10 portraits load correctly
    for idx in range(10):
        p = artwork.portrait("Treefolk", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    # Fallback when no portraits exist
    assert artwork.portrait("NonExistentRace", 0, 32) is None

    # 3. Unit and persistence round-trip
    u = unit.Unit("player", race=tf)
    assert hasattr(u, "portrait_id")
    assert isinstance(u.portrait_id, int)
    saved = persist.unit_to_dict(u)
    assert "portrait_id" in saved
    restored = unit.Unit.from_save(saved)
    assert restored.portrait_id == u.portrait_id
    assert restored.race["name"] == "Treefolk"


def test_goblin_portraits():
    import pygame

    from gartok import data, unit

    from editor import artwork
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    # 1. Loader returns scaled surface
    port = artwork.portrait("Goblin", 0, 48)
    assert port is not None
    assert isinstance(port, pygame.Surface)
    assert port.get_size() == (48, 48)

    # 2. All 7 curated portraits load correctly
    for idx in range(7):
        p = artwork.portrait("Goblin", idx, 32)
        assert p is not None
        assert p.get_size() == (32, 32)

    # 3. Unit integration
    goblin_race = data.race_by_name("Goblin")
    u = unit.Unit("player", race=goblin_race)
    assert hasattr(u, "portrait_id")
    p = artwork.portrait(u.race["name"], u.portrait_id, 24)
    assert p is not None
    assert p.get_size() == (24, 24)


def test_char_editor_attribute_hover_tooltip():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from editor.char_editor_screen import CharEditorScreen
    from editor.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    ed = CharEditorScreen(ui_fonts(), lambda: None)
    surf = pygame.Surface((1280, 720))
    ed.mouse = (0, 0)
    ed.draw(surf)

    found_tooltip = False
    if ed._form_rect:
        for x, y in ((36, 268), (ed._form_rect.x + 40, ed._form_rect.y + 200)):
            ed.mouse = (x, y)
            ed.draw(surf)
            if ed.tooltip and isinstance(ed.tooltip, list):
                title = ed.tooltip[0][0]
                if any(attr in title for attr in ("STR", "DEX", "CON", "INT", "WIS", "CHA")):
                    found_tooltip = True
                    break
    assert found_tooltip, "Character editor attribute cells should set tooltip on hover"


def test_char_editor_screen_hp_tooltip():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from editor.char_editor_screen import CharEditorScreen
    from editor.ui.tokens import fonts as ui_fonts
    from tests.helpers import Unit
    pygame.init()
    pygame.display.set_mode((1, 1))

    u = Unit("player")
    cs = CharEditorScreen(ui_fonts(), lambda: None)
    cs.unit = u
    surf = pygame.Surface((1280, 720))

    cs.mouse = (50, 410)
    cs.draw(surf)
    found_hp_tooltip = bool(cs.tooltip and any("HIT POINTS (HP)" in item[0] for item in cs.tooltip if isinstance(item, tuple)))
    assert found_hp_tooltip, "CharEditorScreen should display HP breakdown tooltip on hover"


def test_footer_bar_hint_offsets_when_back_button_present():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    from unittest.mock import patch

    import pygame

    from editor.ui.primitives import FOOTER_HINT, LEFT_W, footer_bar
    from editor.ui.tokens import T
    from editor.ui.tokens import fonts as ui_fonts

    pygame.init()
    pygame.display.set_mode((1, 1))
    F = ui_fonts()

    class Dummy:
        def __init__(self):
            self.buttons = []
            self._hot = False

        def add_button(self, surf, rect, key, label, *, enabled=True, primary=False, danger=False):
            self.buttons.append((key, rect))

    surf = pygame.Surface((800, 600))
    margin = T.S * 3

    # Without back button: hint starts at left margin
    screen_no_back = Dummy()
    with patch("editor.ui.primitives.text") as mock_text:
        footer_bar(screen_no_back, surf, F, primary=("ok", "OK"))
        hint_calls = [c for c in mock_text.call_args_list if c.args[2] == FOOTER_HINT]
        assert len(hint_calls) == 1
        assert hint_calls[0].args[3][0] == margin

    # With back button: hint starts after the back button
    screen_with_back = Dummy()
    with patch("editor.ui.primitives.text") as mock_text:
        footer_bar(screen_with_back, surf, F, back=("back", "BACK"), primary=("ok", "OK"))
        hint_calls = [c for c in mock_text.call_args_list if c.args[2] == FOOTER_HINT]
        assert len(hint_calls) == 1
        assert hint_calls[0].args[3][0] == margin + LEFT_W + T.S * 3
        # Ensure back button is registered and does not collide with hint
        back_btn = next(r for k, r in screen_with_back.buttons if k == "back")
        assert back_btn.right < hint_calls[0].args[3][0]


def test_battle_screen_victory_card_with_stabilized():
    import pygame

    from gartok.battle import Battle
    from editor.battle_screen import BattleScreen
    from editor.ui.tokens import fonts as ui_fonts
    from gartok.unit import Unit
    pygame.init()
    surf = pygame.Surface((1024, 768))
    batt = Battle([Unit("player"), Unit("player")], [Unit("enemy")])
    batt.winner = "player"
    batt.player_units[0].status = "up"
    batt.player_units[1].status = "stable"
    scr = BattleScreen(ui_fonts(), batt, lambda *a, **k: None)
    scr.draw(surf)


def test_battle_screen_tabs_and_hotkeys():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok import actions
    from gartok.battle import Battle
    from editor.battle_screen import BattleScreen
    from editor.ui.tokens import fonts as ui_fonts
    pygame.init()
    surf = pygame.display.set_mode((1280, 800))

    batt = Battle([Unit("player")], [Unit("enemy")])
    batt.turn_idx = next(i for i, u in enumerate(batt.order) if u.team == "player")
    scr = BattleScreen(ui_fonts(), batt, lambda *a, **k: None)
    scr.draw(surf)

    # 1. Starts in combat tab
    assert scr.action_tab == "combat"
    assert actions.ATTACK in scr._hotkey_actions
    assert actions.DEFEND in scr._hotkey_actions

    # Hotkey [5] or Defend is directly accessible
    defend_idx = scr._hotkey_actions.index(actions.DEFEND)
    assert defend_idx < 9

    # 2. Pressing TAB switches to utility tab
    scr.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB))
    assert scr.action_tab == "utility"
    scr.draw(surf)
    assert actions.FIRST_AID in scr._hotkey_actions

    # 3. Pressing TAB again switches back to combat
    scr.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB))
    assert scr.action_tab == "combat"


def test_battle_screen_actions_wheel_scroll():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.battle import Battle
    from editor.battle_screen import BattleScreen
    from editor.ui.tokens import fonts as ui_fonts
    pygame.init()
    surf = pygame.display.set_mode((1280, 720))

    batt = Battle([Unit("player")], [Unit("enemy")])
    scr = BattleScreen(ui_fonts(), batt, lambda *a, **k: None)
    scr.show_blocked_actions = True
    scr.draw(surf)

    assert scr._actions_scroll_rect is not None
    assert scr._actions_max_scroll > 0

    # Scroll down over the actions area
    scr.mouse = scr._actions_scroll_rect.center
    scr.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=-2, x=0))
    assert scr.actions_scroll > 0

    # Draw again and verify clamping
    scr.draw(surf)
    assert scr.actions_scroll <= scr._actions_max_scroll


def test_battle_screen_16_9_monitor_no_overflow():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.battle import Battle
    from editor.battle_screen import BattleScreen
    from editor.ui.tokens import T
    from editor.ui.tokens import fonts as ui_fonts
    pygame.init()

    resolutions = [
        (1280, 720),    # 720p 16:9
        (1366, 768),    # Common laptop 16:9
        (1600, 900),    # 900p 16:9
        (1920, 1080),   # 1080p 16:9
    ]

    for w, h in resolutions:
        surf = pygame.Surface((w, h))
        batt = Battle([Unit("player")], [Unit("enemy")])
        scr = BattleScreen(ui_fonts(), batt, lambda *a, **k: None)
        scr.show_blocked_actions = True    # maximize number of buttons shown
        scr.inspect_open = True            # full compact inspect card open
        scr.draw(surf)

        panel_r = scr._L["panel"]
        assert panel_r.bottom <= h - T.S * 2

        # Check all registered buttons are strictly on-screen
        for key, rect in scr.buttons:
            assert rect.top >= 0, f"Button {key} top {rect.top} above window in {w}x{h}"
            assert rect.bottom <= h, f"Button {key} bottom {rect.bottom} below window {h} in {w}x{h}"

        # Switch to utility tab and verify no overflow there either
        scr.action_tab = "utility"
        scr.draw(surf)
        for key, rect in scr.buttons:
            assert rect.top >= 0, f"Utility button {key} top {rect.top} above window in {w}x{h}"
            assert rect.bottom <= h, f"Utility button {key} bottom {rect.bottom} below window {h} in {w}x{h}"


def test_primitives_text_and_ellipsize_none_resilience():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from editor.ui.primitives import caps, ellipsize, text
    from editor.ui.tokens import fonts as ui_fonts
    pygame.init()
    surf = pygame.Surface((100, 100))
    f = ui_fonts()["body"]

    assert ellipsize(None, f, 100) == ""
    assert ellipsize("", f, 100) == ""
    assert ellipsize("hello", f, 0) == ""
    assert ellipsize("hello", f, -5) == ""
    assert ellipsize("hello world", f, 30).endswith("…")

    r = text(surf, f, None, (0, 0), (255, 255, 255))
    assert r.width == 0
    rc = caps(surf, f, None, (0, 0), (255, 255, 255))
    assert rc.width == 0
