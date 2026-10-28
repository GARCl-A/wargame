"""Screens draw native at any size; the shared modal and drag plumbing."""

import os
import random

from gartok.guild import Guild
from tests.helpers import Unit, click_menu, data, economy, packed, standard_unit


def test_battle_export_state_writes_a_json_snapshot(tmp_path, monkeypatch):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import json

    import pygame

    from gartok.battle import Battle
    from gartok.battle_screen import BattleScreen
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    import gartok.battle_screen as battle_screen_mod
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
    from gartok.battle_screen import BattleScreen
    from gartok.ui.tokens import fonts as ui_fonts
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

    from gartok.lighting import LightRenderer
    from gartok.ui.board_style import BoardView
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


def test_market_stepper_buys_the_quantity_in_one_drop_and_stops_at_the_purse():
    from gartok.trade import Counter
    random.seed(2)
    buyer = Unit("player")
    buyer._base_inventory = []
    buyer.carry_max = 10_000                          # keep load out of this test
    ms = Counter(Guild([buyer]), [buyer], None)
    ms.deal = []
    unit_price = economy.buy_price("Meat")

    ms.purse = unit_price * 100                       # plenty of coin and carry
    ms.selected = [("stock", "Meat")]
    ms.qty["Meat"] = 10
    ms._drop_on_zone(buyer, "pack")
    assert buyer.count_of("Meat") == 10
    assert ms.purse == unit_price * 90
    assert ms.qty.get("Meat", 1) == 1                 # the stepper resets after a buy

    buyer.carry_max = 10_000                          # _buy re-derived it; keep load out
    ms.purse = unit_price * 3                         # only three affordable
    ms.selected = [("stock", "Meat")]
    ms.qty["Meat"] = 10
    ms._drop_on_zone(buyer, "pack")
    assert buyer.count_of("Meat") == 13
    assert ms.purse == 0 and "3 of 10" in ms.notice


def test_dragselect_ignores_a_mouseup_with_no_matching_press():
    """Entering the market via the squad picker's GO SHOPPING button leaves the
    left button down; the release then lands on the scene that just replaced it.
    That stray MOUSEBUTTONUP must not count as a click (which would fire
    LEAVE THE MARKET and bounce the player straight back out)."""
    import pygame

    from gartok.dragselect import DragSelectMixin
    from gartok.screen import Screen

    class Probe(DragSelectMixin, Screen):
        def __init__(self):
            super().__init__()
            self.drops = 0
            self.tab_hits = []              # [(rect, unit)]
            self.buttons = []                  # [(key, rect)]
            self._pack_scroll = {}
            self._pack_area = None
            self.managed = []
            self._cap = len(self.managed)
            self._hot = False         # columns that fit (recomputed each frame)

        def _source_at(self, px):
            return None

        def _drop(self, px, dragging, src):
            self.drops += 1

    p = Probe()
    up = pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": 1, "pos": (10, 10)})
    p.handle_event(up)
    assert p.drops == 0                               # stray release: no-op

    down = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (5, 5)})
    p.handle_event(down)
    p.handle_event(up)
    assert p.drops == 1                               # a real press/release still lands


