"""The Library's mission board: a NPC offering a paid, time-boxed job (`missions.py`).
"""

import random
from . import missions
from .ui.mission_offer_screen import MissionOfferScreen


class LibraryMissionScreen(MissionOfferScreen):
    GIVER = "library"

    @property
    def title_text(self):
        return "THE SCHOLARS (JOBS)"

    @property
    def subtitle_text(self):
        return '"We seek lost knowledge from the world outside."'

    @property
    def accept_label(self):
        return "ACCEPT THE JOB"

    @property
    def leave_label(self):
        return "LEAVE"

    def get_template(self):
        # Pick an unaccepted library mission randomly, or none if all accepted
        offers = missions.offers_at(self.guild, self.group.node)
        library_offers = [t for t in offers if t.giver == self.GIVER]
        if not library_offers:
            return None
        # We can just return the first one available
        return library_offers[0]

    def get_req_str(self, t):
        return f"goal: {t.goal_qty}x {t.goal_item}  ·  pay: {t.reward} copper  ·  deadline: {t.deadline_days} days"

    def get_status_str(self, t, progress, ready, days_left):
        return f"{progress} / {t.goal_qty} {t.goal_item}  ·  {days_left} day(s) left"

    def get_turn_in_label(self, t, progress, ready):
        return "TURN IN" if ready else f"NEED {t.goal_qty - progress} MORE"

    def get_success_notice(self, reward):
        return f"paid out {reward} copper, split across the group."
