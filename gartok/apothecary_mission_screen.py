"""The apothecary's mission board: a City NPC offering a paid, time-boxed job
(`missions.py`).
"""

from . import missions
from .ui.mission_offer_screen import MissionOfferScreen


class ApothecaryMissionScreen(MissionOfferScreen):
    GIVER = "apothecary"

    @property
    def title_text(self):
        return "THE APOTHECARY (JOBS)"

    @property
    def subtitle_text(self):
        return '"Need someone to fetch rare reagents from the wilds."'

    @property
    def accept_label(self):
        return "ACCEPT THE JOB"

    @property
    def leave_label(self):
        return "LEAVE"

    def get_template(self):
        return next((t for t in missions.TEMPLATES.values()
                     if t.giver == self.GIVER and t.node == self.group.node), None)

    def get_req_str(self, t):
        return f"goal: {t.goal_qty}x {t.goal_item}  ·  pay: {t.reward} copper  ·  deadline: {t.deadline_days} days"

    def get_status_str(self, t, progress, ready, days_left):
        return f"{progress} / {t.goal_qty} {t.goal_item}  ·  {days_left} day(s) left"

    def get_turn_in_label(self, t, progress, ready):
        return "TURN IN" if ready else f"NEED {t.goal_qty - progress} MORE"

    def get_success_notice(self, reward):
        return f"paid out {reward} copper, split across the group."