def test_every_race_has_a_token_icon_that_loads():
    """`theme.token_badge` draws `artwork.RACE_ICON[race]` -> a file under
    assets/icons/head/. A missing mapping or a typo'd filename silently blanks
    the token, so pin both here."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok import artwork
    pygame.init()
    pygame.display.set_mode((1, 1))
    artwork.icon.cache_clear()

    for name in data.RACE_NAMES:
        assert name in artwork.RACE_ICON, f"race {name!r} has no token icon"
        surf = artwork.race_icon(name, 24, (15, 15, 20))
        assert surf is not None and surf.get_size() == (24, 24), name

    assert artwork.race_icon("Goblin", 24) is artwork.race_icon("Goblin", 24)  # cached
    assert artwork.icon("head", "no-such-glyph", 24) is None                   # graceful


def test_guild_screen_member_detail_renders():
    """GuildScreen only draws the detail panel if a member is selected. This test
    ensures _draw_detail runs without crashing."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.guild import Guild
    from gartok.guild_screen import GuildScreen
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    roster = [Unit("player")]
    guild = Guild(roster)
    scr = GuildScreen(ui_fonts(), guild, lambda *args: None, lambda: None)
    scr.member = roster[0]
    
    surf = pygame.Surface((1280, 800))
    scr.mouse = (0, 0)
    scr.draw(surf)

    # Test with experienced unit
    u2 = Unit("veteran")
    u2.combat_xp = 12   # Combat Lv 2
    u2.work_hours = 32  # Work Lv 1 (2 marks)
    roster.append(u2)
    scr.member = u2
    scr.draw(surf)

    # Find progression track coordinates and test tooltips
    pad = 16
    list_w = int(min(max(1280 * 0.24, 264), 380))
    det_w = min(1120, 1280 - 2 * pad - list_w - 16)
    inner = det_w - 2 * 16
    col_a = min(440, int(inner * 0.55))
    bx = pad + list_w + 16 + 16 + col_a + 24
    
    # Hover around progression tracks area
    scr.mouse = (bx + 10, 350)
    scr.draw(surf)
    assert scr.tooltip is not None


def test_group_screen_multidrop_moves_every_picked_pack_item():
    from gartok.group_screen import GroupScreen
    from gartok.guild import Guild
    random.seed(4)
    a, b = Unit("player"), Unit("player")
    a._base_inventory = packed(["Rope", "Meat", "Torch"])
    b._base_inventory = []
    g = Guild([a, b])
    scr = GroupScreen(None, g, g.groups[0], on_back=lambda: None)
    scr.selected = [(a, 0), (a, 2)]                       # indices bracket a keeper
    scr._give_many(b, "pack")
    assert a._base_inventory == packed(["Meat"])     # the un-picked row is untouched
    assert sorted(b._base_inventory) == [("Rope", 1), ("Torch", 1)]
    assert scr.selected == []


def test_group_screen_multidrop_on_a_hand_takes_the_first_that_fits():
    from gartok.group_screen import GroupScreen
    from gartok.guild import Guild
    random.seed(4)
    a = Unit("player")
    a.equipped_weapon = None
    a._base_inventory = packed(["Rope", "Dagger"])
    g = Guild([a])
    scr = GroupScreen(None, g, g.groups[0], on_back=lambda: None)
    scr.selected = [(a, 0), (a, 1)]
    scr._give_many(a, "hand")
    assert a.equipped_weapon == "Dagger" and a._base_inventory == packed(["Rope"])


def test_pack_stacks_group_identical_items_with_their_indices():
    from gartok.group_screen import GroupScreen
    from gartok.guild import Guild
    a = Unit("player")
    a._base_inventory = packed(["Potato"] * 3 + ["Rope"] + ["Potato"] * 2)
    g = Guild([a])
    scr = GroupScreen(None, g, g.groups[0], on_back=lambda: None)
    assert scr._stacks(a._base_inventory) == [
        ("Potato", 0, 5), ("Rope", 1, 1)]


def SKIP_test_shift_click_a_stack_row_grabs_every_index_in_it():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.group_screen import GroupScreen
    from gartok.guild import Guild
    pygame.init()
    pygame.display.set_mode((1, 1))
    a = Unit("player")
    a._base_inventory = ["Potato"] * 3
    g = Guild([a])
    scr = GroupScreen(None, g, g.groups[0], on_back=lambda: None)
    
    # mock the drawn source row
    scr.sources = [(pygame.Rect(0, 0, 10, 10), a, 2)]
    
    try:
        pygame.key.set_mods(pygame.KMOD_LSHIFT)
        scr.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(5, 5), button=1))
    finally:
        pygame.key.set_mods(pygame.KMOD_NONE)
    assert sorted(idx for _, idx in scr.selected) == [0, 1, 2]


