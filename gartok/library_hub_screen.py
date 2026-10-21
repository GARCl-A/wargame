"""The Library Hub: the shop, the writing desk and the jobs behind one row of tabs."""

from . import world
from .crafting_screen import CraftingScreen
from .hub_screen import TabbedHubScreen
from .library_mission_screen import LibraryMissionScreen
from .library_screen import LibraryScreen
from .ui.tokens import fonts as ui_fonts


class LibraryHubScreen(TabbedHubScreen):
    def __init__(self, fonts, guild, group, node, on_done):
        self.guild, self.group = guild, group
        self.shop_screen = LibraryScreen(fonts, guild, list(group.members), node, on_done)
        self.craft_screen = CraftingScreen(fonts, guild, group, on_done,
                                           title="THE LIBRARY (WRITE)",
                                           subtitle="write dictionaries and translate texts  ·  needs recipes and materials",
                                           station="scriptorium",
                                           vendor=world.vendor(node.id, "library"))
        self.jobs_screen = LibraryMissionScreen(ui_fonts(), guild, group, on_done)
        super().__init__(fonts, [("shop", "SHOP", self.shop_screen), ("craft", "WRITE", self.craft_screen),
                                 ("jobs", "JOBS", self.jobs_screen)], node=node, on_done=on_done)
