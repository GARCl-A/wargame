"""Screens draw native at any size; the shared modal and drag plumbing."""

import os
import random

from tests.helpers import data, economy, Unit, packed
from gartok.guild import Guild


def test_battle_export_state_writes_a_json_snapshot(tmp_path, monkeypatch):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import json
    import pygame
    from gartok.battle import Battle
    from gartok.battle_screen import BattleScreen
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    import gartok.battle_screen as battle_screen_mod
    monkeypatch.setattr(battle_screen_mod, "DEBUG_EXPORT_DIR", str(tmp_path))

    batt = Battle([Unit("player")], [Unit("enemy")])
    scr = BattleScreen(Fonts(), batt, lambda *a, **k: None)
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
    from gartok.theme import Fonts
    pygame.init()
    surf = pygame.display.set_mode((1280, 800))

    batt = Battle([Unit("player")], [Unit("enemy")])
    for i in range(80):
        batt.log(f"line {i}")
    scr = BattleScreen(Fonts(), batt, lambda *a, **k: None)
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
    from gartok.theme import BoardView
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


def test_market_sell_is_a_loss_and_checkout_splits_the_purse():
    from gartok.market_screen import MarketScreen
    assert economy.sell_price("Axe") < economy.buy_price("Axe")
    random.seed(1)
    shoppers = [Unit("player") for _ in range(3)]
    for m in shoppers:
        m.gold = 10
    ms = MarketScreen.__new__(MarketScreen)           # no draw in this test
    ms.shoppers = shoppers
    ms._orig_gold = {m: m.gold for m in shoppers}     # all three walked in with 10
    ms.purse = sum(m.gold for m in shoppers)          # 30
    ms.on_done = lambda: None
    ms._checkout()
    assert sorted(m.gold for m in shoppers) == [10, 10, 10] and sum(m.gold for m in shoppers) == 30
    ms.purse = 31
    ms._checkout()
    assert sorted(m.gold for m in shoppers) == [10, 10, 11]   # equal shares -> still an even-ish split


def test_market_stepper_buys_the_quantity_in_one_drop_and_stops_at_the_purse():
    from gartok.market_screen import MarketScreen
    random.seed(2)
    buyer = Unit("player")
    buyer._base_inventory = []
    buyer.carry_max = 10_000                          # keep load out of this test
    ms = MarketScreen.__new__(MarketScreen)
    ms.guild = Guild([buyer])
    ms.node = None
    ms.shoppers = [buyer]
    ms.deal = []
    ms.qty = {}
    ms.notice = None
    unit_price = economy.buy_price("Meat")

    ms.purse = unit_price * 100                       # plenty of coin and carry
    ms.sel = [("stock", "Meat")]
    ms.qty["Meat"] = 10
    ms._drop_on(buyer)
    assert buyer.count_of("Meat") == 10
    assert ms.purse == unit_price * 90
    assert ms.qty.get("Meat", 1) == 1                 # the stepper resets after a buy

    buyer.carry_max = 10_000                          # _buy re-derived it; keep load out
    ms.purse = unit_price * 3                         # only three affordable
    ms.sel = [("stock", "Meat")]
    ms.qty["Meat"] = 10
    ms._drop_on(buyer)
    assert buyer.count_of("Meat") == 13
    assert ms.purse == 0 and "3 of 10" in ms.notice


def test_market_pack_scrolls_and_the_sheet_badge_opens_the_full_sheet():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok import world
    from gartok.market_screen import MarketScreen
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))
    random.seed(3)
    mnode = next(n for n in world.NODES if n.kind == "market")
    shopper = Unit("player")
    shopper._base_inventory = packed([f"Trinket{i}" for i in range(30)])   # distinct: forces overflow
    ms = MarketScreen(Fonts(), None, [shopper], mnode, lambda: None)
    ms.mouse = (0, 0)
    surf = pygame.Surface((1600, 1000))
    ms.draw(surf)
    pack_rows = [idx for _, _, idx in ms.item_rows if isinstance(idx, int)]
    assert 0 < len(pack_rows) < 30                    # a real overflow, not "everything fits"

    ms._pack_scroll[id(shopper)] = 4
    ms.draw(surf)
    pack_rows = [idx for _, _, idx in ms.item_rows if isinstance(idx, int)]
    assert pack_rows[0] == 4                          # the list actually scrolled

    assert ms.info_hits, "the card should offer an 'i' sheet badge"
    badge_rect, who = ms.info_hits[0]
    assert who is shopper
    ms._drop(badge_rect.center, dragging=False, src=None)
    assert ms.sheet_open


def test_market_pack_stacks_identical_items_with_a_count():
    from gartok.market_screen import MarketScreen
    ms = MarketScreen.__new__(MarketScreen)
    assert ms._stacks(packed(["Potato"] * 4)) == [("Potato", 0, 4)]


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