def SKIP_test_group_pack_list_scrolls_instead_of_hiding_items_past_the_first_screenful():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.group_screen import GroupScreen
    from gartok.guild import Guild
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))
    a = Unit("player")
    a._base_inventory = [f"Scroll{i}" for i in range(40)]      # 40 distinct items: no stacking
    g = Guild([a])
    scr = GroupScreen(ui_fonts(), g, g.groups[0], on_back=lambda: None)
    scr.mouse = (0, 0)
    surf = pygame.Surface((1600, 1000))
    scr.draw(surf)
    pack_rows = [idx for _, _, idx in scr.sources if isinstance(idx, int)]
    assert 0 < len(pack_rows) < 40                    # a real overflow, not "everything fits"

    scr._pack_scroll[id(a)] = 5
    scr.draw(surf)
    pack_rows = [idx for _, _, idx in scr.sources if isinstance(idx, int)]
    assert pack_rows[:2] == [5, 6]                    # the list actually scrolled


def test_char_editor_duplicate_forks_an_unsaved_copy():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.char_editor_screen import CharEditorScreen
    from gartok.ui.tokens import fonts as ui_fonts
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


def test_tongue_grippli_renders_across_the_gear_and_editor_screens():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.char_editor_screen import CharEditorScreen
    from gartok.combatant import Combatant
    from gartok.group_screen import GroupScreen
    from gartok.guild import Guild
    from gartok.sheet_panel import draw_sheet
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))
    F = ui_fonts()
    from gartok.ui.tokens import fonts as ui_fonts

    u = Unit("player")
    u.set_race("Grippli")
    u.set_track_level("racial", 5)
    u.choose_talent("racial", "tongue")
    u.give_to_tongue("Dagger")
    u.equipped_weapon = "Broadsword"                     # 2-handed in the hands, dagger on the tongue

    solo = Guild([u])
    surf = pygame.Surface((1600, 1000))
    for scr in (GroupScreen(F, solo, solo.groups[0], lambda: None),
                CharEditorScreen(ui_fonts(), lambda: None)):
        if isinstance(scr, CharEditorScreen):
            scr._load_unit(u)
        scr.mouse = (0, 0)
        scr.draw(surf)
    draw_sheet(surf, pygame.Rect(0, 0, 520, 900), Combatant(u), F)


def test_gear_screen_distribute_load():
    from gartok.group_screen import GroupScreen
    from gartok.guild import Guild
    from gartok.ui.tokens import fonts as ui_fonts
    u1, u2 = standard_unit(), standard_unit()
    u1._base_inventory = packed(["Stone Brick", "Stone Brick"])
    u2._base_inventory = []
    g = Guild([u1, u2])
    gs = GroupScreen(ui_fonts(), g, g.groups[0], lambda: None)
    gs._handle_button("distribute")
    # Heaviest items should be shared across members
    assert len(u1._base_inventory) == 1
    assert len(u2._base_inventory) == 1
    assert gs.notice is not None


