import sys
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
from gartok.unit import Unit
from gartok.guild_screen import GuildScreen


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


