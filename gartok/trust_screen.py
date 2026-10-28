"""The Bankers' trust mission: the window over `job_board.TrustBoard`, offered and turned in at the
City (Ankareth). Its own screen rather than the tanner's because the flavour (a test of trust, not a
gathering job) and the giver read as their own place, though `missions.accept` / `turn_in` are the same."""

from .job_board import TrustBoard
from .ui.mission_offer_screen import MissionOfferScreen


class TrustScreen(MissionOfferScreen, TrustBoard):
    title_text = "THE BANKERS"
    leave_label = "LEAVE THE BANKERS"

    def tutorial_key(self):
        return "trust"