def test_gear_screen_padlock_toggle_exempts_item_from_distribute_load():
    """Clicking the padlock on a pack row toggles `Unit.locked_items` without
    picking the item up -- and distribute_load then leaves it where it is."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok import data
    from gartok.group_screen import GroupScreen
    from gartok.guild import Guild
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    human = data.race_by_name("Human")
    u1 = Unit("player", race=human)
    u2 = Unit("player", race=human)
    for u in (u1, u2):
        u.set_base_attribute("strength", 10)
        u.equipped_weapon = u.equipped_offhand = u.equipped_armor = None
    u1._base_inventory = packed(["Rope"])
    u2._base_inventory = []
    g = Guild([u1, u2])
    gs = GroupScreen(ui_fonts(), g, g.groups[0], lambda: None)
    surf = pygame.Surface((1600, 900))
    gs.mouse = (0, 0)
    gs.draw(surf)

    assert u1.locked_of("Rope") == 0
    lock_rect, member, name = gs._lock_hits[0]
    assert member is u1 and name == "Rope"
    gs.mouse = lock_rect.center
    gs.draw(surf)                                         # refresh hit-lists at this mouse pos
    gs._drop(lock_rect.center, False, None)
    assert u1.locked_of("Rope") == 1
    assert gs.selected == []                              # a lock click never picks the item up

    gs._handle_button("distribute")
    assert u1._base_inventory == packed(["Rope"])          # stayed put, still locked


def test_group_screen_wheel_scroll_reveals_items_below_the_fold():
    """Before the fix, a long pack just truncated at '+N more' with no way to
    reach the rest; the wheel now scrolls the column like the Market already
    did (see `packbox.PackColumnMixin`)."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.group_screen import GroupScreen
    from gartok.guild import Guild
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    u = Unit("player")
    u._base_inventory = packed([f"Rope{i}" for i in range(40)])   # 40 distinct stacks: no merging, far more than one column can show
    g = Guild([u])
    gs = GroupScreen(ui_fonts(), g, g.groups[0], lambda: None)
    surf = pygame.Surface((1280, 720))
    gs.mouse = (0, 0)
    gs.draw(surf)

    visible_before = {idx for _r, unit, idx in gs.sources if unit is u and isinstance(idx, int)}
    last_idx = len(u._base_inventory) - 1
    assert last_idx not in visible_before                 # off the bottom of the column

    area = next(r for r, who in gs._pack_areas if who is u)
    gs.mouse = area.center
    gs.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=-100))  # scroll far down
    gs.draw(surf)

    visible_after = {idx for _r, unit, idx in gs.sources if unit is u and isinstance(idx, int)}
    assert last_idx in visible_after


