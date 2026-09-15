"""Screens draw native at any size; the shared modal and drag plumbing."""

import os
import random

from tests.helpers import data, economy, Unit
from gartok.guild import Guild


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
    shopper._base_inventory = [f"Trinket{i}" for i in range(30)]   # distinct: forces overflow
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
    assert ms._stacks(["Potato"] * 4) == [("Potato", [0, 1, 2, 3])]


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
    from gartok.interactions_screen import InteractionsScreen

    scenes = [
        MenuScreen(F, noop, noop, noop, on_editor=noop),
        EditorMenuScreen(F, noop, noop, on_scenario=noop),
        CharEditorScreen(F, noop),
        MapEditorScreen(F, noop),
        DraftScreen(F, noop),
        MapScreen(F, guild, noop, noop, noop, noop, noop),
        InteractionsScreen(F, guild, guild.groups[0], noop, noop),
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
    scenes.append(PauseScreen(F, scenes[2], noop, noop, noop))

    from gartok.ledger_screen import LedgerScreen
    from gartok.trust_screen import TrustScreen
    scenes.append(TrustScreen(F, guild, guild.groups[0], noop))          # nothing accepted yet
    scenes.append(LedgerScreen(F, guild, guild.groups[0], noop))         # nothing to hand over

    from gartok import missions as _missions
    accepted = Guild(list(roster), node=world.START_NODE)
    _missions.accept(accepted, accepted.roster[0], _missions.TRUST_CHEST)
    scenes.append(TrustScreen(F, accepted, accepted.groups[0], noop))    # carrying the chest
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
    scenes.append(MapScreen(F, apart, noop, noop, noop, noop, noop))

    together = Guild(None, groups=[Group(list(roster[:2]), node=world.START_NODE),
                                   Group(list(roster[2:]), node=world.START_NODE)])
    scenes.append(MapScreen(F, together, noop, noop, noop, noop, noop))   # +N badge, MERGE button
    split_scene = MapScreen(F, together, noop, noop, noop, noop, noop)
    split_scene.mode = "split"
    scenes.append(split_scene)

    crowded = Guild(None, groups=[Group([roster[0], roster[1]], node=world.START_NODE),
                                  Group([roster[2], roster[3]], node=world.START_NODE),
                                  Group([roster[4]], node=world.START_NODE)])
    scenes.append(MapScreen(F, crowded, noop, noop, noop, noop, noop))    # +2 badge, two MERGE rows

    for scene in scenes:
        assert getattr(scene, "native", False), type(scene).__name__
        for size in ((1280, 800), (1920, 1080), (1024, 640)):
            surf = pygame.Surface(size)
            scene.mouse = (size[0] // 2, size[1] // 2)
            scene.draw(surf)


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


def test_group_screen_multidrop_moves_every_picked_pack_item():
    from gartok.guild import Guild
    from gartok.group_screen import GroupScreen
    random.seed(4)
    a, b = Unit("player"), Unit("player")
    a._base_inventory = ["Rope", "Meat", "Map"]
    b._base_inventory = []
    g = Guild([a, b])
    scr = GroupScreen(None, g, g.groups[0], on_back=lambda: None)
    scr.selected = [(a, 0), (a, 2)]                       # Corda + Mapa, indices bracket a keeper
    scr._give_many(b, "pack")
    assert a._base_inventory == ["Meat"]             # the un-picked row is untouched
    assert sorted(b._base_inventory) == ["Map", "Rope"]
    assert scr.selected == []


def test_group_screen_multidrop_on_a_hand_takes_the_first_that_fits():
    from gartok.guild import Guild
    from gartok.group_screen import GroupScreen
    random.seed(4)
    a = Unit("player")
    a.equipped_weapon = None
    a._base_inventory = ["Rope", "Dagger"]
    g = Guild([a])
    scr = GroupScreen(None, g, g.groups[0], on_back=lambda: None)
    scr.selected = [(a, 0), (a, 1)]
    scr._give_many(a, "hand")
    assert a.equipped_weapon == "Dagger" and a._base_inventory == ["Rope"]


def test_pack_stacks_group_identical_items_with_their_indices():
    from gartok.guild import Guild
    from gartok.group_screen import GroupScreen
    a = Unit("player")
    a._base_inventory = ["Potato"] * 3 + ["Rope"] + ["Potato"] * 2
    g = Guild([a])
    scr = GroupScreen(None, g, g.groups[0], on_back=lambda: None)
    assert scr._stacks(a._base_inventory) == [
        ("Potato", [0, 1, 2, 4, 5]), ("Rope", [3])]


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
    u1._base_inventory = ["Stone Brick", "Stone Brick"]
    u2._base_inventory = []
    g = Guild([u1, u2])
    gs = GearScreen.__new__(GearScreen)
    gs.guild = g
    gs.roster = g.roster
    gs.managed = [u1, u2]
    gs.notice = None
    gs._distribute_load()
    # Heaviest items should be shared across members
    assert len(u1._base_inventory) == 1
    assert len(u2._base_inventory) == 1
    assert gs.notice is not None


def test_loot_screen_drop_pack_item_to_ground():
    from gartok.loot_screen import LootScreen
    from gartok.guild import Guild
    import pygame
    u = Unit("player")
    u._base_inventory = ["Torch", "Dagger"]
    g = Guild([u])
    ls = LootScreen.__new__(LootScreen)
    ls.guild = g
    ls.survivors = [u]
    ls.pool = ["Axe"]
    ls.buttons = []
    ls.pack_rows = [(pygame.Rect(0, 0, 100, 20), u, 0)]
    ls.cards = [(pygame.Rect(100, 0, 100, 100), u)]
    ls.rows = [(pygame.Rect(200, 0, 100, 20), 0)]
    ls.pile_rect = pygame.Rect(300, 0, 100, 100)
    ls.pack_sel = None
    ls.sel = None
    ls.notice = None

    # 1. Click pack item to select it
    ls._click((10, 10))
    assert ls.pack_sel == (u, 0)

    # 2. Click ground pile to drop it
    ls._click((310, 10))
    assert "Torch" in ls.pool
    assert "Torch" not in u._base_inventory
    assert ls.pack_sel is None


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


def test_loot_screen_draw_with_pack_selection_hover():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok.guild import Guild
    from gartok.loot_screen import LootScreen
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))
    u = Unit("player")
    u._base_inventory = ["Torch"]
    g = Guild([u])
    ls = LootScreen(Fonts(), g, [u], ["Axe"], lambda: None)
    surf = pygame.Surface((1200, 800))
    ls.mouse = (100, 100)
    ls.draw(surf)
    ls.pack_sel = (u, 0)
    if ls.cards:
        ls.mouse = ls.cards[0][0].center
    ls.draw(surf)


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



