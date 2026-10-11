"""The Tannery: the tanner's shop beside the job the tanner offers."""

from .hub_screen import ShopHubScreen
from .tanner_screen import TannerScreen


class TannerHubScreen(ShopHubScreen):
    def __init__(self, fonts, guild, group, node, on_done):
        super().__init__(fonts, guild, group, node,
                         [("jobs", "JOBS", TannerScreen(fonts, guild, group, on_done))], on_done)