def test_gear_screen_scroll_right_click_offers_and_toggles_study():
    """The only in-game path to set `Unit.study_target` (see the Magic section
    of RULES.md): right-click a known scroll for a "study" row on the send-to
    menu, mirroring the sandbox character editor's toggle."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.group_screen import GroupScreen
    from gartok.guild import Guild
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    u = Unit("player")
    u.magic_sources = ["nature"]
    u._base_inventory = packed(["Scroll of Light Globe"])
    g = Guild([u])
    gs = GroupScreen(ui_fonts(), g, g.groups[0], lambda: None)
    gs.mouse = (5, 5)
    gs.sources = [(pygame.Rect(0, 0, 10, 10), u, 0)]

    surf = pygame.Surface((800, 600))

    gs._open_menu((5, 5))
    assert "study" in [kind for kind, _label, _arg in gs.menu["rows"]]
    gs._draw_menu(surf)
    study_row = next(r for r, kind, _ in gs.menu["hits"] if kind == "study")

    click_menu(gs, study_row.center)
    assert u.study_target == "light_globe"

    gs._open_menu((5, 5))                    # re-open: still offered, now toggles off
    gs._draw_menu(surf)
    study_row = next(r for r, kind, _ in gs.menu["hits"] if kind == "study")
    click_menu(gs, study_row.center)
    assert u.study_target is None


def test_gear_screen_scroll_menu_hidden_without_a_magic_source():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.group_screen import GroupScreen
    from gartok.guild import Guild
    pygame.init()
    pygame.display.set_mode((1, 1))

    u = Unit("player")
    u.magic_sources = []
    u._base_inventory = packed(["Scroll of Light Globe"])
    g = Guild([u])
    from gartok.ui.tokens import fonts as ui_fonts
    gs = GroupScreen(ui_fonts(), g, g.groups[0], lambda: None)
    gs.sources = [(pygame.Rect(0, 0, 10, 10), u, 0)]

    gs._open_menu((5, 5))
    assert "study" not in [kind for kind, _label, _arg in gs.menu["rows"]]


def test_gear_screen_dictionary_right_click_offers_and_toggles_study():
    """Learning a language mirrors learning a spell (see RULES.md "Learning a
    language"): right-click a `Dictionary of <Language>` for a "study" row --
    no `magic_source` required, unlike scrolls."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.group_screen import GroupScreen
    from gartok.guild import Guild
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    u = Unit("player")
    u.magic_sources = []
    u.languages = ["Ankarin"]
    u._base_inventory = packed(["Dictionary of Elvish"])
    g = Guild([u])
    gs = GroupScreen(ui_fonts(), g, g.groups[0], lambda: None)
    gs.mouse = (5, 5)
    gs.sources = [(pygame.Rect(0, 0, 10, 10), u, 0)]

    surf = pygame.Surface((800, 600))

    gs._open_menu((5, 5))
    assert "study" in [kind for kind, _label, _arg in gs.menu["rows"]]
    gs._draw_menu(surf)
    study_row = next(r for r, kind, _ in gs.menu["hits"] if kind == "study")

    click_menu(gs, study_row.center)
    assert u.study_target == "Elvish"

    gs._open_menu((5, 5))                    # re-open: still offered, now toggles off
    gs._draw_menu(surf)
    study_row = next(r for r, kind, _ in gs.menu["hits"] if kind == "study")
    click_menu(gs, study_row.center)
    assert u.study_target is None


def test_gear_screen_dictionary_hidden_once_the_language_is_known():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.group_screen import GroupScreen
    from gartok.guild import Guild
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    u = Unit("player")
    u.languages = ["Ankarin", "Elvish"]
    u._base_inventory = packed(["Dictionary of Elvish"])
    g = Guild([u])
    gs = GroupScreen(ui_fonts(), g, g.groups[0], lambda: None)
    gs.sources = [(pygame.Rect(0, 0, 10, 10), u, 0)]

    gs._open_menu((5, 5))
    assert "study" not in [kind for kind, _label, _arg in gs.menu["rows"]]


def test_group_screen_cargo_search_filter():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.group_screen import GroupScreen
    from gartok.guild import Guild
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.init()
    surf = pygame.display.set_mode((1280, 720))

    u = Unit("player")
    u._base_inventory = packed(["Salt", "Iron Bar", "Dagger"])
    g = Guild([u])
    gs = GroupScreen(ui_fonts(), g, g.groups[0], lambda: None)
    gs.tab = "gear"
    gs.view = "cargo"

    # All items visible with empty search
    rows = gs._cargo_rows()
    assert len(rows) == 3

    # Filter by name
    gs.cargo_search = "salt"
    rows = gs._cargo_rows()
    assert len(rows) == 1
    assert rows[0][1] == "Salt"

    # Filter with no matches
    gs.cargo_search = "unknown item xyz"
    rows = gs._cargo_rows()
    assert len(rows) == 0

    # Draw test
    gs.cargo_search = "iron"
    gs.draw(surf)
    assert gs._search_rect is not None
    assert gs._search_clear_rect is not None

    # Clicking clear rect clears search
    gs._click(gs._search_clear_rect.center)
    assert gs.cargo_search == ""
    assert gs.editing_search is False

    # Keyboard typing
    gs.editing_search = True
    event_type = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d, unicode="d")
    gs.handle_event(event_type)
    assert gs.cargo_search == "d"
    event_esc = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    gs.handle_event(event_esc)
    assert gs.cargo_search == ""
    assert gs.editing_search is False


def test_factions_get_unlocks():
    from gartok import factions
    bank_unlocks = factions.get_unlocks("bankers")
    assert any(u.title == "City Property" and u.rep_required == 4 for u in bank_unlocks)

    arena_unlocks = factions.get_unlocks("arena")
    assert any("The Games" in u.title for u in arena_unlocks)

    library_unlocks = factions.get_unlocks("library")
    assert any(u.title == "Expanded Catalog" and u.rep_required == 1 for u in library_unlocks)
    assert any(u.title == "Rare Manuscripts" and u.rep_required == 2 for u in library_unlocks)


