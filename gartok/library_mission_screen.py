"""The library's mission board: the window over `job_board.LibraryBoard`."""

from .job_board import LibraryBoard
from .ui.mission_offer_screen import MissionOfferScreen


class LibraryMissionScreen(MissionOfferScreen, LibraryBoard):
    VENDOR = ("library", "library")
    title_text = "THE LIBRARY (JOBS)"
    leave_label = "LEAVE"
