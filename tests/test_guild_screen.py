import random
import sys

from tests.helpers import packed

try:
    import pygame
except ImportError:
    from unittest.mock import MagicMock
    mock_pg = MagicMock()
    mock_pg.Surface.side_effect = lambda size, *a, **kw: MagicMock(get_size=lambda: size)
    class MockRect:
        def __init__(self, x=0, y=0, w=0, h=0):
            self.x, self.y, self.w, self.h = int(x), int(y), int(w), int(h)
            self.width, self.height = self.w, self.h
            self.left, self.top = self.x, self.y
            self.right, self.bottom = self.x + self.w, self.y + self.h
            self.centerx, self.centery = self.x + self.w // 2, self.y + self.h // 2
            self.center = (self.centerx, self.centery)
            self.topleft = (self.x, self.y)
            self.topright = (self.right, self.y)
            self.size = (self.w, self.h)
        def collidepoint(self, pt):
            return self.left <= pt[0] <= self.right and self.top <= pt[1] <= self.bottom
        def clip(self, other):
            return self

    mock_pg.Rect = MockRect
    mock_font = MagicMock()
    mock_font.size.side_effect = lambda s: (len(s) * 8, 16)
    mock_font.get_height.return_value = 16
    mock_font.render.side_effect = lambda *a, **kw: MagicMock(get_rect=lambda **kw: MockRect(0, 0, 50, 16), get_width=lambda: 50, get_height=lambda: 16)
    mock_pg.font.SysFont.return_value = mock_font

    sys.modules["pygame"] = mock_pg
    sys.modules["pygame.base"] = MagicMock()
    pygame = mock_pg



from unittest.mock import MagicMock

from gartok.guild import Guild
from gartok.guild_screen import GuildScreen
from gartok.unit import Unit


def test_guild_screen_initialization_and_smart_pick():
    u0 = Unit("player")
    u1 = Unit("player")
    u1.combat_xp = 15
    u1.collect_levels()
    assert u1.pending_picks

    g = Guild([u0, u1])
    gs = GuildScreen(MagicMock(), g, on_back=lambda: None)
    assert gs.member == u1
    assert gs.tab == "members"
    assert gs.tutorial_key() == "guild.members"
    gs.tab = "reputations"
    assert gs.tutorial_key() == "guild.reputations"


def test_guild_screen_events_and_buttons():
    u = Unit("player")
    g = Guild([u])
    back_called = []
    level_called = []
    gs = GuildScreen(MagicMock(), g, on_back=lambda: back_called.append(True), on_level=lambda u: level_called.append(u))

    # Add mock buttons
    gs.buttons = [
        ("back", MagicMock(collidepoint=lambda pos: pos == (10, 10))),
        ("level", MagicMock(collidepoint=lambda pos: pos == (20, 20))),
        ("share_food", MagicMock(collidepoint=lambda pos: pos == (30, 30))),
    ]
    evt_back = MagicMock(type=pygame.MOUSEBUTTONUP, button=1, pos=(10, 10))
    gs.handle_event(evt_back)
    assert back_called == [True]

    evt_lvl = MagicMock(type=pygame.MOUSEBUTTONUP, button=1, pos=(20, 20))
    gs.handle_event(evt_lvl)
    assert level_called == [u]

    food_before = u.share_food
    evt_food = MagicMock(type=pygame.MOUSEBUTTONUP, button=1, pos=(30, 30))
    gs.handle_event(evt_food)
    assert u.share_food != food_before


def test_guild_screen_draw_members_and_reputations():
    u = Unit("player")
    u.study_target = "magic_missile"
    u.study_progress = 10
    g = Guild([u])
    gs = GuildScreen(MagicMock(), g, on_back=lambda: None, on_level=lambda u: None)

    if hasattr(pygame, "font") and hasattr(pygame.font, "init"):
        pygame.font.init()
    surf = pygame.Surface((1280, 800))

    # Draw members tab
    gs.tab = "members"
    gs.draw(surf)
    assert any(k == "level" for k, _ in gs.buttons)
    assert any(k == "back" for k, _ in gs.buttons)

    # Draw reputations tab
    gs.tab = "reputations"
    gs.draw(surf)
    assert any(k == "back" for k, _ in gs.buttons)