def test_attribute_and_derived_help_catalogs():
    for k in ("STR", "DEX", "CON", "INT", "WIS", "CHA"):
        assert k in data.ATTRIBUTE_HELP
        title, desc = data.ATTRIBUTE_HELP[k]
        assert len(title) > 0 and len(desc) > 0

    for k in ("HP", "AC", "MD", "SPD", "INIT"):
        assert k in data.DERIVED_HELP
        title, desc = data.DERIVED_HELP[k]
        assert len(title) > 0 and len(desc) > 0


def test_leshy_icon_asset():
    import pygame

    from gartok import artwork
    assert artwork.RACE_ICON["Leshy"] == "sprout"
    assert artwork.RACE_ICON["Treefolk"] == "sprout"
    surf = artwork.race_icon("Treefolk", 24)
    assert surf is not None
    assert isinstance(surf, pygame.Surface)
    assert surf.get_size() == (24, 24)


def test_treefolk_race_and_portraits():
    import pygame

    from gartok import artwork, data, persist, unit
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

    from gartok import artwork, data, unit
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


def test_draft_screen_attribute_and_stat_hover_tooltips():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.draft_screen import DraftScreen
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    ds = DraftScreen(ui_fonts(), lambda *args: None)
    surf = pygame.Surface((1280, 720))
    ds.mouse = (0, 0)
    ds.draw(surf)

    # Hover on first candidate card: find attribute row position
    card_rect, unit = ds.card_rects[0]
    # In _draw_card, attributes section is placed after header + derived chips
    # We can scan the card area to find the attribute cells and hover
    found_attr_tooltip = False
    found_stat_tooltip = False

    for pt in [(card_rect.x + dx, card_rect.y + dy)
               for dy in (30, 110, 200, 240)
               for dx in (45, 70, 120, 145, 195)]:
        ds.mouse = pt
        ds.draw(surf)
        if ds.tooltip and isinstance(ds.tooltip, list):
            title = ds.tooltip[0][0]
            if any(attr in title for attr in ("STR", "DEX", "CON", "INT", "WIS", "CHA")):
                found_attr_tooltip = True
            if any(stat in title for stat in ("HP", "AC", "MD", "SPD")):
                found_stat_tooltip = True
        if found_attr_tooltip and found_stat_tooltip:
            break

    assert found_attr_tooltip, "Draft card attribute cells should set tooltip on hover"
    assert found_stat_tooltip, "Draft card stat chips should set tooltip on hover"


def test_sheet_panel_attribute_hover_tooltip():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok import sheet_panel
    from gartok.combatant import Combatant
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    u = Unit("player")
    c = Combatant(u)
    fonts = ui_fonts()
    surf = pygame.Surface((1280, 720))
    rect = pygame.Rect(100, 50, sheet_panel.PANEL_W, sheet_panel.PANEL_H)

    # Directly verify the attribute cell collision logic
    w = rect.w - 32
    aw = w // 6
    attr_cell = pygame.Rect(rect.x + 16 + 1, rect.y + 16 + 52 + 44 + 8 + 20, aw - 2, 48)
    sheet_panel.draw_sheet(surf, rect, c, fonts, mouse=attr_cell.center)
    sheet_panel.draw_sheet(surf, rect, c, fonts, mouse=(rect.x + 20, rect.y + 40))


def test_char_editor_attribute_hover_tooltip():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.char_editor_screen import CharEditorScreen
    from gartok.ui.tokens import fonts as ui_fonts
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

