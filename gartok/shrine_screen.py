"""A hidden sanctuary's job board: the window over `job_board.ShrineBoard`."""

from . import world
from .job_board import ShrineBoard
from .ui.mission_offer_screen import MissionOfferScreen


class ShrineMissionScreen(MissionOfferScreen, ShrineBoard):
    leave_label = "LEAVE THE SANCTUARY"

    @property
    def VENDOR(self):
        return self.group.node, "shrine"

    @property
    def title_text(self):
        return world.node(self.group.node).name.upper()