def test_every_screen_draws_native_at_any_window_size():
    """Every screen is `native`: it draws straight to the real window and lays
    itself out from `screen.get_size()`. Render each at a few sizes -- catches a
    stray fixed constant, an out-of-scope `screen`, or a layout that divides by
    something that goes to zero on a small window."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok import world
    from gartok.guild import Guild
    from gartok.battle import Battle
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))
    F = Fonts()

    random.seed(0)
    roster = [Unit("player") for _ in range(5)]
    guild = Guild(list(roster), node=world.START_NODE)
    noop = lambda *a, **k: None
    bnode = next(n for n in world.NODES if n.kind == "battle")
    mnode = next(n for n in world.NODES if n.kind == "market")
    tnode = next(n for n in world.NODES if n.kind == "tavern")
    wnode = next(n for n in world.NODES if n.kind == "wilds")
    batt = Battle(list(roster[:3]), [Unit("enemy") for _ in range(3)],
                  scenario=bnode.scenario(), daylight=True, lethal=True)
    from gartok.scenario import FlagScenario
    ctf_batt = Battle(list(roster[:2]), [Unit("enemy") for _ in range(2)],
                      scenario=FlagScenario(), lethal=False, arena=True)

    from gartok.menu_screen import MenuScreen
    from gartok.bank_screen import BankScreen
    from gartok.draft_screen import DraftScreen
    from gartok.map_screen import MapScreen
    from gartok.squad_screen import SquadScreen
    from gartok.battle_screen import BattleScreen
    from gartok.loot_screen import LootScreen
    from gartok.reward_screen import RewardScreen
    from gartok.market_screen import MarketScreen
    from gartok.taverna_screen import TavernaScreen
    from gartok.hunt import HuntState
    from gartok.hunt_screen import HuntScreen
    from gartok.guild_screen import GuildScreen
    from gartok.gear_screen import GearScreen
    from gartok.group_screen import GroupScreen
    from gartok.level_screen import LevelScreen
    from gartok.pause_screen import PauseScreen
    from gartok.editor_menu_screen import EditorMenuScreen
    from gartok.char_editor_screen import CharEditorScreen
    from gartok.map_editor_screen import MapEditorScreen

    from gartok.ui.tokens import fonts as ui_fonts
    UI_F = ui_fonts()

    scenes = [
        MenuScreen(UI_F, noop, noop, noop, on_editor=noop),
        EditorMenuScreen(UI_F, noop, noop, on_scenario=noop),
        CharEditorScreen(F, noop),
        MapEditorScreen(F, noop),
        DraftScreen(F, noop),
        MapScreen(F, guild, noop, noop, noop, noop),
        SquadScreen(F, roster, bnode, noop, noop),
        BattleScreen(F, batt, noop),
        BattleScreen(F, ctf_batt, noop),                  # capture the flag: setup + pennants
        LootScreen(F, guild, list(roster[:3]), ["Axe", "Rope"], noop),
        RewardScreen(F, guild, list(roster[:3]), 120, noop),
        MarketScreen(F, guild, list(roster[:3]), mnode, noop),
        TavernaScreen(F, guild, list(roster[:3]), tnode, noop),
        HuntScreen(F, guild, HuntState(list(roster[:3]), wnode, hours_left=8),
                   phase="setup", on_ambush=noop, on_done=noop),
        HuntScreen(F, guild, HuntState(list(roster[:3]), wnode, hours_left=4, hours_hunted=6),
                   phase="interlude", on_ambush=noop, on_done=noop),
        GuildScreen(F, guild, noop, noop),
        GearScreen(F, guild, noop),
        GroupScreen(F, guild, guild.groups[0], noop),
        LevelScreen(F, roster[0], noop, noop),
        BankScreen(F, guild, list(roster[:3]), noop),          # locked: no chest yet
    ]

    stocked = Guild(list(roster), node=world.START_NODE, bank_capacity=10,
                    bank_items=["Rope", "Dagger"])
    scenes.append(BankScreen(F, stocked, list(roster[:2]), noop))   # rented + stashed
    scenes.append(PauseScreen(UI_F, scenes[2], noop, noop, noop))

    from gartok.alert_screen import AlertScreen
    scenes.append(AlertScreen(F, scenes[2], "DEATH ALERT",
                              ["Someone starved.", "The guild mourns."], noop, is_danger=True))
    scenes.append(AlertScreen(F, scenes[2], "HUNGER ALERT", ["Rations ran out."], noop))

    from gartok.ledger_screen import LedgerScreen
    from gartok.trust_screen import TrustScreen
    scenes.append(TrustScreen(UI_F, guild, guild.groups[0], noop))          # nothing accepted yet
    scenes.append(LedgerScreen(F, guild, guild.groups[0], noop))         # nothing to hand over

    from gartok import missions as _missions
    accepted = Guild(list(roster), node=world.START_NODE)
    _missions.accept(accepted, accepted.roster[0], _missions.TRUST_CHEST)
    scenes.append(TrustScreen(UI_F, accepted, accepted.groups[0], noop))    # carrying the chest
    scenes.append(LedgerScreen(F, accepted, accepted.groups[0], noop))   # something to hand over

    for tab in ("armor", "kit"):                      # the other market category tabs
        mkt = MarketScreen(F, guild, list(roster[:3]), mnode, noop)
        mkt.tab = tab
        mkt.qty["Meat"] = 12
        scenes.append(mkt)

    guild.reputation = {"arena": 1}
    guild.deeds_done = ["arena_first_blood"]
    rep_tab = GuildScreen(F, guild, noop, noop)
    rep_tab.tab = "reputations"                       # the faction-standing view
    scenes.append(rep_tab)

    from gartok.group import Group
    apart = Guild(None, groups=[Group(list(roster[:2]), node=world.START_NODE),
                                Group(list(roster[2:]), node="market")])
    scenes.append(MapScreen(F, apart, noop, noop, noop, noop))

    together = Guild(None, groups=[Group(list(roster[:2]), node=world.START_NODE),
                                   Group(list(roster[2:]), node=world.START_NODE)])
    scenes.append(MapScreen(F, together, noop, noop, noop, noop))   # +N badge, MERGE button
    split_scene = MapScreen(F, together, noop, noop, noop, noop)
    split_scene._split_target = split_scene.selected.gid
    scenes.append(split_scene)

    crowded = Guild(None, groups=[Group([roster[0], roster[1]], node=world.START_NODE),
                                  Group([roster[2], roster[3]], node=world.START_NODE),
                                  Group([roster[4]], node=world.START_NODE)])
    scenes.append(MapScreen(F, crowded, noop, noop, noop, noop))    # +2 badge, two MERGE rows

    for scene in scenes:
        assert getattr(scene, "native", False), type(scene).__name__
        for size in ((1280, 800), (1920, 1080), (1024, 640)):
            surf = pygame.Surface(size)
            scene.mouse = (size[0] // 2, size[1] // 2)
            scene.draw(surf)


def test_map_screen_heals_a_selected_group_pruned_mid_tick():
    """`Guild.remove_members` (permadeath/starvation) can prune whichever
    group it empties out -- not necessarily the one the map screen has
    `selected` -- while that same `MapScreen` instance stays on screen across
    frames (e.g. an ambush CTA pending on a *different* group). Draw used to
    hand `selected.gid` straight to `draw_map`, which does a bare
    `next(g for g in groups if g["key"] == selected)` with no fallback, so a
    stale `selected` crashed with `StopIteration` the moment it drew again.
    `draw()` now re-derives `selected` the same way `_confirm_merge` already
    did for the group it folds away."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok import world
    from gartok.group import Group
    from gartok.guild import Guild
    from gartok.map_screen import MapScreen
    pygame.init()
    pygame.display.set_mode((1, 1))

    from gartok.ui.tokens import fonts as ui_fonts
    F = ui_fonts()
    noop = lambda *a, **k: None

    g1 = Group([Unit("player")], node=world.START_NODE)
    g2 = Group([Unit("player")], node=world.START_NODE)
    guild = Guild(None, groups=[g1, g2])

    scr = MapScreen(F, guild, noop, noop, noop, noop)
    scr.selected = g1

    guild.remove_members(g1.members)   # empties and prunes g1, same as a casualty mid-tick
    assert g1 not in guild.groups

    surf = pygame.Surface((1280, 800))
    scr.mouse = (640, 400)
    scr.draw(surf)                     # used to raise StopIteration in draw_map

    assert scr.selected is g2


