"""A node's screens behind one row of tabs: the shop beside whatever else the place does.

`TabbedHubScreen` holds `(key, label, screen)` tabs and forwards events, updates and
drawing to the active one; the tab buttons sit in the header's top-right corner, left to
right in the order given. A tab that is a `MarketScreen` is told how much of its header
the row takes (`header_reserve`) so its purse does not slide under the buttons.
`ShopHubScreen` is the Smith's, the Tanner's and the Apothecary's: the node's shop first,
then the rest.
"""

import pygame

from .market_screen import MarketScreen
from .screen import Screen
from .ui.primitives import draw_button
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

TAB_W = 120


class TabbedHubScreen(Screen):
    native = True

    def __init__(self, fonts, tabs, first=None):
        super().__init__()
        self.fonts = fonts
        self._F = ui_fonts()
        self.tabs = list(tabs)
        self.tab = first or self.tabs[0][0]
        self.buttons = []
        for _key, _label, screen in self.tabs:
            if isinstance(screen, MarketScreen):
                screen.header_reserve = len(self.tabs) * (TAB_W + T.S) + T.S * 2

    def active_screen(self):
        return next(s for k, _label, s in self.tabs if k == self.tab)

    def tutorial_key(self):
        return self.active_screen().tutorial_key()

    def handle_escape(self):
        return self.active_screen().handle_escape()

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in self.buttons:
                if rect.collidepoint(event.pos):
                    self.tab = key
                    return
        self.active_screen().mouse = self.mouse
        self.active_screen().handle_event(event)

    def update(self, dt):
        self.active_screen().update(dt)

    def draw(self, screen):
        active = self.active_screen()
        active.mouse = self.mouse
        active.draw(screen)
        self._hot = getattr(active, "_hot", False)

        m = T.S * 3
        x = screen.get_width() - m - TAB_W - T.S * 5      # room for the tutorial `?` badge
        self.buttons = []
        for key, label, _screen in reversed(self.tabs):
            rect = pygame.Rect(x, m, TAB_W, 32)
            draw_button(screen, self._F, rect, label, primary=self.tab == key,
                        enabled=self.tab != key, mpos=self.mouse)
            if self.tab != key:
                self.buttons.append((key, rect))
            self._hot = self._hot or rect.collidepoint(self.mouse)
            x -= TAB_W + T.S


class ShopHubScreen(TabbedHubScreen):
    """The node's shop as the first tab, then `others` (`(key, label, screen)`)."""

    def __init__(self, fonts, guild, group, node, others, on_done, first=None):
        shop = MarketScreen(fonts, guild, list(group.members), node, on_done)
        super().__init__(fonts, [("shop", "SHOP", shop), *others], first=first)
