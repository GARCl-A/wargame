"""Screens draw native at any size; the shared modal and drag plumbing."""

import os
import random

from tests.helpers import data, economy, Unit


def test_market_sell_is_a_loss_and_checkout_splits_the_purse():
    from gartok.market_screen import MarketScreen
    assert economy.sell_price("Axe") < economy.buy_price("Axe")
    random.seed(1)
    shoppers = [Unit("player") for _ in range(3)]
    for m in shoppers:
        m.gold = 10
    ms = MarketScreen.__new__(MarketScreen)           # no draw in this test
    ms.shoppers = shoppers
    ms.purse = sum(m.gold for m in shoppers)          # 30
    ms.on_done = lambda: None
    ms._checkout()
    assert sorted(m.gold for m in shoppers) == [10, 10, 10] and sum(m.gold for m in shoppers) == 30
    ms.purse = 31
    ms._checkout()
    assert sorted(m.gold for m in shoppers) == [10, 10, 11]


def test_market_stepper_buys_the_quantity_in_one_drop_and_stops_at_the_purse():
    from gartok.market_screen import MarketScreen
    random.seed(2)
    buyer = Unit("player")
    buyer._base_inventory = []
    buyer.carry_max = 10_000                          # keep load out of this test
    ms = MarketScreen.__new__(MarketScreen)
    ms.shoppers = [buyer]
    ms.deal = []
    ms.qty = {}
    ms.notice = None
    unit_price = economy.buy_price("Meat")

    ms.purse = unit_price * 100                       # plenty of coin and carry
    ms.sel = [("stock", "Meat")]
    ms.qty["Meat"] = 10
    ms._drop_on(buyer)
    assert buyer._base_inventory.count("Meat") == 10
    assert ms.purse == unit_price * 90
    assert ms.qty.get("Meat", 1) == 1                 # the stepper resets after a buy

    buyer.carry_max = 10_000                          # _buy re-derived it; keep load out
    ms.purse = unit_price * 3                         # only three affordable
    ms.sel = [("stock", "Meat")]
    ms.qty["Meat"] = 10
    ms._drop_on(buyer)
    assert buyer._base_inventory.count("Meat") == 13
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
    from gartok.draft_screen import DraftScreen
    from gartok.map_screen import MapScreen
    from gartok.squad_screen import SquadScreen
    from gartok.battle_screen import BattleScreen
    from gartok.loot_screen import LootScreen
    from gartok.reward_screen import RewardScreen
    from gartok.market_screen import MarketScreen
    from gartok.taverna_screen import TavernaScreen
    from gartok.work_screen import WorkScreen
    from gartok.hunt import HuntState
    from gartok.hunt_screen import HuntScreen
    from gartok.guild_screen import GuildScreen
    from gartok.gear_screen import GearScreen
    from gartok.level_screen import LevelScreen
    from gartok.pause_screen import PauseScreen
    from gartok.editor_menu_screen import EditorMenuScreen
    from gartok.char_editor_screen import CharEditorScreen
    from gartok.map_editor_screen import MapEditorScreen

    scenes = [
        MenuScreen(F, noop, noop, noop, on_editor=noop),
        EditorMenuScreen(F, noop, noop, on_scenario=noop),
        CharEditorScreen(F, noop),
        MapEditorScreen(F, noop),
        DraftScreen(F, noop),
        MapScreen(F, guild, noop, noop, noop, noop, noop, noop, noop),
        SquadScreen(F, roster, bnode, noop, noop),
        BattleScreen(F, batt, noop),
        BattleScreen(F, ctf_batt, noop),                  # capture the flag: setup + pennants
        LootScreen(F, guild, list(roster[:3]), ["Axe", "Rope"], noop),
        RewardScreen(F, guild, list(roster[:3]), 120, noop),
        MarketScreen(F, guild, list(roster[:3]), mnode, noop),
        TavernaScreen(F, guild, list(roster[:3]), tnode, noop),
        WorkScreen(F, guild, list(roster[:3]), noop, noop),
        HuntScreen(F, guild, HuntState(list(roster[:3]), wnode, hours_left=8),
                   phase="setup", on_ambush=noop, on_done=noop),
        HuntScreen(F, guild, HuntState(list(roster[:3]), wnode, hours_left=4, hours_hunted=6),
                   phase="interlude", on_ambush=noop, on_done=noop),
        GuildScreen(F, guild, noop, noop),
        GearScreen(F, guild, noop),
        LevelScreen(F, roster[0], noop, noop),
    ]
    scenes.append(PauseScreen(F, scenes[2], noop, noop, noop))

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

    for scene in scenes:
        assert getattr(scene, "native", False), type(scene).__name__
        for size in ((1280, 800), (1920, 1080), (1024, 640)):
            surf = pygame.Surface(size)
            scene.mouse = (size[0] // 2, size[1] // 2)
            scene.draw(surf)


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


def test_guild_screen_multidrop_moves_every_picked_pack_item():
    from gartok.guild import Guild
    from gartok.guild_screen import GuildScreen
    random.seed(4)
    a, b = Unit("player"), Unit("player")
    a._base_inventory = ["Rope", "Meat", "Map"]
    b._base_inventory = []
    g = Guild([a, b])
    scr = GuildScreen(None, g, on_back=lambda: None)
    scr.selected = [(a, 0), (a, 2)]                       # Corda + Mapa, indices bracket a keeper
    scr._give_many(b, "pack")
    assert a._base_inventory == ["Meat"]             # the un-picked row is untouched
    assert sorted(b._base_inventory) == ["Map", "Rope"]
    assert scr.selected == []


def test_guild_screen_multidrop_on_a_hand_takes_the_first_that_fits():
    from gartok.guild import Guild
    from gartok.guild_screen import GuildScreen
    random.seed(4)
    a = Unit("player")
    a.equipped_weapon = None
    a._base_inventory = ["Rope", "Dagger"]
    g = Guild([a])
    scr = GuildScreen(None, g, on_back=lambda: None)
    scr.selected = [(a, 0), (a, 1)]
    scr._give_many(a, "hand")
    assert a.equipped_weapon == "Dagger" and a._base_inventory == ["Rope"]