def test_guild_screen_reputations_scrolling():
    g = Guild([Unit("player")])
    gs = GuildScreen(MagicMock(), g, on_back=lambda: None)
    gs.tab = "reputations"
    surf_small = pygame.Surface((1280, 400))
    gs.draw(surf_small)
    assert gs._rep_max_scroll > 0

    # Mouse wheel down
    evt_wheel_down = MagicMock(type=pygame.MOUSEWHEEL, y=-1)
    gs.handle_event(evt_wheel_down)
    assert gs._rep_scroll == 36

    # Mouse wheel up
    evt_wheel_up = MagicMock(type=pygame.MOUSEWHEEL, y=1)
    gs.handle_event(evt_wheel_up)
    assert gs._rep_scroll == 0

    # Keyboard down / up
    evt_key_dn = MagicMock(type=pygame.KEYDOWN, key=pygame.K_DOWN)
    gs.handle_event(evt_key_dn)
    assert gs._rep_scroll == 36

    evt_key_up = MagicMock(type=pygame.KEYDOWN, key=pygame.K_UP)
    gs.handle_event(evt_key_up)
    assert gs._rep_scroll == 0




def _two_band_guild():
    from gartok.group import Group
    from gartok.orders import Order
    a, b, c = Unit("player"), Unit("player"), Unit("player")
    idle = Group([a, b], node="city", leader=a)
    busy = Group([c], node="iron_mine", leader=c)
    busy.order = Order(kind="work", hours=8)
    return Guild([a, b, c], groups=[idle, busy]), a, b, c


def _draw(gs, size=(1920, 1080)):
    pygame.font.init()
    gs.draw(pygame.Surface(size))


def test_guild_screen_filters_split_bands_by_order_and_alert():
    g, a, b, c = _two_band_guild()
    b.unfed_days = 3
    gs = GuildScreen(MagicMock(), g, on_back=lambda: None)

    def shown():
        _draw(gs)
        return {u.uid for _, u in gs.member_hits}

    gs.filter_mode = "idle"
    assert shown() == {a.uid, b.uid}
    gs.filter_mode = "busy"
    assert shown() == {c.uid}
    gs.filter_mode = "alerts"
    assert shown() == {b.uid}


def test_guild_screen_collapsing_a_band_hides_its_members():
    g, a, b, c = _two_band_guild()
    gs = GuildScreen(MagicMock(), g, on_back=lambda: None)
    _draw(gs)
    first_rect, gid = gs.accordion_hits[0]
    before = len(gs.member_hits)
    gs._click(first_rect.center)
    _draw(gs)
    assert gid in gs.collapsed_groups
    assert len(gs.member_hits) == before - 2


def test_guild_screen_vault_button_is_view_only_and_needs_a_chest():
    g, a, _, _ = _two_band_guild()
    opened = []
    gs = GuildScreen(MagicMock(), g, on_back=lambda: None, on_bank=lambda: opened.append(1))
    _draw(gs)
    assert not any(k == "vault" for k, _ in gs.buttons)

    g.bank.capacity = 20
    _draw(gs)
    gs.member = next(u for u in g.roster if g.group_of(u).node != "city")   # works from anywhere
    _draw(gs)
    vault = next(r for k, r in gs.buttons if k == "vault")
    gs._click(vault.center)
    assert opened == [1]


def test_guild_screen_distribute_needs_a_band_of_two():
    g, a, b, c = _two_band_guild()
    gs = GuildScreen(MagicMock(), g, on_back=lambda: None)
    gs.member = c
    _draw(gs)
    assert not any(k == "distribute" for k, _ in gs.buttons)
    gs.member = a
    _draw(gs)
    assert any(k == "distribute" for k, _ in gs.buttons)


def test_guild_screen_has_no_dead_view_map_button():
    g, *_ = _two_band_guild()
    gs = GuildScreen(MagicMock(), g, on_back=lambda: None)
    _draw(gs)
    assert not any(k == "view_map" for k, _ in gs.buttons)


def test_guild_screen_renders_at_small_window_and_scrolls_detail():
    g, *_ = _two_band_guild()
    gs = GuildScreen(MagicMock(), g, on_back=lambda: None)
    _draw(gs, (1024, 600))
    assert gs._detail_max_scroll > 0
    gs.mouse = (900, 300)
    gs.handle_event(MagicMock(type=pygame.MOUSEWHEEL, y=-1))
    assert gs._detail_scroll > 0


def test_bank_view_screen_lists_stash_without_any_move_button():
    from gartok.bank_view_screen import BankViewScreen
    g, *_ = _two_band_guild()
    g.bank.capacity = 30
    g.bank.items = packed(["Rope", "Rope", "Torch"])
    done = []
    scr = BankViewScreen(MagicMock(), g, on_done=lambda: done.append(1))
    pygame.font.init()
    scr.draw(pygame.Surface((1280, 720)))
    assert [k for k, _ in scr.buttons] == ["done"]
    scr._click(scr.buttons[0][1].center)
    assert done == [1]


def test_stat_breakdowns_sum_to_the_stat_they_explain():
    from gartok.combatant import Combatant
    for _ in range(40):
        u = Unit("player")
        c = Combatant(u)
        assert sum(v for _, v in u.ac_breakdown()) == c.ac
        assert sum(v for _, v in u.md_breakdown()) == c.mental_defense
        assert sum(v for _, v in u.speed_breakdown()) == c.speed
        assert sum(v for _, v in u.initiative_breakdown()) == c.initiative_bonus()


