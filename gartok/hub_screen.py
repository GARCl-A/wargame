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

    @classmethod
    def for_node(cls, fonts, guild, group, node, on_done, first=None):
        """Constructs a TabbedHubScreen dynamically from node.functions."""
        from . import world
        tabs = []
        if node.has("shop"):
            shop_label = "FOOD & DRINK" if node.id == "tavern" else "FARM" if node.id == "farm" else "SHOP"
            shop = MarketScreen(fonts, guild, list(group.members), node, on_done)
            tabs.append(("shop", shop_label, shop))
        if node.has("recruit"):
            from .taverna_screen import TavernaScreen
            tavern = TavernaScreen(fonts, guild, list(group.members), node, on_done, group=group)
            tabs.append(("tavern", "TAVERN", tavern))
        if node.has("stable"):
            from .stables_screen import StablesScreen
            stables = StablesScreen(fonts, guild, group, on_done)
            tabs.append(("stable", "STABLES", stables))
        if node.has("forge"):
            from .crafting_screen import CraftingScreen
            craft = CraftingScreen(fonts, guild, group, on_done, vendor=world.vendor(node.id, "forge"))
            tabs.append(("forge", "FORGE", craft))
        if node.has("tanner"):
            from .tanner_screen import TannerScreen
            jobs = TannerScreen(fonts, guild, group, on_done)
            tabs.append(("jobs", "JOBS", jobs))
        if node.has("apothecary"):
            from .medic_screen import MedicScreen
            from .apothecary_mission_screen import ApothecaryMissionScreen
            medic = MedicScreen(fonts, guild, group, on_done)
            jobs = ApothecaryMissionScreen(fonts, guild, group, on_done)
            tabs.append(("medic", "MEDIC", medic))
            tabs.append(("jobs", "JOBS", jobs))
        if node.has("library"):
            from .library_screen import LibraryScreen
            from .library_mission_screen import LibraryMissionScreen
            study = LibraryScreen(fonts, guild, group, on_done)
            jobs = LibraryMissionScreen(fonts, guild, group, on_done)
            tabs.append(("study", "STUDY", study))
            tabs.append(("jobs", "JOBS", jobs))

        if not tabs:
            return MarketScreen(fonts, guild, list(group.members), node, on_done)
        if len(tabs) == 1:
            return tabs[0][2]
        chosen = first if (first and any(k == first for k, _, _ in tabs)) else tabs[0][0]
        return cls(fonts, tabs, first=chosen)

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