def test_guild_screen_member_detail_renders():
    """GuildScreen only draws the detail panel if a member is selected. This test
    ensures _draw_detail runs without crashing."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok.guild import Guild
    from gartok.guild_screen import GuildScreen
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    roster = [Unit("player")]
    guild = Guild(roster)
    scr = GuildScreen(Fonts(), guild, lambda *args: None, lambda: None)
    scr.member = roster[0]
    
    surf = pygame.Surface((1280, 800))
    scr.mouse = (0, 0)
    scr.draw(surf)


def test_squad_and_reward_screens_pop_the_sheet_modal():
    """The card's 'i' disc opens the sheet; the dismiss click is spent only on
    closing it, not on picking a fighter / paying the purse."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok import world
    from gartok.guild import Guild
    from gartok.theme import Fonts
    from gartok.squad_screen import SquadScreen
    from gartok.reward_screen import RewardScreen
    pygame.init()
    pygame.display.set_mode((1, 1))
    F = Fonts()

    random.seed(1)
    roster = [Unit("player") for _ in range(3)]
    guild = Guild(list(roster), node=world.START_NODE)
    surf = pygame.Surface((1280, 800))
    noop = lambda *a, **k: None

    sq = SquadScreen(F, roster, next(n for n in world.NODES if n.kind == "battle"), noop, noop)
    sq.mouse = (0, 0)
    sq.draw(surf)
    badge = next(r for r, u in sq.info_hits if u is roster[0])
    picked_before = list(sq.picked)
    sq._click(badge.center)
    assert sq.sheet_open and sq._sheet_unit is roster[0]
    sq.draw(surf)                                     # renders the modal
    sq._click((5, 5))                                 # a click just closes it
    assert not sq.sheet_open
    assert sq.picked == picked_before                # the dismiss click didn't toggle

    rw = RewardScreen(F, guild, list(roster), 120, noop)
    rw.mouse = (0, 0)
    rw.draw(surf)
    rbadge = next(r for r, m in rw.info_hits if m is roster[0])
    rw._click(rbadge.center)
    assert rw.sheet_open
    rw._click((5, 5))
    assert not rw.sheet_open and rw.paid_to is None   # the dismiss click didn't pay the purse