def test_stat_breakdown_names_armor_and_overload():
    u = Unit("player")
    u.equipped_armor = "Chainmail"
    u._derive_combat()
    assert any("Chainmail" in label for label, _ in u.ac_breakdown())
    u._base_inventory = packed(["Iron Bar"] * 99)
    u._derive_combat()
    assert u.encumbered
    assert ("overloaded", -1) in u.speed_breakdown()


def test_guild_screen_stat_tooltips_show_the_calculation():
    g, a, *_ = _two_band_guild()
    gs = GuildScreen(MagicMock(), g, on_back=lambda: None)
    gs.member = a
    seen = set()
    for x in range(480, 1200, 10):
        gs.mouse = (x, 300)
        _draw(gs)
        if isinstance(gs.tooltip, list):
            seen.add(gs.tooltip[0][0])
    assert {"HIT POINTS (HP)", "ARMOR CLASS", "MENTAL DEFENSE", "SPEED (SQUARES)", "INITIATIVE"} <= seen


def test_guild_tab_reports_slots_notices_and_holdings():
    from gartok.group import BASE_CAPACITY, Group
    random.seed(1)
    members = [Unit("player") for _ in range(BASE_CAPACITY + 4)]
    g = Guild(None, groups=[Group(members, node="city"), Group([Unit("player")], node="city")])
    gs = GuildScreen(MagicMock(), g, on_back=lambda: None)
    gs.tab = "guild"
    assert gs.tutorial_key() == "guild.overview"

    rows = gs._group_rows()
    assert [r["size"] for r in rows] == [len(members), 1]
    assert rows[0]["over"] == len(members) - rows[0]["capacity"] > 0 and rows[0]["note"] == ""

    assert [tone for _, tone in gs._notices()] == ["warn"]     # over capacity, no one has given notice yet

    leaver = g.groups[0].members[1]
    g.leaving[leaver.uid] = g.clock.day + 4
    assert "leaves the guild in 4 days" in gs._group_rows()[0]["note"]
    notices = gs._notices()
    assert [tone for _, tone in notices] == ["bad"]            # the notice replaces the generic warning
    assert leaver.name in notices[0][0] and "4 days" in notices[0][0]

    holdings = {h["name"]: h for h in gs._holdings()}
    assert holdings["City house"]["status"] == "NOT OWNED"
    assert holdings["The Claim"]["status"] == "NOT CLAIMED"
    g.house.owned = True
    g.wilds_claim_stage, g.wilds_claim_owner = "ESTABLISHED", "guild"
    holdings = {h["name"]: h for h in gs._holdings()}
    assert holdings["City house"]["status"] == "OWNED"
    assert holdings["The Claim"]["status"] == "UNGUARDED" and holdings["The Claim"]["tone"] == "warn"


def test_every_guild_tab_has_a_registered_tutorial_card():
    from gartok.tutorial import TUTORIALS
    gs = GuildScreen.__new__(GuildScreen)
    for tab in ("members", "guild", "reputations"):
        gs.tab = tab
        assert gs.tutorial_key() in TUTORIALS


def test_guild_screen_draw_unarmed_unarmored_member():
    u = Unit("player")
    u.equipped_weapon = None
    u.equipped_armor = None
    u.equipped_offhand = None
    g = Guild([u])
    gs = GuildScreen(MagicMock(), g, on_back=lambda: None)
    if hasattr(pygame, "font") and hasattr(pygame.font, "init"):
        pygame.font.init()
    surf = pygame.Surface((1280, 800))
    gs.draw(surf)


def test_manage_gear_opens_for_the_selected_members_group_only():
    a, b = Unit("player"), Unit("player")
    g = Guild([a, b])
    g.split_group(g.groups[0], [b])
    opened = []
    gs = GuildScreen(MagicMock(), g, on_back=lambda: None, on_manage=opened.append)
    gs.member = a
    gs.buttons = [("manage", MagicMock(collidepoint=lambda pos: True))]
    gs._press("manage")
    assert opened == [g.group_of(a)]


def test_gear_screen_scoped_to_a_group_lists_only_its_members():
    from gartok.gear_screen import GearScreen
    from gartok.group import Group
    a, b = Unit("player"), Unit("player")
    ga, gb = Group([a], node="city"), Group([b], node="road")
    g = Guild(None, groups=[ga, gb])
    gs = GearScreen(MagicMock(), g, on_back=lambda: None, group=ga)
    assert list(gs.roster) == [a]
    assert gs.pinned == [a]
    assert list(GearScreen(MagicMock(), g, on_back=lambda: None).roster) == [a, b]
