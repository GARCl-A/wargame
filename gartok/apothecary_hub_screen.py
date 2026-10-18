"""The Apothecary Hub: the shop, crafting, the Medic and jobs in a single tabbed screen."""

from . import world
from .apothecary_mission_screen import ApothecaryMissionScreen
from .crafting_screen import CraftingScreen
from .hub_screen import ShopHubScreen
from .medic_screen import MedicScreen
from .ui.tokens import fonts as ui_fonts


class ApothecaryHubScreen(ShopHubScreen):
    def __init__(self, fonts, guild, group, on_done, node=None):
        F = ui_fonts()
        craft = CraftingScreen(fonts, guild, group, on_done,
                               title="THE APOTHECARY",
                               subtitle="brew potions and draughts  ·  needs recipes and materials",
                               station="apothecary")
        super().__init__(fonts, guild, group, node or world.node("apothecary"),
                         [("medic", "MEDIC", MedicScreen(F, guild, group, on_done)),
                          ("craft", "CRAFT", craft),
                          ("jobs", "JOBS", ApothecaryMissionScreen(F, guild, group, on_done))],
                         on_done, first="shop")