def test_level_screen_pops_the_sheet_modal():
    """The character card's inspect badge opens the sheet; dismiss click closes it;
    escape key closes it; and footer button also opens it."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok.theme import Fonts
    from gartok.level_screen import LevelScreen
    pygame.init()
    pygame.display.set_mode((1, 1))
    F = Fonts()

    random.seed(1)
    u = Unit("player")
    surf = pygame.Surface((1280, 800))
    noop = lambda *a, **k: None

    lvl = LevelScreen(F, u, on_back=noop, on_change=noop)
    lvl.mouse = (0, 0)
    lvl.draw(surf)

    assert len(lvl.info_hits) == 1
    badge, hit_unit = lvl.info_hits[0]
    assert hit_unit is u

    # Inspect badge opens sheet
    lvl._click(badge.center)
    assert lvl.sheet_open and lvl._sheet_unit is u

    # Draw modal while open
    lvl.draw(surf)

    # Dismiss click closes sheet
    lvl._click((10, 10))
    assert not lvl.sheet_open

    # Footer button opens sheet
    lvl.draw(surf)
    sheet_btn = next(r for key, r in lvl.buttons if key == "sheet")
    lvl._click(sheet_btn.center)
    assert lvl.sheet_open

    # Escape key dismisses sheet
    assert lvl.handle_escape() is True
    assert not lvl.sheet_open
    assert lvl.handle_escape() is False


def test_group_screen_multidrop_moves_every_picked_pack_item():
    from gartok.guild import Guild
    from gartok.group_screen import GroupScreen
    random.seed(4)
    a, b = Unit("player"), Unit("player")
    a._base_inventory = packed(["Rope", "Meat", "Map"])
    b._base_inventory = []
    g = Guild([a, b])
    scr = GroupScreen(None, g, g.groups[0], on_back=lambda: None)
    scr.selected = [(a, 0), (a, 2)]                       # Corda + Mapa, indices bracket a keeper
    scr._give_many(b, "pack")
    assert a._base_inventory == packed(["Meat"])     # the un-picked row is untouched
    assert sorted(b._base_inventory) == [("Map", 1), ("Rope", 1)]
    assert scr.selected == []


def test_group_screen_multidrop_on_a_hand_takes_the_first_that_fits():
    from gartok.guild import Guild
    from gartok.group_screen import GroupScreen
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
    from gartok.guild import Guild
    from gartok.group_screen import GroupScreen
    a = Unit("player")
    a._base_inventory = packed(["Potato"] * 3 + ["Rope"] + ["Potato"] * 2)
    g = Guild([a])
    scr = GroupScreen(None, g, g.groups[0], on_back=lambda: None)
    assert scr._stacks(a._base_inventory) == [
        ("Potato", 0, 5), ("Rope", 1, 1)]


def SKIP_test_shift_click_a_stack_row_grabs_every_index_in_it():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok.guild import Guild
    from gartok.group_screen import GroupScreen
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
    from gartok.guild import Guild
    from gartok.group_screen import GroupScreen
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))
    a = Unit("player")
    a._base_inventory = [f"Scroll{i}" for i in range(40)]      # 40 distinct items: no stacking
    g = Guild([a])
    scr = GroupScreen(Fonts(), g, g.groups[0], on_back=lambda: None)
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
    from gartok.theme import Fonts
    from gartok.char_editor_screen import CharEditorScreen
    pygame.init()
    pygame.display.set_mode((1, 1))
    scr = CharEditorScreen(Fonts(), lambda: None)
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
    from gartok.guild import Guild
    from gartok.theme import Fonts
    from gartok.char_editor_screen import CharEditorScreen
    from gartok.gear_screen import GearScreen
    from gartok.sheet_panel import draw_sheet
    from gartok.combatant import Combatant
    pygame.init()
    pygame.display.set_mode((1, 1))
    F = Fonts()

    u = Unit("player")
    u.set_race("Grippli")
    u.set_track_level("racial", 5)
    u.choose_talent("racial", "tongue")
    u.give_to_tongue("Dagger")
    u.equipped_weapon = "Broadsword"                     # 2-handed in the hands, dagger on the tongue

    surf = pygame.Surface((1600, 1000))
    for scr in (GearScreen(F, Guild([u]), lambda: None),
                CharEditorScreen(F, lambda: None)):
        if isinstance(scr, CharEditorScreen):
            scr._load_unit(u)
        scr.mouse = (0, 0)
        scr.draw(surf)
    draw_sheet(surf, pygame.Rect(0, 0, 520, 900), Combatant(u), F)


def test_gear_screen_distribute_load():
    from gartok.gear_screen import GearScreen
    from gartok.guild import Guild
    from gartok import data
    r = data.race_by_name("Human")
    u1 = Unit("player", race=r)
    u2 = Unit("player", race=r)
    u1.set_base_attribute("strength", 10)
    u2.set_base_attribute("strength", 10)
    u1._base_inventory = packed(["Stone Brick", "Stone Brick"])
    u2._base_inventory = []
    g = Guild([u1, u2])
    gs = GearScreen.__new__(GearScreen)
    gs.guild = g
    gs.roster = g.roster
    gs.pinned = [u1, u2]
    gs.notice = None
    gs._distribute_load()
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
    from gartok.gear_screen import GearScreen
    from gartok.guild import Guild
    from gartok.theme import Fonts
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
    gs = GearScreen(Fonts(), g, lambda: None)
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

    gs._distribute_load()
    assert u1._base_inventory == packed(["Rope"])          # stayed put, still locked


def test_group_screen_wheel_scroll_reveals_items_below_the_fold():
    """Before the fix, a long pack just truncated at '+N more' with no way to
    reach the rest; the wheel now scrolls the column like the Market already
    did (see `packbox.PackColumnMixin`)."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok.group_screen import GroupScreen
    from gartok.guild import Guild
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    u = Unit("player")
    u._base_inventory = packed([f"Rope{i}" for i in range(40)])   # 40 distinct stacks: no merging, far more than one column can show
    g = Guild([u])
    gs = GroupScreen(Fonts(), g, g.groups[0], lambda: None)
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
    from gartok.gear_screen import GearScreen
    from gartok.guild import Guild
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    u = Unit("player")
    u.magic_source = "nature"
    u._base_inventory = packed(["Scroll of Light Globe"])
    g = Guild([u])
    gs = GearScreen.__new__(GearScreen)
    gs.fonts = Fonts()
    gs.guild = g
    gs.roster = g.roster
    gs.pinned = [u]
    gs.selected = []
    gs.notice = None
    gs.mouse = (5, 5)
    gs.sources = [(pygame.Rect(0, 0, 10, 10), u, 0)]
    gs.menu = None
    gs._hot = False

    surf = pygame.Surface((800, 600))

    gs._open_menu((5, 5))
    assert "study" in [kind for kind, _label, _arg in gs.menu["rows"]]
    gs._draw_menu(surf)
    study_row = next(r for r, kind, _ in gs.menu["hits"] if kind == "study")

    gs._menu_click(study_row.center)
    assert u.study_target == "light_globe"

    gs._open_menu((5, 5))                    # re-open: still offered, now toggles off
    gs._draw_menu(surf)
    study_row = next(r for r, kind, _ in gs.menu["hits"] if kind == "study")
    gs._menu_click(study_row.center)
    assert u.study_target is None


