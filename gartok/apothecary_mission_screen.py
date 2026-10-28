"""The apothecary's mission board: the window over `job_board.ApothecaryBoard`."""

from .job_board import ApothecaryBoard
from .ui.mission_offer_screen import MissionOfferScreen


class ApothecaryMissionScreen(MissionOfferScreen, ApothecaryBoard):
    title_text = "THE APOTHECARY (JOBS)"
    leave_label = "LEAVE"