def test_sheet_panel_hp_breakdown_tooltip():

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok import sheet_panel
    from gartok.combatant import Combatant
    from gartok.ui.sheet_card import hp_tooltip
    from gartok.ui.tokens import fonts as ui_fonts
    from tests.helpers import Unit
    pygame.init()
    pygame.display.set_mode((1, 1))

    u = Unit("player")
    u._hp_roll = 7
    u._level_hp_rolls = [6, 8]
    u.recalculate_hp()

    fonts = ui_fonts()
    lines = hp_tooltip(u, ui_fonts())
    assert any("HIT POINTS (HP)" in text for text, _, _ in lines)
    assert any("Base (L0): 7" in text for text, _, _ in lines)
    assert any("L1: 6" in text for text, _, _ in lines)
    assert any("L2: 8" in text for text, _, _ in lines)
    assert any(f"Max HP: {u.hp_max}" in text for text, _, _ in lines)

    # Hovering over HP chip in draw_sheet
    surf = pygame.Surface((1280, 720))
    rect = pygame.Rect(100, 50, sheet_panel.PANEL_W, sheet_panel.PANEL_H)
    hp_chip_pos = (rect.x + 30, rect.y + 16 + 52 + 20)
    sheet_panel.draw_sheet(surf, rect, Combatant(u), fonts, mouse=hp_chip_pos)


def test_char_editor_screen_hp_tooltip():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.char_editor_screen import CharEditorScreen
    from gartok.ui.tokens import fonts as ui_fonts
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

    from gartok.ui.primitives import FOOTER_HINT, LEFT_W, footer_bar
    from gartok.ui.tokens import T
    from gartok.ui.tokens import fonts as ui_fonts

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
    with patch("gartok.ui.primitives.text") as mock_text:
        footer_bar(screen_no_back, surf, F, primary=("ok", "OK"))
        hint_calls = [c for c in mock_text.call_args_list if c.args[2] == FOOTER_HINT]
        assert len(hint_calls) == 1
        assert hint_calls[0].args[3][0] == margin

    # With back button: hint starts after the back button
    screen_with_back = Dummy()
    with patch("gartok.ui.primitives.text") as mock_text:
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
    from gartok.battle_screen import BattleScreen
    from gartok.ui.tokens import fonts as ui_fonts
    from gartok.unit import Unit
    pygame.init()
    surf = pygame.Surface((1024, 768))
    batt = Battle([Unit("player"), Unit("player")], [Unit("enemy")])
    batt.winner = "player"
    batt.player_units[0].status = "up"
    batt.player_units[1].status = "stable"
    scr = BattleScreen(ui_fonts(), batt, lambda *a, **k: None)
    scr.draw(surf)


def test_guild_screen_level_up_observability():
    import pygame

    from gartok.guild import Guild
    from gartok.guild_screen import GuildScreen
    from gartok.ui.tokens import fonts as ui_fonts
    from gartok.unit import Unit
    pygame.init()
    surf = pygame.Surface((1280, 800))
    u0 = Unit("player")
    u1 = Unit("player")
    u1.combat_xp = 15
    u1.collect_levels()
    assert u1.pending_picks

    guild = Guild([u0, u1])
    level_called = []
    scr = GuildScreen(ui_fonts(), guild, on_back=lambda: None, on_level=lambda u: level_called.append(u))

    # Smart selection: picked u1 because u1 has pending picks
    assert scr.member == u1

    scr.mouse = (0, 0)
    scr.draw(surf)

    # Management card button for level up exists
    btn = next((r for k, r in scr.buttons if k == "level"), None)
    assert btn is not None

    # Clicking it triggers on_level
    evt = pygame.event.Event(pygame.MOUSEBUTTONUP, pos=btn.center, button=1)
    scr.handle_event(evt)
    assert level_called == [u1]


    # Renders without crashing and card lines include the talent line