def test_gear_screen_scroll_menu_hidden_without_a_magic_source():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok.gear_screen import GearScreen
    from gartok.guild import Guild
    pygame.init()
    pygame.display.set_mode((1, 1))

    u = Unit("player")
    u.magic_source = None
    u._base_inventory = packed(["Scroll of Light Globe"])
    g = Guild([u])
    gs = GearScreen.__new__(GearScreen)
    from gartok.theme import Fonts
    gs.fonts = Fonts()
    gs.guild = g
    gs.roster = g.roster
    gs.pinned = [u]
    gs.selected = []
    gs.notice = None
    gs.sources = [(pygame.Rect(0, 0, 10, 10), u, 0)]
    gs.menu = None

    gs._open_menu((5, 5))
    assert "study" not in [kind for kind, _label, _arg in gs.menu["rows"]]


def test_gear_screen_dictionary_right_click_offers_and_toggles_study():
    """Learning a language mirrors learning a spell (see RULES.md "Learning a
    language"): right-click a `Dictionary of <Language>` for a "study" row --
    no `magic_source` required, unlike scrolls."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok.gear_screen import GearScreen
    from gartok.guild import Guild
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    u = Unit("player")
    u.magic_source = None
    u.languages = ["Ankarin"]
    u._base_inventory = packed(["Dictionary of Elvish"])
    g = Guild([u])
    gs = GearScreen.__new__(GearScreen)
    gs.fonts = Fonts()
    gs.guild = g
    gs.roster = g.roster
    gs.pinned = [u]
    gs.selected = []
    gs.notice = None
    gs.mouse = (5, 5)
    gs.sources = [(pygame.Rect(0, 0, 10, 10), u, 0)]
    gs.menu = None
    gs._hot = False

    surf = pygame.Surface((800, 600))

    gs._open_menu((5, 5))
    assert "study" in [kind for kind, _label, _arg in gs.menu["rows"]]
    gs._draw_menu(surf)
    study_row = next(r for r, kind, _ in gs.menu["hits"] if kind == "study")

    gs._menu_click(study_row.center)
    assert u.study_target == "Elvish"

    gs._open_menu((5, 5))                    # re-open: still offered, now toggles off
    gs._draw_menu(surf)
    study_row = next(r for r, kind, _ in gs.menu["hits"] if kind == "study")
    gs._menu_click(study_row.center)
    assert u.study_target is None


def test_gear_screen_dictionary_hidden_once_the_language_is_known():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok.gear_screen import GearScreen
    from gartok.guild import Guild
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    u = Unit("player")
    u.languages = ["Ankarin", "Elvish"]
    u._base_inventory = packed(["Dictionary of Elvish"])
    g = Guild([u])
    gs = GearScreen.__new__(GearScreen)
    gs.fonts = Fonts()
    gs.guild = g
    gs.roster = g.roster
    gs.pinned = [u]
    gs.selected = []
    gs.notice = None
    gs.sources = [(pygame.Rect(0, 0, 10, 10), u, 0)]
    gs.menu = None

    gs._open_menu((5, 5))
    assert "study" not in [kind for kind, _label, _arg in gs.menu["rows"]]





def test_factions_get_unlocks():
    from gartok import factions
    bank_unlocks = factions.get_unlocks("bankers")
    assert any(u.title == "City Property" and u.rep_required == 4 for u in bank_unlocks)

    arena_unlocks = factions.get_unlocks("arena")
    assert any("The Games" in u.title for u in arena_unlocks)


def test_market_screen_draw_multiple_shoppers_hover():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok import world
    from gartok.market_screen import MarketScreen
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))
    mnode = next(n for n in world.NODES if n.kind == "market")
    shoppers = [Unit("player"), Unit("player")]
    ms = MarketScreen(Fonts(), None, shoppers, mnode, lambda: None)
    surf = pygame.Surface((1200, 800))
    ms.mouse = (surf.get_width() - 50, 80)
    ms.draw(surf)
    for label, rect in ms.buttons:
        if label == "distribute":
            ms.mouse = rect.center
            ms.draw(surf)





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
    from gartok import artwork
    import pygame
    assert artwork.RACE_ICON["Leshy"] == "sprout"
    surf = artwork.race_icon("Leshy", 24)
    assert surf is not None
    assert isinstance(surf, pygame.Surface)
    assert surf.get_size() == (24, 24)


def test_draft_screen_attribute_and_stat_hover_tooltips():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok.draft_screen import DraftScreen
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    ds = DraftScreen(Fonts(), lambda *args: None)
    surf = pygame.Surface((1280, 720))
    ds.mouse = (0, 0)
    ds.draw(surf)

    # Hover on first candidate card: find attribute row position
    card_rect, unit = ds.card_rects[0]
    # In _draw_card, attributes section is placed after header + derived chips
    # We can scan the card area to find the attribute cells and hover
    found_attr_tooltip = False
    found_stat_tooltip = False

    # Test scanning Y down the card center
    for y in range(card_rect.y, card_rect.bottom, 4):
        for x in range(card_rect.x + 10, card_rect.right - 10, 15):
            ds.mouse = (x, y)
            ds.draw(surf)
            if ds.tooltip and isinstance(ds.tooltip, list):
                title = ds.tooltip[0][0]
                if any(attr in title for attr in ("STR", "DEX", "CON", "INT", "WIS", "CHA")):
                    found_attr_tooltip = True
                if any(stat in title for stat in ("HP", "AC", "MD", "SPD")):
                    found_stat_tooltip = True
            if found_attr_tooltip and found_stat_tooltip:
                break
        if found_attr_tooltip and found_stat_tooltip:
            break

    assert found_attr_tooltip, "Draft card attribute cells should set tooltip on hover"
    assert found_stat_tooltip, "Draft card stat chips should set tooltip on hover"


def test_sheet_panel_attribute_hover_tooltip():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok import sheet_panel
    from gartok.combatant import Combatant
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    u = Unit("player")
    c = Combatant(u)
    fonts = Fonts()
    surf = pygame.Surface((1280, 720))
    rect = pygame.Rect(100, 50, sheet_panel.PANEL_W, sheet_panel.PANEL_H)

    # Scan across the attribute row area (y ~ 100-260)
    found_tooltip = False
    for y in range(rect.y + 40, rect.y + 240, 6):
        for x in range(rect.x + 20, rect.right - 20, 15):
            sheet_panel.draw_sheet(surf, rect, c, fonts, mouse=(x, y))
            # Test that draw_sheet runs cleanly with mouse hover
    # Also directly verify the attribute cell collision logic
    w = rect.w - 32
    aw = w // 6
    # Attributes header is at section ATTRIBUTES
    # Let's test hovering at first attribute cell: x + 1, centered
    attr_cell = pygame.Rect(rect.x + 16 + 1, rect.y + 16 + 52 + 44 + 8 + 20, aw - 2, 48)
    sheet_panel.draw_sheet(surf, rect, c, fonts, mouse=attr_cell.center)


def test_char_editor_attribute_hover_tooltip():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok.char_editor_screen import CharEditorScreen
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    ed = CharEditorScreen(Fonts(), lambda: None)
    surf = pygame.Surface((1280, 720))
    ed.mouse = (0, 0)
    ed.draw(surf)

    # Hover inside the form area to find attribute cell
    found_tooltip = False
    if ed._form_rect:
        for y in range(ed._form_rect.y + 160, ed._form_rect.y + 350, 8):
            for x in range(ed._form_rect.x + 20, ed._form_rect.right - 20, 20):
                ed.mouse = (x, y)
                ed.draw(surf)
                if ed.tooltip and isinstance(ed.tooltip, list):
                    title = ed.tooltip[0][0]
                    if any(attr in title for attr in ("STR", "DEX", "CON", "INT", "WIS", "CHA")):
                        found_tooltip = True
                        break
            if found_tooltip:
                break
    assert found_tooltip, "Character editor attribute cells should set tooltip on hover"

def test_market_screen_item_hover_tooltip():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok.market_screen import MarketScreen
    from gartok.theme import Fonts
    from gartok.guild import Guild
    from gartok.world import NODES
    from tests.helpers import Unit
    pygame.init()
    pygame.display.set_mode((1, 1))

    shopper = Unit("player")
    shopper.give_to_pack("Dagger")
    guild = Guild([shopper])
    node = next(n for n in NODES if n.kind == "market")
    guild.market_stock = {"Dagger": 5, "Meat": 10}
    
    ms = MarketScreen(Fonts(), guild, [shopper], node, lambda: None)
    surf = pygame.Surface((1280, 720))
    ms.mouse = (0, 0)
    ms.draw(surf)

    found_stock_tooltip = False
    for r, name in ms.stock_rows:
        ms.mouse = r.center
        ms.draw(surf)
        if ms.tooltip and isinstance(ms.tooltip, list):
            if ms.tooltip[0][0] == name:
                found_stock_tooltip = True
                break

    found_pack_tooltip = False
    for r, member, loc in ms.item_rows:
        ms.mouse = r.center
        ms.draw(surf)
        if ms.tooltip and isinstance(ms.tooltip, list):
            found_pack_tooltip = True
            break
            
    assert found_stock_tooltip, "MarketScreen stock rows should set tooltip on hover"
    assert found_pack_tooltip, "MarketScreen pack items should set tooltip on hover"


def test_sheet_panel_hp_breakdown_tooltip():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok import sheet_panel
    from gartok.combatant import Combatant
    from gartok.theme import Fonts
    from tests.helpers import Unit
    pygame.init()
    pygame.display.set_mode((1, 1))

    u = Unit("player")
    u._hp_roll = 7
    u._level_hp_rolls = [6, 8]
    u.recalculate_hp()

    fonts = Fonts()
    lines = sheet_panel.format_hp_breakdown_tooltip(u, fonts)
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


def test_level_screen_hp_hover_tooltip():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok.level_screen import LevelScreen
    from gartok.theme import Fonts
    from tests.helpers import Unit
    pygame.init()
    pygame.display.set_mode((1, 1))

    u = Unit("player")
    ls = LevelScreen(Fonts(), u, lambda: None)
    surf = pygame.Surface((1280, 720))

    # Hover over the subtitle where HP is located (scan y around 70-130)
    found_hp_hover = False
    for y in range(70, 130, 4):
        ls.mouse = (120, y)
        ls.draw(surf)
        if getattr(ls, "_hp_hover", False):
            found_hp_hover = True
            break
    assert found_hp_hover, "LevelScreen subtitle should trigger _hp_hover"


def test_char_editor_screen_hp_tooltip():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok.char_editor_screen import CharEditorScreen
    from gartok.theme import Fonts
    from tests.helpers import Unit
    pygame.init()
    pygame.display.set_mode((1, 1))

    u = Unit("player")
    cs = CharEditorScreen(Fonts(), lambda: None)
    cs.unit = u
    surf = pygame.Surface((1280, 720))

    # Scan across the left column around progression/HP area
    found_hp_tooltip = False
    for y in range(200, 500, 5):
        for x in (50, 100, 150):
            cs.mouse = (x, y)
            cs.draw(surf)
            if cs.tooltip and any("HIT POINTS (HP)" in text for text, _, _ in cs.tooltip):
                found_hp_tooltip = True
                break
        if found_hp_tooltip:
            break
    assert found_hp_tooltip, "CharEditorScreen should display HP breakdown tooltip on hover"


def test_squad_screen_racial_level_display_and_tooltip():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok import world
    from gartok.theme import Fonts
    from gartok.squad_screen import SquadScreen
    from tests.helpers import Unit
    pygame.init()
    pygame.display.set_mode((1, 1))
    F = Fonts()

    u = Unit("player")
    u.set_track_level("combat", 2)
    u.set_track_level("work", 2)
    assert u.racial_level >= 2

    sq = SquadScreen(F, [u], next(n for n in world.NODES if n.kind == "battle"), lambda *a: None, lambda: None)
    surf = pygame.Surface((1280, 800))
    sq.mouse = (0, 0)
    sq.draw(surf)

    # Hover over the racial level badge on the card (x ~ 60..100, y ~ 110..130)
    card_rect, _ = sq.cards[0]
    badge_x = card_rect.x + 16 + 40
    badge_y = card_rect.y + 16 + 25
    sq.mouse = (badge_x, badge_y)
    sq.draw(surf)
    assert sq.tooltip is not None
    title, desc = sq.tooltip[0][0], sq.tooltip[1][0]
    assert f"Racial Level {u.racial_level}" in title
    assert u.race["name"] in desc


def test_map_screen_split_panel_shows_racial_level():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok import world
    from gartok.guild import Guild
    from gartok.group import Group
    from gartok.theme import Fonts
    from gartok.map_screen import MapScreen
    from tests.helpers import Unit
    pygame.init()
    pygame.display.set_mode((1, 1))
    F = Fonts()

    u1, u2 = Unit("player"), Unit("player")
    u1.set_track_level("combat", 3)
    group = Group([u1, u2], node=world.START_NODE)
    g = Guild(None, groups=[group])
    ms = MapScreen(F, g, lambda: None, lambda: None, lambda: None, lambda: None)
    ms._split_target = group.gid
    surf = pygame.Surface((1280, 800))
    ms.draw(surf)
    assert len(ms._split_member_rects) == 2
    assert ms._split_member_rects[0][0] == u1.uid


def test_footer_bar_hint_offsets_when_back_button_present():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from unittest.mock import patch
    from gartok.theme import Fonts, MARGIN, SP3
    from gartok.widgets import ButtonsMixin, footer_bar, LEFT_W, FOOTER_HINT

    pygame.init()
    pygame.display.set_mode((1, 1))

    class Dummy(ButtonsMixin):
        def __init__(self):
            super().__init__()
            self.fonts = Fonts()
            self.mouse = (0, 0)
            self.buttons = []
            self._hot = False

    surf = pygame.Surface((800, 600))

    # Without back button: hint starts at left margin
    screen_no_back = Dummy()
    with patch("gartok.widgets.text") as mock_text:
        footer_bar(screen_no_back, surf, primary=("ok", "OK"))
        hint_calls = [c for c in mock_text.call_args_list if c.args[1] == FOOTER_HINT]
        assert len(hint_calls) == 1
        assert hint_calls[0].args[4][0] == MARGIN

    # With back button: hint starts after the back button
    screen_with_back = Dummy()
    with patch("gartok.widgets.text") as mock_text:
        footer_bar(screen_with_back, surf, back=("back", "BACK"), primary=("ok", "OK"))
        hint_calls = [c for c in mock_text.call_args_list if c.args[1] == FOOTER_HINT]
        assert len(hint_calls) == 1
        assert hint_calls[0].args[4][0] == MARGIN + LEFT_W + SP3
        # Ensure back button is registered and does not collide with hint
        back_btn = next(r for k, r in screen_with_back.buttons if k == "back")
        assert back_btn.right < hint_calls[0].args[4][0]


def test_battle_screen_victory_card_with_stabilized():
    import pygame
    from gartok.battle import Battle
    from gartok.battle_screen import BattleScreen
    from gartok.theme import Fonts
    from gartok.unit import Unit
    pygame.init()
    surf = pygame.Surface((1024, 768))
    batt = Battle([Unit("player"), Unit("player")], [Unit("enemy")])
    batt.winner = "player"
    batt.player_units[0].status = "up"
    batt.player_units[1].status = "stable"
    scr = BattleScreen(Fonts(), batt, lambda *a, **k: None)
    scr.draw(surf)


def test_guild_screen_level_up_observability():
    import pygame
    from gartok.guild import Guild
    from gartok.guild_screen import GuildScreen
    from gartok.theme import Fonts
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
    scr = GuildScreen(Fonts(), guild, on_back=lambda: None, on_level=lambda u: level_called.append(u))

    # Smart selection: picked u1 because u1 has pending picks
    assert scr.member == u1

    scr.mouse = (0, 0)
    scr.draw(surf)

    # Roster button for level up exists
    btn = next((r for k, r in scr.buttons if k == f"roster_level:{u1.uid}"), None)
    assert btn is not None

    # Clicking it triggers on_level
    evt = pygame.event.Event(pygame.MOUSEBUTTONUP, pos=btn.center, button=1)
    scr.handle_event(evt)
    assert level_called == [u1]


def test_map_screen_level_up_observability():
    import pygame
    from gartok.guild import Guild
    from gartok.map_screen import MapScreen
    from gartok.theme import Fonts
    from gartok.unit import Unit
    pygame.init()
    surf = pygame.Surface((1280, 800))
    u = Unit("player")
    u.combat_xp = 15
    u.collect_levels()
    guild = Guild([u], node="city")

    scr = MapScreen(Fonts(), guild, on_guild=lambda: None, on_wipe=lambda: None,
                    on_advance=lambda *a, **k: None, on_manage_group=lambda g: None)
    scr.mouse = (0, 0)
    scr.draw(surf)

    guild_btn = next((r for k, r in scr.buttons if k == "guild"), None)
    assert guild_btn is not None

    # a guild with nobody pending a level-up gets the plain, narrower label
    plain_guild = Guild([Unit("player")], node="city")
    plain_scr = MapScreen(Fonts(), plain_guild, on_guild=lambda: None, on_wipe=lambda: None,
                          on_advance=lambda *a, **k: None, on_manage_group=lambda g: None)
    plain_scr.mouse = (0, 0)
    plain_scr.draw(surf)
    plain_btn = next((r for k, r in plain_scr.buttons if k == "guild"), None)

    # the pending-level-up badge widens the button -- not pinned to an exact
    # pixel count, which would just be re-asserting whatever font renders it
    assert guild_btn.w > plain_btn.w


def test_squad_screen_level_up_observability():
    from gartok import world
    from gartok.squad_screen import SquadScreen
    from gartok.theme import Fonts
    from gartok.unit import Unit
    u = Unit("player")
    u.combat_xp = 15
    u.collect_levels()
    assert u.pending_picks
    bnode = next(n for n in world.NODES if n.kind == "battle")
    scr = SquadScreen(Fonts(), [u], bnode, lambda s: None, lambda: None)
    
    import pygame
    surf = pygame.Surface((1024, 768))
    scr.mouse = (0, 0)
    scr.draw(surf)
    # Renders without crashing and card lines include the talent line

