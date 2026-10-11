"""The Smithy: the smith's shop beside the forge."""

from . import world
from .crafting_screen import CraftingScreen
from .hub_screen import ShopHubScreen


class ForgeHubScreen(ShopHubScreen):
    def __init__(self, fonts, guild, group, node, on_done):
        craft = CraftingScreen(fonts, guild, group, on_done, vendor=world.vendor(node.id, "forge"))
        super().__init__(fonts, guild, group, node, [("craft", "FORGE", craft)], on_done)
