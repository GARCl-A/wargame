"""The tanner's window over `job_board.TannerBoard`: a City NPC offering a paid, time-boxed job
(`missions.py`) -- distinct from the market (buy/sell) and the bank (shared storage)."""

from .job_board import TannerBoard
from .ui.mission_offer_screen import MissionOfferScreen


class TannerScreen(MissionOfferScreen, TannerBoard):
    VENDOR = ("tanner", "tanner")
    title_text = "THE TANNER"
    leave_label = "LEAVE THE TANNER"