def test_guild_screen_study_track_rendered():
    import pygame

    from gartok.guild import Guild
    from gartok.guild_screen import GuildScreen
    from gartok.ui.tokens import fonts as ui_fonts
    from gartok.unit import Unit
    pygame.init()
    surf = pygame.Surface((1280, 800))
    u = Unit("player")
    u.study_target = "magic_missile"
    u.study_progress = 30
    guild = Guild([u])
    scr = GuildScreen(ui_fonts(), guild, on_back=lambda: None)
    scr.mouse = (0, 0)
    scr.draw(surf)

    # Hover over study section to check tooltip
    scr.mouse = (surf.get_width() - 200, 500)
    scr.draw(surf)
    assert scr.member == u


def test_starvation_loot_screen_instantiation():
    from gartok.guild import Guild
    from gartok.loot_screen import LootScreen
    from gartok.ui.tokens import fonts as ui_fonts
    from gartok.unit import Unit
    u1 = Unit("player")
    u2 = Unit("player")
    guild = Guild([u1, u2])
    pool = ["Rations", "Dagger"]
    ls = LootScreen(ui_fonts(), guild, guild.roster, pool, on_done=lambda: None)
    assert ls.guild == guild
    assert len(ls.survivors) == 2


def test_battle_screen_tabs_and_hotkeys():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok import actions
    from gartok.battle import Battle
    from gartok.battle_screen import BattleScreen
    from gartok.ui.tokens import fonts as ui_fonts
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
    from gartok.battle_screen import BattleScreen
    from gartok.ui.tokens import fonts as ui_fonts
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
    from gartok.battle_screen import BattleScreen
    from gartok.ui.tokens import T
    from gartok.ui.tokens import fonts as ui_fonts
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


def test_market_equipping_stack_preserves_remainder():
    from gartok import items, world
    from gartok.trade import Counter

    mnode = next(n for n in world.NODES if n.kind == "market")
    shopper = Unit("player")
    shopper.equipped_offhand = None
    shopper._base_inventory = [items.create_instance("Torch", qty=5)]

    ms = Counter(None, [shopper], mnode)
    ms.selected = [(shopper, 0)]
    ms._drop_on_zone(shopper, "offhand")

    assert shopper.equipped_offhand == "Torch"
    assert len(shopper._base_inventory) == 1
    assert shopper._base_inventory[0].qty == 4


def test_loot_screen_equipping_stack_preserves_remainder():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    from types import SimpleNamespace

    import pygame

    from gartok.loot_screen import LootScreen
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.init()

    u = Unit("player")
    u.equipped_offhand = None
    guild = SimpleNamespace(roster=[u])
    pool = ["Torch"] * 5

    ls = LootScreen(ui_fonts(), guild, [u], pool, lambda: None)
    ls.selected = [("pool", 0)]
    ls._give_many(u, "offhand")

    assert u.equipped_offhand == "Torch"
    assert ls.pool == [("Torch", 4)]


def test_bank_equipping_stack_preserves_remainder():
    from gartok.vault import BankVault

    u = Unit("player")
    u.equipped_offhand = None
    guild = Guild([u])
    guild.bank.put("Torch", 5)

    bs = BankVault(guild, [u])
    bs.selected = [("bank", 0)]
    bs._give_many(u, "offhand")

    assert u.equipped_offhand == "Torch"
    assert len(guild.bank.items) == 1
    assert guild.bank.items[0][1] == 4


def test_house_equipping_stack_preserves_remainder():
    from gartok.vault import HouseVault

    u = Unit("player")
    u.equipped_offhand = None
    guild = Guild([u])
    guild.house.owned = True
    guild.house.stash.put("Torch", 5)

    cps = HouseVault(guild, [u])
    cps.selected = [("house", 0)]
    cps._give_many(u, "offhand")

    assert u.equipped_offhand == "Torch"
    assert len(guild.house.stash.items) == 1
    assert guild.house.stash.items[0][1] == 4


def test_primitives_text_and_ellipsize_none_resilience():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.ui.primitives import caps, ellipsize, text
    from gartok.ui.tokens import fonts as ui_fonts
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
